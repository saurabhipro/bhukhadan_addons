# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class Section3ANH(models.Model):
    _name = 'bhu.section3a.nh'
    _description = 'Section 3A (NH) / धारा 3ए (राष्ट्रीय राजमार्ग)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference / संदर्भ', required=True, tracking=True, default='New', readonly=True)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', required=True, tracking=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', tracking=True)
    
    # SDM signed file
    sdm_signed_file = fields.Binary(string='SDM Signed File / एसडीएम हस्ताक्षरित फ़ाइल', tracking=True)
    sdm_signed_filename = fields.Char(string='SDM Signed Filename', tracking=True)
    
    # Notes
    notes = fields.Text(string='Notes / नोट्स', tracking=True)
    
    village_domain = fields.Char()
    project_domain = fields.Char()
    
    @api.onchange('department_id')
    def _onchange_department_id(self):
        """Filter projects based on selected department"""
        for rec in self:
            if rec.department_id:
                project_ids_from_department_id = self.env['bhu.project'].search([
                    ('department_id', '=', rec.department_id.id)
                ]).ids
                project_ids_from_m2m = rec.department_id.project_ids.ids
                all_project_ids = list(set(project_ids_from_department_id + project_ids_from_m2m))
                if all_project_ids:
                    rec.project_domain = json.dumps([('id', 'in', all_project_ids)])
                else:
                    rec.project_domain = json.dumps([('id', 'in', [])])
                rec.project_id = False
            else:
                rec.project_domain = json.dumps([('id', 'in', [])])
                rec.project_id = False
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain"""
        for rec in self:
            if rec.project_id and rec.project_id.village_ids:
                rec.village_domain = json.dumps([('id', 'in', rec.project_id.village_ids.ids)])
            else:
                rec.village_domain = json.dumps([('id', 'in', [])])
                rec.village_id = False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate reference if not provided"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                project_id = vals.get('project_id')
                if project_id:
                    project = self.env['bhu.project'].browse(project_id)
                    sequence_code = 'bhu.section3a.nh'
                    if project:
                        sequence_code = f'bhu.section3a.nh.{project.id}'
                    vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
        return super().create(vals_list)

