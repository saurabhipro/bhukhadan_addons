# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from .. import utils
import uuid
import json


# Stub models for Process menu items - to be implemented later
# These are minimal models to allow the module to load

class Section4Notification(models.Model):
    _name = 'bhu.section4.notification'
    _description = 'Section 4 Notification'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.notification.mixin', 'bhu.process.workflow.mixin', 'bhu.qr.code.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Notification Name / अधिसूचना का नाम', default='New', tracking=True, readonly=True)
    notification_seq_number = fields.Char(string='Notification Sequence Number', readonly=True, tracking=True, 
                                          help='Sequence number for this notification')
    # Location fields inherited from bhu.process.workflow.mixin
    # Override project_id to add default and domain
    project_id = fields.Many2one(default=lambda self: self._default_project_id(), 
                                  domain="[('is_sia_exempt', '=', False)]")
    
    # Requiring Body - automatically populated from project's department
    requiring_body_id = fields.Many2one('bhu.department', string='Requiring Body / आवश्यक निकाय', 
                                       related='project_id.department_id', store=True, readonly=True, tracking=True,
                                       help='Requiring body/department (automatically populated from project)')
    
    # Department - computed from project (for filtering purposes)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', 
                                   related='project_id.department_id', store=True, readonly=True)
    
    village_domain = fields.Char(string='Village Domain', compute='_compute_village_domain', store=False, readonly=True)
    area_captured_from_form10 = fields.Float(string='Area Captured from Form 10 (Hectares) / फॉर्म 10 से कैप्चर किया गया क्षेत्रफल (हेक्टेयर)',
                                             compute='_compute_area_captured', store=False, digits=(16, 4), readonly=True)
    total_area = fields.Float(string='Total Area (Hectares) / कुल क्षेत्रफल (हेक्टेयर)',
                              compute='_compute_area_captured', store=False, digits=(16, 4), readonly=True)
    
    _sql_constraints = [
        ('unique_village_project', 'UNIQUE(village_id, project_id)', 
         'Only one Section 4 Notification can be created per village per project!')
    ]
    
    # Computed field to show surveys for selected villages
    survey_ids = fields.Many2many('bhu.survey', compute='_compute_survey_ids', string='Surveys', readonly=True)
    survey_count = fields.Integer(string='Survey Count', compute='_compute_survey_ids', readonly=True)
    approved_survey_count = fields.Integer(string='Approved Survey Count', compute='_compute_survey_ids', readonly=True)
    all_surveys_approved = fields.Boolean(string='All Surveys Approved', compute='_compute_survey_ids', readonly=True)
    has_pending_surveys = fields.Boolean(string="Has Pending Surveys", compute='_compute_survey_ids', readonly=True)
    has_no_surveys = fields.Boolean(string="Has No Surveys", compute='_compute_survey_ids', readonly=True)
    
    # Check if Section 11 exists for any of the villages (makes form read-only)
    has_section11 = fields.Boolean(string='Has Section 11', compute='_compute_has_section11', readonly=True)
    
    public_purpose = fields.Text(string='Public Purpose / लोक प्रयोजन का विवरण', 
                                 help='Description of public purpose for land acquisition', tracking=True)
    
    # Public Hearing Details
    public_hearing_datetime = fields.Datetime(string='Public Hearing Date & Time / जन सुनवाई दिनांक और समय', tracking=True)
    public_hearing_date = fields.Date(string='Public Hearing Date / सार्वजनिक सुनवाई दिनांक', tracking=True)
    public_hearing_time = fields.Char(string='Public Hearing Time / सार्वजनिक सुनवाई समय', tracking=True, required=True,
                                       help='Time in HH:MM:SS format')
    public_hearing_place = fields.Char(string='Public Hearing Place / जन सुनवाई स्थान', tracking=True)
    
    # 11 Questions from the template
    # brief_description removed - using project_id.name instead
    # Fields 2, 3, 4, 5, 8, 9, 10, 11 are read-only and come from project master (not stored)
    directly_affected = fields.Char(string='(दो) प्रत्यक्ष रूप से प्रभावित परिवारों की संख्या / Number of directly affected families', 
                                      related='project_id.directly_affected', readonly=True, tracking=True)
    indirectly_affected = fields.Char(string='(तीन) अप्रत्यक्ष रूप से प्रभावित परिवारों की संख्या / Number of indirectly affected families', 
                                         related='project_id.indirectly_affected', readonly=True, tracking=True)
    private_assets = fields.Char(string='(चार) प्रभावित क्षेत्र में निजी मकानों तथा अन्य परिसंपत्तियों की अनुमानित संख्या / Estimated number of private houses and other assets', 
                                    related='project_id.private_assets', readonly=True, tracking=True)
    government_assets = fields.Char(string='(पाँच) प्रभावित क्षेत्र में शासकीय मकान तथा अन्य परिसंपत्तियों की अनुमानित संख्या / Estimated number of government houses and other assets', 
                                       related='project_id.government_assets', readonly=True, tracking=True)
    minimal_acquisition = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं')
    ], string='(छः) क्या प्रस्तावित अर्जन न्यूनतम है? / Is the proposed acquisition minimal?', default='yes', readonly=True, tracking=True)
    alternatives_considered = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं')
    ], string='(सात) क्या संभव विकल्पों और इसकी साध्यता पर विचार कर लिया गया है? / Have possible alternatives and their feasibility been considered?', default='yes', readonly=True, tracking=True)
    total_cost = fields.Char(string='(आठ) परियोजना की कुल लागत / Total cost of the project', 
                                related='project_id.total_cost', readonly=True, tracking=True)
    project_benefits = fields.Text(string='(नौ) परियोजना से होने वाला लाभ / Benefits from the project', 
                                     related='project_id.project_benefits', readonly=True, tracking=True)
    compensation_measures = fields.Text(string='(दस) प्रस्तावित सामाजिक समाघात की प्रतिपूर्ति के लिये उपाय तथा उस पर होने वाला संभावित व्यय / Measures for compensation and likely expenditure', 
                                            related='project_id.compensation_measures', readonly=True, tracking=True)
    other_components = fields.Text(string='(ग्यारह) परियोजना द्वारा प्रभावित होने वाले अन्य घटक / Other components affected by the project', 
                                      related='project_id.other_components', readonly=True, tracking=True)
    
    # Signed document fields
    signed_document_file = fields.Binary(string='Signed Notification / हस्ताक्षरित अधिसूचना')
    signed_document_filename = fields.Char(string='Signed File Name / हस्ताक्षरित फ़ाइल नाम')
    signed_date = fields.Date(string='Signed Date / हस्ताक्षर दिनांक', tracking=True)
    has_signed_document = fields.Boolean(string='Has Signed Document / हस्ताक्षरित दस्तावेज़ है', compute='_compute_has_signed_document', store=True)
    
    
    # UUID for QR code
    notification_uuid = fields.Char(string='Notification UUID', copy=False, readonly=True, index=True)
    
    # State field is inherited from mixin (draft, submitted, approved, send_back)
    # Keep notification_11 as a computed field or separate flag if needed
    has_notification_11 = fields.Boolean(string='Has Notification 11', compute='_compute_has_section11', store=False)
    
    @api.depends('signed_document_file', 'state', 'signed_date')
    def _compute_has_signed_document(self):
        for record in self:
            # Consider it signed if there's a signed document file OR if state is 'signed'
            record.has_signed_document = bool(record.signed_document_file) or record.state == 'signed'
    
    @api.onchange('signed_document_file')
    def _onchange_signed_document_file(self):
        """Auto-change status to 'signed' when signed document is uploaded"""
        if self.signed_document_file and self.state != 'signed':
            self.state = 'signed'
            if not self.signed_date:
                self.signed_date = fields.Date.today()
    
    @api.depends('project_id')
    def _compute_village_domain(self):
        """Compute domain for village_id based on project"""
        for record in self:
            if record.project_id and record.project_id.village_ids:
                record.village_domain = json.dumps([('id', 'in', record.project_id.village_ids.ids)])
            else:
                record.village_domain = json.dumps([])
    
    @api.depends('project_id', 'village_id')
    def _compute_area_captured(self):
        """Compute total area and area captured from Form 10 surveys"""
        for record in self:
            if record.project_id and record.village_id:
                surveys = self.env['bhu.survey'].search([
                    ('project_id', '=', record.project_id.id),
                    ('village_id', '=', record.village_id.id),
                    ('state', 'in', ('approved', 'locked'))
                ])
                record.area_captured_from_form10 = sum(surveys.mapped('acquired_area'))
                record.total_area = sum(surveys.mapped('total_area'))
            else:
                record.area_captured_from_form10 = 0.0
                record.total_area = 0.0
    
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
                # Check for pending surveys (draft or submitted)
                pending_surveys = surveys.filtered(lambda s: s.state in ('draft', 'submitted'))
                record.has_pending_surveys = len(pending_surveys) > 0
                # Check if no surveys exist
                record.has_no_surveys = len(surveys) == 0
            else:
                record.survey_ids = [(5, 0, 0)]
                record.survey_count = 0
                record.approved_survey_count = 0
                record.all_surveys_approved = False
                record.has_pending_surveys = False
                record.has_no_surveys = False
    
    @api.onchange('public_hearing_date', 'public_hearing_time')
    def _onchange_hearing_date_time(self):
        """Sync separate date and time fields to datetime field"""
        if self.public_hearing_date and self.public_hearing_time:
            from datetime import datetime, timedelta
            try:
                # Expecting HH:MM:SS or HH:MM
                time_parts = self.public_hearing_time.split(':')
                hours = int(time_parts[0]) if len(time_parts) > 0 else 0
                minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
                seconds = int(time_parts[2]) if len(time_parts) > 2 else 0
                
                # Combine date and time
                self.public_hearing_datetime = datetime.combine(
                    self.public_hearing_date,
                    datetime.min.time()
                ) + timedelta(hours=hours, minutes=minutes, seconds=seconds)
            except (ValueError, IndexError):
                self.public_hearing_datetime = False
        else:
            self.public_hearing_datetime = False
    
    @api.depends('project_id', 'village_id')
    def _compute_has_section11(self):
        """Check if Section 11 Preliminary Report exists for the village"""
        for record in self:
            if record.project_id and record.village_id:
                section11_reports = self.env['bhu.section11.preliminary.report'].search([
                    ('project_id', '=', record.project_id.id),
                    ('village_id', '=', record.village_id.id)
                ], limit=1)
                record.has_section11 = bool(section11_reports)
            else:
                record.has_section11 = False
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village/tehsil when project changes (requiring_body_id auto-populates via related field)"""
        # If village is already set and is in the project's villages, keep it
        if self.project_id and self.project_id.village_ids:
            if self.village_id and self.village_id.id in self.project_id.village_ids.ids:
                # Village is valid, keep it
                pass
            else:
                # Village is not valid for this project, reset it
                self.village_id = False
        else:
            # No villages in project, reset village
            self.village_id = False
        
        # Reset tehsil when project changes (requiring_body_id auto-populates via related field)
        self.tehsil_id = False
    
    @api.onchange('village_id')
    def _onchange_village_id(self):
        """Auto-populate tehsil when village is selected"""
        if self.village_id and self.village_id.tehsil_id:
            self.tehsil_id = self.village_id.tehsil_id
    
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
        # Fallback to first available project if PROJ01 doesn't exist
        fallback_project = self.env['bhu.project'].search([], limit=1)
        return fallback_project.id if fallback_project else False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create records with batch support"""
        existing_records = []
        new_vals_list = []
        
        for vals in vals_list:
            # Clear default zero time to show placeholder
            if vals.get('public_hearing_time') in ('00:00', '0:00', '0:00:00', '00:00:00', '0.0', '0'):
                vals['public_hearing_time'] = False
            vals = self._sync_public_hearing_datetime_vals(vals)

            # Resolve project_id and village_id
            # Fields might be missing in vals if they are readonly in the view
            check_project_id = vals.get('project_id') or self.env.context.get('default_project_id')
            if not check_project_id:
                 check_project_id = self._default_project_id()
            
            check_village_id = vals.get('village_id') or self.env.context.get('default_village_id')
            
            # Check if project is SIA exempt
            if check_project_id:
                project = self.env['bhu.project'].browse(check_project_id)
                if project.is_sia_exempt:
                    raise ValidationError(_('Section 4 Notifications cannot be created for projects that are exempt from Social Impact Assessment.'))

            # Ensure vals has project_id (if we resolved it from context/default)
            # This ensures the SQL constraint checks the correct project
            if not vals.get('project_id') and check_project_id:
                vals['project_id'] = check_project_id
            
            # Assign resolved values to local variables for use in rest of method
            project_id = check_project_id
            village_id = check_village_id
            
            # Generate sequence number for notification_seq_number
            sequence_number = None
            # Try to use sequence settings from settings master
            if project_id:
                sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                    'section4_notification', project_id, village_id=village_id
                )
                if not sequence_number:
                    # Fallback to ir.sequence
                    sequence_number = self.env['ir.sequence'].next_by_code('bhu.section4.notification') or 'New'
            else:
                # No project_id, use fallback
                sequence_number = self.env['ir.sequence'].next_by_code('bhu.section4.notification') or 'New'
            
            # Set name and notification_seq_number
            if not vals.get('name'):
                vals['name'] = sequence_number
            if not vals.get('notification_seq_number'):
                vals['notification_seq_number'] = sequence_number
            
            if not vals.get('notification_uuid'):
                vals['notification_uuid'] = str(uuid.uuid4())
            # Set default project_id if not provided - always set it to avoid NOT NULL constraint violation
            if not vals.get('project_id'):
                project_id = self._default_project_id()
                if project_id:
                    vals['project_id'] = project_id
                else:
                    # If no project exists at all, we can't create the record
                    # This should not happen if sample_project_data.xml is loaded first
                    # But if it does, the post-init hook will fix it
                    # For now, we'll try to use any project as a last resort
                    any_project = self.env['bhu.project'].search([], limit=1)
                    if any_project:
                        vals['project_id'] = any_project.id
            new_vals_list.append(vals)
        
        # Create new records
        if new_vals_list:
            records = super().create(new_vals_list)
            # requiring_body_id is now automatically populated via related field
            # Tehsil will be computed automatically when village is selected
        else:
            records = self.env['bhu.section4.notification']
        
        if existing_records:
            records = records | self.env['bhu.section4.notification'].browse([r.id for r in existing_records])
        
        return records
    
    def _sync_public_hearing_datetime_vals(self, vals):
        """Keep public_hearing_datetime in sync with date + time Char fields (for PDF/reports)."""
        date_val = vals.get('public_hearing_date')
        time_val = vals.get('public_hearing_time')
        if date_val is None and time_val is None:
            return vals
        from datetime import datetime, timedelta
        record = self[:1] if self else self.env['bhu.section4.notification']
        hearing_date = date_val if date_val is not None else (record.public_hearing_date if record else False)
        hearing_time = time_val if time_val is not None else (record.public_hearing_time if record else False)
        if hearing_date and hearing_time:
            try:
                time_parts = str(hearing_time).split(':')
                hours = int(time_parts[0]) if len(time_parts) > 0 else 0
                minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
                seconds = int(time_parts[2]) if len(time_parts) > 2 else 0
                vals['public_hearing_datetime'] = datetime.combine(
                    fields.Date.to_date(hearing_date),
                    datetime.min.time(),
                ) + timedelta(hours=hours, minutes=minutes, seconds=seconds)
            except (ValueError, IndexError, TypeError):
                vals['public_hearing_datetime'] = False
        elif date_val is not None or time_val is not None:
            vals['public_hearing_datetime'] = False
        return vals

    def write(self, vals):
        """Override write method"""
        # Clear default zero time to show placeholder
        if vals.get('public_hearing_time') in ('00:00', '0:00', '0:00:00', '00:00:00', '0.0', '0'):
            vals['public_hearing_time'] = False
        vals = self._sync_public_hearing_datetime_vals(vals)
        result = super().write(vals)
        return result

    def _section4_approved_surveys(self):
        """Approved/locked surveys for this notification's project + village (sudo for PDF/report)."""
        self.ensure_one()
        if not self.project_id or not self.village_id:
            return self.env['bhu.survey']
        return self.env['bhu.survey'].sudo().search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ('approved', 'locked')),
        ], order='khasra_number asc, id asc')

    def get_approved_surveys_for_report(self):
        """Per-khasra rows for Section 4 PDF (public — callable from QWeb)."""
        self.ensure_one()
        rows = []
        for survey in self._section4_approved_surveys():
            if not survey.khasra_number:
                continue
            rows.append({
                'khasra_number': survey.khasra_number,
                'area': survey.acquired_area or 0.0,
                'survey_name': survey.name,
            })
        return rows

    def get_consolidated_village_data(self):
        """Village summary row for Section 4 PDF (public — callable from QWeb)."""
        return self._get_consolidated_village_data()

    def _get_consolidated_village_data(self):
        """Get consolidated survey data for the village"""
        self.ensure_one()
        surveys = self._section4_approved_surveys()
        if not self.village_id or not self.project_id or not surveys:
            return []

        district_name = (
            self.village_id.district_id.name
            if self.village_id.district_id
            else 'Raigarh (Chhattisgarh)'
        )
        tehsil_name = self.village_id.tehsil_id.name if self.village_id.tehsil_id else ''
        total_area = sum(surveys.mapped('acquired_area'))

        return [{
            'village_id': self.village_id.id,
            'village_name': self.village_id.name,
            'district': district_name,
            'tehsil': tehsil_name,
            'total_area': total_area,
            'surveys': surveys.ids,
        }]

    def get_formatted_hearing_date(self):
        """Format public hearing date and time for display"""
        self.ensure_one()
        if self.public_hearing_datetime:
            return self.public_hearing_datetime.strftime('%d/%m/%Y %I:%M %p')
        if self.public_hearing_date and self.public_hearing_time:
            return '%s %s' % (self.public_hearing_date.strftime('%d/%m/%Y'), self.public_hearing_time)
        return '........................'

    def get_formatted_hearing_date_only(self):
        """Format public hearing date only (for backward compatibility)"""
        self.ensure_one()
        if self.public_hearing_datetime:
            return self.public_hearing_datetime.strftime('%d/%m/%Y')
        if self.public_hearing_date:
            return self.public_hearing_date.strftime('%d/%m/%Y')
        return '........................'

    def get_formatted_hearing_time_only(self):
        """Format public hearing time only (for backward compatibility)"""
        self.ensure_one()
        if self.public_hearing_datetime:
            return self.public_hearing_datetime.strftime('%I:%M %p')
        if self.public_hearing_time:
            return self.public_hearing_time
        return '........................'
    
    # QR code generation is now handled by bhu.qr.code.mixin
    
    def _validate_required_fields(self):
        """Validate that all required fields are filled before generating PDF or submitting"""
        self.ensure_one()
        missing_fields = []
        
        # Basic Information fields
        # Public Purpose and Q1 are optional - removed validation
        if not self.public_hearing_datetime:
            missing_fields.append(_('Public Hearing Date & Time / सार्वजनिक सुनवाई की तारीख और समय'))
        if not self.public_hearing_place:
            missing_fields.append(_('Public Hearing Place / सार्वजनिक सुनवाई का स्थान'))
        
        # Section 4 Questions
        # Brief description is optional - removed validation
        if not self.directly_affected:
            missing_fields.append(_('Question 2: Directly Affected Families / प्रश्न 2: प्रत्यक्ष रूप से प्रभावित परिवार'))
        if not self.indirectly_affected:
            missing_fields.append(_('Question 3: Indirectly Affected Families / प्रश्न 3: अप्रत्यक्ष रूप से प्रभावित परिवार'))
        if not self.private_assets:
            missing_fields.append(_('Question 4: Private Assets / प्रश्न 4: निजी संपत्ति'))
        if not self.government_assets:
            missing_fields.append(_('Question 5: Government Assets / प्रश्न 5: सरकारी संपत्ति'))
        if not self.minimal_acquisition:
            missing_fields.append(_('Question 6: Is Acquisition Minimal? / प्रश्न 6: क्या अर्जन न्यूनतम है?'))
        if not self.alternatives_considered:
            missing_fields.append(_('Question 7: Alternatives Considered? / प्रश्न 7: विकल्पों पर विचार किया गया?'))
        if not self.total_cost:
            missing_fields.append(_('Question 8: Total Cost / प्रश्न 8: कुल लागत'))
        if not self.project_benefits:
            missing_fields.append(_('Question 9: Project Benefits / प्रश्न 9: परियोजना लाभ'))
        if not self.compensation_measures:
            missing_fields.append(_('Question 10: Compensation Measures / प्रश्न 10: मुआवजा उपाय'))
        if not self.other_components:
            missing_fields.append(_('Question 11: Other Components / प्रश्न 11: अन्य घटक'))
        
        if missing_fields:
            raise ValidationError(
                _('Please fill in all required fields before submitting to collector:\n\n%s') %
                '\n'.join(['- ' + field for field in missing_fields])
            )
    
    def action_submit(self):
        """Override mixin method to validate required fields before submitting"""
        self.ensure_one()
        
        # Validate all required fields are filled
        self._validate_required_fields()
        
        # Call parent method from mixin (validates SDM signed file and permissions)
        return super().action_submit()
    
    def _validate_state_to_submitted(self):
        """Override mixin method to validate required fields before submitting via statusbar"""
        # Call parent validation first (validates permissions and SDM signed file)
        super()._validate_state_to_submitted()
        
        # Then validate all required fields are filled
        self._validate_required_fields()
    
    def action_generate_pdf(self):
        """Generate Section 4 Notification PDF"""
        self.ensure_one()
        
        # Validate required fields
        self._validate_required_fields()
        
        # Validate that all surveys for selected village are approved
        if not self.project_id or not self.village_id:
            raise ValidationError(_('Please select a project and village.'))
        
        # Get all surveys for selected village
        all_surveys = self.env['bhu.survey'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id)
        ])
        
        if not all_surveys:
            raise ValidationError(_('No surveys found for the selected village. Please create surveys first.'))
        
        # Check if all surveys are approved
        non_approved_surveys = all_surveys.filtered(lambda s: s.state != 'approved')
        if non_approved_surveys:
            raise ValidationError(_(
                'Cannot generate Section 4 Notification. Some surveys are not approved yet.\n\n'
                'Please approve all surveys before generating the notification.'
            ))
        
        # Don't change state - keep it in draft until submitted
        # State will be changed when SDM submits to Collector
        
        # Use self to generate PDF directly (avoid transient wizard issues)
        report_action = self.env.ref('bhukhadan_core.action_report_section4_notification')
        return report_action.report_action(self)
    
    # Override mixin method to generate Section 4 PDF/Word
    def action_download_unsigned_file(self):
        """Generate and download Section 4 Notification PDF/Word (unsigned) - Override mixin"""
        self.ensure_one()
        return {
            'name': _('Download Section 4 Notification / धारा 4 अधिसूचना डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_section4_notification',
                'default_filename': f'Section4_Notification_{self.name}.doc'
            }
        }
    
    
    def action_download_pdf(self):
        """Download Section 4 Notification PDF (for generated/signed/notification_11 notifications)"""
        self.ensure_one()
        
        if self.state not in ('generated', 'signed', 'notification_11'):
            raise ValidationError(_('Notification must be generated before downloading.'))
        
        # If signed document exists, download it
        if self.signed_document_file:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/bhu.section4.notification/{self.id}/signed_document_file/{self.signed_document_filename or "signed_notification.pdf"}?download=true',
                'target': 'self',
            }
        
        # Otherwise, generate PDF/Word using wizard
        return {
            'name': _('Download Section 4 Notification / धारा 4 अधिसूचना डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_section4_notification',
                'default_filename': f'Section4_Notification_{self.name}.doc'
            }
        }


class Section4NotificationWizard(models.TransientModel):
    _name = 'bhu.section4.notification.wizard'
    _description = 'Section 4 Notification Wizard'
    _inherit = ['bhu.notification.mixin']

    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True)
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True)
    public_purpose = fields.Text(string='Public Purpose / लोक प्रयोजन का विवरण', 
                                 help='Description of public purpose for land acquisition')
    
    # Public Hearing Details
    public_hearing_datetime = fields.Datetime(string='Public Hearing Date & Time / जन सुनवाई दिनांक और समय')
    public_hearing_place = fields.Char(string='Public Hearing Place / जन सुनवाई स्थान')
    
    # 11 Questions from the template
    # brief_description removed - using project_id.name instead
    directly_affected = fields.Char(string='(दो) प्रत्यक्ष रूप से प्रभावित परिवारों की संख्या / Number of directly affected families')
    indirectly_affected = fields.Char(string='(तीन) अप्रत्यक्ष रूप से प्रभावित परिवारों की संख्या / Number of indirectly affected families')
    private_assets = fields.Char(string='(चार) प्रभावित क्षेत्र में निजी मकानों तथा अन्य परिसंपत्तियों की अनुमानित संख्या / Estimated number of private houses and other assets')
    government_assets = fields.Char(string='(पाँच) प्रभावित क्षेत्र में शासकीय मकान तथा अन्य परिसंपत्तियों की अनुमानित संख्या / Estimated number of government houses and other assets')
    minimal_acquisition = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं')
    ], string='(छः) क्या प्रस्तावित अर्जन न्यूनतम है? / Is the proposed acquisition minimal?', default='yes', readonly=True)
    alternatives_considered = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं')
    ], string='(सात) क्या संभव विकल्पों और इसकी साध्यता पर विचार कर लिया गया है? / Have possible alternatives and their feasibility been considered?', default='yes', readonly=True)
    total_cost = fields.Char(string='(आठ) परियोजना की कुल लागत / Total cost of the project')
    project_benefits = fields.Text(string='(नौ) परियोजना से होने वाला लाभ / Benefits from the project')
    compensation_measures = fields.Text(string='(दस) प्रस्तावित सामाजिक समाघात की प्रतिपूर्ति के लिये उपाय तथा उस पर होने वाला संभावित व्यय / Measures for compensation and likely expenditure')
    other_components = fields.Text(string='(ग्यारह) परियोजना द्वारा प्रभावित होने वाले अन्य घटक / Other components affected by the project')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes, set domain, and pull project-level fields"""
        self.village_id = False
        # Always set minimal_acquisition and alternatives_considered to 'yes'
        self.minimal_acquisition = 'yes'
        self.alternatives_considered = 'yes'
        # Pull project-level fields (directly_affected, indirectly_affected, private_assets, government_assets, total_cost, project_benefits, compensation_measures, other_components)
        if self.project_id:
            self.directly_affected = self.project_id.directly_affected
            self.indirectly_affected = self.project_id.indirectly_affected
            self.private_assets = self.project_id.private_assets
            self.government_assets = self.project_id.government_assets
            self.total_cost = self.project_id.total_cost
            self.project_benefits = self.project_id.project_benefits
            self.compensation_measures = self.project_id.compensation_measures
            self.other_components = self.project_id.other_components
            if self.project_id.village_ids:
                return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        else:
            # Clear project-level fields if no project selected
            self.directly_affected = False
            self.indirectly_affected = False
            self.private_assets = False
            self.government_assets = False
            self.total_cost = False
            self.project_benefits = False
            self.compensation_measures = False
            self.other_components = False
        return {'domain': {'village_id': []}}

    def get_approved_surveys_for_report(self):
        self.ensure_one()
        rows = []
        if not self.project_id or not self.village_id:
            return rows
        surveys = self.env['bhu.survey'].sudo().search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ('approved', 'locked')),
        ], order='khasra_number asc, id asc')
        for survey in surveys:
            if survey.khasra_number:
                rows.append({
                    'khasra_number': survey.khasra_number,
                    'area': survey.acquired_area or 0.0,
                    'survey_name': survey.name,
                })
        return rows

    def get_consolidated_village_data(self):
        return self._get_consolidated_village_data()

    def _get_consolidated_village_data(self):
        """Wizard fallback — delegates to notification helpers when linked fields exist."""
        self.ensure_one()
        if not self.project_id or not self.village_id:
            return []
        surveys = self.env['bhu.survey'].sudo().search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ('approved', 'locked')),
        ], order='khasra_number asc, id asc')
        if not surveys:
            return []
        district_name = (
            self.village_id.district_id.name
            if self.village_id.district_id
            else 'Raigarh (Chhattisgarh)'
        )
        tehsil_name = self.village_id.tehsil_id.name if self.village_id.tehsil_id else ''
        return [{
            'village_id': self.village_id.id,
            'village_name': self.village_id.name,
            'district': district_name,
            'tehsil': tehsil_name,
            'total_area': sum(surveys.mapped('acquired_area')),
            'surveys': surveys.ids,
        }]

    def get_formatted_hearing_date(self):
        """Format public hearing date and time for display"""
        self.ensure_one()
        if self.public_hearing_datetime:
            return self.public_hearing_datetime.strftime('%d/%m/%Y %I:%M %p')
        return '........................'

    def get_formatted_hearing_date_only(self):
        """Format public hearing date only (for backward compatibility)"""
        self.ensure_one()
        if self.public_hearing_datetime:
            return self.public_hearing_datetime.strftime('%d/%m/%Y')
        return '........................'

    def get_formatted_hearing_time_only(self):
        """Format public hearing time only (for backward compatibility)"""
        self.ensure_one()
        if self.public_hearing_datetime:
            return self.public_hearing_datetime.strftime('%I:%M %p')
        return '........................'

    def action_generate_pdf(self):
        """Generate Section 4 Notification PDF and create notification record"""
        self.ensure_one()
        
        if not self.village_id:
            raise ValidationError(_('Please select a village.'))
        
        # Get consolidated data
        consolidated_data = self._get_consolidated_village_data()
        
        if not consolidated_data:
            raise ValidationError(_('No approved surveys found for the selected village.'))
        
        # Create notification record
        notification = self.env['bhu.section4.notification'].create({
            'project_id': self.project_id.id,
            'village_id': self.village_id.id,
            'public_purpose': self.public_purpose,
            'public_hearing_datetime': self.public_hearing_datetime,
            'public_hearing_place': self.public_hearing_place,
            'state': 'generated',
        })
        
        # Generate PDF report - pass the persistent notification record
        report_action = self.env.ref('bhukhadan_core.action_report_section4_notification')
        return report_action.report_action(notification)


class ReportSection4Notification(models.AbstractModel):
    """Inject survey rows into Section 4 PDF (QWeb cannot rely on record method calls)."""

    _name = 'report.bhukhadan_core.section4_notification_report'
    _description = 'Section 4 Notification Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['bhu.section4.notification'].sudo().browse(docids)
        notification = docs[:1]
        consolidated_data = []
        surveys_data = []
        if notification:
            consolidated_data = notification.get_consolidated_village_data()
            surveys_data = notification.get_approved_surveys_for_report()
        return {
            'doc_ids': docids,
            'doc_model': 'bhu.section4.notification',
            'docs': docs,
            'notification': notification,
            'object': notification,
            'consolidated_data': consolidated_data,
            'surveys_data': surveys_data,
        }

