import json
import traceback
from datetime import datetime
from odoo import models, fields, api, _


class AutomationDebugLog(models.Model):
    _name = 'automation.debug.log'
    _description = 'Automation Rule Debug Log'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    rule_id = fields.Many2one(
        comodel_name='base.automation',
        string='Automation Rule',
        ondelete='cascade',
        required=True,
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model',
        related='rule_id.model_id',
        store=True,
    )
    model_name = fields.Char(
        string='Model Name',
        related='rule_id.model_id.model',
        store=True,
    )
    record_id = fields.Integer(string='Record ID', default=0)
    record_name = fields.Char(string='Record Name')
    trigger = fields.Char(string='Trigger Used')
    execution_mode = fields.Selection(
        selection=[
            ('simulation', 'Simulation (Dry Run)'),
            ('real', 'Real Execution'),
        ],
        string='Execution Mode',
        default='simulation',
        required=True,
    )
    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('partial', 'Partial'),
            ('skipped', 'Skipped'),
        ],
        string='Status',
        default='skipped',
        required=True,
    )
    duration_ms = fields.Float(string='Duration (ms)', digits=(10, 2))
    log_lines = fields.One2many(
        comodel_name='automation.debug.log.line',
        inverse_name='log_id',
        string='Execution Steps',
    )
    summary = fields.Text(string='Summary')
    error_message = fields.Text(string='Error Message')
    suggestions = fields.Text(string='Suggestions')
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Triggered By',
        default=lambda self: self.env.user,
    )
    domain_result = fields.Boolean(
        string='Domain Matched',
        default=False,
    )
    domain_evaluated = fields.Text(string='Evaluated Domain')
    actions_count = fields.Integer(
        string='Actions Count',
        compute='_compute_actions_count',
        store=True,
    )
    actions_success = fields.Integer(
        string='Actions Succeeded',
        compute='_compute_actions_count',
        store=True,
    )

    @api.depends('rule_id', 'create_date', 'execution_mode')
    def _compute_display_name(self):
        for rec in self:
            rule_name = rec.rule_id.name if rec.rule_id else 'Unknown'
            mode = 'SIM' if rec.execution_mode == 'simulation' else 'REAL'
            ts = rec.create_date.strftime('%Y-%m-%d %H:%M') if rec.create_date else ''
            rec.display_name = f'[{mode}] {rule_name} — {ts}'

    @api.depends('log_lines', 'log_lines.step_type', 'log_lines.state')
    def _compute_actions_count(self):
        for rec in self:
            action_lines = rec.log_lines.filtered(lambda l: l.step_type == 'action')
            rec.actions_count = len(action_lines)
            rec.actions_success = len(action_lines.filtered(lambda l: l.state == 'success'))

    def action_view_record(self):
        self.ensure_one()
        if not self.model_name or not self.record_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.model_name,
            'res_id': self.record_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_rerun_simulation(self):
        self.ensure_one()
        wizard = self.env['automation.test.wizard'].create({
            'rule_id': self.rule_id.id,
            'record_id_int': self.record_id,
            'execution_mode': 'simulation',
        })
        return wizard.action_open_wizard()


class AutomationDebugLogLine(models.Model):
    _name = 'automation.debug.log.line'
    _description = 'Automation Debug Log Line'
    _order = 'sequence asc'

    log_id = fields.Many2one(
        comodel_name='automation.debug.log',
        string='Debug Log',
        ondelete='cascade',
        required=True,
        index=True,
    )
    sequence = fields.Integer(string='Step #', default=10)
    step_type = fields.Selection(
        selection=[
            ('info', 'Info'),
            ('trigger', 'Trigger Check'),
            ('domain', 'Domain Filter'),
            ('condition', 'Extra Condition'),
            ('action', 'Action'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        string='Step Type',
        default='info',
        required=True,
    )
    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
            ('info', 'Info'),
        ],
        string='Result',
        default='info',
        required=True,
    )
    title = fields.Char(string='Step Title', required=True)
    detail = fields.Text(string='Detail')
    technical_info = fields.Text(string='Technical Info')
    duration_ms = fields.Float(string='Duration (ms)', digits=(10, 2))
    icon = fields.Char(
        string='Icon',
        compute='_compute_icon',
    )

    @api.depends('step_type', 'state')
    def _compute_icon(self):
        icon_map = {
            ('info', 'info'): 'fa-info-circle',
            ('trigger', 'success'): 'fa-bolt',
            ('trigger', 'failed'): 'fa-bolt',
            ('domain', 'success'): 'fa-filter',
            ('domain', 'failed'): 'fa-filter',
            ('condition', 'success'): 'fa-check-circle',
            ('condition', 'failed'): 'fa-times-circle',
            ('action', 'success'): 'fa-play-circle',
            ('action', 'failed'): 'fa-exclamation-circle',
            ('warning', 'info'): 'fa-exclamation-triangle',
            ('error', 'failed'): 'fa-times-circle',
        }
        for rec in self:
            rec.icon = icon_map.get((rec.step_type, rec.state), 'fa-circle')
