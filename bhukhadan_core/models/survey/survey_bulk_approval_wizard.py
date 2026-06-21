# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SurveyBulkApprovalWizard(models.TransientModel):
    _name = 'bhu.survey.bulk.approval.wizard'
    _description = 'Survey Bulk Approval Wizard'

    project_id = fields.Many2one('bhu.project', string='Project ID', required=True)
    village_id = fields.Many2one('bhu.village', string='Village ID')
    project_name = fields.Char(string='Project / परियोजना', readonly=True)
    village_name = fields.Char(string='Village / ग्राम', readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        """Override to set default project and village from context or user preferences"""
        res = super(SurveyBulkApprovalWizard, self).default_get(fields_list)
        
        # Try to get from context first
        project_id = self.env.context.get('default_project_id') or self.env.context.get('active_project_id')
        village_id = self.env.context.get('default_village_id') or self.env.context.get('active_village_id')
        
        # If not in context, try to get from selected records in the list view
        if not project_id or not village_id:
            active_ids = self.env.context.get('active_ids', [])
            if active_ids:
                survey = self.env['bhu.survey'].browse(active_ids[0])
                if not project_id and survey.project_id:
                    project_id = survey.project_id.id
                if not village_id and survey.village_id:
                    village_id = survey.village_id.id
        
        # If still not found, try to get from saved dashboard selection
        if not project_id or not village_id:
            saved_selection = self.env['bhuarjan.dashboard'].get_dashboard_selection()
            if not project_id and saved_selection.get('project_id'):
                project_id = saved_selection['project_id']
            if not village_id and saved_selection.get('village_id'):
                village_id = saved_selection['village_id']
        
        # Final fallback - first project where user is assigned as department user
        if not project_id:
            user = self.env.user
            projects = self.env['bhu.project'].search([
                ('department_user_ids', 'in', user.id),
            ], limit=1)
            if projects:
                project_id = projects[0].id
        
        if project_id:
            # Fetch project to get display name
            project = self.env['bhu.project'].browse(project_id)
            if project.exists():
                res['project_id'] = project_id
                res['project_name'] = project.name
        
        if village_id:
            # Fetch village to get display name
            village = self.env['bhu.village'].browse(village_id)
            if village.exists():
                res['village_id'] = village_id
                res['village_name'] = village.name
            
        return res
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain"""
        self.village_id = False
        if self.project_id and self.project_id.village_ids:
            return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        return {'domain': {'village_id': []}}

    def action_approve_surveys(self):
        """Approve surveys based on selected project and villages"""
        self.ensure_one()
        
        # Build domain for surveys to approve
        domain = [
            ('project_id', '=', self.project_id.id),
            ('state', 'in', ['draft', 'submitted'])  # Allow approving draft or submitted surveys
        ]
        
        # Filter by village if selected
        if self.village_id:
            domain.append(('village_id', '=', self.village_id.id))
        
        # Find surveys matching criteria
        surveys = self.env['bhu.survey'].search(domain)
        
        if not surveys:
            # Provide helpful error message
            if self.village_id:
                raise ValidationError(_('No draft or submitted surveys found for project "%s" and village: %s.\n\nPlease check:\n- Survey state (should be Draft or Submitted)\n- Project and Village selection') % (self.project_id.name, self.village_id.name))
            else:
                raise ValidationError(_('No draft or submitted surveys found for project "%s".\n\nPlease check:\n- Survey state (should be Draft or Submitted)\n- Project selection') % self.project_id.name)
        
        # Approve surveys using the existing approve method
        approved_count = 0
        for survey in surveys:
            try:
                if survey.state in ['draft', 'submitted']:
                    survey.action_approve()  # Use the existing approve method
                    survey.message_post(
                        body=_('Bulk approved by %s') % (self.env.user.name),
                        message_type='notification'
                    )
                    approved_count += 1
            except Exception as e:
                # Log error but continue with other surveys
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("Error approving survey %s: %s", survey.name, e)
        
        if approved_count == 0:
            raise ValidationError(_('No surveys could be approved. Please check survey states and permissions.'))
        
        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d survey(s) approved successfully for project %s.') % (approved_count, self.project_id.name),
                'type': 'success',
                'sticky': False,
            }
        }

