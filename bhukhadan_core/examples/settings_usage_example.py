# Example Usage of Settings Master in Other Models

# In your survey model or any other process model:

from odoo import models, fields, api

class Survey(models.Model):
    _name = 'bhuarjan.survey'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Survey Number', required=True, copy=False, readonly=True, default='New')
    project_id = fields.Many2one('bhu.project', string='Project', required=True)
    
    # Workflow fields
    maker_user_ids = fields.Many2many('res.users', string='Makers', readonly=True)
    checker_user_id = fields.Many2one('res.users', string='Checker', readonly=True)
    approver_user_id = fields.Many2one('res.users', string='Approver', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('check', 'Under Check'),
        ('approve', 'Under Approval'),
        ('done', 'Approved'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    @api.model
    def create(self, vals):
        """Override create to set sequence number and workflow users"""
        if vals.get('name', 'New') == 'New':
            # Get sequence number from settings
            sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                'survey', vals.get('project_id')
            )
            vals['name'] = sequence_number
            
            # Get workflow users from settings
            workflow_users = self.env['bhuarjan.settings.master'].get_workflow_users(
                'survey', vals.get('project_id')
            )
            
            if workflow_users:
                vals.update({
                    'maker_user_ids': [(6, 0, workflow_users['makers'].ids)] if workflow_users['makers'] else False,
                    'checker_user_id': workflow_users['checker'].id if workflow_users['checker'] else False,
                    'approver_user_id': workflow_users['approver'].id if workflow_users['approver'] else False,
                })
        
        return super().create(vals)
    
    def action_submit_for_check(self):
        """Submit for checking"""
        workflow_users = self.env['bhuarjan.settings.master'].get_workflow_users(
            'survey', self.project_id.id
        )
        
        if workflow_users and workflow_users['require_checker'] and workflow_users['checker']:
            self.state = 'check'
            # Send notification to checker
            if workflow_users['notify_checker']:
                self._send_notification(workflow_users['checker'], 'check')
        else:
            self.state = 'approve'
    
    def action_check_approve(self):
        """Checker approves"""
        workflow_users = self.env['bhuarjan.settings.master'].get_workflow_users(
            'survey', self.project_id.id
        )
        
        if workflow_users and workflow_users['require_approver'] and workflow_users['approver']:
            self.state = 'approve'
            # Send notification to approver
            if workflow_users['notify_approver']:
                self._send_notification(workflow_users['approver'], 'approve')
        else:
            self.state = 'done'
    
    def action_final_approve(self):
        """Final approval"""
        self.state = 'done'
    
    def _send_notification(self, user, action_type):
        """Send notification to user"""
        # Implementation for sending notifications
        pass

# Usage in other models:
# 
# 1. Get sequence number:
#    sequence = self.env['bhuarjan.settings.master'].get_sequence_number('survey', project_id)
#
# 2. Get workflow users:
#    workflow = self.env['bhuarjan.settings.master'].get_workflow_users('survey', project_id)
#    makers = workflow['makers']  # List of all makers
#    maker = workflow['maker']   # First maker (for backward compatibility)
#    checker = workflow['checker'] 
#    approver = workflow['approver']
