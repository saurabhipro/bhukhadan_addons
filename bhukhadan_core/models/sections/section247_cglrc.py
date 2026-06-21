# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class Section247_1CGLRC(models.Model):
    _name = 'bhu.section247_1.cglrc'
    _description = 'Personal Notice generation (247.1) / व्यक्तिगत सूचना जनरेशन (247.1)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference / संदर्भ', required=True, tracking=True, default='New', readonly=True)

    # Simplified state for CGLRC 247: no submitted/send_back
    state = fields.Selection(selection_add=[
        ('draft', 'Draft'),
        ('approved', 'Approved'),
    ], ondelete={'draft': 'set default', 'approved': 'set default'})

    def action_approve(self):
        """Approve (SDM action for 247) - Direct from Draft"""
        self.ensure_one()
        # Check if user is SDM or Admin
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM or Admin can approve.'))
        
        # Validate state is draft (since we removed submitted)
        if self.state != 'draft':
            raise ValidationError(_('Only draft records can be approved.'))
        
        self.state = 'approved'
        self.approved_date = fields.Datetime.now()
        self.message_post(body=_('Approved by SDM %s') % self.env.user.name, subtype_xmlid='mail.mt_note')

    # Disable generic actions from mixin
    def action_submit(self):
        raise ValidationError(_('Submit is not required for CGLRC 247 sections. SDM can approve directly.'))

    def action_send_back(self):
        raise ValidationError(_('Send back is not applicable for CGLRC 247 sections.'))

    def _validate_state_transition(self, old_state, new_state):
        """Validate simplified state transitions"""
        valid_transitions = {
            'draft': ['approved'],
            'approved': ['draft'],
        }
        if new_state not in valid_transitions.get(old_state, []):
            raise ValidationError(_('Invalid status transition for CGLRC 247.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section247_1.cglrc') or 'New'
        return super().create(vals_list)

class Section247_2CGLRC(models.Model):
    _name = 'bhu.section247_2.cglrc'
    _description = 'Istehar प्रकाशन (247.2) / इश्तेहार प्रकाशन (247.2)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference / संदर्भ', required=True, tracking=True, default='New', readonly=True)

    state = fields.Selection(selection_add=[
        ('draft', 'Draft'),
        ('approved', 'Approved'),
    ], ondelete={'draft': 'set default', 'approved': 'set default'})

    def action_approve(self):
        """Approve (SDM action for 247)"""
        self.ensure_one()
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM or Admin can approve.'))
        
        if self.state != 'draft':
            raise ValidationError(_('Only draft records can be approved.'))
        
        self.state = 'approved'
        self.approved_date = fields.Datetime.now()
        self.message_post(body=_('Approved by SDM %s') % self.env.user.name, subtype_xmlid='mail.mt_note')

    def action_submit(self):
        raise ValidationError(_('Submit is not required for CGLRC 247 sections. SDM can approve directly.'))

    def action_send_back(self):
        raise ValidationError(_('Send back is not applicable for CGLRC 247 sections.'))

    def _validate_state_transition(self, old_state, new_state):
        valid_transitions = {
            'draft': ['approved'],
            'approved': ['draft'],
        }
        if new_state not in valid_transitions.get(old_state, []):
            raise ValidationError(_('Invalid status transition for CGLRC 247.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section247_2.cglrc') or 'New'
        return super().create(vals_list)

class Section247_3CGLRC(models.Model):
    _name = 'bhu.section247_3.cglrc'
    _description = 'Award (247.3) / अवार्ड (247.3)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference / संदर्भ', required=True, tracking=True, default='New', readonly=True)

    state = fields.Selection(selection_add=[
        ('draft', 'Draft'),
        ('approved', 'Approved'),
    ], ondelete={'draft': 'set default', 'approved': 'set default'})

    def action_approve(self):
        """Approve (SDM action for 247)"""
        self.ensure_one()
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM or Admin can approve.'))
        
        if self.state != 'draft':
            raise ValidationError(_('Only draft records can be approved.'))
        
        self.state = 'approved'
        self.approved_date = fields.Datetime.now()
        self.message_post(body=_('Approved by SDM %s') % self.env.user.name, subtype_xmlid='mail.mt_note')

    def action_submit(self):
        raise ValidationError(_('Submit is not required for CGLRC 247 sections. SDM can approve directly.'))

    def action_send_back(self):
        raise ValidationError(_('Send back is not applicable for CGLRC 247 sections.'))

    def _validate_state_transition(self, old_state, new_state):
        valid_transitions = {
            'draft': ['approved'],
            'approved': ['draft'],
        }
        if new_state not in valid_transitions.get(old_state, []):
            raise ValidationError(_('Invalid status transition for CGLRC 247.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('bhu.section247_3.cglrc') or 'New'
        return super().create(vals_list)

