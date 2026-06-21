# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class Section18RRScheme(models.Model):
    _name = 'bhu.section18.rr.scheme'
    _description = 'Section 18 R and R Scheme'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    @api.constrains('project_id')
    def _check_unique_project(self):
        for rec in self:
            if not rec.project_id:
                continue
            duplicate = self.search([
                ('project_id', '=', rec.project_id.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    'Only one R and R Scheme can be created per project! / '
                    'प्रति परियोजना केवल एक R और R योजना बनाई जा सकती है!'
                )

    name = fields.Char(string='Scheme Name / योजना का नाम', compute='_compute_name', store=True, readonly=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    
    # Scheme file upload
    scheme_file = fields.Binary(string='R and R Scheme File / पुनर्वास और पुनर्स्थापना योजना फ़ाइल', required=True, tracking=True)
    scheme_filename = fields.Char(string='Scheme Filename / योजना फ़ाइल नाम', tracking=True)
    
    # Notes
    notes = fields.Text(string='Notes / नोट्स', tracking=True)
    
    # No state field - free from validation as per requirements
    
    @api.depends('project_id')
    def _compute_name(self):
        """Compute scheme name from project"""
        for rec in self:
            if rec.project_id:
                rec.name = f'R and R Scheme - {rec.project_id.name}'
            else:
                rec.name = 'New'
    
    @api.model
    def default_get(self, fields_list):
        """Override default_get to find existing scheme for project or create new"""
        res = super().default_get(fields_list)
        
        # Get project_id from context
        project_id = self.env.context.get('default_project_id') or self.env.context.get('active_id')
        if self.env.context.get('active_model') == 'bhu.project':
            project_id = self.env.context.get('active_id')
        
        # If project_id is in context and we're creating a new record, find existing scheme
        if project_id and 'project_id' in fields_list:
            existing_scheme = self.search([('project_id', '=', project_id)], limit=1)
            if existing_scheme:
                # Return existing record's ID to open it instead of creating new
                # This is handled by the action_open_rr_scheme_form method
                pass
            else:
                # Set project_id in defaults for new record
                res['project_id'] = project_id
        
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create R and R Scheme - name is computed from project"""
        records = super().create(vals_list)
        # Trigger name computation
        for record in records:
            record._compute_name()
        return records
    
    def action_download_scheme(self):
        """Download scheme file"""
        self.ensure_one()
        if not self.scheme_file:
            raise ValidationError(_('No scheme file available to download.'))
        filename = self.scheme_filename or f'rr_scheme_{self.project_id.name or "scheme"}.pdf'
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/scheme_file/{filename}?download=true',
            'target': 'self',
        }
    
    @api.model
    def action_open_rr_scheme_form(self, project_id=None):
        """Open R and R Scheme form directly - find existing or create new for project"""
        # Get project_id from context if not provided
        if not project_id:
            project_id = self.env.context.get('default_project_id') or self.env.context.get('active_id')
            # Try to get from active_model if it's a project
            if self.env.context.get('active_model') == 'bhu.project':
                project_id = self.env.context.get('active_id')
        
        if not project_id:
            # No project selected, open list view
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 18 R and R Scheme',
                'res_model': 'bhu.section18.rr.scheme',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
        
        # Find existing R and R Scheme for this project
        existing_scheme = self.search([('project_id', '=', project_id)], limit=1)
        
        if existing_scheme:
            # Open existing scheme in form view
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 18 R and R Scheme',
                'res_model': 'bhu.section18.rr.scheme',
                'res_id': existing_scheme.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'context': {
                    'default_project_id': project_id,
                }
            }
        else:
            # Create new scheme for this project
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 18 R and R Scheme',
                'res_model': 'bhu.section18.rr.scheme',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'context': {
                    'default_project_id': project_id,
                }
        }

