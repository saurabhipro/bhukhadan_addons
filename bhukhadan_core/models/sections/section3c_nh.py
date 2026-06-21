# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class Section3CNH(models.Model):
    _name = 'bhu.section3c.nh'
    _description = 'Section 3C (Objection) (NH) / धारा 3सी (आपत्ति) (राष्ट्रीय राजमार्ग)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference / संदर्भ', required=True, tracking=True, default='New', readonly=True)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', required=True, tracking=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', tracking=True)
    
    # Section 3C (Objection) specific fields
    objection_date = fields.Date(string='Objection Date / आपत्ति दिनांक', tracking=True)
    objection_number = fields.Char(string='Objection Number / आपत्ति संख्या', tracking=True)
    objection_details = fields.Text(string='Objection Details / आपत्ति विवरण', tracking=True)
    
    # Objection resolution
    resolution_date = fields.Date(string='Resolution Date / समाधान दिनांक', tracking=True)
    resolution_details = fields.Text(string='Resolution Details / समाधान विवरण', tracking=True)
    
    # File uploads
    objection_file = fields.Binary(string='Objection File / आपत्ति फ़ाइल', tracking=True)
    objection_filename = fields.Char(string='Objection Filename', tracking=True)
    resolution_file = fields.Binary(string='Resolution File / समाधान फ़ाइल', tracking=True)
    resolution_filename = fields.Char(string='Resolution Filename', tracking=True)
    
    # SDM signed file
    sdm_signed_file = fields.Binary(string='SDM Signed File / एसडीएम हस्ताक्षरित फ़ाइल', tracking=True)
    sdm_signed_filename = fields.Char(string='SDM Signed Filename', tracking=True)
    
    # Collector signed file
    collector_signed_file = fields.Binary(string='Collector Signed File / कलेक्टर हस्ताक्षरित फ़ाइल', tracking=True)
    collector_signed_filename = fields.Char(string='Collector Signed Filename', tracking=True)
    
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
                    sequence_code = 'bhu.section3c.nh'
                    if project:
                        sequence_code = f'bhu.section3c.nh.{project.id}'
                    vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
        return super().create(vals_list)

