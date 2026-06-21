/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";
import { PasswordEyesIcon } from "./password_eyes_icon";

export class PasswordEyesIconField extends CharField {
  static template = "password_eyes_icon.PasswordEyesIconField";
  static components = { PasswordEyesIcon };

  static props = {
    ...CharField.props,
    value: { type: String, optional: true },
    update: { type: Function, optional: true },
    placeholder: { type: String, optional: true },
    string: { type: String, optional: true },
  };

  get passwordIconProps() {
    return {
      id: this.props.id,
      value: this.props.value || "",
      readonly: this.props.readonly,
      update: (value) => this.props.update(value),
      placeholder: this.props.placeholder || "",
    };
  }
}

export const passwordEyesIconField = {
  component: PasswordEyesIconField,
  supportedTypes: ["char"],
  extractProps: (fieldInfo) => {
    const { attrs, field, record } = fieldInfo;
    const value = record && record.data ? record.data[field.name] || "" : "";
    const updateFunc = record ? record.update.bind(record) : () => {};

    return {
      id: attrs.id,
      readonly: fieldInfo.readonly ?? attrs.readonly ?? false,
      placeholder: attrs.placeholder,
      value: value,
      record: record,
      name: field.name,
      update: updateFunc,
      string: field.string,
    };
  },
};

registry.category("fields").add("password_eyes_icon", passwordEyesIconField);
