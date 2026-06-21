/** @odoo-module */
import { registry } from "@web/core/registry";

const supportService = {
    start(env) {
        document.addEventListener("click", (ev) => {
            const link = ev.target.closest(".o_bhuarjan_support_link");
            if (link) {
                ev.preventDefault();
                env.services.action.doAction("bhukhadan_core.action_bhuarjan_issue_wizard");
            }
        });
    },
};

registry.category("services").add("bhuarjan_support", supportService);
