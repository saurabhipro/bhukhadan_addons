# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError


class Section23AwardConsolidated(models.Model):
    _inherit = 'bhu.section23.award'

    def get_consolidated_report_project_name(self):
        """Project name for consolidated PDF/Excel; sudo browse for ACL-safe display."""
        self.ensure_one()
        pid = self.project_id.id
        if not pid:
            return ''
        project = self.env['bhu.project'].sudo().browse(pid)
        return (project.name or '').strip()

    def action_download_consolidated_pdf(self):
        """Download consolidated award sheet as PDF (one row per khasra) using QWeb template."""
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        consolidated_data = self.get_consolidated_award_data()
        if not consolidated_data:
            raise ValidationError(_('No consolidated data available for this award.'))

        # Use standard report_action so Odoo passes docs/o context correctly.
        report_action = self.env.ref('bhukhadan_core.action_report_consolidated_award_sheet')
        return report_action.sudo().report_action(self)

    def action_download_consolidated_excel(self):
        """Download consolidated award sheet as Excel (one row per khasra)."""
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        import io
        import base64
        try:
            import xlsxwriter
        except ImportError:
            raise ValidationError(_("Python library 'xlsxwriter' is not installed."))

        consolidated_data = self.get_consolidated_award_data()
        if not consolidated_data:
            raise ValidationError(_('No consolidated data available for this award.'))

        award_headers = self.get_award_header_constants()
        consolidated_headers = award_headers['excel']['consolidated_award_headers']

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Consolidated Award')

        # ── Formats ────────────────────────────────────────────────────────
        FONT = 'Noto Sans Devanagari'
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 13, 'font_name': FONT,
            'align': 'center', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#FFFFFF',
        })
        subtitle_fmt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'align': 'center', 'valign': 'vcenter', 'border': 1,
            'text_wrap': True,
        })
        header_fmt = workbook.add_format({
            'bold': True, 'font_size': 9, 'font_name': FONT,
            'bg_color': '#D3D3D3', 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'text_wrap': True,
        })
        cell_fmt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'valign': 'top', 'align': 'left',
        })
        cell_fmt_alt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'valign': 'top', 'align': 'left',
            'bg_color': '#F8F8F8',
        })
        name_fmt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'valign': 'top', 'align': 'left', 'text_wrap': True,
        })
        name_fmt_alt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'valign': 'top', 'align': 'left', 'text_wrap': True,
            'bg_color': '#F8F8F8',
        })
        num_fmt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.00',
        })
        num_fmt_alt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.00',
            'bg_color': '#F8F8F8',
        })
        area_fmt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'num_format': '0.0000',
        })
        area_fmt_alt = workbook.add_format({
            'font_size': 10, 'font_name': FONT,
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'num_format': '0.0000',
            'bg_color': '#F8F8F8',
        })
        total_label_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': FONT,
            'bg_color': '#D3D3D3', 'border': 1,
            'align': 'center', 'valign': 'vcenter',
        })
        total_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': FONT,
            'bg_color': '#D3D3D3', 'border': 1,
            'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.00',
        })
        total_area_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': FONT,
            'bg_color': '#D3D3D3', 'border': 1,
            'align': 'right', 'valign': 'vcenter',
            'num_format': '0.0000',
        })
        subtotal_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': FONT,
            'border': 1, 'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.00',
        })
        subtotal_num_fmt_alt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': FONT,
            'bg_color': '#F8F8F8', 'border': 1,
            'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.00',
        })

        # ── Title ──────────────────────────────────────────────────────────
        sheet.set_row(0, 24)
        sheet.merge_range(0, 0, 0, 8,
            'भूमि, परिसंपत्तियों तथा वृक्षों के मुआवजा का गोशवारा भाग -1 (घ)',
            title_fmt)

        # ── Subtitle ───────────────────────────────────────────────────────
        village_name = self.village_id.name or '-'
        tehsil_name = self.village_id.tehsil_id.name if self.village_id and self.village_id.tehsil_id else '-'
        district_name = self.village_id.district_id.name if self.village_id and self.village_id.district_id else '-'
        state_name = (self.village_id.district_id.state_id.name
                      if self.village_id and self.village_id.district_id and self.village_id.district_id.state_id
                      else '')
        district_full = f"{district_name} ({state_name})" if state_name else district_name
        date_str = self.award_date.strftime('%d-%m-%Y') if self.award_date else ''
        project_name = self.get_consolidated_report_project_name()
        urban_body_label = self.get_urban_body_label()
        urban_part = f" ({urban_body_label})" if urban_body_label else ''
        subtitle = (
            f"भू-अर्जन प्रकरण क्रमांक {self.case_number or ''} / "
            f"ग्राम-{village_name}{urban_part}  "
            f"Project: {project_name}  "
            f"तहसील-{tehsil_name}  जिला-{district_full}  दिनांक: {date_str}"
        )
        sheet.set_row(1, 36)
        sheet.merge_range(1, 0, 1, 8, subtitle, subtitle_fmt)

        # ── Two-row column headers ─────────────────────────────────────────
        header_row = 3
        sheet.set_row(header_row, 36)
        sheet.set_row(header_row + 1, 30)
        sheet.merge_range(header_row, 0, header_row + 1, 0, consolidated_headers[0], header_fmt)
        sheet.merge_range(header_row, 1, header_row + 1, 1, consolidated_headers[1], header_fmt)
        sheet.merge_range(header_row, 2, header_row, 3, 'अर्जित भूमि का विवरण', header_fmt)
        sheet.write(header_row + 1, 2, 'खसरा नं.', header_fmt)
        sheet.write(header_row + 1, 3, 'रकबा (हे.)', header_fmt)
        for col in range(4, 9):
            sheet.merge_range(header_row, col, header_row + 1, col, consolidated_headers[col], header_fmt)

        # ── Data rows ─────────────────────────────────────────────────────
        row = 5
        t_ha = t_land = t_asset = t_tree = t_det = 0.0
        for idx, group in enumerate(consolidated_data):
            is_alt = idx % 2 == 1
            cur_cell = cell_fmt_alt if is_alt else cell_fmt
            cur_name = name_fmt_alt if is_alt else name_fmt
            cur_area = area_fmt_alt if is_alt else area_fmt
            cur_num = num_fmt_alt if is_alt else num_fmt

            khasra_lines = group.get('khasra_lines') or []
            num_lines = len(khasra_lines)
            start_row = row

            # Write one Excel row per khasra line
            for k_idx, kline in enumerate(khasra_lines):
                row_height = 20
                sheet.set_row(row, row_height)

                sheet.write(row, 2, kline.get('khasra', ''), cur_cell)
                ha = float(kline.get('acquired_area_ha') or 0.0)
                land_c = float(kline.get('land_compensation') or 0.0)
                asset_c = float(kline.get('asset_compensation') or 0.0)
                tree_c = float(kline.get('tree_compensation') or 0.0)
                sheet.write_number(row, 3, ha, cur_area)
                sheet.write_number(row, 4, land_c, cur_num)
                sheet.write_number(row, 5, asset_c, cur_num)
                sheet.write_number(row, 6, tree_c, cur_num)
                t_ha += ha; t_land += land_c; t_asset += asset_c
                t_tree += tree_c
                row += 1

            end_row = row - 1
            num_owners = len(group.get('owners') or [])
            owner_height = max(20, num_owners * 42)
            total_det = float(group.get('total_determined') or 0.0)
            t_det += total_det

            if num_lines > 1:
                sheet.set_row(start_row, owner_height)
                # Merge serial, owner name, determined total, and remark across all khasra rows
                sheet.merge_range(start_row, 0, end_row, 0, group['serial'], cur_cell)
                sheet.merge_range(start_row, 1, end_row, 1, group.get('owner_details', ''), cur_name)
                cur_subtotal = subtotal_num_fmt_alt if is_alt else subtotal_num_fmt
                sheet.merge_range(start_row, 7, end_row, 7, total_det, cur_subtotal)
                sheet.merge_range(start_row, 8, end_row, 8, '', cur_cell)
            else:
                sheet.set_row(start_row, owner_height)
                sheet.write(start_row, 0, group['serial'], cur_cell)
                sheet.write(start_row, 1, group.get('owner_details', ''), cur_name)
                sheet.write_number(start_row, 7, total_det, cur_num)
                sheet.write(start_row, 8, '', cur_cell)

        # ── Total row ─────────────────────────────────────────────────────
        sheet.set_row(row, 20)
        sheet.merge_range(row, 0, row, 2, 'कुल / Total', total_label_fmt)
        sheet.write_number(row, 3, t_ha, total_area_fmt)
        sheet.write_number(row, 4, t_land, total_num_fmt)
        sheet.write_number(row, 5, t_asset, total_num_fmt)
        sheet.write_number(row, 6, t_tree, total_num_fmt)
        sheet.write_number(row, 7, t_det, total_num_fmt)
        sheet.write(row, 8, '', total_label_fmt)

        # ── Column widths ─────────────────────────────────────────────────
        sheet.set_column(0, 0, 7)
        sheet.set_column(1, 1, 30)
        sheet.set_column(2, 2, 12)
        sheet.set_column(3, 3, 10)
        sheet.set_column(4, 7, 14)
        sheet.set_column(8, 8, 12)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        attachment = self.env['ir.attachment'].create({
            'name': f"ConsolidatedAwardSheet_{self.village_id.name or 'Award'}.xlsx",
            'type': 'binary',
            'datas': file_data,
            'res_model': 'bhu.section23.award',
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def get_consolidated_award_data(self):
        """Get consolidated award data grouped by owner, with one sub-row per khasra.

        Returns a list of owner-groups. Each group has:
          serial, owners, owner_details, khasra_lines (list per khasra),
          and grand totals for the owner block.
        """
        self.ensure_one()

        land_data = self.get_land_compensation_grouped_data()
        tree_data = self.get_tree_compensation_grouped_data()
        asset_data = self.get_structure_compensation_grouped_data()

        # Build flat khasra → compensation lookups for tree & asset
        tree_by_khasra = {}
        for grp in tree_data:
            for line in grp.get('lines', []):
                k = (line.get('tree_khasra') or line.get('khasra') or '').strip()
                if k:
                    tree_by_khasra[k] = tree_by_khasra.get(k, 0.0) + (line.get('total', 0.0) or 0.0)

        asset_by_khasra = {}
        for grp in asset_data:
            for line in grp.get('lines', []):
                k = (line.get('asset_khasra') or '').strip()
                if k:
                    asset_by_khasra[k] = asset_by_khasra.get(k, 0.0) + (line.get('total', 0.0) or 0.0)

        def _khasra_sort_key(k):
            parts = (k or '').split('/', 1)
            main = int(parts[0]) if parts and parts[0].isdigit() else 10**12
            sub = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10**12
            return (main, sub, k)

        def _owner_text(name, father, spouse, address):
            block = f"1. {name}"
            if father:
                block += f" पिता {father}"
            elif spouse:
                block += f" पति {spouse}"
            if address:
                block += f"\nनिवासी: {address}"
            return block

        result = []
        serial = 1

        # Primary pass: one group per khasra (all owners on that khasra together)
        seen_khasra_in_land = set()
        for grp in land_data:
            owner_name = (grp.get('landowner_name') or '').strip()
            father_name = (grp.get('father_name') or '').strip()
            spouse_name = (grp.get('spouse_name') or '').strip()
            address = (grp.get('address') or '').strip()

            # Aggregate per khasra (urban slabs produce multiple lines for the same khasra)
            khasra_agg = {}
            for line in grp.get('lines', []):
                k = (line.get('khasra') or '').strip()
                if not k:
                    continue
                seen_khasra_in_land.add(k)
                if k not in khasra_agg:
                    khasra_agg[k] = {'acquired_area_ha': 0.0, 'land_compensation': 0.0}
                khasra_agg[k]['acquired_area_ha'] += (line.get('acquired_area', 0.0) or 0.0)
                land_payable = float(
                    line.get('paid_compensation', 0.0)
                    or line.get('total_compensation', 0.0)
                    or 0.0
                )
                khasra_agg[k]['land_compensation'] += land_payable

            khasra_lines = []
            for k in sorted(khasra_agg.keys(), key=_khasra_sort_key):
                land_c = khasra_agg[k]['land_compensation']
                tree_c = tree_by_khasra.get(k, 0.0)
                asset_c = asset_by_khasra.get(k, 0.0)
                khasra_lines.append({
                    'khasra': k,
                    'acquired_area_ha': khasra_agg[k]['acquired_area_ha'],
                    'land_compensation': land_c,
                    'asset_compensation': asset_c,
                    'tree_compensation': tree_c,
                    'determined_total': land_c + asset_c + tree_c,
                })

            owner_blocks = grp.get('owner_blocks') or []
            if owner_blocks:
                owners = [
                    {
                        'name': (b.get('name') or '').strip(),
                        'father_name': (b.get('father_name') or '').strip(),
                        'spouse_name': (b.get('spouse_name') or '').strip(),
                        'address': (b.get('address') or '').strip(),
                    }
                    for b in owner_blocks
                ]
                owner_details = self._land_owner_display_from_blocks(owner_blocks)
            else:
                owners = [{'name': owner_name, 'father_name': father_name,
                           'spouse_name': spouse_name, 'address': address}]
                owner_details = _owner_text(owner_name, father_name, spouse_name, address)
            result.append({
                'serial': serial,
                'owners': owners,
                'owner_details': owner_details,
                'khasra_lines': khasra_lines,
                'total_acquired_area_ha': sum(k['acquired_area_ha'] for k in khasra_lines),
                'total_land_compensation': sum(k['land_compensation'] for k in khasra_lines),
                'total_asset_compensation': sum(k['asset_compensation'] for k in khasra_lines),
                'total_tree_compensation': sum(k['tree_compensation'] for k in khasra_lines),
                'total_determined': sum(k['determined_total'] for k in khasra_lines),
            })
            serial += 1

        # Secondary pass: khasras that have only tree/asset (no land rows)
        extra_khasras = (set(tree_by_khasra) | set(asset_by_khasra)) - seen_khasra_in_land
        for k in sorted(extra_khasras, key=_khasra_sort_key):
            tree_c = tree_by_khasra.get(k, 0.0)
            asset_c = asset_by_khasra.get(k, 0.0)
            kline = {
                'khasra': k,
                'acquired_area_ha': 0.0,
                'land_compensation': 0.0,
                'asset_compensation': asset_c,
                'tree_compensation': tree_c,
                'determined_total': asset_c + tree_c,
            }
            result.append({
                'serial': serial,
                'owners': [],
                'owner_details': '',
                'khasra_lines': [kline],
                'total_acquired_area_ha': 0.0,
                'total_land_compensation': 0.0,
                'total_asset_compensation': asset_c,
                'total_tree_compensation': tree_c,
                'total_determined': asset_c + tree_c,
            })
            serial += 1

        return result
