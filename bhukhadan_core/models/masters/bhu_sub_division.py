from odoo import models, fields, api, _


class BhuSubDivision(models.Model):
    _name = 'bhu.sub.division'
    _description = 'Sub Division'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    name = fields.Char(string='Sub Division', required=True, tracking=True)
    code = fields.Char(
        string='Sub Division Code / उपभाग कोड',
        tracking=True,
        copy=False,
        index=True,
        help='Short code shown as [CODE] Name (e.g. SD1).',
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    district_id = fields.Many2one('bhu.district', string='District', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='SDM', tracking=True)

    def _get_state_domain(self):
        state_ids = self.env['bhu.district'].search([]).mapped('state_id.id')
        return [('id', 'in', state_ids)]

    state_id = fields.Many2one('res.country.state', string='State', required=True, tracking=True)

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
        ('sub_division_code_unique', 'UNIQUE(code)', 'Sub Division Code must be unique!'),
    ]
