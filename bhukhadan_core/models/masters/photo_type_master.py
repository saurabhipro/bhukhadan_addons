# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PhotoTypeMaster(models.Model):
    _name = 'bhu.photo.type'
    _description = 'Photo Type Master / फोटो प्रकार मास्टर'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Photo Type Name / फोटो प्रकार का नाम', required=True, tracking=True,
                      help='Name of the photo type (e.g., Land, Well, House, Shed)')
    code = fields.Char(string='Photo Type Code / फोटो प्रकार कोड', tracking=True,
                      help='Unique code for the photo type')
    description = fields.Text(string='Description / विवरण', tracking=True)
    sequence = fields.Integer(string='Sequence / क्रम', default=10, tracking=True,
                             help='Display order')
    active = fields.Boolean(string='Active / सक्रिय', default=True, tracking=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Photo type name must be unique! / फोटो प्रकार का नाम अद्वितीय होना चाहिए!')
    ]

