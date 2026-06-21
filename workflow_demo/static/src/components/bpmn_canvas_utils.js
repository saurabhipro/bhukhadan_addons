/** @odoo-module **/

/** Minimum zoom so task labels stay readable on large diagrams. */
export const BPMN_MIN_ZOOM = 0.9;
export const BPMN_DEFAULT_ZOOM = 1.0;
export const BPMN_FOCUS_ZOOM = 1.2;

/**
 * Apply zoom that keeps BPMN nodes readable (avoid tiny fit-viewport on wide diagrams).
 * When focusElementId is set, center on that step at focus zoom.
 */
export function applyReadableCanvasZoom(bpmnInstance, options = {}) {
    const {
        focusElementId = null,
        minZoom = BPMN_MIN_ZOOM,
        defaultZoom = BPMN_DEFAULT_ZOOM,
        focusZoom = BPMN_FOCUS_ZOOM,
    } = options;

    const canvas = bpmnInstance.get("canvas");
    canvas.resized();

    if (focusElementId) {
        const elementRegistry = bpmnInstance.get("elementRegistry");
        const element = elementRegistry.get(focusElementId);
        if (element) {
            canvas.scrollToElement(element, {
                top: 140,
                bottom: 140,
                left: 220,
                right: 220,
            });
            canvas.zoom(focusZoom);
            return canvas.zoom();
        }
    }

    canvas.zoom("fit-viewport", "auto");
    const fitZoom = canvas.zoom();
    if (fitZoom < minZoom) {
        canvas.zoom(defaultZoom);
    }
    return canvas.zoom();
}

export function stepCanvasZoom(bpmnInstance, delta) {
    const canvas = bpmnInstance.get("canvas");
    const next = canvas.zoom() + delta;
    canvas.zoom(Math.min(3, Math.max(0.25, next)));
}

export function fitCanvasViewport(bpmnInstance, focusElementId = null) {
    return applyReadableCanvasZoom(bpmnInstance, { focusElementId });
}
