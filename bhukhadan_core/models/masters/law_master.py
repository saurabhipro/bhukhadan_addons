# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LawMaster(models.Model):
    _name = 'bhu.law.master'
    _description = 'Law Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Law Name', required=True, tracking=True,
                      help='Name of the law (e.g., Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act, 2013)')
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    
    # Many2many relationship - sections in this law
    section_ids = fields.Many2many('bhu.section.master', 'bhu_law_section_rel', 
                                   'law_id', 'section_id',
                                   string='Sections / धाराएं',
                                   help='Sections included in this law')
    
    # One2many relationship - projects using this law
    project_ids = fields.One2many('bhu.project', 'law_master_id', 
                                  string='Projects',
                                  help='Projects using this law')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Law name must be unique!')
    ]

