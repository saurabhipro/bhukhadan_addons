import datetime
from odoo import models, fields

class MobileOTP(models.Model):
    _name = 'mobile.otp'
    _description = 'Mobile OTP'

    mobile = fields.Char(string='Mobile Number', required=True)
    otp = fields.Char(string='OTP', required=True)
    user_id = fields.Many2one('res.users', string='User')
    expire_date = fields.Datetime(string='Expire Date', required=True)
