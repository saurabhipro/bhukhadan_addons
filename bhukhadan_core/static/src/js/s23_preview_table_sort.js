/** @odoo-module **/

function parseNumeric(value) {
    if (value === null || value === undefined) return Number.NEGATIVE_INFINITY;
    const cleaned = String(value).replace(/,/g, "").trim();
    const num = parseFloat(cleaned);
    return Number.isFinite(num) ? num : Number.NEGATIVE_INFINITY;
}

function compareValues(a, b, type, direction) {
    let result = 0;
    if (type === "num") {
        result = parseNumeric(a) - parseNumeric(b);
    } else {
        result = String(a || "").localeCompare(String(b || ""), undefined, {
            numeric: true,
            sensitivity: "base",
        });
    }
    return direction === "asc" ? result : -result;
}

document.addEventListener(
    "click",
    (ev) => {
        const th = ev.target.closest(".s23-sim-table .s23-sortable-th");
        if (!th) return;

        const table = th.closest("table.s23-sim-table");
        if (!table) return;
        const tbody = table.querySelector("tbody");
        if (!tbody) return;

        const headerRow = th.parentElement;
        const headers = Array.from(headerRow.querySelectorAll(".s23-sortable-th"));
        const colIndex = headers.indexOf(th);
        if (colIndex < 0) return;

        const currentDirection = th.dataset.sortDir === "asc" ? "asc" : "desc";
        const nextDirection = currentDirection === "asc" ? "desc" : "asc";
        const sortType = th.dataset.sortType === "num" ? "num" : "text";

        headers.forEach((el) => {
            el.dataset.sortDir = "";
            el.classList.remove("s23-sort-asc", "s23-sort-desc");
        });
        th.dataset.sortDir = nextDirection;
        th.classList.add(nextDirection === "asc" ? "s23-sort-asc" : "s23-sort-desc");

        const rows = Array.from(tbody.querySelectorAll("tr"));
        rows.sort((rowA, rowB) => {
            const cellA = rowA.children[colIndex];
            const cellB = rowB.children[colIndex];
            const valA = cellA ? cellA.textContent : "";
            const valB = cellB ? cellB.textContent : "";
            return compareValues(valA, valB, sortType, nextDirection);
        });

        rows.forEach((row) => tbody.appendChild(row));
    },
    true
);

