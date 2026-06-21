/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PatwariDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.user = useService("user");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            userName: "",
            villageIds: [],
            villageNames: [],
            stats: {
                project_count: 0,
                village_count: 0,
                total_surveys: 0,
                approved_surveys: 0,
                pending_surveys: 0,
                total_payment_lines: 0,
                pending_payment_lines: 0,
                failed_payment_lines: 0,
                bene_fail_count: 0,
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        try {
            this.state.loading = true;
            const data = await this.orm.call("bhuarjan.dashboard", "get_patwari_dashboard_data", []);
            this.state.userName = data.user_name || "";
            this.state.villageIds = data.village_ids || [];
            this.state.villageNames = data.village_names || [];
            this.state.stats = data.stats || this.state.stats;
        } catch (error) {
            console.error("Patwari dashboard load failed:", error);
            this.notification.add("Failed to load Patwari dashboard data.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openSurveys() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Patwari Surveys",
            res_model: "bhu.survey",
            views: [[false, "list"], [false, "form"]],
            domain: [
                "|",
                ["user_id", "=", this.user.userId],
                ["village_id", "in", this.state.villageIds],
            ],
            target: "current",
        });
    }

    openPendingPayments() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Pending Payments",
            res_model: "bhu.payment.file.line",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["payment_file_id.village_id", "in", this.state.villageIds],
                ["payment_status", "in", ["pending", "failed"]],
            ],
            target: "current",
        });
    }

    openAllPaymentLines() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Payment Lines",
            res_model: "bhu.payment.file.line",
            views: [[false, "list"], [false, "form"]],
            domain: [["payment_file_id.village_id", "in", this.state.villageIds]],
            target: "current",
        });
    }
}

PatwariDashboard.template = "bhukhadan_core.PatwariDashboard";
registry.category("actions").add("bhukhadan_core.patwari_dashboard", PatwariDashboard);
