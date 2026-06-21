/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const PALETTES = {
    /** Sub divisions — blues / teal family */
    subdiv: ["text-bg-primary", "text-bg-info", "text-bg-secondary"],
    /** Tehsils — warm accents */
    tehsil: ["text-bg-warning text-dark", "text-bg-danger", "text-bg-dark"],
    /** Villages — greens / aqua */
    villages: ["text-bg-success", "text-bg-teal-soft", "text-bg-info"],
};

export class BhuCommaPillsChar extends Component {
    static template = "bhukhadan_core.CommaPillsChar";
    static props = {
        ...standardFieldProps,
        paletteClasses: { type: Array, element: String },
    };

    /** @returns {string[]} trimmed segments from comma-separated summary */
    get parts() {
        const raw = this.props.record.data[this.props.name] || "";
        if (!raw || typeof raw !== "string") {
            return [];
        }
        return raw
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
    }

    pillClass(index) {
        const classes = this.props.paletteClasses;
        return classes[index % classes.length];
    }
}

function commaPillsFieldDef(paletteKey) {
    return {
        component: BhuCommaPillsChar,
        supportedTypes: ["char"],
        extractProps(fieldInfo, dynamicInfo) {
            const classes = PALETTES[paletteKey] || PALETTES.subdiv;
            return {
                paletteClasses: classes,
                readonly: dynamicInfo.readonly,
            };
        },
        isEmpty(record, fieldName) {
            const raw = record.data[fieldName];
            return !(raw && String(raw).trim());
        },
    };
}

registry.category("fields").add("bhu_comma_pills_subdiv", commaPillsFieldDef("subdiv"));
registry.category("fields").add("bhu_comma_pills_tehsil", commaPillsFieldDef("tehsil"));
registry.category("fields").add("bhu_comma_pills_villages", commaPillsFieldDef("villages"));
