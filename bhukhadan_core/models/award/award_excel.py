# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class Section23AwardExcel(models.Model):
    _inherit = 'bhu.section23.award'

    def action_download_excel_components(self, export_scope='all'):
        """Download Section 23 Excel in the exact Simulator format."""
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        export_scope = export_scope or self.env.context.get('bhu_export_scope') or 'all'
        if export_scope not in ('all', 'land', 'asset', 'tree'):
            export_scope = 'all'
        show_land = export_scope in ('all', 'land')
        show_asset = export_scope in ('all', 'asset')
        show_tree = export_scope in ('all', 'tree')
        import io
        import base64
        try:
            import xlsxwriter
        except ImportError:
            raise ValidationError(_("Python library 'xlsxwriter' is not installed."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        award_headers = self.get_award_header_constants()
        land_sheet = asset_sheet = tree_sheet = None
        if show_land:
            land_sheet = workbook.add_worksheet('Land')
        if show_asset:
            asset_sheet = workbook.add_worksheet('Assets')
        if show_tree:
            tree_sheet = workbook.add_worksheet('Trees')

        # Formats (kept same as simulator)
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        subtitle_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        header_group_fmt = workbook.add_format({'bold': True, 'bg_color': '#d9e1f2', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#f2f2f2', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        cell_fmt = workbook.add_format({'border': 1, 'valign': 'top'})
        cell_center_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        rehab_col_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        yes_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#2e7d32', 'color': 'white', 'bold': True})
        no_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#c62828', 'color': 'white', 'bold': True})
        number_fmt = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0.0000'})
        area_dual_fmt = workbook.add_format({'border': 1, 'align': 'right', 'valign': 'vcenter'})
        money_fmt = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0'})
        asset_type_default_fmt = workbook.add_format({'border': 1, 'valign': 'top'})
        asset_type_cell_formats = {
            'house': workbook.add_format({'border': 1, 'valign': 'top'}),
            'well': workbook.add_format({'border': 1, 'valign': 'top'}),
            'shed': workbook.add_format({'border': 1, 'valign': 'top'}),
            'other': workbook.add_format({'border': 1, 'valign': 'top'}),
        }
        asset_type_pukka_formats = {
            'makan': workbook.add_format({'border': 1, 'valign': 'top'}),
            'well': workbook.add_format({'border': 1, 'valign': 'top'}),
            'maveshi_kotha': workbook.add_format({'border': 1, 'valign': 'top'}),
            'poultry_farm_shed': workbook.add_format({'border': 1, 'valign': 'top'}),
            'other': workbook.add_format({'border': 1, 'valign': 'top'}),
        }
        asset_type_pukka_default = workbook.add_format({'border': 1, 'valign': 'top'})
        total_label_fmt = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#e2e8f0', 'align': 'center', 'valign': 'vcenter'})
        total_money_fmt = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#e2e8f0', 'align': 'right', 'num_format': '#,##0'})
        total_number_fmt = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#e2e8f0', 'align': 'right', 'num_format': '#,##0.0000'})
        blank_msg_fmt = workbook.add_format({'italic': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'})

        def _setup_sheet(sheet, col_widths, repeat_to_row):
            sheet.set_landscape()
            sheet.set_paper(9)
            sheet.fit_to_pages(1, 0)
            sheet.repeat_rows(0, repeat_to_row)
            for idx, width in enumerate(col_widths):
                sheet.set_column(idx, idx, width)

        def _yes_no_format(flag):
            return yes_fmt if flag else no_fmt

        rate_val = float(self.avg_three_year_sales_sort_rate or 0.0)
        urban_body_label = self.get_urban_body_label()
        urban_part = f" | Urban Body / नगरीय निकाय: {urban_body_label}" if urban_body_label else ''
        subtitle = (
            f"Village / ग्राम: {self.village_id.name or '-'} | "
            f"Project / परियोजना: {self.project_id.name or '-'} | "
            f"Date / तिथि: {self.award_date or fields.Date.today()}{urban_part} | "
            f"विगत 3 वर्षों का औसत बिक्री छांट दर रुपए में (प्रति हेक्टेयर): {rate_val:,.4f}"
        )

        if show_land:
            # LAND TAB
            land_col_widths = [4, 24, 10, 10, 10, 10, 8, 8, 8, 13, 10, 11, 11, 10, 10, 11, 14, 11, 10]
            _setup_sheet(land_sheet, land_col_widths, 8)
            row = 0
            land_sheet.merge_range(row, 0, row, 18, 'अर्जित भूमि का मुआवजा पत्रक', title_fmt)
            row += 1
            land_sheet.merge_range(row, 0, row, 18, subtitle, subtitle_fmt)
            row += 2
            land_sheet.merge_range(row, 0, row, 18, f"{award_headers['sections']['land_sheet_label']} - {award_headers['sections']['land_title']}", header_group_fmt)
            row += 1

            sim_land_headers = award_headers['excel']['sim_land_headers']
            land_sheet.merge_range(row, 0, row + 1, 0, sim_land_headers['rowspan_headers'][0], header_fmt)
            land_sheet.merge_range(row, 1, row + 1, 1, sim_land_headers['rowspan_headers'][1], header_fmt)
            land_sheet.merge_range(row, 2, row, 3, sim_land_headers['group_held'], header_group_fmt)
            land_sheet.merge_range(row, 4, row, 5, sim_land_headers['group_acquired'], header_group_fmt)
            land_sheet.merge_range(row, 6, row + 1, 6, sim_land_headers['col_7_standalone'], header_fmt)
            land_sheet.merge_range(row, 7, row, 9, sim_land_headers['group_main_road'], header_group_fmt)
            interest_period_note = self.get_interest_period_note()
            for col_offset, label in enumerate(sim_land_headers['tail_headers'], start=10):
                # Column 14 is the interest column (index 4 in tail_headers)
                header_title = f"{label}\n{interest_period_note}" if col_offset == 14 else label
                land_sheet.merge_range(row, col_offset, row + 1, col_offset, header_title, header_fmt)
            row += 1
            sub_header_columns = [2, 3, 4, 5, 7, 8, 9]
            for col_offset, label in zip(sub_header_columns, sim_land_headers['sub_headers']):
                land_sheet.write(row, col_offset, label, header_fmt)
            land_sheet.set_row(row - 1, 36)
            land_sheet.set_row(row, 36)
            row += 1

            land_groups = self.get_land_compensation_grouped_data()
            if not land_groups:
                land_sheet.merge_range(row, 0, row, 18, 'No land data available / भूमि डेटा उपलब्ध नहीं है (Blank)', blank_msg_fmt)
                row += 1
            else:
                total_basic = total_market = total_solatium = 0.0
                total_interest = total_comp = total_paid = total_acq = total_rehab = 0.0
                for i, group in enumerate(land_groups, 1):
                    lines = group.get('lines', [])
                    details = (
                        group.get('landowner_display')
                        or group.get('landowner_name', '')
                    )
                    if not group.get('landowner_display'):
                        father = group.get('father_name')
                        if father:
                            details = f"{details}\nपिता/पति: {father}"

                    line_count = len(lines)

                    # Merge serial and owner cells BEFORE the inner loop (for multi-line groups)
                    if line_count > 1:
                        land_sheet.merge_range(row, 0, row + line_count - 1, 0, i, cell_center_fmt)
                        land_sheet.merge_range(row, 1, row + line_count - 1, 1, details, cell_fmt)

                    for idx, land in enumerate(lines):
                        # For single-line groups, write serial and owner on first (only) iteration
                        if idx == 0 and line_count == 1:
                            land_sheet.write(row, 0, i, cell_center_fmt)
                            land_sheet.write(row, 1, details, cell_fmt)
                        is_urban_slab = bool(land.get('is_urban_slab'))
                        khasra_merge_show = bool(land.get('khasra_merge_show', True))
                        khasra_merge_span = int(land.get('khasra_merge_rowspan', 1) or 1)
                        if is_urban_slab:
                            if khasra_merge_show:
                                if khasra_merge_span > 1:
                                    land_sheet.merge_range(
                                        row, 2, row + khasra_merge_span - 1, 2,
                                        land.get('khasra', ''), cell_center_fmt
                                    )
                                    land_sheet.merge_range(
                                        row, 3, row + khasra_merge_span - 1, 3,
                                        float(land.get('original_area', 0.0) or 0.0), number_fmt
                                    )
                                else:
                                    land_sheet.write(row, 2, land.get('khasra', ''), cell_center_fmt)
                                    land_sheet.write_number(row, 3, float(land.get('original_area', 0.0) or 0.0), number_fmt)
                        else:
                            land_sheet.write(row, 2, land.get('khasra', ''), cell_center_fmt)
                            land_sheet.write_number(row, 3, float(land.get('original_area', 0.0) or 0.0), number_fmt)
                        land_sheet.write(row, 4, land.get('khasra', ''), cell_center_fmt)
                        if is_urban_slab:
                            land_sheet.write(
                                row, 5,
                                self.format_land_sheet_col6_acquired_area(land),
                                area_dual_fmt,
                            )
                        else:
                            land_sheet.write_number(row, 5, float(land.get('acquired_area', 0.0) or 0.0), number_fmt)
                        is_within_distance = bool(land.get('is_within_distance'))
                        is_irrigated = bool(land.get('irrigated'))
                        is_unirrigated = bool(land.get('unirrigated'))
                        is_diverted = bool(land.get('is_diverted'))
                        _guide_unit = (land.get('guide_line_rate_unit') or 'ha')
                        # BMR: डायवर्टेड या नगरीय वर्गमीटर स्लैब → सिंचित/असिंचित कॉलम NA; विचलित कॉलम अलग से भरता है.
                        irr_unirr_show_na = (
                            (not is_within_distance) and (
                                is_diverted
                                or (is_urban_slab and _guide_unit == 'sqm')
                            )
                        )
                        # Col 7 = "on main road": always हाँ (MR) / नहीं (BMR); never raw metres (avoids 51 m vs threshold confusion).
                        if is_urban_slab:
                            if khasra_merge_show:
                                yes_no_text = 'हाँ' if is_within_distance else 'नहीं'
                                yes_no_fmt = _yes_no_format(is_within_distance)
                                if khasra_merge_span > 1:
                                    land_sheet.merge_range(row, 6, row + khasra_merge_span - 1, 6, yes_no_text, yes_no_fmt)
                                    if is_within_distance:
                                        land_sheet.merge_range(row, 7, row + khasra_merge_span - 1, 7, 'NA', cell_center_fmt)
                                        land_sheet.merge_range(row, 8, row + khasra_merge_span - 1, 8, 'NA', cell_center_fmt)
                                        land_sheet.merge_range(row, 9, row + khasra_merge_span - 1, 9, 'NA', cell_center_fmt)
                                    elif irr_unirr_show_na:
                                        land_sheet.merge_range(row, 7, row + khasra_merge_span - 1, 7, 'NA', cell_center_fmt)
                                        land_sheet.merge_range(row, 8, row + khasra_merge_span - 1, 8, 'NA', cell_center_fmt)
                                        land_sheet.merge_range(
                                            row, 9, row + khasra_merge_span - 1, 9,
                                            'हाँ' if is_diverted else 'नहीं',
                                            _yes_no_format(is_diverted),
                                        )
                                    else:
                                        land_sheet.merge_range(
                                            row, 7, row + khasra_merge_span - 1, 7,
                                            'हाँ' if is_irrigated else 'नहीं',
                                            _yes_no_format(is_irrigated),
                                        )
                                        land_sheet.merge_range(
                                            row, 8, row + khasra_merge_span - 1, 8,
                                            'हाँ' if is_unirrigated else 'नहीं',
                                            _yes_no_format(is_unirrigated),
                                        )
                                        land_sheet.merge_range(
                                            row, 9, row + khasra_merge_span - 1, 9,
                                            'हाँ' if is_diverted else 'नहीं',
                                            _yes_no_format(is_diverted),
                                        )
                                else:
                                    land_sheet.write(row, 6, yes_no_text, yes_no_fmt)
                                    if is_within_distance:
                                        land_sheet.write(row, 7, 'NA', cell_center_fmt)
                                        land_sheet.write(row, 8, 'NA', cell_center_fmt)
                                        land_sheet.write(row, 9, 'NA', cell_center_fmt)
                                    elif irr_unirr_show_na:
                                        land_sheet.write(row, 7, 'NA', cell_center_fmt)
                                        land_sheet.write(row, 8, 'NA', cell_center_fmt)
                                        land_sheet.write(row, 9, 'हाँ' if is_diverted else 'नहीं', _yes_no_format(is_diverted))
                                    else:
                                        land_sheet.write(row, 7, 'हाँ' if is_irrigated else 'नहीं', _yes_no_format(is_irrigated))
                                        land_sheet.write(row, 8, 'हाँ' if is_unirrigated else 'नहीं', _yes_no_format(is_unirrigated))
                                        land_sheet.write(row, 9, 'हाँ' if is_diverted else 'नहीं', _yes_no_format(is_diverted))
                        else:
                            land_sheet.write(
                                row, 6,
                                'हाँ' if is_within_distance else 'नहीं',
                                _yes_no_format(is_within_distance),
                            )
                            if is_within_distance:
                                land_sheet.write(row, 7, 'NA', cell_center_fmt)
                                land_sheet.write(row, 8, 'NA', cell_center_fmt)
                                land_sheet.write(row, 9, 'NA', cell_center_fmt)
                            elif irr_unirr_show_na:
                                land_sheet.write(row, 7, 'NA', cell_center_fmt)
                                land_sheet.write(row, 8, 'NA', cell_center_fmt)
                                land_sheet.write(row, 9, 'हाँ' if is_diverted else 'नहीं', _yes_no_format(is_diverted))
                            else:
                                land_sheet.write(row, 7, 'हाँ' if is_irrigated else 'नहीं', _yes_no_format(is_irrigated))
                                land_sheet.write(row, 8, 'हाँ' if is_unirrigated else 'नहीं', _yes_no_format(is_unirrigated))
                                land_sheet.write(row, 9, 'हाँ' if is_diverted else 'नहीं', _yes_no_format(is_diverted))
                        land_sheet.write_number(row, 10, float(land.get('guide_line_rate', 0.0) or 0.0), money_fmt)
                        land_sheet.write_number(row, 11, float(land.get('basic_value', 0.0) or 0.0), money_fmt)
                        land_sheet.write_number(row, 12, float(land.get('market_value', 0.0) or 0.0), money_fmt)
                        land_sheet.write_number(row, 13, float(land.get('solatium', 0.0) or 0.0), money_fmt)
                        if land.get('is_urban_slab'):
                            if land.get('khasra_merge_show', True):
                                urban_span = int(land.get('khasra_merge_rowspan', 1) or 1)
                                if urban_span > 1:
                                    land_sheet.merge_range(row, 14, row + urban_span - 1, 14, 'NA', cell_center_fmt)
                                else:
                                    land_sheet.write(row, 14, 'NA', cell_center_fmt)
                        else:
                            land_sheet.write_number(row, 14, float(land.get('interest', 0.0) or 0.0), money_fmt)
                        land_sheet.write_number(row, 15, float(land.get('total_compensation', 0.0) or 0.0), money_fmt)
                        if land.get('fallow'):
                            land_type_hi = 'पड़ती भूमि'
                        elif land.get('irrigated'):
                            land_type_hi = 'सिंचित भूमि'
                        else:
                            land_type_hi = 'असिंचित भूमि'
                        rehab_show = float(
                            land.get('rehab_policy_amount_display', land.get('rehab_policy_amount', 0.0)) or 0.0
                        )
                        col17_rehab_text = (
                            f"{land_type_hi}\n{self.format_indian_number(rehab_show, 2)}"
                        )
                        # Col 17 (header "पुनर्वास नीति… न्यूनतम देय"): भूमि प्रकार + नीति राशि
                        if land.get('is_urban_slab'):
                            if land.get('khasra_merge_show', True):
                                urban_span = int(land.get('khasra_merge_rowspan', 1) or 1)
                                if urban_span > 1:
                                    land_sheet.merge_range(
                                        row, 16, row + urban_span - 1, 16,
                                        col17_rehab_text, rehab_col_fmt,
                                    )
                                else:
                                    land_sheet.write(row, 16, col17_rehab_text, rehab_col_fmt)
                        else:
                            land_sheet.write(row, 16, col17_rehab_text, rehab_col_fmt)
                        land_sheet.write_number(row, 17, float(land.get('paid_compensation', 0.0) or 0.0), money_fmt)
                        land_sheet.write(row, 18, land.get('remark', ''), cell_fmt)
                        row += 1

                    group_basic_total = float(group.get('basic_value', 0.0) or 0.0)
                    group_market_total = float(group.get('market_value', 0.0) or 0.0)
                    group_solatium_total = float(group.get('solatium', 0.0) or 0.0)
                    group_interest_total, _group_days = self._calculate_interest_on_basic(group_basic_total)
                    group_total_comp = group_market_total + group_solatium_total + group_interest_total
                    land_sheet.merge_range(row, 0, row, 1, 'कुल', total_label_fmt)
                    land_sheet.write_number(row, 3, float(group.get('original_area', 0.0) or 0.0), total_number_fmt)
                    land_sheet.write_number(row, 4, float(group.get('khasra_count', 0) or 0), total_money_fmt)
                    _group_has_urban = any(l.get('is_urban_slab') for l in lines)
                    land_sheet.write(
                        row, 5,
                        self.format_land_sheet_col6_acquired_area_group(group),
                        area_dual_fmt if _group_has_urban else total_number_fmt,
                    )
                    land_sheet.write_blank(row, 6, None, total_label_fmt)
                    land_sheet.write_blank(row, 7, None, total_label_fmt)
                    land_sheet.write_blank(row, 8, None, total_label_fmt)
                    land_sheet.write_blank(row, 9, None, total_label_fmt)
                    land_sheet.write_blank(row, 10, None, total_label_fmt)
                    land_sheet.write_number(row, 11, group_basic_total, total_money_fmt)
                    land_sheet.write_number(row, 12, group_market_total, total_money_fmt)
                    land_sheet.write_number(row, 13, group_solatium_total, total_money_fmt)
                    # Col 15 (interest) in yellow row is always based on yellow Col 12 basic total.
                    land_sheet.write_number(row, 14, group_interest_total, total_money_fmt)
                    land_sheet.write_number(row, 15, group_total_comp, total_money_fmt)
                    _g_rehab = float(group.get('rehab_policy_amount', 0.0) or 0.0)
                    land_sheet.write(
                        row, 16,
                        self.format_indian_number(_g_rehab, 2),
                        total_money_fmt,
                    )
                    land_sheet.write_number(row, 17, float(group.get('paid_compensation', 0.0) or 0.0), total_money_fmt)
                    land_sheet.write_blank(row, 18, None, total_label_fmt)
                    total_acq += float(group.get('acquired_area', 0.0) or 0.0)
                    total_basic += group_basic_total
                    total_market += group_market_total
                    total_solatium += group_solatium_total
                    total_interest += group_interest_total
                    total_comp += group_total_comp
                    total_paid += float(group.get('paid_compensation', 0.0) or 0.0)
                    total_rehab += float(group.get('rehab_policy_amount', 0.0) or 0.0)
                    row += 1

                land_sheet.merge_range(row, 0, row, 3, 'MAHAYOG (TOTAL) / महायोग', total_label_fmt)
                land_sheet.write_blank(row, 4, None, total_label_fmt)
                _mah_urb = any(
                    any(l.get('is_urban_slab') for l in (g.get('lines') or []))
                    for g in land_groups
                )
                land_sheet.write(
                    row, 5,
                    self.format_land_sheet_col6_acquired_area_mahayog(land_groups, total_acq),
                    area_dual_fmt if _mah_urb else total_number_fmt,
                )
                land_sheet.write_blank(row, 6, None, total_label_fmt)
                land_sheet.write_blank(row, 7, None, total_label_fmt)
                land_sheet.write_blank(row, 8, None, total_label_fmt)
                land_sheet.write_blank(row, 9, None, total_label_fmt)
                land_sheet.write_blank(row, 10, None, total_label_fmt)
                land_sheet.write_number(row, 11, total_basic, total_money_fmt)
                land_sheet.write_number(row, 12, total_market, total_money_fmt)
                land_sheet.write_number(row, 13, total_solatium, total_money_fmt)
                land_sheet.write_number(row, 14, total_interest, total_money_fmt)
                land_sheet.write_number(row, 15, total_comp, total_money_fmt)
                land_sheet.write(
                    row, 16,
                    self.format_indian_number(total_rehab, 2),
                    total_money_fmt,
                )
                land_sheet.write_number(row, 17, total_paid, total_money_fmt)
                land_sheet.write_blank(row, 18, None, total_label_fmt)

        if show_asset:
            # ASSET TAB
            asset_col_widths = [4, 24, 10, 10, 22, 10, 12, 12, 12, 12, 12]
            _setup_sheet(asset_sheet, asset_col_widths, 4)
            asset_row = 0
            asset_sheet.merge_range(asset_row, 0, asset_row, 10, 'परिसंपत्तियों का मुआवजा प्रपत्र', title_fmt)
            asset_row += 1
            asset_sheet.merge_range(asset_row, 0, asset_row, 10, subtitle, subtitle_fmt)
            asset_row += 2
            asset_sheet.merge_range(asset_row, 0, asset_row, 10, f"{award_headers['sections']['asset_sheet_label']} - {award_headers['sections']['asset_title']}", header_group_fmt)
            asset_row += 1
            asset_headers = award_headers['excel']['sim_asset_headers']
            interest_period_note = self.get_interest_period_note()
            for col, title in enumerate(asset_headers):
                header_title = f"{title}\n{interest_period_note}" if col == 8 else title
                asset_sheet.write(asset_row, col, header_title, header_fmt)
            asset_row += 1
            asset_groups = self.get_structure_compensation_grouped_data()
            if not asset_groups:
                asset_sheet.merge_range(asset_row, 0, asset_row, 10, 'No asset/structure data available / परिसम्पत्ति डेटा उपलब्ध नहीं है (Blank)', blank_msg_fmt)
                asset_row += 1
            else:
                for i, group in enumerate(asset_groups, 1):
                    lines = group.get('lines', [])
                    details = (
                        group.get('landowner_display')
                        or group.get('landowner_name', '')
                    )
                    if not group.get('landowner_display'):
                        father = group.get('father_name')
                        if father:
                            details = f"{details}\nपिता/पति: {father}"
                    group_start_row = asset_row
                    group_khasra = ''
                    for idx, asset in enumerate(lines):
                        if idx == 0:
                            group_khasra = asset.get('asset_khasra', '')
                        asset_sheet.write(asset_row, 0, '', cell_center_fmt)
                        asset_sheet.write(asset_row, 1, '', cell_fmt)
                        asset_sheet.write(asset_row, 2, asset.get('asset_khasra', '') if idx == 0 else '', cell_center_fmt)
                        structure_type_code = str(asset.get('structure_type') or '').lower()
                        is_pukka = asset.get('construction_type') == 'pukka'
                        if is_pukka:
                            asset_type_fmt = asset_type_pukka_formats.get(structure_type_code, asset_type_pukka_default)
                        else:
                            asset_type_fmt = asset_type_cell_formats.get(structure_type_code, asset_type_default_fmt)
                        asset_sheet.write(asset_row, 3, f"({asset.get('asset_code', '4')}) {asset.get('asset_type', '')}", asset_type_fmt)
                        asset_sheet.write_number(asset_row, 4, float(asset.get('asset_dimension', 0.0) or 0.0), number_fmt)
                        asset_sheet.write_number(asset_row, 5, float(asset.get('rate_per_sqm', 0.0) or 0.0), money_fmt)
                        asset_sheet.write_number(asset_row, 6, float(asset.get('market_value', 0.0) or 0.0), money_fmt)
                        asset_sheet.write_number(asset_row, 7, float(asset.get('solatium', 0.0) or 0.0), money_fmt)
                        asset_sheet.write_number(asset_row, 8, float(asset.get('interest', 0.0) or 0.0), money_fmt)
                        asset_sheet.write_number(asset_row, 9, float(asset.get('total', 0.0) or 0.0), money_fmt)
                        asset_sheet.write(asset_row, 10, asset.get('remark', ''), cell_fmt)
                        asset_row += 1
                    if len(lines) > 1:
                        asset_sheet.merge_range(group_start_row, 0, asset_row - 1, 0, i, cell_center_fmt)
                        asset_sheet.merge_range(group_start_row, 1, asset_row - 1, 1, details or '', cell_fmt)
                    else:
                        asset_sheet.write(group_start_row, 0, i, cell_center_fmt)
                        asset_sheet.write(group_start_row, 1, details or '', cell_fmt)
                    if len(lines) > 1:
                        asset_sheet.merge_range(group_start_row, 2, asset_row - 1, 2, group_khasra or '', cell_center_fmt)

                    # Check if all assets in group are of the same type
                    all_same_type = len(lines) > 0 and len(set(asset.get('structure_type', '') for asset in lines)) == 1

                    # Only show total if all assets are of the same type
                    if all_same_type:
                        asset_sheet.merge_range(asset_row, 0, asset_row, 1, 'कुल', total_label_fmt)
                        asset_sheet.write_number(asset_row, 2, float(group.get('khasra_count', 0) or 0), total_money_fmt)
                        asset_sheet.write_blank(asset_row, 3, None, total_label_fmt)
                        asset_sheet.write_number(asset_row, 4, float(group.get('asset_dimension', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_blank(asset_row, 5, None, total_label_fmt)
                        asset_sheet.write_number(asset_row, 6, float(group.get('market_value', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_number(asset_row, 7, float(group.get('solatium', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_number(asset_row, 8, float(group.get('interest', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_number(asset_row, 9, float(group.get('total', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_blank(asset_row, 10, None, total_label_fmt)
                    else:
                        # Mixed asset types: keep rupee totals, mark non-comparable/unit columns as NA.
                        asset_sheet.merge_range(asset_row, 0, asset_row, 1, 'कुल', total_label_fmt)
                        asset_sheet.write_number(asset_row, 2, float(group.get('khasra_count', 0) or 0), total_money_fmt)
                        asset_sheet.write(asset_row, 3, 'NA', total_label_fmt)
                        asset_sheet.write(asset_row, 4, 'NA', total_label_fmt)
                        asset_sheet.write(asset_row, 5, 'NA', total_label_fmt)
                        asset_sheet.write_number(asset_row, 6, float(group.get('market_value', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_number(asset_row, 7, float(group.get('solatium', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_number(asset_row, 8, float(group.get('interest', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write_number(asset_row, 9, float(group.get('total', 0.0) or 0.0), total_money_fmt)
                        asset_sheet.write(asset_row, 10, 'NA', total_label_fmt)
                    asset_row += 1

        if show_tree:
            # TREE TAB (13 columns — पत्रक भाग-1 ग)
            tree_col_widths = [4, 22, 10, 16, 8, 8, 10, 11, 11, 11, 11, 11, 14]
            _setup_sheet(tree_sheet, tree_col_widths, 4)
            tree_row = 0
            tree_last_col = 12
            tree_sheet.merge_range(tree_row, 0, tree_row, tree_last_col, 'वृक्षों का मुआवजा पत्रक', title_fmt)
            tree_row += 1
            tree_sheet.merge_range(tree_row, 0, tree_row, tree_last_col, subtitle, subtitle_fmt)
            tree_row += 2
            tree_sheet.merge_range(
                tree_row, 0, tree_row, tree_last_col,
                f"{award_headers['sections']['tree_sheet_label']} - {award_headers['sections']['tree_title']}",
                header_group_fmt
            )
            tree_row += 1
            tree_headers = award_headers['excel']['sim_tree_headers']
            interest_period_note = self.get_interest_period_note()
            for col, title in enumerate(tree_headers):
                header_title = f"{title}\n{interest_period_note}" if col == 10 else title
                tree_sheet.write(tree_row, col, header_title, header_fmt)
            tree_row += 1
            tree_groups = self.get_tree_compensation_grouped_data()
            if not tree_groups:
                tree_sheet.merge_range(
                    tree_row, 0, tree_row, tree_last_col,
                    'No tree data available / वृक्ष डेटा उपलब्ध नहीं है (Blank)', blank_msg_fmt
                )
                tree_row += 1
            else:
                for i, group in enumerate(tree_groups, 1):
                    lines = group.get('lines', [])
                    details = (
                        group.get('landowner_display')
                        or group.get('landowner_name', '')
                    )
                    if not group.get('landowner_display'):
                        father = group.get('father_name')
                        if father:
                            details = f"{details}\nपिता/पति: {father}"
                    group_start_row = tree_row
                    group_khasra = ''
                    for idx, tree in enumerate(lines):
                        if idx == 0:
                            group_khasra = tree.get('tree_khasra', tree.get('khasra', ''))
                        mulya = float(tree.get('mulya', tree.get('value', 0.0)) or 0.0)
                        kul_r = float(tree.get('kul_rashi', tree.get('value', 0.0)) or 0.0)
                        tree_sheet.write(tree_row, 0, '', cell_center_fmt)
                        tree_sheet.write(tree_row, 1, '', cell_fmt)
                        tree_sheet.write(tree_row, 2, tree.get('tree_khasra', tree.get('khasra', '')) if idx == 0 else '', cell_center_fmt)
                        tree_sheet.write(tree_row, 3, tree.get('tree_type', ''), cell_fmt)
                        tree_sheet.write_number(tree_row, 4, float(tree.get('tree_count', 0.0) or 0.0), number_fmt)
                        tree_sheet.write_number(tree_row, 5, float(tree.get('girth_cm', 0.0) or 0.0), number_fmt)
                        tree_sheet.write_number(tree_row, 6, float(tree.get('rate', 0.0) or 0.0), money_fmt)
                        tree_sheet.write_number(tree_row, 7, mulya, money_fmt)
                        tree_sheet.write_number(tree_row, 8, kul_r, money_fmt)
                        tree_sheet.write_number(tree_row, 9, float(tree.get('solatium', 0.0) or 0.0), money_fmt)
                        tree_sheet.write_number(tree_row, 10, float(tree.get('interest', 0.0) or 0.0), money_fmt)
                        tree_sheet.write_number(tree_row, 11, float(tree.get('total', 0.0) or 0.0), money_fmt)
                        tree_sheet.write(tree_row, 12, tree.get('remark', ''), cell_fmt)
                        tree_row += 1
                    if len(lines) > 1:
                        tree_sheet.merge_range(group_start_row, 0, tree_row - 1, 0, i, cell_center_fmt)
                        tree_sheet.merge_range(group_start_row, 1, tree_row - 1, 1, details or '', cell_fmt)
                    else:
                        tree_sheet.write(group_start_row, 0, i, cell_center_fmt)
                        tree_sheet.write(group_start_row, 1, details or '', cell_fmt)
                    if len(lines) > 1:
                        tree_sheet.merge_range(group_start_row, 2, tree_row - 1, 2, group_khasra or '', cell_center_fmt)

                    tree_sheet.merge_range(tree_row, 0, tree_row, 1, 'कुल', total_label_fmt)
                    tree_sheet.write_blank(tree_row, 2, None, total_label_fmt)
                    tree_sheet.write_blank(tree_row, 3, None, total_label_fmt)
                    tree_sheet.write_number(tree_row, 4, float(group.get('tree_count', 0.0) or 0.0), total_money_fmt)
                    tree_sheet.write_blank(tree_row, 5, None, total_label_fmt)
                    tree_sheet.write_blank(tree_row, 6, None, total_label_fmt)
                    tree_sheet.write_number(tree_row, 7, float(group.get('mulya', group.get('value', 0.0)) or 0.0), total_money_fmt)
                    tree_sheet.write_number(tree_row, 8, float(group.get('kul_rashi', group.get('value', 0.0)) or 0.0), total_money_fmt)
                    tree_sheet.write_number(tree_row, 9, float(group.get('solatium', 0.0) or 0.0), total_money_fmt)
                    tree_sheet.write_number(tree_row, 10, float(group.get('interest', 0.0) or 0.0), total_money_fmt)
                    tree_sheet.write_number(tree_row, 11, float(group.get('total', 0.0) or 0.0), total_money_fmt)
                    tree_sheet.write_blank(tree_row, 12, None, total_label_fmt)
                    tree_row += 1

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        scope_suffix = {
            'all': 'all',
            'land': 'land',
            'asset': 'asset',
            'tree': 'tree',
        }.get(export_scope, 'all')
        attachment = self.env['ir.attachment'].create({
            'name': f"Section23_Award_{self.village_id.name or 'Export'}_{scope_suffix}.xlsx",
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
