from odoo import models, fields, api, _
import json

class BhuVillageLine(models.Model):
    _name = 'bhu.village.line'
    _description = 'Village Line'

    district_id = fields.Many2one('bhu.district', string="District")
    village_id = fields.Many2one('bhu.village', string="Village", required=True)
    village_domain = fields.Char(string="Vi Domain", compute="_compute_vi_domain")

    @api.depends('village_id', 'district_id')
    def _compute_display_name(self):
        for record in self:
            if record.village_id and record.district_id:
                record.display_name = _("%s (%s)") % (record.village_id.name or '', record.district_id.name or '')
            elif record.village_id:
                record.display_name = record.village_id.name or ''
            else:
                record.display_name = ''

    @api.onchange('village_id')
    def _onchange_village_id(self):
        """Automatically set district when village is selected"""
        if self.village_id and self.village_id.district_id:
            self.district_id = self.village_id.district_id

    @api.depends('district_id')
    def _compute_vi_domain(self):
        for rec in self:
            if rec.district_id:
                valid_village_ids = rec.district_id.village_line_ids.mapped('district_id').ids
                rec.village_domain = json.dumps([('id', 'in', valid_village_ids)])
            else:
                rec.village_domain = json.dumps([])


class BhuVillage(models.Model):
    _name = 'bhu.village'
    _description = 'Village'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Village Name / ग्राम का नाम', required=True, tracking=True)
    district_id = fields.Many2one('bhu.district', string='District / जिला', required=True, tracking=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील', required=True, tracking=True)
    pincode = fields.Char(string='Pincode / पिनकोड', tracking=True)
    population = fields.Integer(string='Population / जनसंख्या', tracking=True)
    area_hectares = fields.Float(string='Area (Hectares) / क्षेत्रफल (हेक्टेयर)', digits=(10, 4), tracking=True)
    is_tribal_area = fields.Boolean(string='Tribal Area / आदिवासी क्षेत्र', tracking=True)
    is_forest_area = fields.Boolean(string='Forest Area / वन क्षेत्र', tracking=True)



class BhuDepartment(models.Model):
    _name = 'bhu.department'
    _description = 'Department'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    name = fields.Char(string='Department Name', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    department_logo = fields.Image(
        string='Department Logo',
        max_width=512,
        max_height=512,
    )
    icon = fields.Char(string='Icon Class', help='Bootstrap icon class (e.g. fa-building)', tracking=True)
    district_id = fields.Many2one('bhu.district', string='District', tracking=True,
                                  default=lambda self: self._get_default_district(),
                                  help='District for this department')
    is_district_readonly = fields.Boolean(compute='_compute_is_district_readonly', store=False)
    code = fields.Char(
        string='Department Code / विभाग कोड',
        tracking=True,
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    description = fields.Text(string='Description', tracking=True)
    head_of_department = fields.Char(string='Head of Department', tracking=True)
    contact_number = fields.Char(string='Contact Number', tracking=True)
    email = fields.Char(string='Email', tracking=True)
    address = fields.Text(string='Address', tracking=True)
    project_ids = fields.Many2many('bhu.project', string='Projects', tracking=True,
                                   help='Select multiple projects associated with this department')
    fk_project_ids = fields.One2many(
        'bhu.project',
        'department_id',
        string='Projects (department field)',
        readonly=True,
        help='Projects whose Department / विभाग field points to this record.',
    )
    project_count = fields.Integer(
        string='Project count',
        compute='_compute_project_count',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Department User',
        domain="[('bhuarjan_role', 'in', ['staff_officer_pp', 'staff_officer_hr', 'staff_officer_civil'])]",
        tracking=True,
    )

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            label = (rec.name or '').strip()
            code = (rec.code or '').strip()
            if code and label:
                rec.display_name = f'[{code}] {label}'
            elif label:
                rec.display_name = label
            elif code:
                rec.display_name = f'[{code}]'
            else:
                rec.display_name = f'{rec._name},{rec.id}'

    @api.depends_context('uid')
    def _compute_is_district_readonly(self):
        """Compute if district field should be readonly (for non-admin users)"""
        user = self.env.user
        is_admin = user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system')
        for record in self:
            record.is_district_readonly = not is_admin

    @api.model
    def _get_default_district(self):
        """Get default district based on logged-in user (for non-administrators)"""
        user = self.env.user
        # Administrators can select any district, so no default
        if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
            return False
        # For other users, default to their district
        return user.district_id.id if user.district_id else False

    @api.model
    def default_get(self, fields_list):
        """Override to set district automatically for non-admin users"""
        res = super(BhuDepartment, self).default_get(fields_list)
        user = self.env.user
        # For non-admin users, force district to their district
        if not (user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system')):
            if user.district_id:
                res['district_id'] = user.district_id.id
        return res

    @api.depends('project_ids', 'fk_project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids | rec.fk_project_ids)

    def action_view_projects(self):
        """Open bhu.project linked by M2M and/or by project.department_id."""
        self.ensure_one()
        domain = ['|', ('department_id', '=', self.id), ('id', 'in', self.project_ids.ids)]
        action = {
            'name': _('Projects / परियोजनाएं'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhu.project',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_department_id': self.id, 'skip_project_domain_filter': True},
            'target': 'current',
        }
        try:
            project_action = self.env.ref('bhukhadan_core.action_bhu_project')
            if project_action:
                action_ref = project_action.read(['view_mode', 'views', 'search_view_id'])[0]
                if action_ref.get('views'):
                    action['views'] = action_ref['views']
                if action_ref.get('view_mode'):
                    action['view_mode'] = action_ref['view_mode']
                if action_ref.get('search_view_id'):
                    sv = action_ref['search_view_id']
                    action['search_view_id'] = sv[0] if isinstance(sv, (list, tuple)) else sv
        except Exception:
            pass
        return action

