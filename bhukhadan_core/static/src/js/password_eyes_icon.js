/** @odoo-module **/

import { Component, useState, useRef, onWillUpdateProps } from "@odoo/owl";

export class PasswordEyesIcon extends Component {
  static template = "password_eyes_icon.PasswordEyesIcon";
  static props = {
    id: { type: String, optional: true },
    value: { type: String, optional: true },
    readonly: { type: Boolean, optional: true },
    update: { type: Function },
    placeholder: { type: String, optional: true },
  };

  setup() {
    this.state = useState({
      isPasswordVisible: false,
      localValue: this.props.value || "",
    });
    this.inputRef = useRef("passwordInput");

    onWillUpdateProps((nextProps) => {
      if (nextProps.value !== this.state.localValue) {
        this.state.localValue = nextProps.value || "";
      }
    });
  }

  togglePasswordVisibility() {
    this.state.isPasswordVisible = !this.state.isPasswordVisible;
  }

  onChange(ev) {
    this.state.localValue = ev.target.value;
    this.props.update(this.state.localValue);
  }

  get inputType() {
    return this.state.isPasswordVisible ? "text" : "password";
  }

  get eyeIconClass() {
    return this.state.isPasswordVisible ? "fa fa-eye-slash" : "fa fa-eye";
  }
}
