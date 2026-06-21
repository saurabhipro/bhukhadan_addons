/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, onWillUpdateProps, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

import { applyReadableCanvasZoom, fitCanvasViewport, stepCanvasZoom } from "../bpmn_canvas_utils";

const BPMN_VIEWER_CDN =
    "https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-navigated-viewer.production.min.js";
const BPMN_MODELER_CDN =
    "https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-modeler.production.min.js";

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

async function loadBpmnViewerLib() {
    document.querySelectorAll(`script[src="${BPMN_MODELER_CDN}"]`).forEach((el) => el.remove());
    const existing = document.querySelector(`script[src="${BPMN_VIEWER_CDN}"]`);
    if (existing?.dataset?.loaded === "1" && window.BpmnJS) {
        return window.BpmnJS;
    }
    if (existing) {
        existing.remove();
    }
    delete window.BpmnJS;
    await Promise.all(BPMN_CSS.map(loadStylesheetOnce));
    await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = BPMN_VIEWER_CDN;
        script.async = true;
        script.onload = () => {
            script.dataset.loaded = "1";
            resolve();
        };
        script.onerror = () => reject(new Error(`Failed to load ${BPMN_VIEWER_CDN}`));
        document.head.appendChild(script);
    });
    if (!window.BpmnJS) {
        throw new Error("BpmnJS viewer not available");
    }
    return window.BpmnJS;
}

function parseHighlightJson(raw) {
    if (!raw) {
        return { current: false, completed: [], workflow_id: false };
    }
    try {
        const data = typeof raw === "string" ? JSON.parse(raw) : raw;
        return {
            current: data.current || false,
            completed: Array.isArray(data.completed) ? data.completed : [],
            workflow_id: data.workflow_id || false,
        };
    } catch {
        return { current: false, completed: [], workflow_id: false };
    }
}

function getMany2oneId(value) {
    if (!value) {
        return false;
    }
    if (Array.isArray(value)) {
        return value[0] || false;
    }
    if (typeof value === "object" && value.id) {
        return value.id;
    }
    return value;
}

export class BpmnViewerField extends Component {
    static template = "bhuarjan_cba_core.BpmnViewerField";
    static props = {
        ...standardFieldProps,
        caseIdField: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.containerRef = useRef("bpmnContainer");
        this.viewer = null;
        this.renderGeneration = 0;
        this.state = useState({
            loading: false,
            error: null,
            legend: "",
            ready: false,
            zoomLevel: 100,
        });

        onMounted(() => {
            this.safeRenderDiagram();
        });
        onWillUpdateProps((nextProps) => {
            const workflowChanged =
                getMany2oneId(nextProps.record.data.workflow_id) !==
                getMany2oneId(this.props.record.data.workflow_id);
            const highlightChanged =
                nextProps.record.data[this.props.name] !==
                this.props.record.data[this.props.name];
            const savedChanged =
                nextProps.record.resId !== this.props.record.resId;

            if (workflowChanged || savedChanged || !this.viewer) {
                this.safeRenderDiagram();
            } else if (highlightChanged && this.viewer) {
                this.applyMarkers();
                this.state.legend = this.buildLegend();
            }
        });
        onWillUnmount(() => {
            this.renderGeneration += 1;
            this.destroyViewer();
        });
    }

    safeRenderDiagram() {
        this.renderDiagram().catch((err) => {
            if (err?.name === "AbortError") {
                return;
            }
            console.error("[CBA BPMN Viewer]", err);
            this.state.error = err.message || String(err);
            this.state.loading = false;
        });
    }

    get highlightData() {
        return parseHighlightJson(this.props.record.data[this.props.name]);
    }

    get workflowId() {
        return (
            getMany2oneId(this.props.record.data.workflow_id) ||
            this.highlightData.workflow_id ||
            false
        );
    }

    async renderDiagram() {
        const generation = ++this.renderGeneration;
        this.state.loading = true;
        this.state.error = null;
        try {
            const BpmnViewer = await loadBpmnViewerLib();
            if (generation !== this.renderGeneration) {
                throw new DOMException("Render superseded", "AbortError");
            }

            let xml;
            const workflowId = this.workflowId;
            if (workflowId) {
                const payload = await this.orm.call(
                    "cba.workflow",
                    "get_modeler_payload",
                    [workflowId]
                );
                xml = payload.bpmn_xml;
            } else {
                const payload = await this.orm.call(
                    "cba.bpmn.definition",
                    "get_bpmn_viewer_payload",
                    []
                );
                xml = payload.bpmn_xml;
            }

            if (generation !== this.renderGeneration) {
                throw new DOMException("Render superseded", "AbortError");
            }

            if (!xml || xml.includes("Loaded from static")) {
                const resp = await fetch(
                    "/bhuarjan_cba_core/static/src/bpmn/lr-department-master-process.bpmn"
                );
                if (!resp.ok) {
                    throw new Error(_t("BPMN diagram file not found."));
                }
                xml = await resp.text();
            }

            if (generation !== this.renderGeneration) {
                throw new DOMException("Render superseded", "AbortError");
            }

            this.destroyViewer();
            const container = this.containerRef.el;
            if (!container) {
                return;
            }
            container.innerHTML = "";
            this.viewer = new BpmnViewer({ container });
            await this.viewer.importXML(xml);

            if (generation !== this.renderGeneration) {
                this.destroyViewer();
                throw new DOMException("Render superseded", "AbortError");
            }

            this.applyMarkers();
            const focusId = this.highlightData.current || null;
            const zoom = applyReadableCanvasZoom(this.viewer, { focusElementId: focusId });
            this.state.zoomLevel = Math.round(zoom * 100);
            this.state.legend = this.buildLegend();
            this.state.ready = true;
        } catch (err) {
            if (err?.name === "AbortError") {
                throw err;
            }
            console.error("[CBA BPMN Viewer]", err);
            this.state.error = err.message || String(err);
            this.state.ready = false;
        } finally {
            if (generation === this.renderGeneration) {
                this.state.loading = false;
            }
        }
    }

    buildLegend() {
        const { current, completed } = this.highlightData;
        const parts = [];
        if (current) {
            parts.push(_t("Current: %s", current));
        }
        if (completed.length) {
            parts.push(_t("%s step(s) completed", completed.length));
        }
        return parts.join(" · ");
    }

    applyMarkers() {
        if (!this.viewer) {
            return;
        }
        try {
            const canvas = this.viewer.get("canvas");
            const elementRegistry = this.viewer.get("elementRegistry");
            const { current, completed } = this.highlightData;

            for (const element of elementRegistry.getAll()) {
                canvas.removeMarker(element.id, "cba-done");
                canvas.removeMarker(element.id, "cba-current");
            }
            for (const bpmnId of completed) {
                if (elementRegistry.get(bpmnId)) {
                    canvas.addMarker(bpmnId, "cba-done");
                }
            }
            if (current && elementRegistry.get(current)) {
                canvas.addMarker(current, "cba-current");
                canvas.scrollToElement(elementRegistry.get(current), {
                    top: 140,
                    bottom: 140,
                    left: 220,
                    right: 220,
                });
                if (canvas.zoom() < 1.0) {
                    canvas.zoom(1.2);
                }
                this.state.zoomLevel = Math.round(canvas.zoom() * 100);
            }
        } catch (err) {
            console.warn("[CBA BPMN Viewer] marker update failed", err);
        }
    }

    zoomIn(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.viewer) return;
        stepCanvasZoom(this.viewer, 0.15);
        this.state.zoomLevel = Math.round(this.viewer.get("canvas").zoom() * 100);
    }

    zoomOut(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.viewer) return;
        stepCanvasZoom(this.viewer, -0.15);
        this.state.zoomLevel = Math.round(this.viewer.get("canvas").zoom() * 100);
    }

    zoomReset(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.viewer) return;
        const zoom = fitCanvasViewport(this.viewer, this.highlightData.current || null);
        this.state.zoomLevel = Math.round(zoom * 100);
    }

    destroyViewer() {
        if (this.viewer) {
            try {
                this.viewer.destroy();
            } catch (err) {
                console.warn("[CBA BPMN Viewer] destroy failed", err);
            }
            this.viewer = null;
        }
    }
}

export const bpmnViewerField = {
    component: BpmnViewerField,
    supportedTypes: ["char"],
};

registry.category("fields").add("cba_bpmn_viewer", bpmnViewerField);
