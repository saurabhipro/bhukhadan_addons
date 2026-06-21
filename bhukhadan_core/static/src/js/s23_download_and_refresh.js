/** @odoo-module **/

import { registry } from "@web/core/registry";
import { downloadFile } from "@web/core/network/download";

registry.category("actions").add("bhuarjan_s23_download_and_refresh", async (env, action) => {
    const url = action?.params?.url;
    if (url) {
        await downloadFile(url);
    }
    return { type: "ir.actions.act_window_close" };
});

