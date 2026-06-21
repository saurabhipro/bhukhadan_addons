/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { router } from "@web/core/browser/router";
import { useService } from "@web/core/utils/hooks";
import { ProjectTimelineDialog } from "../../js/components/project_timeline";
import { _t } from "@web/core/l10n/translation";

const PIPELINE_DOT_IDS = [
    "survey",
    "section4",
    "sia_team",
    "expert_committee",
    "section11",
    "section15",
    "section19",
    "section21",
    "section23",
    "payment_voucher",
    "payment_file",
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

function _normLower(s) {
    return String(s || "")
        .trim()
        .toLowerCase();
}

function _digitsOnly(s) {
    return String(s || "").replace(/\D/g, "");
}

/** Match mobile: substring on full string, or digits-only contains when query has 3+ digits */
function _mobileMatches(termLc, termDigits, mobile) {
    const m = String(mobile || "");
    if (_normLower(m).includes(termLc)) {
        return true;
    }
    if (termDigits.length >= 3) {
        const md = _digitsOnly(m);
        return md.includes(termDigits);
    }
    return false;
}

/** Pipeline dot id → Odoo model (aligned with unified dashboard). */
const PIPELINE_STAGE_MODELS = {
    survey: "bhu.survey",
    section4: "bhu.section4.notification",
    sia_team: "bhu.sia.team",
    expert_committee: "bhu.expert.committee.report",
    section11: "bhu.section11.preliminary.report",
    section15: "bhu.section15.objection",
    section19: "bhu.section19.notification",
    section21: "bhu.section21.notification",
    section23: "bhu.section23.award",
    payment_voucher: "bhu.payment.voucher",
    payment_file: "bhu.payment.voucher.export",
};

const PIPELINE_MODELS_WITH_VILLAGE = new Set([
    "bhu.survey",
    "bhu.section4.notification",
    "bhu.section11.preliminary.report",
    "bhu.section15.objection",
    "bhu.section19.notification",
    "bhu.section21.notification",
    "bhu.section23.award",
    "bhu.payment.voucher",
    "bhu.payment.voucher.export",
]);

export class SdmPipelineDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            raw: null,
            searchTerm: "",
            showProjectPct: true,
            showVillagePct: true,
            expandedSubIds: {},
            expandedProjectKeys: {},
        });

        onWillStart(async () => {
            await this.loadData();
            this._expandAllSubdivisions();
        });
    }

    _expandAllSubdivisions() {
        const subs = this.state.raw?.subdivisions || [];
        const cur = { ...this.state.expandedSubIds };
        for (const sd of subs) {
            cur[sd.id] = true;
        }
        this.state.expandedSubIds = cur;
    }

    async loadData() {
        this.state.loading = true;
        try {
            const companyIds = this.env.services.company.activeCompanyIds;
            const data = await this.orm.call(
                "bhuarjan.dashboard.stats",
                "get_sdm_pipeline_dashboard_data",
                [],
                { company_ids: companyIds }
            );
            this.state.raw = data;
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Could not load SDM Pipeline Dashboard."), { type: "danger" });
            this.state.raw = {
                subdivisions: [],
                totals: {},
                is_admin_view: false,
            };
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        await this.loadData();
        this._expandAllSubdivisions();
        this.notification.add(_t("Dashboard refreshed."), { type: "success" });
    }

    get bannerHint() {
        if (this.state.raw?.is_admin_view) {
            return _t("All sub divisions · Leadership view");
        }
        return _t("Your sub division · Projects linked on each project form");
    }

    get pipelineCollectors() {
        return this.state.raw?.collectors || [];
    }

    get filteredBlocks() {
        const rawTerm = (this.state.searchTerm || "").trim();
        const termLc = _normLower(rawTerm);
        const termDigits = _digitsOnly(rawTerm);
        const blocks = this.state.raw?.subdivisions || [];
        if (!termLc && !termDigits) {
            return blocks;
        }
        const haySubFields = (sd) =>
            _normLower(sd.name).includes(termLc) ||
            _normLower(sd.district_name).includes(termLc) ||
            _normLower(sd.state_name).includes(termLc) ||
            _normLower(sd.sdm_user).includes(termLc);

        const hayProjectFields = (p) =>
            _normLower(p.name).includes(termLc) ||
            _normLower(p.code).includes(termLc) ||
            _normLower(p.district).includes(termLc) ||
            _normLower(p.sub_division).includes(termLc) ||
            _normLower(p.tehsil).includes(termLc) ||
            _normLower(p.department).includes(termLc) ||
            _normLower(p.state).includes(termLc);

        const hayVillage = (v) =>
            _normLower(v.name).includes(termLc) ||
            _normLower(v.code).includes(termLc) ||
            _normLower(v.patwari_name).includes(termLc) ||
            _mobileMatches(termLc, termDigits, v.patwari_mobile);

        return blocks
            .map((sd) => {
                const haySub = haySubFields(sd);
                const projects = (sd.projects || [])
                    .map((p) => {
                        const villages = p.villages || [];
                        const matchingVillages = villages.filter(hayVillage);
                        const projectHay = hayProjectFields(p);

                        if (haySub || projectHay) {
                            return p;
                        }
                        if (!matchingVillages.length) {
                            return null;
                        }
                        return {
                            ...p,
                            villages: matchingVillages,
                            village_count: matchingVillages.length,
                            survey_count: matchingVillages.reduce(
                                (sum, v) => sum + (Number(v.survey_count) || 0),
                                0
                            ),
                        };
                    })
                    .filter(Boolean);
                if (!haySub && !projects.length) {
                    return null;
                }
                return { ...sd, projects };
            })
            .filter(Boolean);
    }

    toggleSub(sdId) {
        const cur = { ...this.state.expandedSubIds };
        cur[sdId] = !cur[sdId];
        this.state.expandedSubIds = cur;
    }

    isSubExpanded(sdId) {
        return !!this.state.expandedSubIds[sdId];
    }

    projKey(sdId, pid) {
        return `${sdId}_${pid}`;
    }

    toggleProject(sdId, pid) {
        const k = this.projKey(sdId, pid);
        const cur = { ...this.state.expandedProjectKeys };
        cur[k] = !cur[k];
        this.state.expandedProjectKeys = cur;
    }

    isProjectExpanded(sdId, pid) {
        return !!this.state.expandedProjectKeys[this.projKey(sdId, pid)];
    }

    normalizeDots(dots) {
        if (Array.isArray(dots) && dots.length) {
            return dots;
        }
        return defaultStageDots();
    }

    stageDotTitle(dot) {
        const base = (dot && dot.title) || "";
        return base
            ? `${base} — ${_t("Click to open this section")}`
            : _t("Click to open this section");
    }

    /** Odoo 18 doAction expects ir.actions.act_window.views on RPC payloads. */
    _normalizeRpcActWindow(action) {
        if (!action || action.type !== "ir.actions.act_window") {
            return action;
        }
        let views = action.views;
        if (!Array.isArray(views) || views.length === 0) {
            const rawVm = action.view_mode || "list,form";
            const modes = String(rawVm)
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean);
            views = modes.length
                ? modes.map((m) => [false, m])
                : [
                      [false, "list"],
                      [false, "form"],
                  ];
            return { ...action, views };
        }
        return action;
    }

    /** Color tone for pipeline completion % badges */
    pctTone(pct) {
        const n = Number(pct) || 0;
        if (n >= 75) {
            return "o_sdm_pd_pct_high";
        }
        if (n >= 40) {
            return "o_sdm_pd_pct_mid";
        }
        if (n > 0) {
            return "o_sdm_pd_pct_low";
        }
        return "o_sdm_pd_pct_zero";
    }

    /** Survey count badge styling tier */
    surveyBadgeClass(count) {
        const n = Number(count) || 0;
        if (n >= 10) {
            return "o_sdm_pd_survey_hot";
        }
        if (n > 0) {
            return "o_sdm_pd_survey_warm";
        }
        return "o_sdm_pd_survey_empty";
    }

    /** Same route as department master list ``widget="image"`` thumbnails */
    departmentLogoSrc(deptId) {
        return deptId ? `/web/image/bhu.department/${deptId}/department_logo` : "";
    }

    /** Fallback icon when ``department_logo`` is empty (master uses Icon Class field). */
    deptPlaceholderIcon(proj) {
        const ic = ((proj && proj.department_icon) || "").trim();
        return ic || "fa fa-building text-secondary";
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
    }

    expandAllSubs() {
        const cur = {};
        for (const sd of this.filteredBlocks) {
            cur[sd.id] = true;
        }
        this.state.expandedSubIds = cur;
    }

    collapseAllSubs() {
        this.state.expandedSubIds = {};
        this.state.expandedProjectKeys = {};
    }

    async showProjectTimeline(projectId) {
        try {
            const stages = await this.orm.call("bhu.project", "get_project_progress", [projectId]);
            this.dialog.add(
                ProjectTimelineDialog,
                {
                    projectId,
                    stages: stages || [],
                    title: _t("Project Progress Timeline"),
                },
                { size: "lg" }
            );
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Could not load project timeline."), { type: "danger" });
        }
    }

    async showVillageTimeline(projectId, villageId) {
        try {
            const stages = await this.orm.call(
                "bhu.project",
                "get_village_progress_timeline_for_dashboard",
                [projectId, villageId]
            );
            this.dialog.add(
                ProjectTimelineDialog,
                {
                    projectId,
                    villageId,
                    stages: stages || [],
                    title: _t("Village pipeline / ग्राम चरण"),
                },
                { size: "lg" }
            );
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Could not load village pipeline."), { type: "danger" });
        }
    }

    async _openPipelineStageAction(stageId, projectId, villageId, dotKind) {
        if (dotKind === "na") {
            this.notification.add(_t("This stage is not applicable for this project."), {
                type: "info",
            });
            return;
        }
        if (!stageId || !projectId) {
            return;
        }
        try {
            const action = await this.orm.call(
                "bhuarjan.dashboard.stats",
                "get_pipeline_stage_window_action",
                [stageId, projectId, villageId || false]
            );
            await this.action.doAction(this._normalizeRpcActWindow(action));
        } catch (e) {
            console.error(e);
            const msg =
                e?.data?.message || e?.message || _t("Could not open this section.");
            this.notification.add(msg, { type: "danger" });
        }
    }

    async openVillageSurveys(projectId, villageId) {
        if (!projectId || !villageId) {
            return;
        }
        await this._openPipelineStageAction("survey", projectId, villageId, "done");
    }

    async openProjectSurveys(projectId) {
        if (!projectId) {
            return;
        }
        await this._openPipelineStageAction("survey", projectId, null, "done");
    }

    async _openActWindowInNewTab(action) {
        if (!action || !action.res_model) {
            return;
        }
        const state = {
            model: action.res_model,
            view_type: (action.view_mode || "form").split(",")[0],
        };
        if (action.res_id) {
            state.resId = action.res_id;
        }
        if (action.domain) {
            state.domain =
                typeof action.domain === "string"
                    ? action.domain
                    : JSON.stringify(action.domain);
        }
        if (action.context) {
            state.context =
                typeof action.context === "string"
                    ? action.context
                    : JSON.stringify(action.context);
        }
        const url = router.stateToUrl(state);
        await this.action.doAction({
            type: "ir.actions.act_url",
            url,
            target: "new",
        });
    }

    async openDocViewerInNewTab(projectId) {
        if (!projectId) {
            return;
        }
        try {
            const act = await this.orm.call(
                "bhuarjan.dashboard.stats",
                "open_document_vault_navigator_for_project",
                [projectId]
            );
            await this._openActWindowInNewTab(act);
        } catch (e) {
            console.error(e);
            const msg = e?.data?.message || e?.message || _t("Could not open document viewer.");
            this.notification.add(msg, { type: "danger" });
        }
    }

    async openPipelineStage(stageId, projectId, villageId, dotKind) {
        await this._openPipelineStageAction(stageId, projectId, villageId, dotKind);
    }

    openProjectForm(projectId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openVillageForm(villageId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.village",
            res_id: villageId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSubDivisionForm(sdId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bhu.sub.division",
            res_id: sdId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSdmUser(userId) {
        if (!userId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.users",
            res_id: userId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async loginAsSdm(userId, userName) {
        if (!userId) {
            return;
        }
        const label = userName || _t("SDM");
        if (!window.confirm(_t("Login as %s? You will see exactly what this SDM sees. Use Switch back in the top banner or user menu to return.", label))) {
            return;
        }
        try {
            const redirect = window.location.pathname + window.location.search || "/web";
            const url = await this.orm.call(
                "bhuarjan.dashboard.stats",
                "get_login_as_sdm_url",
                [userId, redirect]
            );
            window.location.assign(url);
        } catch (e) {
            console.error(e);
            const msg = e?.data?.message || e?.message || _t("Could not login as this SDM.");
            this.notification.add(msg, { type: "danger" });
        }
    }

    openCollectorUser(userId) {
        if (!userId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.users",
            res_id: userId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async loginAsCollector(userId, userName) {
        if (!userId) {
            return;
        }
        const label = userName || _t("Collector");
        if (!window.confirm(_t("Login as %s? You will see exactly what this Collector sees. Use Exit impersonation in the top banner to return.", label))) {
            return;
        }
        try {
            const redirect = window.location.pathname + window.location.search || "/web";
            const url = await this.orm.call(
                "bhuarjan.dashboard.stats",
                "get_login_as_collector_url",
                [userId, redirect]
            );
            window.location.assign(url);
        } catch (e) {
            console.error(e);
            const msg = e?.data?.message || e?.message || _t("Could not login as this Collector.");
            this.notification.add(msg, { type: "danger" });
        }
    }
}

SdmPipelineDashboard.template = "bhukhadan_core.SdmPipelineDashboard";

registry.category("actions").add("bhukhadan_core.sdm_pipeline_dashboard", SdmPipelineDashboard);
