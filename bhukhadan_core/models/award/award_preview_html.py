# -*- coding: utf-8 -*-

import html as html_lib

from markupsafe import Markup, escape

from odoo import models, api, _


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def _html_s23_land_preview(self):
        self.ensure_one()
        if not (self.project_id and self.village_id):
            return Markup(
                '<p class="text-muted s23_note mb-0">'
                'Select project and village to see land lines (same engine as the award / अवार्ड).'
                '</p>'
            )
        rows = self.get_land_compensation_data()
        if not rows:
            return Markup(
                '<p class="text-muted s23_note mb-0">'
                'No land rows found for this village/project. Check surveys and khasra data.'
                '</p>'
            )
        try:
            _cur = self.currency_id or self.env.company.currency_id
            cur_sym = _cur.symbol or '₹'
        except Exception:
            cur_sym = '₹'
        # Soft alternating palette for khasra groups
        _SLAB_COLORS = [
            '#e3f2fd',  # light blue
            '#f3e5f5',  # light purple
            '#e8f5e9',  # light green
            '#fff3e0',  # light amber
            '#fce4ec',  # light pink
            '#e0f7fa',  # light cyan
            '#f9fbe7',  # light lime
            '#ede7f6',  # light violet
        ]

        # Build a khasra→color mapping so every slab row of the same khasra
        # shares one color; rural (non-slab) rows get a plain white background.
        khasra_color = {}
        color_idx = 0
        for r in rows:
            if r.get('is_urban_slab'):
                k = (r.get('khasra') or '').strip()
                if k and k not in khasra_color:
                    khasra_color[k] = _SLAB_COLORS[color_idx % len(_SLAB_COLORS)]
                    color_idx += 1

        headers = [
            ('Sr. No. / क्र.', 'num'),
            ('Owner / भूमि स्वामी', 'text'),
            ('Khasra / खसरा', 'text'),
            ('Village / ग्राम', 'text'),
            ('Distance (m) / दूरी', 'num'),
            ('Road / सड़क', 'text'),
            ('Irrigation / सिंचाई', 'text'),
            ('Diverted / विचलित', 'text'),
            ('Acquired (Ha) / अधि.', 'num'),
            ('Slab / Remark', 'text'),
        ]
        parts = [
            '<div class="table-responsive s23-preview-wrap s23-land-sim-table-wrap">',
            '<table class="table table-sm s23-sim-table s23-sim-table-land">',
            '<thead><tr>',
        ]
        for col_label, col_type in headers:
            parts.append(
                f'<th class="s23-sim-th s23-sortable-th" scope="col" '
                f'data-sort-type="{escape(col_type)}" title="Click to sort">'
                f'{escape(col_label)}'
                f'<span class="s23-sort-indicator" aria-hidden="true"></span>'
                f'</th>'
            )
        parts.append('</tr></thead><tbody>')

        rows_sorted = sorted(
            rows,
            key=lambda x: (
                x.get('khasra') or '',
                x.get('landowner_name') or '',
                float(x.get('distance_from_main_road') or 0.0),
            ),
        )
        merged_by_khasra = {}
        for r in rows_sorted:
            khasra_val = (r.get("khasra") or "").strip()
            if not khasra_val:
                continue
            if khasra_val not in merged_by_khasra:
                merged_by_khasra[khasra_val] = {
                    'khasra': khasra_val,
                    'owners': [],
                    'village_name': r.get("village_name") or "",
                    'distance_from_main_road': r.get("distance_from_main_road") or 0.0,
                    'road_type_label': r.get("road_type_label") or ("MR" if r.get("is_within_distance") else "BMR"),
                    'irrigation_label': r.get("irrigation_label") or "",
                    'irrigation_type': r.get("irrigation_type") or "",
                    'is_diverted': r.get("is_diverted"),
                    'diverted_label': r.get("diverted_label") or ("Yes" if r.get("is_diverted") else "No"),
                    'acquired_area': r.get("acquired_area") or 0.0,
                    'remark': r.get("remark") or "",
                }
            bucket = merged_by_khasra[khasra_val]
            for owner in self._land_row_owner_names(r):
                if owner not in bucket['owners']:
                    bucket['owners'].append(owner)
            # same khasra rows often duplicate acquired area per owner; keep logical single-khasra value
            bucket['acquired_area'] = max(bucket['acquired_area'], r.get("acquired_area") or 0.0)
            remark = (r.get("remark") or "").strip()
            if remark and remark not in (bucket['remark'] or ""):
                bucket['remark'] = (bucket['remark'] + ", " + remark).strip(", ")

        for sr_no, row in enumerate(merged_by_khasra.values(), start=1):
            stripe_cls = 's23_row_odd' if sr_no % 2 else 's23_row_even'
            parts.append(f'<tr class="{stripe_cls}">')
            parts.append(f'<td class="text-center tabular-nums">{sr_no}</td>')
            owner_display = '<br/>'.join(
                escape(o) for o in (row['owners'] or []) if o
            )
            owner_title = html_lib.escape(', '.join(row['owners'] or []), quote=True)
            parts.append(
                f'<td class="s23-owner-cell" title="{owner_title}">'
                f'{owner_display}</td>'
            )
            parts.append(f'<td class="text-nowrap fw-semibold">{escape(row["khasra"])}</td>')
            parts.append(f'<td class="text-nowrap">{escape(row.get("village_name") or "")}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(row.get("distance_from_main_road"), 2)}</td>')
            road = row.get("road_type_label") or ("MR" if row.get("is_within_distance") else "BMR")
            road_key = road.strip().upper()
            road_style = (
                'color:#1b8f4f;font-weight:700;'
                if road_key == "MR" else
                'color:#c0392b;font-weight:700;'
            )
            parts.append(
                f'<td class="text-nowrap text-center"><span class="s23-sim-badge" style="{road_style}">{escape(road)}</span></td>'
            )
            irrigation_label = (row.get("irrigation_label") or "").strip()
            irrigation_key = (row.get("irrigation_type") or "").strip().lower()
            label_key = irrigation_label.lower()
            irrigated_yes = irrigation_key == "irrigated" or (
                "irrigated" in label_key and "unirrigated" not in label_key
            )
            irrigation_style = (
                'color:#1b8f4f;font-weight:600;'
                if irrigated_yes else
                'color:#d66a6a;font-weight:600;'
            )
            parts.append(
                f'<td class="text-nowrap small text-center" style="{irrigation_style}">{escape(irrigation_label)}</td>'
            )
            div_lbl = (row.get("diverted_label") or ("Yes" if row.get("is_diverted") else "No"))
            diverted_flag = row.get("is_diverted")
            diverted_yes = bool(diverted_flag) if diverted_flag is not None else (
                div_lbl.strip().lower() in {"yes", "y", "true", "1", "हाँ", "ha", "haan"}
            )
            diverted_style = (
                'color:#1b8f4f;font-weight:700;'
                if diverted_yes else
                'color:#c0392b;font-weight:700;'
            )
            parts.append(f'<td class="text-center text-nowrap" style="{diverted_style}">{escape(div_lbl)}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(row.get("acquired_area"), 4)}</td>')
            _remark = row.get("remark") or ""
            parts.append(
                f'<td class="s23-wrap-cell small" style="font-style:italic;" '
                f'title="{html_lib.escape(_remark, quote=True)}">{escape(_remark)}</td>'
            )
            parts.append('</tr>')

        parts.append(
            '</tbody></table>'
            '<p class="s23-sim-hint text-muted small mb-0">'
            'Each colour group = one khasra split into urban slabs / एक रंग = एक खसरा के स्लैब'
            '</p></div>'
        )
        return Markup(''.join(parts))

    def _html_s23_tree_preview(self):
        self.ensure_one()
        if not (self.project_id and self.village_id):
            return Markup(
                '<p class="text-muted s23_note mb-0">'
                'Select project and village to see tree lines.'
                '</p>'
            )
        rows = self.get_tree_compensation_data()
        if not rows:
            return Markup(
                '<p class="text-muted s23_note mb-0">'
                'No tree compensation rows (no tree lines on surveys or zero quantities).'
                '</p>'
            )
        try:
            _cur = self.currency_id or self.env.company.currency_id
            cur_sym = _cur.symbol or '₹'
        except Exception:
            cur_sym = '₹'
        headers = [
            'Khasra', 'Owner', 'Tree', 'Tree Type', 'Dev. Stage',
            'Girth (cm)', 'Qty',
            f'Unit Rate ({cur_sym})', f'Value ({cur_sym})',
            f'Solatium ({cur_sym})', f'Interest ({cur_sym})', f'Total ({cur_sym})',
        ]
        merged_by_khasra = {}

        def _fnum(val):
            try:
                return float(val or 0.0)
            except Exception:
                return 0.0

        for r in rows:
            khasra = (r.get("tree_khasra") or r.get("khasra") or "").strip()
            if not khasra:
                continue
            bucket = merged_by_khasra.setdefault(khasra, {
                'khasra': khasra,
                'owners': [],
                'tree_names': [],
                'tree_type_labels': [],
                'dev_stage_labels': [],
                'girth_labels': [],
                'unit_rates': [],
                'qty': 0.0,
                'value': 0.0,
                'solatium': 0.0,
                'interest': 0.0,
                'total': 0.0,
            })

            for owner in self._land_row_owner_names(r):
                if owner not in bucket['owners']:
                    bucket['owners'].append(owner)

            tree_name = str(r.get("tree_type") or "").strip()
            if tree_name and tree_name not in bucket['tree_names']:
                bucket['tree_names'].append(tree_name)

            tc = r.get("tree_type_code") or ""
            tc_label = "Fruit Bearing" if tc == "fruit_bearing" else ("Timber" if tc == "timber" else tc.replace("_", " ").title())
            if tc_label and tc_label not in bucket['tree_type_labels']:
                bucket['tree_type_labels'].append(tc_label)

            _ds_map = {'undeveloped': 'Undeveloped', 'semi_developed': 'Semi-Developed', 'fully_developed': 'Fully Developed'}
            ds_label = _ds_map.get(r.get('development_stage') or '', r.get('development_stage') or '—')
            if ds_label and ds_label not in bucket['dev_stage_labels']:
                bucket['dev_stage_labels'].append(ds_label)

            girth_val = _fnum(r.get("girth_cm"))
            girth_lbl = self._html_s23_num(girth_val, 1)
            if girth_lbl and girth_lbl not in bucket['girth_labels']:
                bucket['girth_labels'].append(girth_lbl)

            unit_rate = _fnum(r.get("unit_rate") or r.get("rate") or 0.0)
            if unit_rate > 0 and unit_rate not in bucket['unit_rates']:
                bucket['unit_rates'].append(unit_rate)

            bucket['qty'] += _fnum(r.get("tree_count"))
            bucket['value'] += _fnum(r.get("value"))
            bucket['solatium'] += _fnum(r.get("solatium"))
            bucket['interest'] += _fnum(r.get("interest"))
            bucket['total'] += _fnum(r.get("total"))

        parts = [
            '<div class="table-responsive s23-preview-wrap s23-land-sim-table-wrap">',
            '<table class="table table-sm s23-sim-table s23-sim-table-land">',
            '<thead><tr>',
        ]
        for col in headers:
            parts.append(f'<th class="s23-sim-th" scope="col">{escape(col)}</th>')
        parts.append('</tr></thead><tbody>')
        for idx, (khasra, r) in enumerate(merged_by_khasra.items(), start=1):
            stripe_cls = 's23_row_odd' if idx % 2 else 's23_row_even'
            parts.append(f'<tr class="{stripe_cls}">')
            parts.append(f'<td class="text-nowrap fw-semibold">{escape(khasra)}</td>')
            owner_display = '<br/>'.join(
                escape(o) for o in (r.get("owners") or []) if o
            )
            owners_joined = ', '.join(r.get("owners") or [])
            parts.append(
                f'<td class="s23-owner-cell" title="{html_lib.escape(owners_joined, quote=True)}">'
                f'{owner_display}</td>'
            )
            tree_joined = ", ".join(r.get("tree_names") or [])
            parts.append(
                f'<td class="s23-wrap-cell" title="{html_lib.escape(tree_joined, quote=True)}">'
                f'{escape(tree_joined)}</td>'
            )
            ttl_joined = ", ".join(r.get("tree_type_labels") or [])
            parts.append(
                f'<td class="s23-wrap-cell small" title="{html_lib.escape(ttl_joined, quote=True)}">'
                f'{escape(ttl_joined)}</td>'
            )
            dev_joined = ", ".join(r.get("dev_stage_labels") or [])
            parts.append(
                f'<td class="s23-wrap-cell small" title="{html_lib.escape(dev_joined, quote=True)}">'
                f'{escape(dev_joined)}</td>'
            )
            parts.append(f'<td class="text-end tabular-nums">{escape(", ".join(r.get("girth_labels") or []))}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(r.get("qty"), 0)}</td>')
            unit_rates = r.get("unit_rates") or []
            if len(unit_rates) == 1:
                unit_rate_display = self._html_s23_num(unit_rates[0], 0)
            elif len(unit_rates) > 1:
                unit_rate_display = "Mixed"
            else:
                unit_rate_display = self._html_s23_num(0, 0)
            parts.append(f'<td class="text-end tabular-nums">{escape(unit_rate_display)}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(r.get("value"), 0)}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(r.get("solatium"), 0)}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(r.get("interest"), 0)}</td>')
            parts.append(f'<td class="text-end tabular-nums fw-bold">{self._html_s23_num(r.get("total"), 0)}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table></div>')
        return Markup(''.join(parts))

    def _html_s23_asset_preview(self):
        self.ensure_one()
        rows = self.award_structure_line_ids
        term = (self.asset_khasra_filter or '').strip().lower()
        if term:
            rows = rows.filtered(lambda l, t=term: t in (l.khasra_number or '').lower())
        if not rows:
            msg = (
                'No asset lines found for this award.'
                if not term else
                f'No asset lines matched khasra "{escape(self.asset_khasra_filter)}".'
            )
            return Markup(
                f'<p class="text-muted s23_note mb-0">{msg}</p>'
            )

        try:
            _cur = self.currency_id or self.env.company.currency_id
            cur_sym = _cur.symbol or '₹'
        except Exception:
            cur_sym = '₹'

        headers = [
            'Khasra',
            'Structure Type',
            'Construction Type',
            'Description',
            'Count',
            'Area (Sq. Meter)',
            f'Rate ({cur_sym})',
            f'Asset Value ({cur_sym})',
        ]
        parts = [
            '<div class="table-responsive s23-preview-wrap s23-land-sim-table-wrap">',
            '<table class="table table-sm s23-sim-table s23-sim-table-land">',
            '<thead><tr>',
        ]
        for col in headers:
            parts.append(f'<th class="s23-sim-th" scope="col">{escape(col)}</th>')
        parts.append('</tr></thead><tbody>')

        for idx, line in enumerate(rows.sorted(key=lambda r: ((r.khasra_number or ''), (r.id or 0))), start=1):
            stripe_cls = 's23_row_odd' if idx % 2 else 's23_row_even'
            s_type = dict(line._fields['structure_type'].selection).get(line.structure_type, line.structure_type or '')
            c_type = dict(line._fields['construction_type'].selection).get(line.construction_type, line.construction_type or '')
            parts.append(f'<tr class="{stripe_cls}">')
            parts.append(f'<td class="text-nowrap fw-semibold">{escape(line.khasra_number or "")}</td>')
            parts.append(f'<td class="text-nowrap">{escape(s_type or "")}</td>')
            parts.append(f'<td class="text-nowrap">{escape(c_type or "")}</td>')
            _desc = line.description or ""
            parts.append(
                f'<td class="s23-wrap-cell" title="{html_lib.escape(_desc, quote=True)}">'
                f'{escape(_desc)}</td>'
            )
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(line.asset_count, 0)}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(line.area_sqm, 2)}</td>')
            parts.append(f'<td class="text-end tabular-nums">{self._html_s23_num(line.market_rate_per_sqm, 0)}</td>')
            parts.append(f'<td class="text-end tabular-nums fw-bold">{self._html_s23_num(line.asset_value, 0)}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table></div>')
        return Markup(''.join(parts))
