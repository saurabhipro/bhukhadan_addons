/** @odoo-module **/

import { session } from "@web/session";

export function getImpersonationInfo() {
    return session.bhu_impersonator || null;
}

export function getImpersonatedDisplayName() {
    return (
        session.name ||
        session.username ||
        session.partner_display_name ||
        ""
    );
}

export function exitImpersonation() {
    const info = getImpersonationInfo();
    if (!info) {
        return;
    }
    const redirect = encodeURIComponent(
        window.location.pathname + window.location.search || "/web"
    );
    const back = info.back_url || "/bhuarjan/login_as/back";
    window.location.assign(`${back}?redirect=${redirect}`);
}
