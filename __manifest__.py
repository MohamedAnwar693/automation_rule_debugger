# -*- coding: utf-8 -*-
{
    'name': 'Automation Rule Testing & Debugger',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Test, simulate and debug automation rules with step-by-step execution logs',
    'description': """
        Automation Rule Testing & Debugger
        ====================================
        This module extends Odoo's automation rules with:
        - Live rule simulation on any record
        - Step-by-step execution log viewer
        - Rule health checker & suggestions
        - Trigger condition evaluator
        - Action dry-run mode (no real writes)
        - Execution history dashboard
    """,
    'author': 'Mohamed Anwar',
    'depends': ['base_automation', 'base_setup', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/automation_debugger_data.xml',
        'views/automation_debug_log_views.xml',
        'views/automation_rule_views.xml',
        'wizards/automation_test_wizard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'automation_rule_debugger/static/src/css/debugger.css',
            'automation_rule_debugger/static/src/js/debugger_widget.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
