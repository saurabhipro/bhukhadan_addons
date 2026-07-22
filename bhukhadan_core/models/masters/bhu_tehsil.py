from odoo import models, fields, api, _


class BhuTehsil(models.Model):
    _name = 'bhu.tehsil'
    _description = 'Tehsil'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    name = fields.Char(string='Tehsil Name / तहसील का नाम', required=True)
    code = fields.Char(
        string='Tehsil Code / तहसील कोड',
        tracking=True,
        copy=False,
        index=True,
        help='Short code shown as [CODE] Name (e.g. T1).',
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )

    def _get_state_domain(self):
        state_ids = self.env['bhu.district'].search([]).mapped('state_id.id')
        return [('id', 'in', state_ids)]

    state_id = fields.Many2one('res.country.state', string='State', tracking=True)
    district_id = fields.Many2one('bhu.district', string='District / जिला', tracking=True)
    sub_division_id = fields.Many2one('bhu.sub.division', string='Sub Division / उपभाग', tracking=True)
    village_line_ids = fields.One2many('bhu.village', 'tehsil_id', string='Villages / गांव')
    user_id = fields.Many2one('res.users', string='Tehsildar / तहसीलदार', tracking=True)

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

    _sql_constraints = [
        ('tehsil_code_unique', 'UNIQUE(code)', 'Tehsil Code must be unique!'),
    ]
