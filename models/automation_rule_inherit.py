import time
import json
import traceback
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class BaseAutomationInherit(models.Model):
    _inherit = 'base.automation'

    debug_log_ids = fields.One2many(
        comodel_name='automation.debug.log',
        inverse_name='rule_id',
        string='Debug Logs',
    )
    debug_log_count = fields.Integer(
        string='Debug Logs',
        compute='_compute_debug_log_count',
    )
    last_debug_state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('partial', 'Partial'),
            ('skipped', 'Skipped'),
            ('never', 'Never Tested'),
        ],
        string='Last Test Result',
        compute='_compute_last_debug_state',
    )

    @api.depends('debug_log_ids')
    def _compute_debug_log_count(self):
        for rec in self:
            rec.debug_log_count = len(rec.debug_log_ids)

    @api.depends('debug_log_ids', 'debug_log_ids.state')
    def _compute_last_debug_state(self):
        for rec in self:
            last = rec.debug_log_ids[:1]
            rec.last_debug_state = last.state if last else 'never'

    def action_open_debugger(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Test Automation Rule'),
            'res_model': 'automation.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_rule_id': self.id,
            },
        }

    def action_view_debug_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Debug Logs — %s') % self.name,
            'res_model': 'automation.debug.log',
            'view_mode': 'list,form',
            'domain': [('rule_id', '=', self.id)],
            'context': {'default_rule_id': self.id},
        }

    def action_health_check(self):
        self.ensure_one()
        issues = self._collect_health_issues()
        if not issues:
            message = _('✅ No issues found. This rule looks healthy!')
        else:
            lines = '\n'.join(f'• {i}' for i in issues)
            message = _('⚠️ Found %d issue(s):\n\n%s') % (len(issues), lines)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rule Health Check'),
                'message': message,
                'type': 'warning' if issues else 'success',
                'sticky': True,
            },
        }

    def _collect_health_issues(self):
        self.ensure_one()
        issues = []

        if not self.active:
            issues.append(_('Rule is inactive — it will never trigger.'))

        if not self.model_id:
            issues.append(_('No model selected.'))
            return issues

        # Check filter_domain
        if self.filter_domain and self.filter_domain not in ('[]', False):
            try:
                domain = safe_eval(self.filter_domain)
                if not isinstance(domain, list):
                    issues.append(_('Filter domain is not a valid list.'))
                else:
                    # Validate field names exist
                    model_fields = self.env[self.model_id.model]._fields
                    for leaf in domain:
                        if isinstance(leaf, (list, tuple)) and len(leaf) >= 1:
                            fname = leaf[0].split('.')[0]
                            if fname not in ('|', '&', '!') and fname not in model_fields:
                                issues.append(
                                    _('Field "%s" in filter domain does not exist on %s.')
                                    % (fname, self.model_id.model)
                                )
            except Exception as e:
                issues.append(_('Filter domain has syntax error: %s') % str(e))

        # Check filter_pre_domain
        if self.filter_pre_domain and self.filter_pre_domain not in ('[]', False):
            try:
                safe_eval(self.filter_pre_domain)
            except Exception as e:
                issues.append(_('Before-update domain has syntax error: %s') % str(e))

        # Check actions
        if not self.action_server_ids:
            issues.append(_('No server actions defined — rule does nothing.'))

        # Check trigger-specific issues
        trigger = getattr(self, 'trigger', None)
        if trigger == 'on_time' and not self.trg_date_id:
            issues.append(_('Time-based trigger has no date field selected.'))

        if trigger in ('on_write', 'on_write_or_create') and not getattr(self, 'filter_pre_domain', False):
            issues.append(_(
                'Write trigger without a before-update domain: '
                'rule fires on every write, not just field changes.'
            ))

        return issues

    # -------------------------------------------------------------------------
    # Core Simulation Engine
    # -------------------------------------------------------------------------

    def run_simulation(self, record_id, execution_mode='simulation'):
        self.ensure_one()
        log_lines = []
        start_time = time.time()
        overall_state = 'skipped'
        error_msg = False
        suggestions = []

        log = self.env['automation.debug.log'].create({
            'rule_id': self.id,
            'record_id': record_id,
            'trigger': getattr(self, 'trigger', 'unknown'),
            'execution_mode': execution_mode,
            'state': 'skipped',
        })

        try:
            # Step 1: Validate record exists
            seq = 1
            record = False
            try:
                record = self.env[self.model_id.model].browse(record_id)
                record.ensure_one()  # will raise if not found
                _ = record.display_name  # force load
                log.write({'record_name': record.display_name})
                log_lines.append({
                    'log_id': log.id,
                    'sequence': seq,
                    'step_type': 'info',
                    'state': 'success',
                    'title': _('Record Located'),
                    'detail': _('Found record: %s (ID: %s) on model %s')
                              % (record.display_name, record_id, self.model_id.model),
                })
            except Exception as e:
                log_lines.append({
                    'log_id': log.id,
                    'sequence': seq,
                    'step_type': 'error',
                    'state': 'failed',
                    'title': _('Record Not Found'),
                    'detail': _('Could not load record ID %s on %s: %s')
                              % (record_id, self.model_id.model, str(e)),
                })
                overall_state = 'failed'
                error_msg = str(e)
                suggestions.append(_('Make sure the record ID exists and you have access to it.'))
                self._finalise_log(log, log_lines, overall_state, start_time, error_msg, suggestions)
                return log

            seq += 1

            # Step 2: Check rule is active
            if not self.active:
                log_lines.append({
                    'log_id': log.id,
                    'sequence': seq,
                    'step_type': 'warning',
                    'state': 'skipped',
                    'title': _('Rule is Inactive'),
                    'detail': _('This automation rule is currently disabled.'),
                })
                suggestions.append(_('Enable the rule to allow it to trigger.'))
                overall_state = 'skipped'
                self._finalise_log(log, log_lines, overall_state, start_time, error_msg, suggestions)
                return log

            log_lines.append({
                'log_id': log.id,
                'sequence': seq,
                'step_type': 'info',
                'state': 'success',
                'title': _('Rule is Active'),
                'detail': _('The rule "%s" is active and enabled.') % self.name,
            })
            seq += 1

            # Step 3: Evaluate filter_domain
            domain_matched = True
            domain_info = ''
            if self.filter_domain and self.filter_domain not in ('[]', False, ''):
                t0 = time.time()
                try:
                    domain = safe_eval(self.filter_domain)
                    matching = self.env[self.model_id.model].search(
                        [('id', '=', record_id)] + domain
                    )
                    domain_matched = bool(matching)
                    domain_info = _('Domain: %s — Match: %s') % (self.filter_domain, domain_matched)
                    log_lines.append({
                        'log_id': log.id,
                        'sequence': seq,
                        'step_type': 'domain',
                        'state': 'success' if domain_matched else 'failed',
                        'title': _('Filter Domain') + (' ✅' if domain_matched else ' ❌'),
                        'detail': domain_info,
                        'technical_info': str(domain),
                        'duration_ms': (time.time() - t0) * 1000,
                    })
                    log.domain_result = domain_matched
                    log.domain_evaluated = domain_info
                    if not domain_matched:
                        suggestions.append(
                            _('The record does not match the filter domain. '
                              'Check field values or adjust the domain.')
                        )
                except Exception as e:
                    log_lines.append({
                        'log_id': log.id,
                        'sequence': seq,
                        'step_type': 'error',
                        'state': 'failed',
                        'title': _('Filter Domain Error'),
                        'detail': str(e),
                        'technical_info': traceback.format_exc(),
                    })
                    domain_matched = False
                    suggestions.append(_('Fix the filter domain syntax error: %s') % str(e))
            else:
                log_lines.append({
                    'log_id': log.id,
                    'sequence': seq,
                    'step_type': 'domain',
                    'state': 'success',
                    'title': _('No Filter Domain'),
                    'detail': _('Rule has no filter domain — applies to all records.'),
                })
                log.domain_result = True

            seq += 1

            if not domain_matched:
                overall_state = 'skipped'
                self._finalise_log(log, log_lines, overall_state, start_time, error_msg, suggestions)
                return log

            # Step 4: Evaluate extra condition (filter_pre_domain for write triggers)
            trigger = getattr(self, 'trigger', '')
            if trigger in ('on_write', 'on_write_or_create') and \
               self.filter_pre_domain and self.filter_pre_domain not in ('[]', False, ''):
                t0 = time.time()
                try:
                    pre_domain = safe_eval(self.filter_pre_domain)
                    log_lines.append({
                        'log_id': log.id,
                        'sequence': seq,
                        'step_type': 'condition',
                        'state': 'info',
                        'title': _('Before-Update Domain (simulation)'),
                        'detail': _(
                            'Pre-update domain: %s\n'
                            'Note: In simulation mode the pre-update state cannot be replicated.'
                        ) % self.filter_pre_domain,
                        'technical_info': str(pre_domain),
                        'duration_ms': (time.time() - t0) * 1000,
                    })
                    suggestions.append(
                        _('The before-update domain requires a real write event to be fully validated.')
                    )
                except Exception as e:
                    log_lines.append({
                        'log_id': log.id,
                        'sequence': seq,
                        'step_type': 'error',
                        'state': 'failed',
                        'title': _('Before-Update Domain Error'),
                        'detail': str(e),
                    })
                seq += 1

            # Step 5: Evaluate each server action
            action_ids = self.action_server_ids
            if not action_ids:
                log_lines.append({
                    'log_id': log.id,
                    'sequence': seq,
                    'step_type': 'warning',
                    'state': 'skipped',
                    'title': _('No Actions Defined'),
                    'detail': _('The rule has no server actions to execute.'),
                })
                overall_state = 'skipped'
                suggestions.append(_('Add at least one server action to this rule.'))
            else:
                action_results = []
                for action in action_ids:
                    t0 = time.time()
                    action_state = 'success'
                    action_detail = ''
                    action_tech = ''
                    try:
                        action_detail = self._describe_action(action)
                        if execution_mode == 'real':
                            action.with_context(active_id=record.id, active_ids=[record.id]).run()
                            action_detail += _('\n✅ Action executed successfully (REAL mode).')
                        else:
                            # Dry-run: just describe what would happen
                            action_detail += _('\n🔵 Simulation mode: action NOT executed.')
                    except Exception as e:
                        action_state = 'failed'
                        action_detail += _('\n❌ Error: %s') % str(e)
                        action_tech = traceback.format_exc()
                        suggestions.append(
                            _('Action "%s" failed: %s') % (action.name, str(e))
                        )

                    dur = (time.time() - t0) * 1000
                    log_lines.append({
                        'log_id': log.id,
                        'sequence': seq,
                        'step_type': 'action',
                        'state': action_state,
                        'title': _('Action: %s') % action.name,
                        'detail': action_detail,
                        'technical_info': action_tech or False,
                        'duration_ms': dur,
                    })
                    action_results.append(action_state)
                    seq += 1

                if all(s == 'success' for s in action_results):
                    overall_state = 'success'
                elif any(s == 'success' for s in action_results):
                    overall_state = 'partial'
                else:
                    overall_state = 'failed'

            # Step 6: Health check suggestions
            health_issues = self._collect_health_issues()
            if health_issues:
                for issue in health_issues:
                    if issue not in suggestions:
                        suggestions.append(issue)

        except Exception as e:
            overall_state = 'failed'
            error_msg = str(e)
            log_lines.append({
                'log_id': log.id,
                'sequence': 999,
                'step_type': 'error',
                'state': 'failed',
                'title': _('Unexpected Error'),
                'detail': str(e),
                'technical_info': traceback.format_exc(),
            })
            suggestions.append(_('An unexpected error occurred. Check technical info for details.'))

        self._finalise_log(log, log_lines, overall_state, start_time, error_msg, suggestions)
        return log

    def _describe_action(self, action):
        state = action.state
        desc_map = {
            'object_create': _('📝 Create a new record on model: %s') % (action.crud_model_id.name if action.crud_model_id else '?'),
            'object_write': _('✏️ Update fields on the record'),
            'mail_post': _('📧 Send email/message'),
            'followers': _('👥 Manage followers'),
            'next_activity': _('📅 Schedule an activity'),
            'sms': _('💬 Send SMS'),
            'code': _('⚙️ Execute Python code:\n%s') % (action.code or ''),
            'multi': _('🔁 Run multiple actions (%d)') % len(action.child_ids),
        }
        base = desc_map.get(state, _('Action type: %s') % state)
        return _('Action "%s" would:\n%s') % (action.name, base)

    def _finalise_log(self, log, log_lines, overall_state, start_time, error_msg, suggestions):
        duration = (time.time() - start_time) * 1000
        # Create all lines in one batch
        if log_lines:
            # Remove log_id from lines since we set it separately to avoid issues
            lines_to_create = []
            for line in log_lines:
                line_vals = dict(line)
                line_vals['log_id'] = log.id
                lines_to_create.append(line_vals)
            self.env['automation.debug.log.line'].create(lines_to_create)

        summary_parts = [
            _('Rule: %s') % self.name,
            _('Status: %s') % overall_state.upper(),
            _('Steps: %d') % len(log_lines),
            _('Duration: %.1f ms') % duration,
        ]

        log.write({
            'state': overall_state,
            'duration_ms': duration,
            'error_message': error_msg or False,
            'suggestions': '\n'.join(f'• {s}' for s in suggestions) if suggestions else False,
            'summary': '\n'.join(summary_parts),
        })
