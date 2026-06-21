from odoo import models, fields, api
import io
import xlsxwriter
import base64
from datetime import datetime, date

class BhuKhadanGanttReportWizard(models.TransientModel):
    _name = 'bhuarjan.gantt.report.wizard'
    _description = 'Project Gantt and Status Report'

    project_id = fields.Many2one('bhu.project', string='Project', required=True)

    def action_download_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Project Status')

        # Formats
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        header_format = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#8B4513', 'font_color': 'white', 'border': 1})
        text_format = workbook.add_format({'border': 1})
        date_format = workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        
        # Highlighting formats for "Gantt" visual
        color_formats = {
            'draft': workbook.add_format({'bg_color': '#f0f0f0', 'border': 1}), # Gray
            'submitted': workbook.add_format({'bg_color': '#fff3cd', 'border': 1}), # Yellow
            'approved': workbook.add_format({'bg_color': '#d4edda', 'border': 1}), # Green
            'rejected': workbook.add_format({'bg_color': '#f8d7da', 'border': 1}), # Red
        }

        # Title
        worksheet.merge_range('A1:F1', f"Project Status Report: {self.project_id.name}", title_format)
        worksheet.set_row(0, 30)

        # Headers
        headers = ['Step / Section', 'Status', 'Start Date', 'Last Updated', 'Duration (Days)', 'Completion']
        for col, header in enumerate(headers):
            worksheet.write(2, col, header, header_format)
            worksheet.set_column(col, col, 20)
        
        worksheet.set_column(0, 0, 30) # Section Name wider

        # Data Collection Helper
        def get_section_data(model_name, name, step_num):
            records = self.env[model_name].search([('project_id', '=', self.project_id.id)])
            if not records:
                return [f"{step_num}. {name}", "Not Started", "-", "-", 0, 0]
            
            # Aggregate status
            total = len(records)
            
            # Check if model has state field
            has_state = 'state' in records._fields
            
            if has_state:
                approved = len(records.filtered(lambda r: r.state == 'approved'))
                submitted = len(records.filtered(lambda r: r.state == 'submitted'))
                draft = len(records.filtered(lambda r: r.state == 'draft'))
            else:
                # If no state field, assume completed if records exist (e.g. simple lists)
                approved = total
                submitted = 0
                draft = 0
            
            status = "In Progress"
            if approved == total and total > 0:
                status = "Completed"
            elif total == 0:
                status = "Not Started"
            elif draft == total:
                status = "Draft"
                
            start_date = min(records.mapped('create_date')).date() if records else None
            end_date = max(records.mapped('write_date')).date() if records else None
            
            duration = (end_date - start_date).days if start_date and end_date else 0
            completion = (approved / total * 100) if total > 0 else 0
            
            return [f"{step_num}. {name}", status, start_date, end_date, duration, completion]

        # Sections to iterate
        sections = [
            ('bhu.survey', 'Surveys', '1'),
            ('bhu.sia.team', 'SIA Team', '2'),
            ('bhu.section4.notification', 'Section 4 Notification', '3'),
            ('bhu.expert.committee.report', 'Expert Committee', '4'),
            ('bhu.section11.preliminary.report', 'Section 11 Preliminary', '5'),
            ('bhu.section15.objection', 'Section 15 Objections', '6'),
            ('bhu.section18.rr.scheme', 'R&R Scheme', '7'),
            ('bhu.section19.notification', 'Section 19 Notification', '8'),
            ('bhu.section21.notification', 'Section 21 Notification', '9'),
            ('bhu.section23.award', 'Section 23 Award', '10'),
        ]

        row = 3
        for model, name, step in sections:
            data = get_section_data(model, name, step)
            # Write row
            worksheet.write(row, 0, data[0], text_format)
            
            # Status Color
            status = data[1]
            fmt = text_format
            if status == 'Completed': fmt = color_formats['approved']
            elif status == 'Draft': fmt = color_formats['draft']
            elif status == 'Not Started': fmt = text_format
            else: fmt = color_formats['submitted'] # In Progress
            
            worksheet.write(row, 1, status, fmt)
            
            worksheet.write(row, 2, data[2] if data[2] != '-' else '', date_format)
            worksheet.write(row, 3, data[3] if data[3] != '-' else '', date_format)
            worksheet.write(row, 4, data[4], text_format)
            worksheet.write(row, 5, f"{data[5]:.1f}%", text_format)
            
            # "Gantt" bar representation in next columns?
            # Let's keep it simple table for now as requested "nice gantt chart" in Excel usually implies visual bars 
            # which are hard to align with rows without graph objects. 
            # A "Conditional Formatting" bar in the Completion column is nice.
            row += 1

        # Add a simple chart using xlsxwriter chart class
        chart = workbook.add_chart({'type': 'bar'})
        chart.add_series({
            'name': 'Duration (Days)',
            'categories': ['Project Status', 3, 0, row-1, 0], # Section Names
            'values':     ['Project Status', 3, 4, row-1, 4], # Durations
            'fill':       {'color': '#8B4513'},
        })
        chart.set_title({'name': 'Project Timeline (Days per Section)'})
        chart.set_x_axis({'name': 'Days'})
        chart.set_y_axis({'name': 'Section'})
        chart.set_style(11) 
        
        worksheet.insert_chart('G3', chart, {'x_scale': 1.5, 'y_scale': 1.5})

        workbook.close()
        output.seek(0)
        file_content = base64.b64encode(output.read())
        output.close()

        attachment = self.env['ir.attachment'].create({
            'name': f'Project_Report_{self.project_id.name}.xlsx',
            'type': 'binary',
            'datas': file_content,
            'res_model': 'bhuarjan.gantt.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
