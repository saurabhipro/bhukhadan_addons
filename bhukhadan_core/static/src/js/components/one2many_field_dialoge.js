/** @odoo-module **/

// get popup on one2many field
// just just widget="in2it_one2many"

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { In2itListRenderer } from './list_renderer';

export class In2itOne2ManyField extends X2ManyField {}

In2itOne2ManyField.components = {
    ...X2ManyField.components,
    ListRenderer: In2itListRenderer,
};

export const in2itOne2ManyField = {
    ...x2ManyField,
    component: In2itOne2ManyField,
    additionalClasses: ["o_field_one2many"],
};

registry.category("fields").add("in2it_one2many", in2itOne2ManyField);



