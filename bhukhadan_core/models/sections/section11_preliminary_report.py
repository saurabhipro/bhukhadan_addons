from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import uuid
import json

class Section11PreliminaryReport(models.Model):
    _name = 'bhu.section11.preliminary.report'
    _description = 'Section 11 Preliminary Report'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.notification.mixin', 'bhu.process.workflow.mixin', 'bhu.qr.code.mixin']
    _order = 'create_date desc'

    # Note: Removed unique project constraint to allow one Section 11 per village per project

    name = fields.Char(string='Report Name', required=True, default='New', tracking=True, readonly=True)
    # Location fields inherited from bhu.process.workflow.mixin
    # Override project_id to add default
    project_id = fields.Many2one(default=lambda self: self._default_project_id())
    
    @api.constrains('project_id', 'village_id')
    def _check_unique_village_per_project(self):
        """Ensure only one Section 11 Preliminary Report per village per project"""
        for record in self:
            if record.project_id and record.village_id:
                existing = self.search([
                    ('id', '!=', record.id),
                    ('project_id', '=', record.project_id.id),
                    ('village_id', '=', record.village_id.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('A Section 11 Preliminary Report already exists for village "%s" in project "%s". Only one Section 11 Preliminary Report can be created per village per project.') %
                        (record.village_id.name, record.project_id.name)
                    )


    village_domain = fields.Char(default='[]')
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain"""
        for rec in self:
            if rec.project_id and rec.project_id.village_ids:
                village_ids = rec.project_id.village_ids.ids
                # If village is already set and is in the project's villages, keep it
                if rec.village_id and rec.village_id.id in village_ids:
                    # Village is valid, keep it
                    rec.village_domain = json.dumps([('id', 'in', village_ids)])
                else:
                    # Village is not valid for this project, reset it
                    rec.village_domain = json.dumps([('id', 'in', village_ids)])
                    rec.village_id = False
            else:
                rec.village_domain = json.dumps([])   # empty domain
                rec.village_id = False
    
    @api.onchange('village_id')
    def _onchange_village_id(self):
        """Ensure domain is set when village is changed"""
        for rec in self:
            if rec.project_id and rec.project_id.village_ids:
                rec.village_domain = json.dumps([('id', 'in', rec.project_id.village_ids.ids)])
            else:
                rec.village_domain = json.dumps([])
    
    # Section 4 Notification reference
    section4_notification_id = fields.Many2one('bhu.section4.notification', string='Section 4 Notification',
                                               tracking=True, help='Select Section 4 Notification to auto-populate survey details')
    
    # Notification Details
    notification_number = fields.Char(string='Notification Number', readonly=True, tracking=True,
                                      help='Auto-generated notification number')
    prakaran_kramank = fields.Char(string='Prakaran Kramank / प्रकरण क्रमांक', required=False, tracking=True,
                                   help='Case number to be displayed in the report (optional)')
    publication_date = fields.Date(string='Publication Date', tracking=True)
    
    # Computed fields from Form 10 surveys
    total_khasras_count = fields.Integer(string='Total Khasras Count / कुल खसरा संख्या',
                                         compute='_compute_project_statistics', store=False)
    total_area_acquired = fields.Float(string='Total Area Acquired (Hectares) / रकबा (हेक्टेयर)',
                                       compute='_compute_project_statistics', store=False,
                                       digits=(16, 4))
    
    # Schedule/Table - Land Parcels (One2many)
    land_parcel_ids = fields.One2many('bhu.section11.land.parcel', 'report_id', 
                                      string='Land Parcels', tracking=True)
    
    # Computed fields for list view
    khasra_numbers = fields.Char(string='Khasra Numbers', compute='_compute_khasra_info', store=False)
    khasra_count = fields.Integer(string='Khasra Count', compute='_compute_khasra_info', store=False)
    survey_numbers = fields.Char(string='Survey Numbers', compute='_compute_survey_info', store=False)
    survey_date = fields.Date(string='Survey Date', compute='_compute_survey_info', store=False)
    
    # Survey IDs for read-only display (all non-rejected surveys for project + village)
    survey_ids = fields.Many2many('bhu.survey', string='Related Surveys / सर्वे', compute='_compute_survey_ids', store=False)
    
    @api.depends('project_id', 'village_id')
    def _compute_project_statistics(self):
        """Compute total khasras count and total area acquired from Form 10 surveys"""
        for record in self:
            if record.project_id and record.village_id:
                # Get all surveys for selected village in this project (exclude rejected)
                surveys = self.env['bhu.survey'].search([
                    ('project_id', '=', record.project_id.id),
                    ('village_id', '=', record.village_id.id),
                    ('khasra_number', '!=', False),
                    ('state', '!=', 'rejected'),
                ])
                
                # Count unique khasra numbers
                unique_khasras = set(surveys.mapped('khasra_number'))
                record.total_khasras_count = len(unique_khasras)
                
                # Sum acquired area
                record.total_area_acquired = sum(surveys.mapped('acquired_area'))
            else:
                record.total_khasras_count = 0
                record.total_area_acquired = 0.0
    
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
    
    @api.depends('village_id', 'project_id')
    def _compute_survey_info(self):
        """Compute survey numbers and date from related surveys"""
        for record in self:
            if record.village_id and record.project_id:
                surveys = self.env['bhu.survey'].search([
                    ('village_id', '=', record.village_id.id),
                    ('project_id', '=', record.project_id.id),
                    ('state', '=', 'locked')
                ], order='survey_date desc', limit=10)
                if surveys:
                    survey_names = surveys.mapped('name')
                    record.survey_numbers = ', '.join([s for s in survey_names if s])
                    record.survey_date = surveys[0].survey_date if surveys[0].survey_date else False
                else:
                    record.survey_numbers = ''
                    record.survey_date = False
            else:
                record.survey_numbers = ''
                record.survey_date = False
    
    @api.depends('village_id', 'project_id')
    def _compute_survey_ids(self):
        """Related Form 10 surveys for this village and project (excluding rejected)."""
        for record in self:
            if record.village_id and record.project_id:
                surveys = self.env['bhu.survey'].search([
                    ('village_id', '=', record.village_id.id),
                    ('project_id', '=', record.project_id.id),
                    ('state', '!=', 'rejected'),
                ], order='survey_date desc, khasra_number, id')
                record.survey_ids = surveys
            else:
                record.survey_ids = False
    
    # Paragraph 2: Claims/Objections Information - REMOVED (not needed)
    # paragraph_2_claims_info removed as per user request
    
    # Land Map Inspection - Read-only from project (not stored)
    map_inspection_location = fields.Char(string='Land Map Inspection / भूमि मानचित्र निरीक्षण',
                                                       related='project_id.map_inspection_location', readonly=True,
                                                       help='Location where land map can be inspected (SDO Revenue office)',
                                                       tracking=True)
    
    # Officer authorized by Section 12 - Read-only from project (not stored)
    authorized_officer = fields.Char(string='Officer authorized by Section 12 / धारा 12 द्वारा प्राधिकृत अधिकारी',
                                                related='project_id.authorized_officer', readonly=True,
                                                help='Officer authorized by Section 12',
                                                tracking=True)
    
    # Description of public purpose - REMOVED (not needed)
    
    # Displacement - Read-only from project (not stored)
    is_displacement = fields.Boolean(string='Is Displacement Involved? / कितने परिवारों का विस्थापन निहित है।',
                                                 related='project_id.is_displacement', readonly=True,
                                                 tracking=True)
    affected_families_count = fields.Integer(string='Affected Families Count / प्रभावित परिवारों की संख्या',
                                                         related='project_id.affected_families_count', readonly=True,
                                                         tracking=True)
    
    # Exemption or SIA Justification - Read-only from project (not stored)
    is_exemption = fields.Boolean(string='Is Exemption Granted? / क्या प्रस्तावित परियोजना के लिए अधिनियम 2013 के अध्याय "दो" एवं "तीन" के प्रावधानों से छूट प्रदान की गई है।',
                                               related='project_id.is_exemption', readonly=True,
                                               tracking=True)
    section5_text_type = fields.Selection(related='project_id.section5_text_type', readonly=True, tracking=True,
       string='Section 5 Text / धारा 5 पाठ',
       help='Select which text to display in Section 5 of the report')
    exemption_details = fields.Text(string='Exemption Details / छूट विवरण',
                                                 related='project_id.exemption_details', readonly=True,
                                                 help='Details of exemption notification (number, date, exempted chapters)',
                                                 tracking=True)
    sia_justification = fields.Text(string='SIA Justification / SIA औचित्य',
                                                related='project_id.sia_justification', readonly=True,
                                                help='SIA justification details (last resort, social benefits)',
                                                tracking=True)
    
    # Rehabilitation Administrator - Read-only from project (not stored)
    rehab_admin_name = fields.Char(string='Rehabilitation Administrator / पुनर्वास प्रशासक',
                                               related='project_id.rehab_admin_name', readonly=True,
                                               help='Name/Designation of Rehabilitation and Resettlement Administrator',
                                               tracking=True)
    
    def get_section5_text(self):
        """Get the text for section 5 based on the selected type"""
        self.ensure_one()
        if not self.section5_text_type:
            return ''
        # Get the selection label
        field = self._fields.get('section5_text_type')
        if field and field.selection:
            selection = field.selection
            if callable(selection):
                selection = selection(self)
            selection_dict = dict(selection) if selection else {}
            return selection_dict.get(self.section5_text_type, '')
        return ''
    
    # Signed document fields
    signed_document_file = fields.Binary(string='Signed Report')
    signed_document_filename = fields.Char(string='Signed File Name')
    signed_date = fields.Date(string='Signed Date', tracking=True)
    has_signed_document = fields.Boolean(string='Has Signed Document', 
                                         compute='_compute_has_signed_document', store=True)
    
    
    # UUID for QR code
    report_uuid = fields.Char(string='Report UUID', copy=False, readonly=True, index=True)
    
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
    
    @api.onchange('signed_document_file')
    def _onchange_signed_document_file(self):
        """Auto-change status to 'signed' when signed document is uploaded"""
        if self.signed_document_file and self.state != 'signed':
            self.state = 'signed'
            if not self.signed_date:
                self.signed_date = fields.Date.today()
    
    @api.onchange('village_id', 'project_id')
    def _onchange_village_populate_surveys(self):
        """Auto-populate land parcels when village or project changes"""
        # Auto-populate surveys when village or project changes
        if self.village_id and self.project_id:
            self._populate_land_parcels_from_surveys()
    
    def _populate_land_parcels_from_surveys(self):
        """Helper method to populate land parcels from locked surveys"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
            return
        
        # Always search directly for locked surveys for the selected village and project
        # This ensures we get the surveys even if Section 4's computed survey_ids is not ready
        locked_surveys = self.env['bhu.survey'].search([
            ('village_id', '=', self.village_id.id),
            ('project_id', '=', self.project_id.id),
            ('state', '=', 'locked')
        ], order='khasra_number')
        
        # If no locked surveys found, also check for approved surveys
        if not locked_surveys:
            locked_surveys = self.env['bhu.survey'].search([
                ('village_id', '=', self.village_id.id),
                ('project_id', '=', self.project_id.id),
                ('state', '=', 'approved')
            ], order='khasra_number')
        
        # Clear existing land parcels
        self.land_parcel_ids = [(5, 0, 0)]
        
        # Create land parcel records from locked/approved surveys
        parcel_vals = []
        for survey in locked_surveys:
            # Get department name for authorized officer if available
            authorized_officer = ''
            if survey.department_id:
                authorized_officer = survey.department_id.name or ''
            
            # Get public purpose from project if available
            public_purpose = ''
            if self.project_id:
                public_purpose = self.project_id.name or ''
            
            parcel_vals.append((0, 0, {
                'khasra_number': survey.khasra_number or '',
                'area_in_hectares': survey.acquired_area or 0.0,
                'authorized_officer': authorized_officer,
                'public_purpose_description': public_purpose,
                'village_id': survey.village_id.id,
            }))
        
        # Set the land parcels
        if parcel_vals:
            self.land_parcel_ids = parcel_vals
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        
        # Initialize village_domain to empty list if not set
        if 'village_domain' not in res or not res.get('village_domain'):
            res['village_domain'] = json.dumps([])
        
        # Get defaults from context (set by dashboard or other actions)
        if 'default_project_id' in self.env.context:
            project_id = self.env.context['default_project_id']
            res['project_id'] = project_id
            # Set domain based on project
            if project_id:
                project = self.env['bhu.project'].browse(project_id)
                if project.exists() and project.village_ids:
                    res['village_domain'] = json.dumps([('id', 'in', project.village_ids.ids)])
                else:
                    res['village_domain'] = json.dumps([])
        
        if 'default_village_id' in self.env.context:
            res['village_id'] = self.env.context['default_village_id']
        
        return res
    
    @api.model
    def _default_project_id(self):
        """Default project_id to PROJ01 if it exists, otherwise use first available project"""
        project = self.env['bhu.project'].search([('code', '=', 'PROJ01')], limit=1)
        if project:
            return project.id
        # Fallback to first available project if PROJ01 doesn't exist
        fallback_project = self.env['bhu.project'].search([], limit=1)
        return fallback_project.id if fallback_project else False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create records with batch support"""
        # Check for existing records to avoid unique constraint violations
        existing_records = []
        new_vals_list = []
        
        for vals in vals_list:
            # If section4_notification_id is provided, populate project_id and village_id from it
            section4_notification_id = vals.get('section4_notification_id')
            if section4_notification_id:
                section4_notif = self.env['bhu.section4.notification'].browse(section4_notification_id)
                if section4_notif.exists():
                    # Check if Section 4 is already in 'notification_11' status - prevent recreation
                    if section4_notif.state == 'notification_11':
                        raise ValidationError(_(
                            'Notification 11 has already been generated for this Section 4 Notification (%s). '
                            'Cannot create another Notification 11 for the same village and project.'
                        ) % section4_notif.name)
                    
                    # Set project_id from Section 4 if not already set
                    if not vals.get('project_id') and section4_notif.project_id:
                        vals['project_id'] = section4_notif.project_id.id
                    # Set village_id from Section 4 if not already set
                    if not vals.get('village_id') and section4_notif.village_id:
                        vals['village_id'] = section4_notif.village_id.id
                    # Don't use Section 4's notification number - generate new one using sequence master
                    # The notification_number will be generated below using the sequence master for section11_notification
            
            project_id = vals.get('project_id')
            village_id = vals.get('village_id')
            
            # Ensure required fields are set
            if not village_id and project_id:
                # Try to get from default if available
                project = self.env['bhu.project'].browse(project_id)
                if project and project.village_ids and len(project.village_ids) == 1:
                    # Auto-populate village if project has only one village
                    vals['village_id'] = project.village_ids[0].id
            
            # Generate sequence number for both name and notification_number
            sequence_number = None
            if project_id:
                village_id = vals.get('village_id')
                if village_id:
                    try:
                        village_id = int(village_id)
                        sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                            'section11_notification', project_id, village_id=village_id
                        )
                    except (ValueError, TypeError):
                        # If conversion fails, don't pass village_id
                        sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                            'section11_notification', project_id, village_id=None
                        )
                else:
                    # No village - don't pass village_id
                    sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'section11_notification', project_id, village_id=None
                    )
                
                if not sequence_number:
                    # Fallback to ir.sequence
                    sequence_number = self.env['ir.sequence'].next_by_code('bhu.section11.preliminary.report') or 'New'
            else:
                # No project_id, use fallback
                sequence_number = self.env['ir.sequence'].next_by_code('bhu.section11.preliminary.report') or 'New'
            
            # Set name and notification_number to the same sequence number
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                vals['name'] = sequence_number
            if not vals.get('notification_number'):
                vals['notification_number'] = sequence_number
            # Generate UUID if not provided
            if not vals.get('report_uuid'):
                vals['report_uuid'] = str(uuid.uuid4())
            new_vals_list.append(vals)
        
        # Create only new records
        records = super().create(new_vals_list) if new_vals_list else self.env['bhu.section11.preliminary.report']
        
        # Add existing records to the result
        if existing_records:
            records = records | self.env['bhu.section11.preliminary.report'].browse([r.id for r in existing_records])
        
        # Auto-populate land parcels after creation if village and project are set
        # Also update Section 4 Notification status to 'notification_11'
        for record in records:
            if record.village_id and record.project_id:
                record._populate_land_parcels_from_surveys()
            # Update Section 4 Notification status to 'notification_11' when Section 11 is created
            if record.section4_notification_id and record.section4_notification_id.state != 'notification_11':
                record.section4_notification_id.write({'state': 'notification_11'})
        return records
    
    # QR code generation is now handled by bhu.qr.code.mixin
    
    def action_populate_from_surveys(self):
        """Manually populate land parcels from surveys"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
            raise ValidationError(_('Please select Village and Project first.'))
        self._populate_land_parcels_from_surveys()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Land parcels have been populated from surveys.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _validate_required_fields(self):
        """Validate that all required fields in Questions tab are filled"""
        # Fields are now read-only from project master, so validation is not needed
        # All required fields should be filled at project level
        pass
    
    def action_generate_pdf(self):
        """Generate Section 11 Preliminary Report PDF - Creates separate notifications for each village with approved surveys"""
        self.ensure_one()
        
        # Validate required fields
        self._validate_required_fields()
        
        if not self.project_id:
            raise ValidationError(_('Please select a project first.'))
        
        if not self.village_id:
            raise ValidationError(_('Please select a village first.'))
        
        # Check if approved surveys exist for this village
        approved_surveys = self.env['bhu.survey'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', '=', 'approved')
        ], limit=1)
        
        if not approved_surveys:
            raise ValidationError(
                _('No approved surveys found for the selected village. Please ensure the village has approved surveys.')
            )
        
        # Check if Section 11 already exists for this project and village
        existing = self.env['bhu.section11.preliminary.report'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id)
        ], limit=1)
        
        if existing:
            raise ValidationError(
                _('A Section 11 Preliminary Report already exists for village "%s" in project "%s".') %
                (self.village_id.name, self.project_id.name)
            )
        
        # Update current record state to 'generated'
        self.write({'state': 'generated'})
        
        # Populate land parcels from approved surveys
        self._populate_land_parcels_from_surveys()
        
        # Add message to current record
        self.message_post(body=_('Section 11 Preliminary Report generated successfully for village %s.') % self.village_id.name)
        
        # Return to form view
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Section 11 Preliminary Report generated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_download_unsigned_file(self):
        """Generate and download Section 11 Preliminary Report PDF/Word (unsigned) - Override mixin"""
        self.ensure_one()
        return {
            'name': _('Download Section 11 Preliminary Report / धारा 11 प्रारंभिक रिपोर्ट डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_section11_preliminary',
                'default_filename': f'Section11_Report_{self.name}.doc'
            }
        }
    
    def action_download_pdf(self):
        """Download Section 11 Preliminary Report PDF - Legacy method"""
        return self.action_download_unsigned_file()
    
    
    @api.model
    def action_open_wizard(self):
        """Open wizard to generate new report - works without record selection"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Section 11 Preliminary Report',
            'res_model': 'bhu.section11.preliminary.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
    


class Section11LandParcel(models.Model):
    _name = 'bhu.section11.land.parcel'
    _description = 'Section 11 Land Parcel'
    _order = 'khasra_number'

    report_id = fields.Many2one('bhu.section11.preliminary.report', string='Report', required=True, ondelete='cascade')
    khasra_number = fields.Char(string='Khasra Number', required=True)
    area_in_hectares = fields.Float(string='Area (Hectares)', required=True, digits=(16, 4))
    authorized_officer = fields.Char(string='Authorized Officer',
                                     help='Officer authorized by Section 12')
    public_purpose_description = fields.Text(string='Public Purpose Description')
    
    # Related fields from report and village
    district_id = fields.Many2one('bhu.district', string='District', related='village_id.district_id', store=True, readonly=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil', related='village_id.tehsil_id', store=True, readonly=True)
    village_id = fields.Many2one('bhu.village', string='Village', required=True)
    project_id = fields.Many2one('bhu.project', string='Project', related='report_id.project_id', store=True, readonly=True)
    
    # Computed fields from related survey
    survey_number = fields.Char(string='Survey Number', compute='_compute_survey_info', store=False)
    survey_date = fields.Date(string='Survey Date', compute='_compute_survey_info', store=False)
    survey_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('locked', 'Locked'),
        ('rejected', 'Rejected'),
    ], string='Survey Status', compute='_compute_survey_info', store=False)
    
    @api.depends('khasra_number', 'village_id', 'report_id.project_id')
    def _compute_survey_info(self):
        """Compute survey number, date, and state from related survey"""
        for record in self:
            if record.khasra_number and record.village_id and record.report_id and record.report_id.project_id:
                survey = self.env['bhu.survey'].search([
                    ('khasra_number', '=', record.khasra_number),
                    ('village_id', '=', record.village_id.id),
                    ('project_id', '=', record.report_id.project_id.id),
                    ('state', 'in', ('locked', 'approved'))
                ], limit=1)
                if survey:
                    record.survey_number = survey.name or ''
                    record.survey_date = survey.survey_date or False
                    record.survey_state = survey.state or False
                else:
                    record.survey_number = ''
                    record.survey_date = False
                    record.survey_state = False
            else:
                record.survey_number = ''
                record.survey_date = False
                record.survey_state = False


class Section19Notification(models.Model):

    _name = 'bhu.section11.preliminary.wizard'
    _description = 'Section 11 Preliminary Report Wizard'

    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True)

    def action_generate_report(self):
        """Create Section 11 Preliminary Report record"""
        self.ensure_one()
        
        # Create the report record (village will be selected by user)
        report = self.env['bhu.section11.preliminary.report'].create({
            'project_id': self.project_id.id,
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

