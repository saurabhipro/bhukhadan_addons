/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Pipeline milestones aligned with ``bhu.project.get_project_progress`` (through payment file). */
const PIPELINE_DOT_DEFS = [
    { id: "survey", label: _t("Survey / सर्वे"), short_label: "10" },
    { id: "section4", label: _t("Section 4 / धारा 4"), short_label: "4" },
    { id: "sia_team", label: _t("SIA team / SIA टीम"), short_label: "SI" },
    { id: "expert_committee", label: _t("Expert committee / विशेषज्ञ समिति"), short_label: "EC" },
    { id: "section11", label: _t("Section 11 / धारा 11"), short_label: "11" },
    { id: "section15", label: _t("Section 15 / धारा 15"), short_label: "15" },
    { id: "section19", label: _t("Section 19 / धारा 19"), short_label: "19" },
    { id: "section21", label: _t("Section 21 / धारा 21"), short_label: "21" },
    { id: "section23", label: _t("Section 23 award / धारा 23"), short_label: "23" },
    { id: "payment_voucher", label: _t("Payment Voucher / भुगतान वाउचर"), short_label: "PV" },
    { id: "payment_file", label: _t("Payment File / भुगतान फ़ाइल"), short_label: "PF" },
];

function computeStageDots(stages, isSiaExempt) {
    const map = {};
    for (const s of stages || []) {
        map[s.id] = s;
    }
    return PIPELINE_DOT_DEFS.map((def) => {
        const sl = def.short_label || "";
        if ((def.id === "sia_team" || def.id === "expert_committee") && isSiaExempt) {
            return {
                id: def.id,
                title: `${def.label} — ${_t("Not applicable (SIA exempt)")}`,
                kind: "na",
                short_label: sl,
            };
        }
        const st = map[def.id];
        if (!st) {
            return {
                id: def.id,
                title: `${def.label} — ${_t("Pending")}`,
                kind: "pending",
                short_label: sl,
            };
        }
        let kind = "pending";
        if (st.status === "completed") {
            kind = "done";
        } else if (st.status === "in_progress") {
            kind = "active";
        }
        const detail = st.details ? ` (${st.details})` : "";
        return {
            id: def.id,
            title: `${st.name}${detail}`,
            kind,
            short_label: sl,
        };
    });
}

/** Batch ``get_pipeline_dots_for_dashboard`` so list rows share one RPC per paint. */
const dotsBatchQueue = {
    ids: new Set(),
    callbacks: new Map(),
    timer: null,
};

function schedulePipelineDotsBatch(orm) {
    if (dotsBatchQueue.timer) {
        return;
    }
    dotsBatchQueue.timer = setTimeout(async () => {
        dotsBatchQueue.timer = null;
        const ids = [...dotsBatchQueue.ids];
        dotsBatchQueue.ids.clear();
        const cbMap = dotsBatchQueue.callbacks;
        dotsBatchQueue.callbacks = new Map();
        if (!ids.length) {
            return;
        }
        try {
            const data = await orm.call(
                "bhu.project",
                "get_pipeline_dots_for_dashboard",
                [ids]
            );
            for (const pid of ids) {
                const row = data[pid] ?? data[String(pid)];
                const list = cbMap.get(pid) || [];
                for (const cb of list) {
                    cb(row || null);
                }
            }
        } catch (e) {
            console.warn("get_pipeline_dots_for_dashboard batch failed:", e);
            for (const pid of ids) {
                const list = cbMap.get(pid) || [];
                for (const cb of list) {
                    cb(null);
                }
            }
        }
    }, 48);
}

function enqueuePipelineDots(orm, projectId, callback) {
    if (!projectId) {
        callback(null);
        return;
    }
    dotsBatchQueue.ids.add(projectId);
    if (!dotsBatchQueue.callbacks.has(projectId)) {
        dotsBatchQueue.callbacks.set(projectId, []);
    }
    dotsBatchQueue.callbacks.get(projectId).push(callback);
    schedulePipelineDotsBatch(orm);
}

export class ProjectTimelineDialog extends Component {
    static template = "bhukhadan_core.ProjectTimeline";
    static components = { Dialog };
    static props = {
        projectId: { type: Number },
        stages: { type: Array },
        title: { type: String, optional: true },
        villageId: { type: Number, optional: true },
        close: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            stages: this.props.stages || [],
        });
    }

    async refreshProgress() {
        const label = this.props.villageId ? "village pipeline" : "project";
        console.log(`Refreshing progress for ${label}:`, this.props.projectId, this.props.villageId || "");
        try {
            let stages;
            if (this.props.villageId) {
                stages = await this.orm.call(
                    "bhu.project",
                    "get_village_progress_timeline_for_dashboard",
                    [this.props.projectId, this.props.villageId]
                );
            } else {
                stages = await this.orm.call(
                    "bhu.project",
                    "get_project_progress",
                    [this.props.projectId]
                );
            }
            this.state.stages = stages || [];
            console.log("Progress refreshed:", stages);
        } catch (error) {
            console.error("Failed to refresh progress:", error);
        }
    }
}

export class ProjectStageWidget extends Component {
    static template = "bhukhadan_core.StageButton";
    static props = {
        ...standardFieldProps,
        listCompact: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            currentStage: _t("Initial / प्रारंभिक"),
            stageDots: computeStageDots([], false),
        });

        onWillStart(async () => {
            await this.refreshStageSummary();
        });

        onWillUpdateProps(async (nextProps) => {
            const nextId = nextProps.record.resId;
            const prevId = this.props.record.resId;
            const nextEx = Boolean(nextProps.record.data?.is_sia_exempt);
            const prevEx = Boolean(this.props.record.data?.is_sia_exempt);
            const nextLc = Boolean(nextProps.listCompact);
            const prevLc = Boolean(this.props.listCompact);
            if (nextId !== prevId || nextEx !== prevEx || nextLc !== prevLc) {
                await this.refreshStageSummary(nextProps.record, nextProps);
            }
        });
    }

    get listTimelineHint() {
        return _t("Pipeline stages — click for timeline");
    }

    async refreshStageSummary(record, propsRef) {
        const props = propsRef || this.props;
        const rec = record || props.record;
        const pid = rec.resId;
        const exempt = Boolean(rec.data?.is_sia_exempt);
        const listCompact = Boolean(props.listCompact);

        if (!pid) {
            this.state.currentStage = listCompact ? "" : _t("Save project to view stages");
            this.state.stageDots = computeStageDots([], exempt);
            return;
        }

        if (listCompact) {
            this.state.stageDots = computeStageDots([], exempt);
            enqueuePipelineDots(this.orm, pid, (row) => {
                if (row && row.length) {
                    this.state.stageDots = row;
                } else {
                    this.state.stageDots = computeStageDots([], exempt);
                }
            });
            return;
        }

        try {
            const stages = await this.orm.call("bhu.project", "get_project_progress", [pid]);
            const latest = [...stages]
                .reverse()
                .find((s) => s.status === "completed" || s.status === "in_progress");
            this.state.currentStage = latest ? latest.name : _t("Initial / प्रारंभिक");
            this.state.stageDots = computeStageDots(stages, exempt);
        } catch (e) {
            console.error("Failed to fetch project progress", e);
            this.state.stageDots = computeStageDots([], exempt);
        }
    }

    async onStageClick() {
        if (!this.props.record.resId) {
            this.notification.add(_t("Please save the project first."), { type: "warning" });
            return;
        }

        const stages = await this.orm.call(
            "bhu.project",
            "get_project_progress",
            [this.props.record.resId]
        );

        this.dialog.add(ProjectTimelineDialog, {
            projectId: this.props.record.resId,
            stages: stages,
            title: _t("Project Progress Timeline"),
        }, {
            size: "lg",
        });
    }
}

registry.category("fields").add("bhu_project_stage", {
    component: ProjectStageWidget,
    supportedTypes: ["char"],
    extractProps(fieldInfo, dynamicInfo) {
        return {
            readonly: dynamicInfo.readonly,
            listCompact: Boolean(fieldInfo.options?.list_compact),
        };
    },
});
