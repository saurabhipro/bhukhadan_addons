# -*- coding: utf-8 -*-

import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class Section23Award(models.Model):
    _name = 'bhu.section23.award'
    _description = 'Section 23 Award'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Award Reference / अवार्ड संदर्भ', required=True, tracking=True, default='New')
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, index=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True, tracking=True, index=True)
    
    # Department - computed from project (for filtering purposes)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', 
                                   related='project_id.department_id', store=True, readonly=True)
    
    # Award details
    award_date = fields.Date(string='Award Date / अवार्ड दिनांक', default=fields.Date.today, tracking=True)
    case_number = fields.Char(
        string='Case Number / प्रकरण क्रमांक',
        tracking=True,
        help='Land acquisition case/proceeding number (e.g., SEC23-New, SEC23-2024-001)'
    )
    section4_hearing_date = fields.Date(
        string='Section 4 Public Hearing Date / धारा 4 सार्वजनिक सुनवाई दिनांक',
        compute='_compute_section4_hearing_date',
        store=False,
        readonly=True,
        help='Automatically fetched from Section 4 notification public hearing date'
    )
    avg_three_year_sales_sort_rate = fields.Float(
        string='Avg. sales sort rate (3 years) / विगत तीन वर्षों का औसत बिक्री छांट दर',
        digits=(16, 4),
        required=True,
        default=0.0,
        tracking=True,
        help='Mandatory before generating the award; shown on land schedule (Excel/PDF).',
    )

    # Award rate inputs (defaulted from active rate master; editable on the award)
    rate_master_main_road_ha = fields.Monetary(
        string='MR Rate (₹/Ha)', currency_field='currency_id',
        default=0.0,
        tracking=True,
        help='Main Road rate per hectare from the active land rate master for this village.',
    )
    rate_master_other_road_ha = fields.Monetary(
        string='BMR Rate (₹/Ha)', currency_field='currency_id',
        default=0.0,
        tracking=True,
        help='Beyond Main Road rate per hectare from the active land rate master for this village.',
    )
    rate_master_main_road_sqm = fields.Float(
        string='MR Plot Rate (₹/sqm)',
        digits=(16, 2),
        default=0.0,
        tracking=True,
    )
    rate_master_other_road_sqm = fields.Float(
        string='BMR Plot Rate (₹/sqm)',
        digits=(16, 2),
        default=0.0,
        tracking=True,
    )

    # Village profile for this award (defaulted from village master; editable on award)
    village_type = fields.Selection([
        ('rural', 'Rural / ग्रामीण'),
        ('urban', 'Urban / नगरीय'),
    ], string='Village Type / ग्राम प्रकार',
       default='rural', tracking=True)

    # Urban award settings
    urban_body_type = fields.Selection([
        ('nagar_nigam',     'Nagar Nigam / नगर निगम'),
        ('nagar_palika',    'Nagar Palika / नगर पालिका'),
        ('nagar_panchayat', 'Nagar Panchayat / नगर पंचायत'),
    ], string='Urban Body Type / नगरीय निकाय प्रकार',
       tracking=True,
       help='Pulled from village; override here if needed. Controls urban area-slab calculation.')

    is_urban = fields.Boolean(
        string='Is Urban / नगरीय है',
        compute='_compute_is_urban',
        store=False,
        help='True when selected village is Urban in village master.',
    )
    
    # Award document
    award_document = fields.Binary(string='Award Document / अवार्ड दस्तावेज़', tracking=False)
    award_document_filename = fields.Char(string='Document Filename / दस्तावेज़ फ़ाइल नाम', tracking=True)
    signed_land_award_document = fields.Binary(string='Signed Land Award PDF', tracking=False)
    signed_land_award_filename = fields.Char(string='Signed Land Award Filename', tracking=True)
    signed_tree_award_document = fields.Binary(string='Signed Tree Award PDF', tracking=False)
    signed_tree_award_filename = fields.Char(string='Signed Tree Award Filename', tracking=True)
    signed_asset_award_document = fields.Binary(string='Signed Asset Award PDF', tracking=False)
    signed_asset_award_filename = fields.Char(string='Signed Asset Award Filename', tracking=True)
    signed_consolidated_award_document = fields.Binary(string='Signed Consolidated Award PDF', tracking=False)
    signed_consolidated_award_filename = fields.Char(string='Signed Consolidated Award Filename', tracking=True)
    signed_rr_award_document = fields.Binary(string='Signed R&R Award PDF', tracking=False)
    signed_rr_award_filename = fields.Char(string='Signed R&R Award Filename', tracking=True)
    
    # Notes
    notes = fields.Text(string='Notes / नोट्स', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft / प्रारूप'),
        ('approved', 'Generated / उत्पन्न'),
        ('submitted', 'Submitted'),   # legacy — no longer used in new flow
        ('sent_back', 'Sent Back'),   # legacy — no longer used in new flow
    ], string='Status', default='draft', tracking=True, index=True)
    
    is_generated = fields.Boolean(string='Is Generated', default=False, tracking=True)
    land_generated = fields.Boolean(string='Land Generated', default=False, tracking=True)
    tree_generated = fields.Boolean(string='Tree Generated', default=False, tracking=True)
    asset_generated = fields.Boolean(string='Asset Generated', default=False, tracking=True)
    consolidated_generated = fields.Boolean(string='Consolidated Generated', default=False, tracking=True)
    rr_generated = fields.Boolean(string='R&R Generated', default=False, tracking=True)
    loader_progress_active = fields.Boolean(string='Loader Progress Active', default=False, tracking=False)
    loader_progress_done = fields.Integer(string='Loader Progress Done', default=0, tracking=False)
    loader_progress_total = fields.Integer(string='Loader Progress Total', default=0, tracking=False)
    loader_progress_pct = fields.Float(string='Loader Progress %', digits=(6, 2), default=0.0, tracking=False)
    loader_progress_label = fields.Char(string='Loader Progress Label', tracking=False)
    all_components_generated = fields.Boolean(
        string='All Components Generated',
        compute='_compute_all_components_generated',
        store=False,
    )
    s23_generation_stage = fields.Selection(
        [
            ('draft', 'Draft'),
            ('land_generated', 'Land Generated'),
            ('tree_generated', 'Tree Generated'),
            ('asset_generated', 'Asset Generated'),
            ('all_generated', 'All Generated'),
            ('consolidated_generated', 'Consolidated Generated'),
            ('rr_generated', 'R&R Generated'),
        ],
        string='Generation Progress',
        compute='_compute_s23_generation_stage',
        store=False,
    )
    
    village_domain = fields.Char()
    
    # Survey lines for award generation
    award_survey_line_ids = fields.One2many('bhu.section23.award.survey.line', 'award_id', 
                                            string='Approved Surveys / स्वीकृत सर्वेक्षण',
                                            help='Select type and distance for each approved survey')
    # Khasra search filter — stored so value persists across reloads
    khasra_filter = fields.Char(string='Search Khasra', default='')
    tree_khasra_filter = fields.Char(string='Search Tree Khasra', default='')
    award_line_item_ids = fields.One2many(
        'bhu.section23.award.line.item',
        'award_id',
        string='Award Line Items',
        readonly=True,
    )
    award_structure_line_ids = fields.One2many(
        'bhu.award.structure.details',
        'award_id',
        string='Award Structure Entries / अवार्ड परिसम्पत्ति प्रविष्टियां'
    )
    
    # Rate Permutations for Village (read-only, computed)
    rate_permutation_ids = fields.One2many('bhu.rate.master.permutation.line', 'award_id', 
                                           string='Rate Permutations', readonly=True, 
                                           compute='_compute_rate_permutations', store=False)
    
    # Computed field to check if all surveys have type and distance selected
    all_surveys_configured = fields.Boolean(string='All Surveys Configured', 
                                           compute='_compute_all_surveys_configured',
                                           help='True when all surveys have type and distance selected')
    
    # User Role Fields for UI Logic
    is_sdm = fields.Boolean(compute='_compute_user_roles')
    is_section_officer = fields.Boolean(compute='_compute_user_roles')
    is_admin = fields.Boolean(compute='_compute_user_roles')

    # Premium form (simulator-style dashboard totals – non-stored)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', compute='_compute_s23_premium_currency', readonly=True,
    )
    land_total = fields.Float(
        string='Land Total', digits=(16, 2), compute='_compute_land_total', store=False,
    )
    tree_total = fields.Float(
        string='Tree Total', digits=(16, 2), compute='_compute_tree_total', store=False,
    )
    structure_total = fields.Float(
        string='Structure Total', digits=(16, 2), compute='_compute_structure_total', store=False,
    )
    grand_total = fields.Float(
        string='Grand Total', digits=(16, 2), compute='_compute_grand_total', store=False,
    )
    s23_survey_count = fields.Integer(
        string='Survey Count', compute='_compute_s23_survey_count', store=False,
    )
    s23_land_khasra_count = fields.Integer(
        string='Land Khasra Count', compute='_compute_s23_land_khasra_count', store=False,
    )
    s23_tree_count = fields.Integer(
        string='Tree Count', compute='_compute_s23_tree_count', store=False,
    )
    s23_asset_count = fields.Integer(
        string='Asset Count', compute='_compute_s23_asset_count', store=False,
    )
    s23_land_preview_html = fields.Html(
        string='Land preview', compute='_compute_s23_section_previews', sanitize=False, store=False,
    )
    s23_tree_preview_html = fields.Html(
        string='Tree preview', compute='_compute_s23_section_previews', sanitize=False, store=False,
    )
    s23_asset_preview_html = fields.Html(
        string='Asset preview', compute='_compute_s23_section_previews', sanitize=False, store=False,
    )
    asset_khasra_filter = fields.Char(string='Search Asset Khasra', default='')

    _sql_constraints = [
        ('project_village_unique', 'unique(project_id, village_id)', 
         'Only one award per project and village is allowed! / प्रत्येक परियोजना और गाँव के लिए केवल एक अवार्ड की अनुमति है!')
    ]

    @api.model
    def _auto_init(self):
        res = super()._auto_init()
        self._cr.execute(
            """
            CREATE INDEX IF NOT EXISTS bhu_s23_award_state_proj_vill_idx
            ON bhu_section23_award (state, project_id, village_id)
            """
        )
        return res

    @api.constrains('project_id', 'village_id')
    def _check_unique_award(self):
        """Python constraint to prevent duplicates during creation/write"""
        for record in self:
            if record.project_id and record.village_id:
                existing = self.search([
                    ('project_id', '=', record.project_id.id),
                    ('village_id', '=', record.village_id.id),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_('An award already exists for this Project and Village. / इस परियोजना और गाँव के लिए एक अवार्ड पहले से ही मौजूद है।'))

    @api.depends('project_id', 'village_id')
    def _compute_section4_hearing_date(self):
        for rec in self:
            if rec.project_id and rec.village_id:
                hearing_date = rec._get_section4_public_hearing_date()
                rec.section4_hearing_date = hearing_date
            else:
                rec.section4_hearing_date = False

    def _compute_user_roles(self):
        for rec in self:
            rec.is_sdm = self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm')
            rec.is_section_officer = self.env.user.has_group('bhukhadan_core.group_bhu_section_officer')
            rec.is_admin = self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')

    def _sync_village_profile_from_master(self, force=False):
        for rec in self:
            if not rec.village_id:
                continue
            master_vtype = rec.village_id.village_type or 'rural'
            master_ubody = rec.village_id.urban_body_type or False
            if force or not rec.village_type:
                rec.village_type = master_vtype
            if force or not rec.urban_body_type:
                rec.urban_body_type = master_ubody

    def _sync_village_profile_to_master(self):
        for rec in self:
            if not rec.village_id:
                continue
            rec.village_id.sudo().write({
                'village_type': rec.village_type or 'rural',
                'urban_body_type': rec.urban_body_type if rec.village_type == 'urban' else False,
            })

    @api.onchange('village_type')
    def _onchange_village_type_clear_urban_body(self):
        for rec in self:
            if rec.village_type != 'urban':
                rec.urban_body_type = False

    @api.depends('village_type', 'village_id', 'village_id.village_type')
    def _compute_is_urban(self):
        for rec in self:
            vtype = rec.village_type or (rec.village_id.village_type if rec.village_id else 'rural')
            rec.is_urban = (vtype == 'urban')

    def _sync_rate_fields_from_master(self, force=False):
        for rec in self:
            rm = rec._get_active_rate_master_for_village()
            mr_rate = float(rm.main_road_rate_hectare or 0.0) if rm else 0.0
            bmr_rate = float(rm.other_road_rate_hectare or 0.0) if rm else 0.0
            mr_plot_rate = float(rm.main_road_rate_sqm or 0.0) if rm else 0.0
            bmr_plot_rate = float(rm.other_road_rate_sqm or 0.0) if rm else 0.0
            if force or not rec.rate_master_main_road_ha:
                rec.rate_master_main_road_ha = mr_rate
            if force or not rec.rate_master_other_road_ha:
                rec.rate_master_other_road_ha = bmr_rate
            if force or not rec.rate_master_main_road_sqm:
                rec.rate_master_main_road_sqm = mr_plot_rate
            if force or not rec.rate_master_other_road_sqm:
                rec.rate_master_other_road_sqm = bmr_plot_rate

    @api.depends('project_id', 'project_id.company_id', 'project_id.company_id.currency_id')
    def _compute_s23_premium_currency(self):
        for rec in self:
            # Section 23 award UI must always show INR amounts.
            try:
                inr = rec.env.ref('base.INR')
            except Exception:
                inr = False
            cur = rec.project_id.company_id.currency_id if rec.project_id and rec.project_id.company_id else False
            rec.currency_id = inr or cur or rec.env.company.currency_id

    @api.depends(
        'award_survey_line_ids',
        'award_survey_line_ids.land_award_amount',
        'award_survey_line_ids.solatium_display',
        'award_survey_line_ids.interest_display',
    )
    def _compute_land_total(self):
        for rec in self:
            rec.land_total = sum(
                (line.land_award_amount or 0.0) +
                (line.solatium_display or 0.0) +
                (line.interest_display or 0.0)
                for line in rec.award_survey_line_ids
            )

    @api.depends(
        'award_structure_line_ids',
        'award_structure_line_ids.line_total',
    )
    def _compute_structure_total(self):
        for rec in self:
            rec.structure_total = sum((line.line_total or 0.0) * 2.0 for line in rec.award_structure_line_ids)

    @api.depends('project_id', 'village_id')
    def _compute_tree_total(self):
        for rec in self:
            tree_total = 0.0
            if rec.project_id and rec.village_id:
                surveys = rec.env['bhu.survey'].search([
                    ('project_id', '=', rec.project_id.id),
                    ('village_id', '=', rec.village_id.id),
                    ('state', 'in', ['draft', 'submitted', 'approved', 'locked']),
                ])
                for survey in surveys:
                    for tree_line in survey.tree_line_ids:
                        qty = float(getattr(tree_line, 'quantity', 0) or 0.0)
                        rate = float(tree_line.get_applicable_rate() if hasattr(tree_line, 'get_applicable_rate') else 0.0)
                        base_value = qty * rate
                        tree_total += base_value + (base_value * 0.1) + (base_value * 2.1)
            rec.tree_total = tree_total

    @api.depends('land_total', 'tree_total', 'structure_total')
    def _compute_grand_total(self):
        for rec in self:
            rec.grand_total = (rec.land_total or 0.0) + (rec.tree_total or 0.0) + (rec.structure_total or 0.0)

    @api.depends(
        'award_survey_line_ids', 'award_survey_line_ids.land_type', 'award_survey_line_ids.is_within_distance',
        'award_survey_line_ids.survey_id', 'award_survey_line_ids.rate_per_hectare',
        'award_structure_line_ids', 'award_structure_line_ids.survey_id', 'award_structure_line_ids.khasra_number',
        'award_structure_line_ids.structure_type', 'award_structure_line_ids.construction_type',
        'award_structure_line_ids.description', 'award_structure_line_ids.asset_count',
        'award_structure_line_ids.area_sqm', 'award_structure_line_ids.market_rate_per_sqm',
        'award_structure_line_ids.asset_value',
        'asset_khasra_filter',
        'village_id', 'project_id', 'award_date',
    )
    def _compute_s23_section_previews(self):
        for rec in self:
            rec.s23_land_preview_html = rec._html_s23_land_preview()
            rec.s23_tree_preview_html = rec._html_s23_tree_preview()
            rec.s23_asset_preview_html = rec._html_s23_asset_preview()

    @api.depends('award_survey_line_ids')
    def _compute_s23_survey_count(self):
        for rec in self:
            rec.s23_survey_count = len(rec.award_survey_line_ids)

    @api.depends('award_survey_line_ids', 'award_survey_line_ids.khasra_number')
    def _compute_s23_land_khasra_count(self):
        for rec in self:
            rec.s23_land_khasra_count = len(set(filter(None, rec.award_survey_line_ids.mapped('khasra_number'))))

    @api.depends('project_id', 'village_id')
    def _compute_s23_tree_count(self):
        for rec in self:
            tree_count = 0
            if rec.project_id and rec.village_id:
                surveys = rec.env['bhu.survey'].search([
                    ('project_id', '=', rec.project_id.id),
                    ('village_id', '=', rec.village_id.id),
                    ('state', 'in', ['draft', 'submitted', 'approved', 'locked', 'rejected']),
                ])
                if surveys.ids:
                    # Sum quantities directly — read_group aggregate keys differ across Odoo
                    # versions (e.g. quantity_sum vs quantity:sum), which caused badge to show 0.
                    lines = rec.env['bhu.survey.tree.line'].search([
                        ('survey_id', 'in', surveys.ids),
                    ])
                    tree_count = int(sum(lines.mapped('quantity')) or 0)
            rec.s23_tree_count = tree_count

    @api.depends('award_structure_line_ids', 'award_structure_line_ids.asset_count')
    def _compute_s23_asset_count(self):
        for rec in self:
            rec.s23_asset_count = sum(int(al.asset_count or 1) for al in rec.award_structure_line_ids)
    
    @api.depends('village_id')
    def _compute_rate_permutations(self):
        """Keep relation empty; do not create/link persisted lines here.

        Creating real ``bhu.rate.master.permutation.line`` rows and assigning
        ``(6, 0, [db_ids...])`` on this computed One2many during web onchange
        leaves x2many snapshot keys as plain ints; ``web``'s
        ``RecordSnapshot.diff`` then fails with ``AttributeError: 'int' object
        has no attribute 'origin'``. Permutations are not shown on award views;
        use the rate master / wizard flows for matrix display.
        """
        for award in self:
            award.rate_permutation_ids = [(5, 0, 0)]

    @api.depends('land_generated', 'tree_generated', 'asset_generated', 'is_generated')
    def _compute_all_components_generated(self):
        for rec in self:
            rec.all_components_generated = bool(
                (rec.land_generated and rec.tree_generated and rec.asset_generated) or rec.is_generated
            )

    @api.depends(
        'land_generated',
        'tree_generated',
        'asset_generated',
        'all_components_generated',
        'consolidated_generated',
        'rr_generated',
    )
    def _compute_s23_generation_stage(self):
        for rec in self:
            if rec.rr_generated:
                rec.s23_generation_stage = 'rr_generated'
            elif rec.consolidated_generated:
                rec.s23_generation_stage = 'consolidated_generated'
            elif rec.all_components_generated:
                rec.s23_generation_stage = 'all_generated'
            elif rec.asset_generated:
                rec.s23_generation_stage = 'asset_generated'
            elif rec.tree_generated:
                rec.s23_generation_stage = 'tree_generated'
            elif rec.land_generated:
                rec.s23_generation_stage = 'land_generated'
            else:
                rec.s23_generation_stage = 'draft'
    
    @api.depends('award_survey_line_ids.land_type', 'award_survey_line_ids.is_within_distance')
    def _compute_all_surveys_configured(self):
        """Check if all survey lines have type and distance configured"""
        for record in self:
            if not record.award_survey_line_ids:
                record.all_surveys_configured = False
            else:
                # land_type must be set (Village or Residential)
                # is_within_distance can be True or False (both are valid - checked or unchecked)
                # We just need to ensure land_type is set
                record.all_surveys_configured = all(
                    line.land_type for line in record.award_survey_line_ids
                )
    
    def _onchange_add_award_survey_lines_if_empty(self):
        """Pre-create land lines only when the O2M is still empty (no 5,0,0 in onchange).

        A full O2M replace with (5,0,0) + (0,0,...) during @api.onchange makes the web
        client snapshot diff crash (int ids vs NewId.origin). Full rebuild is done in
        create() / write() only.
        """
        self.ensure_one()
        if not (self.project_id and self.village_id):
            return
        if self.award_survey_line_ids:
            return
        surveys = self.env['bhu.survey'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ['draft', 'submitted', 'approved', 'locked', 'rejected']),
        ])
        if not surveys:
            return
        commands = []
        for survey in surveys:
            distance = survey.distance_from_main_road or 0.0
            threshold = self._s23_distance_threshold()
            commands.append((0, 0, {
                'survey_id': survey.id,
                'land_type': survey.land_type_for_award or 'village',
                'is_within_distance': distance <= threshold,
            }))
        if commands:
            self.award_survey_line_ids = commands
            self.award_survey_line_ids._compute_rate_per_hectare()
            self.award_survey_line_ids._compute_line_display_amounts()
        if self.project_id and self.village_id:
            self._sync_award_structure_lines()

    @api.onchange('village_id', 'project_id')
    def _onchange_village_populate_surveys(self):
        """Pre-fill land lines on first project+village (empty list only; save refreshes the rest)."""
        for rec in self:
            rec._sync_village_profile_from_master(force=bool(rec.village_id))
            rec._sync_rate_fields_from_master(force=bool(rec.village_id))
            rec._onchange_add_award_survey_lines_if_empty()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain"""
        for rec in self:
            if rec.project_id and rec.project_id.village_ids:
                rec.village_domain = json.dumps([('id', 'in', rec.project_id.village_ids.ids)])
            else:
                rec.village_domain = json.dumps([])
                rec.village_id = False
            if rec.village_id:
                rec._onchange_add_award_survey_lines_if_empty()
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate award reference and reuse existing project+village award when present."""
        to_create = []
        existing_records = self.browse()
        for vals in vals_list:
            vals = dict(vals)
            # Never apply O2M from the web client: it can send CREATE rows without
            # survey_id (required), causing SQL errors. Lines are built by _populate_award_survey_lines.
            vals.pop('award_survey_line_ids', None)
            project_id = vals.get('project_id')
            village_id = vals.get('village_id')
            if project_id and village_id:
                existing = self.search([
                    ('project_id', '=', project_id),
                    ('village_id', '=', village_id),
                ], limit=1)
                if existing:
                    existing_records |= existing
                    continue
            if vals.get('name', 'New') == 'New':
                # Try to use sequence settings from settings master
                if project_id:
                    sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'section23_award', project_id, village_id=village_id
                    )
                    if sequence_number:
                        vals['name'] = sequence_number
                    else:
                        # Fallback to ir.sequence
                        sequence = self.env['ir.sequence'].next_by_code('bhu.section23.award') or 'New'
                        vals['name'] = f'SEC23-{sequence}'
                else:
                    # No project_id, use fallback
                    sequence = self.env['ir.sequence'].next_by_code('bhu.section23.award') or 'New'
                    vals['name'] = f'SEC23-{sequence}'
            to_create.append(vals)
        records = super().create(to_create) if to_create else self.browse()
        records |= existing_records
        # Onchange does not run for backend create() calls; ensure lines are populated/synced.
        for record in records:
            record._sync_village_profile_from_master(force=False)
            record._sync_rate_fields_from_master(force=False)
            record._populate_award_survey_lines(reset_if_empty=False)
        return records

    def write(self, vals):
        vals = dict(vals)
        # Ignore direct O2M payloads from web client by default, but allow
        # trusted server-side flows (populate/debug) to write survey lines.
        if not self.env.context.get('allow_award_survey_line_write'):
            vals.pop('award_survey_line_ids', None)
        # Only compare scope after write. Do not repopulate land lines whenever
        # project_id/village_id *appear* in vals — the web client often re-sends
        # the same M2O on any save, which would (5,0,0) rebuild every time and
        # make land award rows or amounts "vanish" after Save.
        pre_scope = {
            rec.id: (
                rec.project_id.id if rec.project_id else False,
                rec.village_id.id if rec.village_id else False,
            )
            for rec in self
        }
        result = super().write(vals)
        village_profile_changed = any(k in vals for k in ('village_type', 'urban_body_type'))
        for rec in self:
            old_p, old_v = pre_scope.get(rec.id, (False, False))
            new_p = rec.project_id.id if rec.project_id else False
            new_v = rec.village_id.id if rec.village_id else False
            if new_p != old_p or new_v != old_v:
                rec._sync_village_profile_from_master(force=True)
                rec._sync_rate_fields_from_master(force=True)
                rec._populate_award_survey_lines(reset_if_empty=True)
                if rec.project_id and rec.village_id:
                    rec._sync_award_structure_lines()
            if village_profile_changed and rec.village_id:
                rec._sync_village_profile_to_master()
        return result

    def unlink(self):
        """Remove dependent payment records, then O2M children, then the award.

        ``bhu.payment.file`` historically used restrict FK on ``award_id``; we unlink
        payment files (and draft reconciliations) explicitly so award delete works
        from the list view without a raw SQL constraint error.
        """
        PaymentFile = self.env['bhu.payment.file'].sudo()
        Reconciliation = self.env['bhu.payment.reconciliation.bank'].sudo()
        Voucher = self.env['bhu.payment.voucher'].sudo()
        LandownerPayment = self.env['bhu.landowner.payment.status'].sudo()
        for rec in self:
            payment_files = PaymentFile.search([('award_id', '=', rec.id)])
            if payment_files:
                blocking_recons = Reconciliation.search([
                    ('payment_file_id', 'in', payment_files.ids),
                    ('state', 'not in', ('draft',)),
                ])
                if blocking_recons:
                    raise UserError(_(
                        'Cannot delete award "%(award)s" because payment reconciliation '
                        '"%(recon)s" is already processed. Cancel or complete reconciliation '
                        'before deleting this award.'
                    ) % {
                        'award': rec.display_name,
                        'recon': blocking_recons[0].display_name,
                    })
                Reconciliation.search([
                    ('payment_file_id', 'in', payment_files.ids),
                ]).unlink()
                Voucher.search([
                    ('payment_file_id', 'in', payment_files.ids),
                ]).write({'payment_file_id': False})
                LandownerPayment.search([
                    ('payment_file_id', 'in', payment_files.ids),
                ]).write({'payment_file_id': False})
                payment_files.unlink()
            rec.award_survey_line_ids.unlink()
            rec.award_line_item_ids.unlink()
        return super().unlink()

    def _populate_award_survey_lines(self, reset_if_empty=False):
        """Populate survey lines from draft/submitted/approved surveys.

        Rebuilds lines deterministically for the selected project+village.
        """
        self.ensure_one()
        _logger.info(f"[DEBUG] _populate_award_survey_lines called for award {self.name} (ID {self.id})")
        _logger.info(f"[DEBUG]   project_id={self.project_id.id if self.project_id else None}, village_id={self.village_id.id if self.village_id else None}")
        
        if not (self.project_id and self.village_id):
            _logger.warning(f"[DEBUG] Missing project_id or village_id. Returning early.")
            if reset_if_empty:
                self.award_survey_line_ids = [(5, 0, 0)]
            return

        surveys = self.env['bhu.survey'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            # Include rejected as fallback; standard states are draft/submitted/approved/locked
            ('state', 'in', ['draft', 'submitted', 'approved', 'locked', 'rejected']),
        ])
        _logger.info(f"[DEBUG] Found {len(surveys)} surveys matching project {self.project_id.id} and village {self.village_id.id}")
        for i, s in enumerate(surveys):
            _logger.info(f"[DEBUG]   Survey {i+1}: ID={s.id}, name={s.name}, khasra={s.khasra_number}, state={s.state}")
        
        if not surveys:
            _logger.warning(f"[DEBUG] No surveys found. reset_if_empty={reset_if_empty}, current award_survey_line_ids={len(self.award_survey_line_ids)}")
            # Never wipe existing land lines on a "soft" repopulate: if the search returns
            # no rows (workflow timing, or state not matching yet), a full clear would
            # remove khasra from the form — e.g. on Generate when _validate repopulates.
            if self.award_survey_line_ids and not reset_if_empty:
                _logger.info(f"[DEBUG] Keeping existing {len(self.award_survey_line_ids)} award_survey_line_ids (soft repopulate with no surveys)")
                return
            self.award_survey_line_ids = [(5, 0, 0)]
            _logger.info(f"[DEBUG] Cleared award_survey_line_ids")
            return
        # Rebuild commands from current surveys to avoid stale/empty UI rows.
        commands = [(5, 0, 0)]
        for survey in surveys:
            distance = survey.distance_from_main_road or 0.0
            threshold = self._s23_distance_threshold()
            commands.append((0, 0, {
                'survey_id': survey.id,
                'land_type': survey.land_type_for_award or 'village',
                'is_within_distance': distance <= threshold,
            }))
        _logger.info(f"[DEBUG] Creating {len(commands)-1} award_survey_line records from {len(surveys)} surveys")
        self.with_context(allow_award_survey_line_write=True).write({
            'award_survey_line_ids': commands,
        })
        # Force rate recompute now that award_id is fully linked on each line
        if self.award_survey_line_ids:
            self.award_survey_line_ids._compute_rate_per_hectare()
            self.award_survey_line_ids._compute_line_display_amounts()
        if self.project_id and self.village_id:
            self._sync_award_structure_lines()
        _logger.info(f"[DEBUG] _populate_award_survey_lines complete. Final count: {len(self.award_survey_line_ids)}")
