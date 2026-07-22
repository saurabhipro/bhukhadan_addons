/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { onMounted } from "@odoo/owl";
import {
    exitImpersonation,
    getImpersonatedDisplayName,
    getImpersonationInfo,
} from "../../js/login_as_banner";
import { scheduleBhuTermsAcceptanceGate } from "../../js/bhu_terms_acceptance";
import { scheduleScreenshotWatermark } from "../../js/screenshot_watermark";

patch(WebClient.prototype, {
    setup() {
        super.setup();

        onMounted(() => {
            this.makeLogoClickable();
            this._scheduleImpersonationNav();
            scheduleBhuTermsAcceptanceGate();
            scheduleScreenshotWatermark();
        });
    },

    _scheduleImpersonationNav() {
        const mount = () => this._ensureImpersonationNav();
        mount();
        setTimeout(mount, 300);
        setTimeout(mount, 1200);
    },

    _ensureImpersonationNav() {
        const info = getImpersonationInfo();
        // Remove legacy bottom-left control if still present
        document.getElementById("bhu-impersonation-fab")?.remove();

        const navbar = document.querySelector(".o_main_navbar");
        if (!navbar) {
            return;
        }

        let wrap = document.getElementById("bhu-impersonation-nav");
        if (!info) {
            wrap?.remove();
            return;
        }

        const asUser = getImpersonatedDisplayName();
        const adminName = info.name || "";
        const title = asUser
            ? `Viewing as ${asUser}${adminName ? ` — return to ${adminName}` : ""}`
            : "Exit impersonation";

        if (!wrap) {
            wrap = document.createElement("div");
            wrap.id = "bhu-impersonation-nav";
            wrap.className = "bhu-impersonation-nav";
            navbar.appendChild(wrap);
        }

        let btn = wrap.querySelector(".bhu-impersonation-nav-btn");
        if (!btn) {
            btn = document.createElement("button");
            btn.type = "button";
            btn.className = "bhu-impersonation-nav-btn";
            btn.addEventListener("click", () => exitImpersonation());
            wrap.appendChild(btn);
        }

        btn.title = title;
        btn.innerHTML = `<i class="fa fa-sign-out" aria-hidden="true"></i><span class="bhu-impersonation-nav-label">Exit impersonation</span>`;
    },

    makeLogoClickable() {
        setTimeout(() => {
            const logoElements = document.querySelectorAll(
                '.o_main_navbar .navbar-brand, .o_main_navbar [data-menu="root"]'
            );

            logoElements.forEach((logo) => {
                if (!logo.hasAttribute("data-dashboard-click")) {
                    logo.setAttribute("data-dashboard-click", "true");
                    logo.style.cursor = "pointer";
                    logo.addEventListener("click", (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (this.env.services.action) {
                            this.env.services.action.doAction(
                                "bhukhadan_core.action_role_based_dashboard",
                                { clearBreadcrumbs: true }
                            );
                        } else {
                            window.location.href =
                                "/web#action=bhukhadan_core.action_role_based_dashboard";
                        }
                    });
                }
            });
        }, 1500);
    },
});
