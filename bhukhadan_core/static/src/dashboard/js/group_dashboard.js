/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ProjectTimelineDialog } from "../../js/components/project_timeline";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/** Pipeline milestone ids (same order as ``bhu.project.get_pipeline_dots_for_dashboard``). */
const PIPELINE_DOT_IDS = [
    "survey", "section4", "sia_team", "expert_committee",
    "section11", "section15", "section19", "section21", "section23",
    "payment_voucher", "payment_file",
];

const PIPELINE_DOT_SHORT_LABELS = {
    survey: "10",
    section4: "4",
    sia_team: "SI",
    expert_committee: "EC",
    section11: "11",
    section15: "15",
    section19: "19",
    section21: "21",
    section23: "23",
    payment_voucher: "PV",
    payment_file: "PF",
};

function defaultStageDots() {
    return PIPELINE_DOT_IDS.map((id) => ({
        id,
        kind: "pending",
        title: "",
        short_label: PIPELINE_DOT_SHORT_LABELS[id] || "",
    }));
}

// ── Survey Trend Chart Dialog ──────────────────────────────────────────────
class SurveyTrendDialog extends Component {
    static template = "bhukhadan_core.SurveyTrendDialog";
    static components = { Dialog };
    static props = { close: Function, trendData: Object };

    setup() {
        this.state = useState({ view: 'daily' }); // daily | weekly | monthly
        onMounted(() => this._drawChart());
    }

    get currentData() {
        return this.props.trendData[this.state.view] || [];
    }

    get maxVal() {
        const vals = this.currentData.map(d => d.value);
        return Math.max(...vals, 1);
    }

    setView(v) {
        this.state.view = v;
        // redraw on next tick after OWL re-renders
        setTimeout(() => this._drawChart(), 50);
    }

    _drawChart() {
        const canvas = document.getElementById('bhu_survey_chart');
        if (!canvas) return;
        const data = this.currentData;
        const maxVal = this.maxVal;
        const W = canvas.offsetWidth || 800;
        const H = 260;
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, W, H);

        const PAD_L = 42, PAD_R = 16, PAD_T = 20, PAD_B = 60;
        const chartW = W - PAD_L - PAD_R;
        const chartH = H - PAD_T - PAD_B;
        const n = data.length;
        const barW = Math.max(6, (chartW / n) * 0.62);
        const gap = chartW / n;

        // Grid lines
        const gridSteps = 5;
        ctx.strokeStyle = 'rgba(139,69,19,0.10)';
        ctx.lineWidth = 1;
        ctx.font = '11px system-ui, sans-serif';
        ctx.fillStyle = '#888';
        ctx.textAlign = 'right';
        for (let i = 0; i <= gridSteps; i++) {
            const y = PAD_T + chartH - (chartH * i / gridSteps);
            ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD_R, y); ctx.stroke();
            ctx.fillText(Math.round(maxVal * i / gridSteps), PAD_L - 6, y + 4);
        }

        // Bars
        data.forEach((d, idx) => {
            const x = PAD_L + idx * gap + (gap - barW) / 2;
            const barH = d.value === 0 ? 2 : Math.max(4, (d.value / maxVal) * chartH);
            const y = PAD_T + chartH - barH;

            // Gradient fill
            const grad = ctx.createLinearGradient(x, y, x, PAD_T + chartH);
            grad.addColorStop(0, '#C87941');
            grad.addColorStop(1, '#6B3410');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.roundRect ? ctx.roundRect(x, y, barW, barH, [4, 4, 0, 0])
                          : ctx.rect(x, y, barW, barH);
            ctx.fill();

            // Value on top
            if (d.value > 0) {
                ctx.fillStyle = '#5D2E0C';
                ctx.font = 'bold 11px system-ui, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(d.value, x + barW / 2, y - 5);
            }

            // X-axis label (show every nth to avoid overlap)
            const showEvery = n > 20 ? 5 : n > 10 ? 2 : 1;
            if (idx % showEvery === 0) {
                ctx.fillStyle = '#666';
                ctx.font = '10px system-ui, sans-serif';
                ctx.textAlign = 'center';
                ctx.save();
                ctx.translate(x + barW / 2, PAD_T + chartH + 10);
                ctx.rotate(-Math.PI / 5);
                ctx.fillText(d.label, 0, 0);
                ctx.restore();
            }
        });

        // X axis line
        ctx.strokeStyle = 'rgba(139,69,19,0.3)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(PAD_L, PAD_T + chartH);
        ctx.lineTo(W - PAD_R, PAD_T + chartH);
        ctx.stroke();
    }
}
// ──────────────────────────────────────────────────────────────────────────

export class GroupDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            projects: [],
            loading: true,
            searchTerm: "",
            sortConfig: {
                field: "create_date",
                direction: "desc"
            },
            stats: {
                total_projects: 0,
                sia_stage: 0,
                section4_stage: 0,
                section11_stage: 0,
                section19_stage: 0,
                section21_stage: 0,
                award_stage: 0,
                total_patwaris: 0,
                total_villages: 0,
                total_surveys: 0,
                surveys_today: 0,
                total_landowners: 0,
                total_budget: 0,
            }
        });

        onWillStart(async () => {
            this._showBodyLoader();
            await this.loadDashboardData();
            this._hideBodyLoader();
        });
    }

    // ── Body-level loader (works with any Odoo theme including Spiffy) ──────
    _showBodyLoader() {
        if (document.getElementById('bhu_group_loader')) return;
        const el = document.createElement('div');
        el.id = 'bhu_group_loader';
        el.style.cssText = 'position:fixed!important;inset:0!important;z-index:99999!important;display:flex!important;align-items:center!important;justify-content:center!important;flex-direction:column!important;background:linear-gradient(135deg,var(--bd-theme-primary, var(--spiffy-primary-color, var(--o-brand-odoo, #875A7B))) 0%,color-mix(in srgb, var(--bd-theme-primary, var(--spiffy-primary-color, var(--o-brand-odoo, #875A7B))) 78%, #000) 100%)!important;';
        el.innerHTML = `
            <style>
                #bhu_group_loader {
                    position: fixed !important;
                    inset: 0 !important;
                    z-index: 99999 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    flex-direction: column !important;
                    background: linear-gradient(135deg, var(--bd-theme-primary, var(--spiffy-primary-color, var(--o-brand-odoo, #875A7B))) 0%, color-mix(in srgb, var(--bd-theme-primary, var(--spiffy-primary-color, var(--o-brand-odoo, #875A7B))) 78%, #000) 100%) !important;
                }
                #bhu_group_loader .bgl-ring {
                    width: 96px; height: 96px;
                    border-radius: 50%;
                    background: rgba(255,255,255,0.15);
                    border: 3px solid rgba(255,255,255,0.4);
                    display: flex; align-items: center; justify-content: center;
                    margin-bottom: 18px;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
                    overflow: hidden;
                    padding: 6px;
                }
                #bhu_group_loader .bgl-ring img {
                    width: 100%; height: 100%;
                    object-fit: contain;
                    border-radius: 50%;
                }
                #bhu_group_loader .bgl-spinner {
                    width: 60px; height: 60px;
                    border: 5px solid rgba(255,255,255,0.15);
                    border-top-color: #ffd88a;
                    border-radius: 50%;
                    animation: bgl-spin 0.85s linear infinite;
                    margin-bottom: 26px;
                }
                #bhu_group_loader .bgl-title {
                    color: #fff; font-size: 1.5rem; font-weight: 700;
                    margin: 0 0 6px 0; font-family: inherit;
                }
                #bhu_group_loader .bgl-sub {
                    color: rgba(255,255,255,0.70); font-size: 0.95rem;
                    margin: 0 0 26px 0; font-style: italic; font-family: inherit;
                }
                #bhu_group_loader .bgl-dots {
                    display: flex; gap: 9px; margin-bottom: 30px;
                }
                #bhu_group_loader .bgl-dots span {
                    width: 10px; height: 10px; border-radius: 50%;
                    background: #ffd88a;
                    animation: bgl-bounce 1.2s ease-in-out infinite;
                }
                #bhu_group_loader .bgl-dots span:nth-child(2) { animation-delay: 0.18s; }
                #bhu_group_loader .bgl-dots span:nth-child(3) { animation-delay: 0.36s; }
                #bhu_group_loader .bgl-dots span:nth-child(4) { animation-delay: 0.54s; }
                #bhu_group_loader .bgl-dots span:nth-child(5) { animation-delay: 0.72s; }
                #bhu_group_loader .bgl-brand {
                    color: rgba(255,255,255,0.35); font-size: 0.75rem;
                    letter-spacing: 1.2px; text-transform: uppercase; font-family: inherit;
                }
                @keyframes bgl-spin {
                    to { transform: rotate(360deg); }
                }
                @keyframes bgl-bounce {
                    0%, 80%, 100% { transform: scale(0.55); opacity: 0.4; }
                    40%           { transform: scale(1.2);  opacity: 1;   }
                }
            </style>
            <div class="bgl-ring"><img src="/bhukhadan_core/static/img/icon.png" alt="BhuKhadan"/></div>
            <div class="bgl-spinner"></div>
            <div class="bgl-title">Please wait…</div>
            <div class="bgl-sub">We are loading your dashboard</div>
            <div class="bgl-dots">
                <span></span><span></span><span></span><span></span><span></span>
            </div>
            <div class="bgl-brand">BhuKhadan · Land Acquisition System</div>
        `;
        document.body.appendChild(el);
    }

    _hideBodyLoader() {
        const el = document.getElementById('bhu_group_loader');
        if (el) {
            el.style.transition = 'opacity 0.35s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 380);
        }
    }

    parseCost(value) {
        if (!value) return 0;
        let clean = value.toLowerCase().replace(/,/g, '');
        let multiplier = 1;
        if (clean.includes('lakh')) multiplier = 100000;
        if (clean.includes('crore') || clean.includes('cr')) multiplier = 10000000;

        const num = parseFloat(clean.replace(/[^0-9.]/g, ''));
        return isNaN(num) ? 0 : num * multiplier;
    }

    async loadDashboardData() {
        try {
            const companyIds = this.env.services.company.activeCompanyIds;

            // Fetch all projects with their current stage information (Filtered by Company)
            const projects = await this.orm.searchRead(
                "bhu.project",
                [["company_id", "in", companyIds]],
                ["name", "code", "department_id", "district_id", "state", "village_ids", "patwari_ids", "total_cost", "create_date"],
                { order: "create_date desc" }
            );

            let dotsMap = {};
            try {
                dotsMap = await this.orm.call(
                    "bhu.project",
                    "get_pipeline_dots_for_dashboard",
                    [projects.map((p) => p.id)]
                );
            } catch (e) {
                console.warn("get_pipeline_dots_for_dashboard failed:", e);
            }

            let globalTotalBudget = 0;
            let projectVillageIds = new Set();

            // Today's date string in YYYY-MM-DD format
            const todayStr = new Date().toISOString().slice(0, 10);

            // Fetch all global totals in one parallel batch for 100% accuracy (Filtered by Company)
            const [totalPatwaris, totalSurveys, totalLandowners, surveysToday] = await Promise.all([
                this.orm.searchCount("res.users", [
                    ["bhuarjan_role", "=", "halka_patwari"],
                    ["company_id", "in", companyIds]
                ]),
                this.orm.searchCount("bhu.survey", [
                    ["company_id", "in", companyIds]
                ]),
                this.orm.searchCount("bhu.landowner", [
                    ["company_id", "in", companyIds]
                ]),
                this.orm.searchCount("bhu.survey", [
                    ["company_id", "in", companyIds],
                    ["survey_date", "=", todayStr]
                ]),
            ]);

            // For each project, determine its current stage, counts and last survey date
            for (let project of projects) {
                const dotRow =
                    (dotsMap && (dotsMap[project.id] || dotsMap[String(project.id)])) || null;
                project.stage_dots =
                    Array.isArray(dotRow) && dotRow.length ? dotRow : defaultStageDots();
                project.current_stage = await this.determineProjectStage(project.id);
                project.village_count = project.village_ids ? project.village_ids.length : 0;

                // Track unique villages from these projects
                if (project.village_ids) project.village_ids.forEach(id => projectVillageIds.add(id));

                // Parse budget using smart parser
                globalTotalBudget += this.parseCost(project.total_cost);

                // Fetch last survey date for the project
                try {
                    const lastSurvey = await this.orm.searchRead(
                        "bhu.survey",
                        [["project_id", "=", project.id]],
                        ["survey_date"],
                        { limit: 1, order: "survey_date desc" }
                    );
                    project.last_survey_date = lastSurvey.length > 0 ? lastSurvey[0].survey_date : "No Survey";
                } catch (error) {
                    console.warn("Could not fetch last survey date for project", project.id, error);
                    project.last_survey_date = "N/A";
                }

                // Get counts for the table row (Project specific)
                const [khasraCount, landownerCount] = await Promise.all([
                    this.orm.searchCount("bhu.survey", [["project_id", "=", project.id]]),
                    this.orm.searchCount("bhu.landowner", [["survey_ids.project_id", "=", project.id]])
                ]);
                project.total_khasras = khasraCount;
                project.total_landowners = landownerCount;
            }

            this.state.projects = projects;
            this.state.stats.total_projects = projects.length;
            this.state.stats.total_villages = projectVillageIds.size;
            this.state.stats.total_patwaris = totalPatwaris;
            this.state.stats.total_surveys = totalSurveys;
            this.state.stats.surveys_today = surveysToday;
            this.state.stats.total_landowners = totalLandowners;
            this.state.stats.total_budget = globalTotalBudget.toLocaleString('en-IN', {
                maximumFractionDigits: 0
            });

            // Calculate stage statistics
            this.calculateStageStats(projects);

            this.state.loading = false;
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.loading = false;
        }
    }

    get filteredProjects() {
        let projects = [...this.state.projects];

        // 1. Apply Filtering
        if (this.state.searchTerm) {
            const term = this.state.searchTerm.toLowerCase();
            projects = projects.filter(p =>
                (p.name && p.name.toLowerCase().includes(term)) ||
                (p.code && p.code.toLowerCase().includes(term)) ||
                (p.district_id && p.district_id[1].toLowerCase().includes(term)) ||
                (p.department_id && p.department_id[1].toLowerCase().includes(term)) ||
                (p.total_cost && p.total_cost.toLowerCase().includes(term))
            );
        }

        // 2. Apply Sorting
        const { field, direction } = this.state.sortConfig;
        projects.sort((a, b) => {
            let valA = this.getFieldValue(a, field);
            let valB = this.getFieldValue(b, field);

            if (valA === null || valA === undefined) valA = "";
            if (valB === null || valB === undefined) valB = "";

            if (valA < valB) return direction === "asc" ? -1 : 1;
            if (valA > valB) return direction === "asc" ? 1 : -1;
            return 0;
        });

        return projects;
    }

    getFieldValue(obj, field) {
        if (field === "department_id" || field === "district_id") {
            return obj[field] ? obj[field][1] : "";
        }
        if (field === "total_khasras" || field === "total_landowners" || field === "village_count") {
            return obj[field] || 0;
        }
        if (field === "total_cost") {
            return this.parseCost(obj[field]);
        }
        return obj[field];
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
    }

    sortBy(field) {
        if (this.state.sortConfig.field === field) {
            this.state.sortConfig.direction = this.state.sortConfig.direction === "asc" ? "desc" : "asc";
        } else {
            this.state.sortConfig.field = field;
            this.state.sortConfig.direction = "asc";
        }
    }

    getSortIcon(field) {
        if (this.state.sortConfig.field !== field) return "fa-sort text-muted opacity-50";
        return this.state.sortConfig.direction === "asc" ? "fa-sort-up" : "fa-sort-down";
    }

    async openProject(projectId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openDepartment(departmentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.department",
            res_id: departmentId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openDistrict(districtId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.district",
            res_id: districtId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async determineProjectStage(projectId) {
        // Check stages in reverse order (latest first)

        // Check for Awards (Section 23)
        const awards = await this.orm.searchCount("bhu.section23.award", [
            ["project_id", "=", projectId]
        ]);
        if (awards > 0) return "award";

        // Check for Section 21
        const sec21 = await this.orm.searchCount("bhu.section21.notification", [
            ["project_id", "=", projectId]
        ]);
        if (sec21 > 0) return "section21";

        // Check for Section 19
        const sec19 = await this.orm.searchCount("bhu.section19.notification", [
            ["project_id", "=", projectId]
        ]);
        if (sec19 > 0) return "section19";

        // Check for Section 11
        const sec11 = await this.orm.searchCount("bhu.section11.preliminary.report", [
            ["project_id", "=", projectId]
        ]);
        if (sec11 > 0) return "section11";

        // Check for Section 4
        const sec4 = await this.orm.searchCount("bhu.section4.notification", [
            ["project_id", "=", projectId]
        ]);
        if (sec4 > 0) return "section4";

        // Check for SIA
        const sia = await this.orm.searchCount("bhu.sia.team", [
            ["project_id", "=", projectId]
        ]);
        if (sia > 0) return "sia";

        return "initial";
    }

    async calculateDelay(project) {
        // Calculate delay based on Land Acquisition Act timelines
        const createDate = new Date(project.create_date);
        const today = new Date();
        const daysSinceCreation = Math.floor((today - createDate) / (1000 * 60 * 60 * 24));

        // Define expected timelines as per Act (in days)
        const timelines = {
            sia: 180,          // 6 months for SIA completion
            section4: 210,     // 7 months for Section 4
            section11: 365,    // 12 months for Section 11
            section19: 455,    // 15 months for Section 19
            section21: 545,    // 18 months for Section 21
            award: 730         // 24 months for Award
        };

        let expectedDays = 0;
        let stageName = "";

        switch (project.current_stage) {
            case "sia":
                expectedDays = timelines.sia;
                stageName = "SIA";
                break;
            case "section4":
                expectedDays = timelines.section4;
                stageName = "Section 4";
                break;
            case "section11":
                expectedDays = timelines.section11;
                stageName = "Section 11";
                break;
            case "section19":
                expectedDays = timelines.section19;
                stageName = "Section 19";
                break;
            case "section21":
                expectedDays = timelines.section21;
                stageName = "Section 21";
                break;
            case "award":
                expectedDays = timelines.award;
                stageName = "Award";
                break;
            default:
                expectedDays = 90; // 3 months for initial stage
                stageName = "Initial";
        }

        const delayDays = daysSinceCreation - expectedDays;
        const isDelayed = delayDays > 0;

        return {
            is_delayed: isDelayed,
            delay_days: Math.abs(delayDays),
            days_since_creation: daysSinceCreation,
            expected_days: expectedDays,
            stage_name: stageName
        };
    }

    calculateStageStats(projects) {
        const stageCounts = {
            sia: 0,
            section4: 0,
            section11: 0,
            section19: 0,
            section21: 0,
            award: 0,
            initial: 0
        };

        projects.forEach(project => {
            if (stageCounts[project.current_stage] !== undefined) {
                stageCounts[project.current_stage]++;
            }
        });

        this.state.stats.sia_stage = stageCounts.sia;
        this.state.stats.section4_stage = stageCounts.section4;
        this.state.stats.section11_stage = stageCounts.section11;
        this.state.stats.section19_stage = stageCounts.section19;
        this.state.stats.section21_stage = stageCounts.section21;
        this.state.stats.award_stage = stageCounts.award;
    }

    getStageLabel(stage) {
        const labels = {
            initial: "Initial / प्रारंभिक",
            sia: "SIA Stage / SIA चरण",
            section4: "Section 4 / धारा 4",
            section11: "Section 11 / धारा 11",
            section19: "Section 19 / धारा 19",
            section21: "Section 21 / धारा 21",
            award: "Award Stage / पुरस्कार चरण"
        };
        return labels[stage] || stage;
    }

    getStageColor(stage) {
        const colors = {
            initial: "#6c757d",
            sia: "#17a2b8",
            section4: "#007bff",
            section11: "#28a745",
            section19: "#ffc107",
            section21: "#fd7e14",
            award: "#28a745"
        };
        return colors[stage] || "#6c757d";
    }

    getDelayBadgeClass(delayInfo) {
        if (!delayInfo.is_delayed) {
            return "badge-success";
        } else if (delayInfo.delay_days <= 30) {
            return "badge-warning";
        } else {
            return "badge-danger";
        }
    }

    getDelayText(delayInfo) {
        if (!delayInfo.is_delayed) {
            return `On Track (${delayInfo.delay_days} days ahead)`;
        } else {
            return `Delayed by ${delayInfo.delay_days} days`;
        }
    }

    async openProject(projectId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async showSurveyChart() {
        const companyIds = this.env.services.company.activeCompanyIds;
        const trendData = await this.orm.call('bhuarjan.dashboard', 'get_survey_trend_data', [], { company_ids: companyIds });
        this.dialog.add(SurveyTrendDialog, { trendData });
    }

    async refreshDashboard() {
        this.state.loading = true;
        await this.loadDashboardData();
    }

    async showTimeline(projectId) {
        console.log("showTimeline triggered for project:", projectId);
        try {
            this.notification.add(_t("Fetching progress data..."), { type: "info", sticky: false });

            const stages = await this.orm.call(
                "bhu.project",
                "get_project_progress",
                [projectId]
            );

            console.log("Stages data received:", stages);

            if (!ProjectTimelineDialog) {
                console.error("ProjectTimelineDialog is undefined in showTimeline!");
                this.notification.add(_t("Technical Error: Dialog component not found."), { type: "danger" });
                return;
            }

            this.dialog.add(ProjectTimelineDialog, {
                projectId: projectId,
                stages: stages,
                title: _t("Project Progress Timeline"),
            }, {
                size: "lg",
            });
            console.log("Dialog.add called successfully");
        } catch (error) {
            console.error("FATAL: Failed to show timeline:", error);
            this.notification.add(_t("Server Error: Could not load project progress."), { type: "danger" });
        }
    }
}

GroupDashboard.template = "bhukhadan_core.GroupDashboard";

registry.category("actions").add("bhukhadan_core.group_dashboard", GroupDashboard);
