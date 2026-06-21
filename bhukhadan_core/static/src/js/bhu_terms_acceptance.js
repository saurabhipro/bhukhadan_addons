/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { rpc } from "@web/core/network/rpc";
import { Component, onMounted, xml } from "@odoo/owl";

const OVERLAY_ID = "bhu-terms-gate-overlay";

const DISCLAIMER_HTML = `
<p>The <strong>BhuKhadan</strong> application is a software platform developed and maintained by
<strong>Redmelon Technologies Private Limited</strong> ("Redmelon") solely for the purpose of
facilitating digital processing, workflow management, record keeping, and payment administration
activities as configured by the concerned Department/Authority.</p>
<p>All payment-related information, including but not limited to beneficiary details, ownership
records, bank account information, compensation amounts, award calculations, approvals, and payment
authorizations, are entered, verified, approved, and processed by authorized officials of the
concerned Department/Authority.</p>
<p>Redmelon does not verify, validate, audit, certify, or guarantee the accuracy, completeness,
authenticity, or legality of any data entered into the system by users. The responsibility for
ensuring the correctness of beneficiary details, payment amounts, ownership records, and all related
approvals rests exclusively with the concerned Department/Authority and its authorized users.</p>
<p>Redmelon shall not be liable for any direct, indirect, incidental, consequential, financial, legal,
or administrative loss, damage, claim, dispute, recovery proceeding, excess payment, short payment,
duplicate payment, erroneous payment, fraudulent payment, or payment made to an incorrect beneficiary
arising from or related to the use of the application, incorrect data entry, improper verification,
unauthorized access, user error, or departmental decisions.</p>
<p>By using the BhuKhadan application, the Department/Authority acknowledges and agrees that all payment
approvals and disbursements are undertaken at its sole responsibility and risk. The Department/Authority
shall remain solely responsible for compliance with all applicable laws, rules, notifications, financial
regulations, audit requirements, and departmental procedures governing such payments.</p>
<p>Redmelon acts only as a technology service provider and shall not be considered a party to any payment
transaction, compensation determination, ownership verification process, or beneficiary entitlement
decision conducted through the application.</p>`;

async function fetchTermsAccepted() {
    if (session.bhu_terms_accepted === true) {
        return true;
    }
    if (session.bhu_terms_accepted === false) {
        return false;
    }
    try {
        const res = await rpc("/bhuarjan/terms/status", {});
        session.bhu_terms_accepted = !!res.accepted;
        return session.bhu_terms_accepted;
    } catch (err) {
        console.warn("BhuKhadan: terms status check failed", err);
        return false;
    }
}

function removeTermsOverlay() {
    document.getElementById(OVERLAY_ID)?.remove();
}

function mountTermsOverlay() {
    if (document.getElementById(OVERLAY_ID)) {
        return;
    }

    const overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.className = "bhu-terms-gate-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "bhu-terms-gate-title");

    overlay.innerHTML = `
        <div class="bhu-terms-gate-backdrop"></div>
        <div class="bhu-terms-gate-panel">
            <div class="bhu-terms-gate-panel-head">
                <span class="bhu-terms-gate-kicker">Required before you continue</span>
                <h2 id="bhu-terms-gate-title">BhuKhadan Terms &amp; Conditions</h2>
                <p class="bhu-terms-gate-lead">
                    Please read and accept the terms and payment processing disclaimer to use BhuKhadan.
                </p>
            </div>
            <h3 class="bhu-terms-gate-subtitle">Disclaimer Regarding Payment Processing and Liability</h3>
            <div class="bhu-terms-gate-scroll">${DISCLAIMER_HTML}</div>
            <p class="bhu-terms-gate-links">
                <a href="/terms-and-conditions" target="_blank" rel="noopener noreferrer">Terms &amp; Conditions</a>
                &nbsp;·&nbsp;
                <a href="/privacy-policy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
            </p>
            <label class="bhu-terms-gate-check">
                <input type="checkbox" id="bhu-terms-gate-checkbox"/>
                <span>
                    I have read and agree to the BhuKhadan Terms &amp; Conditions and Privacy Policy,
                    including the payment processing disclaimer above.
                </span>
            </label>
            <div class="bhu-terms-gate-actions">
                <button type="button" class="btn btn-primary bhu-terms-gate-accept" disabled>
                    Accept &amp; Continue
                </button>
            </div>
        </div>`;

    const checkbox = overlay.querySelector("#bhu-terms-gate-checkbox");
    const acceptBtn = overlay.querySelector(".bhu-terms-gate-accept");

    checkbox.addEventListener("change", () => {
        acceptBtn.disabled = !checkbox.checked;
    });

    acceptBtn.addEventListener("click", async () => {
        if (!checkbox.checked || acceptBtn.classList.contains("is-loading")) {
            return;
        }
        acceptBtn.classList.add("is-loading");
        acceptBtn.textContent = "Please wait…";
        acceptBtn.disabled = true;
        try {
            await rpc("/bhuarjan/terms/accept", {});
            session.bhu_terms_accepted = true;
            removeTermsOverlay();
        } catch (err) {
            console.error("BhuKhadan: terms acceptance failed", err);
            acceptBtn.classList.remove("is-loading");
            acceptBtn.textContent = "Accept & Continue";
            acceptBtn.disabled = !checkbox.checked;
        }
    });

    document.body.appendChild(overlay);
}

export async function ensureBhuTermsAcceptanceGate() {
    if (!session.uid) {
        return;
    }
    const accepted = await fetchTermsAccepted();
    if (accepted) {
        removeTermsOverlay();
        return;
    }
    mountTermsOverlay();
}

export function scheduleBhuTermsAcceptanceGate() {
    const run = () => ensureBhuTermsAcceptanceGate();
    run();
    for (const ms of [300, 800, 1500, 3000, 6000, 10000]) {
        setTimeout(run, ms);
    }
}

/** Mounts with every backend web-client load (independent of WebClient patch). */
class BhuTermsGateMainComponent extends Component {
    static template = xml`<div class="d-none" aria-hidden="true"/>`;
    static props = ["*"];

    setup() {
        onMounted(() => scheduleBhuTermsAcceptanceGate());
    }
}

registry.category("main_components").add("bhu_terms_gate", {
    Component: BhuTermsGateMainComponent,
});

/** Runs as soon as the web client services start. */
export const bhuTermsGateService = {
    start() {
        scheduleBhuTermsAcceptanceGate();
        return {};
    },
};

registry.category("services").add("bhu_terms_gate", bhuTermsGateService);
