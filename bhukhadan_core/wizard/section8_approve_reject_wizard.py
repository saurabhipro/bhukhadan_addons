# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Section8ApproveRejectWizard(models.TransientModel):
    _name = 'bhu.section8.approve.reject.wizard'
    _description = 'Section 8 Approve/Reject Wizard'

    res_id = fields.Integer(string='Record ID', required=True)
    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ], string='Action Type', required=True)
    reason = fields.Text(string='Reason / कारण', 
                        help='Please provide a reason for approval or rejection')

    def action_confirm(self):
        """Confirm approve or reject action"""
        self.ensure_one()
        
        # Get the Section 8 record
        section8 = self.env['bhu.section8'].browse(self.res_id)
        if not section8.exists():
            raise ValidationError(_('Section 8 record not found.'))
        
        if self.action_type == 'approve':
            if section8.state == 'approved':
                raise ValidationError(_('Section 8 is already approved.'))
            section8.state = 'approved'
            section8.approval_date = fields.Datetime.now()
            if self.reason:
                section8.approval_reason = self.reason
            message = _('Section 8 approved by %s') % self.env.user.name
            if self.reason:
                message += _('\n\nReason: %s') % self.reason
            section8.message_post(body=message, message_type='notification')
        elif self.action_type == 'reject':
            if section8.state == 'rejected':
                raise ValidationError(_('Section 8 is already rejected.'))
            if not self.reason:
                raise ValidationError(_('Please provide a rejection reason.'))
            section8.state = 'rejected'
            section8.rejection_date = fields.Datetime.now()
            section8.rejection_reason = self.reason
            section8.message_post(
                body=_('Section 8 rejected by %s\n\nReason: %s') % (self.env.user.name, self.reason),
                message_type='notification'
            )
        
        return {'type': 'ir.actions.act_window_close'}

