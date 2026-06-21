# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PostAwardPayment(models.Model):
    _name = 'bhu.post.award.payment'
    _description = 'Post-Award Payment / पुरस्कारोत्तर भुगतान'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, name'

    name = fields.Char(string='Payment Number / भुगतान संख्या', required=True, tracking=True)
    payment_date = fields.Date(string='Payment Date / भुगतान दिनाँक', required=True, 
                               default=fields.Date.today, tracking=True)
    
    # Company/Organization Information
    company_id = fields.Many2one('res.company', string='Company / कंपनी', required=True, 
                                 default=lambda self: self.env.company, tracking=True)
    
    # Related Records
    survey_id = fields.Many2one('bhu.survey', string='Survey / सर्वे', required=True, tracking=True)
    landowner_id = fields.Many2one('bhu.landowner', string='Payee / प्राप्तकर्ता', 
                                  required=True, tracking=True)
    
    # Payment Details
    payment_type = fields.Selection([
        ('compensation', 'Compensation / मुआवजा'),
        ('rehabilitation', 'Rehabilitation / पुनर्वास'),
        ('bonus', 'Bonus / बोनस'),
        ('interest', 'Interest / ब्याज'),
        ('other', 'Other / अन्य')
    ], string='Payment Type / भुगतान प्रकार', required=True, tracking=True)
    
    amount = fields.Monetary(string='Amount / राशि', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency / मुद्रा', 
                                 default=lambda self: self.env.company.currency_id, tracking=True)
    
    # Payment Method
    payment_method = fields.Selection([
        ('cash', 'Cash / नकद'),
        ('cheque', 'Cheque / चेक'),
        ('bank_transfer', 'Bank Transfer / बैंक ट्रांसफर'),
        ('demand_draft', 'Demand Draft / डिमांड ड्राफ्ट'),
        ('neft', 'NEFT / एनईएफटी'),
        ('rtgs', 'RTGS / आरटीजीएस'),
        ('upi', 'UPI / यूपीआई')
    ], string='Payment Method / भुगतान विधि', required=True, tracking=True)
    
    # Bank Details
    bank_name = fields.Char(string='Bank Name / बैंक का नाम', tracking=True)
    account_number = fields.Char(string='Account Number / खाता संख्या', tracking=True)
    ifsc_code = fields.Char(string='IFSC Code / आईएफएससी कोड', tracking=True)
    branch_name = fields.Char(string='Branch Name / शाखा का नाम', tracking=True)
    
    # Cheque/DD Details
    cheque_number = fields.Char(string='Cheque/DD Number / चेक/डीडी संख्या', tracking=True)
    cheque_date = fields.Date(string='Cheque/DD Date / चेक/डीडी दिनाँक', tracking=True)
    drawee_bank = fields.Char(string='Drawee Bank / आहर्ता बैंक', tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft / मसौदा'),
        ('approved', 'Approved / स्वीकृत'),
        ('processed', 'Processed / प्रसंस्कृत'),
        ('paid', 'Paid / भुगतान किया गया'),
        ('cancelled', 'Cancelled / रद्द')
    ], string='Status / स्थिति', default='draft', tracking=True)
    
    # Approval Details
    approved_by = fields.Many2one('res.users', string='Approved By / द्वारा स्वीकृत', tracking=True)
    approval_date = fields.Date(string='Approval Date / स्वीकृति दिनाँक', tracking=True)
    approval_notes = fields.Text(string='Approval Notes / स्वीकृति नोट्स', tracking=True)
    
    # Processing Details
    processed_by = fields.Many2one('res.users', string='Processed By / द्वारा प्रसंस्कृत', tracking=True)
    processing_date = fields.Date(string='Processing Date / प्रसंस्करण दिनाँक', tracking=True)
    processing_notes = fields.Text(string='Processing Notes / प्रसंस्करण नोट्स', tracking=True)
    
    # Payment Confirmation
    payment_reference = fields.Char(string='Payment Reference / भुगतान संदर्भ', tracking=True)
    transaction_id = fields.Char(string='Transaction ID / लेनदेन आईडी', tracking=True)
    payment_confirmation_date = fields.Date(string='Confirmation Date / पुष्टि दिनाँक', tracking=True)
    
    # Attachments
    attachment_ids = fields.One2many('ir.attachment', 'res_id', string='Attachments / अनुलग्नक', 
                                   domain=[('res_model', '=', 'bhu.post.award.payment')])
    
    @api.constrains('amount')
    def _check_amount(self):
        """Validate payment amount"""
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero.'))
    
    @api.constrains('payment_date', 'cheque_date', 'approval_date', 'processing_date', 'payment_confirmation_date')
    def _check_dates(self):
        """Validate payment dates"""
        for record in self:
            if record.cheque_date and record.payment_date:
                if record.cheque_date < record.payment_date:
                    raise ValidationError(_('Cheque date cannot be before payment date.'))
            if record.approval_date and record.payment_date:
                if record.approval_date < record.payment_date:
                    raise ValidationError(_('Approval date cannot be before payment date.'))
            if record.processing_date and record.approval_date:
                if record.processing_date < record.approval_date:
                    raise ValidationError(_('Processing date cannot be before approval date.'))
    
    def action_approve(self):
        """Approve the payment"""
        for record in self:
            if record.state == 'draft':
                record.write({
                    'state': 'approved',
                    'approved_by': self.env.user.id,
                    'approval_date': fields.Date.today()
                })
                record.message_post(
                    body=_('Payment approved by %s') % self.env.user.name,
                    message_type='notification'
                )
    
    def action_process(self):
        """Process the payment"""
        for record in self:
            if record.state == 'approved':
                record.write({
                    'state': 'processed',
                    'processed_by': self.env.user.id,
                    'processing_date': fields.Date.today()
                })
                record.message_post(
                    body=_('Payment processed by %s') % self.env.user.name,
                    message_type='notification'
                )
    
    def action_pay(self):
        """Mark payment as paid"""
        for record in self:
            if record.state == 'processed':
                record.write({
                    'state': 'paid',
                    'payment_confirmation_date': fields.Date.today()
                })
                record.message_post(
                    body=_('Payment completed and confirmed'),
                    message_type='notification'
                )
    
    def action_cancel(self):
        """Cancel the payment"""
        for record in self:
            if record.state in ['draft', 'approved', 'processed']:
                record.write({'state': 'cancelled'})
                record.message_post(
                    body=_('Payment cancelled'),
                    message_type='notification'
                )
