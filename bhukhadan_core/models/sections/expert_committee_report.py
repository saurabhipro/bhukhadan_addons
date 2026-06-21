# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import uuid
import logging

_logger = logging.getLogger(__name__)

class ExpertCommitteeReport(models.Model):
    _name = 'bhu.expert.committee.report'
    _description = 'Expert Committee Report / विशेषज्ञ समिति रिपोर्ट'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin', 'bhu.qr.code.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Report Name / रिपोर्ट का नाम', required=True, default='New', tracking=True)
    expert_committee_uuid = fields.Char(string='Expert Committee UUID', readonly=True, copy=False, index=True,
                                        help='Unique identifier for QR code download')
    # Kramank (Reference Number)
    kramank = fields.Char(string='Kramank / क्रमांक', required=False, tracking=True,
                          help='Reference number to be displayed in the report (optional)')
    # Location fields inherited from bhu.process.workflow.mixin
    # Override project_id to add default and domain
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True)
    
    # Override village_id to make it Many2many for Expert Committee (multiple villages)
    # Expert Committee can cover multiple villages, unlike other sections
    village_id = fields.Many2one(required=False)  # Make single village optional
    village_ids = fields.Many2many('bhu.village', string='Affected Villages / प्रभावित ग्राम', tracking=True,
                                   help='Select affected villages for this report')
    
    requiring_body_id = fields.Many2one('bhu.department', string='Requiring Body / अपेक्षक निकाय', required=True, tracking=True,
                                       help='Select the requiring body/department', related="project_id.department_id")
    
    # Computed fields from Form 10 surveys
    total_khasras_count = fields.Integer(string='Total Khasras Count / कुल खसरा संख्या',
                                         compute='_compute_project_statistics', store=False)
    total_area_acquired = fields.Float(string='Total Area Acquired (Hectares) / कुल अर्जित क्षेत्रफल (हेक्टेयर)',
                                       compute='_compute_project_statistics', store=False,
                                       digits=(16, 4))
    
    # Project villages for reference (read-only)
    project_village_ids = fields.Many2many('bhu.village', 
                                           string='Project Villages / परियोजना ग्राम',
                                           compute='_compute_project_villages', 
                                           store=False,
                                           help='Villages mapped to the selected project (read-only for reference)')
    
    # Expert Committee Team Members - 4 Sections (One2many lines)
    # (क) Non-Government Social Scientist
    non_govt_social_scientist_line_ids = fields.One2many(
        'bhu.expert.committee.member.line', 
        'expert_committee_id',
        string='Non-Government Social Scientist / गैर शासकीय सामाजिक वैज्ञानिक',
        domain=[('member_type', '=', 'non_govt_social_scientist')],
        context={'default_member_type': 'non_govt_social_scientist'},
        tracking=True)
    
    # (ख) Representatives of Local Bodies
    local_bodies_representative_line_ids = fields.One2many(
        'bhu.expert.committee.member.line',
        'expert_committee_id',
        string='Representatives of Local Bodies / ग्राम पंचायत या नगरीय निकाय के प्रतिनिधि',
        domain=[('member_type', '=', 'local_bodies_representative')],
        context={'default_member_type': 'local_bodies_representative'},
        tracking=True)
    
    # (ग) Resettlement Expert
    resettlement_expert_line_ids = fields.One2many(
        'bhu.expert.committee.member.line',
        'expert_committee_id',
        string='Resettlement Expert / पुनर्व्यवस्थापन संबंधी विशेषज्ञ',
        domain=[('member_type', '=', 'resettlement_expert')],
        context={'default_member_type': 'resettlement_expert'},
        tracking=True)
    
    # (घ) Technical Expert on Project Related Subject
    technical_expert_line_ids = fields.One2many(
        'bhu.expert.committee.member.line',
        'expert_committee_id',
        string='Technical Expert / परियोजना से संबंधित विषय का तकनीकि विशेषज्ञ',
        domain=[('member_type', '=', 'technical_expert')],
        context={'default_member_type': 'technical_expert'},
        tracking=True)
    
    @api.constrains('project_id', 'village_ids')
    def _check_project_village_uniqueness(self):
        """Ensure no overlapping villages for the same project"""
        for record in self:
            if not record.project_id or not record.village_ids:
                continue
            
            # This report covers specific villages. Check if any of these villages are already covered.
            domain = [
                ('project_id', '=', record.project_id.id),
                ('id', '!=', record.id)
            ]
            existing_reports = self.search(domain)
            
            for existing in existing_reports:
                # If existing report has no villages, skip it (allow overlap with "full project" reports as per user request)
                if not existing.village_ids:
                    continue
                
                # Check for overlap
                # intersection of IDs
                overlap = set(record.village_ids.ids) & set(existing.village_ids.ids)
                if overlap:
                    overlapping_villages = self.env['bhu.village'].browse(list(overlap))
                    names = ', '.join(overlapping_villages.mapped('name'))
                    raise ValidationError(_('Expert Committee Report already exists for the following village(s): %s') % names)
    
    @api.depends('project_id', 'project_id.village_ids', 'village_ids')
    def _compute_project_villages(self):
        """Compute villages - show selected villages if any, otherwise show all project villages"""
        for record in self:
            if record.village_ids:
                # Show only selected villages
                record.project_village_ids = record.village_ids
            elif record.project_id and record.project_id.village_ids:
                # If no villages selected, show all project villages
                record.project_village_ids = record.project_id.village_ids
            else:
                record.project_village_ids = False
    
    @api.depends('project_id', 'village_ids')
    def _compute_project_statistics(self):
        """Compute total khasras count and total area acquired from Form 10 surveys"""
        for record in self:
            if record.project_id:
                # If specific villages are selected, use those; otherwise use all project villages
                village_ids = record.village_ids.ids if record.village_ids else record.project_id.village_ids.ids
                
                if village_ids:
                    # Get all surveys for selected villages in this project
                    surveys = self.env['bhu.survey'].search([
                        ('project_id', '=', record.project_id.id),
                        ('village_id', 'in', village_ids),
                        ('khasra_number', '!=', False),
                    ])
                    
                    # Count unique khasra numbers
                    unique_khasras = set(surveys.mapped('khasra_number'))
                    record.total_khasras_count = len(unique_khasras)
                    
                    # Sum acquired area
                    record.total_area_acquired = sum(surveys.mapped('acquired_area'))
                else:
                    record.total_khasras_count = 0
                    record.total_area_acquired = 0.0
            else:
                record.total_khasras_count = 0
                record.total_area_acquired = 0.0
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Auto-populate villages and filter domain based on project selection"""
        # Auto-populate villages with all project villages when project is selected
        if self.project_id and self.project_id.village_ids:
            # Always populate with project villages when project is selected
            self.village_ids = self.project_id.village_ids
        else:
            self.village_ids = False
        
        # Set domain to only show project villages
        if self.project_id and self.project_id.village_ids:
            return {'domain': {'village_ids': [('id', 'in', self.project_id.village_ids.ids)]}}
        else:
            return {'domain': {'village_ids': [('id', '=', False)]}}
    
    # Expert Group Report
    expert_group_report_file = fields.Binary(string='Expert Group Report / विशेषज्ञ समूह रिपोर्ट')
    expert_group_report_filename = fields.Char(string='Expert Group Report Filename')
    
    # Signed document fields (similar to Section 4 Notification)
    signed_document_file = fields.Binary(string='Signed Report / हस्ताक्षरित रिपोर्ट')
    signed_document_filename = fields.Char(string='Signed File Name / हस्ताक्षरित फ़ाइल नाम')
    signed_date = fields.Date(string='Signed Date / हस्ताक्षर दिनांक', tracking=True)
    has_signed_document = fields.Boolean(string='Has Signed Document / हस्ताक्षरित दस्तावेज़ है', 
                                         compute='_compute_has_signed_document', store=True)
    
    # Signatory information
    signatory_name = fields.Char(string='Signatory Name / हस्ताक्षरकर्ता का नाम', tracking=True)
    signatory_designation = fields.Char(string='Signatory Designation / हस्ताक्षरकर्ता का पद', tracking=True)
    
    # State field is inherited from mixin
    
    @api.depends('signed_document_file')
    def _compute_has_signed_document(self):
        for record in self:
            record.has_signed_document = bool(record.signed_document_file)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create records with batch support"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhu.expert.committee.report') or 'New'
            
            # Removed automatic project assignment logic - rely on context or user input
            # This fixes the issue where project defaults to PROJ01 incorrectly

            
            # Check if project is SIA exempt
            # Check if project is SIA exempt - Removed as per user request
            # project_id = vals.get('project_id')
            # if project_id:
            #     project = self.env['bhu.project'].browse(project_id)
            #     if project.is_sia_exempt:
            #         raise ValidationError(_('Expert Group Reports cannot be created for projects that are exempt from Social Impact Assessment.'))
            
            # Generate UUID if not provided
            if not vals.get('expert_committee_uuid'):
                vals['expert_committee_uuid'] = str(uuid.uuid4())
        records = super().create(vals_list)
        return records
    
    def action_mark_signed(self):
        """Mark report as signed"""
        self.ensure_one()
        if not self.signed_document_file:
            raise ValidationError(_('Please upload signed document first.'))
        self.state = 'signed'
        if not self.signed_date:
            self.signed_date = fields.Date.today()
    
    # Workflow methods are inherited from mixin
    # Override action_download_unsigned_file to generate PDF report
    def action_download_unsigned_file(self):
        """Generate and download Expert Committee Proposal PDF/Word (unsigned) - Override mixin"""
        self.ensure_one()
        return {
            'name': _('Download Expert Committee Proposal / विशेषज्ञ समिति प्रस्ताव डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_expert_committee_proposal',
                'default_filename': f'Expert_Committee_Proposal_{self.name}.doc'
            }
        }
    
    def action_download_expert_group_report(self):
        """Download Expert Group Report file"""
        self.ensure_one()
        if not self.expert_group_report_file:
            raise ValidationError(_('Expert Group Report file is not available.'))
        filename = self.expert_group_report_filename or 'expert_group_report.pdf'
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/expert_group_report_file/{filename}?download=true',
            'target': 'self',
        }
    
    def action_download_expert_committee_order(self):
        """Generate and download Expert Committee Approval Order PDF/Word - For Collector"""
        self.ensure_one()
        return {
            'name': _('Download Expert Committee Order / विशेषज्ञ समिति आदेश डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_expert_committee_order',
                'default_filename': f'Expert_Committee_Order_{self.name}.doc'
            }
        }
    
    def action_download_latest_pdf(self):
        """Override mixin method to always download Expert Committee Proposal PDF"""
        self.ensure_one()
        # Always use the proposal report template
        return self.action_download_unsigned_file()
    
    
    def action_create_section11_notification(self):
        """Create Section 11 Preliminary Report from this Expert Committee Report - Creates one per village"""
        self.ensure_one()
        
        if not self.project_id:
            raise ValidationError(_('Please select a project first.'))
        
        if not self.village_ids:
            raise ValidationError(_('Please select at least one village first.'))
        
        # Create a separate Section 11 notification for each village
        created_notifications = []
        skipped_villages = []
        
        for village in self.village_ids:
            # Check if Section 11 already exists for this project and village
            existing = self.env['bhu.section11.preliminary.report'].search([
                ('project_id', '=', self.project_id.id),
                ('village_id', '=', village.id)
            ], limit=1)
            
            if existing:
                skipped_villages.append(village.name)
                continue
            
            # Create new Section 11 Preliminary Report for this village
            section11 = self.env['bhu.section11.preliminary.report'].create({
                'project_id': self.project_id.id,
                'village_id': village.id,
            })
            created_notifications.append(section11)
        
        if not created_notifications:
            # All villages already have Section 11 notifications
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('Section 11 notifications already exist for all selected villages. Skipped: %s') % ', '.join(skipped_villages),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Add message to Expert Committee Report
        message = _('Created %d Section 11 Preliminary Report(s) from this Expert Committee Report.') % len(created_notifications)
        if skipped_villages:
            message += _(' Skipped: %s') % ', '.join(skipped_villages)
        self.message_post(body=message, subtype_xmlid='mail.mt_note')
        
        # Open the created Section 11 reports
        if len(created_notifications) == 1:
            # Open single notification in form view
            return {
                'type': 'ir.actions.act_window',
                'name': _('Section 11 Preliminary Report'),
                'res_model': 'bhu.section11.preliminary.report',
                'res_id': created_notifications[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Open multiple notifications in list view
            return {
                'type': 'ir.actions.act_window',
                'name': _('Section 11 Preliminary Reports'),
                'res_model': 'bhu.section11.preliminary.report',
                'view_mode': 'list,form',
                'domain': [('id', 'in', [n.id for n in created_notifications])],
                'target': 'current',
            }
    
    # action_reject is replaced by action_send_back in mixin
    # action_submit is inherited from mixin
    
    def action_generate_order(self):
        """Generate Expert Committee Order - Opens wizard with current report's project"""
        self.ensure_one()
        return {
            'name': _('Generate Expert Committee Order / विशेषज्ञ समिति आदेश जेनरेट करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhu.expert.committee.order.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
            }
        }
    
    @api.model
    def _generate_missing_uuids(self):
        """Generate UUIDs for existing Expert Committee Reports that don't have one"""
        reports_without_uuid = self.search([('expert_committee_uuid', '=', False)])
        for report in reports_without_uuid:
            report.write({'expert_committee_uuid': str(uuid.uuid4())})
        return len(reports_without_uuid)
    
    # QR code generation is now handled by bhu.qr.code.mixin


class ExpertCommitteeOrderWizard(models.TransientModel):
    _name = 'bhu.expert.committee.order.wizard'
    _description = 'Expert Committee Order Wizard'

    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True)

    def action_generate_order(self):
        """Generate Order - To be implemented"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Order generation will be implemented soon.'),
                'type': 'info',
            }
        }


