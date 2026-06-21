# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SiaSendBackWizard(models.TransientModel):
    _name = 'sia.send.back.wizard'
    _description = 'SIA Send Back Reason Wizard'

    reason = fields.Text(string='Reason / कारण', required=True, 
                        help='Please provide the reason for sending back the SIA proposal')
    sia_team_id = fields.Many2one('bhu.sia.team', string='SIA Team', required=True)

    def action_send_back(self):
        """Send back the SIA Team with reason"""
        self.ensure_one()
        
        if not self.reason:
            raise ValidationError(_('Please provide a reason for sending back.'))
        
        sia_team = self.sia_team_id
        sia_team.state = 'send_back'
        sia_team.message_post(
            body=_('SIA Team sent back by %s\n\nReason: %s') % (self.env.user.name, self.reason)
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('SIA Team has been sent back successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

