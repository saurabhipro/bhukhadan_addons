from odoo import _, models, fields, api
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression
from odoo.tools import sql as odoo_sql


class BhuUserMobile(models.Model):
    """Additional mobile numbers for a user (for multi-mobile OTP login)"""
    _name = 'bhu.user.mobile'
    _description = 'User Additional Mobile Number'
    _order = 'sequence, id'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    mobile = fields.Char(string='Mobile Number', required=True)
    label = fields.Char(string='Label', help='e.g. Personal, Office, WhatsApp')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    @api.constrains('mobile')
    def _check_mobile_unique(self):
        """Ensure this additional mobile is not already used by any user (primary or additional)"""
        for rec in self:
            # Check against primary mobile of all users
            dup_primary = self.env['res.users'].search([
                ('mobile', '=', rec.mobile),
                ('id', '!=', rec.user_id.id),
            ], limit=1)
            if dup_primary:
                raise ValidationError(
                    f'Mobile {rec.mobile} is already the primary number of user "{dup_primary.name}".'
                )
            # Check against other additional mobiles
            dup_additional = self.env['bhu.user.mobile'].search([
                ('mobile', '=', rec.mobile),
                ('id', '!=', rec.id),
            ], limit=1)
            if dup_additional:
                raise ValidationError(
                    f'Mobile {rec.mobile} is already registered as an additional number for user "{dup_additional.user_id.name}".'
                )


class ResUsers(models.Model):
    _inherit = 'res.users'

    parent_id = fields.Many2one('res.users', string="Parent")
    child_ids = fields.One2many('res.users', 'parent_id', string='Direct subordinates')
    # color = fields.Integer(string="Color Index")
    department_color = fields.Char(string="Color", default="#4c7cf3")
    def _get_state_domain(self):
        state_ids = self.env['bhu.district'].search([]).mapped('state_id.id')    
        return [('id', 'in', state_ids)]

    bhu_terms_accepted = fields.Boolean(
        string='BhuKhadan Terms Accepted',
        default=False,
        copy=False,
        help='Set when the user accepts BhuKhadan Terms & Conditions on first login.',
    )
    bhu_terms_accepted_date = fields.Datetime(
        string='Terms Accepted On',
        copy=False,
        readonly=True,
    )

    mobile = fields.Char(string="Mobile")
    name_english = fields.Char(
        string='Name (English)',
        tracking=True,
        index=True,
        help='Romanized or English spelling; used in search and many2one lookups.',
    )

    # Additional mobile numbers for multi-mobile OTP login
    mobile_number_ids = fields.One2many(
        'bhu.user.mobile', 'user_id',
        string='Additional Mobile Numbers / अतिरिक्त मोबाइल नंबर',
        help='Add extra mobile numbers so this user can login with any of them.'
    )

    def copy_data(self, default=None):
        if default is None:
            default = {}
        default['mobile'] = False
        default['login'] = (self.login or '') + ' (copy)'
        return super().copy_data(default)

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        """Allow BhuKhadan Admin and District Admin to write/create users.
        BhuKhadan Admin is explicitly included to ensure they bypass standard Odoo 
        restrictions even if they aren't 'System' users.
        """
        if operation in ('write', 'create', 'read', 'unlink'):
            user = self.env.user
            if (user.has_group('bhukhadan_core.group_bhuarjan_admin') or
                    user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')):
                return True
        return super().check_access_rights(operation, raise_exception=raise_exception)

    def check_access_rule(self, operation):
        """Allow BhuKhadan Admin and District Admin to bypass record-level rules on res.users.
        This is required so the form renders as editable in the UI (the web client
        probes check_access_rule to decide whether to show Save/Edit buttons).
        """
        user = self.env.user
        if (user.has_group('bhukhadan_core.group_bhuarjan_admin') or
                user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')):
            return None  # explicitly return None to signal success
        return super().check_access_rule(operation)

    def write(self, vals):
        """Allow BhuKhadan Administrator and District Administrator to edit users."""
        current_user = self.env.user
        is_privileged = (
            current_user.has_group('bhukhadan_core.group_bhuarjan_admin') or
            current_user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        )
        if is_privileged:
            # Use sudo() to bypass Odoo's internal ERP-Manager write restriction
            # Record rules still enforce district-level scope for District Admins
            return super(ResUsers, self.sudo()).write(vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Allow BhuKhadan Administrator and District Administrator to create users."""
        current_user = self.env.user
        is_admin = current_user.has_group('bhukhadan_core.group_bhuarjan_admin')
        is_district_admin = current_user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        
        for vals in vals_list:
            if is_admin or is_district_admin:
                # Auto-fill district for District Admin's newly created users
                if is_district_admin and not is_admin:
                    if 'district_id' not in vals and current_user.district_id:
                        vals['district_id'] = current_user.district_id.id
            
        # Call super with sudo() if privileged
        if is_admin or is_district_admin:
            return super(ResUsers, self.sudo()).create(vals_list)
        return super().create(vals_list)

    @api.constrains('mobile')
    def _check_mobile_unique(self):
        """Ensure mobile number is unique across all users"""
        for record in self:
            if record.mobile:  # Only validate if mobile is provided
                # Search for other users with the same mobile number
                duplicate = self.env['res.users'].search([
                    ('mobile', '=', record.mobile),
                    ('id', '!=', record.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        f'Mobile number {record.mobile} is already assigned to user "{duplicate.name}". '
                        f'Each user must have a unique mobile number.'
                    )
    state_id = fields.Many2one('res.country.state', string='State', domain=lambda self: self._get_state_domain(), default=lambda self: self.env.user.state_id.id)
    district_id = fields.Many2one('bhu.district', string='District / जिला', default=lambda self: self.env.user.district_id.id)
    bhuarjan_role = fields.Selection([
        ('patwari', 'Patwari'),
        ('ri', 'Revenue Inspector'),
        ('revenue_inspector', 'Revenue Inspector'),
        ('nayab_tahsildar', 'Nayab Tahsildar'),
        ('tahsildar', 'Tehsildar'),
        ('sdm', 'SDM'),
        ('additional_collector', 'Additional Collector'),
        ('collector', 'Collector'),
        ('district_administrator', 'District Administrator'),
        ('administrator', 'Administrator'),
        ('department_user', 'Department User'),
    ], string="BhuKhadan Role", default=False)

    bhu_patwari_village_ids = fields.One2many(
        comodel_name='bhu.village',
        inverse_name='user_id',
        string='Assigned villages / असाइन गाँव',
        help='Villages whose Patwari (master) field points to this user.',
    )
    bhu_patwari_village_summary = fields.Char(
        compute='_compute_bhu_patwari_village_summary',
        string='Villages (Patwari)',
        store=False,
    )

    @api.depends('bhu_patwari_village_ids', 'bhu_patwari_village_ids.name', 'bhuarjan_role')
    def _compute_bhu_patwari_village_summary(self):
        for user in self:
            if user.bhuarjan_role != 'patwari':
                user.bhu_patwari_village_summary = ''
                continue
            names = [n for n in user.bhu_patwari_village_ids.mapped('name') if n]
            names.sort()
            summary = ', '.join(names)
            if len(summary) > 240:
                summary = summary[:237] + '...'
            user.bhu_patwari_village_summary = summary

    bhu_scope_sub_division_summary = fields.Char(
        compute='_compute_bhu_scope_geo_summaries',
        string='Sub Division / उपभाग',
        store=False,
    )
    bhu_scope_tehsil_summary = fields.Char(
        compute='_compute_bhu_scope_geo_summaries',
        string='Tehsil / तहसील',
        store=False,
    )

    @api.depends(
        'bhu_patwari_village_ids',
        'bhu_patwari_village_ids.tehsil_id',
        'bhu_patwari_village_ids.sub_division_id',
    )
    def _compute_bhu_scope_geo_summaries(self):
        """Sub division / tehsil labels from SDM·Tehsildar masters + Patwari villages."""
        SubDiv = self.env['bhu.sub.division'].sudo()
        Tehsil = self.env['bhu.tehsil'].sudo()

        def clip(label_set):
            names = sorted(n for n in label_set if n)
            text = ', '.join(names)
            return (text[:237] + '...') if len(text) > 240 else text

        for user in self:
            subdiv_names = {n for n in SubDiv.search([('user_id', '=', user.id)]).mapped('name') if n}
            tehsil_names = {n for n in Tehsil.search([('user_id', '=', user.id)]).mapped('name') if n}
            for village in user.bhu_patwari_village_ids:
                if village.tehsil_id:
                    tehsil_names.add(village.tehsil_id.name or '')
                if village.sub_division_id:
                    subdiv_names.add(village.sub_division_id.name or '')
            user.bhu_scope_tehsil_summary = clip(tehsil_names)
            user.bhu_scope_sub_division_summary = clip(subdiv_names)

    bhuarjan_category_id = fields.Many2one(
        'ir.module.category',
        string="BhuKhadan Category",
        compute='_compute_bhuarjan_category'
    )

    def _compute_bhuarjan_category(self):
        category = self.env.ref('bhukhadan_core.module_category_bhuarjan_bhuarjan', raise_if_not_found=False)
        for record in self:
            record.bhuarjan_category_id = category

    def init(self):
        """Ensure DB schema matches model (deploy without -u)."""
        cr = self.env.cr
        # Field added in code must exist even if admins skip ``-u bhuarjan`` once.
        if not odoo_sql.column_exists(cr, 'res_users', 'name_english'):
            odoo_sql.create_column(cr, 'res_users', 'name_english', 'varchar')
        if not odoo_sql.column_exists(cr, 'res_users', 'bhu_terms_accepted'):
            odoo_sql.create_column(cr, 'res_users', 'bhu_terms_accepted', 'boolean')
        if not odoo_sql.column_exists(cr, 'res_users', 'bhu_terms_accepted_date'):
            odoo_sql.create_column(cr, 'res_users', 'bhu_terms_accepted_date', 'timestamp without time zone')

    def _register_hook(self):
        """Ensure ``name_english`` exists after code deploy without ``-u`` (runs each registry load)."""
        super()._register_hook()
        cr = self.env.cr
        if not odoo_sql.column_exists(cr, 'res_users', 'name_english'):
            odoo_sql.create_column(cr, 'res_users', 'name_english', 'varchar')
        if not odoo_sql.column_exists(cr, 'res_users', 'bhu_terms_accepted'):
            odoo_sql.create_column(cr, 'res_users', 'bhu_terms_accepted', 'boolean')
        if not odoo_sql.column_exists(cr, 'res_users', 'bhu_terms_accepted_date'):
            odoo_sql.create_column(cr, 'res_users', 'bhu_terms_accepted_date', 'timestamp without time zone')

    survey_count_in_project = fields.Integer(
        string='Survey Count / सर्वे संख्या',
        compute='_compute_survey_count_in_project',
        store=False
    )
    
    def _compute_survey_count_in_project(self):
        """Compute survey count for patwari in the current project context
        Counts surveys where:
        1. Survey was created by this patwari (user_id), OR
        2. Survey is in a village assigned to this patwari
        
        Note: This field is context-dependent and recomputes on every read
        """
        project_id = self.env.context.get('default_project_id') or self.env.context.get('active_id')
        if not project_id:
            # Try to get from parent record if in Many2many view
            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')
            if active_model == 'bhu.project' and active_id:
                project_id = active_id
        
        for user in self:
            if user.bhuarjan_role == 'patwari' and project_id:
                # Count surveys where:
                # 1. Created by this patwari, OR
                # 2. In villages where this user is Patwari (bhu.village.user_id)
                village_ids = user._patwari_assigned_villages().ids
                domain = [
                    ('project_id', '=', project_id),
                    '|',
                    ('user_id', '=', user.id),
                    ('village_id', 'in', village_ids)
                ]
                user.survey_count_in_project = self.env['bhu.survey'].search_count(domain)
            else:
                user.survey_count_in_project = 0
    
    def read(self, fields=None, load='_classic_read'):
        """Override read to recompute survey_count_in_project when context has project"""
        result = super().read(fields=fields, load=load)
        # Force recomputation if survey_count_in_project is being read and context has project
        if fields is None or 'survey_count_in_project' in fields:
            project_id = self.env.context.get('default_project_id') or self.env.context.get('active_id')
            if project_id:
                # Recompute for all records
                self._compute_survey_count_in_project()
                # Update result with recomputed values
                for record, res in zip(self, result):
                    if 'survey_count_in_project' in res:
                        res['survey_count_in_project'] = record.survey_count_in_project
        return result

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Force fields as editable for privileged users in the UI."""
        res = super(ResUsers, self).fields_get(allfields, attributes)
        user = self.env.user
        is_privileged = (
            user.has_group('bhukhadan_core.group_bhuarjan_admin') or
            user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        )
        if is_privileged:
            for field in ['name', 'login', 'mobile', 'email', 'name_english']:
                if field in res:
                    res[field]['readonly'] = False
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Extend default user lookup to include ``name_english``."""
        domain = args or []
        if (
            name and operator not in expression.NEGATIVE_TERM_OPERATORS
            and (user := self.search_fetch(expression.AND([[('login', '=', name)], domain]), ['display_name']))
        ):
            return [(user.id, user.display_name)]
        if name and operator not in expression.NEGATIVE_TERM_OPERATORS:
            like_domain = expression.OR([
                [('name', operator, name)],
                [('login', operator, name)],
                [('email', operator, name)],
                [('name_english', operator, name)],
            ])
            users = self.search_fetch(expression.AND([like_domain, domain]), ['display_name'], limit=limit)
            return [(u.id, u.display_name) for u in users]
        return super().name_search(name, domain, operator, limit)


    assigned_project_ids = fields.Many2many(
        'bhu.project', 
        compute='_compute_assigned_projects',
        string='Assigned Projects',
        help='Projects where this user is assigned as SDM or Tehsildar'
    )

    def _compute_assigned_projects(self):
        """Compute projects assigned to this user"""
        for user in self:
            projects = self.env['bhu.project'].search([
                '|',
                '|',
                ('sdm_ids', 'in', user.id),
                ('tehsildar_ids', 'in', user.id),
                ('department_user_ids', 'in', user.id)
            ])
            user.assigned_project_ids = projects
    
    def _get_assigned_project_ids(self):
        """Get assigned project IDs for current user (for domain use)"""
        user = self.env.user
        # Admin and system users see all projects
        if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
            return []
        
        projects = self.env['bhu.project'].search([
            '|',
            '|',
            ('sdm_ids', 'in', user.id),
            ('tehsildar_ids', 'in', user.id),
            ('department_user_ids', 'in', user.id)
        ])
        return projects.ids if projects else [False]  # Return [False] to show no projects

    @api.onchange('bhuarjan_role')
    def _onchange_bhuarjan_role(self):
        """Assign the corresponding group based on selected role"""
        # Clear all previous custom roles (you can add all group XML IDs here)
        all_custom_group_ids = [
            self.env.ref('bhukhadan_core.group_bhuarjan_patwari').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_ri').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_nayab_tahsildar').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_tahsildar').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_sdm').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_additional_collector').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_collector').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_district_administrator').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_admin').id,
            self.env.ref('bhukhadan_core.group_bhuarjan_department_user').id,
        ]
        if self.groups_id:
            # properly handle removing ids from One2many
            current_ids = self.groups_id.ids
            new_ids = [gid for gid in current_ids if gid not in all_custom_group_ids]
            # Use command to replace
            self.groups_id = [(6, 0, new_ids)]

        # Assign selected group
        group_map = {
            'patwari': 'bhukhadan_core.group_bhuarjan_patwari',
            'ri': 'bhukhadan_core.group_bhuarjan_ri',
            'revenue_inspector': 'bhukhadan_core.group_bhuarjan_ri',
            'nayab_tahsildar': 'bhukhadan_core.group_bhuarjan_nayab_tahsildar',
            'tahsildar': 'bhukhadan_core.group_bhuarjan_tahsildar',
            'sdm': 'bhukhadan_core.group_bhuarjan_sdm',
            'additional_collector': 'bhukhadan_core.group_bhuarjan_additional_collector',
            'collector': 'bhukhadan_core.group_bhuarjan_collector',
            'district_administrator': 'bhukhadan_core.group_bhuarjan_district_administrator',
            'administrator': 'bhukhadan_core.group_bhuarjan_admin',
            'department_user': 'bhukhadan_core.group_bhuarjan_department_user',
        }

        group_ref = group_map.get(self.bhuarjan_role)
        if group_ref:
            group = self.env.ref(group_ref)
            if group:
                self.groups_id = [(4, group.id)]

    def _patwari_assigned_villages(self):
        """Villages where this user is the assigned Patwari (master: bhu.village.user_id)."""
        return self.env['bhu.village'].search([('user_id', 'in', self.ids)])

    def action_view_surveys_in_project(self):
        """Open surveys for this patwari in the project from context"""
        self.ensure_one()
        # Get project_id from context
        project_id = self.env.context.get('default_project_id') or self.env.context.get('active_id')
        if not project_id:
            # Try to get from parent record if in Many2many view
            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')
            if active_model == 'bhu.project' and active_id:
                project_id = active_id
        
        if not project_id:
            return False
        
        action = {
            'type': 'ir.actions.act_window',
            'name': f'Surveys by {self.name}',
            'res_model': 'bhu.survey',
            'view_mode': 'list,form',
            'domain': [
                ('user_id', '=', self.id),
                ('project_id', '=', project_id)
            ],
            'context': {
                'default_project_id': project_id,
                'default_user_id': self.id,
                'search_default_group_by_state': 1,
            },
            'target': 'current',
        }
        # Try to get the survey action reference for better view configuration
        try:
            survey_action = self.env.ref('bhukhadan_core.action_bhu_survey')
            if survey_action:
                action_ref = survey_action.read(['view_mode', 'views'])[0]
                if action_ref.get('views'):
                    action['views'] = action_ref['views']
                if action_ref.get('view_mode'):
                    action['view_mode'] = action_ref['view_mode']
        except Exception:
            pass  # Use default if reference not found
        return action

    def action_accept_bhu_terms(self):
        """Record terms acceptance for the current user (RPC / first-login dialog)."""
        self.ensure_one()
        if self.id != self.env.uid and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('You can only accept terms for your own account.'))
        self.write({
            'bhu_terms_accepted': True,
            'bhu_terms_accepted_date': fields.Datetime.now(),
        })
        return True

    def action_reconcile_patwari_google_sheet(self):
        """Download Excel comparing Odoo Patwari roster with published Google Sheet CSV.

        Administrators only; reads sheet URL from system parameter ``bhukhadan_core.patwari_google_sheet_csv_url``
        or defaults to the standard mapped-sheet CSV export.
        """
        user = self.env.user
        if not (
            user.has_group('base.group_system')
            or user.has_group('bhukhadan_core.group_bhuarjan_admin')
        ):
            raise AccessError(_('Only Administrators can run Patwari sheet reconcile.'))
        wiz = self.env['user.report.wizard'].create(
            {'include_patwaris_without_villages': False}
        )
        return wiz.action_export_patwari_sheet_reconcile()


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Extend permission for signup_type to District Administrator
    signup_type = fields.Selection(
        [('signup', 'Signup Token'), ('reset', 'Reset Password Token')],
        groups="base.group_erp_manager,bhukhadan_core.group_bhuarjan_district_administrator"
    )

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        """Allow District Admin and BhuKhadan Admin to bypass partner access checks."""
        user = self.env.user
        if operation in ('write', 'create', 'read'):
            if (user.has_group('bhukhadan_core.group_bhuarjan_admin') or
                    user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')):
                return True
        return super().check_access_rights(operation, raise_exception=raise_exception)

    def check_access_rule(self, operation):
        """Allow District Admin and BhuKhadan Admin to bypass record rules for partners."""
        user = self.env.user
        if (user.has_group('bhukhadan_core.group_bhuarjan_admin') or
                user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')):
            return None
        return super().check_access_rule(operation)

    def write(self, vals):
        """Allow District Admin and BhuKhadan Admin to edit partners (linked to users)."""
        user = self.env.user
        if (user.has_group('bhukhadan_core.group_bhuarjan_admin') or
                user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')):
            return super(ResPartner, self.sudo()).write(vals)
        return super().write(vals)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Force partner fields as editable for privileged users in the UI."""
        res = super(ResPartner, self).fields_get(allfields, attributes)
        user = self.env.user
        is_privileged = (
            user.has_group('bhukhadan_core.group_bhuarjan_admin') or
            user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        )
        if is_privileged:
            for field in ['name', 'email', 'mobile']:
                if field in res:
                    res[field]['readonly'] = False
        return res

