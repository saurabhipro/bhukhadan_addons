from odoo import models, fields, api, _

class BhuTehsil(models.Model):
    _name = 'bhu.tehsil'
    _description = 'Tehsil'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Tehsil Name / तहसील का नाम', required=True)

    def _get_state_domain(self):
        state_ids = self.env['bhu.district'].search([]).mapped('state_id.id')    
        return [('id', 'in', state_ids)]
            
    state_id = fields.Many2one('res.country.state', string='State', tracking=True)
    district_id = fields.Many2one('bhu.district', string='District / जिला', tracking=True)
    sub_division_id = fields.Many2one('bhu.sub.division', string='Sub Division / उपभाग', tracking=True)
    village_line_ids = fields.One2many('bhu.village', 'tehsil_id', string='Villages / गांव')
    user_id = fields.Many2one('res.users', string='Tehsildar / तहसीलदार', tracking=True)