/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

/**
 * Avoid `state.*` in OWL templates — Odoo client actions may inject `props.state`
 * (breadcrumb / restore), which can clash with useState’s `state` in edge cases.
 */

/**
 * Plate wrapper fills dashlet body; bitmap height tracks its client box.
 */
function measureMgmtDashboardChartHeight(canvasEl) {
    const plate = canvasEl && canvasEl.parentElement;
    if (!plate || !plate.classList.contains("bhu-mgmt-chart-plate")) {
        return null;
    }
    const h = Math.floor(plate.clientHeight - 2);
    if (h <= 48) {
        return null;
    }
    return Math.max(148, Math.min(400, h));
}

/** Fallback when measurement is not ready */
const MGMT_CHART_H_FALLBACK = 236;

function drawVerticalBarChart(canvasEl, items, valueKey, labelKey, options = {}) {
    if (!canvasEl || !items.length) {
        return;
    }
    const values = items.map((d) => Number(d[valueKey]) || 0);
    const maxVal = Math.max(...values, 1);
    const W = canvasEl.parentElement?.clientWidth || canvasEl.offsetWidth || 400;
    const H = options.height || 220;
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = Math.floor(W * dpr);
    canvasEl.height = Math.floor(H * dpr);
    canvasEl.style.width = `${W}px`;
    canvasEl.style.height = `${H}px`;
    const ctx = canvasEl.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const compact = H <= 160;
    const PAD_L = compact ? 26 : 36;
    const PAD_R = compact ? 6 : 10;
    /* Reserve bottom for rotated x labels only; plot sits on baseline (bottom). */
    const PAD_B = compact ? 24 : 44;
    /* Tiny top margin — value labels sit just above bar tops */
    const PAD_T = compact ? 4 : 8;
    const baselineY = H - PAD_B;
    const chartTop = PAD_T;
    const chartH = Math.max(4, baselineY - chartTop);
    const chartW = W - PAD_L - PAD_R;
    const n = items.length;
    const barW = Math.max(compact ? 6 : 8, (chartW / n) * 0.55);
    const gap = chartW / n;
    const primary = options.primary || "#0d9488";
    const primary2 = options.primary2 || "#22d3ee";

    ctx.strokeStyle = options.gridColor || "rgba(15,23,42,0.06)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const gy = baselineY - (chartH * i) / 4;
        ctx.beginPath();
        ctx.moveTo(PAD_L, gy);
        ctx.lineTo(W - PAD_R, gy);
        ctx.stroke();
    }

    items.forEach((d, idx) => {
        const v = Number(d[valueKey]) || 0;
        const x = PAD_L + idx * gap + (gap - barW) / 2;
        const barH = v === 0 ? 2 : Math.max(4, (v / maxVal) * chartH);
        const yTop = baselineY - barH;
        const grad = ctx.createLinearGradient(x, yTop, x, baselineY);
        grad.addColorStop(0, primary2);
        grad.addColorStop(1, primary);
        ctx.fillStyle = grad;
        ctx.beginPath();
        const rbar = compact ? 4 : 6;
        if (ctx.roundRect) {
            ctx.roundRect(x, yTop, barW, barH, [rbar, rbar, 0, 0]);
        } else {
            ctx.rect(x, yTop, barW, barH);
        }
        ctx.fill();
        if (v > 0) {
            ctx.fillStyle = "#0f172a";
            ctx.font = compact
                ? "600 9px Segoe UI, system-ui, sans-serif"
                : "600 10px Segoe UI, system-ui, sans-serif";
            ctx.textAlign = "center";
            const vy = Math.max(chartTop + 11, yTop - (compact ? 2 : 3));
            ctx.fillText(String(v), x + barW / 2, vy);
        }
        const raw = d[labelKey];
        const lab = raw && String(raw).length > 14 ? `${String(raw).slice(0, 12)}…` : raw || "-";
        ctx.fillStyle = "#64748b";
        ctx.font = compact ? "8px Segoe UI, system-ui, sans-serif" : "9px Segoe UI, system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.save();
        ctx.translate(x + barW / 2, baselineY + (compact ? 5 : 8));
        ctx.rotate(-Math.PI / 5.5);
        ctx.fillText(lab, 0, 0);
        ctx.restore();
    });
}

export class ManagementDashboard extends Component {
    static template = "bhukhadan_core.ManagementDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.dash = useState({
            loading: true,
            error: null,
            data: null,
            filters: {
                department_id: "",
                project_id: "",
                date_from: "",
                date_to: "",
            },
        });

        onWillStart(() => this.load());
        onPatched(() => {
            browser.setTimeout(() => this._redrawCharts(), 0);
        });
    }

    // --- Safe list getters (keep XML expressions trivial) ---

    get hasKpis() {
        return !!(this.dash.data && this.dash.data.kpis);
    }

    get surveyKpiLabelText() {
        const k = this.dash.data && this.dash.data.kpis;
        return k && k.filters_active ? _t("Surveys (filtered)") : _t("Surveys (all)");
    }

    get showBody() {
        return !this.dash.loading && this.dash.data;
    }

    get projectsOverviewRows() {
        const d = this.dash.data;
        return d && d.projects_overview ? d.projects_overview : [];
    }

    _rpcPayload() {
        const companyIds = this.env.services.company.activeCompanyIds;
        const f = this.dash.filters;
        return {
            company_ids: companyIds,
            department_id: f.department_id ? parseInt(f.department_id, 10) : null,
            project_id: f.project_id ? parseInt(f.project_id, 10) : null,
            date_from: f.date_from || null,
            date_to: f.date_to || null,
        };
    }

    async load() {
        this.dash.loading = true;
        this.dash.error = null;
        try {
            const data = await this.orm.call(
                "bhuarjan.dashboard",
                "get_management_dashboard_data",
                [],
                this._rpcPayload()
            );
            this.dash.data = data;
            const echo = data.filter_echo || {};
            this.dash.filters.department_id =
                echo.department_id !== null && echo.department_id !== undefined
                    ? String(echo.department_id)
                    : "";
            this.dash.filters.project_id =
                echo.project_id !== null && echo.project_id !== undefined ? String(echo.project_id) : "";
            this.dash.filters.date_from = echo.date_from || "";
            this.dash.filters.date_to = echo.date_to || "";
        } catch (e) {
            this.dash.error = (e && e.message) || String(e);
        } finally {
            this.dash.loading = false;
            browser.setTimeout(() => this._redrawCharts(), 60);
        }
    }

    _redrawCharts() {
        const d = this.dash.data;
        if (!d) {
            return;
        }

        const drawAll = () => {
            const c1 = document.querySelector(".bhu_mgmt_canvas_patwari");
            const c2 = document.querySelector(".bhu_mgmt_canvas_stage");
            const cDept = document.querySelector(".bhu_mgmt_canvas_department");
            const cPrSrv = document.querySelector(".bhu_mgmt_canvas_project_surveys");
            const cPrArb = document.querySelector(".bhu_mgmt_canvas_project_arb");
            const cSdm = document.querySelector(".bhu_mgmt_canvas_sdm_projects");

            const h1 = measureMgmtDashboardChartHeight(c1) || MGMT_CHART_H_FALLBACK;
            const h2 = measureMgmtDashboardChartHeight(c2) || MGMT_CHART_H_FALLBACK;
            const hDept = measureMgmtDashboardChartHeight(cDept) || MGMT_CHART_H_FALLBACK;
            const hSrv = measureMgmtDashboardChartHeight(cPrSrv) || MGMT_CHART_H_FALLBACK;
            const hArb = measureMgmtDashboardChartHeight(cPrArb) || MGMT_CHART_H_FALLBACK;
            const hSdm = measureMgmtDashboardChartHeight(cSdm) || MGMT_CHART_H_FALLBACK;

            drawVerticalBarChart(c1, d.patwari_leaderboard || [], "survey_count", "name", {
                primary: "#0e7490",
                primary2: "#38bdf8",
                height: h1,
            });

            const stages = d.stage_distribution || {};
            const order = ["initial", "sia", "section4", "section11", "section19", "section21", "award"];
            const labels = d.stage_labels || {};
            let stageRows = order
                .map((k) => ({
                    name: labels[k] || k,
                    survey_count: stages[k] || 0,
                }))
                .filter((r) => r.survey_count > 0);
            if (!stageRows.length) {
                stageRows = [{ name: _t("No projects"), survey_count: 0 }];
            }
            drawVerticalBarChart(c2, stageRows, "survey_count", "name", {
                primary: "#6d28d9",
                primary2: "#c084fc",
                height: h2,
            });

            let deptBars = (d.department_stats || []).map((r) => ({
                name: r.name,
                project_count: Number(r.projects) || 0,
            }));
            deptBars.sort((a, b) => b.project_count - a.project_count);
            deptBars = deptBars.slice(0, 14);
            if (!deptBars.length) {
                deptBars = [{ name: _t("No departments"), project_count: 0 }];
            }
            drawVerticalBarChart(cDept, deptBars, "project_count", "name", {
                primary: "#78350f",
                primary2: "#d97706",
                height: hDept,
            });

            drawVerticalBarChart(cPrSrv, d.project_survey_bars || [], "survey_count", "name", {
                primary: "#0f766e",
                primary2: "#34d399",
                height: hSrv,
            });
            drawVerticalBarChart(cPrArb, d.project_arbitration_bars || [], "grievance_count", "name", {
                primary: "#b45309",
                primary2: "#fbbf24",
                height: hArb,
            });
            drawVerticalBarChart(cSdm, d.sdm_project_bars || [], "project_count", "name", {
                primary: "#0369a1",
                primary2: "#38bdf8",
                height: hSdm,
            });
        };

        drawAll();
        browser.requestAnimationFrame(() => browser.requestAnimationFrame(drawAll));
    }

    async onRefresh() {
        await this.load();
    }

    fmtKpi(n) {
        if (n == null) {
            return "0";
        }
        return new Intl.NumberFormat().format(n);
    }

    openProject(projectId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openAllProjects() {
        const domain = [["company_id", "in", this.env.services.company.activeCompanyIds]];
        if (this.dash.filters.department_id) {
            domain.push(["department_id", "=", parseInt(this.dash.filters.department_id, 10)]);
        }
        if (this.dash.filters.project_id) {
            domain.push(["id", "=", parseInt(this.dash.filters.project_id, 10)]);
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Projects"),
            res_model: "bhu.project",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain,
            target: "current",
        });
    }

    openSection23Awards() {
        const ctx = {};
        let domain = [];
        if (this.dash.filters.project_id) {
            domain = [["project_id", "=", parseInt(this.dash.filters.project_id, 10)]];
        } else if (this.dash.filters.department_id) {
            domain = [["department_id", "=", parseInt(this.dash.filters.department_id, 10)]];
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Section 23 Awards"),
            res_model: "bhu.section23.award",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain,
            context: ctx,
            target: "current",
        });
    }

    openReconciliations() {
        const domain = [["state", "=", "completed"]];
        if (this.dash.filters.project_id) {
            domain.push(["project_id", "=", parseInt(this.dash.filters.project_id, 10)]);
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Bank reconciliations"),
            res_model: "bhu.payment.reconciliation.bank",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain,
            target: "current",
        });
    }

    async openLandArbitration() {
        try {
            await this.action.doAction("bharatnyay_core.action_bharat_arbitration_grievance");
        } catch {
            this.notification.add(
                _t("Land Arbitration is not available (install or enable bharatnyay_core)."),
                { type: "warning" }
            );
        }
    }
}

registry.category("actions").add("bhukhadan_core.management_dashboard", ManagementDashboard);
