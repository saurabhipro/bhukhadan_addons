/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class RoleBasedDashboard extends Component {
    static template = xml`<div class="o_loading" style="text-align: center; padding: 50px;"><div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div></div>`;

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");

        // Redirect immediately without blocking
        onMounted(async () => {
            try {
                // Call server-side method to get the appropriate dashboard action
                // The server has reliable access to user groups and role information
                const dashboardAction = await this.orm.call(
                    "bhuarjan.dashboard",
                    "get_role_based_dashboard_action",
                    []
                );

                if (dashboardAction && dashboardAction.tag) {
                    // Use replaceStacked to replace current action and prevent breadcrumb issues
                    await this.action.doAction(dashboardAction, {
                        replaceStacked: true,
                    });
                } else {
                    // Fallback to SDM dashboard if action is not returned
                    await this.action.doAction({
                        type: "ir.actions.client",
                        tag: "bhukhadan_core.sdm_dashboard_tag",
                        name: "SDM Dashboard",
                    }, {
                        replaceStacked: true,
                    });
                }
            } catch (error) {
                console.error("RoleBasedDashboard: Error loading dashboard:", error);
                // Fallback to SDM dashboard on any error
                await this.action.doAction({
                    type: "ir.actions.client",
                    tag: "bhukhadan_core.sdm_dashboard_tag",
                    name: "SDM Dashboard",
                }, {
                    replaceStacked: true,
                });
            }
        });
    }
}

// Register the action
registry.category("actions").add(
    "bhukhadan_core.role_based_dashboard",
    RoleBasedDashboard
);
