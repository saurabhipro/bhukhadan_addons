# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProcessSendBackWizard(models.TransientModel):
    _name = 'process.send.back.wizard'
    _description = 'Process Send Back Reason Wizard'

    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Integer(string='Record ID', required=True)
    reason = fields.Text(string='Reason / कारण', required=True, 
                        help='Please provide the reason for sending back')

    def action_send_back_confirm(self):
        """Send back the record with reason"""
        self.ensure_one()
        
        if not self.reason:
            raise ValidationError(_('Please provide a reason for sending back.'))
        
        # Get the record
        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise ValidationError(_('Record not found.'))
        
        # Update state and post message
        record.write({'state': 'send_back'})
        record.message_post(
            body=_('Sent back by %s\n\nReason: %s') % (self.env.user.name, self.reason)
        )
        
        # Create activity for SDM users
        if hasattr(record, '_create_send_back_activity'):
            record._create_send_back_activity()
        
        return {'type': 'ir.actions.act_window_close'}

