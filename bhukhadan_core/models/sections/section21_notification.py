# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import uuid

class Section21Notification(models.Model):
    _name = 'bhu.section21.notification'
    _description = 'Section 21 Notification / धारा 21 अधिसूचना'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.notification.mixin', 'bhu.process.workflow.mixin', 'bhu.qr.code.mixin']
    _order = 'create_date desc'
    @api.constrains('project_id', 'village_id')
    def _check_unique_section21_per_project_village(self):
        for rec in self:
            if not rec.project_id or not rec.village_id:
                continue
            duplicate = self.search([
                ('project_id', '=', rec.project_id.id),
                ('village_id', '=', rec.village_id.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    'A Section 21 notification already exists for this project and village. '
                    'Only one is allowed.'
                )

    name = fields.Char(string='Notification Name / अधिसूचना का नाम', default='New', tracking=True, readonly=True)
    
    # Title field
    title = fields.Char(string='Title / शीर्षक', tracking=True,
                       help='Title for the Section 21 notification')
    
    # Location fields inherited from bhu.process.workflow.mixin
    # Override project_id to make it optional
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=False, tracking=True)

    
    # Notice Date
    notice_date = fields.Date(string='Notice Date / नोटिस दिनांक', tracking=True,
                              default=fields.Date.today,
                              help='Date of issue of the public notice')
    
    # Kramank (Reference Number)
    kramank = fields.Char(string='Kramank / क्रमांक', required=False, tracking=True,
                          help='Reference number to be displayed in the report')
    
    # Requisitioning Body - Related from project's department
    requisitioning_body = fields.Char(string='Requisitioning Body / अपेक्षक निकाय', 
                                     related='project_id.department_id.name', 
                                     readonly=True, store=True, tracking=True,
                                     help='Name of the requisitioning body from project department')
    
    # Public Purpose - Related from project name
    public_purpose = fields.Char(string='Public Purpose / सार्वजनिक प्रयोजन', 
                                 related='project_id.name', 
                                 readonly=True, store=True, tracking=True,
                                 help='Public purpose from project name')
    
    # Land Parcels (One2many)
    land_parcel_ids = fields.One2many('bhu.section21.land.parcel', 'notification_id', 
                                      string='Land Parcels / भूमि खंड', tracking=True)
    
    # Computed fields for list view
    khasra_numbers = fields.Char(string='Khasra Numbers / खसरा नंबर', compute='_compute_khasra_info', store=False)
    khasra_count = fields.Integer(string='Khasra Count / खसरा संख्या', compute='_compute_khasra_info', store=False)
    
    # Signed document fields (legacy - kept for backward compatibility)
    signed_document_file = fields.Binary(string='Signed Notification / हस्ताक्षरित अधिसूचना')
    signed_document_filename = fields.Char(string='Signed File Name / हस्ताक्षरित फ़ाइल नाम')
    signed_date = fields.Date(string='Signed Date / हस्ताक्षर दिनांक', tracking=True)
    has_signed_document = fields.Boolean(string='Has Signed Document / हस्ताक्षरित दस्तावेज़ है', 
                                         compute='_compute_has_signed_document', store=True)
    
    # SDM Signed File
    sdm_signed_file = fields.Binary(string='SDM Signed File / एसडीएम हस्ताक्षरित फ़ाइल')
    sdm_signed_filename = fields.Char(string='SDM Signed File Name / एसडीएम हस्ताक्षरित फ़ाइल नाम')
    
    # Collector Signed File
    collector_signed_file = fields.Binary(string='Collector Signed File / कलेक्टर हस्ताक्षरित फ़ाइल')
    collector_signed_filename = fields.Char(string='Collector Signed File Name / कलेक्टर हस्ताक्षरित फ़ाइल नाम')
    
    # Personal Section 21 Signed File
    personal_signed_file = fields.Binary(string='Personal Section 21 Signed File / व्यक्तिगत धारा 21 हस्ताक्षरित फ़ाइल')
    personal_signed_filename = fields.Char(string='Personal Signed File Name / व्यक्तिगत हस्ताक्षरित फ़ाइल नाम')
    
    # Collector signature (for reports)
    collector_signature = fields.Binary(string='Collector Signature / कलेक्टर हस्ताक्षर')
    collector_signature_filename = fields.Char(string='Signature File Name')
    collector_name = fields.Char(string='Collector Name / कलेक्टर का नाम', tracking=True,
                                  default='कलेक्टर जिला-रायगढ़')
    
    # Additional Collector
    additional_collector_name = fields.Char(string='Additional Collector Name / अपर कलेक्टर का नाम', tracking=True,
                                           default='अपर कलेक्टर जिला-रायगढ़')
    
    # UUID for QR code
    notification_uuid = fields.Char(string='Notification UUID', copy=False, readonly=True, index=True)
    
    # State field - simple states like Section 19
    # State field inherited from bhu.process.workflow.mixin
    # Uses standard workflow: draft -> submitted -> approved (with send_back option)
    
    @api.depends('signed_document_file')
    def _compute_has_signed_document(self):
        for record in self:
            record.has_signed_document = bool(record.signed_document_file)

    is_collector_role = fields.Boolean(compute='_compute_is_collector_role', compute_sudo=True)

    def _compute_is_collector_role(self):
        is_collector = self.env.user.bhuarjan_role == 'collector'
        for record in self:
            record.is_collector_role = is_collector
            # Auto-approve when signed document is uploaded (using standard workflow)
            if record.has_signed_document and record.state != 'approved':
                record.state = 'approved'
                if not record.approved_date:
                    record.approved_date = fields.Datetime.now()
                if not record.signed_date:
                    record.signed_date = fields.Date.today()
    
    @api.depends('village_id')

    @api.depends('land_parcel_ids.khasra_number')
    def _compute_khasra_info(self):
        """Compute khasra numbers and count for list view"""
        for record in self:
            if record.land_parcel_ids:
                khasras = record.land_parcel_ids.mapped('khasra_number')
                record.khasra_numbers = ', '.join([k for k in khasras if k])
                record.khasra_count = len([k for k in khasras if k])
            else:
                record.khasra_numbers = ''
                record.khasra_count = 0
    
    def _get_approved_surveys_data(self):
        """Get approved/locked survey data grouped by khasra number with total area and landowner info"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
            return []
        surveys = self.env['bhu.survey'].search([
            ('village_id', '=', self.village_id.id),
            ('project_id', '=', self.project_id.id),
            ('state', 'in', ['approved', 'locked'])
        ], order='khasra_number')
        khasra_data = {}
        for survey in surveys:
            if survey.khasra_number:
                if survey.khasra_number not in khasra_data:
                    khasra_data[survey.khasra_number] = {
                        'area': 0.0,
                        'landowner': False,
                        'landowner_name': '',
                        'landowner_father': '',
                        'landowner_address': ''
                    }
                khasra_data[survey.khasra_number]['area'] += survey.acquired_area or 0.0
                # Get first landowner if available
                if survey.landowner_ids and not khasra_data[survey.khasra_number]['landowner']:
                    landowner = survey.landowner_ids[0]
                    khasra_data[survey.khasra_number]['landowner'] = landowner
                    khasra_data[survey.khasra_number]['landowner_name'] = landowner.name or ''
                    khasra_data[survey.khasra_number]['landowner_father'] = landowner.father_name or landowner.spouse_name or ''
                    khasra_data[survey.khasra_number]['landowner_address'] = (
                        survey.landowner_ids[0].village_id.display_name or ''
                    ) if survey.landowner_ids[0].village_id else ''
        return [{
            'khasra_number': k,
            'area': v['area'],
            'landowner_name': v['landowner_name'],
            'landowner_father': v['landowner_father'],
            'landowner_address': v['landowner_address']
        } for k, v in sorted(khasra_data.items())]
    
    # Survey-related fields (similar to Section 4)
    survey_ids = fields.Many2many('bhu.survey', compute='_compute_survey_ids', string='Surveys', readonly=True)
    survey_count = fields.Integer(string='Survey Count', compute='_compute_survey_ids', readonly=True)
    approved_survey_count = fields.Integer(string='Approved Survey Count', compute='_compute_survey_ids', readonly=True)
    all_surveys_approved = fields.Boolean(string='All Surveys Approved', compute='_compute_survey_ids', readonly=True)
    
    @api.depends('project_id', 'village_id')
    def _compute_survey_ids(self):
        """Compute surveys for selected village and project"""
        for record in self:
            if record.project_id and record.village_id:
                surveys = self.env['bhu.survey'].search([
                    ('project_id', '=', record.project_id.id),
                    ('village_id', '=', record.village_id.id)
                ])
                record.survey_ids = [(6, 0, surveys.ids)]
                record.survey_count = len(surveys)
                # Treat both 'approved' and 'locked' as approved
                approved_or_locked_surveys = surveys.filtered(lambda s: s.state in ('approved', 'locked'))
                record.approved_survey_count = len(approved_or_locked_surveys)
                # Check if all surveys are approved or locked (and there are surveys)
                record.all_surveys_approved = len(surveys) > 0 and len(approved_or_locked_surveys) == len(surveys)
            else:
                record.survey_ids = [(5, 0, 0)]
                record.survey_count = 0
                record.approved_survey_count = 0
                record.all_surveys_approved = False
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain to only show project villages."""
        if self.project_id:
            if self.project_id.village_ids:
                if self.village_id and self.village_id.id in self.project_id.village_ids.ids:
                    pass
                else:
                    self.village_id = False
                return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
            else:
                self.village_id = False
                return {'domain': {'village_id': [('id', '=', False)]}}
        else:
            self.village_id = False
            return {'domain': {'village_id': [('id', '=', False)]}}
    
    @api.onchange('village_id', 'project_id')
    def _onchange_village_populate_land_parcels(self):
        """Auto-populate land parcels from surveys when village is selected"""
        if self.village_id and self.project_id:
            self._populate_land_parcels_from_section19()
    
    def _populate_land_parcels_from_section19(self):
        """Helper method to populate land parcels directly from approved/locked surveys"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
            return
        
        # Clear existing land parcels
        self.land_parcel_ids = [(5, 0, 0)]
        
        # Populate directly from approved/locked surveys
        surveys = self.env['bhu.survey'].search([
            ('village_id', '=', self.village_id.id),
            ('project_id', '=', self.project_id.id),
            ('state', 'in', ['approved', 'locked'])
        ], order='khasra_number')
        
        # Use a set to track unique khasra numbers to avoid duplicates
        seen_khasras = set()
        parcel_vals = []
        for survey in surveys:
            if survey.khasra_number and survey.khasra_number not in seen_khasras:
                seen_khasras.add(survey.khasra_number)
                # Sum up area for this khasra from all surveys with the same khasra
                total_area = sum(s.acquired_area or 0.0 for s in surveys if s.khasra_number == survey.khasra_number)
                parcel_vals.append((0, 0, {
                    'khasra_number': survey.khasra_number,
                    'area_hectares': total_area,
                    'remark': '',  # Default empty remark
                }))
        
        # Set the land parcels
        if parcel_vals:
            self.land_parcel_ids = parcel_vals
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        
        # Get defaults from context
        if 'default_project_id' in self.env.context:
            res['project_id'] = self.env.context['default_project_id']
        if 'default_village_id' in self.env.context:
            res['village_id'] = self.env.context['default_village_id']
        
        return res
    

    
    @api.model_create_multi
    def create(self, vals_list):
        """Create records with batch support"""
        for vals in vals_list:
            # Check for duplicate project + village combination before creating
            project_id = vals.get('project_id')
            village_id = vals.get('village_id')
            if project_id and village_id:
                existing = self.search([
                    ('project_id', '=', project_id),
                    ('village_id', '=', village_id)
                ], limit=1)
                if existing:
                    project = self.env['bhu.project'].browse(project_id)
                    village = self.env['bhu.village'].browse(village_id)
                    raise ValidationError(
                        _('A Section 21 notification already exists for project "%s" and village "%s".\n'
                          'Only one Section 21 notification is allowed per project-village combination.\n'
                          'Existing notification: %s') % (project.name, village.name, existing.name)
                    )
            
            # village_id is already required at field level, no need for extra validation
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                # Try to use sequence settings from settings master
                if project_id:
                    try:
                        sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                            'section21_notification', project_id, village_id=village_id
                        )
                        if sequence_number:
                            vals['name'] = sequence_number
                        else:
                            # Fallback to ir.sequence
                            vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section21.notification') or 'New'
                    except:
                        # Fallback to ir.sequence
                        vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section21.notification') or 'New'
                else:
                    # No project_id, use fallback
                    vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section21.notification') or 'New'
            # Generate UUID if not provided
            if not vals.get('notification_uuid'):
                vals['notification_uuid'] = str(uuid.uuid4())

        records = super().create(vals_list)
        # Auto-populate land parcels after creation
        for record in records:
            if record.village_id and record.project_id:
                record._populate_land_parcels_from_section19()
        return records
    
    def write(self, vals):
        """Override write to repopulate land parcels when village or project changes"""
        # Check for duplicate project + village combination when updating
        if 'project_id' in vals or 'village_id' in vals:
            for record in self:
                new_project_id = vals.get('project_id', record.project_id.id)
                new_village_id = vals.get('village_id', record.village_id.id)
                if new_project_id and new_village_id:
                    existing = self.search([
                        ('project_id', '=', new_project_id),
                        ('village_id', '=', new_village_id),
                        ('id', '!=', record.id)
                    ], limit=1)
                    if existing:
                        project = self.env['bhu.project'].browse(new_project_id)
                        village = self.env['bhu.village'].browse(new_village_id)
                        raise ValidationError(
                            _('A Section 21 notification already exists for project "%s" and village "%s".\n'
                              'Only one Section 21 notification is allowed per project-village combination.\n'
                              'Existing notification: %s') % (project.name, village.name, existing.name)
                        )
        
        result = super().write(vals)
        # If village_id or project_id changed, repopulate land parcels
        if 'village_id' in vals or 'project_id' in vals:
            for record in self:
                if record.village_id and record.project_id:
                    record._populate_land_parcels_from_section19()
        return result
    
    def get_deadline_date(self):
        """Calculate deadline date based on state:
        Proposal (Draft): blank
        Order (Submitted/Approved): current date + 45 days
        """
        if self.state not in ['submitted', 'approved']:
            return None
        
        # User explicitly asked for "current date + 45 days" for the order
        return fields.Date.today() + relativedelta(days=45)
    
    def get_deadline_date_formatted(self):
        """Get deadline date formatted as dd/mm/yyyy"""
        deadline = self.get_deadline_date()
        if deadline:
            return deadline.strftime('%d/%m/%Y')
        return None
    
    # QR code generation is now handled by bhu.qr.code.mixin
    

    
    def _get_khasra_landowner_mapping(self):
        """Get mapping of khasra numbers to landowners directly from surveys (no land parcel dependency)"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
            return []
        
        # Find all approved/locked surveys for this village/project with khasra numbers
        surveys = self.env['bhu.survey'].search([
            ('village_id', '=', self.village_id.id),
            ('project_id', '=', self.project_id.id),
            ('khasra_number', '!=', False),
            ('state', 'in', ['approved', 'locked']),
        ])
        
        # Create mapping: khasra_number -> list of landowners (ensure at least one entry per khasra)
        khasra_landowner_map = {}
        for survey in surveys:
            khasra = survey.khasra_number
            if not khasra:
                continue
            if khasra not in khasra_landowner_map:
                khasra_landowner_map[khasra] = []
            for landowner in survey.landowner_ids:
                if landowner.id not in [lo.id for lo in khasra_landowner_map[khasra]]:
                    khasra_landowner_map[khasra].append(landowner)
            # If no landowner linked, keep an empty list (handled below)
        
        # Convert to list of tuples: (khasra_number, landowner or False)
        result = []
        for khasra, landowners in khasra_landowner_map.items():
            if landowners:
                for landowner in landowners:
                    result.append((khasra, landowner))
            else:
                # No landowner for this khasra, still return a placeholder to generate notice
                result.append((khasra, False))
        
                result.append((khasra, False))
        
        return result
    
    # -------------------------------------------------------------------------
    # NEW REPORTING LOGIC (Refactored)
    # -------------------------------------------------------------------------

    def get_section21_public_data(self):
        """
        Data provider for Public Notice section.
        Returns a list containing the record itself to trigger one iteration in QWeb.
        """
        self.ensure_one()
        return [self]

    def get_section21_personal_data(self):
        """
        Data provider for Personal Notice section.
        Returns a list of dictionaries with all data needed for the personal notice.
        No transient model dependency.
        """
        self.ensure_one()
        
        # Get khasra-landowner mapping
        khasra_landowner_mapping = self._get_khasra_landowner_mapping()
        
        # Helper to get area for a khasra
        def get_khasra_area(khasra_num):
            surveys = self.env['bhu.survey'].search([
                ('village_id', '=', self.village_id.id),
                ('project_id', '=', self.project_id.id),
                ('khasra_number', '=', khasra_num),
                ('state', 'in', ['approved', 'locked'])
            ])
            return sum(s.acquired_area or 0.0 for s in surveys)

        personal_data_list = []
        
        # If no mapping, check if we simply have khasras without landowners
        if not khasra_landowner_mapping:
             surveys = self.env['bhu.survey'].search([
                ('village_id', '=', self.village_id.id),
                ('project_id', '=', self.project_id.id),
                ('state', 'in', ['approved', 'locked']),
                ('khasra_number', '!=', False)
            ])
             unique_khasras = list(set(surveys.mapped('khasra_number')))
             for khasra in unique_khasras:
                 personal_data_list.append({
                     'khasra_number': khasra,
                     'area': get_khasra_area(khasra),
                     'landowner_name': '',
                     'landowner_father': '',
                     'landowner_address': '',
                     # Add notification UUID for QR code generation if needed in loop
                     'notification_uuid': self.notification_uuid
                 })
        else:
            for khasra, landowner in khasra_landowner_mapping:
                data = {
                    'khasra_number': khasra,
                    'area': get_khasra_area(khasra),
                    'landowner_name': landowner.name if landowner else '',
                    'landowner_father': (landowner.father_name or landowner.spouse_name) if landowner else '',
                    'landowner_address': (
                        landowner.village_id.display_name or ''
                    ) if landowner and landowner.village_id else '',
                    'notification_uuid': self.notification_uuid
                }
                personal_data_list.append(data)
        
        # Sort by khasra number
        try:
             personal_data_list.sort(key=lambda x: x['khasra_number'])
        except:
             pass
             
        return personal_data_list

    def action_print_section21_report(self):
        """
        Unified method to print Section 21 Report.
        Uses context flags to determine what to show.
        """
        self.ensure_one()
        
        # Default flags (overridden by context if provided, otherwise assume specific button actions set them)
        show_public = self.env.context.get('show_public_notice', False)
        show_personal = self.env.context.get('show_personal_notice', False)
        
        # If no context flags, assume standard print (Public Only by default for legacy reasons, or check caller)
        # But here we will rely on specific actions calling this with context
        
        return self.env.ref('bhukhadan_core.action_report_section21_notification').report_action(self, data=None)

    def action_generate_public_notice(self):
        """Generate Section 21 Public Notice PDF"""
        self.ensure_one()
        return self.with_context(show_public_notice=True, show_personal_notice=False).action_print_section21_report()
    
    def action_generate_personal_notices(self):
        """Generate Section 21 Personal Notices PDF"""
        self.ensure_one()
        # Ensure validation
        if not self.village_id or not self.project_id:
             raise ValidationError(_('Please select Village and Project.'))
        return self.with_context(show_public_notice=False, show_personal_notice=True).action_print_section21_report()
    

        
    def action_generate_section21_public_for_all(self):
        """Generate Both Public and Personal"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
             raise ValidationError(_('Please select Village and Project.'))
        return self.with_context(show_public_notice=True, show_personal_notice=True).action_print_section21_report()

    def action_generate_both_notices(self):
         return self.action_generate_section21_public_for_all()



    # -------------------------------------------------------------------------
    # Legacy / Deprecated methods kept for compatibility or cleanup
    # -------------------------------------------------------------------------

    # Override mixin method to generate Section 21 Notification PDF
    def action_download_signed_document(self):
        """Download signed Section 21 notification document"""
        self.ensure_one()
        if not self.signed_document_file:
            raise ValidationError(_('No signed document available for download.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/bhu.section21.notification/{self.id}/signed_document_file/{self.signed_document_filename or "section21_signed_notification.pdf"}?download=true',
            'target': 'self',
        }
    
    def action_download_sdm_signed_file(self):
        """Download SDM signed file"""
        self.ensure_one()
        if not self.sdm_signed_file:
            raise ValidationError(_('No SDM signed file available for download.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/bhu.section21.notification/{self.id}/sdm_signed_file/{self.sdm_signed_filename or "section21_sdm_signed.pdf"}?download=true',
            'target': 'self',
        }
    
    def action_download_collector_signed_file(self):
        """Download Collector signed file"""
        self.ensure_one()
        if not self.collector_signed_file:
            raise ValidationError(_('No Collector signed file available for download.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/bhu.section21.notification/{self.id}/collector_signed_file/{self.collector_signed_filename or "section21_collector_signed.pdf"}?download=true',
            'target': 'self',
        }
    
    def action_download_personal_signed_file(self):
        """Download Personal Section 21 signed file"""
        self.ensure_one()
        if not self.personal_signed_file:
            raise ValidationError(_('No Personal Section 21 signed file available for download.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/bhu.section21.notification/{self.id}/personal_signed_file/{self.personal_signed_filename or "section21_personal_signed.pdf"}?download=true',
            'target': 'self',
        }
    
    
    def action_generate_pdf(self):
        """Generate Section 21 Notification PDF - Legacy method (defaults to public)"""
        return self.action_generate_public_notice()
    
    
    def action_mark_signed(self):
        """Submit notification to Collector after SDM uploads file (standard workflow)"""
        self.ensure_one()
        if not self.sdm_signed_file:
            raise ValidationError(_('Please upload SDM signed file first.'))
        self.state = 'submitted'
        self.submitted_date = fields.Datetime.now()
        if not self.signed_date:
            self.signed_date = fields.Date.today()
    
    def action_approve(self):
        """Allow Collector to approve even from draft state if they have the file"""
        self.ensure_one()
        if self.state == 'draft':
            self.state = 'submitted'
            if not self.submitted_date:
                self.submitted_date = fields.Datetime.now()
        return super(Section21Notification, self).action_approve()

    def action_upload_personal_file(self):
        """Handle upload of Personal Section 21 signed file"""
        self.ensure_one()
        if not self.personal_signed_file:
            raise ValidationError(_('Please select a Personal Section 21 signed file to upload.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Personal Section 21 signed file uploaded successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }


class Section21LandParcel(models.Model):
    _name = 'bhu.section21.land.parcel'
    _description = 'Section 21 Land Parcel'
    _order = 'khasra_number'

    notification_id = fields.Many2one('bhu.section21.notification', string='Notification', required=True, ondelete='cascade')
    khasra_number = fields.Char(string='Khasra Number / खसरा नंबर', required=True)
    area_hectares = fields.Float(string='Area (Hectares) / अर्जित रकबा (हेक्टेयर में)', required=True, digits=(16, 4))
    remark = fields.Char(string='Remark / रिमार्क', help='Additional remarks for this land parcel')




