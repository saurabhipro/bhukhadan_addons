from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import uuid
import logging
from datetime import datetime, timezone
import io
import base64

_logger = logging.getLogger(__name__)


class Survey(models.Model):
    _name = 'bhu.survey'
    _inherit = ['bhu.qr.code.mixin']
    _description = 'Survey (सर्वे)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.qr.code.mixin']
    # Show latest surveys first everywhere (kanban, list, search)
    _order = 'create_date desc, id desc'


    @api.model
    def _auto_init(self):
        res = super()._auto_init()
        self._cr.execute(
            """
            CREATE INDEX IF NOT EXISTS bhu_survey_proj_vill_state_idx
            ON bhu_survey (project_id, village_id, state)
            """
        )
        self._cr.execute(
            """
            CREATE INDEX IF NOT EXISTS bhu_survey_proj_vill_state_khasra_nn_idx
            ON bhu_survey (project_id, village_id, state, khasra_number)
            WHERE khasra_number IS NOT NULL AND khasra_number <> ''
            """
        )
        self._cr.execute(
            """
            UPDATE bhu_survey s
               SET tehsil_id = v.tehsil_id
              FROM bhu_village v
             WHERE s.village_id = v.id
               AND s.tehsil_id IS NULL
               AND v.tehsil_id IS NOT NULL
            """
        )
        self._cr.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                     WHERE table_name = 'bhu_survey' AND column_name = 'khada_no'
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                     WHERE table_name = 'bhu_survey' AND column_name = 'khata_no'
                ) THEN
                    ALTER TABLE bhu_survey RENAME COLUMN khada_no TO khata_no;
                END IF;
            END $$;
            """
        )
        return res

    # Basic Information
    user_id = fields.Many2one('res.users', string="User", default=lambda self : self.env.user.id, readonly=True)
    name = fields.Char(string='Survey Number', required=True, tracking=True, readonly=True, copy=False, default='New')
    survey_uuid = fields.Char(string='Survey UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, index=True, ondelete='cascade')
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', required=True, tracking=True)
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम का नाम', required=True, tracking=True, index=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील', required=False, tracking=True)
    area_id = fields.Many2one('bhukhadan.area.master', string='Area / क्षेत्र', tracking=True, ondelete='restrict')
    allowed_village_ids = fields.Many2many(
        'bhu.village',
        compute='_compute_allowed_village_ids',
        string='Villages available for selection',
    )
    
    survey_type = fields.Selection([
        ('rural', 'Rural / ग्रामीण'),
        ('urban', 'Urban / शहरी')
    ], string='Survey Type / सर्वे प्रकार', default='rural', tracking=True)

    payment_status_line_ids = fields.One2many(
        'bhu.landowner.payment.status',
        'survey_id',
        string='Payment Status Lines / भुगतान स्थिति पंक्तियां',
        readonly=True,
    )

    payment_status = fields.Selection([
        ('new', 'New'),
        ('payment_under_process', 'Payment Under Process'),
        ('payment_done', 'Payment Done'),
        ('payment_failed', 'Payment Failed'),
    ], string='Payment Status', compute='_compute_payment_status', readonly=True, tracking=True)

    # Read-only mirrors for compact form header strip (avoid duplicate widgets in view)
    bhu_summary_project = fields.Char(related='project_id.display_name', string='Project (Header)')
    bhu_summary_village = fields.Char(related='village_id.display_name', string='Village (Header)')
    bhu_summary_tehsil = fields.Char(related='tehsil_id.name', string='Tehsil (Header)')
    bhu_summary_khasra = fields.Char(related='khasra_number', string='Khasra (Header)')
    bhu_summary_patwari = fields.Char(related='user_id.name', string='Patwari (Header)')
    bhu_summary_survey_date = fields.Date(related='survey_date', string='Survey Date (Header)')
    bhu_summary_payment = fields.Selection(related='payment_status', string='Payment (Header)')
    bhu_summary_survey_type = fields.Selection(related='survey_type', string='Survey Type (Header)')
    
    @api.depends('project_id', 'project_id.village_ids', 'village_id')
    def _compute_allowed_village_ids(self):
        """Project villages plus the currently linked village (mobile/API may use villages not on project M2M)."""
        for rec in self:
            villages = rec.project_id.village_ids if rec.project_id else rec.env['bhu.village'].browse()
            if rec.village_id and rec.village_id not in villages:
                villages = villages | rec.village_id
            rec.allowed_village_ids = villages

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Filter villages to project mapping; always keep the currently selected village visible."""
        if self.project_id:
            if self.project_id.department_id:
                self.department_id = self.project_id.department_id
            village_ids = list(self.project_id.village_ids.ids)
            if self.village_id and self.village_id.id not in village_ids:
                village_ids.append(self.village_id.id)
            return {'domain': {'village_id': [('id', 'in', village_ids)]}}
        return {'domain': {'village_id': []}}

    district_name = fields.Char(string='District / जिला', default='Raigarh (Chhattisgarh)', readonly=True, tracking=True)
    survey_date = fields.Date(string='Survey Date / सर्वे दिनाँक', required=True, tracking=True, default=fields.Date.today)
    
    # Company/Organization Information
    company_id = fields.Many2one('res.company', string='Company / कंपनी', required=True, 
                                 default=lambda self: self.env.company, tracking=True)
    
    # Single Khasra Details - One survey per khasra
    khasra_number = fields.Char(string='Khasra Number / खसरा नंबर', required=True, tracking=True, index=True)
    khata_no = fields.Char(string='Khata No / खाता नंबर', tracking=True)
    total_area = fields.Float(string='Total Area (Hectares) / कुल क्षेत्रफल (हेक्टेयर)', digits=(10, 4), tracking=True)
    acquired_area = fields.Float(string='Acquired Area (Hectares) / अर्जन हेतु प्रस्तावित क्षेत्रफल (हेक्टेयर)', digits=(10, 4), tracking=True)
    has_traded_land = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Diverted (Traded) Land / विचलित (व्यापारित) भूमि', default='no', tracking=True,
                                      help='Indicates if the land is diverted (formerly traded land)')
    traded_land_area = fields.Float(string='Traded Land Area (Hectares) / व्यापारित भूमि क्षेत्रफल (हेक्टेयर)', 
                                    digits=(10, 4), tracking=True, default=0.0,
                                    help='Area of land that has been traded in hectares')
    
    # Land Details
    crop_type_id = fields.Many2one('bhu.land.type', string='Crop Type / फसल का प्रकार', tracking=True,
                                    help='Select the crop type from the land type master (एक फसली, दो फसली, पड़ती)')
    
    irrigation_type = fields.Selection([
        ('irrigated', 'Irrigated / सिंचित'),
        ('unirrigated', 'Unirrigated / असिंचित'),
    ], string='Irrigation Type / सिंचाई का प्रकार', default='irrigated', tracking=True)
    
    # Award-related fields (editable only from award section)
    land_type_for_award = fields.Selection([
        ('village', 'Village / ग्राम'),
        ('residential', 'Residential / आवासीय')
    ], string='Type for Award / अवार्ड के लिए प्रकार', readonly=True, tracking=True,
       help='Select whether this is village land or residential land (editable only from Award section)')
    
    is_within_distance_for_award = fields.Boolean(string='Within Distance for Award / अवार्ड के लिए दूरी के भीतर', 
                                                 readonly=True, tracking=True,
                                                 help='Auto-derived from "Distance from Main Road" if provided '
                                                      '(<= 50 m for rural surveys, <= 20 m for urban surveys). '
                                                      'Otherwise editable only from the Award section.')

    distance_from_main_road = fields.Float(
        string='Distance from Main Road (m) / मुख्य मार्ग से दूरी (मीटर)',
        digits=(10, 2), tracking=True,
        help='Optional. Actual measured distance from the main road in metres. '
             'When set, the "Within Distance for Award" flag is auto-computed '
             'using thresholds: rural <= 50 m, urban <= 20 m.',
    )

    @api.onchange('distance_from_main_road', 'survey_type')
    def _onchange_distance_from_main_road(self):
        for rec in self:
            distance = rec.distance_from_main_road or 0.0
            threshold = 50.0 if rec.survey_type == 'rural' else 20.0
            rec.is_within_distance_for_award = distance <= threshold

    def _sync_within_distance_from_metres(self, vals):
        """Keep is_within_distance_for_award in sync when distance is provided
        through API/import (where onchange does not fire)."""
        if 'distance_from_main_road' not in vals and 'survey_type' not in vals:
            return
        for rec in self:
            distance = vals.get('distance_from_main_road', rec.distance_from_main_road)
            survey_type = vals.get('survey_type', rec.survey_type)
            distance = distance or 0.0
            threshold = 50.0 if survey_type == 'rural' else 20.0
            rec.sudo().write({'is_within_distance_for_award': distance <= threshold})

    @api.depends('payment_status_line_ids.status', 'khasra_number', 'project_id', 'village_id')
    def _compute_payment_status(self):
        """Reflect live payment lifecycle for each survey/khasra.

        Priority:
        1) Any failed reconciliation => Payment Failed
        2) All available reconciled statuses paid => Payment Done
        3) Any pending/partial status OR payment file generated => Payment Under Process
        4) Otherwise => New
        """
        PaymentFileLine = self.env['bhu.payment.file.line']
        for rec in self:
            statuses = set(rec.payment_status_line_ids.mapped('status'))

            if 'failed' in statuses:
                rec.payment_status = 'payment_failed'
                continue

            if statuses and statuses.issubset({'paid'}):
                rec.payment_status = 'payment_done'
                continue

            if statuses:
                rec.payment_status = 'payment_under_process'
                continue

            # No reconciliation status lines yet:
            # if present in a payment file, treat as under process; else new.
            has_payment_line = False
            if rec.khasra_number and rec.project_id and rec.village_id:
                has_payment_line = bool(PaymentFileLine.search_count([
                    ('khasra_number', '=ilike', rec.khasra_number.strip()),
                    ('payment_file_id.project_id', '=', rec.project_id.id),
                    ('payment_file_id.village_id', '=', rec.village_id.id),
                ]))

            rec.payment_status = 'payment_under_process' if has_payment_line else 'new'
    
    # Rate Permutations for Village (read-only, computed)
    rate_permutation_ids = fields.One2many('bhu.rate.master.permutation.line', 'survey_id', 
                                           string='Rate Permutations', readonly=True, 
                                           compute='_compute_rate_permutations', store=False)
    
    # Tree Lines - Detailed tree information
    tree_line_ids = fields.One2many('bhu.survey.tree.line', 'survey_id', 
                                    string='Tree Details / वृक्ष विवरण')
    
    # Separated tree lines by type
    fruit_bearing_tree_line_ids = fields.One2many('bhu.survey.tree.line', 'survey_id',
                                                   string='Fruit-bearing Trees / फलदार वृक्ष',
                                                   domain="[('tree_type', '=', 'fruit_bearing')]")
    non_fruit_bearing_tree_line_ids = fields.One2many('bhu.survey.tree.line', 'survey_id',
                                                       string='Non-fruit-bearing Trees / गैर-फलदार वृक्ष',
                                                       domain="[('tree_type', '=', 'non_fruit_bearing')]")
    
    photo_ids = fields.One2many('bhu.survey.photo', 'survey_id', 
                                string='Photos / फोटो', 
                                help='Photos uploaded for this survey with tags')
    award_structure_ids = fields.One2many(
        'bhu.award.structure.details',
        'survey_id',
        string='Award Structure Details / अवार्ड परिसम्पत्ति विवरण'
    )
    
    # House Details
    has_house = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has House / घर है', default='no', tracking=True)
    house_type = fields.Selection([
        ('kaccha', 'कच्चा'),
        ('pakka', 'पक्का')
    ], string='House Type / घर का प्रकार', tracking=True)
    house_area = fields.Float(string='House Area (Sq. Ft.) / घर का क्षेत्रफल (वर्ग फुट)', digits=(10, 2), tracking=True)
    has_shed = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has Shed / शेड है', default='no', tracking=True)
    shed_area = fields.Float(string='Shed Area (Sq. Ft.) / शेड का क्षेत्रफल (वर्ग फुट)', digits=(10, 2), tracking=True)
    has_well = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has Well / कुआं है', default='no', tracking=True)
    well_type = fields.Selection([
        ('kaccha', 'कच्चा'),
        ('pakka', 'पक्का')
    ], string='Well Type / कुएं का प्रकार', default='kaccha', required=False, tracking=True)
    well_count = fields.Integer(string='Well Count / कुओं की संख्या', default=1, tracking=True, help='Number of wells')
    has_tubewell = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has Tubewell/Submersible Pump / ट्यूबवेल/सम्बमर्शिबल पम्प', default='no', tracking=True)
    tubewell_count = fields.Integer(string='Tubewell Count / ट्यूबवेल की संख्या', default=1, tracking=True, help='Number of tubewells/submersible pumps')
    has_pond = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has Pond / तालाब है', default='no', tracking=True)
    
    # Multiple Landowners
    landowner_ids = fields.One2many(
        'bhu.landowner', 'survey_id', string='Landowners / भूमिस्वामी', tracking=True,
    )
    house_owner_ids = fields.One2many(
        'bhu.house.owner', 'survey_id', string='House Owners / मकान मालिक', tracking=True,
    )
    
    section15_objection_ids = fields.Many2many('bhu.section15.objection',
                                               'bhu_survey_section15_objection_rel',
                                               'survey_id', 'objection_id',
                                               string='Section 15 Objections / धारा 15 आपत्ति',
                                               readonly=True,
                                               help='Objections raised for this survey. Multiple objections can track different changes (landowner added/removed, area decreased).')
    section15_objection_count = fields.Integer(string='Objection Count', compute='_compute_section15_objection_count', store=False)
    
    approved_objection_id = fields.Many2one('bhu.section15.objection', string='Approved Objection / स्वीकृत आपत्ति', 
                                            compute='_compute_approved_objection', store=True)
    has_approved_objection = fields.Boolean(string='Has Approved Objection / स्वीकृत आपत्ति है', 
                                            compute='_compute_approved_objection', store=True)

    @api.depends('section15_objection_ids', 'section15_objection_ids.state')
    def _compute_approved_objection(self):
        """Compute approved objection and flag for UI highlighting"""
        for record in self:
            approved_obj = record.section15_objection_ids.filtered(lambda x: x.state == 'approved')
            if approved_obj:
                # Get the latest approved objection
                record.approved_objection_id = approved_obj[0]
                record.has_approved_objection = True
            else:
                record.approved_objection_id = False
                record.has_approved_objection = False

    
    @api.depends('section15_objection_ids')
    def _compute_section15_objection_count(self):
        """Compute the count of Section 15 objections"""
        for record in self:
            record.section15_objection_count = len(record.section15_objection_ids)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True, index=True)
    
    # Track submission date
    submitted_date = fields.Datetime(string='Submitted Date / प्रस्तुत दिनांक', readonly=True, tracking=True,
                                     help='Date and time when the survey was submitted for approval')
    
    # Computed fields for list view
    landowner_count = fields.Integer(string='Landowners Count / भूमिस्वामी संख्या', compute='_compute_landowner_count', store=True)
    tree_detail_count = fields.Integer(
        string='Tree Details Count',
        compute='_compute_survey_sheet_stat_counts',
    )
    award_structure_count = fields.Integer(
        string='Award Structures Count',
        compute='_compute_survey_sheet_stat_counts',
    )
    photo_count = fields.Integer(
        string='Photos Count',
        compute='_compute_survey_sheet_stat_counts',
    )

    pending_since = fields.Char(string='Pending Since / लंबित', compute='_compute_pending_since', store=False,
                                help='How long the survey has been pending for approval')
    
    # Days pending approval
    days_pending_approval = fields.Integer(string='Days Pending / लंबित दिन',
                                          compute='_compute_days_pending_survey', store=False,
                                          help='Number of days survey has been pending approval')
    
    # Pending with field - shows who the survey is currently pending with (name + department + days)
    pending_with = fields.Char(string='Pending With / लंबित', compute='_compute_pending_with_survey', store=False,
                                help='Shows who the survey is currently pending with (name, department, and days pending)')
    
    # Computed field to check if survey is approved (for readonly)
    is_approved_readonly = fields.Boolean(string='Is Approved Readonly', compute='_compute_is_approved_readonly', store=False,
                                          help='True when survey is approved, making it readonly')
    
    @api.depends('state')
    def _compute_is_approved_readonly(self):
        """Compute if survey is approved and should be readonly"""
        for record in self:
            record.is_approved_readonly = record.state == 'approved'
    
    @api.depends('landowner_ids')
    def _compute_landowner_count(self):
        """Compute the count of landowners"""
        for record in self:
            record.landowner_count = len(record.landowner_ids)

    @api.depends('tree_line_ids', 'award_structure_ids', 'photo_ids')
    def _compute_survey_sheet_stat_counts(self):
        for rec in self:
            rec.tree_detail_count = len(rec.tree_line_ids)
            rec.award_structure_count = len(rec.award_structure_ids)
            rec.photo_count = len(rec.photo_ids)

    @api.depends('state', 'submitted_date', 'write_date')
    def _compute_pending_since(self):
        """Compute how long the survey has been pending for approval"""
        for record in self:
            if record.state == 'submitted' and record.submitted_date:
                # Calculate time difference
                # Odoo stores datetimes as naive (UTC), so we compare naive datetimes
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                submitted = record.submitted_date
                # Ensure submitted is naive datetime
                if submitted.tzinfo is not None:
                    submitted = submitted.replace(tzinfo=None)
                
                delta = now - submitted
                days = delta.days
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                
                if days > 0:
                    record.pending_since = f"{days} day{'s' if days > 1 else ''} ago"
                elif hours > 0:
                    record.pending_since = f"{hours} hour{'s' if hours > 1 else ''} ago"
                elif minutes > 0:
                    record.pending_since = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                else:
                    record.pending_since = "Just now"
            else:
                record.pending_since = ''
    
    # Notification 4 Generation - Read-only, controlled from Notification 4 process
    is_notification_4_generated = fields.Boolean(string='Is Noti 4 Generated / अधिसूचना 4 जेनरेट है', default=False, tracking=True, readonly=True, help='This field is automatically set when Notification 4 is generated. It cannot be manually edited.')
    
    # Computed field to check if current user is a collector (for readonly purposes)
    is_collector_readonly = fields.Boolean(string='Is Collector Readonly', compute='_compute_is_collector_readonly', store=False)
    
    @api.depends()
    def _compute_is_collector_readonly(self):
        """Compute if current user is a collector for readonly purposes"""
        is_collector = self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector')
        for record in self:
            record.is_collector_readonly = is_collector

    is_admin = fields.Boolean(string='Is Admin', compute='_compute_is_admin', store=False)

    @api.depends()
    def _compute_is_admin(self):
        """Compute if current user has admin access"""
        is_admin_user = self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin') or self.env.user.has_group('base.group_system')
        for record in self:
            record.is_admin = is_admin_user
    
    @api.depends('state', 'submitted_date')
    def _compute_days_pending_survey(self):
        """Compute number of days pending approval"""
        for record in self:
            if record.state == 'submitted' and record.submitted_date:
                now = fields.Datetime.now()
                submitted = record.submitted_date
                # Ensure submitted is naive datetime
                if submitted.tzinfo is not None:
                    submitted = submitted.replace(tzinfo=None)
                delta = now - submitted
                record.days_pending_approval = delta.days
            else:
                record.days_pending_approval = 0
    
    @api.depends('state', 'project_id', 'submitted_date', 'days_pending_approval', 'department_id')
    def _compute_pending_with_survey(self):
        """Compute who the survey is currently pending with (name + department + days)"""
        for record in self:
            if record.state == 'approved' or record.state == 'rejected':
                # Hide when approved or rejected
                record.pending_with = ''
            elif record.state == 'submitted':
                # Pending with Department User - get names from project
                if record.project_id and record.project_id.department_user_ids:
                    dept_users = record.project_id.department_user_ids
                    dept_user_names = dept_users.mapped('name')
                    department_name = record.department_id.name if record.department_id else ''
                    
                    days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                    
                    if dept_user_names:
                        names_str = ', '.join(dept_user_names)
                        if department_name:
                            record.pending_with = _('Department User: %s (%s)%s') % (names_str, department_name, days_text)
                        else:
                            record.pending_with = _('Department User: %s%s') % (names_str, days_text)
                    else:
                        if department_name:
                            record.pending_with = _('Department User / विभाग उपयोगकर्ता (%s)%s') % (department_name, days_text)
                        else:
                            record.pending_with = _('Department User / विभाग उपयोगकर्ता%s') % days_text
                else:
                    department_name = record.department_id.name if record.department_id else ''
                    days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                    if department_name:
                        record.pending_with = _('Department User / विभाग उपयोगकर्ता (%s)%s') % (department_name, days_text)
                    else:
                        record.pending_with = _('Department User / विभाग उपयोगकर्ता%s') % days_text
            elif record.state == 'draft':
                # Pending with Patwari (creator)
                patwari_name = record.user_id.name if record.user_id else 'Patwari'
                department_name = record.department_id.name if record.department_id else ''
                days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                
                if department_name:
                    record.pending_with = _('Patwari: %s (%s)%s') % (patwari_name, department_name, days_text)
                else:
                    record.pending_with = _('Patwari: %s%s') % (patwari_name, days_text)
            else:
                record.pending_with = ''
    
    # Computed fields for Form 10 report
    is_single_crop = fields.Boolean(string='Is Single Crop', compute='_compute_crop_fields', store=False)
    is_double_crop = fields.Boolean(string='Is Double Crop', compute='_compute_crop_fields', store=False)
    is_irrigated = fields.Boolean(string='Is Irrigated', compute='_compute_irrigation_fields', store=False)
    is_unirrigated = fields.Boolean(string='Is Unirrigated', compute='_compute_irrigation_fields', store=False)
    
    # Tree counts by development stage (for PDF reports)
    undeveloped_tree_count = fields.Integer(string='Undeveloped Tree Count', compute='_compute_tree_counts_by_stage', store=False)
    semi_developed_tree_count = fields.Integer(string='Semi-developed Tree Count', compute='_compute_tree_counts_by_stage', store=False)
    fully_developed_tree_count = fields.Integer(string='Fully Developed Tree Count', compute='_compute_tree_counts_by_stage', store=False)
    
    @api.depends('crop_type_id')
    def _compute_crop_fields(self):
        for record in self:
            if record.crop_type_id:
                # Check if it's single crop or double crop based on land type code or name
                crop_code = record.crop_type_id.code or ''
                crop_name = record.crop_type_id.name or ''
                record.is_single_crop = 'SINGLE_CROP' in crop_code or 'एक फसली' in crop_name
                record.is_double_crop = 'DOUBLE_CROP' in crop_code or 'दो फसली' in crop_name
            else:
                record.is_single_crop = False
                record.is_double_crop = False
    
    @api.depends('irrigation_type')
    def _compute_irrigation_fields(self):
        for record in self:
            record.is_irrigated = record.irrigation_type == 'irrigated'
            # Backward compatible for legacy values like "fallow".
            record.is_unirrigated = record.irrigation_type in ('unirrigated', 'fallow')
    
    @api.depends('tree_line_ids', 'tree_line_ids.tree_type', 'tree_line_ids.development_stage', 'tree_line_ids.quantity')
    def _compute_tree_counts_by_stage(self):
        """Compute tree counts by development stage for non-fruit-bearing trees"""
        for record in self:
            undeveloped_count = 0
            semi_developed_count = 0
            fully_developed_count = 0
            
            # Ensure tree_line_ids are loaded
            if record.tree_line_ids:
                for line in record.tree_line_ids:
                    if line.tree_type == 'non_fruit_bearing':
                        if line.development_stage == 'undeveloped':
                            undeveloped_count += line.quantity or 0
                        elif line.development_stage == 'semi_developed':
                            semi_developed_count += line.quantity or 0
                        elif line.development_stage == 'fully_developed':
                            fully_developed_count += line.quantity or 0
            
            record.undeveloped_tree_count = undeveloped_count
            record.semi_developed_tree_count = semi_developed_count
            record.fully_developed_tree_count = fully_developed_count
    
    # QR code generation is now handled by bhu.qr.code.mixin
    # The mixin handles the special case of Form 10 using project_uuid and village_uuid
   


    # Survey Images and Location
    survey_image = fields.Binary(string='Survey Image / सर्वे छवि', help='Photo taken during survey')
    survey_image_filename = fields.Char(string='Image Filename / छवि फ़ाइल नाम', tracking=True)
    latitude = fields.Float(string='Latitude / अक्षांश', digits=(10, 8), help='GPS Latitude coordinate', tracking=True)
    longitude = fields.Float(string='Longitude / देशांतर', digits=(11, 8), help='GPS Longitude coordinate', tracking=True)
    location_accuracy = fields.Float(string='Location Accuracy (meters) / स्थान सटीकता (मीटर)', digits=(8, 2), help='GPS accuracy in meters', tracking=True)
    location_timestamp = fields.Datetime(string='Location Timestamp / स्थान समय', help='When the GPS coordinates were captured', tracking=True)
    
    # Attachments removed per request

    # Remarks
    remarks = fields.Text(string='Remarks / टिप्पणी', tracking=True)

    # Measuring Book checklist/declaration fields
    # Measuring Book declaration fields
    mb_owner_decl_date = fields.Date(string='Owner Declaration Date')
    mb_decl_no_claim_pending = fields.Boolean(string='No claim pending declaration')
    mb_decl_documents_received = fields.Boolean(string='Required documents received')
    mb_decl_gps_photo_video = fields.Boolean(string='GPS photo/video captured')
    
    @api.depends('name', 'khasra_number')
    def _compute_display_name(self):
        """Show khasra number prominently when called from Section 15 objections or when context requires it"""
        show_khasra = self.env.context.get('show_khasra', False)
        for record in self:
            if show_khasra and record.khasra_number:
                record.display_name = record.khasra_number
            else:
                record.display_name = record.name or 'New'

    def name_get(self):
        """Backward compatibility for older Odoo calls"""
        result = []
        for record in self:
            result.append((record.id, record.display_name))
        return result
    
    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        """Override name_search to allow searching by khasra number when show_khasra is in context"""
        args = args or []
        show_khasra = self.env.context.get('show_khasra', False)
        
        if show_khasra and name:
            # When searching for surveys in Section 15, allow searching by khasra number
            domain = [
                '|',  # OR condition
                ('name', operator, name),  # Search by survey name
                ('khasra_number', operator, name),  # Search by khasra number
            ]
            domain = args + domain
            return self._search(domain, limit=limit, order=order or self._order)
        
        # Default behavior for other contexts
        return super()._name_search(name, args, operator, limit, order)
    
    @api.model
    def _apply_tehsil_from_village_vals(self, vals):
        """Derive tehsil from village when mobile/web omits tehsil_id."""
        if vals.get('tehsil_id') or not vals.get('village_id'):
            return vals
        village = self.env['bhu.village'].browse(vals['village_id'])
        if village.exists() and village.tehsil_id:
            vals['tehsil_id'] = village.tehsil_id.id
        return vals

    @api.onchange('village_id')
    def _onchange_village_id_tehsil(self):
        if self.village_id and self.village_id.tehsil_id:
            self.tehsil_id = self.village_id.tehsil_id

    @api.model_create_multi
    def create(self, vals_list):
        """Generate automatic survey numbers using bhuarjan settings master"""
        for vals in vals_list:
            self._apply_tehsil_from_village_vals(vals)
            # If state is explicitly set to 'submitted' (e.g., from API), set submitted_date
            # Otherwise, default to 'draft' for web UI
            if vals.get('state') == 'submitted' and 'submitted_date' not in vals:
                from datetime import datetime, timezone
                vals['submitted_date'] = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if vals.get('name', 'New') == 'New':
                # Check if project_id is available
                if vals.get('project_id'):
                    project = self.env['bhu.project'].browse(vals['project_id'])
                    project_code = project.code or project.name or 'PROJ'
                    
                    # Check if sequence settings exist for survey process (global settings, no project dependency)
                    sequence_settings = self.env['bhuarjan.sequence.settings'].search([
                        ('process_name', '=', 'survey'),
                        ('active', '=', True)
                    ], limit=1)
                    
                    if sequence_settings:
                        # Get village_id if available
                        village_id = vals.get('village_id')
                        
                        # Generate sequence number using settings master (placeholders already replaced)
                        sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                            'survey', vals['project_id'], village_id=village_id
                        )
                        if sequence_number:
                            vals['name'] = sequence_number
                        else:
                            # Fallback to default naming if sequence generation fails
                            sequence = self.env['ir.sequence'].next_by_code('bhu.survey') or '001'
                            vals['name'] = f'SC_{project_code}_{sequence.zfill(3)}'
                    else:
                        # No sequence settings found, use fallback naming
                        sequence = self.env['ir.sequence'].next_by_code('bhu.survey') or '001'
                        vals['name'] = f'SC_{project_code}_{sequence.zfill(3)}'
                else:
                    # No project_id, use default naming
                    sequence = self.env['ir.sequence'].next_by_code('bhu.survey') or '001'
                    vals['name'] = f'SC_PROJ_{sequence.zfill(3)}'
        
        records = super(Survey, self).create(vals_list)
        # Log creation
        for record, vals in zip(records, vals_list):
            record._sync_within_distance_from_metres(vals)
            record.message_post(
                body=_('Survey created by %s') % self.env.user.name,
                message_type='notification'
            )
        return records

    def write(self, vals):
        if 'village_id' in vals and not vals.get('tehsil_id'):
            self._apply_tehsil_from_village_vals(vals)
        result = super(Survey, self).write(vals)
        if 'distance_from_main_road' in vals or 'survey_type' in vals:
            self._sync_within_distance_from_metres(vals)
        return result
    
    def unlink(self):
        """Override unlink to reset sequence counter after deletion"""
        # Store project_id and village_id before deletion
        project_village_map = {}
        for record in self:
            if record.project_id and record.village_id:
                key = (record.project_id.id, record.village_id.id)
                if key not in project_village_map:
                    project_village_map[key] = {
                        'project_id': record.project_id.id,
                        'village_id': record.village_id.id,
                        'project_code': record.project_id.code or record.project_id.name or 'PROJ',
                        'village_code': record.village_id.village_code if record.village_id.village_code else '',
                    }
        
        # Delete the records
        result = super(Survey, self).unlink()
        
        # After deletion, update sequence counters for affected project+village combinations
        for key, info in project_village_map.items():
            self._reset_sequence_after_deletion(
                info['project_id'],
                info['village_id'],
                info['project_code'],
                info['village_code']
            )
        
        return result
    
    def _reset_sequence_after_deletion(self, project_id, village_id, project_code, village_code):
        """Reset sequence counter based on highest remaining sequence number"""
        # Check if sequence settings exist
        sequence_setting = self.env['bhuarjan.sequence.settings'].search([
            ('process_name', '=', 'survey'),
            ('active', '=', True)
        ], limit=1)
        
        if not sequence_setting:
            return
        
        # Prepare prefix pattern
        sequence_prefix = sequence_setting.prefix.replace('{%PROJ_CODE%}', project_code)
        sequence_prefix = sequence_prefix.replace('{bhu.project.code}', project_code)
        sequence_prefix = sequence_prefix.replace('{PROJ_CODE}', project_code)
        sequence_prefix = sequence_prefix.replace('{bhu.village.code}', village_code)
        
        # Get the last sequence number from existing records
        next_seq_number = self.env['bhuarjan.settings.master']._get_last_sequence_number(
            'bhu.survey',
            sequence_prefix,
            project_id=project_id,
            village_id=village_id,
            initial_seq=sequence_setting.initial_sequence
        )
        
        # Update the ir.sequence counter
        sequence_code = f'bhuarjan.survey.{project_id}.{village_id}'
        ir_sequence = self.env['ir.sequence'].search([
            ('code', '=', sequence_code)
        ], limit=1)
        
        if ir_sequence:
            # Set counter to next_seq_number (which is already last + 1)
            ir_sequence.write({'number_next': next_seq_number})
    
    @api.constrains('khasra_number', 'village_id')
    def _check_unique_khasra_per_village(self):
        """Ensure only one survey per khasra number in one village"""
        for survey in self:
            if survey.khasra_number and survey.village_id:
                existing_surveys = self.search([
                    ('id', '!=', survey.id),
                    ('village_id', '=', survey.village_id.id),
                    ('khasra_number', '=', survey.khasra_number)
                ])
                if existing_surveys:
                    raise ValidationError(_('Khasra number %s already exists in village %s in another survey.') % 
                                        (survey.khasra_number, survey.village_id.name))

    # Business validations
    @api.constrains('total_area', 'acquired_area')
    def _check_areas_positive_and_relation(self):
        for rec in self:
            # both areas must be strictly greater than zero
            if rec.total_area is None or rec.total_area <= 0:
                raise ValidationError(_('Total Area must be greater than 0.'))
            if rec.acquired_area is None or rec.acquired_area <= 0:
                raise ValidationError(_('Acquired Area must be greater than 0.'))
            # acquired cannot exceed total
            if rec.acquired_area > rec.total_area:
                raise ValidationError(_('Acquired Area cannot be greater than Total Area.'))

    @api.constrains('landowner_ids')
    def _check_landowners_present(self):
        for rec in self:
            if not rec.landowner_ids:
                raise ValidationError(_('At least one landowner is required on the survey.'))

    def action_view_landowners(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Landowners'),
            'res_model': 'bhu.landowner',
            'view_mode': 'list,form',
            'domain': [('survey_id', '=', self.id)],
            'context': {
                'default_survey_id': self.id,
                'default_company_id': self.company_id.id,
                'default_village_id': self.village_id.id,
            },
        }

    def action_view_tree_details(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tree Details'),
            'res_model': 'bhu.survey.tree.line',
            'view_mode': 'list,form',
            'domain': [('survey_id', '=', self.id)],
            'context': {
                'default_survey_id': self.id,
                'default_development_stage': 'undeveloped',
            },
        }

    def action_view_award_structures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Award Structures'),
            'res_model': 'bhu.award.structure.details',
            'view_mode': 'list,form',
            'domain': [('survey_id', '=', self.id)],
            'context': {'default_survey_id': self.id},
        }

    def action_view_photos(self):
        self.ensure_one()
        self.env['bhu.survey.photo'].sync_from_s3_for_survey(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Survey Photos / सर्वे फोटो'),
            'res_model': 'bhu.survey.photo',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('bhukhadan_core.view_bhu_survey_photo_list').id, 'list'),
                (self.env.ref('bhukhadan_core.view_bhu_survey_photo_form').id, 'form'),
            ],
            'domain': [('survey_id', '=', self.id), ('active', '=', True)],
            'context': {
                'default_survey_id': self.id,
                'create': False,
            },
        }

    def action_print_measuring_book(self):
        """Print House & Other Asset Measurement Book in PDF format."""
        self.ensure_one()
        return self.env.ref('bhukhadan_core.action_report_measuring_book').report_action(self)

    def action_export_measuring_book_excel(self):
        """Export Measuring Book in sheet layout similar to scanned format."""
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError:
            raise ValidationError(_("Python library 'xlsxwriter' is not installed."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Measuring Book')
        # Column widths A:M
        col_widths = [6, 30, 12, 12, 12, 12, 12, 10, 24, 10, 12, 12, 14]
        for col, width in enumerate(col_widths):
            ws.set_column(col, col, width)

        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 12, 'align': 'center', 'valign': 'vcenter',
            'border': 2, 'bg_color': '#D9D9D9',
        })
        hdr_fmt = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'border': 2, 'bg_color': '#D9D9D9',
        })
        subhdr_fmt = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#E6E6E6',
        })
        cell_fmt = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter'})
        cell_center = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        num_fmt = workbook.add_format({'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00'})
        total_fmt = workbook.add_format({'bold': True, 'border': 2, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00'})
        label_total_fmt = workbook.add_format({'bold': True, 'border': 2, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#D9D9D9'})

        row = 0
        ws.set_row(row, 26)
        ws.merge_range(row, 0, row, 12,
                       f"COMPENSATION OF HOUSE AND OTHER ASSETS OF {(self.village_id.name or '').upper()} "
                       f"VILLAGE ACQUIRED IN YEAR 2004 & 2010 BY {(self.project_id.name or '').upper()}",
                       title_fmt)
        row += 1

        # House owner block
        house_owner = self.house_owner_ids[:1]
        house_owner_name = house_owner.name if house_owner else ''
        house_owner_aadhar = house_owner.aadhar_number if house_owner else ''
        house_owner_caste = house_owner.caste if house_owner else ''
        house_owner_dob = house_owner.dob if house_owner else ''
        house_owner_mobile = house_owner.phone if house_owner else ''
        house_owner_village = (
            house_owner.village_id.display_name if house_owner and house_owner.village_id
            else (self.village_id.name or '')
        )
        house_number = house_owner.house_number if house_owner else ''
        mohalla = house_owner.mohalla if house_owner else ''
        ws.merge_range(row, 0, row, 9, f"NAME OF HOUSE OWNER : {house_owner_name}", hdr_fmt)
        ws.merge_range(row, 10, row, 12, f"HOUSE NO : {house_number}", hdr_fmt)
        row += 1
        ws.merge_range(row, 0, row, 5, f"AADHAR NO : {house_owner_aadhar}", subhdr_fmt)
        ws.merge_range(row, 6, row, 8, f"CASTE/CAT : {house_owner_caste}", subhdr_fmt)
        ws.merge_range(row, 9, row, 12, f"MOHALLA : {mohalla}", subhdr_fmt)
        row += 1
        ws.merge_range(row, 0, row, 3, f"Date of Birth : {house_owner_dob or ''}", subhdr_fmt)
        ws.merge_range(row, 4, row, 7, f"MOBILE NO : {house_owner_mobile}", subhdr_fmt)
        ws.merge_range(row, 8, row, 12, f"VILLAGE : {house_owner_village}", subhdr_fmt)
        row += 1
        land_owner = self.landowner_ids[:1]
        land_owner_name = land_owner.name if land_owner else ''
        land_owner_aadhar = land_owner.aadhar_number if land_owner else ''
        land_owner_rakba = land_owner.rakba if land_owner else ''
        ws.merge_range(row, 0, row, 12, 'RELATION BETWEEN HOUSE OWNER AND LAND OWNER :', hdr_fmt)
        row += 1

        # Land owner block (from linked landowners)
        ws.merge_range(row, 0, row, 9, f"NAME OF LAND OWNER : {land_owner_name}", hdr_fmt)
        ws.merge_range(row, 10, row, 12, f"KHASRA NO : {self.khasra_number or ''}", hdr_fmt)
        row += 1
        ws.merge_range(row, 0, row, 5, f"AADHAR NO : {land_owner_aadhar}", subhdr_fmt)
        ws.merge_range(row, 6, row, 8, 'CASTE/CAT :', subhdr_fmt)
        ws.merge_range(row, 9, row, 12, f"RAKBA : {land_owner_rakba}", subhdr_fmt)
        row += 1
        ws.merge_range(row, 0, row, 3, 'Date of Birth :', subhdr_fmt)
        ws.merge_range(row, 4, row, 12, 'NAME OF PRESENT LAND OWNER :', subhdr_fmt)
        row += 1

        # House details table
        ws.merge_range(row, 0, row, 7, "HOUSE / WELLS (A)", hdr_fmt)
        ws.merge_range(row, 8, row, 12, "TREES (B)", hdr_fmt)
        row += 1
        headers = ['SL NO', 'DETAILS OF HOUSE', 'LENGTH (Ft.)', 'WIDTH (Ft.)', 'AREA (Sq. Ft.)', 'Rate/sq. ft', 'AMOUNT', 'DEDUCTION', 'FINAL AMOUNT', 'NAME OF TREE', 'SIZE', 'NO. OF TREE', 'TREE AMOUNT']
        for c, h in enumerate(headers):
            ws.write(row, c, h, subhdr_fmt)
        row += 1

        house_rows = self.award_structure_ids[:8]
        house_total = 0.0
        sl = 1
        for line in house_rows:
            area_val = (line.area_sqm or 0.0) * 10.7639
            rate_val = line.market_rate_per_sqm or 0.0
            amt = line.asset_value or 0.0
            house_total += amt
            ws.write(row, 0, sl, cell_center)
            ws.write(row, 1, (line.description or line.structure_type or '').upper(), cell_fmt)
            ws.write(row, 2, '', cell_center)
            ws.write(row, 3, '', cell_center)
            ws.write_number(row, 4, area_val, num_fmt)
            ws.write_number(row, 5, rate_val, num_fmt)
            ws.write_number(row, 6, amt, num_fmt)
            ws.write_number(row, 7, 0.0, num_fmt)
            ws.write_number(row, 8, amt, num_fmt)
            ws.write(row, 9, '', cell_fmt)
            ws.write(row, 10, '', cell_center)
            ws.write(row, 11, '', cell_center)
            ws.write(row, 12, '', cell_center)
            sl += 1
            row += 1

        tree_total = 0.0
        tree_line = self.tree_line_ids[:1]
        if tree_line:
            t = tree_line[0]
            tree_amt = 0.0
            tree_total += tree_amt
            ws.write(row, 0, sl, cell_center)
            ws.write(row, 1, '', cell_fmt)
            ws.write(row, 2, '', cell_center)
            ws.write(row, 3, '', cell_center)
            ws.write(row, 4, '', cell_center)
            ws.write(row, 5, '', cell_center)
            ws.write(row, 6, '', cell_center)
            ws.write(row, 7, '', cell_center)
            ws.write(row, 8, '', cell_center)
            ws.write(row, 9, (t.tree_master_id.name or '').upper(), cell_fmt)
            ws.write(row, 10, t.girth_cm or '', cell_center)
            ws.write(row, 11, t.quantity or 0, cell_center)
            ws.write_number(row, 12, tree_amt, num_fmt)
            row += 1

        ws.merge_range(row, 0, row, 7, "TOTAL OF HOUSES (A)", label_total_fmt)
        ws.write_number(row, 8, house_total, total_fmt)
        ws.merge_range(row, 9, row, 11, "TOTAL OF TREES (B)", label_total_fmt)
        ws.write_number(row, 12, tree_total, total_fmt)
        row += 1

        grand_total = house_total + tree_total
        ws.merge_range(row, 0, row, 11, "TOTAL OF HOUSE AND TREE (A+B)", label_total_fmt)
        ws.write_number(row, 12, grand_total, total_fmt)
        row += 1
        ws.merge_range(row, 0, row, 11, "% SOLATIUM IF HOUSE/ASSETS ON OWN LAND AND LINEAR DEPENDENT (C)", label_total_fmt)
        ws.write_number(row, 12, grand_total, total_fmt)
        row += 1
        ws.merge_range(row, 0, row, 11, "GRAND TOTAL OF ASSET COMPENSATION (A+B+C)", label_total_fmt)
        ws.write_number(row, 12, grand_total * 2, total_fmt)
        row += 2

        # Committee section
        ws.merge_range(row, 0, row, 12, "STATE AUTHORITY COMMITTEE MEMBERS", hdr_fmt)
        row += 1
        ws.merge_range(row, 0, row, 12, "All committee members must sign with DATE, SEAL AND NAME", subhdr_fmt)
        row += 1
        ws.merge_range(row, 0, row + 1, 2, "PATWARI", cell_center)
        ws.merge_range(row, 3, row + 1, 5, "REVENUE INSPECTOR", cell_center)
        ws.merge_range(row, 6, row + 1, 8, "HORTICULTURE", cell_center)
        ws.merge_range(row, 9, row + 1, 12, "SUB DIVISIONAL MAGISTRATE", cell_center)
        row += 2
        ws.merge_range(row, 0, row, 12, "SECL DIPKA AREA SCREENING COMMITTEE MEMBERS", hdr_fmt)
        row += 1
        ws.merge_range(row, 0, row + 1, 3, "SECL CIVIL", cell_center)
        ws.merge_range(row, 4, row + 1, 7, "SECL SURVEY", cell_center)
        ws.merge_range(row, 8, row + 1, 12, "SECL MINING/EXCV", cell_center)
        row += 2

        # Document checklist as annexure block
        row += 1
        ws.merge_range(row, 0, row, 12, "LIST OF DOCUMENTS COLLECTED FROM HOUSE OWNER", hdr_fmt)
        row += 1
        ws.write_row(row, 0, ['S.No', 'Document', 'Checked', 'S.No', 'Document', 'Checked'], subhdr_fmt)
        row += 1
        docs_left = [
            ('1', 'Electricity Bill - House owner', house_owner.doc_electricity_bill if house_owner else False),
            ('2', 'Voter Card - House owner', house_owner.doc_voter_card_owner if house_owner else False),
            ('3', 'Aadhar Card - House owner', house_owner.doc_aadhar_owner if house_owner else False),
            ('4', 'Aadhar Card - Witness 01', house_owner.doc_aadhar_witness_1 if house_owner else False),
            ('5', 'Aadhar Card - Witness 02', house_owner.doc_aadhar_witness_2 if house_owner else False),
            ('6', 'Ration Card - House owner', house_owner.doc_ration_owner if house_owner else False),
            ('7', 'Educational certificate - House owner', house_owner.doc_education_owner if house_owner else False),
        ]
        docs_right = [
            ('8', 'Aadhar Card - Land owner', house_owner.doc_aadhar_landowner if house_owner else False),
            ('9', 'Affidavit/NOC', house_owner.doc_affidavit_noc if house_owner else False),
            ('10', 'Passport size photos (4)', house_owner.doc_passport_photos if house_owner else False),
            ('11', 'PAN Card - House owner', house_owner.doc_pan_owner if house_owner else False),
            ('12', 'PAN Card - Land owner', house_owner.doc_pan_landowner if house_owner else False),
            ('13', 'Bank Passbook', house_owner.doc_bank_passbook if house_owner else False),
            ('14', f"NEFT/Other: {(house_owner.doc_other_text or '') if house_owner else ''}",
             ((house_owner.doc_bank_neft_form or house_owner.doc_other) if house_owner else False)),
        ]
        for idx in range(7):
            l = docs_left[idx]
            r = docs_right[idx]
            ws.write(row, 0, l[0], cell_center)
            ws.merge_range(row, 1, row, 4, l[1], cell_fmt)
            ws.write(row, 5, 'Yes' if l[2] else 'No', cell_center)
            ws.write(row, 6, r[0], cell_center)
            ws.merge_range(row, 7, row, 11, r[1], cell_fmt)
            ws.write(row, 12, 'Yes' if r[2] else 'No', cell_center)
            row += 1

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        filename = f"Measuring_Book_{(self.name or 'Survey').replace('/', '_')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
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

    def action_submit(self):
        """Submit the survey for approval"""
        for record in self:
            if not record.khasra_number:
                raise ValidationError(_('Please enter khasra number before submitting.'))
            if record.state != 'submitted':
                record.state = 'submitted'
            # Store submission date (as naive datetime for Odoo compatibility) if not already set
            if not record.submitted_date:
                record.submitted_date = datetime.now(timezone.utc).replace(tzinfo=None)
            # Log the submission
            record.message_post(
                body=_('Survey submitted for approval by %s') % self.env.user.name,
                message_type='notification'
            )
            
            # Create activity notification for department users
            record._create_department_user_activity()

            # Send email notification to the user
            template = self.env.ref("bhukhadan_core.email_bhuarjan_survey_submit_form", raise_if_not_found=False)
            if template and record.user_id:
                # Get email from partner or user
                partner_email = None
                if record.user_id.partner_id:
                    partner_email = record.user_id.partner_id.email
                if not partner_email:
                    partner_email = record.user_id.email
                
                # Only send if we have a valid email
                if partner_email and '@' in partner_email and partner_email.strip():
                    try:
                        # Render template to check email_to field
                        rendered_values = template._render_template(template.email_to, 'bhu.survey', [record.id])
                        email_to_value = rendered_values.get(record.id, '').strip()
                        
                        if email_to_value and '@' in email_to_value:
                            template.send_mail(record.id, force_send=True)
                            _logger.info(f"Email notification sent for survey {record.name} to {email_to_value}")
                        else:
                            _logger.warning(f"No valid email recipient in template for survey {record.name}")
                    except Exception as e:
                        # Log error but don't fail the submission
                        _logger.warning(f"Failed to send email notification for survey {record.name}: {str(e)}", exc_info=True)
                else:
                    _logger.info(f"Skipping email for survey {record.name}: User {record.user_id.name} does not have a valid email address")

                    
        wiz = self.env['bhu.survey.message.wizard'].create({
            'message': _('Survey Submitted.\nSurvey No: %s') % ', '.join(self.mapped('name'))
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bhu.survey.message.wizard',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Information'),
        }

    def action_approve(self):
        """Approve the survey - Only Department Users can approve"""
        # Check if user is Department User
        # Check if user is Department User or Admin
        if not self.env.user.has_group('bhukhadan_core.group_bhuarjan_department_user') and not self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin'):
            raise ValidationError(_('Only Department Users or Admins can approve surveys.'))
        
        for record in self:
            record.state = 'approved'
            # Log the approval
            record.message_post(
                body=_('Survey approved by %s') % self.env.user.name,
                message_type='notification'
            )

    def action_reject(self):
        """Reject the survey - Only Department Users can reject"""
        # Check if user is Department User
        # Check if user is Department User or Admin
        if not self.env.user.has_group('bhukhadan_core.group_bhuarjan_department_user') and not self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin'):
            raise ValidationError(_('Only Department Users or Admins can reject surveys.'))
        
        for record in self:
            record.state = 'rejected'
            # Log the rejection
            record.message_post(
                body=_('Survey rejected by %s') % self.env.user.name,
                message_type='notification'
            )
    
    def _create_department_user_activity(self):
        """Create activity for department users when survey is submitted"""
        self.ensure_one()
        
        # Get department users from project
        dept_users = self.env['res.users']
        
        if self.project_id and self.project_id.department_user_ids:
            dept_users = self.project_id.department_user_ids
        else:
            # Fallback: get all department users
            dept_group = self.env.ref('bhukhadan_core.group_bhuarjan_department_user', raise_if_not_found=False)
            if dept_group:
                dept_users = self.env['res.users'].search([
                    ('groups_id', 'in', dept_group.id)
                ])
        
        if not dept_users:
            return
        
        # Get activity type
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([('name', '=', 'To Do')], limit=1)
        
        if not activity_type:
            return
        
        # Include project name in summary
        project_name = self.project_id.name if self.project_id else ''
        survey_name = self.name or f"#{self.id}"
        if project_name:
            activity_summary = _('%s - Survey %s submitted for approval') % (project_name, survey_name)
        else:
            activity_summary = _('Survey %s submitted for approval') % survey_name
        
        activity_note = _('Survey submitted for approval: %s\n\nProject: %s\n\nVillage: %s\n\nKhasra Number: %s\n\nSubmitted by: %s') % (
            self.name or f"#{self.id}",
            self.project_id.name if self.project_id else 'N/A',
            self.village_id.name if self.village_id else 'N/A',
            self.khasra_number or 'N/A',
            self.env.user.name
        )
        
        for dept_user in dept_users:
            # Check if activity already exists for this user and record
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'bhu.survey'),
                ('res_id', '=', self.id),
                ('user_id', '=', dept_user.id),
                ('activity_type_id', '=', activity_type.id),
                ('summary', '=', activity_summary),
            ], limit=1)
            
            if not existing_activity:
                self.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=activity_summary,
                    note=activity_note,
                    user_id=dept_user.id,
                )

    def action_reset_to_submitted(self):
        """Reset survey to submitted (from rejected state) - Only Department Users can reset"""
        # Check if user is Department User
        # Check if user is Department User or Admin
        if not self.env.user.has_group('bhukhadan_core.group_bhuarjan_department_user') and not self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin'):
            raise ValidationError(_('Only Department Users or Admins can reset surveys to submitted state.'))
        
        for record in self:
            if record.state == 'rejected':
                record.state = 'submitted'
                # Log the reset
                record.message_post(
                    body=_('Survey reset to submitted by %s') % self.env.user.name,
                    message_type='notification'
                )

    def action_download_form10(self):
        """Download Form-10 as PDF"""
        # Use bulk table report for all selected records (works for single or multiple)
        report_action = self.env.ref('bhukhadan_core.action_report_form10_bulk_table')
        return report_action.report_action(self)

    def action_bulk_download_form10(self):
        """Download one PDF containing all visible surveys in a table layout.
        - 10 rows per page, signature section at the end.
        """
        # Respect current user's visibility (patwari: own + assigned villages)
        if self.env.user.bhuarjan_role in self.env['res.users'].BHUKHADAN_PATWARI_ROLES:
            domain = ['|', ('user_id', '=', self.env.user.id), ('village_id.user_id', '=', self.env.user.id)]
        else:
            domain = []

        all_records = self.search(domain)
        # Use consolidated single-PDF table report
        report_action = self.env.ref('bhukhadan_core.action_report_form10_bulk_table')
        return report_action.report_action(all_records)

    def action_download_award_letter(self):
        """Download Award Letter as PDF"""
        for record in self:
            # Generate PDF report
            report_action = self.env.ref('bhukhadan_core.action_report_award_letter')
            return report_action.report_action(record)

    def action_bulk_download_award_letter(self):
        """Download Award Letter PDFs for all selected surveys"""
        if not self:
            raise ValidationError(_('Please select at least one survey to download.'))
        
        # Generate PDF report for all selected surveys
        report_action = self.env.ref('bhukhadan_core.action_report_award_letter')
        return report_action.report_action(self)

    def action_form10_preview(self):
        """Preview all Form-10s in a single scrollable HTML view"""
        # Get all surveys for the current user based on their role
        if self.env.user.bhuarjan_role in self.env['res.users'].BHUKHADAN_PATWARI_ROLES:
            domain = [
                '|',
                ('user_id', '=', self.env.user.id),
                ('village_id.user_id', '=', self.env.user.id),
            ]
        else:
            # Other users can see all surveys
            domain = []
        
        # Get all surveys that have Form-10 data
        surveys = self.env['bhu.survey'].search(domain)
        
        if not surveys:
            raise ValidationError(_('No surveys found to preview.'))
        
        # Generate HTML report for all surveys (inline view)
        report_action = self.env.ref('bhukhadan_core.action_report_form10_bulk_table')
        report_action.report_type = 'qweb-html'
        return report_action.report_action(surveys)




    def log_survey_activity(self, activity_type, details=None):
        """Log custom survey activities"""
        for record in self:
            message = _('Survey activity: %s') % activity_type
            if details:
                message += _(' - %s') % details
            record.message_post(
                body=message,
                message_type='notification'
            )
    
    landowner_aadhar_numbers = fields.Char(
        string="Aadhaar Numbers",
        compute="_compute_landowner_aadhar_numbers",
        store=True,
        search="_search_landowner_aadhar_numbers"
    )

    def _compute_landowner_aadhar_numbers(self):
        for rec in self:
            if rec.landowner_ids:
                aadhar_numbers = [
                    str(aadhar).strip() for aadhar in rec.landowner_ids.mapped('aadhar_number') if aadhar
                ]
                rec.landowner_aadhar_numbers = ', '.join(aadhar_numbers)
            else:
                rec.landowner_aadhar_numbers = ''

    @api.depends('village_id')
    def _compute_rate_permutations(self):
        """Keep relation empty; do not create/link persisted lines in compute.

        Same rationale as ``bhu.section23.award``: real DB ids on a computed
        One2many during onchange break ``RecordSnapshot.diff`` in the web
        client (int line keys vs ``NewId.origin``).
        """
        for survey in self:
            survey.rate_permutation_ids = [(5, 0, 0)]

    @api.model
    def _search(self, args, offset=0, limit=None, order=None):
        """Override search to apply role-based filtering for Patwari users"""
        if self.env.user.bhuarjan_role in self.env['res.users'].BHUKHADAN_PATWARI_ROLES:
            patwari_domain = [
                '|',
                ('user_id', '=', self.env.user.id),
                ('village_id.user_id', '=', self.env.user.id),
            ]
            args = patwari_domain + args

        return super(Survey, self)._search(args, offset=offset, limit=limit, order=order)

    def action_sync_photos_from_s3(self):
        Photo = self.env['bhu.survey.photo']
        added = 0
        for survey in self:
            before = len(survey.photo_ids)
            Photo.sync_from_s3_for_survey(survey)
            added += max(len(survey.photo_ids) - before, 0)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Photos synced / फोटो सिंक'),
                'message': _(
                    '%(count)s photo(s) linked from S3. Refresh the Photos tab if needed.',
                    count=added,
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def get_survey_trend_data(self, company_ids=None):
        """Delegate to dashboard stats (keeps RPC working with cached assets calling bhu.survey)."""
        return self.env['bhuarjan.dashboard'].get_survey_trend_data(company_ids=company_ids)


class SurveyTreeLine(models.Model):
    _name = 'bhu.survey.tree.line'
    _description = 'Survey Tree Line / सर्वे वृक्ष लाइन'
    _order = 'development_stage, tree_master_id'

    survey_id = fields.Many2one('bhu.survey', string='Survey / सर्वे', required=True, ondelete='cascade')
    tree_master_id = fields.Many2one('bhu.tree.master', string='Tree / वृक्ष', required=True,
                                     help='Select tree from master')
    is_other_tree = fields.Boolean(string='Other Tree / अन्य वृक्ष', default=False)
    tree_description = fields.Char(string='Tree Description / वृक्ष विवरण')
    
    @api.onchange('tree_type')
    def _onchange_tree_type(self):
        """Update tree_master_id when tree_type changes"""
        # Allow any tree to be selected - no domain restriction
        return {}
    
    @api.onchange('tree_master_id')
    def _onchange_tree_master_id(self):
        """Set default development_stage when tree is selected"""
        if self.tree_master_id:
            # tree_type is computed, so it will update automatically
            # Set default development_stage if not already set
            if not self.development_stage:
                self.development_stage = self._context.get('default_development_stage', 'undeveloped')
            if self.tree_master_id and 'other' not in (self.tree_master_id.name or '').lower():
                self.is_other_tree = False
                self.tree_description = False
    
    @api.model_create_multi
    def create(self, vals_list):
        """tree_type is computed, so it will be set automatically"""
        return super().create(vals_list)
    
    def write(self, vals):
        """tree_type is computed, so it will be updated automatically"""
        return super().write(vals)
    development_stage = fields.Selection([
        ('undeveloped', 'Undeveloped / अविकसित'),
        ('semi_developed', 'Semi-developed / अर्ध-विकसित'),
        ('fully_developed', 'Fully Developed / पूर्ण विकसित')
    ], string='Development Stage / विकास स्तर', default='undeveloped',
       help='Development stage of the tree. Optional for all tree types.')       
    girth_cm = fields.Float(string='Girth (cm) / छाती (से.मी.)', digits=(10, 2),
                            help='Tree trunk girth (circumference) in centimeters. Optional for non-fruit-bearing trees.')
    quantity = fields.Integer(string='Quantity / मात्रा', required=True, default=1,
                             help='Number of trees of this type')
    
    # Tree type - automatically comes from tree master
    tree_type = fields.Selection(related="tree_master_id.tree_type", string="Tree Type", store=True)
    
    # @api.depends('tree_master_id.tree_type')
    # def _compute_tree_type(self):
    #     """Compute tree_type from tree_master_id"""
    #     for record in self:
    #         if record.tree_master_id:
    #             record.tree_type = record.tree_master_id.tree_type
    #         else:
    #             record.tree_type = False

    @api.constrains('tree_master_id')
    def _check_tree_master(self):
        """Ensure tree master is selected"""
        for record in self:
            if not record.tree_master_id:
                raise ValidationError(_('Tree must be selected'))

    @api.constrains('is_other_tree', 'tree_description')
    def _check_other_tree_description(self):
        for record in self:
            if record.is_other_tree and not (record.tree_description or '').strip():
                raise ValidationError(_('Please enter tree description when Other Tree is selected.'))
    
    @api.constrains('girth_cm')
    def _check_girth_positive(self):
        """Ensure girth is positive if provided"""
        for record in self:
            # girth_cm is optional - only validate if it's actually a positive number
            # Skip validation if girth_cm is False, None, or 0.0 (means "not set")
            girth_value = record.girth_cm
            if girth_value is False or girth_value is None:
                # Not set - that's fine, it's optional
                pass
            elif girth_value == 0.0:
                # 0.0 means not set for optional fields - that's fine
                pass
            else:
                # girth_cm is provided - validate it's a positive number
                try:
                    girth_float = float(girth_value)
                    if girth_float <= 0:
                        raise ValidationError('Girth (cm) must be greater than 0 if provided.')
                except (ValueError, TypeError):
                    # If it's not a valid number, that's an error
                    raise ValidationError('Girth (cm) must be a valid number if provided.')
    
    @api.constrains('quantity')
    def _check_quantity_positive(self):
        """Ensure quantity is positive"""
        for record in self:
            if record.quantity and record.quantity <= 0:
                raise ValidationError(_('Tree quantity must be greater than 0.'))

    def _fallback_rate(self):
        """Coarse fallback when no master rate matches (keeps reports working)."""
        self.ensure_one()
        return 6000.0 if self.tree_type == 'fruit_bearing' else 177.0

    def get_applicable_rate(self):
        """Return the applicable per-tree rate from ``bhu.tree.rate.master``.

        For fruit-bearing trees, uses flat rate from ``bhu.tree.master.fruit_rate``.
        For non-fruit-bearing trees, looked up by tree_master_id + development_stage + girth range.
        Falls back to a coarse rate when no master entry matches, so callers
        (award simulator, Section 23 report, downloads) never crash.
        """
        self.ensure_one()
        if not self.tree_master_id:
            return self._fallback_rate()
        if self.tree_type == 'fruit_bearing':
            return self.tree_master_id.fruit_rate or self._fallback_rate()
        domain = [
            ('tree_master_id', '=', self.tree_master_id.id),
            ('active', '=', True),
        ]
        if self.development_stage:
            domain.append(('development_stage', '=', self.development_stage))
        rates = self.env['bhu.tree.rate.master'].search(domain)
        if not rates:
            return self._fallback_rate()
        girth = self.girth_cm or 0.0
        for rate in rates:
            lo = rate.girth_range_min or 0.0
            hi = rate.girth_range_max
            if girth >= lo and (not hi or girth <= hi):
                return rate.rate or self._fallback_rate()
        return rates[0].rate or self._fallback_rate()


class SurveyLine(models.Model):
    _name = 'bhu.survey.line'
    _description = 'Survey Line (सर्वे लाइन)'
    _order = 'khasra_number'

    survey_id = fields.Many2one('bhu.survey', string='Survey', required=True, ondelete='cascade')
    khasra_number = fields.Char(string='Khasra Number / प्रभावित खसरा क्रमांक', required=True)
    total_area = fields.Float(string='Total Area (Hectares) / कुल रकबा (हे.में.)', required=True, digits=(10, 4))
    acquired_area = fields.Float(string='Acquired Area (Hectares) / अर्जन हेतु प्रस्तावित क्षेत्रफल (हे.में.)', required=True, digits=(10, 4))
    landowner_name = fields.Char(string='Landowner Name / भूमिस्वामी का नाम', required=True)
    
    # Land Type / भूमि का प्रकार
    crop_type = fields.Selection([
        ('single', 'Single Crop / एक फसली'),
        ('double', 'Double Crop / दो फसली'),
    ], string='Crop Type / फसल का प्रकार', default='single')
    
    irrigation_type = fields.Selection([
        ('irrigated', 'Irrigated / सिंचित'),
        ('unirrigated', 'Unirrigated / असिंचित'),
    ], string='Irrigation Type / सिंचाई का प्रकार', default='irrigated')
    
    # Trees on Land / भूमि पर स्थित वृक्ष की संख्या
    # Note: tree_development_stage and tree_count have been removed
    # Use tree_line_ids to access tree details with development_stage
    
    # Assets on Land / भूमि पर स्थित परिसंपत्तियों का विवरण
    # House Details
    has_house = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has House / घर है', default='no')
    house_type = fields.Selection([
        ('kaccha', 'Kaccha / कच्चा'),
        ('pakka', 'Pakka / पक्का')
    ], string='House Type / मकान प्रकार')
    house_area = fields.Float(string='House Area (Sq. Ft.) / मकान क्षेत्रफल (वर्गफुट)', digits=(10, 2))
    
    # Shed
    shed_area = fields.Float(string='Shed Area (Sq. Ft.) / शेड क्षेत्रफल (वर्गफुट)', digits=(10, 2))
    
    # Well
    has_well = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has Well / कुँआ है', default='no')
    well_type = fields.Selection([
        ('kaccha', 'Kaccha / कच्चा'),
        ('pakka', 'Pakka / पक्का')
    ], string='Well Type / कुँआ प्रकार')
    
    # Tubewell/Submersible Pump
    has_tubewell = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has Tubewell/Submersible Pump / ट्यूबवेल/सम्बमर्शिबल पम्प', default='no')
    
    # Pond
    has_pond = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Has Pond / तालाब है', default='no')
    
    # Remarks
    remarks = fields.Text(string='Remarks / रिमार्क')
    
    @api.constrains('acquired_area', 'total_area')
    def _check_area_validation(self):
        """Validate that acquired area is not more than total area"""
        for line in self:
            if line.acquired_area > line.total_area:
                raise ValidationError(_('Acquired area cannot be more than total area for Khasra %s') % line.khasra_number)
    
    @api.constrains('has_house', 'house_type', 'house_area')
    def _check_house_details(self):
        """Validate house details"""
        for line in self:
            if line.has_house == 'yes':
                if not line.house_type:
                    raise ValidationError(_('House type is required when house exists for Khasra %s') % line.khasra_number)
                if not line.house_area:
                    raise ValidationError(_('House area is required when house exists for Khasra %s') % line.khasra_number)
    
    @api.constrains('has_well', 'well_type')
    def _check_well_details(self):
        """Validate well details"""
        for line in self:
            if line.has_well == 'yes' and not line.well_type:
                raise ValidationError(_('Well type is required when well is present for Khasra %s') % line.khasra_number)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to validate sequence settings and generate sequence number"""
        for vals in vals_list:
            # Get project_id and village_id from survey_id if available
            project_id = None
            village_id = None
            if vals.get('survey_id'):
                survey = self.env['bhu.survey'].browse(vals['survey_id'])
                project_id = survey.project_id.id if survey.project_id else None
                village_id = survey.village_id.id if survey.village_id else None
            
            # Check if sequence settings exist for survey process (global settings, no project dependency)
            if project_id:
                sequence_settings = self.env['bhuarjan.sequence.settings'].search([
                    ('process_name', '=', 'survey'),
                    ('active', '=', True)
                ])
                
                if not sequence_settings:
                    raise ValidationError(_(
                        'Sequence settings for Survey process are not defined in Settings Master for project "%s". '
                        'Please configure sequence settings before creating surveys.'
                    ) % self.env['bhu.project'].browse(project_id).name)
                
                # Generate sequence number if name is 'New'
                if vals.get('name', 'New') == 'New':
                    sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'survey', project_id, village_id=village_id
                    )
                    if sequence_number:
                        vals['name'] = sequence_number
                    else:
                        raise ValidationError(_(
                            'Failed to generate sequence number for Survey process. '
                            'Please check sequence settings configuration.'
                        ))
        
        return super().create(vals_list)
    
    @api.model
    def check_sequence_settings(self, project_id):
        """Check if sequence settings are available for survey process (global settings, no project dependency)"""
        sequence_settings = self.env['bhuarjan.sequence.settings'].search([
            ('process_name', '=', 'survey'),
            ('active', '=', True)
        ], limit=1)
        
        if not sequence_settings:
            project_name = self.env['bhu.project'].browse(project_id).name
            return {
                'available': False,
                'message': _(
                    'Sequence settings for Survey process are not defined in Settings Master for project "%s". '
                    'Please configure sequence settings before creating surveys.'
                ) % project_name
            }
        
        return {
            'available': True,
            'message': _('Sequence settings are properly configured for Survey process.')
        }

    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        """Check sequence settings when survey is changed"""
        if self.survey_id and self.survey_id.project_id:
            sequence_check = self.check_sequence_settings(self.survey_id.project_id.id)
            if not sequence_check['available']:
                return {
                    'warning': {
                        'title': _('Sequence Settings Not Configured'),
                        'message': sequence_check['message']
                    }
                }