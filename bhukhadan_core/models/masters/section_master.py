# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SectionMaster(models.Model):
    _name = 'bhu.section.master'
    _description = 'Section Master / धारा मास्टर'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Section Name / धारा नाम', required=True, tracking=True,
                      help='Name of the section (e.g., Section 4, Section 8, Section 11)')
    
    description = fields.Text(string='Description / विवरण', tracking=True,
                             help='Detailed description of the section')
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    
    # Many2many relationship - laws using this section
    law_ids = fields.Many2many('bhu.law.master', 'bhu_law_section_rel', 
                               'section_id', 'law_id',
                               string='Laws / कानून',
                               help='Laws that include this section')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Section name must be unique!')
    ]

