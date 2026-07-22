/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { Component, onMounted, xml } from "@odoo/owl";

const OVERLAY_ID = "bhu-screenshot-watermark";

function watermarkLabel() {
    const name = session.name || session.partner_display_name || "";
    const login = session.username || "";
    const uid = session.uid || "";
    const parts = [name, login, uid ? `uid:${uid}` : ""].filter(Boolean);
    return parts.join(" · ") || "BhuKhadan";
}

function ensureInlineStyles(root) {
    // Keep readable even if CSS asset bundle is stale / not upgraded yet.
    Object.assign(root.style, {
        position: "fixed",
        inset: "0",
        zIndex: "10050",
        pointerEvents: "none",
        overflow: "hidden",
        opacity: "0.28",
        userSelect: "none",
    });
    const grid = root.querySelector(".bhu-screenshot-watermark__grid");
    if (grid) {
        Object.assign(grid.style, {
            position: "absolute",
            inset: "-45%",
            width: "190%",
            height: "190%",
            display: "flex",
            flexWrap: "wrap",
            alignContent: "flex-start",
            gap: "3.5rem 2.5rem",
            transform: "rotate(-28deg)",
            transformOrigin: "center",
        });
    }
}

export function mountScreenshotWatermark() {
    if (!session.uid || !document.body) {
        return;
    }
    let root = document.getElementById(OVERLAY_ID);
    if (!root) {
        root = document.createElement("div");
        root.id = OVERLAY_ID;
        root.className = "bhu-screenshot-watermark";
        root.setAttribute("aria-hidden", "true");
        const grid = document.createElement("div");
        grid.className = "bhu-screenshot-watermark__grid";
        root.appendChild(grid);
        document.body.appendChild(root);
    }
    ensureInlineStyles(root);
    const grid = root.querySelector(".bhu-screenshot-watermark__grid");
    if (!grid) {
        return;
    }
    const label = watermarkLabel();
    grid.replaceChildren();
    for (let i = 0; i < 60; i++) {
        const tile = document.createElement("span");
        tile.className = "bhu-screenshot-watermark__tile";
        tile.textContent = label;
        Object.assign(tile.style, {
            flex: "0 0 auto",
            whiteSpace: "nowrap",
            fontSize: "1.1rem",
            fontWeight: "700",
            letterSpacing: "0.06em",
            color: "#2c1a4a",
            fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
        });
        grid.appendChild(tile);
    }
}

export function scheduleScreenshotWatermark() {
    const run = () => {
        try {
            mountScreenshotWatermark();
        } catch (err) {
            console.warn("BhuKhadan: watermark mount failed", err);
        }
    };
    run();
    for (const ms of [200, 500, 1000, 2000, 4000, 8000]) {
        setTimeout(run, ms);
    }
}

class BhuScreenshotWatermarkComponent extends Component {
    static template = xml`<div class="d-none" aria-hidden="true"/>`;
    static props = ["*"];

    setup() {
        onMounted(() => scheduleScreenshotWatermark());
    }
}

registry.category("main_components").add("bhu_screenshot_watermark", {
    Component: BhuScreenshotWatermarkComponent,
});

export const bhuScreenshotWatermarkService = {
    start() {
        scheduleScreenshotWatermark();
        return {};
    },
};

registry.category("services").add("bhu_screenshot_watermark", bhuScreenshotWatermarkService);

// Also schedule as soon as the module evaluates (covers late service start).
scheduleScreenshotWatermark();
