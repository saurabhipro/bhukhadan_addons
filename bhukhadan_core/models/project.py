from odoo import models, fields, api, _
import uuid
import json
import zlib
from collections import defaultdict

_BHU_PIPELINE_DOT_IDS = (
    'survey', 'section4', 'sia_team',
    'section8', 'section9', 'section11', 'section15', 'section19', 'section21', 'section23',
    'payment_voucher', 'payment_file',
)

_BHU_PIPELINE_DOT_SHORT_LABELS = {
    'survey': '10',
    'section4': '4',
    'sia_team': 'SI',
    'section8': '8',
    'section9': '9',
    'section11': '11',
    'section15': '15',
    'section19': '19',
    'section21': '21',
    'section23': '23',
    'payment_voucher': 'PV',
    'payment_file': 'PF',
}


def _bhu_pipeline_dot_payload(sid, kind, title):
    """Dot dict for dashboards / RPC (includes compact numeric labels)."""
    return {
        'id': sid,
        'kind': kind,
        'title': title,
        'short_label': _BHU_PIPELINE_DOT_SHORT_LABELS.get(sid, ''),
    }


class BhuProject(models.Model):
    _name = 'bhu.project'
    _description = 'Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Project Name', required=True, tracking=True)
    tag_color = fields.Integer(
        string='Tag Color',
        compute='_compute_tag_color',
        help='Palette index (0–11) for many2many tag / pill widgets in list views.',
    )

    @api.depends('project_uuid', 'name')
    def _compute_tag_color(self):
        """Palette slot for tag widgets; derived from UUID (stable), else from name."""
        for rec in self:
            pu = (rec.project_uuid or '').strip()
            key = pu if pu else (rec.name or '').strip()
            rec.tag_color = zlib.adler32(key.encode('utf-8')) % 12 if key else 0

    project_uuid = fields.Char(string='Project UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))
    
    def action_regenerate_uuid(self):
        """Regenerate UUID for a single project"""
        if not self:
            return
        new_uuid = str(uuid.uuid4())
        # Ensure the new UUID is unique
        while self.env['bhu.project'].search([('project_uuid', '=', new_uuid)]):
            new_uuid = str(uuid.uuid4())
        
        self.write({'project_uuid': new_uuid})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'UUID Regenerated',
                'message': f'New UUID: {new_uuid}',
                'type': 'success',
                'sticky': False,
            }
        }
    code = fields.Char(string='Project Code', tracking=True)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        """Prefix many2one labels with project code when set (e.g. ``[CODE] Name``)."""
        for project in self:
            label = (project.name or '').strip()
            code = (project.code or '').strip()
            if code and label:
                project.display_name = f'[{code}] {label}'
            elif label:
                project.display_name = label
            elif code:
                project.display_name = f'[{code}]'
            else:
                project.display_name = f'{project._name},{project.id}'

    department_id = fields.Many2one('bhu.department', string='Department / विभाग', tracking=True,
                                    help='Select the department for this project')
    district_id = fields.Many2one('bhu.district', string='District / जिला', tracking=True, help='Select the district for this project')
    sub_division_id = fields.Many2many('bhu.sub.division', string='Sub Division / अनुविभाग', tracking=True, help='Select the sub-division for this project')
    description = fields.Text(string='Description', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    def action_set_draft(self):
        """Set project status to Draft"""
        self.write({'state': 'draft'})
        return True
    
    def action_set_active(self):
        """Set project status to Active"""
        self.write({'state': 'active'})
        return True
    
    def action_set_completed(self):
        """Set project status to Completed"""
        self.write({'state': 'completed'})
        return True
    
    def action_set_cancelled(self):
        """Set project status to Cancelled"""
        self.write({'state': 'cancelled'})
        return True

    tehsil_ids = fields.Many2many('bhu.tehsil', string='Tehsil / तहसील', 
    tracking=True, help='Select the tehsil for this project', store=True)
    sdm_domain_json = fields.Char(string="SDM Domain JSON",default=json.dumps([('id', 'in', [False])]))
    tehsil_domain_json = fields.Char(string="Tehsil Domain JSON",default=json.dumps([('id', 'in', [False])]))
    village_domain_json = fields.Char(string="Village Domain JSON", default=json.dumps([('id', 'in', [False])]))
    tehsildar_domain_json = fields.Char(string="Tehsildar Domain JSON", default=json.dumps([('id', 'in', [False])]))


    @api.onchange(
        'district_id',
        'sub_division_id',
    )
    def _compute_location_hierarchy(self):
        false_domain = json.dumps([('id', 'in', [False])])

        for rec in self:
            prev_villages = rec.village_ids
            rec.tehsil_ids = False
            rec.sdm_ids = False
            rec.tehsildar_ids = False

            rec.sdm_domain_json = false_domain
            rec.tehsil_domain_json = false_domain
            rec.village_domain_json = false_domain
            rec.tehsildar_domain_json = false_domain

            # =====================================================
            # TEHSIL + SDM
            # =====================================================

            tehsils = self.env['bhu.tehsil']

            if rec.sub_division_id:
                tehsils = self.env['bhu.tehsil'].search([
                    ('sub_division_id', 'in', rec.sub_division_id.ids)
                ])
                rec.sdm_ids = rec.sub_division_id.user_id

            elif rec.district_id:
                tehsils = self.env['bhu.tehsil'].search([
                    ('district_id', '=', rec.district_id.id)
                ])
                # Do not auto-link every SDM in the district — only sub_division_id drives SDM.

            rec.tehsil_ids = tehsils

            if rec.sdm_ids:
                rec.sdm_domain_json = json.dumps([
                    ('id', 'in', rec.sdm_ids.ids)
                ])

            if rec.tehsil_ids:
                rec.tehsil_domain_json = json.dumps([
                    ('id', 'in', rec.tehsil_ids.ids)
                ])

            # =====================================================
            # VILLAGE + TEHSILDAR
            # =====================================================

            if rec.tehsil_ids:
                valid_villages = self.env['bhu.village'].search([
                    ('tehsil_id', 'in', rec.tehsil_ids.ids)
                ])
                # Never auto-assign every village in the tehsils: that floods project_ids on
                # every village list view and defeats explicit mapping on the Villages tab.
                # Keep only villages the user already picked that still fall under the scope.
                rec.village_ids = prev_villages & valid_villages

                rec.tehsildar_ids = rec.tehsil_ids.mapped('user_id')

                rec.village_domain_json = json.dumps([
                    ('id', 'in', valid_villages.ids)
                ])

                rec.tehsildar_domain_json = json.dumps([
                    ('id', 'in', rec.tehsildar_ids.ids)
                ])

            else:
                rec.village_ids = False
                rec.village_domain_json = false_domain

        self._compute_patwari_from_villages()

    


    village_ids = fields.Many2many(
        'bhu.village',
        'bhu_project_bhu_village_rel',
        'bhu_project_id',
        'bhu_village_id',
        string="Villages",
        tracking=True,
        store=True,
    )
    sdm_ids = fields.Many2many('res.users', 'bhu_project_sdm_rel', 'project_id', 'user_id',
                               string="SDM / उप-विभागीय मजिस्ट्रेट", tracking=True,
                               help="SDM users synced from linked sub divisions (not district-wide auto-fill).")
    sub_division_sdm_ids = fields.Many2many(
        'res.users',
        string='SDM (from Sub Division)',
        compute='_compute_sub_division_sdm_ids',
        help='SDM users on the linked sub division master — matches form/list sub division.',
    )



    tehsildar_ids = fields.Many2many('res.users', 'bhu_project_tehsildar_rel', 'project_id', 'user_id',
                                     string="Tehsildar / तहसीलदार", 
                                     domain="[('bhuarjan_role', '=', 'tahsildar')]", tracking=True,
                                     help="Select Tehsildars for this project")
    department_user_ids = fields.Many2many('res.users', 'bhu_project_department_user_rel', 'project_id', 'user_id',
                                           string="Department User / विभाग उपयोगकर्ता", 
                                           domain="[('bhuarjan_role', '=', 'department_user')]", tracking=True,
                                           help="Select Department Users for this project. They can approve/reject surveys.")
    
    patwari_ids = fields.Many2many(
        'res.users',
        'bhu_project_patwari_rel',
        'project_id',
        'user_id',
        string="Patwaris / पटवारी",
        compute='_compute_patwari_from_villages',
        store=True,
        readonly=True,
        help="Patwaris from each linked village Patwari (user). Lists the same users as on villages; bhuarjan_role filter is not applied here.",
    )

    survey_ids = fields.One2many(
        'bhu.survey',
        'project_id',
        string='Surveys / सर्वे',
        readonly=True,
    )

    survey_count = fields.Integer(
        string='Survey Count',
        compute='_compute_survey_count',
    )

    @api.depends('survey_ids')
    def _compute_survey_count(self):
        for rec in self:
            rec.survey_count = len(rec.survey_ids)

    @api.onchange('village_ids')
    def _onchange_village_ids_patwaris(self):
        self._compute_patwari_from_villages()

    @api.depends('village_ids', 'village_ids.user_id')
    def _compute_patwari_from_villages(self):
        for rec in self:
            users = rec.village_ids.mapped('user_id').ids
            if users:
                rec.patwari_ids = users
            else:
                rec.patwari_ids = False


    is_patwari_editable = fields.Boolean(compute='_compute_is_patwari_editable')
    
    # Tehsils
    def action_view_tehsils(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tehsils',
            'res_model': 'bhu.tehsil',
            'view_mode': 'list',
            'domain': [('id', 'in', self.tehsil_ids.ids)],
            'context': {'create': False, 'edit': False},
        }

    tehsil_count = fields.Integer(
        string='Tehsil Count',
        compute='_compute_smart_btn_count'
    )

    # Villages
    def action_view_villages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Villages',
            'res_model': 'bhu.village',
            'view_mode': 'list',
            'domain': [('id', 'in', self.village_ids.ids)],
            'context': {'create': False, 'edit': False},
        }

    village_count = fields.Integer(
        string='Village Count',
        compute='_compute_smart_btn_count'
    )

    # SDM (users on selected sub-divisions)
    def action_view_sdm(self):
        self.ensure_one()
        user_ids = self.sub_division_id.mapped('user_id').filtered('id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'SDM',
            'res_model': 'res.users',
            'view_mode': 'list',
            'domain': [('id', 'in', user_ids)],
            'context': {'create': False, 'edit': False},
        }

    sdm_count = fields.Integer(
        string='SDM Count',
        compute='_compute_smart_btn_count',
    )

    # Tehsildar
    def action_view_tehsildar(self):
        self.ensure_one()
        user_ids = self.tehsil_ids.mapped('user_id').filtered('id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tehsildar',
            'res_model': 'res.users',
            'view_mode': 'list',
            'domain': [('id', 'in', user_ids)],
            'context': {'create': False, 'edit': False},
        }

    tehsildar_count = fields.Integer(
        string='Tehsildar Count',
        compute='_compute_smart_btn_count'
    )

    # Patwari (users set on linked villages)
    def action_view_patwari(self):
        self.ensure_one()
        user_ids = self.village_ids.mapped('user_id').filtered('id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Patwari',
            'res_model': 'res.users',
            'view_mode': 'list',
            'domain': [('id', 'in', user_ids)],
            'context': {'create': False, 'edit': False},
        }

    patwari_count = fields.Integer(
        string='Patwari Count',
        compute='_compute_smart_btn_count'
    )

    def action_view_surveys(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Surveys'),
            'res_model': 'bhu.survey',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'search_default_group_by_state': 1,
            },
            'target': 'current',
        }
        try:
            survey_action = self.env.ref('bhukhadan_core.action_bhu_survey')
            if survey_action:
                action_ref = survey_action.read(['view_mode', 'views'])[0]
                if action_ref.get('views'):
                    action['views'] = action_ref['views']
                if action_ref.get('view_mode'):
                    action['view_mode'] = action_ref['view_mode']
        except Exception:
            pass
        return action

    @api.depends(
        'tehsil_ids',
        'tehsil_ids.user_id',
        'village_ids',
        'village_ids.user_id',
        'sub_division_id',
        'sub_division_id.user_id',
    )
    def _compute_smart_btn_count(self):
        for rec in self:
            rec.tehsil_count = len(rec.tehsil_ids)
            rec.village_count = len(rec.village_ids)
            rec.sdm_count = len(
                rec.sub_division_id.mapped('user_id').filtered('id')
            )
            rec.tehsildar_count = len(
                rec.tehsil_ids.mapped('user_id').filtered('id')
            )
            rec.patwari_count = len(
                rec.village_ids.mapped('user_id').filtered('id')
            )




    def _compute_is_patwari_editable(self):
        for rec in self:
            rec.is_patwari_editable = (
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_district_administrator') or
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_additional_collector') or
                self.env.user.has_group('base.group_system')
            )
    
    def action_view_patwari_surveys(self, patwari_id):
        """Open surveys for a specific patwari in this project"""
        self.ensure_one()
        patwari = self.env['res.users'].browse(patwari_id)
        if not patwari.exists():
            return False
        return patwari.action_view_surveys_in_project(self.id)
    
    # Law Master - Many to One relationship
    law_master_id = fields.Many2one('bhu.law.master', string='Law', tracking=True,
                                    help='Select the law applicable to this project')
    
    # SIA Exemption - If True, project is exempt from Social Impact Assessment
    is_sia_exempt = fields.Boolean(string='SIA Exempt / सामाजिक समाघत अध्ययन से छूट', 
                                   default=False, tracking=True,
                                   help='If checked, this project is exempt from Social Impact Assessment. Section 4 and Expert Group will be disabled for this project.')
    
    # Company field for multi-company support
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                default=lambda self: self.env.company, tracking=True)
    
    # Section 4 Notification fields - These are project-level fields
    directly_affected = fields.Char(string='(दो) प्रत्यक्ष रूप से प्रभावित परिवारों की संख्या / Number of directly affected families', tracking=True,
                                      help='Number of directly affected families for this project')
    indirectly_affected = fields.Char(string='(तीन) अप्रत्यक्ष रूप से प्रभावित परिवारों की संख्या / Number of indirectly affected families', tracking=True,
                                        help='Number of indirectly affected families for this project')
    private_assets = fields.Char(string='(चार) प्रभावित क्षेत्र में निजी मकानों तथा अन्य परिसंपत्तियों की अनुमानित संख्या / Estimated number of private houses and other assets', tracking=True,
                                    help='Esti  mated number of private houses and other assets in the affected area')
    government_assets = fields.Char(string='(पाँच) प्रभावित क्षेत्र में शासकीय मकान तथा अन्य परिसंपत्तियों की अनुमानित संख्या / Estimated number of government houses and other assets', tracking=True,
                                      help='Estimated number of government houses and other assets in the affected area')
    total_cost = fields.Char(string='(आठ) परियोजना की कुल लागत / Total cost of the project', tracking=True,
                               help='Total cost of the project')
    project_benefits = fields.Text(string='(नौ) परियोजना से होने वाला लाभ / Benefits from the project', tracking=True,
                                      help='Benefits from the project')
    compensation_measures = fields.Text(string='(दस) प्रस्तावित सामाजिक समाघात की प्रतिपूर्ति के लिये उपाय तथा उस पर होने वाला संभावित व्यय / Measures for compensation and likely expenditure', tracking=True,
                                           help='Measures for compensation of proposed social impact and potential expenditure thereon')
    other_components = fields.Text(string='(ग्यारह) परियोजना द्वारा प्रभावित होने वाले अन्य घटक / Other components affected by the project', tracking=True,
                                      help='Other components affected by the project')
    
    # Section 11 Preliminary Report fields - These are project-level fields
    map_inspection_location = fields.Char(string='Land Map Inspection / भूमि मानचित्र निरीक्षण', tracking=True,
                                                       help='Location where land map can be inspected (SDO Revenue office)')
    authorized_officer = fields.Char(string='Officer authorized by Section 12 / धारा 12 द्वारा प्राधिकृत अधिकारी', tracking=True,
                                               help='Officer authorized by Section 12')
    is_displacement = fields.Boolean(string='Is Displacement Involved? / कितने परिवारों का विस्थापन निहित है।', 
                                                 default=False, tracking=True,
                                                 help='Whether displacement is involved for this project')
    affected_families_count = fields.Integer(string='Affected Families Count / प्रभावित परिवारों की संख्या', tracking=True,
                                                         help='Number of affected families if displacement is involved')
    affected_persons_count = fields.Integer(string='Affected Persons Count / प्रभावित व्यक्तियों की संख्या', tracking=True,
                                                         help='Number of persons affected by the proposed land acquisition who will be rehabilitated')
    is_exemption = fields.Boolean(string='Is Exemption Granted? / क्या प्रस्तावित परियोजना के लिए अधिनियम 2013 के अध्याय "दो" एवं "तीन" के प्रावधानों से छूट प्रदान की गई है।',
                                               default=False, tracking=True,
                                               help='Whether exemption is granted from Chapters Two and Three of Act 2013')
    section5_text_type = fields.Selection([
        ('exemption', 'प्रस्तावित प्रयोजन के लिए भूमि अर्जन को छत्तीसगढ़ शासन, राजस्व एवं आपदा प्रबंधन विभाग के अधिसूचना क्र. एफ 4-28/सात-1/2014, दिनाँक 02.03.2015 के द्वारा अधिनियम, 2013 के अध्याय "दो" एवं "तीन" के प्रावधानों से छूट प्रदान की गई है।'),
        ('sia_justification', 'प्रस्तावित प्रयोजन के भू-अर्जन के लिये कराये गये सामाजिक समाघात अध्ययन के अनुसार भूमि का अर्जन अंतिम विकल्प के रूप में किया जाना प्रस्तावित है तथा भूमि अर्जन से सामाजिक समाघात की तुलना में सामाजिक लाभ अधिक होना पाया गया है।')
    ], string='Section 5 Text / धारा 5 पाठ', default='exemption', tracking=True,
       help='Select which text to display in Section 5 of the report')
    exemption_details = fields.Text(string='Exemption Details / छूट विवरण', tracking=True,
                                                 help='Details of exemption notification (number, date, exempted chapters)')
    sia_justification = fields.Text(string='SIA Justification / SIA औचित्य', tracking=True,
                                                help='SIA justification details (last resort, social benefits)')
    rehab_admin_name = fields.Char(string='Rehabilitation Administrator / पुनर्वास प्रशासक', tracking=True,
                                               help='Name/Designation of Rehabilitation and Resettlement Administrator')
    
    # KML File for Map Visualization
    kml_file = fields.Binary(string='KML File / KML फाइल', attachment=True, 
                             help='Upload a KML file to view on map')
    kml_filename = fields.Char(string='KML Filename')

    @api.onchange('department_id')
    def _onchange_department_id(self):
        if self.department_id:
            self.authorized_officer = self.department_id.name

    @api.depends('sub_division_id', 'sub_division_id.user_id')
    def _compute_sub_division_sdm_ids(self):
        for rec in self:
            rec.sub_division_sdm_ids = rec.sub_division_id.mapped('user_id').filtered('id')

    @api.onchange('sub_division_id')
    def _onchange_sub_division_sdm_rehab(self):
        users = self.sub_division_id.mapped('user_id').filtered('id')
        if users:
            self.rehab_admin_name = ", ".join(users.mapped('name'))

    def _bhu_sync_sdm_from_sub_division(self):
        """Persist SDM users from linked sub divisions (onchange alone does not save)."""
        for rec in self:
            if rec.sub_division_id:
                users = rec.sub_division_id.mapped('user_id').filtered('id')
                rec.sdm_ids = users
            else:
                rec.sdm_ids = False

    @api.model
    def _bhu_repair_stale_sdm_links(self):
        """Remove district-wide SDM links where sub division was never set."""
        stale = self.sudo().search([
            ('sub_division_id', '=', False),
            ('sdm_ids', '!=', False),
        ])
        if stale:
            stale.write({'sdm_ids': [(5, 0, 0)]})
        with_sub = self.sudo().search([('sub_division_id', '!=', False)])
        if with_sub:
            with_sub._bhu_sync_sdm_from_sub_division()
        return len(stale)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bhu_sync_sdm_from_sub_division()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'sub_division_id' in vals:
            self._bhu_sync_sdm_from_sub_division()
        return res
    
    # Rehabilitation Allocation Fields (shown when is_displacement is True)
    allocated_village = fields.Char(string='Allocated Village / आवंटित ग्राम', tracking=True,
                                     help='Village allocated for rehabilitation and resettlement')
    allocated_tehsil = fields.Char(string='Allocated Tehsil / आवंटित तहसील', tracking=True,
                                  help='Tehsil allocated for rehabilitation and resettlement')
    allocated_district = fields.Char(string='Allocated District / आवंटित जिला', tracking=True,
                                     help='District allocated for rehabilitation and resettlement')
    allocated_khasra_number = fields.Char(string='Allocated Khasra Number / आवंटित खसरा नंबर', tracking=True,
                                         help='Khasra number of the allocated land for rehabilitation')
    allocated_area_hectares = fields.Float(string='Allocated Area (Hectares) / आवंटित रकबा (हेक्टेयर)', 
                                          digits=(16, 4), tracking=True,
                                          help='Area in hectares allocated for rehabilitation and resettlement')
    
    # Computed fields for List View display
    sia_exempt_display = fields.Char(string='SIA Exempt Status', compute='_compute_yes_no_flags')
    displacement_display = fields.Char(string='Displacement Status', compute='_compute_yes_no_flags')
    pipeline_stage_indicator = fields.Char(
        string='Stages',
        compute='_compute_pipeline_stage_indicator',
        store=False,
    )

    @api.depends('is_sia_exempt')
    def _compute_pipeline_stage_indicator(self):
        """Unused value; anchors ``widget=bhu_project_stage`` on list/form."""
        for rec in self:
            rec.pipeline_stage_indicator = ''

    @api.depends('is_sia_exempt', 'is_displacement')
    def _compute_yes_no_flags(self):
        for rec in self:
            rec.sia_exempt_display = 'Yes' if rec.is_sia_exempt else 'No'
            rec.displacement_display = 'Yes' if rec.is_displacement else 'No'
    
    @api.model
    def _search(self, args, offset=0, limit=None, order=None):
        """Override search to filter projects by user's assigned projects"""
        # Skip filtering if context flag is set (to avoid recursion)
        if self.env.context.get('skip_project_domain_filter'):
            return super()._search(args, offset=offset, limit=limit, order=order)
        
        # Get current user
        user = self.env.user
        
        # Allow public users to access all projects if they have access rights
        # This is needed for API endpoints that use auth='public' with sudo()
        if user.has_group('base.group_public') and not user.has_group('base.group_user'):
            # Public user - check if they have access rights, if so, allow access to all projects
            # The access rights check will happen at the ORM level, so we don't filter here
            return super()._search(args, offset=offset, limit=limit, order=order)
        
        # Admin, system users, and collectors see all projects - no filtering needed
        if not (user.has_group('bhukhadan_core.group_bhuarjan_admin') or 
                user.has_group('bhukhadan_core.group_bhuarjan_department_user') or
                user.has_group('base.group_system') or
                user.has_group('bhukhadan_core.group_bhuarjan_collector') or
                user.has_group('bhukhadan_core.group_bhuarjan_additional_collector') or
                user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')):
            try:
                # Get user's assigned projects using sudo() to bypass access rights and context flag to avoid recursion
                # Use sudo() to ensure we can search even if user doesn't have direct access
                # Include department users in the search
                assigned_projects = self.sudo().with_context(skip_project_domain_filter=True).search([
                    '|', '|', '|',
                    ('sdm_ids', 'in', user.id),
                    ('tehsildar_ids', 'in', user.id),
                    ('department_user_ids', 'in', user.id),
                    ('sub_division_id.user_id', 'in', user.id),
                ])
                
                if assigned_projects:
                    # Add domain to filter by assigned projects
                    args = args + [('id', 'in', assigned_projects.ids)]
                else:
                    # No assigned projects, return domain that matches nothing
                    args = args + [('id', 'in', [])]
            except Exception as e:
                # If there's an error getting assigned projects, log it and continue without filtering
                # This ensures users can still access projects if they have proper access rights
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Error filtering projects by assigned projects for user {user.id}: {e}")
                # Continue with original args - don't filter if there's an error
        
        # Call parent search with modified domain
        return super()._search(args, offset=offset, limit=limit, order=order)

    def get_project_progress(self):
        """Returns progress of each stage for the project with icons and counts"""
        self.ensure_one()
        villages = self.village_ids
        village_count = len(villages)
        
        def get_village_info(model_name, domain_extra=[]):
            if not village_count:
                return {'status': 'not_started', 'count': 0, 'total': 0, 'details': 'No Villages'}
            
            domain = [('project_id', '=', self.id)] + domain_extra
            records = self.env[model_name].sudo().search(domain)
            
            approved_records = records.filtered(lambda r: r.state == 'approved')
            approved_villages = approved_records.mapped('village_id')
            count = len(approved_villages)
            
            status = 'not_started'
            if count >= village_count and village_count > 0:
                status = 'completed'
            elif records:
                status = 'in_progress'
            
            return {
                'status': status,
                'count': count,
                'total': village_count,
                'details': f"{count}/{village_count} Villages"
            }

        def get_project_level_info(model_name):
            records = self.env[model_name].sudo().search([('project_id', '=', self.id)])
            approved = records.filtered(lambda r: r.state == 'approved')
            
            status = 'not_started'
            details = 'Pending'
            if approved:
                status = 'completed'
                details = 'Approved'
            elif records:
                status = 'in_progress'
                details = 'Draft/Submitted'
                
            return {
                'status': status,
                'details': details
            }

        # Survey Status
        surveys = self.env['bhu.survey'].sudo().search([('project_id', '=', self.id)])
        survey_count = len(surveys)
        approved_surveys = surveys.filtered(lambda s: s.state in ('approved', 'locked'))
        survey_status = 'completed' if survey_count > 0 and len(approved_surveys) == survey_count else ('in_progress' if survey_count > 0 else 'not_started')
        
        stages = [
            {
                'id': 'survey',
                'name': 'Surveying / सर्वेक्षण',
                'status': survey_status,
                'icon': 'fa-clipboard',
                'count': len(approved_surveys),
                'total': survey_count,
                'details': f"{len(approved_surveys)}/{survey_count} Approved"
            }
        ]

        # Section 4
        s4_info = get_village_info('bhu.section4.notification')
        stages.append({
            'id': 'section4',
            'name': 'Sec 4(i) Notification of intention to prospect',
            'status': s4_info['status'],
            'icon': 'fa-bullhorn',
            'count': s4_info['count'],
            'total': s4_info['total'],
            'details': s4_info['details']
        })
        
        if not self.is_sia_exempt:
            sia_info = get_project_level_info('bhu.sia.team')
            stages.append({
                'id': 'sia_team',
                'name': 'Sec 7(i) Notification of intention to acquire land',
                'status': sia_info['status'],
                'icon': 'fa-users',
                'details': sia_info['details']
            })

        s8_info = get_project_level_info('bhu.section8')
        stages.append({
            'id': 'section8',
            'name': 'Sec 8 Objections',
            'status': s8_info['status'],
            'icon': 'fa-gavel',
            'details': s8_info['details']
        })

        s9_info = get_village_info('bhu.section9.notification')
        stages.append({
            'id': 'section9',
            'name': 'Sec 9(i) Declaration of acquisition',
            'status': s9_info['status'],
            'icon': 'fa-flag',
            'count': s9_info['count'],
            'total': s9_info['total'],
            'details': s9_info['details']
        })

        # Section 11
        s11_info = get_village_info('bhu.section11.preliminary.report')
        stages.append({
            'id': 'section11',
            'name': 'Sec 11(i) Vesting order',
            'status': s11_info['status'],
            'icon': 'fa-file-text-o',
            'count': s11_info['count'],
            'total': s11_info['total'],
            'details': s11_info['details']
        })

        # Section 15
        s15_info = get_village_info('bhu.section15.objection')
        stages.append({
            'id': 'section15',
            'name': 'Post-Gazette Step 1 Land Records',
            'status': s15_info['status'],
            'icon': 'fa-comments-o',
            'count': s15_info['count'],
            'total': s15_info['total'],
            'details': s15_info['details']
        })

        # Section 19
        s19_info = get_village_info('bhu.section19.notification')
        stages.append({
            'id': 'section19',
            'name': 'Post-Gazette Step 2 DRRC Meeting',
            'status': s19_info['status'],
            'icon': 'fa-newspaper-o',
            'count': s19_info['count'],
            'total': s19_info['total'],
            'details': s19_info['details']
        })

        # Section 21
        s21_info = get_village_info('bhu.section21.notification')
        stages.append({
            'id': 'section21',
            'name': 'Post-Gazette Step 3 Asset Survey Committee Formation',
            'status': s21_info['status'],
            'icon': 'fa-map-marker',
            'count': s21_info['count'],
            'total': s21_info['total'],
            'details': s21_info['details']
        })

        # Section 23
        s23_info = get_village_info('bhu.section23.award')
        stages.append({
            'id': 'section23',
            'name': 'Post-Gazette Step 5 Land Compensation & Award',
            'status': s23_info['status'],
            'icon': 'fa-trophy',
            'count': s23_info['count'],
            'total': s23_info['total'],
            'details': s23_info['details']
        })

        pv_info = self._pipeline_payment_voucher_info()
        stages.append({
            'id': 'payment_voucher',
            'name': _('Payment Voucher / भुगतान वाउचर'),
            'status': pv_info['status'],
            'icon': 'fa-credit-card',
            'count': pv_info.get('count', 0),
            'total': pv_info.get('total', 0),
            'details': pv_info['details'],
        })

        pf_info = self._pipeline_payment_file_info()
        stages.append({
            'id': 'payment_file',
            'name': _('Payment File / भुगतान फ़ाइल'),
            'status': pf_info['status'],
            'icon': 'fa-file-excel-o',
            'count': pf_info.get('count', 0),
            'total': pf_info.get('total', 0),
            'details': pf_info['details'],
        })

        return stages

    def _pipeline_payment_voucher_info(self, village_id=None):
        """One R&R payment voucher per Section 23 award (village)."""
        self.ensure_one()
        Award = self.env['bhu.section23.award'].sudo()
        Voucher = self.env['bhu.payment.voucher'].sudo()
        award_domain = [('project_id', '=', self.id)]
        if village_id:
            award_domain.append(('village_id', '=', int(village_id)))
        awards = Award.search(award_domain)
        if village_id:
            award = awards[:1]
            if not award:
                return {
                    'status': 'not_started',
                    'details': _('No award — create Section 23 first'),
                    'count': 0,
                    'total': 1,
                }
            voucher = Voucher.search([('award_id', '=', award.id)], limit=1)
            if not voucher:
                return {
                    'status': 'not_started',
                    'details': _('Not generated — click Create'),
                    'count': 0,
                    'total': 1,
                }
            return {
                'status': 'completed',
                'details': _('Voucher generated'),
                'count': 1,
                'total': 1,
            }

        vouchers = Voucher.search([('award_id', 'in', awards.ids)]) if awards else Voucher.browse()
        by_award = {v.award_id.id: v for v in vouchers}
        generated = sum(1 for award in awards if by_award.get(award.id))
        total = len(awards) or len(self.village_ids)
        if not total:
            total = len(vouchers.mapped('village_id'))
        status = 'completed' if awards and generated >= len(awards) else (
            'in_progress' if awards else 'not_started'
        )
        return {
            'status': status,
            'details': _('%s/%s vouchers generated') % (generated, total or len(awards)),
            'count': generated,
            'total': total or len(awards),
        }

    def _pipeline_payment_file_amounts(self, village_id=None):
        """Voucher payable vs total generated payment file amount for pipeline / dashboard."""
        self.ensure_one()
        Voucher = self.env['bhu.payment.voucher'].sudo()
        Export = self.env['bhu.payment.voucher.export'].sudo()
        domain = [('project_id', '=', self.id)]
        if village_id:
            domain.append(('village_id', '=', int(village_id)))
        vouchers = Voucher.search(domain)
        voucher_amount = sum(float(v.total_determined or 0.0) for v in vouchers)
        exports = Export.search([('voucher_id', 'in', vouchers.ids)]) if vouchers else Export.browse()
        file_amount = sum(float(e.amount or 0.0) for e in exports)
        pending_amount = max(0.0, voucher_amount - file_amount)
        epsilon = 0.01
        is_complete = voucher_amount > epsilon and pending_amount <= epsilon
        return {
            'voucher_amount': voucher_amount,
            'file_amount': file_amount,
            'pending_amount': pending_amount,
            'file_count': len(exports),
            'is_complete': is_complete,
            'has_voucher': bool(vouchers),
        }

    def _pipeline_payment_file_info(self, village_id=None):
        """Payment files complete when filed amount equals voucher payable (no approval)."""
        self.ensure_one()
        amounts = self._pipeline_payment_file_amounts(village_id)
        if village_id:
            if not amounts['has_voucher']:
                return {
                    'status': 'not_started',
                    'details': _('Create payment voucher first'),
                    'count': 0,
                    'total': 1,
                }
            if amounts['is_complete']:
                status = 'completed'
                details = _('₹%s filed — voucher total matched') % (
                    f'{amounts["file_amount"]:,.0f}',
                )
            elif amounts['file_count']:
                status = 'in_progress'
                details = _('₹%s / ₹%s filed — pending') % (
                    f'{amounts["file_amount"]:,.0f}',
                    f'{amounts["voucher_amount"]:,.0f}',
                )
            else:
                status = 'in_progress'
                details = _('₹%s payable — generate payment file') % (
                    f'{amounts["voucher_amount"]:,.0f}',
                )
            return {
                'status': status,
                'details': details,
                'count': 1 if amounts['is_complete'] else 0,
                'total': 1,
            }

        vouchers = self.env['bhu.payment.voucher'].sudo().search([
            ('project_id', '=', self.id),
        ])
        complete_villages = 0
        for village in vouchers.mapped('village_id'):
            if self._pipeline_payment_file_amounts(village.id)['is_complete']:
                complete_villages += 1
        total_villages = len(vouchers.mapped('village_id')) or len(self.village_ids)
        file_count = amounts['file_count']
        status = 'completed' if total_villages and complete_villages >= total_villages else (
            'in_progress' if amounts['has_voucher'] or file_count else 'not_started'
        )
        return {
            'status': status,
            'details': _('%s file(s) · %s/%s villages amount complete') % (
                file_count, complete_villages, total_villages or complete_villages
            ),
            'count': complete_villages,
            'total': total_villages or 1,
        }

    def _dashboard_pipeline_dots(self):
        """RFCTLARR + payment pipeline for dashboards (same order as ``get_project_progress``)."""
        self.ensure_one()
        stages_list = self.get_project_progress()
        smap = {s['id']: s for s in stages_list}
        exempt = self.is_sia_exempt
        dots = []
        for sid in _BHU_PIPELINE_DOT_IDS:
            if sid in ('sia_team', 'expert_committee') and exempt:
                dots.append(_bhu_pipeline_dot_payload(
                    sid, 'na', _('Not applicable (SIA exempt)'),
                ))
                continue
            st = smap.get(sid)
            if not st:
                dots.append(_bhu_pipeline_dot_payload(sid, 'pending', _('Pending')))
                continue
            status = st.get('status') or 'not_started'
            if status == 'completed':
                kind = 'done'
            elif status == 'in_progress':
                kind = 'active'
            else:
                kind = 'pending'
            name = st.get('name') or sid
            detail = st.get('details') or ''
            title = name + (f' ({detail})' if detail else '')
            dots.append(_bhu_pipeline_dot_payload(sid, kind, title))
        return dots

    def _get_village_progress(self, village_id):
        """Same pipeline semantics as ``get_project_progress`` but for one village on this project."""
        self.ensure_one()
        vid = int(village_id)

        def village_stage_aggregate(model_name):
            domain = [('project_id', '=', self.id), ('village_id', '=', vid)]
            records = self.env[model_name].sudo().search(domain)
            approved_recs = records.filtered(lambda r: r.state == 'approved')
            status = 'not_started'
            if approved_recs:
                status = 'completed'
            elif records:
                status = 'in_progress'
            return {
                'status': status,
                'count': 1 if approved_recs else 0,
                'total': 1,
                'details': _('1/1 Villages') if approved_recs else (_('In progress') if records else _('0/1 Villages')),
            }

        def project_level_info(model_name):
            records = self.env[model_name].sudo().search([('project_id', '=', self.id)])
            approved = records.filtered(lambda r: r.state == 'approved')
            st = 'not_started'
            details = _('Pending')
            if approved:
                st = 'completed'
                details = _('Approved')
            elif records:
                st = 'in_progress'
                details = _('Draft/Submitted')
            return {'status': st, 'details': details}

        surveys = self.env['bhu.survey'].sudo().search([
            ('project_id', '=', self.id),
            ('village_id', '=', vid),
        ])
        survey_count = len(surveys)
        approved_surveys = surveys.filtered(lambda s: s.state in ('approved', 'locked'))
        survey_status = (
            'completed' if survey_count > 0 and len(approved_surveys) == survey_count
            else ('in_progress' if survey_count > 0 else 'not_started')
        )

        stages = [
            {
                'id': 'survey',
                'name': _('Surveying / सर्वेक्षण'),
                'status': survey_status,
                'icon': 'fa-clipboard',
                'count': len(approved_surveys),
                'total': survey_count,
                'details': _('%s/%s Approved') % (len(approved_surveys), survey_count),
            }
        ]

        s4_info = village_stage_aggregate('bhu.section4.notification')
        stages.append({
            'id': 'section4',
            'name': _('Sec 4(i) Notification of intention to prospect'),
            'status': s4_info['status'],
            'icon': 'fa-bullhorn',
            'count': s4_info['count'],
            'total': s4_info['total'],
            'details': s4_info['details'],
        })

        if not self.is_sia_exempt:
            sia_info = project_level_info('bhu.sia.team')
            stages.append({
                'id': 'sia_team',
                'name': _('Sec 7(i) Notification of intention to acquire land'),
                'status': sia_info['status'],
                'icon': 'fa-users',
                'details': sia_info['details'],
            })

        s8_info = project_level_info('bhu.section8')
        stages.append({
            'id': 'section8',
            'name': _('Sec 8 Objections'),
            'status': s8_info['status'],
            'icon': 'fa-gavel',
            'details': s8_info['details'],
        })

        s9_info = village_stage_aggregate('bhu.section9.notification')
        stages.append({
            'id': 'section9',
            'name': _('Sec 9(i) Declaration of acquisition'),
            'status': s9_info['status'],
            'icon': 'fa-flag',
            'count': s9_info['count'],
            'total': s9_info['total'],
            'details': s9_info['details'],
        })

        s11_info = village_stage_aggregate('bhu.section11.preliminary.report')
        stages.append({
            'id': 'section11',
            'name': _('Sec 11(i) Vesting order'),
            'status': s11_info['status'],
            'icon': 'fa-file-text-o',
            'count': s11_info['count'],
            'total': s11_info['total'],
            'details': s11_info['details'],
        })

        s15_info = village_stage_aggregate('bhu.section15.objection')
        stages.append({
            'id': 'section15',
            'name': _('Post-Gazette Step 1 Land Records'),
            'status': s15_info['status'],
            'icon': 'fa-comments-o',
            'count': s15_info['count'],
            'total': s15_info['total'],
            'details': s15_info['details'],
        })

        s19_info = village_stage_aggregate('bhu.section19.notification')
        stages.append({
            'id': 'section19',
            'name': _('Post-Gazette Step 2 DRRC Meeting'),
            'status': s19_info['status'],
            'icon': 'fa-newspaper-o',
            'count': s19_info['count'],
            'total': s19_info['total'],
            'details': s19_info['details'],
        })

        s21_info = village_stage_aggregate('bhu.section21.notification')
        stages.append({
            'id': 'section21',
            'name': _('Post-Gazette Step 3 Asset Survey Committee Formation'),
            'status': s21_info['status'],
            'icon': 'fa-map-marker',
            'count': s21_info['count'],
            'total': s21_info['total'],
            'details': s21_info['details'],
        })

        s23_info = village_stage_aggregate('bhu.section23.award')
        stages.append({
            'id': 'section23',
            'name': _('Post-Gazette Step 5 Land Compensation & Award'),
            'status': s23_info['status'],
            'icon': 'fa-trophy',
            'count': s23_info['count'],
            'total': s23_info['total'],
            'details': s23_info['details'],
        })

        pv_info = self._pipeline_payment_voucher_info(village_id)
        stages.append({
            'id': 'payment_voucher',
            'name': _('Payment Voucher / भुगतान वाउचर'),
            'status': pv_info['status'],
            'icon': 'fa-credit-card',
            'count': pv_info.get('count', 0),
            'total': pv_info.get('total', 0),
            'details': pv_info['details'],
        })

        pf_info = self._pipeline_payment_file_info(village_id)
        stages.append({
            'id': 'payment_file',
            'name': _('Payment File / भुगतान फ़ाइल'),
            'status': pf_info['status'],
            'icon': 'fa-file-excel-o',
            'count': pf_info.get('count', 0),
            'total': pf_info.get('total', 0),
            'details': pf_info['details'],
        })

        return stages

    def _village_dashboard_pipeline_dots(self, village_id):
        """Pipeline rows for one village (aligned with ``_dashboard_pipeline_dots``)."""
        self.ensure_one()
        stages_list = self._get_village_progress(village_id)
        smap = {s['id']: s for s in stages_list}
        exempt = self.is_sia_exempt
        dots = []
        for sid in _BHU_PIPELINE_DOT_IDS:
            if sid in ('sia_team', 'expert_committee') and exempt:
                dots.append(_bhu_pipeline_dot_payload(
                    sid, 'na', _('Not applicable (SIA exempt)'),
                ))
                continue
            st = smap.get(sid)
            if not st:
                dots.append(_bhu_pipeline_dot_payload(sid, 'pending', _('Pending')))
                continue
            status = st.get('status') or 'not_started'
            if status == 'completed':
                kind = 'done'
            elif status == 'in_progress':
                kind = 'active'
            else:
                kind = 'pending'
            name = st.get('name') or sid
            detail = st.get('details') or ''
            title = name + ((' (%s)' % detail) if detail else '')
            dots.append(_bhu_pipeline_dot_payload(sid, kind, title))
        return dots

    @api.model
    def get_village_pipeline_dots_for_dashboard(self, pairs):
        """Batch village pipeline dots: ``pairs`` is list of ``[project_id, village_id]``.

        Returns dict keyed ``\"{project_id}_{village_id}\"``.
        """
        by_project = defaultdict(list)
        for pair in pairs or []:
            if not pair or len(pair) < 2:
                continue
            try:
                pid = int(pair[0])
                vid = int(pair[1])
            except (TypeError, ValueError):
                continue
            by_project[pid].append(vid)
        out = {}
        for pid, vids in by_project.items():
            project = self.sudo().browse(pid)
            if not project.exists():
                continue
            for vid in vids:
                key = '%s_%s' % (project.id, int(vid))
                out[key] = project._village_dashboard_pipeline_dots(int(vid))
        return out

    @api.model
    def get_village_progress_timeline_for_dashboard(self, project_id, village_id):
        """Stages payload for timeline dialog (village scoped); used by SDM Pipeline Dashboard."""
        proj = self.sudo().browse(int(project_id))
        if not proj.exists():
            return []
        return proj._get_village_progress(int(village_id))

    @api.model
    def get_pipeline_dots_for_dashboard(self, project_ids):
        """Return ``{project_id: [{id, kind, title}, ...]}`` for group dashboard (single RPC)."""
        ids = [int(i) for i in (project_ids or []) if i]
        out = {}
        for project in self.sudo().browse(ids):
            if project.exists():
                out[project.id] = project._dashboard_pipeline_dots()
        return out

    @api.model
    def get_acquisition_stage_map(self, project_ids):
        """Batch map project id → coarse acquisition stage (matches Group Dashboard ordering)."""
        ids = [int(i) for i in (project_ids or []) if i]
        if not ids:
            return {}

        def proj_set(model):
            recs = self.env[model].search([('project_id', 'in', ids)])
            return set(recs.mapped('project_id').ids)

        award_p = proj_set('bhu.section23.award')
        s21_p = proj_set('bhu.section21.notification')
        s19_p = proj_set('bhu.section19.notification')
        s11_p = proj_set('bhu.section11.preliminary.report')
        s4_p = proj_set('bhu.section4.notification')
        sia_p = proj_set('bhu.sia.team')

        out = {}
        for pid in ids:
            if pid in award_p:
                out[pid] = 'award'
            elif pid in s21_p:
                out[pid] = 'section21'
            elif pid in s19_p:
                out[pid] = 'section19'
            elif pid in s11_p:
                out[pid] = 'section11'
            elif pid in s4_p:
                out[pid] = 'section4'
            elif pid in sia_p:
                out[pid] = 'sia'
            else:
                out[pid] = 'initial'
        return out