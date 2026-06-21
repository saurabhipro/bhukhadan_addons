/** @odoo-module **/

// R&R Payment Voucher: HTML preview table — row click opens line popup (read-only if locked).

import { rpc } from "@web/core/network/rpc";

function _pvApplyLinesPreviewHtml(root, html) {
    const wrap = root.querySelector(".bhu_pv_lines_preview_wrap");
    if (!wrap || !html) {
        return;
    }
    // Inject into a static host so we do not fight Owl patching the html field widget.
    const widget = wrap.querySelector('.o_field_widget[name="lines_preview_html"]');
    if (widget) {
        widget.classList.add("d-none");
    }
    let staticHost = wrap.querySelector(".bhu_pv_lines_preview_static");
    if (!staticHost) {
        staticHost = document.createElement("div");
        staticHost.className = "bhu_pv_lines_preview_static";
        wrap.appendChild(staticHost);
    }
    staticHost.innerHTML = html;
}

function _pvApplyVoucherSnapshotDeferred(snapshot) {
    window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
            try {
                _pvApplyVoucherSnapshot(snapshot);
            } catch (_err) {
                // Avoid breaking Owl if the parent form re-rendered mid-update.
            }
        });
    });
}

function _pvUpdateFormCounter(root, fieldName, value) {
    if (value === undefined || value === null) {
        return;
    }
    const text = String(value);
    root.querySelectorAll(`.o_field_widget[name="${fieldName}"]`).forEach((widget) => {
        try {
            const input = widget.querySelector("input");
            if (input) {
                input.value = text;
            }
            const span = widget.querySelector("span");
            if (span && !input) {
                span.textContent = text;
            }
        } catch (_err) {
            // Owl may be reconciling this widget; skip silently.
        }
    });
}

function _pvApplyVoucherSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") {
        return;
    }
    const root = _pvGetVoucherRoot();
    if (!root) {
        return;
    }
    if (snapshot.lines_preview_html) {
        _pvApplyLinesPreviewHtml(root, snapshot.lines_preview_html);
    }
    _pvUpdateFormCounter(root, "line_count", snapshot.line_count);
    _pvUpdateFormCounter(root, "export_count", snapshot.export_count);
    _pvUpdateFormCounter(root, "pending_account_count", snapshot.pending_account_count);
    _pvUpdateFormCounter(root, "lines_file_generated_count", snapshot.lines_file_generated_count);
    _pvUpdateFormCounter(root, "account_ready_count", snapshot.account_ready_count);

    const genBtn = root.querySelector('button[name="action_generate_payment_files"]');
    if (genBtn) {
        const ready = (snapshot.account_ready_count || 0) > 0;
        genBtn.classList.toggle("d-none", !ready);
        genBtn.classList.toggle("o_invisible_modifier", !ready);
    }

    _pvSyncTabBadges();
    _pvInitKhasraSearch(root);
}

async function _pvClearLineAccount(lineId) {
    const snapshot = await rpc("/web/dataset/call_kw", {
        model: "bhu.payment.voucher.line",
        method: "clear_line_account",
        args: [parseInt(lineId, 10)],
        kwargs: {},
    });
    _pvApplyVoucherSnapshotDeferred(snapshot);
}

document.addEventListener("bhu-pv-ui-snapshot", (ev) => {
    _pvApplyVoucherSnapshotDeferred(ev.detail);
});

function _pvFindTriggerRow(lineId) {
    if (!lineId) {
        return null;
    }
    const idStr = String(lineId);
    const rows = document.querySelectorAll(".bhu_pv_o2many_triggers tr.o_data_row");
    for (const row of rows) {
        const rid = row.dataset.id || row.getAttribute("data-id") || "";
        if (rid === idStr) {
            return row;
        }
    }
    const htmlRow = document.querySelector(`tr.bhu_pv_line_row[data-line-id="${idStr}"], tr[data-line-id="${idStr}"]`);
    if (!htmlRow) {
        return null;
    }
    const htmlRows = Array.from(
        htmlRow.closest("tbody")?.querySelectorAll("tr[data-line-id]") || []
    );
    const idx = htmlRows.indexOf(htmlRow);
    return idx >= 0 ? rows[idx] || null : null;
}

function _pvTriggerLineButton(lineId, btnClass) {
    const row = _pvFindTriggerRow(lineId);
    const trigger = row?.querySelector(btnClass);
    if (trigger) {
        trigger.click();
        return true;
    }
    return false;
}

function _pvSelectRow(row) {
    if (!row) {
        return;
    }
    const table = row.closest("table");
    if (table) {
        table.querySelectorAll("tr[data-line-id]").forEach((r) => {
            r.classList.toggle("bhu_pv_row_selected", r === row);
        });
    }
}

function _pvGetVoucherRoot(fromEl) {
    if (fromEl && fromEl instanceof Element) {
        return fromEl.closest(".bhu_payment_voucher_premium");
    }
    return document.querySelector(".bhu_payment_voucher_premium");
}

function _pvGetKhasraTable(root) {
    if (!root) {
        return null;
    }
    const wrap = root.querySelector(".bhu_pv_lines_preview_wrap");
    if (wrap) {
        const searchRoot = wrap.querySelector(".bhu_pv_lines_preview_static") || wrap;
        const table = searchRoot.querySelector(
            "table.bhu_pv_sim_table, table.bhu_pv_pay_table, table.s23-sim-table"
        );
        if (table) {
            return table;
        }
    }
    return root.querySelector(
        '.bhu_pv_rr_panel[data-tab-panel="khasra"] table.bhu_pv_sim_table, .bhu_pv_rr_panel[data-tab-panel="khasra"] table.s23-sim-table'
    );
}

function _pvRowKhasraText(row) {
    const fromData = row.getAttribute("data-khasra");
    if (fromData) {
        return fromData;
    }
    const cell = row.querySelector(".bhu_pv_td_khasra") || row.cells?.[2];
    return cell ? cell.textContent : "";
}

function _pvNormalizeKhasraQuery(value) {
    return (value || "").trim().toLowerCase().replace(/\s+/g, "");
}

function _pvFilterKhasraRows(query, rootEl) {
    const root = _pvGetVoucherRoot(rootEl);
    if (!root) {
        return;
    }
    const table = _pvGetKhasraTable(root);
    const tbody = table?.querySelector("tbody");
    if (!tbody) {
        return;
    }
    const q = _pvNormalizeKhasraQuery(query);
    const rows = tbody.querySelectorAll("tr[data-line-id]");
    let visible = 0;
    rows.forEach((row) => {
        const khasra = _pvNormalizeKhasraQuery(_pvRowKhasraText(row));
        const show = !q || khasra.includes(q);
        row.classList.toggle("bhu_pv_row_hidden", !show);
        row.style.display = show ? "" : "none";
        if (show) {
            visible += 1;
        }
    });
    let emptyRow = tbody.querySelector("tr.bhu_pv_khasra_empty");
    if (q && visible === 0) {
        const colCount = table.querySelectorAll("thead th").length || 10;
        if (!emptyRow) {
            emptyRow = document.createElement("tr");
            emptyRow.className = "bhu_pv_khasra_empty";
            tbody.appendChild(emptyRow);
        }
        emptyRow.innerHTML = `<td colspan="${colCount}" class="text-muted text-center py-3">No khasra matching your search.</td>`;
        emptyRow.style.display = "";
        emptyRow.classList.remove("d-none");
    } else if (emptyRow) {
        emptyRow.style.display = "none";
        emptyRow.classList.add("d-none");
    }
}

function _pvActivateTab(tabName) {
    const root = _pvGetVoucherRoot();
    if (!root || !tabName) {
        return;
    }
    root.dataset.activeRrTab = tabName;
    root.querySelectorAll(".bhu_pv_rr_tab").forEach((btn) => {
        const active = btn.dataset.tab === tabName;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
    });
    root.querySelectorAll(".bhu_pv_rr_panel").forEach((panel) => {
        const show = panel.dataset.tabPanel === tabName;
        panel.classList.toggle("d-none", !show);
    });
    if (tabName === "khasra") {
        const input = root.querySelector(".bhu_pv_khasra_search");
        if (input) {
            _pvFilterKhasraRows(input.value, root);
        }
    }
}

function _pvClearPaymentHighlights(root) {
    root.querySelectorAll(".bhu_pv_pay_highlight").forEach((row) => {
        row.classList.remove("bhu_pv_pay_highlight");
    });
}

function _pvJumpToExport(exportId, voucherLineId) {
    const root = _pvGetVoucherRoot();
    if (!root || !exportId) {
        return;
    }
    _pvClearPaymentHighlights(root);
    _pvActivateTab("pending");

    const panel = root.querySelector('.bhu_pv_rr_panel[data-tab-panel="pending"]');
    if (!panel) {
        return;
    }
    let scrollTarget = null;
    panel.querySelectorAll(`tr[data-export-id="${exportId}"]`).forEach((row) => {
        row.classList.add("bhu_pv_pay_highlight");
        if (!scrollTarget) {
            scrollTarget = row;
        }
    });
    if (scrollTarget) {
        scrollTarget.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
}

function _pvSyncTabBadges() {
    const root = _pvGetVoucherRoot();
    if (!root) {
        return;
    }
    root.querySelectorAll(".bhu_pv_count_val").forEach((src) => {
        const key = src.dataset.countFor;
        if (!key) {
            return;
        }
        const val = (src.textContent || "").trim();
        const badge = root.querySelector(`.bhu_pv_tab_badge[data-count-for="${key}"]`);
        if (!badge) {
            return;
        }
        if (val && val !== "0") {
            badge.textContent = val;
            badge.style.display = "";
        } else {
            badge.textContent = "";
            badge.style.display = "none";
        }
    });
}

function _pvInitKhasraSearch(rootEl) {
    const root = _pvGetVoucherRoot(rootEl);
    if (!root) {
        return;
    }
    const input = root.querySelector(".bhu_pv_khasra_search");
    if (input) {
        _pvFilterKhasraRows(input.value, root);
    }
}

function _pvInitPaymentVoucherUi() {
    _pvSyncTabBadges();
    const root = _pvGetVoucherRoot();
    if (root && !root.dataset.activeRrTab) {
        root.dataset.activeRrTab = "khasra";
    }
    _pvInitKhasraSearch(root);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _pvInitPaymentVoucherUi);
} else {
    _pvInitPaymentVoucherUi();
}

const _pvBadgeObserver = new MutationObserver(() => {
    _pvSyncTabBadges();
    const root = _pvGetVoucherRoot();
    if (root) {
        const input = root.querySelector(".bhu_pv_khasra_search");
        if (input) {
            _pvFilterKhasraRows(input.value, root);
        }
    }
});
document.addEventListener("DOMContentLoaded", () => {
    const root = _pvGetVoucherRoot();
    if (root) {
        _pvBadgeObserver.observe(root, { childList: true, subtree: true, characterData: true });
    }
});

document.addEventListener(
    "input",
    (ev) => {
        const target = ev.target;
        if (!target || !(target instanceof Element)) {
            return;
        }
        const input = target.closest(".bhu_pv_khasra_search");
        if (!input) {
            return;
        }
        const root = input.closest(".bhu_payment_voucher_premium");
        if (!root) {
            return;
        }
        _pvFilterKhasraRows(input.value, root);
    },
    true
);

document.addEventListener(
    "click",
    (ev) => {
        const target = ev.target;
        if (!target || !(target instanceof Element)) {
            return;
        }
        if (!target.closest(".bhu_payment_voucher_premium")) {
            return;
        }

        const exportRefLink = target.closest(".bhu_pv_export_ref_link");
        if (exportRefLink) {
            ev.preventDefault();
            ev.stopPropagation();
            _pvJumpToExport(
                exportRefLink.dataset.exportId || "",
                exportRefLink.dataset.voucherLineId || ""
            );
            return;
        }

        const tabBtn = target.closest(".bhu_pv_rr_tab");
        if (tabBtn && tabBtn.dataset.tab) {
            ev.preventDefault();
            _pvActivateTab(tabBtn.dataset.tab);
            return;
        }

        const editBtn = target.closest(".bhu_pv_line_edit_btn");
        if (editBtn) {
            ev.preventDefault();
            ev.stopPropagation();
            const row = editBtn.closest("tr[data-line-id]");
            _pvSelectRow(row);
            _pvTriggerLineButton(editBtn.dataset.lineId, ".bhu_pv_line_edit_trigger");
            return;
        }

        const removeBtn = target.closest(".bhu_pv_line_remove_btn");
        if (removeBtn) {
            ev.preventDefault();
            ev.stopPropagation();
            const lineId = removeBtn.dataset.lineId;
            if (
                lineId &&
                window.confirm(
                    "Remove bank account for this khasra? Status will return to Pending account so you can add details again."
                )
            ) {
                _pvClearLineAccount(lineId).catch((err) => {
                    const msg =
                        err?.data?.message ||
                        err?.message?.data?.message ||
                        err?.message ||
                        "Could not remove account.";
                    window.alert(msg);
                });
            }
            return;
        }

        const row = target.closest("tr[data-line-id]");
        if (!row || !row.closest(".bhu_pv_lines_preview_wrap, .bhu_pv_sim_table, .s23-sim-table")) {
            return;
        }
        if (target.closest(".bhu_pv_export_ref_link")) {
            return;
        }
        if (target.closest(".bhu_pv_line_edit_btn, .bhu_pv_line_remove_btn")) {
            return;
        }
        _pvSelectRow(row);
        const lineId = row.getAttribute("data-line-id");
        if (!lineId) {
            return;
        }
        const triggerCls = row.classList.contains("bhu_pv_line_row_locked")
            ? ".bhu_pv_line_view_trigger"
            : ".bhu_pv_line_edit_trigger";
        _pvTriggerLineButton(lineId, triggerCls);
    },
    true
);
