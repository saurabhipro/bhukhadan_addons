/** @odoo-module **/

// Robust logout handler for mobile: force a hard navigation to the logout URL
// Works even if overlays or event handlers interfere with the default action

import { registry } from "@odoo/web";

const LOGOUT_URL = "/web/session/logout";

function goLogout() {
    try {
        window.location.href = LOGOUT_URL;
    } catch (e) {
        try {
            window.location.assign(LOGOUT_URL);
        } catch (_) {
            // Fallback
            window.location = LOGOUT_URL;
        }
    }
}

registry.category("services").add("bhukhadan_core.logout_fix", {
    start() {
        // Capture taps/clicks on any logout-related element
        document.addEventListener(
            "click",
            (ev) => {
                const target = ev.target;
                if (!target) return;
                const link = target.closest(
                    'a[href="/web/session/logout"], [data-menu="logout"], a[data-action="logout"], button[data-action="logout"]'
                );
                if (link) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    goLogout();
                }
            },
            true // use capture to reliably intercept on mobile
        );
    },
});


