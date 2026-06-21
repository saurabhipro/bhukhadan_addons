from odoo import models, fields
import datetime

class JWTToken(models.Model):
    _name = 'jwt.token'
    _description = 'JWT Token'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='User', required=True)
    token = fields.Char(string='Token', required=True)
    channel_type = fields.Selection(
        [('mobile', 'Mobile'), ('web', 'Web / Portal')],
        string='Channel',
        default='mobile',
        index=True,
        help='Where this JWT was issued. Dashboard “mobile users” counts mobile and legacy tokens (unset).',
    )

    create_date = fields.Datetime(string='Created On', readonly=True)
