/** @odoo-module **/

/**
 * Doc Vault Navigator UI polish:
 * - Section icons + card styling on step rows
 * - Hide duplicate step rows (safety net)
 * - Step/variant clicks are handled by docvault_navigator_form.js (step_no RPC)
 */

const THEME_CLASS_PREFIX = "theme-";

const THEME_BY_LABEL = [
    ["sia team", "theme-sia"],
    ["section 4", "theme-sec4"],
    ["expert group", "theme-expert"],
    ["section 8", "theme-sec8"],
    ["section 11", "theme-sec11"],
    ["section 15", "theme-sec15"],
    ["section 18", "theme-sec18"],
    ["section 19", "theme-sec19"],
    ["section 21", "theme-sec21"],
    ["section 23", "theme-award"],
    ["award", "theme-award"],
    ["payment file", "theme-payment"],
    ["form 10", "theme-survey"],
    ["surveys", "theme-survey"],
];

function themeForLabel(label) {
    const text = (label || "").trim().toLowerCase();
    for (const [needle, theme] of THEME_BY_LABEL) {
        if (text.includes(needle)) {
            return theme;
        }
    }
    return "theme-default";
}

function decorateDocvaultPanel(panel) {
    if (!panel) return;

    const seenSteps = new Set();
    const rows = panel.querySelectorAll(".o_list_renderer .o_data_row, .o_list_view .o_data_row");

    rows.forEach((row) => {
        if (row.dataset.docvaultDecorated === "1") {
            return;
        }

        const iconCell = row.querySelector('td[name="section_icon"], .o_docvault_icon_col');
        const stepCell = row.querySelector('td[name="step_label"], .o_docvault_step_col');
        const sectionCell = row.querySelector('td[name="section_label"], .o_docvault_section_col');
        const themeCell = row.querySelector('td[name="section_theme"]');

        if (!sectionCell) {
            return;
        }

        row.classList.add("o_docvault_step_card");

        // Theme class for icon gradient
        let theme = "";
        if (themeCell) {
            theme = (themeCell.textContent || "").trim();
        }
        if (!theme) {
            theme = themeForLabel(sectionCell.textContent || "");
        }
        if (theme) {
            row.classList.add(theme.startsWith(THEME_CLASS_PREFIX) ? theme : `${THEME_CLASS_PREFIX}${theme}`);
        }

        // Build icon from section_icon cell text (fa-* class from server)
        if (iconCell && !iconCell.querySelector(".o_docvault_section_icon")) {
            const iconClass = (iconCell.textContent || "fa-file-pdf-o").trim().replace(/^fa\s+/, "fa-");
            iconCell.textContent = "";
            const iconWrap = document.createElement("span");
            iconWrap.className = `o_docvault_section_icon fa ${iconClass.startsWith("fa-") ? iconClass : `fa-${iconClass}`}`;
            iconWrap.setAttribute("aria-hidden", "true");
            iconCell.appendChild(iconWrap);
        }

        // Active / missing states from Odoo decorations
        if (row.classList.contains("text-success")) {
            row.classList.add("o_docvault_step_card--active");
        }
        if (row.classList.contains("text-muted")) {
            row.classList.add("o_docvault_step_card--missing");
        }

        // Dedupe by step label text
        const stepKey = (stepCell && stepCell.textContent || "").trim();
        if (stepKey) {
            if (seenSteps.has(stepKey)) {
                row.classList.add("o_docvault_step_card--dup");
            } else {
                seenSteps.add(stepKey);
            }
        }

        const countCell = row.querySelector('td[name="doc_count_label"], .o_docvault_count_col');
        if (countCell && !countCell.querySelector(".o_docvault_doc_badge")) {
            const text = (countCell.textContent || "").trim();
            if (text) {
                countCell.textContent = "";
                const badge = document.createElement("span");
                badge.className = "o_docvault_doc_badge";
                badge.textContent = text;
                countCell.appendChild(badge);
            }
        }

        row.dataset.docvaultDecorated = "1";
    });
}

function decorateVariantChips(scope) {
    const root = scope || document;
    root.querySelectorAll(".o_docvault_variant_chips .o_data_row").forEach((row) => {
        if (row.dataset.docvaultChipDecorated === "1") {
            return;
        }
        row.classList.add("o_docvault_variant_chip_row");

        const labelCell = row.querySelector('td[name="variant_label"]');
        if (!labelCell) {
            return;
        }

        const label = (labelCell.textContent || "").trim();
        const isMissing = row.classList.contains("text-muted");
        const isActive = row.classList.contains("text-success");
        const stepNoCell = row.querySelector('td[name="step_no"]');
        const stepNo = stepNoCell ? (stepNoCell.textContent || "").trim() : "";

        labelCell.textContent = "";
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "o_docvault_variant_chip";
        if (stepNo) {
            chip.dataset.stepNo = String(stepNo).trim();
        }
        chip.dataset.variantLabel = label;
        if (isActive) {
            chip.classList.add("o_docvault_variant_chip--active");
        }
        if (isMissing) {
            chip.classList.add("o_docvault_variant_chip--missing");
            chip.disabled = true;
        }
        chip.textContent = label;
        labelCell.appendChild(chip);
        if (stepNo) {
            row.dataset.stepNo = String(stepNo).trim();
        }

        row.dataset.docvaultChipDecorated = "1";
    });
}

function refreshDocvaultUi(root) {
    const scope = root || document;
    scope.querySelectorAll(".o_docvault_left_panel").forEach(decorateDocvaultPanel);
    decorateVariantChips(scope);
}

let observer;
function startDocvaultObserver() {
    if (observer) return;

    observer = new MutationObserver(() => {
        refreshDocvaultUi(document);
    });

    const boot = () => {
        const form = document.querySelector(".o_docvault_navigator_form");
        if (form) {
            observer.observe(form, { childList: true, subtree: true });
            refreshDocvaultUi(form);
        }
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

    // Odoo SPA navigation: re-decorate when form appears
    setInterval(() => {
        if (document.querySelector(".o_docvault_navigator_form")) {
            refreshDocvaultUi(document);
        }
    }, 1200);
}

startDocvaultObserver();
