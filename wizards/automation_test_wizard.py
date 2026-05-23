# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AutomationTestWizard(models.TransientModel):
    _name = 'automation.test.wizard'
    _description = 'Automation Rule Test Wizard'

    rule_id = fields.Many2one(
        comodel_name='base.automation',
        string='Automation Rule',
        required=True,
        ondelete='cascade',
    )
    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model',
        related='rule_id.model_id',
        readonly=True,
    )
    model_name = fields.Char(
        string='Technical Model Name',
        related='rule_id.model_id.model',
        readonly=True,
    )
    record_id_int = fields.Integer(
        string='Record ID',
        required=True,
        help='Enter the ID of the record you want to test this rule against.',
    )
    record_preview = fields.Char(
        string='Record Preview',
        compute='_compute_record_preview',
        readonly=True,
    )
    execution_mode = fields.Selection(
        selection=[
            ('simulation', '🔵 Simulation (Dry Run — no real changes)'),
            ('real', '🔴 Real Execution (applies actual changes)'),
        ],
        string='Execution Mode',
        default='simulation',
        required=True,
    )
    rule_summary = fields.Html(
        string='Rule Summary',
        compute='_compute_rule_summary',
        readonly=True,
    )
    health_issues = fields.Text(
        string='Health Issues',
        compute='_compute_health_issues',
        readonly=True,
    )
    has_health_issues = fields.Boolean(
        compute='_compute_health_issues',
        readonly=True,
    )

    @api.depends('rule_id', 'model_name', 'record_id_int')
    def _compute_record_preview(self):
        for rec in self:
            if rec.model_name and rec.record_id_int:
                try:
                    obj = self.env[rec.model_name].browse(rec.record_id_int)
                    obj.ensure_one()
                    name = obj.display_name or str(rec.record_id_int)
                    rec.record_preview = f'✅ {name}'
                except Exception:
                    rec.record_preview = f'❌ Record ID {rec.record_id_int} not found'
            else:
                rec.record_preview = ''

    @api.depends('rule_id')
    def _compute_rule_summary(self):
        for rec in self:
            if not rec.rule_id:
                rec.rule_summary = ''
                continue
            rule = rec.rule_id
            trigger = getattr(rule, 'trigger', 'unknown')
            actions = rule.action_server_ids
            action_list = ''.join(
                f'<li>{a.name} ({a.state})</li>' for a in actions
            ) if actions else '<li><em>No actions defined</em></li>'

            domain_html = (
                f'<code>{rule.filter_domain}</code>'
                if rule.filter_domain and rule.filter_domain != '[]'
                else '<em>None (matches all records)</em>'
            )

            rec.rule_summary = f"""
<div class="o_field_html">
    <table class="table table-sm table-bordered">
        <tr><th>Rule Name</th><td>{rule.name}</td></tr>
        <tr><th>Model</th><td>{rule.model_id.name} ({rule.model_id.model})</td></tr>
        <tr><th>Trigger</th><td>{trigger}</td></tr>
        <tr><th>Active</th><td>{'✅ Yes' if rule.active else '❌ No'}</td></tr>
        <tr><th>Filter Domain</th><td>{domain_html}</td></tr>
        <tr><th>Actions</th><td><ul>{action_list}</ul></td></tr>
    </table>
</div>
"""

    @api.depends('rule_id')
    def _compute_health_issues(self):
        for rec in self:
            if not rec.rule_id:
                rec.health_issues = ''
                rec.has_health_issues = False
                continue
            issues = rec.rule_id._collect_health_issues()
            rec.has_health_issues = bool(issues)
            if issues:
                rec.health_issues = '\n'.join(f'⚠️ {i}' for i in issues)
            else:
                rec.health_issues = '✅ No health issues detected.'

    @api.constrains('record_id_int')
    def _check_record_id(self):
        for rec in self:
            if rec.record_id_int <= 0:
                raise ValidationError(_('Record ID must be a positive integer.'))

    def action_run_test(self):
        self.ensure_one()
        if not self.model_name:
            raise UserError(_('The selected rule has no model configured.'))

        if self.execution_mode == 'real':
            pass

        log = self.rule_id.run_simulation(
            record_id=self.record_id_int,
            execution_mode=self.execution_mode,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Debug Log'),
            'res_model': 'automation.debug.log',
            'res_id': log.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Test Automation Rule'),
            'res_model': 'automation.test.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_health_check_only(self):
        self.ensure_one()
        return self.rule_id.action_health_check()
