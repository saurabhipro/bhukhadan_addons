/** @odoo-module **/


import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ListRenderer } from "@web/views/list/list_renderer";
import { nextTick } from "@odoo/owl";

export class In2itListRenderer extends ListRenderer {
    setup() {        
        super.setup();
        this.dialog = useService("dialog");
        
    }

    async onDeleteRecord(record) {
        console.log("delete a domain function  - ")
        
        this.dialog.add(ConfirmationDialog, {
            body: _t("Are you sure you want to delete this record?"),
            confirm: () => this.activeActions.onDelete(record),
            cancel: () => {},
        });
    }

    async add(params) {
        return new Promise((resolve, reject) => {
            this.dialog.add(ConfirmationDialog, {
                body: _t("Are you sure you want to add a new line?"),
                confirm: () => resolve(),
                cancel: () => reject(),
            });
        })
        .then(() => {
            return super.add(params);
        })
        .catch(() => {
            console.log("User cancelled add.");
        });
    }

}

// import { patch } from "@web/core/utils/patch";
// import { FormController } from "@web/views/form/form_controller";

// console.log("\n\n kjhgcxcghj----------");


// patch(FormController.prototype, {
    
//     name: "in2it_skills_save_popup",  
//     record: {
//         async saveButtonClicked(ev) {
//             console.log("jhgfdsadfghjk");
//             ev.preventDefault();

//             const dialogService = useService("dialog");

//             const confirmed = await new Promise((resolve) => {
//                 dialogService.add(ConfirmationDialog, {
//                     title: "Confirm Save",
//                     body: "Are you sure you want to save this record?",
//                     confirmLabel: "Yes, Save",
//                     cancelLabel: "Cancel",
//                     confirm: () => resolve(true),
//                     cancel: () => resolve(false),
//                 });
//             });

//             if (confirmed) {
//                 await this._super(ev); // proceed to save
//             } else {
//                 return; // do nothing if cancelled
//             }
//         },
//     },
// });
