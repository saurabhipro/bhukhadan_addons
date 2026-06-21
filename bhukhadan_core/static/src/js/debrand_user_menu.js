/** @odoo-module **/

import { registry } from "@web/core/registry";

// Remove unwanted user menu items
registry.category("user_menuitems").remove('odoo_account');
registry.category("user_menuitems").remove('documentation');
registry.category("user_menuitems").remove('support');
registry.category("user_menuitems").remove('install_pwa');
registry.category("user_menuitems").remove('shortcuts');
registry.category("user_menuitems").remove("web_tour.tour_enabled");
