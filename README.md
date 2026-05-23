# Automation Rule Testing & Debugger

**Odoo Module — Version 19.0.1.0.0**
**Author:** Mohamed Anwar
**Category:** Technical

---

## Overview

The **Automation Rule Testing & Debugger** module solves one of the most frustrating problems in Odoo administration: you create an automation rule, deploy it, and then it silently does nothing — with no feedback on *why*.

This module gives you a full testing and debugging environment directly inside Odoo. You can simulate a rule against any record, walk through every execution step in a detailed log, run automated health checks, and get actionable suggestions when something is wrong — all without leaving the automation rule form.

---

## The Problem It Solves

Odoo's built-in automation rules (`Settings → Technical → Automation → Automated Actions`) are powerful but completely opaque when they fail. Common pain points:

- A rule doesn't trigger and there's no error message anywhere.
- The filter domain looks correct but the rule still skips records.
- A server action fails silently in production.
- You can't test a rule without actually writing to the database.
- Debugging means adding `_logger.info` calls in custom code or tailing server logs.

---

## Features

### 🧪 Rule Simulation (Dry Run)
Test any automation rule against any record without making real changes. The simulation engine:
- Verifies the record exists and is accessible.
- Checks whether the rule is active.
- Evaluates the filter domain against the chosen record.
- Evaluates the before-update domain (for write triggers).
- Describes exactly what each server action *would* do — without executing it.

### 🔴 Real Execution Mode
When you're confident the rule is correct, switch to **Real Execution** mode to fire the rule's server actions against the record for real — with full logging of what happened.

### 📋 Step-by-Step Execution Log
Every test run creates a detailed `automation.debug.log` record with individual log lines for each step:

| Step Type | What it covers |
|---|---|
| `Info` | General information (record found, rule active) |
| `Trigger Check` | Whether the trigger condition is met |
| `Domain Filter` | Evaluation of the filter domain |
| `Extra Condition` | Before-update domain for write triggers |
| `Action` | Each server action and its outcome |
| `Warning` | Non-fatal issues |
| `Error` | Failures with full traceback |

Each line shows: step type, result (success/failed/skipped), title, detail message, technical info, and execution duration in milliseconds.

### 🩺 Health Check
One-click rule analysis that scans for common configuration problems:

- Rule is inactive.
- No model selected.
- Filter domain has syntax errors.
- Filter domain references fields that don't exist on the model.
- Before-update domain has syntax errors.
- No server actions defined (rule does nothing).
- Time-based trigger has no date field selected.
- Write trigger has no before-update domain (fires on every write).

### 💡 Smart Suggestions
When a test run fails or is skipped, the debugger automatically generates human-readable suggestions explaining what to fix and how.

### 📊 Debug Log History Dashboard
All test runs are stored and accessible:
- From the automation rule form via a smart button showing the log count.
- From the global menu at **Settings → Technical → Automation Debug Logs**.
- Filterable by rule, model, status, execution mode, and date.
- Groupable by rule, model, status, or mode.

### 🏷️ Last Test Result Badge
The automation rules list view shows a **Last Test** badge for each rule, coloured by outcome (`success`, `failed`, `partial`, `skipped`, `never tested`), so you can see at a glance which rules have been validated.

---

## Installation

### Requirements
- Odoo **19.0** (Community or Enterprise)
- Depends on: `base_automation`, `base_setup`, `mail`

### Steps

1. Copy the `automation_rule_debugger` folder into your Odoo addons directory:
   ```
   /path/to/your/odoo/addons/automation_rule_debugger/
   ```

2. Restart the Odoo server:
   ```bash
   sudo systemctl restart odoo
   # or
   python odoo-bin -c odoo.conf --stop-after-init
   python odoo-bin -c odoo.conf
   ```

3. Go to **Apps** in your Odoo backend.

4. Click **Update Apps List** (if the module doesn't appear).

5. Search for `Automation Rule Testing Debugger` and click **Install**.

---

## Usage

### Testing a Rule

1. Go to **Settings → Technical → Automation → Automated Actions**.
2. Open any automation rule.
3. Click the **Test Rule** button in the header.
4. In the wizard:
   - The **Rule Summary** shows you the rule's model, trigger, domain, and actions at a glance.
   - The **Health Check** section highlights any configuration issues immediately.
   - Enter the **Record ID** of a record you want to test the rule against.
   - The **Record Preview** field confirms whether the ID resolves to a valid record.
   - Choose **Simulation (Dry Run)** or **Real Execution** mode.
5. Click **Run Test**.
6. The debug log opens automatically, showing every step with pass/fail indicators and timing.

### Running a Health Check

1. Open any automation rule.
2. Click **Health Check** in the header.
3. A notification lists all detected issues, or confirms the rule is healthy.

### Viewing All Debug Logs

- Open any automation rule and click the **Debug Logs** smart button (visible when logs exist).
- Or go to **Settings → Technical → Automation Debug Logs** from the menu.

### Re-running a Test

From any debug log record, click **Re-run Simulation** to open the wizard pre-filled with the same rule and record.

---

## Security

| Group | Read | Write | Create | Delete |
|---|---|---|---|---|
| `base.group_system` (Administrators) | ✅ | ✅ | ✅ | ✅ |
| `base.group_user` (Internal Users) | ✅ | — | — | — |

Only system administrators can create, edit, or delete debug logs. Internal users can view them.

The **Test Rule** wizard is accessible to all internal users, allowing team members to test rules they have access to without needing full admin rights.

---

## Module Structure

```
automation_rule_debugger/
│
├── __manifest__.py                        # Module metadata
├── __init__.py                            # Package init
├── README.md                              # This file
│
├── models/
│   ├── __init__.py
│   ├── automation_debug_log.py            # automation.debug.log model
│   │                                      # automation.debug.log.line model
│   └── automation_rule_inherit.py         # Extends base.automation with:
│                                          #   - Simulation engine
│                                          #   - Health checker
│                                          #   - Debug log relation
│
├── wizards/
│   ├── __init__.py
│   ├── automation_test_wizard.py          # automation.test.wizard transient model
│   └── automation_test_wizard_views.xml   # Wizard form view
│
├── views/
│   ├── automation_debug_log_views.xml     # Log list, form, search views + action
│   ├── automation_rule_views.xml          # Inherited base.automation views
│   └── menus.xml                          # Menu items
│
├── security/
│   └── ir.model.access.csv               # Access control rules
│
├── data/
│   └── automation_debugger_data.xml      # Initial data (placeholder)
│
└── static/
    └── src/
        ├── css/
        │   └── debugger.css              # UI styling
        └── js/
            └── debugger_widget.js        # Frontend helpers (OWL component)
```

---

## Models Reference

### `automation.debug.log`
Stores one record per test run.

| Field | Type | Description |
|---|---|---|
| `rule_id` | Many2one | The tested automation rule |
| `model_id` | Many2one | Model of the rule (computed) |
| `record_id` | Integer | ID of the tested record |
| `record_name` | Char | Display name of the tested record |
| `trigger` | Char | Trigger used |
| `execution_mode` | Selection | `simulation` or `real` |
| `state` | Selection | `success`, `failed`, `partial`, `skipped` |
| `duration_ms` | Float | Total execution time in milliseconds |
| `log_lines` | One2many | Individual step records |
| `summary` | Text | Human-readable summary |
| `error_message` | Text | Error details if applicable |
| `suggestions` | Text | Auto-generated fix hints |
| `domain_result` | Boolean | Whether the filter domain matched |
| `actions_count` | Integer | Number of actions evaluated |
| `actions_success` | Integer | Number of actions that succeeded |

### `automation.debug.log.line`
Stores one record per execution step within a log.

| Field | Type | Description |
|---|---|---|
| `log_id` | Many2one | Parent log record |
| `sequence` | Integer | Step order |
| `step_type` | Selection | `info`, `trigger`, `domain`, `condition`, `action`, `warning`, `error` |
| `state` | Selection | `success`, `failed`, `skipped`, `info` |
| `title` | Char | Short step title |
| `detail` | Text | Full explanation |
| `technical_info` | Text | Traceback or raw technical data |
| `duration_ms` | Float | Step execution time in milliseconds |

### `automation.test.wizard` (Transient)
The test wizard shown when clicking **Test Rule**.

| Field | Description |
|---|---|
| `rule_id` | The rule being tested |
| `record_id_int` | Record ID to test against |
| `record_preview` | Live validation of the entered Record ID |
| `execution_mode` | Simulation or Real |
| `rule_summary` | HTML summary of the rule's configuration |
| `health_issues` | Plain-text list of health check findings |

---

## Technical Notes

### Simulation Engine Flow

```
run_simulation(record_id, execution_mode)
    │
    ├── Step 1: Load record → verify exists & accessible
    ├── Step 2: Check rule.active
    ├── Step 3: Evaluate filter_domain against record
    ├── Step 4: Evaluate filter_pre_domain (write triggers only)
    ├── Step 5: For each action_server_id:
    │           ├── [simulation] → describe action (no writes)
    │           └── [real]       → action.run() with context
    └── Step 6: Collect health check suggestions → finalise log
```

### Health Checker

The `_collect_health_issues()` method on `base.automation` checks:
- `active` flag
- `model_id` presence
- `filter_domain` syntax via `safe_eval`
- Field name existence in domain leaves
- `filter_pre_domain` syntax
- `action_server_ids` non-empty
- Trigger-specific requirements (date field for time triggers, pre-domain for write triggers)

### Odoo 19 Compatibility

- Uses `invisible=` attribute syntax (replaces legacy `attrs={'invisible': ...}`).
- Views use `<list>` tag (replaces `<tree>`).
- OWL-based JS component registered via `registry.category("fields")`.
- All `safe_eval` calls use `odoo.tools.safe_eval` for security.
- No deprecated API calls.

---

## Changelog

### 19.0.1.0.0 — Initial Release
- Simulation engine with dry-run and real execution modes.
- Step-by-step execution log with 7 step types.
- Health checker with 8 rule validation checks.
- Smart suggestions system.
- Debug log history dashboard.
- Last Test badge on automation rules list.
- Test wizard with live record preview and rule summary.
- OWL frontend component for clipboard copy.

---

## Author

**Mohamed Anwar**

For issues, feature requests, or contributions, please open a ticket or pull request in the module's repository.

---

