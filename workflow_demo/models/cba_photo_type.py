# -*- coding: utf-8 -*-

from odoo import models, fields


class CbaPhotoType(models.Model):
    _name = 'cba.photo.type'
    _description = 'CBA Photo Type'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
