# -*- coding: utf-8 -*-

from odoo import models, api, _


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def action_preview_attachment(self):
        """Open attachment in a popup preview window"""
        self.ensure_one()
        if not self.datas:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No file to preview.'),
                    'type': 'danger',
                }
            }
        
        # Generate URL for the attachment
        url = f'/web/content/{self.id}?download=false'
        
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

