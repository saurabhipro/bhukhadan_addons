/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PaymentDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            searchTerm: "",
            expandedProjectId: null,
            stats: {
                total_count: 0,
                success_count: 0,
                failed_count: 0,
                pending_count: 0,
                total_amount: 0,
                success_amount: 0,
                failed_amount: 0,
                pending_amount: 0,
                success_rate: 0,
                project_count: 0,
                village_count: 0,
            },
            projects: [],
            villages: [],
            recent_failures: [],
        });

        onWillStart(async () => {
            this._showBodyLoader();
            await this.loadData();
            this._hideBodyLoader();
        });
    }

    // ── Body-level loader (works with any Odoo theme including Spiffy) ──────
    _showBodyLoader() {
        if (document.getElementById('bhu_pay_loader')) return;
        const el = document.createElement('div');
        el.id = 'bhu_pay_loader';
        el.style.cssText = 'position:fixed!important;inset:0!important;z-index:99999!important;display:flex!important;align-items:center!important;justify-content:center!important;flex-direction:column!important;background:linear-gradient(135deg,#3b1a0e 0%,#6b2f0f 40%,#8B4513 70%,#c47c3e 100%)!important;';
        el.innerHTML = `
            <style>
                #bhu_pay_loader .bpl-ring {
                    width: 96px; height: 96px; border-radius: 50%;
                    background: rgba(255,255,255,0.15);
                    border: 3px solid rgba(255,255,255,0.4);
                    display: flex; align-items: center; justify-content: center;
                    margin-bottom: 18px;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
                    overflow: hidden; padding: 6px;
                }
                #bhu_pay_loader .bpl-ring img { width:100%; height:100%; object-fit:contain; border-radius:50%; }
                #bhu_pay_loader .bpl-spinner {
                    width: 60px; height: 60px;
                    border: 5px solid rgba(255,255,255,0.15);
                    border-top-color: #ffd88a; border-radius: 50%;
                    animation: bpl-spin 0.85s linear infinite; margin-bottom: 26px;
                }
                #bhu_pay_loader .bpl-title { color:#fff; font-size:1.5rem; font-weight:700; margin:0 0 6px 0; font-family:inherit; }
                #bhu_pay_loader .bpl-sub { color:rgba(255,255,255,0.70); font-size:0.95rem; margin:0 0 26px 0; font-style:italic; font-family:inherit; }
                #bhu_pay_loader .bpl-dots { display:flex; gap:9px; margin-bottom:30px; }
                #bhu_pay_loader .bpl-dots span { width:10px; height:10px; border-radius:50%; background:#ffd88a; animation:bpl-bounce 1.2s ease-in-out infinite; }
                #bhu_pay_loader .bpl-dots span:nth-child(2){animation-delay:0.18s;}
                #bhu_pay_loader .bpl-dots span:nth-child(3){animation-delay:0.36s;}
                #bhu_pay_loader .bpl-dots span:nth-child(4){animation-delay:0.54s;}
                #bhu_pay_loader .bpl-dots span:nth-child(5){animation-delay:0.72s;}
                #bhu_pay_loader .bpl-brand { color:rgba(255,255,255,0.35); font-size:0.75rem; letter-spacing:1.2px; text-transform:uppercase; font-family:inherit; }
                @keyframes bpl-spin { to { transform: rotate(360deg); } }
                @keyframes bpl-bounce {
                    0%,80%,100% { transform:scale(0.55); opacity:0.4; }
                    40%         { transform:scale(1.2);  opacity:1;   }
                }
            </style>
            <div class="bpl-ring"><img src="/bhukhadan_core/static/img/icon.png" alt="BhuKhadan"/></div>
            <div class="bpl-spinner"></div>
            <div class="bpl-title">Please wait…</div>
            <div class="bpl-sub">We are loading your dashboard</div>
            <div class="bpl-dots"><span></span><span></span><span></span><span></span><span></span></div>
            <div class="bpl-brand">BhuKhadan · Land Acquisition System</div>
        `;
        document.body.appendChild(el);
    }

    _hideBodyLoader() {
        const el = document.getElementById('bhu_pay_loader');
        if (el) {
            el.style.transition = 'opacity 0.35s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 380);
        }
    }

    async loadData() {
        try {
            this.state.loading = true;
            const data = await this.orm.call(
                "bhu.payment.dashboard",
                "get_payment_dashboard_data",
                []
            );
            this.state.stats = data.stats || this.state.stats;
            this.state.projects = data.projects || [];
            this.state.villages = data.villages || [];
            this.state.recent_failures = data.recent_failures || [];
            this.state.loading = false;
        } catch (err) {
            console.error("Payment dashboard load failed:", err);
            this.notification.add("Failed to load payment dashboard data.", { type: "danger" });
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    // Formatting helpers
    // ------------------------------------------------------------------
    formatInr(value) {
        const v = Number(value || 0);
        if (v >= 10000000) return "₹ " + (v / 10000000).toFixed(2) + " Cr";
        if (v >= 100000) return "₹ " + (v / 100000).toFixed(2) + " L";
        return "₹ " + v.toLocaleString("en-IN", { maximumFractionDigits: 0 });
    }

    formatInrFull(value) {
        return "₹ " + Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
    }

    formatPct(value) {
        return (Number(value || 0)).toFixed(2) + " %";
    }

    rateColor(rate) {
        if (rate >= 90) return "#2e7d32";
        if (rate >= 60) return "#ef6c00";
        return "#c62828";
    }

    rateBg(rate) {
        if (rate >= 90) return "#e8f5e9";
        if (rate >= 60) return "#fff3e0";
        return "#ffebee";
    }

    // ------------------------------------------------------------------
    // Filtering / expansion
    // ------------------------------------------------------------------
    get filteredProjects() {
        const term = (this.state.searchTerm || "").toLowerCase().trim();
        if (!term) return this.state.projects;
        return this.state.projects.filter(p =>
            (p.project_name || "").toLowerCase().includes(term) ||
            (p.project_code || "").toLowerCase().includes(term) ||
            (p.department_name || "").toLowerCase().includes(term) ||
            (p.district_name || "").toLowerCase().includes(term)
        );
    }

    villagesForProject(projectId) {
        return this.state.villages.filter(v => v.project_id === projectId);
    }

    toggleProject(projectId) {
        this.state.expandedProjectId =
            this.state.expandedProjectId === projectId ? null : projectId;
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
    }

    statusBadgeClass(project) {
        const key = project.payment_status_key || "none";
        if (key === "danger") return "pd-status pd-status-danger";
        if (key === "warning") return "pd-status pd-status-warning";
        if (key === "success") return "pd-status pd-status-success";
        return "pd-status pd-status-none";
    }

    // ------------------------------------------------------------------
    // Navigation actions
    // ------------------------------------------------------------------
    async refresh() {
        await this.loadData();
    }

    openAllFailed() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "All Failed Payments",
            res_model: "bhu.payment.reconciliation.bank.line",
            views: [[false, "list"], [false, "form"]],
            domain: [["status", "=", "failed"]],
            target: "current",
        });
    }

    openAllSuccess() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Successful Payments",
            res_model: "bhu.payment.reconciliation.bank.line",
            views: [[false, "list"], [false, "form"]],
            domain: [["status", "=", "settled"]],
            target: "current",
        });
    }

    openAllPending() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Pending Payments",
            res_model: "bhu.payment.reconciliation.bank.line",
            views: [[false, "list"], [false, "form"]],
            domain: [["status", "=", "pending"]],
            target: "current",
        });
    }

    openAllLines() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "All Payment Lines",
            res_model: "bhu.payment.reconciliation.bank.line",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openVillageFailed(village) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Failed Payments - ${village.project_name} / ${village.village_name}`,
            res_model: "bhu.payment.reconciliation.bank.line",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["status", "=", "failed"],
                ["reconciliation_id.project_id", "=", village.project_id],
                ["reconciliation_id.village_id", "=", village.village_id],
            ],
            target: "current",
        });
    }

    openProjectFailed(project) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Failed Payments - ${project.project_name}`,
            res_model: "bhu.payment.reconciliation.bank.line",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["status", "=", "failed"],
                ["reconciliation_id.project_id", "=", project.project_id],
            ],
            target: "current",
        });
    }

    openFailureLine(line) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Bank Reconciliation",
            res_model: "bhu.payment.reconciliation.bank",
            res_id: line.reconciliation_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openProject(project) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.project",
            res_id: project.project_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

PaymentDashboard.template = "bhukhadan_core.PaymentDashboard";

registry.category("actions").add("bhukhadan_core.payment_dashboard", PaymentDashboard);
