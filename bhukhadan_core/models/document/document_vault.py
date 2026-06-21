# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64


class DocumentVault(models.Model):
    _name = 'bhu.document.vault'
    _description = 'Document Vault'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'signed_date desc, create_date desc'

    name = fields.Char(string='Document Name / दस्तावेज़ का नाम', required=True, tracking=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True, tracking=True)
    document_type = fields.Selection([
        ('sec4_signed_notification', 'Section 4 Signed Notification / धारा 4 हस्ताक्षरित अधिसूचना'),
        ('sia_reports', 'SIA Reports / SIA रिपोर्ट'),
        ('sec15_objections', 'Section 15 Objections / धारा 15 आपत्तियां'),
        ('sec19_signed_notification', 'Section 19 Signed Notification / धारा 19 हस्ताक्षरित अधिसूचना'),
        ('sec21_notification', 'Section 21 Notification / धारा 21 अधिसूचना'),
        ('section23_land_award', 'Section 23 Land Award / धारा 23 भूमि अवार्ड'),
        ('section23_tree_award', 'Section 23 Tree Award / धारा 23 वृक्ष अवार्ड'),
        ('section23_asset_award', 'Section 23 Asset Award / धारा 23 परिसंपत्ति अवार्ड'),
        ('section23_standard_award', 'Section 23 Standard Award / धारा 23 मानक अवार्ड'),
        ('section23_consolidated_award', 'Section 23 Consolidated Award / धारा 23 समेकित अवार्ड'),
        ('section23_rr_award', 'Section 23 R&R Award / धारा 23 पुनर्वास अवार्ड'),
        ('payment_signed_proof', 'Payment Signed Payment Proof / भुगतान हस्ताक्षरित प्रमाण'),
    ], string='Document Type / दस्तावेज़ प्रकार', required=True, tracking=True)
    signed_date = fields.Date(string='Final Signed Date / अंतिम हस्ताक्षर दिनांक', required=True, tracking=True, default=fields.Date.today)
    
    # Document file
    document_file = fields.Binary(string='Document File / दस्तावेज़ फ़ाइल', required=True, tracking=True)
    document_filename = fields.Char(string='File Name / फ़ाइल नाम')
    
    # Additional fields
    description = fields.Text(string='Description / विवरण', tracking=True)
    uploaded_by = fields.Many2one('res.users', string='Uploaded By / अपलोड किया गया', default=lambda self: self.env.user, readonly=True)
    upload_date = fields.Datetime(string='Upload Date / अपलोड दिनांक', default=fields.Datetime.now, readonly=True)
    
    # Email sharing
    email_recipients = fields.Char(string='Email Recipients / ईमेल प्राप्तकर्ता', 
                                   help='Comma-separated email addresses / अल्पविराम से अलग ईमेल पते')
    
    @api.constrains('village_id', 'project_id')
    def _check_village_project(self):
        """Ensure village belongs to the selected project"""
        for record in self:
            if record.village_id and record.project_id:
                if record.village_id not in record.project_id.village_ids:
                    raise ValidationError(_('Selected village does not belong to the selected project.'))

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain"""
        self.village_id = False
        if self.project_id and self.project_id.village_ids:
            return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        return {'domain': {'village_id': []}}

    def action_send_email(self):
        """Send document via email"""
        self.ensure_one()
        if not self.email_recipients:
            raise ValidationError(_('Please enter email recipients.'))
        
        # Parse email addresses
        emails = [email.strip() for email in self.email_recipients.split(',') if email.strip()]
        if not emails:
            raise ValidationError(_('Please enter valid email addresses.'))
        
        # Create mail message
        mail_values = {
            'subject': _('Document: %s') % self.name,
            'body_html': _('''
                <p>Dear Recipient,</p>
                <p>Please find attached document: <strong>%s</strong></p>
                <p><strong>Project:</strong> %s</p>
                <p><strong>Village:</strong> %s</p>
                <p><strong>Document Type:</strong> %s</p>
                <p><strong>Signed Date:</strong> %s</p>
                <p>Best regards,<br/>%s</p>
            ''') % (self.name, self.project_id.name, self.village_id.name, 
                   dict(self._fields['document_type'].selection)[self.document_type], 
                   self.signed_date, self.env.user.name),
            'email_to': ','.join(emails),
            'attachment_ids': [(0, 0, {
                'name': self.document_filename or self.name,
                'datas': self.document_file,
                'res_model': 'bhu.document.vault',
                'res_id': self.id,
            })],
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        self.message_post(
            body=_('Document sent via email to: %s') % self.email_recipients,
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Document sent successfully to %d recipient(s).') % len(emails),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_download(self):
        """Download document"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/bhu.document.vault/%s/document_file/%s?download=true' % (self.id, self.document_filename or 'document'),
            'target': 'self',
        }

    def action_preview(self):
        """Preview document"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/bhu.document.vault/%s/document_file/%s' % (self.id, self.document_filename or 'document'),
            'target': 'new',
        }

