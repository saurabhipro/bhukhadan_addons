# -*- coding: utf-8 -*-

from odoo import models, fields


class CbaProject(models.Model):
    _name = 'cba.project'
    _description = 'CBA Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Project Name', required=True, tracking=True)
    code = fields.Char(string='Project Code', tracking=True)
    district_id = fields.Many2one('cba.district', string='District', tracking=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
