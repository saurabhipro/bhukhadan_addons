/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

const IFSC_CODE_RE = /^[A-Za-z]{4}0[A-Za-z0-9]{6}$/;
const ACCOUNT_RE = /^\d{9,18}$/;

function _pvLeValidateIfsc(ifsc, contextLabel) {
    const code = (ifsc || "").trim().toUpperCase();
    if (!code) {
        throw new Error(`Please enter IFSC${contextLabel ? ` (${contextLabel})` : ""}.`);
    }
    if (!IFSC_CODE_RE.test(code)) {
        throw new Error(
            `Invalid IFSC "${ifsc.trim()}"${contextLabel ? ` for ${contextLabel}` : ""}. ` +
            "Use format: 4 letters + 0 + 6 alphanumeric characters (e.g. SBIN0001234)."
        );
    }
    return code;
}

function _pvLeValidateAccount(acct, contextLabel) {
    const num = (acct || "").trim().replace(/\s+/g, "");
    if (!num) {
        throw new Error(`Please enter account number${contextLabel ? ` (${contextLabel})` : ""}.`);
    }
    if (!ACCOUNT_RE.test(num)) {
        throw new Error(
            `Invalid account number "${acct.trim()}"${contextLabel ? ` for ${contextLabel}` : ""}. ` +
            "Use 9–18 digits only."
        );
    }
    return num;
}

function _pvLeValidatePayload(payload, config) {
    const khasra = config.khasra_number || config.khasra || "khasra";
    if (payload.payout_mode === "single") {
        _pvLeValidateAccount(payload.account_number, khasra);
        _pvLeValidateIfsc(payload.ifsc_code, khasra);
        payload.ifsc_code = (payload.ifsc_code || "").trim().toUpperCase();
        payload.account_number = (payload.account_number || "").trim().replace(/\s+/g, "");
        return;
    }
    for (const row of payload.splits || []) {
        const label = row.payee_name || khasra;
        row.account_number = _pvLeValidateAccount(row.account_number, label);
        row.ifsc_code = _pvLeValidateIfsc(row.ifsc_code, label);
    }
}

function _pvLeParseConfig(root) {
    const script = root.querySelector(".bhu_pv_le_config");
    if (!script || !script.textContent) {
        return null;
    }
    try {
        return JSON.parse(script.textContent);
    } catch (_e) {
        return null;
    }
}

function _pvLeFmtMoney(sym, amount) {
    const n = Number(amount) || 0;
    return `${sym}${n.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
}

function _pvLeBankOptions(banks, selectedId) {
    const parts = ['<option value="">Bank…</option>'];
    for (const bank of banks || []) {
        const sel = selectedId && Number(selectedId) === Number(bank.id) ? " selected" : "";
        const name = (bank.name || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        parts.push(`<option value="${bank.id}"${sel}>${name}</option>`);
    }
    return parts.join("");
}

function _pvLeRenderSplitRows(root, config, rows) {
    const tbody = root.querySelector('[data-role="split-body"]');
    if (!tbody) {
        return;
    }
    const sym = config.currency_symbol || "₹";
    const payable = Number(config.payable) || 0;
    const banks = config.banks || [];
    const html = (rows || []).map((row) => {
        const payee = (row.payee_name || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
        const pct = Number(row.percent_share) || 0;
        const amt = row.amount != null
            ? Number(row.amount)
            : Math.round((payable * pct) / 100 * 100) / 100;
        const acct = (row.account_number || "")
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;");
        const ifsc = (row.ifsc_code || "")
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;");
        return (
            `<tr class="bhu_pv_le_split_row" data-split-id="${row.id || ""}" ` +
            `data-landowner-id="${row.landowner_id || 0}">` +
            `<td class="bhu_pv_le_payee" title="${payee}">${payee}</td>` +
            `<td class="bhu_pv_le_pct"><input type="number" class="bhu_pv_le_input bhu_pv_le_pct_in" ` +
            `min="0" max="100" step="0.01" value="${pct.toFixed(2)}"/></td>` +
            `<td class="bhu_pv_le_amt tabular-nums" data-role="amount">${_pvLeFmtMoney(sym, amt)}</td>` +
            `<td class="bhu_pv_le_bank"><select class="bhu_pv_le_input bhu_pv_le_bank_sel">` +
            `${_pvLeBankOptions(banks, row.bank_id)}</select></td>` +
            `<td class="bhu_pv_le_acct"><input type="text" class="bhu_pv_le_input bhu_pv_le_acct_in" ` +
            `value="${acct}" placeholder="Account"/></td>` +
            `<td class="bhu_pv_le_ifsc"><input type="text" class="bhu_pv_le_input bhu_pv_le_ifsc_in" ` +
            `value="${ifsc}" placeholder="IFSC"/></td></tr>`
        );
    }).join("");
    tbody.innerHTML = html || (
        '<tr><td colspan="6" class="text-muted text-center py-2">No payees for this khasra</td></tr>'
    );
}

function _pvLeUpdateSplitStatus(root, config) {
    const statusEl = root.querySelector('[data-role="split-status"]');
    if (!statusEl) {
        return;
    }
    const sym = config.currency_symbol || "₹";
    const payable = Number(config.payable) || 0;
    let totalP = 0;
    root.querySelectorAll(".bhu_pv_le_pct_in").forEach((inp) => {
        totalP += Number(inp.value) || 0;
    });
    if (Math.abs(totalP - 100) <= 0.02) {
        statusEl.className = "bhu_pv_le_status bhu_pv_le_status_ok";
        statusEl.textContent = `OK — 100% · ${_pvLeFmtMoney(sym, payable)}`;
        statusEl.classList.remove("d-none");
    } else if (totalP > 0) {
        statusEl.className = "bhu_pv_le_status bhu_pv_le_status_warn";
        statusEl.textContent = `Percent total is ${totalP.toFixed(2)} (must be 100).`;
        statusEl.classList.remove("d-none");
    } else {
        statusEl.classList.add("d-none");
    }
}

function _pvLeRecalcAmounts(root, config) {
    const sym = config.currency_symbol || "₹";
    const payable = Number(config.payable) || 0;
    root.querySelectorAll(".bhu_pv_le_split_row").forEach((tr) => {
        const pctIn = tr.querySelector(".bhu_pv_le_pct_in");
        const amtCell = tr.querySelector('[data-role="amount"]');
        if (!pctIn || !amtCell) {
            return;
        }
        const pct = Number(pctIn.value) || 0;
        const amt = Math.round((payable * pct) / 100 * 100) / 100;
        amtCell.textContent = _pvLeFmtMoney(sym, amt);
    });
    _pvLeUpdateSplitStatus(root, config);
}

function _pvLeSetMode(root, config, mode) {
    root.querySelectorAll(".bhu_pv_le_mode").forEach((btn) => {
        btn.classList.toggle("is-on", btn.dataset.mode === mode);
    });
    root.querySelectorAll(".bhu_pv_le_panel").forEach((panel) => {
        panel.classList.toggle("d-none", panel.dataset.panel !== mode);
    });
    config.payout_mode = mode;
}

function _pvLeGetActiveMode(root, config) {
    const active = root.querySelector(".bhu_pv_le_mode.is-on");
    return active?.dataset.mode || config.payout_mode || "single";
}

function _pvLeCollectPayload(root, config) {
    const mode = _pvLeGetActiveMode(root, config);
    if (mode === "single") {
        const bankSel = root.querySelector(".bhu_pv_le_single_bank");
        const acct = root.querySelector(".bhu_pv_le_single_acct");
        const ifsc = root.querySelector(".bhu_pv_le_single_ifsc");
        return {
            payout_mode: "single",
            bank_id: bankSel && bankSel.value ? Number(bankSel.value) : false,
            account_number: acct ? acct.value.trim() : "",
            ifsc_code: ifsc ? ifsc.value.trim() : "",
            splits: [],
        };
    }
    const splits = [];
    root.querySelectorAll(".bhu_pv_le_split_row").forEach((tr) => {
        const payeeCell = tr.querySelector(".bhu_pv_le_payee");
        const pctIn = tr.querySelector(".bhu_pv_le_pct_in");
        const bankSel = tr.querySelector(".bhu_pv_le_bank_sel");
        const acctIn = tr.querySelector(".bhu_pv_le_acct_in");
        const ifscIn = tr.querySelector(".bhu_pv_le_ifsc_in");
        if (!pctIn) {
            return;
        }
        const rawId = tr.dataset.splitId;
        const splitId =
            rawId && Number.isFinite(Number(rawId)) && Number(rawId) > 0
                ? Number(rawId)
                : false;
        splits.push({
            id: splitId,
            landowner_id: Number(tr.dataset.landownerId) || false,
            payee_name: payeeCell ? payeeCell.textContent.trim() : "",
            percent_share: Number(pctIn.value) || 0,
            bank_id: bankSel && bankSel.value ? Number(bankSel.value) : false,
            account_number: acctIn ? acctIn.value.trim() : "",
            ifsc_code: ifscIn ? ifscIn.value.trim() : "",
        });
    });
    return { payout_mode: "split", splits };
}

function _pvLeDialog(root) {
    return root.closest(".o_dialog");
}

function _pvLeWaitDialogClosed(dialogEl) {
    return new Promise((resolve) => {
        if (!dialogEl || !document.body.contains(dialogEl)) {
            resolve();
            return;
        }
        const timeoutId = window.setTimeout(() => {
            observer.disconnect();
            resolve();
        }, 600);
        const observer = new MutationObserver(() => {
            if (!document.body.contains(dialogEl)) {
                window.clearTimeout(timeoutId);
                observer.disconnect();
                resolve();
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });
}

function _pvLeCloseDialog(root) {
    const dialog = _pvLeDialog(root);
    if (!dialog) {
        return null;
    }
    const cancelBtn =
        dialog.querySelector(".o_form_button_cancel") ||
        dialog.querySelector('button[special="cancel"]') ||
        dialog.querySelector(".btn-close");
    cancelBtn?.click();
    return dialog;
}

function _pvLeApplyUiSnapshot(snapshot) {
    document.dispatchEvent(
        new CustomEvent("bhu-pv-ui-snapshot", { detail: snapshot || {} })
    );
}

function _pvLeRpcErrorMessage(err) {
    const data = err?.data || err?.error?.data;
    return (
        data?.message ||
        err?.message?.data?.message ||
        err?.message ||
        "Could not save. Check bank details and split percentages."
    );
}

async function _pvLeSaveLine(root, config, saveBtn) {
    if (saveBtn) {
        saveBtn.disabled = true;
    }
    try {
        const payload = _pvLeCollectPayload(root, config);
        if (payload.payout_mode === "split" && (!payload.splits || payload.splits.length < 2)) {
            throw new Error(
                "Split mode needs at least two payee rows. Close and reopen this khasra, then try Save again."
            );
        }
        _pvLeValidatePayload(payload, config);
        const snapshot = await rpc("/web/dataset/call_kw", {
            model: "bhu.payment.voucher.line",
            method: "apply_line_editor_payload",
            args: [config.line_id, payload],
            kwargs: {},
        });
        const dialogEl = _pvLeCloseDialog(root);
        if (dialogEl) {
            await _pvLeWaitDialogClosed(dialogEl);
        }
        await new Promise((resolve) => window.setTimeout(resolve, 50));
        _pvLeApplyUiSnapshot(snapshot);
    } catch (err) {
        if (saveBtn) {
            saveBtn.disabled = false;
        }
        window.alert(_pvLeRpcErrorMessage(err));
    }
}

function _pvLeBindDialogFooter(root, config) {
    const dialog = _pvLeDialog(root);
    if (!dialog) {
        return false;
    }
    const saveBtn =
        dialog.querySelector(".o_form_button_save") ||
        dialog.querySelector('button[special="save"]');
    if (!saveBtn || saveBtn.dataset.pvLeBound === "1") {
        return !!saveBtn;
    }
    saveBtn.dataset.pvLeBound = "1";
    saveBtn.addEventListener(
        "click",
        async (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            ev.stopImmediatePropagation();
            const editorRoot = dialog.querySelector(".bhu_pv_line_editor");
            if (!editorRoot) {
                return;
            }
            let cfg = _pvLeParseConfig(editorRoot) || config;
            if (!cfg?.line_id) {
                return;
            }
            cfg = { ...cfg, payout_mode: _pvLeGetActiveMode(editorRoot, cfg) };
            editorRoot._pvLeConfig = cfg;
            await _pvLeSaveLine(editorRoot, cfg, saveBtn);
        },
        true
    );
    return true;
}

function _pvLeBindFooterRetry(root, config, attempt = 0) {
    if (_pvLeBindDialogFooter(root, config) || attempt >= 15) {
        return;
    }
    window.setTimeout(() => _pvLeBindFooterRetry(root, config, attempt + 1), 80);
}

function _pvLeInitEditor(root) {
    if (!root || root.dataset.pvLeBound === "1") {
        return;
    }
    const config = _pvLeParseConfig(root);
    if (!config) {
        return;
    }
    root.dataset.pvLeBound = "1";
    root._pvLeConfig = config;

    _pvLeBindFooterRetry(root, config);

    root.addEventListener("click", async (ev) => {
        const clearBtn = ev.target.closest(".bhu_pv_le_clear_btn");
        if (clearBtn && config.line_id) {
            ev.preventDefault();
            if (
                !window.confirm(
                    "Remove bank account for this khasra? You can add bank details again afterwards."
                )
            ) {
                return;
            }
            try {
                const snapshot = await rpc("/web/dataset/call_kw", {
                    model: "bhu.payment.voucher.line",
                    method: "clear_line_account",
                    args: [config.line_id],
                    kwargs: {},
                });
                const dialogEl = _pvLeCloseDialog(root);
                if (dialogEl) {
                    await _pvLeWaitDialogClosed(dialogEl);
                }
                await new Promise((resolve) => window.setTimeout(resolve, 50));
                _pvLeApplyUiSnapshot(snapshot);
            } catch (err) {
                window.alert(_pvLeRpcErrorMessage(err));
            }
            return;
        }
        const modeBtn = ev.target.closest(".bhu_pv_le_mode");
        if (modeBtn && !modeBtn.disabled) {
            ev.preventDefault();
            const mode = modeBtn.dataset.mode;
            _pvLeSetMode(root, config, mode);
            if (mode === "split") {
                const hasRows = root.querySelector(".bhu_pv_le_split_row");
                if (!hasRows && config.line_id) {
                    const rows = await rpc("/web/dataset/call_kw", {
                        model: "bhu.payment.voucher.line",
                        method: "line_editor_split_defaults",
                        args: [config.line_id],
                        kwargs: {},
                    });
                    _pvLeRenderSplitRows(root, config, rows);
                    _pvLeRecalcAmounts(root, config);
                }
            }
        }
    });

    root.addEventListener("input", (ev) => {
        if (ev.target.closest(".bhu_pv_le_pct_in")) {
            _pvLeRecalcAmounts(root, config);
        }
    });
}

function _pvLeScanEditors() {
    document.querySelectorAll(".bhu_pv_line_editor").forEach(_pvLeInitEditor);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _pvLeScanEditors);
} else {
    _pvLeScanEditors();
}

const _pvLeObserver = new MutationObserver(() => {
    _pvLeScanEditors();
});
document.addEventListener("DOMContentLoaded", () => {
    _pvLeObserver.observe(document.body, { childList: true, subtree: true });
});
