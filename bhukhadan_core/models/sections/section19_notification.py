# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import uuid

import json

class Section19Notification(models.Model):
    _name = 'bhu.section19.notification'
    _description = 'Section 19 Notification'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.notification.mixin', 'bhu.process.workflow.mixin', 'bhu.qr.code.mixin']
    _order = 'create_date desc'

    _sql_constraints = [
        ('unique_project_village', 'unique(project_id, village_id)', 'A Section 19 notification already exists for this Project and Village! / इस परियोजना और ग्राम के लिए धारा 19 अधिसूचना पहले से मौजूद है!')
    ]


    name = fields.Char(string='Notification Name / अधिसूचना का नाम', default='New', tracking=True, readonly=True)
    
    # Location fields inherited from bhu.process.workflow.mixin
    # Override project_id to make it optional and add default
    project_id = fields.Many2one(default=lambda self: self._default_project_id(), required=False)
    
    # Prakaran Kramank
    prakaran_kramank = fields.Char(string='Prakaran Kramank / प्रकरण क्रमांक', required=False, tracking=True,
                                   help='Case number to be displayed in the report (optional)')
    
    # Public Purpose
    public_purpose = fields.Text(string='Public Purpose / लोक प्रयोजन', 
                                 help='Description of public purpose for land acquisition', tracking=True)
    
    # Computed fields for list view
    khasra_numbers = fields.Char(string='Khasra Numbers / खसरा नंबर', compute='_compute_khasra_info', store=False)
    khasra_count = fields.Integer(string='Khasra Count / खसरा संख्या', compute='_compute_khasra_info', store=False)
    
    # Related surveys (approved/locked) for the village and project
    survey_ids = fields.Many2many('bhu.survey', string='Surveys / सर्वे', 
                                   compute='_compute_survey_ids', store=False, readonly=True)
    
    # Paragraph 2: Map Inspection
    sdo_revenue_name = fields.Char(string='SDO (Revenue) Name / अनुविभागीय अधिकारी (राजस्व) का नाम',
                                   tracking=True)
    sdo_office_location = fields.Char(string='SDO Office Location / अनुविभागीय अधिकारी कार्यालय स्थान',
                                      tracking=True)
    
    # Paragraph 3: Displacement and Rehabilitation - Related from project
    is_displacement_involved = fields.Boolean(string='Is Displacement Involved? / क्या विस्थापन शामिल है?',
                                              related='project_id.is_displacement', readonly=True, tracking=True)
    
    # Number of affected persons for rehabilitation - Related from project
    affected_persons_count = fields.Integer(string='Affected Persons Count / प्रभावित व्यक्तियों की संख्या',
                                             related='project_id.affected_persons_count', readonly=True, tracking=True,
                                             help='Number of persons affected by the proposed land acquisition who will be rehabilitated')
    
    # Rehabilitation land details (conditional)
    rehab_village = fields.Char(string='Rehabilitation Village / पुनर्वास ग्राम',
                                tracking=True)
    rehab_tehsil = fields.Char(string='Rehabilitation Tehsil / पुनर्वास तहसील',
                               tracking=True)
    rehab_district = fields.Char(string='Rehabilitation District / पुनर्वास जिला',
                                  tracking=True)
    rehab_khasra_number = fields.Char(string='Rehabilitation Khasra Number / पुनर्वास खसरा नंबर',
                                      tracking=True)
    rehab_area_hectares = fields.Float(string='Rehabilitation Area (Hectares) / पुनर्वास क्षेत्रफल (हेक्टेयर)',
                                        digits=(16, 4), tracking=True)
    rehab_officer_name = fields.Char(string='Rehabilitation Officer / पुनर्वास अधिकारी',
                                     tracking=True)
    rehab_officer_office_location = fields.Char(string='Rehabilitation Officer Office / पुनर्वास अधिकारी कार्यालय',
                                                 tracking=True)
    
    # Signed document fields
    signed_document_file = fields.Binary(string='Signed Notification / हस्ताक्षरित अधिसूचना')
    signed_document_filename = fields.Char(string='Signed File Name / हस्ताक्षरित फ़ाइल नाम')
    signed_date = fields.Date(string='Signed Date / हस्ताक्षर दिनांक', tracking=True)
    has_signed_document = fields.Boolean(string='Has Signed Document / हस्ताक्षरित दस्तावेज़ है', 
                                         compute='_compute_has_signed_document', store=True)
    
    # Collector signature
    collector_signature = fields.Binary(string='Collector Signature / कलेक्टर हस्ताक्षर')
    collector_signature_filename = fields.Char(string='Signature File Name')
    collector_name = fields.Char(string='Collector Name / कलेक्टर का नाम', tracking=True)
    
    # UUID for QR code
    notification_uuid = fields.Char(string='Notification UUID', copy=False, readonly=True, index=True)
    
    # State field is inherited from mixin
    
    @api.depends('signed_document_file')
    def _compute_has_signed_document(self):
        for record in self:
            record.has_signed_document = bool(record.signed_document_file)
            # Auto-sign when signed document is uploaded
            if record.has_signed_document and record.state != 'signed':
                record.state = 'signed'
                if not record.signed_date:
                    record.signed_date = fields.Date.today()
    
    @api.depends('village_id')

    def _get_approved_surveys_data(self):
        """Get grouped survey data (khasra_number and total area) from approved surveys"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
            return []
        
        # Get all approved/locked surveys for the village and project
        surveys = self.env['bhu.survey'].search([
            ('village_id', '=', self.village_id.id),
            ('project_id', '=', self.project_id.id),
            ('state', 'in', ['approved', 'locked'])
        ], order='khasra_number')
        
        # Group by khasra_number and sum areas
        khasra_data = {}
        for survey in surveys:
            if survey.khasra_number:
                if survey.khasra_number not in khasra_data:
                    khasra_data[survey.khasra_number] = 0.0
                khasra_data[survey.khasra_number] += survey.acquired_area or 0.0
        
        # Convert to list of dicts
        return [{'khasra_number': k, 'area': v} for k, v in sorted(khasra_data.items())]
    
    def _get_total_area_from_surveys(self):
        """Get total area from approved surveys"""
        self.ensure_one()
        surveys_data = self._get_approved_surveys_data()
        return sum(item['area'] for item in surveys_data)
    
    @api.depends('village_id', 'project_id')
    def _compute_khasra_info(self):
        """Compute khasra numbers and count from approved surveys"""
        for record in self:
            surveys_data = record._get_approved_surveys_data()
            if surveys_data:
                khasras = [item['khasra_number'] for item in surveys_data]
                record.khasra_numbers = ', '.join(khasras)
                record.khasra_count = len(khasras)
            else:
                record.khasra_numbers = ''
                record.khasra_count = 0
    
    @api.depends('village_id', 'project_id')
    def _compute_survey_ids(self):
        """Compute related surveys (approved/locked) for the village and project"""
        for record in self:
            if record.village_id and record.project_id:
                surveys = self.env['bhu.survey'].search([
                    ('village_id', '=', record.village_id.id),
                    ('project_id', '=', record.project_id.id),
                    ('state', 'in', ['approved', 'locked'])
                ], order='khasra_number')
                record.survey_ids = surveys
            else:
                record.survey_ids = False
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain to only show project villages.
        Also auto-populate rehabilitation fields from project allocated fields."""
        # Only reset village if it's not valid for the new project
        if self.project_id and self.project_id.village_ids:
            # If village is already set and is in the project's villages, keep it
            if self.village_id and self.village_id.id in self.project_id.village_ids.ids:
                # Village is valid, keep it
                pass
            else:
                # Village is not valid for this project, reset it
                self.village_id = False
            # Auto-populate rehabilitation fields from project allocated fields
            if self.project_id.allocated_village:
                self.rehab_village = self.project_id.allocated_village
            if self.project_id.allocated_tehsil:
                self.rehab_tehsil = self.project_id.allocated_tehsil
            if self.project_id.allocated_district:
                self.rehab_district = self.project_id.allocated_district
            if self.project_id.allocated_khasra_number:
                self.rehab_khasra_number = self.project_id.allocated_khasra_number
            if self.project_id.allocated_area_hectares:
                self.rehab_area_hectares = self.project_id.allocated_area_hectares
            return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        else:
            # No villages in project, reset village
            self.village_id = False
            return {'domain': {'village_id': [('id', '=', False)]}}
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        
        # Get defaults from context (set by dashboard or other actions)
        if 'default_project_id' in self.env.context:
            res['project_id'] = self.env.context['default_project_id']
        if 'default_village_id' in self.env.context:
            res['village_id'] = self.env.context['default_village_id']
        
        return res
    
    @api.model
    def _default_project_id(self):
        """Default project_id to PROJ01 if it exists, otherwise use first available project"""
        project = self.env['bhu.project'].search([('code', '=', 'PROJ01')], limit=1)
        if project:
            return project.id
        fallback_project = self.env['bhu.project'].search([], limit=1)
        return fallback_project.id if fallback_project else False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create records with batch support and validation"""
        for vals in vals_list:
            # Check validation before flush
            project_id_val = vals.get('project_id')
            village_id_val = vals.get('village_id')
            if project_id_val and village_id_val:
                existing = self.sudo().search([
                    ('project_id', '=', project_id_val),
                    ('village_id', '=', village_id_val)
                ], limit=1)
                if existing:
                    raise ValidationError(_('A Section 19 notification already exists for this Project and Village (ID: %s, Name: %s, State: %s)! Please check and edit the existing record. / इस परियोजना और ग्राम के लिए धारा 19 अधिसूचना (ID: %s) पहले से मौजूद है! (स्थिति: %s)') % (existing.id, existing.name, existing.state, existing.id, existing.state))

            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                # Try to use sequence settings from settings master
                project_id = vals.get('project_id')
                village_id = vals.get('village_id')
                if project_id:
                    try:
                        sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                            'section19_notification', project_id, village_id=village_id
                        )
                        if sequence_number:
                            vals['name'] = sequence_number
                        else:
                            # Fallback to ir.sequence
                            vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section19.notification') or 'New'
                    except:
                        # Fallback to ir.sequence
                        vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section19.notification') or 'New'
                else:
                    # No project_id, use fallback
                    vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section19.notification') or 'New'
            # Generate UUID if not provided
            if not vals.get('notification_uuid'):
                vals['notification_uuid'] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, vals):
        """Override write to validate uniqueness and repopulate land parcels"""
        # Check uniqueness if project or village is changing
        if 'project_id' in vals or 'village_id' in vals:
            for record in self:
                project_id = vals.get('project_id', record.project_id.id)
                village_id = vals.get('village_id', record.village_id.id)
                
                if project_id and village_id:
                    existing = self.sudo().search([
                        ('project_id', '=', project_id),
                        ('village_id', '=', village_id),
                        ('id', '!=', record.id)
                    ], limit=1)
                    if existing:
                        raise ValidationError(_('A Section 19 notification already exists for this Project and Village (ID: %s, Name: %s, State: %s)! Please check and edit the existing record. / इस परियोजना और ग्राम के लिए धारा 19 अधिसूचना (ID: %s) पहले से मौजूद है! (स्थिति: %s)') % (existing.id, existing.name, existing.state, existing.id, existing.state))

        result = super().write(vals)
        # If village_id or project_id changed, repopulate land parcels
        if 'village_id' in vals or 'project_id' in vals:
            for record in self:
                if record.village_id and record.project_id:
                     # Reset village if not in new project - logic already handled by onchange but good for write too
                     # But here we assume valid data. Re-populate land parcels.
                     record._populate_land_parcels_from_section19()
        return result
    
    # QR code generation is now handled by bhu.qr.code.mixin
    
    
    def action_download_unsigned_file(self):
        """Generate and download Section 19 Notification PDF/Word (unsigned) - Override mixin"""
        self.ensure_one()
        return {
            'name': _('Download Section 19 Notification / धारा 19 अधिसूचना डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_section19_notification',
                'default_filename': f'Section19_Notification_{self.name}.doc'
            }
        }
    
    def action_generate_pdf(self):
        """Generate Section 19 Notification PDF - Legacy method"""
        return self.action_download_unsigned_file()
    
    def action_mark_signed(self):
        """Mark notification as signed"""
        self.ensure_one()
        if not self.signed_document_file:
            raise ValidationError(_('Please upload signed document first.'))
        self.state = 'signed'
        if not self.signed_date:
            self.signed_date = fields.Date.today()
    
    @api.model
    def action_open_wizard(self):
        """Open wizard to generate new notification - works without record selection"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Section 19 Notification',
            'res_model': 'bhu.section19.notification.wizard',
            'view_mode': 'form',
            'target': 'new',
        }


class Section19NotificationWizard(models.TransientModel):
    _name = 'bhu.section19.notification.wizard'
    _description = 'Section 19 Notification Wizard'

    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True)
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True)
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain to only show project villages"""
        # Only reset village if it's not valid for the new project
        if self.project_id and self.project_id.village_ids:
            # If village is already set and is in the project's villages, keep it
            if self.village_id and self.village_id.id in self.project_id.village_ids.ids:
                # Village is valid, keep it
                pass
            else:
                # Village is not valid for this project, reset it
                self.village_id = False
            return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        else:
            # No villages in project, reset village
            self.village_id = False
            return {'domain': {'village_id': [('id', '=', False)]}}
    
    def action_generate_notification(self):
        """Create Section 19 Notification record and generate PDF"""
        self.ensure_one()
        
        # Check if notification already exists
        existing = self.env['bhu.section19.notification'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id)
        ])
        if existing:
            raise ValidationError(_('A Section 19 notification already exists for this Project and Village! / इस परियोजना और ग्राम के लिए धारा 19 अधिसूचना पहले से मौजूद है!'))
        
        # Create notification record
        notification = self.env['bhu.section19.notification'].create({
            'project_id': self.project_id.id,
            'village_id': self.village_id.id,
            'state': 'generated',
        })
        
        # Generate PDF report
        report_action = self.env.ref('bhukhadan_core.action_report_section19_notification')
        return report_action.report_action(notification)


class Section11PreliminaryWizard(models.TransientModel):
    _name = 'bhu.section11.preliminary.wizard'
    _description = 'Section 11 Preliminary Report Wizard'

    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True)
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True)

    def action_generate_report(self):
        """Create Section 11 Preliminary Report record"""
        self.ensure_one()
        
        # Create the report record
        report = self.env['bhu.section11.preliminary.report'].create({
            'project_id': self.project_id.id,
            'village_id': self.village_id.id,
        })
        
        # Open the form view
        return {
            'type': 'ir.actions.act_window',
            'name': _('Section 11 Preliminary Report'),
            'res_model': 'bhu.section11.preliminary.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }




