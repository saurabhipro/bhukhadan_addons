/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { onMounted, onWillUnmount } from "@odoo/owl";

const DOC_VAULT_MODEL = "bhu.document.vault.navigator";

async function docvaultEnsureSaved(root) {
    if (!root.isDirty) {
        return;
    }
    try {
        await root.save({ reload: false });
    } catch {
        root.discard();
    }
}

function parseStepNo(row) {
    const stepCell = row.querySelector('td[name="step_no"]');
    if (stepCell) {
        const n = parseInt((stepCell.textContent || "").trim(), 10);
        if (!Number.isNaN(n) && n > 0) {
            return n;
        }
    }
    const stepLabelCell = row.querySelector('td[name="step_label"], .o_docvault_step_col');
    const match = (stepLabelCell?.textContent || "").match(/Step\s*(\d+)/i);
    return match ? parseInt(match[1], 10) : 0;
}

function docvaultReloadPdfIframe(revision) {
    const iframe = document.querySelector(
        ".o_docvault_navigator_form .o_docvault_pdf_viewer iframe"
    );
    if (!iframe || !iframe.src) {
        return;
    }
    try {
        const url = new URL(iframe.src, window.location.origin);
        url.searchParams.set("_docvault_rev", String(revision || Date.now()));
        const nextSrc = url.pathname + url.search + (url.hash || "");
        if (iframe.src !== nextSrc) {
            iframe.src = nextSrc;
        }
    } catch {
        iframe.src = iframe.src.split("&_docvault_rev=")[0] + "&_docvault_rev=" + Date.now();
    }
}

export class DocVaultNavigatorFormController extends FormController {
    static template = "web.FormView";

    setup() {
        super.setup();
        this.actionService = useService("action");
        this._docvaultClick = this.onDocvaultClick.bind(this);
        onMounted(() => {
            document.addEventListener("click", this._docvaultClick, true);
        });
        onWillUnmount(() => {
            document.removeEventListener("click", this._docvaultClick, true);
        });
    }

    get displaySaveButton() {
        return false;
    }

    async beforeExecuteActionButton(clickParams) {
        await docvaultEnsureSaved(this.model.root);
        return super.beforeExecuteActionButton(clickParams);
    }

    async beforeLeave() {
        this.model.root.discard();
        return true;
    }

    async _docvaultAfterSelection() {
        await this.model.root.load();
        docvaultReloadPdfIframe(this.model.root.data.selected_preview_revision);
    }

    async _docvaultSelectVariant(resId, stepNo, label) {
        const result = await this.orm.call(
            DOC_VAULT_MODEL,
            "action_select_variant_label",
            [[resId], stepNo, label]
        );
        if (result !== true) {
            await this.actionService.doAction(result);
        }
        await this._docvaultAfterSelection();
    }

    async _docvaultSelectStep(resId, stepNo) {
        const result = await this.orm.call(
            DOC_VAULT_MODEL,
            "action_select_step_by_step_no",
            [[resId], stepNo]
        );
        if (result !== true) {
            await this.actionService.doAction(result);
        }
        await this._docvaultAfterSelection();
    }

    async onDocvaultClick(ev) {
        if (this.props.resModel !== DOC_VAULT_MODEL) {
            return;
        }
        const target = ev.target;
        if (!(target instanceof Element)) {
            return;
        }

        const chip = target.closest(".o_docvault_variant_chip");
        if (chip && !chip.disabled) {
            ev.preventDefault();
            ev.stopPropagation();
            const resId = this.model.root.resId;
            if (!resId) {
                return;
            }
            const stepNo = parseInt(chip.dataset.stepNo || "", 10) ||
                this.model.root.data.focused_step_no;
            const label = (chip.dataset.variantLabel || chip.textContent || "").trim();
            if (stepNo && label) {
                await this._docvaultSelectVariant(resId, stepNo, label);
            }
            return;
        }

        const variantRow = target.closest(
            ".o_docvault_variant_chips .o_data_row, .o_docvault_variant_chips_wrap .o_data_row"
        );
        if (variantRow) {
            ev.preventDefault();
            ev.stopPropagation();
            if (variantRow.classList.contains("text-muted")) {
                return;
            }
            const resId = this.model.root.resId;
            if (!resId) {
                return;
            }
            const stepNo = parseInt(variantRow.dataset.stepNo || "", 10) ||
                this.model.root.data.focused_step_no;
            const chipEl = variantRow.querySelector(".o_docvault_variant_chip");
            const label = (
                chipEl?.dataset.variantLabel ||
                chipEl?.textContent ||
                variantRow.querySelector('td[name="variant_label"]')?.textContent ||
                ""
            ).trim();
            if (stepNo && label) {
                await this._docvaultSelectVariant(resId, stepNo, label);
            }
            return;
        }

        const row = target.closest(
            ".o_docvault_left_panel .o_list_renderer .o_data_row, .o_docvault_left_panel .o_list_view .o_data_row"
        );
        if (!row || row.classList.contains("o_docvault_step_card--dup")) {
            return;
        }
        if (target.closest("button, a, input, select, textarea, label")) {
            return;
        }

        const stepNo = parseStepNo(row);
        if (!stepNo) {
            return;
        }

        ev.preventDefault();
        ev.stopPropagation();
        const resId = this.model.root.resId;
        if (!resId) {
            return;
        }
        await this._docvaultSelectStep(resId, stepNo);
    }
}

patch(FormController.prototype, {
    get displaySaveButton() {
        if (this.props.resModel === DOC_VAULT_MODEL) {
            return false;
        }
        return super.displaySaveButton;
    },

    async beforeExecuteActionButton(clickParams) {
        if (this.props.resModel === DOC_VAULT_MODEL) {
            await docvaultEnsureSaved(this.model.root);
        }
        return super.beforeExecuteActionButton(clickParams);
    },

    async beforeLeave() {
        if (this.props.resModel === DOC_VAULT_MODEL) {
            this.model.root.discard();
            return true;
        }
        return super.beforeLeave();
    },
});

export const docVaultNavigatorFormView = {
    ...formView,
    Controller: DocVaultNavigatorFormController,
};

registry.category("views").add("docvault_navigator_form", docVaultNavigatorFormView);
