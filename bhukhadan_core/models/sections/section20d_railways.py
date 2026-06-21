# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
import json


class Section20DRailways(models.Model):
    _name = 'bhu.section20d.railways'
    _description = 'Section 20 D (Objection) (Railways) / धारा 20 डी (आपत्ति) (रेलवे)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference / संदर्भ', required=True, tracking=True, default='New', readonly=True)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', required=True, tracking=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', tracking=True)
    
    # Single survey (khasra) selection
    survey_id = fields.Many2one('bhu.survey', string='Survey (Khasra) / सर्वे (खसरा)', tracking=True,
                                help='Select a khasra from the selected village.')
    
    # Available surveys for selection (computed based on village)
    available_survey_ids = fields.Many2many('bhu.survey', string='Available Surveys', compute='_compute_available_survey_ids', store=False)

    # Resolution Changes
    resolution_landowner_ids = fields.Many2many('bhu.landowner', 
                                                'section20d_railways_landowner_rel',
                                                'objection_id', 'landowner_id',
                                                string='Landowners (After Resolution) / भूमिस्वामी (समाधान के बाद)', 
                                                tracking=True)
    
    original_landowner_ids = fields.Many2many('bhu.landowner', 
                                             'section20d_railways_original_landowner_rel',
                                             'objection_id', 'landowner_id',
                                             string='Original Landowners / मूल भूमिस्वामी', 
                                             compute='_compute_original_landowner_ids', 
                                             store=True, readonly=True)

    resolution_khasra_ids = fields.One2many('bhu.section20d.railways.khasra', 'section20d_id',
                                            string='Khasra Resolution Changes / खसरा समाधान परिवर्तन',
                                            tracking=True)
    
    # Section 20 D (Objection) specific fields
    objection_date = fields.Date(string='Objection Date / आपत्ति दिनांक', tracking=True, default=fields.Date.today)
    objection_number = fields.Char(string='Objection Number / आपत्ति संख्या', tracking=True)
    objection_details = fields.Text(string='Objection Details / आपत्ति विवरण', tracking=True)
    
    # Objection resolution
    resolution_date = fields.Date(string='Resolution Date / समाधान दिनांक', tracking=True)
    resolution_details = fields.Text(string='Resolution Details / समाधान विवरण', tracking=True)
    objection_resolution_comments = fields.Text(string='Objection and Resolution Comments / आपत्ति एवं निराकरण कमेंट बॉक्स', tracking=True)
    
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
    
    # Age in days
    age_days = fields.Integer(string='Age (Days) / आयु (दिन)', compute='_compute_age_days', store=False)

    village_domain = fields.Char()
    project_domain = fields.Char()
    
    @api.depends('objection_date')
    def _compute_age_days(self):
        """Compute age of objection in days"""
        today = date.today()
        for record in self:
            if record.objection_date:
                delta = today - record.objection_date
                record.age_days = delta.days
            else:
                record.age_days = 0

    @api.depends('village_id')
    def _compute_available_survey_ids(self):
        """Compute available survey IDs based on village"""
        for record in self:
            if record.village_id:
                surveys = self.env['bhu.survey'].search([
                    ('village_id', '=', record.village_id.id),
                    ('state', 'in', ['draft', 'submitted', 'approved'])
                ], order='khasra_number desc')
                record.available_survey_ids = surveys
            else:
                record.available_survey_ids = False
    
    @api.depends('survey_id')
    def _compute_original_landowner_ids(self):
        """Compute original landowners from selected survey"""
        for record in self:
            if record.survey_id:
                record.original_landowner_ids = record.survey_id.landowner_ids
            else:
                record.original_landowner_ids = False

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
    
    @api.onchange('village_id')
    def _onchange_village_id(self):
        """Reset survey when village changes"""
        self.survey_id = False
        self.resolution_landowner_ids = False
        self.resolution_khasra_ids = False
        self._compute_available_survey_ids()

    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        """Initialize resolution data when survey changes"""
        if not self.survey_id:
            self.resolution_landowner_ids = False
            self.resolution_khasra_ids = [(5, 0, 0)]
            return
        
        # Initialize landowners
        all_landowners = self.survey_id.landowner_ids
        self.original_landowner_ids = all_landowners
        if not self.resolution_landowner_ids and all_landowners:
            self.resolution_landowner_ids = all_landowners
        
        # Initialize khasra resolution
        if not self.resolution_khasra_ids:
             self.resolution_khasra_ids = [(0, 0, {
                    'survey_id': self.survey_id.id,
                    'original_acquired_area': self.survey_id.acquired_area,
                    'resolved_acquired_area': self.survey_id.acquired_area,
                })]
        else:
            # Update existing line if present
            existing = self.resolution_khasra_ids[0]
            existing.survey_id = self.survey_id.id
            existing.original_acquired_area = self.survey_id.acquired_area
            # Check logic to not overwrite resolved if already set validly? 
            # For simplicity, reset if switching survey
            existing.resolved_acquired_area = self.survey_id.acquired_area

    @api.constrains('resolution_landowner_ids')
    def _check_resolution_landowners(self):
        """Ensure at least one landowner remains"""
        for record in self:
            if record.survey_id and not record.resolution_landowner_ids:
                 raise ValidationError(_('At least one landowner must remain.'))

    @api.model_create_multi
    def create(self, vals_list):
        """Generate reference if not provided"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                project_id = vals.get('project_id')
                if project_id:
                    project = self.env['bhu.project'].browse(project_id)
                    sequence_code = 'bhu.section20d.railways'
                    if project:
                        sequence_code = f'bhu.section20d.railways.{project.id}'
                    vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
        return super().create(vals_list)

    def write(self, vals):
        """Update survey when objection is saved"""
        result = super().write(vals)
        
        # Similar to Section 15, update the original survey if resolution changes
        if 'resolution_landowner_ids' in vals:
            for record in self:
                if record.survey_id and record.resolution_landowner_ids:
                    record.survey_id.write({
                        'landowner_ids': [(6, 0, record.resolution_landowner_ids.ids)]
                    })
        
        return result

    def action_open_reject_wizard(self):
        """Open the reject survey wizard"""
        self.ensure_one()
        if not self.survey_id:
            raise ValidationError(_('Please select a survey (khasra) first.'))
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Survey / सर्वे अस्वीकार करें'),
            'res_model': 'bhu.reject.railways.survey.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_section20d_id': self.id,
                'default_survey_id': self.survey_id.id,
            }
        }


class Section20DRailwaysKhasra(models.Model):
    """Model to track resolution changes per khasra for Railways"""
    _name = 'bhu.section20d.railways.khasra'
    _description = 'Section 20D Railways Khasra Resolution'
    
    section20d_id = fields.Many2one('bhu.section20d.railways', string='Section 20D Record', required=True, ondelete='cascade')
    survey_id = fields.Many2one('bhu.survey', string='Survey (Khasra) / सर्वे (खसरा)', required=True, ondelete='restrict')
    khasra_number = fields.Char(string='Khasra Number / खसरा नंबर', related='survey_id.khasra_number', readonly=True, store=True)
    
    original_acquired_area = fields.Float(string='Original Acquired Area (Hectares) / मूल अर्जन क्षेत्रफल (हेक्टेयर)', 
                                          digits=(10, 4), required=True, readonly=True)
    resolved_acquired_area = fields.Float(string='Resolved Acquired Area (Hectares) / समाधान अर्जन क्षेत्रफल (हेक्टेयर)', 
                                         digits=(10, 4), required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'default_section20d_id' in self.env.context:
             section20d_id = self.env.context.get('default_section20d_id')
             if section20d_id:
                  res['section20d_id'] = section20d_id
        return res

    def unlink(self):
        """Reject survey if line deleted"""
        for record in self:
            if record.survey_id:
                record.survey_id.write({'state': 'rejected'})
        return super().unlink()
    
    def write(self, vals):
        """Update survey area if resolved area changed"""
        result = super().write(vals)
        for record in self:
            if record.survey_id and record.resolved_acquired_area:
                 if record.resolved_acquired_area <= record.original_acquired_area:
                      record.survey_id.write({'acquired_area': record.resolved_acquired_area})
        return result

    def action_open_reject_wizard(self):
        """Open the reject survey wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Survey / सर्वे अस्वीकार करें'),
            'res_model': 'bhu.reject.railways.survey.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_section20d_id': self.section20d_id.id,
                'default_survey_id': self.survey_id.id,
            }
        }
