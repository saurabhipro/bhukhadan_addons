# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import ValidationError


class Section23AwardRR(models.Model):
    _inherit = 'bhu.section23.award'

    RR_TITLE_TEXT = ""

    def get_rr_title_text(self):
        self.ensure_one()
        return self.RR_TITLE_TEXT

    def _get_rr_owner_text(self, row):
        owner_name = row.get('landowner_name', '') or '-'
        relation = ''
        if row.get('father_name'):
            relation = f"पिता {row.get('father_name')}"
        elif row.get('spouse_name'):
            relation = f"पति {row.get('spouse_name')}"
        caste = row.get('caste', '') or '-'
        return f"{owner_name}, {relation}, जाति {caste}" if relation else f"{owner_name}, जाति {caste}"

    def _get_rr_khasra_asset_tree_maps(self):
        """Per-khasra structure and tree totals (same source as consolidated award)."""
        self.ensure_one()
        tree_by_khasra = {}
        for grp in self.get_tree_compensation_grouped_data() or []:
            for line in grp.get('lines') or []:
                k = (line.get('tree_khasra') or line.get('khasra') or '').strip()
                if k:
                    tree_by_khasra[k] = tree_by_khasra.get(k, 0.0) + (line.get('total', 0.0) or 0.0)

        asset_by_khasra = {}
        for grp in self.get_structure_compensation_grouped_data() or []:
            for line in grp.get('lines') or []:
                k = (line.get('asset_khasra') or '').strip()
                if k:
                    asset_by_khasra[k] = asset_by_khasra.get(k, 0.0) + (line.get('total', 0.0) or 0.0)
        return asset_by_khasra, tree_by_khasra

    def _s23_land_payable_amount(self, row):
        """Section 23 land payable used as R&R / consolidated column 5."""
        return float(
            (row or {}).get('paid_compensation', 0.0)
            or (row or {}).get('total_compensation', 0.0)
            or 0.0
        )

    def get_rr_award_data(self):
        """Return grouped R&R rows (9-column format), aligned with consolidated columns 5–9."""
        self.ensure_one()
        rows = self.get_land_compensation_data() or []
        asset_by_khasra, tree_by_khasra = self._get_rr_khasra_asset_tree_maps()

        def _khasra_sort_key(k):
            parts = (k or '').split('/', 1)
            main = int(parts[0]) if parts and parts[0].isdigit() else 10**12
            sub = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10**12
            return (main, sub, k)

        grouped = {}
        for row in rows:
            key = (
                row.get('landowner_name', '') or '',
                row.get('father_name', '') or '',
                row.get('spouse_name', '') or '',
                row.get('caste', '') or '',
            )
            owner_text = (row.get('landowner_display') or '').strip()
            if not owner_text:
                owner_text = self._get_rr_owner_text(row)
            group = grouped.setdefault(key, {
                'owner_text': owner_text,
                'rows': [],
            })
            if (row.get('landowner_display') or '').strip():
                group['owner_text'] = row['landowner_display']
            group['rows'].append(row)

        result = []
        serial = 1
        for group in grouped.values():
            khasra_agg = {}
            for row in group['rows']:
                khasra = (row.get('khasra') or '').strip()
                if not khasra:
                    continue
                bucket = khasra_agg.setdefault(khasra, {
                    'field_area': 0.0,
                    'land_compensation': 0.0,
                    'land_type': row.get('land_type_label', '') or (
                        'सिंचित' if bool(row.get('irrigated', False)) else 'असिंचित'
                    ),
                })
                bucket['field_area'] += float(row.get('acquired_area', 0.0) or row.get('original_area', 0.0) or 0.0)
                bucket['land_compensation'] += self._s23_land_payable_amount(row)

            lines = []
            for khasra in sorted(khasra_agg.keys(), key=_khasra_sort_key):
                agg = khasra_agg[khasra]
                land_c = float(agg.get('land_compensation', 0.0) or 0.0)
                asset_c = float(asset_by_khasra.get(khasra, 0.0) or 0.0)
                tree_c = float(tree_by_khasra.get(khasra, 0.0) or 0.0)
                lines.append({
                    'khasra': khasra,
                    'field_area': float(agg.get('field_area', 0.0) or 0.0),
                    'land_type': agg.get('land_type', '') or '',
                    'land_compensation': land_c,
                    'asset_compensation': asset_c,
                    'tree_compensation': tree_c,
                    'total_compensation': land_c + asset_c + tree_c,
                })

            line_count = len(lines) or 1
            owner_land_comp = sum((ln.get('land_compensation', 0.0) or 0.0) for ln in lines)
            owner_asset_comp = sum((ln.get('asset_compensation', 0.0) or 0.0) for ln in lines)
            owner_tree_comp = sum((ln.get('tree_compensation', 0.0) or 0.0) for ln in lines)
            owner_determined_comp = owner_land_comp + owner_asset_comp + owner_tree_comp
            owner_final_comp = min(owner_determined_comp * 0.5, 500000.0)
            render_rows = []
            for idx, line in enumerate(lines):
                line_data = dict(line)
                line_data.update({
                    'show_owner': idx == 0,
                    'rowspan': line_count,
                    'owner_land_compensation': owner_land_comp,
                    'owner_asset_compensation': owner_asset_comp,
                    'owner_tree_compensation': owner_tree_comp,
                    'owner_determined_compensation': owner_determined_comp,
                    'owner_final_compensation': owner_final_comp,
                })
                render_rows.append(line_data)
            result.append({
                'serial': serial,
                'owner_text': group['owner_text'],
                'rowspan': line_count,
                'lines': lines,
                'render_rows': render_rows,
                'owner_land_compensation': owner_land_comp,
                'owner_asset_compensation': owner_asset_comp,
                'owner_tree_compensation': owner_tree_comp,
                'owner_determined_compensation': owner_determined_comp,
                'owner_final_compensation': owner_final_comp,
            })
            serial += 1
        return result

    def action_download_rr_pdf(self):
        """Download R&R award sheet as PDF."""
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        rr_data = self.get_rr_award_data()
        if not rr_data:
            raise ValidationError(_('No R&R data available for this award.'))
        report_action = self.env.ref('bhukhadan_core.action_report_rr_award_sheet')
        return report_action.sudo().report_action(self)

    def action_download_rr_excel(self):
        """Download R&R award sheet as Excel."""
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        import io
        import base64
        try:
            import xlsxwriter
        except ImportError:
            raise ValidationError(_("Python library 'xlsxwriter' is not installed."))

        rr_rows = self.get_rr_award_data()
        if not rr_rows:
            raise ValidationError(_('No R&R data available for this award.'))

        headers = self.get_award_header_constants()['excel']['rr_award_headers']
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('R&R Award')
        font = 'Noto Sans Devanagari'
        title_fmt = wb.add_format({'font_name': font, 'bold': True, 'font_size': 14, 'align': 'center'})
        head_fmt = wb.add_format({
            'font_name': font, 'bold': True, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'text_wrap': True, 'bg_color': '#D3D3D3',
        })
        number_head_fmt = wb.add_format({
            'font_name': font, 'bold': True, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#E8E8E8',
        })
        cell_fmt = wb.add_format({'font_name': font, 'border': 1, 'valign': 'vcenter'})
        owner_cell_fmt = wb.add_format({'font_name': font, 'border': 1, 'valign': 'top', 'text_wrap': True})
        center_cell_fmt = wb.add_format({'font_name': font, 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        num2_fmt = wb.add_format({'font_name': font, 'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
        num4_fmt = wb.add_format({'font_name': font, 'border': 1, 'align': 'right', 'num_format': '0.0000'})
        total_lbl_fmt = wb.add_format({'font_name': font, 'bold': True, 'border': 1, 'align': 'center', 'bg_color': '#E8E8E8'})
        total_num2_fmt = wb.add_format({'font_name': font, 'bold': True, 'border': 1, 'align': 'right', 'num_format': '#,##0.00', 'bg_color': '#E8E8E8'})
        total_num4_fmt = wb.add_format({'font_name': font, 'bold': True, 'border': 1, 'align': 'right', 'num_format': '0.0000', 'bg_color': '#E8E8E8'})

        ws.merge_range(0, 0, 0, 8, 'पुनर्वास अवार्ड पत्रक (R&R Award Sheet)', title_fmt)
        for idx, h in enumerate(headers):
            ws.write(3, idx, h, head_fmt)
        number_row = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
        for idx, n in enumerate(number_row):
            ws.write(4, idx, n, number_head_fmt)

        total_area = total_land = total_asset = total_tree = total_det = total_final = 0.0
        row_idx = 5
        for group in rr_rows:
            lines = group.get('lines', [])
            if not lines:
                continue
            start_row = row_idx
            end_row = row_idx + len(lines) - 1
            owner_land = float(group.get('owner_land_compensation', 0.0) or 0.0)
            owner_asset = float(group.get('owner_asset_compensation', 0.0) or 0.0)
            owner_tree = float(group.get('owner_tree_compensation', 0.0) or 0.0)
            owner_det = float(group.get('owner_determined_compensation', 0.0) or 0.0)
            owner_final = float(group.get('owner_final_compensation', 0.0) or 0.0)
            if start_row == end_row:
                ws.write(start_row, 0, group['serial'], center_cell_fmt)
                ws.write(start_row, 1, group['owner_text'], owner_cell_fmt)
                ws.write_number(start_row, 4, owner_land, num2_fmt)
                ws.write_number(start_row, 5, owner_asset, num2_fmt)
                ws.write_number(start_row, 6, owner_tree, num2_fmt)
                ws.write_number(start_row, 7, owner_det, num2_fmt)
                ws.write_number(start_row, 8, owner_final, num2_fmt)
            else:
                ws.merge_range(start_row, 0, end_row, 0, group['serial'], center_cell_fmt)
                ws.merge_range(start_row, 1, end_row, 1, group['owner_text'], owner_cell_fmt)
                ws.merge_range(start_row, 4, end_row, 4, owner_land, num2_fmt)
                ws.merge_range(start_row, 5, end_row, 5, owner_asset, num2_fmt)
                ws.merge_range(start_row, 6, end_row, 6, owner_tree, num2_fmt)
                ws.merge_range(start_row, 7, end_row, 7, owner_det, num2_fmt)
                ws.merge_range(start_row, 8, end_row, 8, owner_final, num2_fmt)

            for line in lines:
                ws.write(row_idx, 2, line['khasra'], cell_fmt)
                ws.write_number(row_idx, 3, line['field_area'], num4_fmt)
                total_area += line['field_area']
                total_land += line['land_compensation']
                total_asset += line['asset_compensation']
                total_tree += line['tree_compensation']
                row_idx += 1
            total_det += owner_det
            total_final += owner_final

        ws.merge_range(row_idx, 0, row_idx, 2, 'कुल / Total', total_lbl_fmt)
        ws.write_number(row_idx, 3, total_area, total_num4_fmt)
        ws.write_number(row_idx, 4, total_land, total_num2_fmt)
        ws.write_number(row_idx, 5, total_asset, total_num2_fmt)
        ws.write_number(row_idx, 6, total_tree, total_num2_fmt)
        ws.write_number(row_idx, 7, total_det, total_num2_fmt)
        ws.write_number(row_idx, 8, total_final, total_num2_fmt)

        widths = [8, 38, 14, 12, 14, 14, 14, 16, 16]
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)

        wb.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()
        attachment = self.env['ir.attachment'].create({
            'name': f"RRAwardSheet_{self.village_id.name or 'Award'}.xlsx",
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
