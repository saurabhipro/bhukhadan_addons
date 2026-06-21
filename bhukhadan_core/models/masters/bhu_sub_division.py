from odoo import models, fields, api, _
import json

class BhuSubDivision(models.Model):
    _name = 'bhu.sub.division'
    _description = 'Sub Division'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Sub Division', required=True, tracking=True)
    district_id = fields.Many2one('bhu.district', string='District', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='SDM', tracking=True)
    
    def _get_state_domain(self):
        state_ids = self.env['bhu.district'].search([]).mapped('state_id.id')    
        return [('id', 'in', state_ids)]

    state_id = fields.Many2one('res.country.state', string='State', required=True, tracking=True)

