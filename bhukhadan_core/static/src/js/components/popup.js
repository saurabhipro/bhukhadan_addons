// Get popup while save record for a specific model for eg
/* <form
                    string="Project Category"
                    js_class="confirm_save_form"
                    popup_title="Confirm Category Save"
                    popup_body="Do you want to save changes to this Project Category?"
                    confirm_label="Yes, Save"
                    cancel_label="Cancel"
                ></form> */

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

class ConfirmSaveController extends FormController {
    async saveButtonClicked(params = {}) {
        // ✅ Read dynamic attributes from the form tag
        const arch = this.props.archInfo?.arch || {};
        const title = arch.attrs?.popup_title || "Confirm Save";
        const body = arch.attrs?.popup_body || "Are you sure you want to save this record?";
        const confirmLabel = arch.attrs?.confirm_label || "Yes, Save";
        const cancelLabel = arch.attrs?.cancel_label || "Cancel";

        const dialogService = this.env.services.dialog;

        const confirmed = await new Promise((resolve) => {
            dialogService.add(ConfirmationDialog, {
                title,
                body,
                confirmLabel,
                cancelLabel,
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });

        if (confirmed) {
            if (!("onError" in params)) {
                params.onError = this.onSaveError.bind(this);
            }
            await super.saveButtonClicked(params);
        } else {
            console.log("❌ Save canceled by user");
        }
    }
}

// ✅ Extend the standard form view
export const confirmSaveFormView = {
    ...formView,
    Controller: ConfirmSaveController,
};

// ✅ Register under your name
registry.category("views").add("confirm_save_form", confirmSaveFormView);
