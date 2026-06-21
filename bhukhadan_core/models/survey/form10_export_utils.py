# -*- coding: utf-8 -*-
"""
Form 10 Export Utility Functions
Common utilities for PDF and Excel generation that can be used by both web interface and API
"""
from odoo import models, api
from odoo.exceptions import UserError
import io
import re
import logging
from urllib.parse import quote

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False
    _logger.warning("xlsxwriter library not found. Excel export will not be available.")


class Form10ExportUtils(models.AbstractModel):
    """Utility class for Form 10 PDF and Excel export"""
    _name = 'form10.export.utils'
    _description = 'Form 10 Export Utilities'

    @api.model
    def get_surveys_for_export(self, village_id=None, project_id=None, survey_id=None, limit=None):
        """
        Get surveys for export based on filters
        Args:
            village_id: Village ID (optional)
            project_id: Project ID (optional)
            survey_id: Survey ID (optional, takes precedence)
            limit: Maximum number of surveys to return (optional)
        Returns:
            Recordset of surveys
        """
        domain = []
        
        if survey_id:
            # If survey_id is provided, return only that survey
            domain = [('id', '=', survey_id)]
        else:
            # Build domain based on village_id and project_id
            if village_id:
                domain.append(('village_id', '=', village_id))
            if project_id:
                domain.append(('project_id', '=', project_id))
        
        # Search with context to avoid mixin filters
        surveys = self.env['bhu.survey'].sudo().with_context(
            active_test=False,
            bhuarjan_current_project_id=False
        ).search(domain, order='id', limit=limit)
        
        return surveys

    @api.model
    def generate_form10_pdf(self, surveys):
        """
        Generate Form 10 PDF using Odoo's report system
        Args:
            surveys: Recordset of surveys
        Returns:
            bytes: PDF data
        """
        if not surveys:
            raise UserError("No surveys found.")
        
        # Get the Form 10 bulk table report using env.ref (bypasses permission checks)
        try:
            report_action = self.env.ref('bhukhadan_core.action_report_form10_bulk_table').sudo()
            
            if not report_action or not report_action.exists():
                raise UserError("Form 10 report not found. Please contact administrator.")
            
            _logger.info(f"Form 10 PDF: Report action found: {report_action.id}, report_name: {report_action.report_name}")
        except ValueError as ve:
            # env.ref raises ValueError if XML ID not found
            _logger.error(f"Form 10 PDF: Report XML ID not found: {str(ve)}", exc_info=True)
            raise UserError("Form 10 report not found. Please ensure the report is properly installed.")
        except Exception as e:
            _logger.error(f"Form 10 PDF: Error getting report action: {str(e)}", exc_info=True)
            raise UserError(f"Error accessing report: {str(e)}")

        # Convert surveys to list of IDs for PDF rendering
        res_ids = [int(sid) for sid in surveys.ids]
        
        if not res_ids:
            raise UserError("No survey IDs found.")
        
        _logger.info(f"Form 10 PDF: Rendering PDF for {len(res_ids)} surveys")

        # Generate PDF with error handling
        report_name = report_action.report_name
        try:
            pdf_result = report_action.sudo().with_context(
                lang='en_US',
                tz='UTC'
            )._render_qweb_pdf(report_name, res_ids, data={})
        except MemoryError as mem_error:
            _logger.error(f"Form 10 PDF: Memory error during PDF generation: {str(mem_error)}")
            raise UserError("PDF generation failed due to memory constraints. Please reduce the number of surveys or contact administrator.")
        except Exception as render_error:
            _logger.error(f"Form 10 PDF: PDF rendering failed: {str(render_error)}", exc_info=True)
            raise UserError(f"Error generating PDF: {str(render_error)}")

        if not pdf_result:
            raise UserError("Error generating PDF")

        # Extract PDF bytes
        if isinstance(pdf_result, (tuple, list)) and len(pdf_result) > 0:
            pdf_data = pdf_result[0]
        else:
            pdf_data = pdf_result

        if not isinstance(pdf_data, bytes):
            _logger.error(f"Form 10 PDF: Invalid PDF data type: {type(pdf_data)}")
            raise UserError("Invalid PDF data")

        return pdf_data

    @api.model
    def generate_form10_excel(self, surveys):
        """
        Generate Form 10 Excel file (without logo and QR code)
        Args:
            surveys: Recordset of surveys
        Returns:
            bytes: Excel file data
        """
        if not HAS_XLSXWRITER:
            raise UserError("xlsxwriter library is required for Excel export. Please install it: pip install xlsxwriter")
        
        if not surveys:
            raise UserError("No surveys found.")
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Form 10')
        
        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 18
        })
        
        header_info_format = workbook.add_format({
            'bold': True,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 12
        })
        
        header_info_value_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 12
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'valign': 'vcenter',
            'border': 2,
            'text_wrap': True,
            'font_size': 11
        })
        
        cell_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'text_wrap': True,
            'font_size': 11
        })
        
        # Formats for yes/no values
        cell_format_yes = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'text_wrap': True,
            'font_size': 11,
            'font_color': '#00AA00'  # Green color
        })
        
        cell_format_no = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'text_wrap': True,
            'font_size': 11,
            'font_color': '#FF0000'  # Red color
        })
        
        signature_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 12
        })
        
        cell_format_bold = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'text_wrap': True,
            'font_size': 11,
            'bg_color': '#f8f9fa'
        })
        
        first = surveys[0]
        current_row = 0
        
        # Title
        worksheet.merge_range(current_row, 0, current_row, 20, 'भू अर्जन प्रारंभिक सर्वे प्रपत्र', title_format)
        current_row += 1
        current_row += 1  # Spacing
        
        # Header info table (3 rows) - WITHOUT logo and QR code columns
        # Row 1: Project and Department
        worksheet.write(current_row, 0, 'परियोजना का नाम :', header_info_format)
        worksheet.merge_range(current_row, 1, current_row, 8, first.project_id.name or '', header_info_value_format)
        worksheet.write(current_row, 9, 'विभाग का नाम', header_info_format)
        worksheet.merge_range(current_row, 10, current_row, 20, first.department_id.name or '', header_info_value_format)
        current_row += 1
        
        # Row 2: Village and Tehsil
        worksheet.write(current_row, 0, 'ग्राम का नाम', header_info_format)
        worksheet.merge_range(current_row, 1, current_row, 9, first.village_id.name or '', header_info_value_format)
        worksheet.write(current_row, 9, 'तहसील का नाम', header_info_format)
        worksheet.merge_range(current_row, 10, current_row, 20, f"{first.tehsil_id.name or ''} जिला-रायगढ़ (छ.ग.)", header_info_value_format)
        current_row += 1
        
        # Row 3: Survey Date
        survey_date_str = first.survey_date.strftime('%d/%m/%Y') if first.survey_date else ''
        worksheet.write(current_row, 0, 'सर्वे दिनाँक', header_info_format)
        worksheet.merge_range(current_row, 1, current_row, 20, survey_date_str, header_info_value_format)
        current_row += 1
        current_row += 1  # Spacing
        
        # Table headers (2 rows - matching PDF structure)
        # First header row
        worksheet.write(current_row, 0, 'क्र.', header_format)
        worksheet.write(current_row, 1, 'प्रभावित खसरा क्रमांक', header_format)
        worksheet.write(current_row, 2, 'कुल रकबा (हे.में.)', header_format)
        worksheet.write(current_row, 3, 'अर्जन हेतु प्रस्तावित क्षेत्रफल (हेक्टेयर)', header_format)
        worksheet.write(current_row, 4, 'भूमिस्वामी का नाम', header_format)
        worksheet.merge_range(current_row, 5, current_row, 8, 'भूमि का प्रकार', header_format)
        worksheet.merge_range(current_row, 9, current_row, 11, 'भूमि पर स्थित वृक्ष की संख्या (प्रजातिवार)', header_format)
        worksheet.merge_range(current_row, 12, current_row, 20, 'भूमि पर स्थित परिसंपत्तियों का विवरण / सर्वे अतिरिक्त विवरण', header_format)
        current_row += 1
        
        # Second header row
        worksheet.write(current_row, 0, '', header_format)  # Skip first 4 columns (merged above)
        worksheet.write(current_row, 1, '', header_format)
        worksheet.write(current_row, 2, '', header_format)
        worksheet.write(current_row, 3, '', header_format)
        worksheet.write(current_row, 4, '', header_format)
        worksheet.write(current_row, 5, 'एक फसली', header_format)
        worksheet.write(current_row, 6, 'दो फसली', header_format)
        worksheet.write(current_row, 7, 'सिंचित', header_format)
        worksheet.write(current_row, 8, 'असिंचित', header_format)
        worksheet.write(current_row, 9, 'अविकसित', header_format)
        worksheet.write(current_row, 10, 'अर्द्ध विकसित', header_format)
        worksheet.write(current_row, 11, 'पूर्ण विकसित', header_format)
        worksheet.write(current_row, 12, 'मकान (कच्चा/पक्का) क्षेत्रफल वर्गफुट में', header_format)
        worksheet.write(current_row, 13, 'शेड (क्षेत्रफल वर्गफुट में)', header_format)
        worksheet.write(current_row, 14, 'कुँआ (कच्चा/पक्का) (हाँ/नहीं)', header_format)
        worksheet.write(current_row, 15, 'ट्यूबवेल / सम्बमर्शिबल पम्प फिटिंग सहित (हाँ/नहीं)', header_format)
        worksheet.write(current_row, 16, 'तालाब (हाँ/नहीं)', header_format)
        worksheet.write(current_row, 17, 'रिमार्क', header_format)
        worksheet.write(current_row, 18, 'सर्वे प्रकार', header_format)
        worksheet.write(current_row, 19, 'मुख्य मार्ग से दूरी (मीटर)', header_format)
        worksheet.write(current_row, 20, 'पड़ती भूमि (हाँ/नहीं)', header_format)
        current_row += 1
        
        # Data rows
        total_area_sum = 0.0
        total_acquired_area_sum = 0.0
        
        for idx, survey in enumerate(surveys):
            serial_num = idx + 1
            
            # Get landowner names (sudo: rows are exactly those on this survey; avoids read ACL
            # on bhu.landowner when project/district data is out of sync for SDM/Tehsildar)
            owner_names = []
            counter = 1
            for lo in survey.landowner_ids.sudo():
                name = lo.name or ''
                if lo.father_name:
                    name += f" पिता {lo.father_name}"
                elif lo.spouse_name:
                    name += f" पति {lo.spouse_name}"
                owner_names.append(f"{counter}. {name}")
                counter += 1
            owner_str = "\n".join(owner_names) if owner_names else "नहीं"
            
            # Well type with count
            well_str = "नहीं"
            if survey.has_well == 'yes':
                well_count = survey.well_count or 1
                if survey.well_type == 'kaccha':
                    well_str = f"हाँ-कच्चा ({well_count})" if well_count > 1 else "हाँ-कच्चा"
                elif survey.well_type == 'pakka':
                    well_str = f"हाँ-पक्का ({well_count})" if well_count > 1 else "हाँ-पक्का"
                else:
                    well_str = f"हाँ ({well_count})" if well_count > 1 else "हाँ"
            
            # House type - check has_house first
            house_str = "नहीं"
            if survey.has_house == 'yes' and survey.house_type and survey.house_area:
                house_type_str = "पक्का" if survey.house_type == 'pakka' else ("कच्चा" if survey.house_type == 'kaccha' else survey.house_type)
                house_str = f"{house_type_str} / {survey.house_area} वर्गफुट"
            
            # Tree details by development stage (matching PDF structure)
            # ALL trees (both fruit-bearing and non-fruit-bearing) are categorized by development_stage
            undeveloped_trees = []
            semi_developed_trees = []
            fully_developed_trees = []
            
            if survey.tree_line_ids:
                for tree_line in survey.tree_line_ids:
                    tree_name = tree_line.tree_master_id.name if tree_line.tree_master_id else ''
                    quantity = tree_line.quantity or 0
                    development_stage = tree_line.development_stage
                    
                    if quantity > 0 and development_stage:
                        # All trees are categorized by their development_stage, regardless of tree_type
                        if development_stage == 'undeveloped':
                            undeveloped_trees.append(f"{tree_name} - {quantity}")
                        elif development_stage == 'semi_developed':
                            semi_developed_trees.append(f"{tree_name} - {quantity}")
                        elif development_stage == 'fully_developed':
                            fully_developed_trees.append(f"{tree_name} - {quantity}")
            
            undeveloped_str = "\n".join(undeveloped_trees) if undeveloped_trees else "नहीं"
            semi_developed_str = "\n".join(semi_developed_trees) if semi_developed_trees else "नहीं"
            fully_developed_str = "\n".join(fully_developed_trees) if fully_developed_trees else "नहीं"
            
            # Survey type / distance / fallow
            survey_type_str = 'ग्रामीण' if survey.survey_type == 'rural' else ('शहरी' if survey.survey_type == 'urban' else 'नहीं')
            distance_str = f"{round(survey.distance_from_main_road, 2)}" if survey.distance_from_main_road is not None else "नहीं"
            is_fallow = bool(survey.crop_type_id and (survey.crop_type_id.code == 'FALLOW' or 'पड़ती' in (survey.crop_type_id.name or '')))
            fallow_str = "हाँ" if is_fallow else "नहीं"

            # Remarks
            remarks_parts = []
            if survey.has_traded_land == 'yes' and survey.traded_land_area:
                remarks_parts.append(f"व्यपवर्तित-{survey.traded_land_area} हेक्टेयर")
            if is_fallow:
                remarks_parts.append("पड़ती भूमि")
            if survey.remarks:
                remarks_parts.append(survey.remarks)
            remarks_str = "\n".join(remarks_parts) if remarks_parts else "नहीं"
            
            data = [
                serial_num,
                survey.khasra_number or "नहीं",
                survey.total_area or 0,
                survey.acquired_area or 0,
                owner_str,
                "हाँ" if survey.is_single_crop else "नहीं",
                "हाँ" if survey.is_double_crop else "नहीं",
                "हाँ" if survey.is_irrigated else "नहीं",
                "हाँ" if survey.is_unirrigated else "नहीं",
                undeveloped_str,
                semi_developed_str,
                fully_developed_str,
                house_str,
                f"{survey.shed_area} वर्गफुट" if (survey.has_shed == 'yes' and survey.shed_area) else "नहीं",
                well_str,
                f"हाँ ({survey.tubewell_count or 1})" if (survey.has_tubewell == 'yes' and (survey.tubewell_count or 1) > 1) else ("हाँ" if survey.has_tubewell == 'yes' else "नहीं"),
                "हाँ" if survey.has_pond == 'yes' else "नहीं",
                remarks_str,
                survey_type_str,
                distance_str,
                fallow_str,
            ]
            
            # Write data with conditional formatting for yes/no values
            for col, value in enumerate(data):
                # Determine format based on value
                if isinstance(value, str):
                    value_stripped = value.strip()
                    # Check if value is exactly "हाँ" or starts with "हाँ" (for values like "हाँ-कच्चा")
                    if value_stripped == "हाँ" or value_stripped.startswith("हाँ"):
                        # Yes value - use green
                        format_to_use = cell_format_yes
                    elif value_stripped == "नहीं" or "नहीं" in value_stripped:
                        # No value - use red
                        format_to_use = cell_format_no
                    else:
                        # Default format for other values
                        format_to_use = cell_format
                else:
                    # Non-string values (numbers) use default format
                    format_to_use = cell_format
                
                worksheet.write(current_row, col, value, format_to_use)
            
            # Accumulate totals
            total_area_sum += survey.total_area or 0.0
            total_acquired_area_sum += survey.acquired_area or 0.0
            
            current_row += 1
        
        # Total Row
        worksheet.merge_range(current_row, 0, current_row, 1, 'कुल योग', cell_format_bold)
        worksheet.write(current_row, 2, round(total_area_sum, 4), cell_format_bold)
        worksheet.write(current_row, 3, round(total_acquired_area_sum, 4), cell_format_bold)
        for col in range(4, 21):
             worksheet.write(current_row, col, '', cell_format_bold)
        current_row += 1
        
        # Signature section at the end
        current_row += 1  # Spacing
        
        # Signature headers
        worksheet.write(current_row, 0, '(हस्ताक्षर)', signature_format)
        worksheet.merge_range(current_row, 1, current_row, 4, 'अपेक्षक निकाय के अधिकृत प्रतिनिधि', signature_format)
        worksheet.write(current_row, 5, '(हस्ताक्षर)', signature_format)
        worksheet.merge_range(current_row, 6, current_row, 9, 'तहसीलदार', signature_format)
        worksheet.write(current_row, 10, '(हस्ताक्षर)', signature_format)
        worksheet.merge_range(current_row, 11, current_row, 14, 'नायब तहसीलदार', signature_format)
        worksheet.write(current_row, 15, '(हस्ताक्षर)', signature_format)
        worksheet.merge_range(current_row, 16, current_row, 17, 'राजस्व निरीक्षक', signature_format)
        current_row += 1
        
        # Signature details
        worksheet.merge_range(current_row, 0, current_row, 4, 'नाम -', signature_format)
        worksheet.write(current_row, 5, 'पदनाम', signature_format)
        worksheet.merge_range(current_row, 6, current_row, 9, 'नाम -', signature_format)
        worksheet.merge_range(current_row, 10, current_row, 14, 'नाम -', signature_format)
        worksheet.merge_range(current_row, 15, current_row, 16, 'नाम-', signature_format)
        worksheet.write(current_row, 17, 'रा.नि.मं.', signature_format)
        current_row += 1
        
        # Set column widths
        worksheet.set_column(0, 0, 5)   # Serial
        worksheet.set_column(1, 1, 20)  # Khasra
        worksheet.set_column(2, 3, 15)  # Areas
        worksheet.set_column(4, 4, 30)  # Landowners
        worksheet.set_column(5, 8, 12)  # Land type columns
        worksheet.set_column(9, 11, 15)  # Tree columns
        worksheet.set_column(12, 17, 15)  # Asset + remarks columns
        worksheet.set_column(18, 20, 14)  # Survey type / distance / fallow
        
        workbook.close()
        output.seek(0)
        return output.read()

    @api.model
    def sanitize_filename(self, name, max_length=80):
        """
        Make a string safe for use in file names. Keeps Unicode (e.g. Hindi/Devanagari);
        only strips characters that are invalid in paths on common OSes.
        """
        if name is None:
            return 'Unknown'
        name = str(name).strip()
        if not name:
            return 'Unknown'
        # Remove characters invalid in file names (Windows + Unix)
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '', name)
        name = re.sub(r'\s+', '_', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('._')
        if not name:
            return 'Unknown'
        return name[:max_length]

    @api.model
    def generate_form10_filename(self, surveys, file_extension='pdf', project_name=None, village_name=None):
        """
        Build Form10_<project>_<village>.<ext> for PDF, Excel, and CSV.
        Names default from the first survey; optional overrides (e.g. from the wizard) win.
        """
        if not surveys:
            return f"Form10_Unknown.{file_extension}"

        first = surveys[0]
        if project_name is None:
            project_name = first.project_id.name if first.project_id else None
        if village_name is None:
            village_name = first.village_id.name if first.village_id else None
        if not project_name and first.project_id:
            project_name = 'Project_%s' % first.project_id.id
        elif not project_name:
            project_name = 'Project'
        if not village_name and first.village_id:
            village_name = 'Village_%s' % first.village_id.id
        elif not village_name:
            village_name = 'Village'

        p = self.sanitize_filename(project_name)
        v = self.sanitize_filename(village_name)
        return 'Form10_%s_%s.%s' % (p, v, file_extension)

    @api.model
    def content_disposition_attachment(self, filename, ascii_fallback='Form10_Export.pdf'):
        """
        Build a Content-Disposition value safe for WSGI (header values are encoded as
        latin-1). Non–Latin-1 names use RFC 5987 ``filename*``; browsers still get the
        full Unicode name for Save As.
        """
        if not filename:
            filename = ascii_fallback
        # Short ASCII/Latin-1 name for old clients; must be header-safe
        try:
            af = (ascii_fallback or 'export.pdf')[:200]
            af.encode('latin-1')
        except UnicodeEncodeError:
            af = 'export.pdf'

        def _esc_quoted(s):
            return s.replace('\\', '\\\\').replace('"', '\\"')

        try:
            filename.encode('latin-1')
        except UnicodeEncodeError:
            return 'attachment; filename="%s"; filename*=UTF-8\'\'%s' % (
                _esc_quoted(af),
                quote(filename, safe=''),
            )
        return 'attachment; filename="%s"' % _esc_quoted(filename)

