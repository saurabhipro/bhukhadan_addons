/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useInputField } from "@web/views/fields/input_field_hook";
const { Component, useRef, onMounted } = owl;
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * Time picker field widget that allows manual input without increment/decrement buttons
 */
export class FieldTimePicker extends Component {
    static template = 'FieldTimePicker';

    setup() {
        this.input = useRef('input_time');
        onMounted(() => {
            if (!this.input.el) {
                console.error("Input element is not available.");
            }
        });
        useInputField({
            getValue: () => {
                const val = this.props.record.data[this.props.name];
                if (val === "00:00" || val === "0:00" || val === "0:00:00" || val === "00:00:00" || val === "0.0" || val === "0") {
                    return "";
                }
                return val || "";
            },
            refName: "input_time"
        });
    }

    _onClickTimeField(ev) {
        const timePicker = this.input.el;
        if (!timePicker) {
            console.error("Input element is not available.");
            return;
        }

        if (this.props.record.fields[this.props.name].type === "char" && timePicker) {
            const currentTime = timePicker.value || "00:00:00";
            const [hour, minute, second] = currentTime.split(':').map(Number);

            // Remove any existing time picker popup if present
            const existingPopup = document.querySelector(".time-picker-container");
            if (existingPopup) {
                existingPopup.remove();
            }

            // Create popup container
            const timePickerContainer = document.createElement("div");
            timePickerContainer.className = "time-picker-container";
            Object.assign(timePickerContainer.style, {
                position: "absolute",
                display: "flex",
                flexDirection: "column", // Stack elements vertically
                alignItems: "center",
                gap: "10px",
                padding: "10px",
                backgroundColor: "white",
                border: "1px solid #ccc",
                borderRadius: "5px",
                boxShadow: "0 2px 10px rgba(0, 0, 0, 0.1)",
                zIndex: "1000",
                width: "250px"
            });
            document.body.appendChild(timePickerContainer);

            // Position popup near input field
            const rect = timePicker.getBoundingClientRect();
            Object.assign(timePickerContainer.style, {
                position: "fixed", // Change to fixed
                top: `${rect.bottom + 5}px`, // Use viewport-relative position
                left: `${rect.left}px`, // Use viewport-relative position
            });

            // Create a time box with manual input
            const createTimeBox = (value, max) => {
                const display = document.createElement("input");
                display.type = "number";
                display.min = 0;
                display.max = max;
                display.value = value < 10 ? `0${value}` : `${value}`;
                Object.assign(display.style, {
                    fontSize: "15px",
                    padding: "5px",
                    backgroundColor: "#f9f9f9",
                    border: "1px solid #ccc",
                    borderRadius: "3px",
                    minWidth: "50px",
                    textAlign: "center"
                });

                // Validate and pad input on blur
                display.addEventListener("blur", () => {
                    let val = parseInt(display.value, 10);
                    if (isNaN(val) || val < 0) val = 0;
                    else if (val > max) val = max;
                    display.value = val < 10 ? `0${val}` : `${val}`;
                });

                return display;
            };

            // Create hour, minute, second boxes
            const hourBox = createTimeBox(hour, 23);
            const minuteBox = createTimeBox(minute, 59);
            const secondBox = createTimeBox(second, 59);

            // Create a container for the input fields
            const inputContainer = document.createElement("div");
            Object.assign(inputContainer.style, {
                display: "flex",
                gap: "10px",
                justifyContent: "center",
                marginBottom: "10px" // Space between input fields and the button
            });
            timePickerContainer.appendChild(inputContainer);

            inputContainer.appendChild(hourBox);
            inputContainer.appendChild(minuteBox);
            inputContainer.appendChild(secondBox);

            // Confirm button
            const confirmButton = document.createElement("button");
            confirmButton.textContent = _t("Set Time");
            confirmButton.type = "button";
            confirmButton.className = "time-picker-confirm-button";
            Object.assign(confirmButton.style, {
                padding: "5px 15px",
                backgroundColor: "#714B67",
                color: "white",
                border: "none",
                borderRadius: "5px",
                cursor: "pointer",
                fontSize: "14px",
                textAlign: "center",
                transition: "background-color 0.3s ease",
                width: "83%"
            });

            confirmButton.addEventListener("mouseover", () => {
                confirmButton.style.backgroundColor = "#5a3b52"; // Hover effect
            });
            confirmButton.addEventListener("mouseout", () => {
                confirmButton.style.backgroundColor = "#714B67";
            });

            // Append the confirm button below the input boxes
            timePickerContainer.appendChild(confirmButton);

            confirmButton.addEventListener("click", () => {
                if (this.input?.el) {
                    const selectedTime = [
                        hourBox.value,
                        minuteBox.value,
                        secondBox.value,
                    ].join(':');
                    this.input.el.value = selectedTime;
                    this.props.record.update({
                        [this.props.name]: selectedTime
                    });
                    document.body.removeChild(timePickerContainer);
                    document.removeEventListener("mousedown", onClickOutside);
                    document.removeEventListener("keydown", onEscPress);
                } else {
                    document.body.removeChild(timePickerContainer);
                    document.removeEventListener("mousedown", onClickOutside);
                    document.removeEventListener("keydown", onEscPress);
                }
            });

            // Close the popup if clicked outside or Escape pressed
            // Use mousedown so we don't steal the click from other form fields
            const onClickOutside = (event) => {
                if (!timePickerContainer.contains(event.target) && event.target !== timePicker) {
                    // Remove listeners FIRST so we don't block the click on the other element
                    document.removeEventListener("mousedown", onClickOutside);
                    document.removeEventListener("keydown", onEscPress);
                    timePickerContainer.remove();
                }
            };
            const onEscPress = (event) => {
                if (event.key === "Escape") {
                    document.removeEventListener("mousedown", onClickOutside);
                    document.removeEventListener("keydown", onEscPress);
                    timePickerContainer.remove();
                }
            };

            // Use setTimeout to avoid immediately triggering on the same click that opened the popup
            setTimeout(() => {
                document.addEventListener("mousedown", onClickOutside);
                document.addEventListener("keydown", onEscPress);
            }, 0);

        } else {
            this.env.model.dialog.add(AlertDialog, {
                body: _t("This widget can only be added to 'Char' field"),
            });
        }
    }
}
FieldTimePicker.props = {
    ...standardFieldProps,
};

export const TimePickerField = {
    component: FieldTimePicker,
    supportedTypes: ["char"],
};

registry.category("fields").add("timepicker", TimePickerField);