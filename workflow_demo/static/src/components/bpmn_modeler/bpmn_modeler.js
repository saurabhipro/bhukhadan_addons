/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

import { applyReadableCanvasZoom } from "../bpmn_canvas_utils";

const BPMN_MODELER_CDN =
    "https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-modeler.production.min.js";
const BPMN_VIEWER_CDN =
    "https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-viewer.production.min.js";

const BPMN_CSS = [
    "https://unpkg.com/bpmn-js@17.11.1/dist/assets/diagram-js.css",
    "https://unpkg.com/bpmn-js@17.11.1/dist/assets/bpmn-js.css",
    "https://unpkg.com/bpmn-js@17.11.1/dist/assets/bpmn-font/css/bpmn-embedded.css",
];

function loadStylesheetOnce(url) {
    if (document.querySelector(`link[href="${url}"]`)) {
        return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = url;
        link.onload = () => resolve();
        link.onerror = () => reject(new Error(url));
        document.head.appendChild(link);
    });
}

function loadScript(url) {
    const existing = document.querySelector(`script[src="${url}"]`);
    if (existing) {
        existing.remove();
    }
    delete window.BpmnJS;
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = url;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`Failed to load ${url}`));
        document.head.appendChild(script);
    });
}

const BPMN_NAVIGATED_VIEWER_CDN =
    "https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-navigated-viewer.production.min.js";

async function loadBpmnModelerLib() {
    document.querySelectorAll(`script[src="${BPMN_VIEWER_CDN}"], script[src="${BPMN_NAVIGATED_VIEWER_CDN}"]`).forEach((el) => el.remove());
    await Promise.all(BPMN_CSS.map(loadStylesheetOnce));
    await loadScript(BPMN_MODELER_CDN);
    if (!window.BpmnJS) {
        throw new Error("BpmnJS modeler not available");
    }
    return window.BpmnJS;
}

export class BpmnModelerField extends Component {
    static template = "bhuarjan_cba_core.BpmnModelerField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.containerRef = useRef("bpmnContainer");
        this.fileInputRef = useRef("fileInput");
        this.modeler = null;
        this.resizeObserver = null;
        this.state = useState({
            loading: true,
            saving: false,
            syncing: false,
            importing: false,
            error: null,
            dirty: false,
        });

        onMounted(() => this.initModeler());
        onWillUnmount(() => this.cleanup());
    }

    get workflowId() {
        return this.props.record.resId;
    }

    async initModeler() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const BpmnModeler = await loadBpmnModelerLib();
            if (!this.workflowId) {
                return;
            }
            const payload = await this.orm.call(
                "cba.workflow",
                "get_modeler_payload",
                [this.workflowId]
            );
            this.destroyModeler();
            const container = this.containerRef.el;
            if (!container) {
                return;
            }
            container.innerHTML = "";
            this.modeler = new BpmnModeler({ container });
            await this.modeler.importXML(payload.bpmn_xml);
            this.fitAndResize();
            const eventBus = this.modeler.get("eventBus");
            eventBus.on("commandStack.changed", () => {
                this.state.dirty = true;
            });
            this.setupElementDoubleClick(eventBus);
            this.setupSequenceFlowClick(eventBus);
            this.setupResizeObserver(container);
        } catch (err) {
            console.error("[CBA BPMN Modeler]", err);
            this.state.error = err.message || String(err);
        } finally {
            this.state.loading = false;
        }
    }

    setupElementDoubleClick(eventBus) {
        const skipTypes = new Set([
            "bpmn:SequenceFlow",
            "label",
            "bpmn:Lane",
            "bpmn:Participant",
            "bpmn:Process",
            "bpmn:Collaboration",
        ]);
        eventBus.on("element.dblclick", 2000, (event) => {
            const element = event.element;
            if (!element || skipTypes.has(element.type)) {
                return;
            }
            event.preventDefault?.();
            event.stopPropagation?.();
            this.openNodeActivityForm(element);
        });
    }

    setupSequenceFlowClick(eventBus) {
        eventBus.on("element.click", 2000, (event) => {
            const element = event.element;
            if (!element || element.type !== "bpmn:SequenceFlow") {
                return;
            }
            event.preventDefault?.();
            event.stopPropagation?.();
            this.openTransitionForm(element);
        });
    }

    async openTransitionForm(element) {
        if (!this.workflowId || !element?.businessObject?.id) {
            return;
        }
        const bo = element.businessObject;
        const bpmnFlowId = bo.id;
        const flowName = bo.name || bpmnFlowId;
        const sourceRef = bo.sourceRef?.id;
        const targetRef = bo.targetRef?.id;
        try {
            const action = await this.orm.call(
                "cba.workflow",
                "action_open_transition_by_bpmn_flow",
                [[this.workflowId], bpmnFlowId, flowName, sourceRef, targetRef]
            );
            await this.action.doAction(action, {
                onClose: () => this.syncFlowLabelFromTransition(bpmnFlowId),
            });
        } catch (err) {
            console.error("[CBA BPMN Modeler] open transition form failed", err);
            this.notification.add(err.message || String(err), { type: "danger" });
        }
    }

    async syncFlowLabelFromTransition(bpmnFlowId) {
        if (!this.modeler || !this.workflowId || !bpmnFlowId) {
            return;
        }
        try {
            const transitions = await this.orm.searchRead(
                "cba.workflow.transition",
                [
                    ["workflow_id", "=", this.workflowId],
                    ["bpmn_flow_id", "=", bpmnFlowId],
                ],
                ["name"]
            );
            if (!transitions.length) {
                return;
            }
            const elementRegistry = this.modeler.get("elementRegistry");
            const modeling = this.modeler.get("modeling");
            const canvasElement = elementRegistry.get(bpmnFlowId);
            if (canvasElement) {
                modeling.updateProperties(canvasElement, { name: transitions[0].name });
            }
            await this.props.record.load();
        } catch (err) {
            console.warn("[CBA BPMN Modeler] flow label sync failed", err);
        }
    }

    async openNodeActivityForm(element) {
        if (!this.workflowId || !element?.businessObject?.id) {
            return;
        }
        const bpmnId = element.businessObject.id;
        const elementName = element.businessObject.name || bpmnId;
        try {
            const action = await this.orm.call(
                "cba.workflow",
                "action_open_node_by_bpmn_element",
                [[this.workflowId], bpmnId, element.type, elementName]
            );
            await this.action.doAction(action, {
                onClose: () => this.syncElementLabelFromNode(bpmnId),
            });
        } catch (err) {
            console.error("[CBA BPMN Modeler] open node form failed", err);
            this.notification.add(err.message || String(err), { type: "danger" });
        }
    }

    async syncElementLabelFromNode(bpmnId) {
        if (!this.modeler || !this.workflowId || !bpmnId) {
            return;
        }
        try {
            const nodes = await this.orm.searchRead(
                "cba.workflow.node",
                [
                    ["workflow_id", "=", this.workflowId],
                    ["bpmn_id", "=", bpmnId],
                ],
                ["name"]
            );
            if (!nodes.length) {
                return;
            }
            const elementRegistry = this.modeler.get("elementRegistry");
            const modeling = this.modeler.get("modeling");
            const canvasElement = elementRegistry.get(bpmnId);
            if (canvasElement) {
                modeling.updateProperties(canvasElement, { name: nodes[0].name });
            }
            await this.props.record.load();
        } catch (err) {
            console.warn("[CBA BPMN Modeler] label sync failed", err);
        }
    }

    setupResizeObserver(container) {
        if (typeof ResizeObserver === "undefined") {
            return;
        }
        this.resizeObserver = new ResizeObserver(() => this.fitAndResize());
        this.resizeObserver.observe(container);
    }

    fitAndResize() {
        if (!this.modeler) {
            return;
        }
        try {
            applyReadableCanvasZoom(this.modeler);
        } catch (err) {
            console.warn("[CBA BPMN Modeler] resize failed", err);
        }
    }

    async getCurrentXml() {
        if (!this.modeler) {
            throw new Error(_t("BPMN designer is not ready yet."));
        }
        const { xml } = await this.modeler.saveXML({ format: true });
        return xml;
    }

    async saveDiagram(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.modeler || !this.workflowId) {
            return;
        }
        this.state.saving = true;
        try {
            const xml = await this.getCurrentXml();
            await this.orm.call("cba.workflow", "save_bpmn_xml", [[this.workflowId], xml]);
            await this.props.record.load();
            this.state.dirty = false;
            this.notification.add(_t("BPMN diagram saved."), { type: "success" });
        } catch (err) {
            console.error("[CBA BPMN Modeler] save failed", err);
            this.notification.add(err.message || String(err), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    async syncNodesAndTransfers(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.modeler || !this.workflowId) {
            this.notification.add(_t("Open a saved workflow first."), { type: "warning" });
            return;
        }
        this.state.syncing = true;
        try {
            const xml = await this.getCurrentXml();
            const result = await this.orm.call(
                "cba.workflow",
                "sync_bpmn_xml",
                [[this.workflowId], xml]
            );
            await this.props.record.load();
            this.state.dirty = false;
            this.notification.add(
                _t("Synced %s node(s) and %s transfer(s).", result.node_count, result.transition_count),
                { type: "success" }
            );
        } catch (err) {
            console.error("[CBA BPMN Modeler] sync failed", err);
            this.notification.add(err.message || String(err), { type: "danger" });
        } finally {
            this.state.syncing = false;
        }
    }

    async downloadBpmn(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.modeler) {
            return;
        }
        try {
            const xml = await this.getCurrentXml();
            this._downloadBlob(new Blob([xml], { type: "application/xml" }), "workflow.bpmn");
        } catch (err) {
            this.notification.add(err.message || String(err), { type: "danger" });
        }
    }

    async downloadSvg(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.modeler) {
            return;
        }
        try {
            const { svg } = await this.modeler.saveSVG();
            this._downloadBlob(new Blob([svg], { type: "image/svg+xml" }), "workflow.svg");
        } catch (err) {
            this.notification.add(err.message || String(err), { type: "danger" });
        }
    }

    _downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
    }

    triggerImport(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        const input = this.fileInputRef.el;
        if (input) {
            input.value = "";
            input.click();
        }
    }

    async onFileSelected(ev) {
        ev?.stopPropagation?.();
        const file = ev.target.files?.[0];
        if (!file) {
            return;
        }
        if (!this.modeler || !this.workflowId) {
            this.notification.add(_t("Open a saved workflow first."), { type: "warning" });
            return;
        }
        this.state.importing = true;
        try {
            const text = await file.text();
            await this.modeler.importXML(text);
            this.fitAndResize();
            const xml = await this.getCurrentXml();
            const result = await this.orm.call(
                "cba.workflow",
                "sync_bpmn_xml",
                [[this.workflowId], xml]
            );
            await this.props.record.load();
            this.state.dirty = false;
            this.notification.add(
                _t(
                    "BPMN imported — synced %s node(s) and %s transfer(s).",
                    result.node_count,
                    result.transition_count
                ),
                { type: "success" }
            );
        } catch (err) {
            console.error("[CBA BPMN Modeler] import failed", err);
            this.notification.add(err.message || String(err), { type: "danger" });
        } finally {
            this.state.importing = false;
            if (ev.target) {
                ev.target.value = "";
            }
        }
    }

    destroyModeler() {
        if (this.modeler) {
            this.modeler.destroy();
            this.modeler = null;
        }
    }

    cleanup() {
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        this.destroyModeler();
    }
}

export const bpmnModelerField = {
    component: BpmnModelerField,
    supportedTypes: ["text"],
};

registry.category("fields").add("cba_bpmn_modeler", bpmnModelerField);
