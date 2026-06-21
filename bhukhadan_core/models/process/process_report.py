# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import io
import base64
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False
    _logger.warning("xlsxwriter library not found. Excel export will not be available.")


class ProcessReport(models.TransientModel):
    """Process Report - Aggregated view of all process notifications"""
    _name = 'bhu.process.report'
    _description = 'Process Report'
    _order = 'serial_number'

    serial_number = fields.Integer(string='S.No. / स.क्र.', readonly=True)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', readonly=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', readonly=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील', readonly=True)
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', readonly=True)
    total_khasras = fields.Integer(string='Total Khasras / ख. नं. कूल प्रभावित', readonly=True)
    total_area = fields.Float(string='Total Proposed Area (Hectares) / कुल अर्जन हेतु प्रस्तवित रकबा', 
                              digits=(16, 4), readonly=True)
    status = fields.Char(string='Status / स्टेटस', readonly=True)
    status_mark = fields.Char(string='Red or Green Mark / रेड या ग्रीन मार्क', readonly=True)
    section_type = fields.Selection([
        ('sec4', 'Section 4'),
        ('sec11', 'Section 11'),
        ('sec19', 'Section 19'),
        ('sec21', 'Section 21'),
        ('sec23', 'Section 23'),
        ('form10', 'Form 10'),
        ('sia_order', 'SIA Order'),
        ('sia_proposal', 'SIA Proposal'),
    ], string='Section Type', readonly=True)


class ProcessReportWizard(models.TransientModel):
    """Wizard for filtering Process Report"""
    _name = 'bhu.process.report.wizard'
    _description = 'Process Report Wizard'
    _inherit = ['bhu.process.report.pdf.download.mixin', 'bhu.process.report.signed.docs.download.mixin']

    department_id = fields.Many2one('bhu.department', string='Department / विभाग')
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', 
                                domain="[('department_id', '=', department_id)]")
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम')
    allowed_village_ids = fields.Many2many(
        'bhu.village',
        string='Allowed Villages',
        compute='_compute_allowed_village_ids',
        store=False,
    )
    status_type = fields.Selection([
        ('sec4', 'Sec-4'),
        ('sec11', 'Sec-11'),
        ('sec19', 'Sec-19'),
        ('sec21', 'Sec-21'),
        ('sec23', 'Sec-23'),
        ('form10', 'Form-10'),
        ('sia_order', 'SIA Order'),
        ('sia_proposal', 'SIA Proposal'),
        ('all', 'All'),
    ], string='Status Wise / स्टेटस वाइज', default='all')
    
    @api.depends('project_id')
    def _compute_allowed_village_ids(self):
        """Compute allowed villages based on project"""
        for wizard in self:
            if wizard.project_id and wizard.project_id.village_ids:
                wizard.allowed_village_ids = [(6, 0, wizard.project_id.village_ids.ids)]
            else:
                wizard.allowed_village_ids = [(6, 0, [])]

    @api.onchange('department_id')
    def _onchange_department_id(self):
        """Reset project and village when department changes"""
        self.project_id = False
        self.village_id = False
        if self.department_id:
            return {'domain': {'project_id': [('department_id', '=', self.department_id.id)]}}
        else:
            return {'domain': {'project_id': []}}

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain to only show project villages"""
        self.village_id = False
        if self.project_id and self.project_id.village_ids:
            return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        else:
            return {'domain': {'village_id': [('id', '=', False)]}}

    def action_generate_report(self):
        """Generate process report based on filters"""
        self.ensure_one()
        
        # Build domain for filtering
        # Note: department_id is on project, not directly on notifications
        project_domain = []
        if self.department_id:
            project_domain.append(('department_id', '=', self.department_id.id))
        if self.project_id:
            project_domain.append(('id', '=', self.project_id.id))
        
        # Get filtered project IDs
        project_ids = self.env['bhu.project'].search(project_domain).ids if project_domain else []
        
        # Build notification domain
        domain = []
        if project_ids:
            domain.append(('project_id', 'in', project_ids))
        elif self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        if self.village_id:
            domain.append(('village_id', '=', self.village_id.id))
        
        # Clear existing report records (use sudo for transient model cleanup)
        self.env['bhu.process.report'].sudo().search([]).unlink()
        
        report_records = []
        serial = 1
        
        # Section 4 Notifications
        if self.status_type in ('sec4', 'all'):
            section4_domain = domain.copy()
            section4_records = self.env['bhu.section4.notification'].search(section4_domain)
            for record in section4_records:
                # Get total khasras and area from surveys
                surveys = self.env['bhu.survey'].search([
                    ('project_id', '=', record.project_id.id),
                    ('village_id', '=', record.village_id.id),
                    ('khasra_number', '!=', False),
                ])
                unique_khasras = len(set(surveys.mapped('khasra_number')))
                total_area = sum(surveys.mapped('acquired_area'))
                
                # Determine status mark (green if approved, red otherwise)
                status_mark = 'Green' if record.state == 'approved' else 'Red'
                
                report_records.append({
                    'serial_number': serial,
                    'department_id': record.project_id.department_id.id if record.project_id.department_id else False,
                    'project_id': record.project_id.id,
                    'tehsil_id': record.tehsil_id.id if record.tehsil_id else False,
                    'village_id': record.village_id.id,
                    'total_khasras': unique_khasras,
                    'total_area': total_area,
                    'status': dict(record._fields['state'].selection).get(record.state, record.state),
                    'status_mark': status_mark,
                    'section_type': 'sec4',
                })
                serial += 1
        
        # Section 11 Preliminary Reports
        if self.status_type in ('sec11', 'all'):
            section11_domain = domain.copy()
            section11_records = self.env['bhu.section11.preliminary.report'].search(section11_domain)
            for record in section11_records:
                # Get total khasras and area from land parcels
                unique_khasras = len(set(record.land_parcel_ids.mapped('khasra_number'))) if record.land_parcel_ids else 0
                total_area = sum(record.land_parcel_ids.mapped('area_in_hectares')) if record.land_parcel_ids else 0.0
                
                status_mark = 'Green' if record.state == 'approved' else 'Red'
                
                report_records.append({
                    'serial_number': serial,
                    'department_id': record.project_id.department_id.id if record.project_id and record.project_id.department_id else False,
                    'project_id': record.project_id.id if record.project_id else False,
                    'tehsil_id': record.village_id.tehsil_id.id if record.village_id and record.village_id.tehsil_id else False,
                    'village_id': record.village_id.id if record.village_id else False,
                    'total_khasras': unique_khasras,
                    'total_area': total_area,
                    'status': dict(record._fields['state'].selection).get(record.state, record.state),
                    'status_mark': status_mark,
                    'section_type': 'sec11',
                })
                serial += 1
        
        # Section 19 Notifications
        if self.status_type in ('sec19', 'all'):
            section19_domain = domain.copy()
            section19_records = self.env['bhu.section19.notification'].search(section19_domain)
            for record in section19_records:
                # Surveys (approved/locked) — no land_parcel_ids on this model
                surveys_data = record._get_approved_surveys_data()
                unique_khasras = len(surveys_data)
                total_area = record._get_total_area_from_surveys()
                
                status_mark = 'Green' if record.state == 'approved' else 'Red'
                
                report_records.append({
                    'serial_number': serial,
                    'department_id': record.project_id.department_id.id if record.project_id and record.project_id.department_id else False,
                    'project_id': record.project_id.id if record.project_id else False,
                    'tehsil_id': record.tehsil_id.id if record.tehsil_id else False,
                    'village_id': record.village_id.id if record.village_id else False,
                    'total_khasras': unique_khasras,
                    'total_area': total_area,
                    'status': dict(record._fields['state'].selection).get(record.state, record.state),
                    'status_mark': status_mark,
                    'section_type': 'sec19',
                })
                serial += 1

        # SIA Teams (Order and Proposal)
        if self.status_type in ('sia_order', 'sia_proposal', 'all'):
            sia_domain = []
            if project_ids:
                sia_domain.append(('project_id', 'in', project_ids))
            elif self.project_id:
                sia_domain.append(('project_id', '=', self.project_id.id))
            
            sia_teams = self.env['bhu.sia.team'].search(sia_domain)
            
            for team in sia_teams:
                # Add SIA Order if selected
                if self.status_type in ('sia_order', 'all'):
                    report_records.append({
                        'serial_number': serial,
                        'department_id': team.project_id.department_id.id if team.project_id.department_id else False,
                        'project_id': team.project_id.id,
                        'tehsil_id': team.tehsil_ids[0].id if team.tehsil_ids else False,
                        # Use first village or empty if multiple/none, as SIA team is project level
                        'village_id': team.village_ids[0].id if team.village_ids else False,
                        'total_khasras': team.total_khasras_count,
                        'total_area': team.total_area_acquired,
                        'status': dict(team._fields['state'].selection).get(team.state, team.state),
                        'status_mark': 'Green' if team.state == 'approved' else 'Red',
                        'section_type': 'sia_order',
                    })
                    serial += 1
                
                # Add SIA Proposal if selected
                if self.status_type in ('sia_proposal', 'all'):
                    report_records.append({
                        'serial_number': serial,
                        'department_id': team.project_id.department_id.id if team.project_id.department_id else False,
                        'project_id': team.project_id.id,
                        'tehsil_id': team.tehsil_ids[0].id if team.tehsil_ids else False,
                        'village_id': team.village_ids[0].id if team.village_ids else False,
                        'total_khasras': team.total_khasras_count,
                        'total_area': team.total_area_acquired,
                        'status': dict(team._fields['state'].selection).get(team.state, team.state),
                        'status_mark': 'Green' if team.state == 'approved' else 'Red',
                        'section_type': 'sia_proposal',
                    })
                    serial += 1
        
        # Create report records
        if report_records:
            self.env['bhu.process.report'].create(report_records)
        
        # Open report view
        return {
            'type': 'ir.actions.act_window',
            'name': _('Process Report'),
            'res_model': 'bhu.process.report',
            'view_mode': 'list',
            'target': 'current',
            'context': {'search_default_group_by_section': 1},
        }

    def action_export_excel(self):
        """Export process report to Excel"""
        self.ensure_one()
        
        if not HAS_XLSXWRITER:
            raise ValidationError(_('xlsxwriter library is not installed. Please install it to export Excel files.'))
        
        # Generate report first
        self.action_generate_report()
        
        # Get report records
        report_records = self.env['bhu.process.report'].search([])
        
        # Create Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Process Report')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#FFFF99',  # Light yellow
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
        })
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
        })
        
        # Write headers
        headers = [
            'S.No. / स.क्र.',
            'Department / विभाग',
            'Project / परियोजना',
            'Tehsil / तहसील',
            'Village / ग्राम',
            'Total Khasras / ख. नं. कूल प्रभावित',
            'Total Proposed Area (Hectares) / कुल अर्जन हेतु प्रस्तवित रकबा',
            'Status / स्टेटस',
            'Red or Green Mark / रेड या ग्रीन मार्क',
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Write data
        row = 1
        for record in report_records:
            worksheet.write(row, 0, record.serial_number, cell_format)
            worksheet.write(row, 1, record.department_id.name if record.department_id else '', cell_format)
            worksheet.write(row, 2, record.project_id.name if record.project_id else '', cell_format)
            worksheet.write(row, 3, record.tehsil_id.name if record.tehsil_id else '', cell_format)
            worksheet.write(row, 4, record.village_id.name if record.village_id else '', cell_format)
            worksheet.write(row, 5, record.total_khasras, cell_format)
            worksheet.write(row, 6, record.total_area, number_format)
            worksheet.write(row, 7, record.status or '', cell_format)
            worksheet.write(row, 8, record.status_mark or '', cell_format)
            row += 1
        
        # Set column widths
        worksheet.set_column(0, 0, 10)  # Serial Number
        worksheet.set_column(1, 1, 20)  # Department
        worksheet.set_column(2, 2, 25)  # Project
        worksheet.set_column(3, 3, 20)  # Tehsil
        worksheet.set_column(4, 4, 20)  # Village
        worksheet.set_column(5, 5, 25)  # Total Khasras
        worksheet.set_column(6, 6, 30)  # Total Area
        worksheet.set_column(7, 7, 20)  # Status
        worksheet.set_column(8, 8, 25)  # Status Mark
        
        workbook.close()
        output.seek(0)
        
        # Create attachment
        excel_data = base64.b64encode(output.read())
        filename = f'Process_Report_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': excel_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'bhu.process.report.wizard',
            'res_id': self.id,
        })
        
        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _get_filtered_records(self):
        """Get filtered records based on wizard filters"""
        self.ensure_one()
        
        # Build domain for filtering
        project_domain = []
        if self.department_id:
            project_domain.append(('department_id', '=', self.department_id.id))
        if self.project_id:
            project_domain.append(('id', '=', self.project_id.id))
        
        # Get filtered project IDs
        project_ids = self.env['bhu.project'].search(project_domain).ids if project_domain else []
        
        # Build notification domain
        domain = []
        if project_ids:
            domain.append(('project_id', 'in', project_ids))
        elif self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        if self.village_id:
            domain.append(('village_id', '=', self.village_id.id))
        
        records = {
            'section4': [],
            'section11': [],
            'section19': [],
            'section21': [],
            'sia_teams': [],  # SIA teams (project level)
            'expert_committees': [],  # Expert Committee reports (project level)
            'form10': [],  # Will store village IDs for Form 10
        }
        
        # Section 4 Notifications
        if self.status_type in ('sec4', 'all'):
            section4_domain = domain.copy()
            records['section4'] = self.env['bhu.section4.notification'].search(section4_domain)
        
        # Section 11 Preliminary Reports
        if self.status_type in ('sec11', 'all'):
            section11_domain = domain.copy()
            records['section11'] = self.env['bhu.section11.preliminary.report'].search(section11_domain)
        
        # Section 19 Notifications
        if self.status_type in ('sec19', 'all'):
            section19_domain = domain.copy()
            records['section19'] = self.env['bhu.section19.notification'].search(section19_domain)
        
        # Section 21 Notifications
        if self.status_type in ('sec21', 'all'):
            section21_domain = domain.copy()
            records['section21'] = self.env['bhu.section21.notification'].search(section21_domain)
        
        # SIA Teams (project level - filter by project only)
        # Include SIA teams if status is All, SIA Order, or SIA Proposal
        records['sia_teams'] = []
        if self.status_type in ('all', 'sia_order', 'sia_proposal'):
            sia_domain = []
            if project_ids:
                sia_domain.append(('project_id', 'in', project_ids))
            elif self.project_id:
                sia_domain.append(('project_id', '=', self.project_id.id))
            records['sia_teams'] = self.env['bhu.sia.team'].search(sia_domain) if sia_domain else []
        
        # Expert Committee Reports (project level - filter by project only)
        # Always include Expert Committee reports when project is selected (they're project-level documents)
        expert_domain = []
        if project_ids:
            expert_domain.append(('project_id', 'in', project_ids))
        elif self.project_id:
            expert_domain.append(('project_id', '=', self.project_id.id))
        records['expert_committees'] = self.env['bhu.expert.committee.report'].search(expert_domain) if expert_domain else []
        
        # Form 10 (surveys grouped by village)
        if self.status_type in ('form10', 'all'):
            # Build survey domain
            survey_domain = []
            if project_ids:
                survey_domain.append(('project_id', 'in', project_ids))
            elif self.project_id:
                survey_domain.append(('project_id', '=', self.project_id.id))
            if self.village_id:
                survey_domain.append(('village_id', '=', self.village_id.id))
            
            # Get surveys and group by village
            surveys = self.env['bhu.survey'].search(survey_domain)
            village_ids = list(set(surveys.mapped('village_id.id')))
            records['form10'] = village_ids
        
        return records

