# -*- coding: utf-8 -*-

from odoo import models, fields


class AreaMaster(models.Model):
    _name = 'bhukhadan.area.master'
    _description = 'Area Master / क्षेत्र मास्टर'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Area Name / क्षेत्र का नाम', required=True, tracking=True)
    active = fields.Boolean(string='Active / सक्रिय', default=True, tracking=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Area name must be unique! / क्षेत्र का नाम अद्वितीय होना चाहिए!'),
    ]
