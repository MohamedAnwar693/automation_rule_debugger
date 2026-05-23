/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";


class DebugCopyTextField extends Component {
    static template = "automation_rule_debugger.DebugCopyText";
    static props = {
        value: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.notification = useService("notification");
    }

    onCopy() {
        const text = this.props.value || "";
        if (!text) return;
        navigator.clipboard.writeText(text).then(() => {
            this.notification.add("Copied to clipboard", { type: "success" });
        });
    }
}

try {
    registry.category("fields").add("debug_copy_text", {
        component: DebugCopyTextField,
    });
} catch (e) {
}
