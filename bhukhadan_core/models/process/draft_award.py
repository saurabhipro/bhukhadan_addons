# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import uuid
import json

class DraftAward(models.Model):
    _name = 'bhu.draft.award'
    _description = 'Draft Award / अवार्ड आदेश'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Award Reference / अवार्ड संदर्भ', required=True, default='New', tracking=True, readonly=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade',
                                 default=lambda self: self._default_project_id())
    
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True, tracking=True)
    
    # District, Tehsil - computed from village
    district_id = fields.Many2one('bhu.district', string='District / जिला', compute='_compute_location', store=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील', compute='_compute_location', store=True)
    
    # Department - computed from project (for filtering purposes)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', 
                                   related='project_id.department_id', store=True, readonly=True)
    
    # Award Details
    award_number = fields.Char(string='Award Number / अवार्ड संख्या', tracking=True)
    
    # Void Title
    void_title = fields.Char(string='Void Title / शीर्षक', tracking=True,
                             help='Title field for the award document')
    
    # Applicant (Executive Engineer)
    applicant_name = fields.Char(string='Applicant Name / आवेदक का नाम', tracking=True,
                                 default='कार्यपालन अभियंता, केलो परियोजना सर्वेक्षण संभाग, जिला- रायगढ़ (छ.ग.)')
    applicant_designation = fields.Char(string='Applicant Designation / आवेदक का पद', tracking=True)
    
    # Respondents (Landowners) - computed from Section 11
    respondent_ids = fields.Many2many('bhu.landowner', string='Respondents / अनावेदक', 
                                     compute='_compute_respondents', store=False)
    
    # Land Parcels (One2many) - populated from Section 11
    land_parcel_ids = fields.One2many('bhu.draft.award.land.parcel', 'award_id',
                                      string='Land Parcels / भूमि खंड', tracking=True)
    
    # Computed total land area
    total_land_area = fields.Float(string='Total Land Area (Hectares) / कुल भूमि क्षेत्रफल (हेक्टेयर)',
                                    compute='_compute_total_land_area', store=True, digits=(16, 4))
    
    # Section 11 Reference
    section11_report_id = fields.Many2one('bhu.section11.preliminary.report', 
                                          string='Section 11 Report / धारा 11 रिपोर्ट',
                                          compute='_compute_section11_report', store=True)
    
    
    # Publication Details
    section11_gazette_date = fields.Date(string='Section 11 Gazette Date / धारा 11 राजपत्र दिनांक', tracking=True)
    section11_gazette_part = fields.Char(string='Section 11 Gazette Part / धारा 11 राजपत्र भाग', tracking=True,
                                         help='e.g., Part-1')
    section11_gazette_page = fields.Char(string='Section 11 Gazette Page / धारा 11 राजपत्र पृष्ठ', tracking=True,
                                         help='e.g., Page No. 488')
    section11_newspaper_1_name = fields.Char(string='Newspaper 1 Name / समाचार पत्र 1 का नाम', tracking=True,
                                              help='e.g., नवभारत')
    section11_newspaper_1_date = fields.Date(string='Newspaper 1 Date / समाचार पत्र 1 दिनांक', tracking=True)
    section11_newspaper_2_name = fields.Char(string='Newspaper 2 Name / समाचार पत्र 2 का नाम', tracking=True,
                                              help='e.g., कांतिकारी संकेत')
    section11_newspaper_2_date = fields.Date(string='Newspaper 2 Date / समाचार पत्र 2 दिनांक', tracking=True)
    section11_munadi_date = fields.Date(string='Section 11 Munadi Date / धारा 11 मुनादी दिनांक', tracking=True)
    
    section19_gazette_date = fields.Date(string='Section 19 Gazette Date / धारा 19 राजपत्र दिनांक', tracking=True)
    section19_gazette_part = fields.Char(string='Section 19 Gazette Part / धारा 19 राजपत्र भाग', tracking=True)
    section19_gazette_page = fields.Char(string='Section 19 Gazette Page / धारा 19 राजपत्र पृष्ठ', tracking=True)
    section19_newspaper_1_name = fields.Char(string='Section 19 Newspaper 1 Name', tracking=True)
    section19_newspaper_1_date = fields.Date(string='Section 19 Newspaper 1 Date', tracking=True)
    section19_newspaper_2_name = fields.Char(string='Section 19 Newspaper 2 Name', tracking=True)
    section19_newspaper_2_date = fields.Date(string='Section 19 Newspaper 2 Date', tracking=True)
    section19_munadi_date = fields.Date(string='Section 19 Munadi Date', tracking=True)
    
    section21_notice_date = fields.Date(string='Section 21 Notice Date / धारा 21 नोटिस दिनांक', tracking=True)
    section21_hearing_date = fields.Date(string='Section 21 Hearing Date / धारा 21 सुनवाई दिनांक', tracking=True)
    
    # Compensation Details
    total_compensation_amount = fields.Float(string='Total Compensation Amount / कुल मुआवजा राशि',
                                              digits=(16, 2), tracking=True,
                                              compute='_compute_total_compensation', store=True)
    compensation_amount_text = fields.Char(string='Compensation Amount (Text) / मुआवजा राशि (पाठ)',
                                          tracking=True,
                                          help='Amount in words, e.g., उन्नीस लाख चौसठ हजार सात सौ बियालीस रुपये मात्र')
    
    # Detailed Compensation Lines (One2many)
    compensation_line_ids = fields.One2many('bhu.draft.award.compensation.line', 'award_id',
                                            string='Compensation Details / मुआवजा विवरण', tracking=True)
    
    # Displacement
    is_displacement_involved = fields.Boolean(string='Is Displacement Involved? / क्या विस्थापन शामिल है?',
                                              default=False, tracking=True)
    
    # Signed document fields
    signed_document_file = fields.Binary(string='Signed Award / हस्ताक्षरित अवार्ड')
    signed_document_filename = fields.Char(string='Signed File Name / हस्ताक्षरित फ़ाइल नाम')
    signed_date = fields.Date(string='Signed Date / हस्ताक्षर दिनांक', tracking=True)
    has_signed_document = fields.Boolean(string='Has Signed Document / हस्ताक्षरित दस्तावेज़ है',
                                         compute='_compute_has_signed_document', store=True)
    
    # Officer signature
    officer_signature = fields.Binary(string='Officer Signature / अधिकारी हस्ताक्षर')
    officer_signature_filename = fields.Char(string='Signature File Name')
    officer_name = fields.Char(string='Officer Name / अधिकारी का नाम', tracking=True,
                               default='अनुविभागीय अधिकारी (राजस्व) एवं अनुविभागीय अधिकारी (भू-अर्जन) रायगढ़')
    officer_designation = fields.Char(string='Officer Designation / अधिकारी का पद', tracking=True)
    
    # UUID for QR code
    award_uuid = fields.Char(string='Award UUID', copy=False, readonly=True, index=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('signed', 'Signed'),
    ], string='Status', default='draft', tracking=True)
    
    # Computed fields for edit permissions (similar to process workflow mixin)
    is_sdm = fields.Boolean(string='Is SDM', compute='_compute_user_roles', store=False)
    is_collector = fields.Boolean(string='Is Collector', compute='_compute_user_roles', store=False)
    can_sdm_edit = fields.Boolean(string='Can SDM Edit', compute='_compute_edit_permissions', store=False,
                                   help='SDM can edit when state is draft or generated, readonly when signed')
    can_collector_edit = fields.Boolean(string='Can Collector Edit', compute='_compute_edit_permissions', store=False,
                                        help='Collector can edit when state is generated, readonly when signed')
    
    @api.depends()
    def _compute_user_roles(self):
        """Compute if current user is SDM or Collector"""
        current_user = self.env.user
        is_sdm_user = current_user.has_group('bhukhadan_core.group_bhuarjan_sdm')
        is_collector_user = current_user.has_group('bhukhadan_core.group_bhuarjan_collector')
        
        for record in self:
            record.is_sdm = is_sdm_user
            record.is_collector = is_collector_user
    
    @api.depends('state', 'is_sdm', 'is_collector')
    def _compute_edit_permissions(self):
        """Compute edit permissions based on state and user role"""
        for record in self:
            # SDM can edit when state is 'draft' or 'generated', readonly when 'signed'
            record.can_sdm_edit = record.is_sdm and record.state in ('draft', 'generated')
            
            # Collector can edit when state is 'generated', readonly when 'signed'
            record.can_collector_edit = record.is_collector and record.state == 'generated'
    
    _sql_constraints = [
        ('unique_village_project', 'UNIQUE(village_id, project_id)', 
         'Only one Draft Award can be created per village per project! / प्रति ग्राम प्रति परियोजना केवल एक अवार्ड बनाया जा सकता है!')
    ]
    
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
    def _compute_location(self):
        """Compute district and tehsil from village"""
        for record in self:
            if record.village_id:
                record.district_id = record.village_id.district_id.id if record.village_id.district_id else False
                record.tehsil_id = record.village_id.tehsil_id.id if record.village_id.tehsil_id else False
            else:
                record.district_id = False
                record.tehsil_id = False
    
    @api.depends('village_id', 'project_id')
    def _compute_section11_report(self):
        """Find Section 11 report for this village and project"""
        for record in self:
            if record.village_id and record.project_id:
                section11 = self.env['bhu.section11.preliminary.report'].search([
                    ('village_id', '=', record.village_id.id),
                    ('project_id', '=', record.project_id.id),
                    ('state', 'in', ['generated', 'signed'])
                ], limit=1, order='create_date desc')
                record.section11_report_id = section11.id if section11 else False
            else:
                record.section11_report_id = False
    
    
    village_domain = fields.Char()
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Clear Section 19 selection when project changes"""

        for rec in self:
            if rec.project_id and rec.project_id.village_ids:
                rec.village_domain = json.dumps([('id', 'in', rec.project_id.village_ids.ids)])
            else:
                rec.village_domain = json.dumps([])   # empty domain
                rec.village_id = False


    
    @api.depends('village_id', 'project_id')
    def _compute_respondents(self):
        """Compute respondents (landowners) from Section 11 land parcels"""
        for record in self:
            if record.section11_report_id and record.section11_report_id.land_parcel_ids:
                # Get all surveys for the khasras in Section 11
                khasra_numbers = record.section11_report_id.land_parcel_ids.mapped('khasra_number')
                surveys = self.env['bhu.survey'].search([
                    ('village_id', '=', record.village_id.id),
                    ('project_id', '=', record.project_id.id),
                    ('khasra_number', 'in', khasra_numbers),
                    ('state', '=', 'locked')
                ])
                # Get unique landowners from these surveys
                landowner_ids = surveys.mapped('landowner_ids')
                record.respondent_ids = landowner_ids
            else:
                record.respondent_ids = False
    
    @api.depends('land_parcel_ids.area_hectares', 'land_parcel_ids.khasra_number')
    def _compute_total_land_area(self):
        """Compute total land area from land parcels"""
        for record in self:
            record.total_land_area = sum(record.land_parcel_ids.mapped('area_hectares'))
    
    @api.depends('compensation_line_ids.payable_compensation_amount')
    def _compute_total_compensation(self):
        """Compute total compensation from compensation lines"""
        for record in self:
            record.total_compensation_amount = sum(record.compensation_line_ids.mapped('payable_compensation_amount'))
    
    @api.onchange('village_id', 'project_id')
    def _onchange_village_populate_land_parcels(self):
        """Auto-populate land parcels from Section 11 when village/project changes (only if Section 19 is not selected)"""
        # Populate from Section 11
        self._populate_land_parcels_from_section11()
    
    def _populate_land_parcels_from_section11(self):
        """Helper method to populate land parcels from Section 11 report"""
        self.ensure_one()
        if not self.village_id or not self.project_id:
            return
        
        # Find Section 11 report
        section11 = self.env['bhu.section11.preliminary.report'].search([
            ('village_id', '=', self.village_id.id),
            ('project_id', '=', self.project_id.id),
            ('state', 'in', ['generated', 'signed'])
        ], limit=1, order='create_date desc')
        
        if not section11 or not section11.land_parcel_ids:
            return
        
        # Clear existing land parcels
        self.land_parcel_ids = [(5, 0, 0)]
        
        # Create land parcel records from Section 11
        parcel_vals = []
        for parcel in section11.land_parcel_ids:
            parcel_vals.append((0, 0, {
                'khasra_number': parcel.khasra_number or '',
                'area_hectares': parcel.area_in_hectares or 0.0,
            }))
        
        # Set the land parcels
        if parcel_vals:
            self.land_parcel_ids = parcel_vals
        
        # Auto-populate compensation lines after land parcels are set
        self._populate_compensation_lines()
    
    def _populate_compensation_lines(self):
        """Helper method to populate compensation lines from land parcels and surveys"""
        self.ensure_one()
        if not self.land_parcel_ids:
            return
        
        # Clear existing compensation lines
        self.compensation_line_ids = [(5, 0, 0)]
        
        # Get all surveys for the khasras in land parcels
        khasra_numbers = self.land_parcel_ids.mapped('khasra_number')
        surveys = self.env['bhu.survey'].search([
            ('village_id', '=', self.village_id.id),
            ('project_id', '=', self.project_id.id),
            ('khasra_number', 'in', khasra_numbers),
            ('state', '=', 'locked')
        ])
        
        # Create compensation line for each survey
        line_vals = []
        serial = 1
        for survey in surveys:
            # Get land parcel for this khasra
            parcel = self.land_parcel_ids.filtered(lambda p: p.khasra_number == survey.khasra_number)
            if not parcel:
                continue
            
            # Create a line for each landowner
            for landowner in survey.landowner_ids:
                # Determine land type
                is_irrigated = survey.irrigation_type == 'irrigated'
                is_unirrigated = survey.irrigation_type == 'unirrigated'
                
                line_vals.append((0, 0, {
                    'serial_number': serial,
                    'landowner_id': landowner.id,
                    'khasra_number': survey.khasra_number or '',
                    'acquired_area': parcel[0].area_hectares or 0.0,
                    'is_irrigated': is_irrigated,
                    'is_unirrigated': is_unirrigated,
                    'is_fallow': False,  # Default, can be updated manually
                    'total_held_khasra': survey.khasra_number or '',
                    'total_held_area': survey.total_area or 0.0,
                    'acquired_revenue': 0.0,  # Can be updated manually
                }))
                serial += 1
        
        # Set the compensation lines
        if line_vals:
            self.compensation_line_ids = line_vals
    
    @api.model
    def _default_project_id(self):
        """Default project_id to PROJ01 if it exists"""
        project = self.env['bhu.project'].search([('code', '=', 'PROJ01')], limit=1)
        if project:
            return project.id
        fallback_project = self.env['bhu.project'].search([], limit=1)
        return fallback_project.id if fallback_project else False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create records with batch support"""
        for vals in vals_list:
            # Populate village and project if provided
            # Populate village and project if provided
            if 'village_id' in vals or 'project_id' in vals:
                pass
            
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                # Try to use sequence settings from settings master
                project_id = vals.get('project_id')
                village_id = vals.get('village_id')
                if project_id:
                    sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'draft_award', project_id, village_id=village_id
                    )
                    if sequence_number:
                        vals['name'] = sequence_number
                    else:
                        # Fallback to ir.sequence
                        vals['name'] = self.env['ir.sequence'].next_by_code('bhu.draft.award') or 'New'
                else:
                    # No project_id, use fallback
                    vals['name'] = self.env['ir.sequence'].next_by_code('bhu.draft.award') or 'New'
            # Generate UUID if not provided
            if not vals.get('award_uuid'):
                vals['award_uuid'] = str(uuid.uuid4())
            # Set default project_id if not provided
            if not vals.get('project_id'):
                project_id = self._default_project_id()
                if project_id:
                    vals['project_id'] = project_id
        records = super().create(vals_list)
        # Auto-populate land parcels after creation
        for record in records:
            if record.village_id and record.project_id:
                # Populate from Section 11 (old method)
                record._populate_land_parcels_from_section11()
        return records
    
    def get_qr_code_data(self):
        """Generate QR code data for the award"""
        try:
            import qrcode
            import io
            import base64
            
            # Ensure UUID exists
            if not self.award_uuid:
                self.write({'award_uuid': str(uuid.uuid4())})
            
            # Generate QR code URL - using award UUID
            qr_url = f"https://bhuarjan.com/bhuarjan/draftaward/{self.award_uuid}/download"
            
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=2,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # Generate image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return img_str
        except ImportError:
            return None
        except Exception as e:
            return None
    
    def action_populate_compensation(self):
        """Manually populate compensation lines"""
        self.ensure_one()
        if not self.land_parcel_ids:
            raise ValidationError(_('Please populate land parcels first from Section 11.'))
        self._populate_compensation_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Compensation lines have been populated.'),
                'type': 'success',
            }
        }
    
    def action_generate_pdf(self):
        """Generate Draft Award PDF"""
        self.ensure_one()
        # Ensure compensation lines are populated before generating PDF
        if not self.compensation_line_ids and self.land_parcel_ids:
            self._populate_compensation_lines()
        self.state = 'generated'
        return self.env.ref('bhukhadan_core.action_report_draft_award').report_action(self)
    
    def action_generate_notices(self):
        """Generate Notices for this award"""
        self.ensure_one()
        # Open wizard to generate notices
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Notices / नोटिस जेनरेट करें',
            'res_model': 'bhu.generate.notices.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_village_ids': [(6, 0, [self.village_id.id])] if self.village_id else [],
            }
        }
    
    def action_download_notices(self):
        """Download Notices for this award"""
        self.ensure_one()
        # Open wizard to download notices
        return {
            'type': 'ir.actions.act_window',
            'name': 'Download Notices / नोटिस डाउनलोड करें',
            'res_model': 'bhu.download.notices.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_village_id': self.village_id.id if self.village_id else False,
            }
        }
    
    def action_mark_signed(self):
        """Mark award as signed"""
        self.ensure_one()
        if not self.signed_document_file:
            raise ValidationError(_('Please upload signed document first.'))
        self.state = 'signed'
        if not self.signed_date:
            self.signed_date = fields.Date.today()
    
    def action_open_generate_award_notification(self):
        """Open Generate Award Notification wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Award Notification / पुरस्कार अधिसूचना जेनरेट करें',
            'res_model': 'bhu.award.notification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_village_ids': [(6, 0, [self.village_id.id])],
            }
        }
    
    def action_open_download_award_notification(self):
        """Open Download Award Notification wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Download Award Notification / पुरस्कार अधिसूचना डाउनलोड करें',
            'res_model': 'bhu.download.award.notification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_village_id': self.village_id.id,
            }
        }


class DraftAwardLandParcel(models.Model):
    _name = 'bhu.draft.award.land.parcel'
    _description = 'Draft Award Land Parcel'
    _order = 'khasra_number'

    award_id = fields.Many2one('bhu.draft.award', string='Award', required=True, ondelete='cascade')
    khasra_number = fields.Char(string='Khasra Number / खसरा नंबर', required=True)
    area_hectares = fields.Float(string='Area (Hectares) / रकबा (हेक्टेयर में)', required=True, digits=(16, 4))
    
    # Additional fields from Section 19
    survey_number = fields.Char(string='Survey Number / सर्वे नंबर')
    survey_date = fields.Date(string='Survey Date / सर्वे दिनांक')
    survey_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('locked', 'Locked'),
        ('rejected', 'Rejected'),
    ], string='Survey Status / सर्वे स्थिति')
    
    # Location fields
    district_id = fields.Many2one('bhu.district', string='District / जिला')
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम')
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना')
    
    # Additional details
    authorized_officer = fields.Char(string='Authorized Officer / प्राधिकृत अधिकारी',
                                    help='Officer authorized by Section 12')
    public_purpose_description = fields.Text(string='Public Purpose Description / लोक प्रयोजन विवरण')


class DraftAwardCompensationLine(models.Model):
    _name = 'bhu.draft.award.compensation.line'
    _description = 'Draft Award Compensation Line / अवार्ड मुआवजा पंक्ति'
    _order = 'serial_number, khasra_number'

    award_id = fields.Many2one('bhu.draft.award', string='Award', required=True, ondelete='cascade')
    
    # Serial Number
    serial_number = fields.Integer(string='Serial Number / क्र.', required=True, default=1)
    
    # Landowner Details
    landowner_id = fields.Many2one('bhu.landowner', string='Landowner / भूमिस्वामी', required=False, ondelete='set null')
    landowner_name = fields.Char(string='Landowner Name / भूमिस्वामी का नाम', related='landowner_id.name', store=True, readonly=True)
    father_husband_name = fields.Char(string='Father/Husband Name / पिता/पति का नाम', compute='_compute_father_husband_name', store=True)
    caste = fields.Char(string='Caste / जाति', help='Enter caste information')
    
    @api.depends('landowner_id')
    def _compute_father_husband_name(self):
        """Compute father/husband name from landowner"""
        for record in self:
            if record.landowner_id:
                # Use father_name if available, otherwise spouse_name
                record.father_husband_name = record.landowner_id.father_name or record.landowner_id.spouse_name or ''
            else:
                record.father_husband_name = ''
    
    # Total Held Land / कुल धारित भूमि
    total_held_khasra = fields.Char(string='Total Held Khasra / कुल धारित ख.न.')
    total_held_area = fields.Float(string='Total Held Area (Hectares) / कुल धारित रकबा (हेक्टेयर)', digits=(16, 4))
    total_held_revenue = fields.Float(string='Total Held Revenue / कुल धारित लगान', digits=(16, 2))
    
    # Acquired Land Details / अर्जित भूमि का विवरण
    khasra_number = fields.Char(string='Acquired Khasra Number / अर्जित ख.न.', required=True)
    acquired_area = fields.Float(string='Acquired Area (Hectares) / अर्जित रकबा (हेक्टेयर)', required=True, digits=(16, 4))
    acquired_revenue = fields.Float(string='Acquired Revenue / अर्जित लगान', digits=(16, 2))
    
    # Land Type / अर्जित भूमि का प्रकार
    is_fallow = fields.Boolean(string='Fallow / पड़त', default=False)
    is_unirrigated = fields.Boolean(string='Unirrigated / असिंचित', default=False)
    is_irrigated = fields.Boolean(string='Irrigated / सिंचित', default=False)
    
    # Guide Line Compensation / गाईड लाइन मुआवजा
    guideline_rate_per_hectare = fields.Float(string='Guide Line Rate per Hectare / गाईड लाइन दर प्रति हेक्टेयर',
                                               digits=(16, 2), help='Guide Line March 2023-2024')
    guideline_compensation_value = fields.Float(string='Guide Line Compensation Value / गाईड लाइन मूल्य',
                                                digits=(16, 2), compute='_compute_compensation', store=True)
    
    # Market Value Calculations / बाजार मूल्य गणना
    market_value = fields.Float(string='Market Value / मूल्य', digits=(16, 2), compute='_compute_compensation', store=True)
    market_value_factor_2 = fields.Float(string='Market Value x (Factor-2) / बाजार मूल्य x (कारक-2)',
                                         digits=(16, 2), compute='_compute_compensation', store=True)
    
    # Solatium / सोलेशियम
    solatium_percentage = fields.Float(string='Solatium Percentage / सोलेशियम प्रतिशत', default=100.0, digits=(5, 2))
    solatium_amount = fields.Float(string='100% Solatium Amount / 100% सोलेशियम की राशि',
                                   digits=(16, 2), compute='_compute_compensation', store=True)
    
    # Interest / ब्याज
    interest_start_date = fields.Date(string='Interest Start Date / ब्याज प्रारंभ दिनांक')
    interest_end_date = fields.Date(string='Interest End Date / ब्याज समाप्ति दिनांक')
    interest_months = fields.Integer(string='Interest Months / ब्याज माह', compute='_compute_interest_months', store=True)
    interest_rate = fields.Float(string='Interest Rate / ब्याज दर', default=30.0, digits=(5, 2),
                                 help='Interest rate as per Section 30(3)')
    interest_amount = fields.Float(string='Interest Amount / ब्याज राशि', digits=(16, 2),
                                   compute='_compute_compensation', store=True)
    
    # Total Determined Compensation / कुल निर्धारित मुआवजा
    total_determined_compensation = fields.Float(string='Total Determined Compensation / कुल निर्धारित मुआवजा',
                                                  digits=(16, 2), compute='_compute_compensation', store=True)
    
    # Rehabilitation Policy / पुनर्वास नीति
    rehab_policy_rate_per_acre = fields.Float(string='Rehab Policy Rate per Acre / पुनर्वास नीति दर प्रति एकड़',
                                              digits=(16, 2))
    rehab_policy_compensation = fields.Float(string='Rehab Policy Compensation / पुनर्वास नीति मुआवजा',
                                             digits=(16, 2), compute='_compute_compensation', store=True)
    
    # Payable Compensation / देय मुआवजा
    payable_compensation_amount = fields.Float(string='Payable Compensation / देय मुआवजा राशि',
                                             digits=(16, 2), compute='_compute_compensation', store=True)
    
    # Remarks / रिमार्क
    remark = fields.Text(string='Remark / रिमार्क')
    
    @api.depends('interest_start_date', 'interest_end_date')
    def _compute_interest_months(self):
        """Compute interest months from start and end dates"""
        for record in self:
            if record.interest_start_date and record.interest_end_date:
                delta = relativedelta(record.interest_end_date, record.interest_start_date)
                record.interest_months = delta.years * 12 + delta.months
            else:
                record.interest_months = 0
    
    @api.depends('acquired_area', 'guideline_rate_per_hectare', 'market_value_factor_2', 
                 'solatium_percentage', 'interest_rate', 'interest_months', 'market_value',
                 'rehab_policy_rate_per_acre')
    def _compute_compensation(self):
        """Compute all compensation amounts"""
        for record in self:
            # Guide Line Compensation Value
            if record.acquired_area and record.guideline_rate_per_hectare:
                record.guideline_compensation_value = record.acquired_area * record.guideline_rate_per_hectare
            else:
                record.guideline_compensation_value = 0.0
            
            # Market Value (use guideline value as base)
            record.market_value = record.guideline_compensation_value
            
            # Market Value x Factor-2
            record.market_value_factor_2 = record.market_value * 2.0
            
            # Solatium (100% of market value factor-2)
            record.solatium_amount = record.market_value_factor_2 * (record.solatium_percentage / 100.0)
            
            # Interest (on market value factor-2, as per Section 30(3))
            if record.interest_months > 0 and record.interest_rate > 0:
                monthly_rate = record.interest_rate / 12.0
                record.interest_amount = record.market_value_factor_2 * (monthly_rate / 100.0) * record.interest_months
            else:
                record.interest_amount = 0.0
            
            # Total Determined Compensation
            record.total_determined_compensation = (record.market_value_factor_2 + 
                                                     record.solatium_amount + 
                                                     record.interest_amount)
            
            # Rehabilitation Policy Compensation (convert hectares to acres: 1 hectare = 2.471 acres)
            if record.acquired_area and record.rehab_policy_rate_per_acre:
                area_in_acres = record.acquired_area * 2.471
                record.rehab_policy_compensation = area_in_acres * record.rehab_policy_rate_per_acre
            else:
                record.rehab_policy_compensation = 0.0
            
            # Payable Compensation (higher of total determined or rehab policy)
            record.payable_compensation_amount = max(record.total_determined_compensation, 
                                                    record.rehab_policy_compensation)


class GenerateNoticesWizard(models.TransientModel):
    _name = 'bhu.generate.notices.wizard'
    _description = 'Generate Notices Wizard'

    project_id = fields.Many2one('bhu.project', string='Project', required=True)
    village_ids = fields.Many2many('bhu.village', string='Villages')

    def action_generate_notices(self):
        """Generate Notices - To be implemented"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Notice generation will be implemented soon.'),
                'type': 'info',
            }
        }


class DownloadNoticesWizard(models.TransientModel):
    _name = 'bhu.download.notices.wizard'
    _description = 'Download Notices Wizard'

    project_id = fields.Many2one('bhu.project', string='Project')
    village_id = fields.Many2one('bhu.village', string='Village')
    landowner_id = fields.Many2one('bhu.landowner', string='Landowner')

    def action_download_notices(self):
        """Download Notices - To be implemented"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Notice download will be implemented soon.'),
                'type': 'info',
            }
        }


class AwardNotificationWizard(models.TransientModel):
    _name = 'bhu.award.notification.wizard'
    _description = 'Award Notification Wizard'

    project_id = fields.Many2one('bhu.project', string='Project', required=True)
    village_ids = fields.Many2many('bhu.village', string='Villages', required=True)

    def action_generate_award_notification(self):
        """Generate Award Notification - To be implemented"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Award notification generation will be implemented soon.'),
                'type': 'info',
            }
        }


class DownloadAwardNotificationWizard(models.TransientModel):
    _name = 'bhu.download.award.notification.wizard'
    _description = 'Download Award Notification Wizard'

    project_id = fields.Many2one('bhu.project', string='Project')
    village_id = fields.Many2one('bhu.village', string='Village')
    landowner_id = fields.Many2one('bhu.landowner', string='Landowner')

    def action_download_award_notification(self):
        """Download Award Notification - To be implemented"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Award notification download will be implemented soon.'),
                'type': 'info',
            }
        }

