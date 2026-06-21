# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PaymentReconciliation(models.Model):
    _name = 'bhu.payment.reconciliation'
    _description = 'Payment Reconciliation / भुगतान समाधान'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reconciliation_date desc, name'

    name = fields.Char(string='Reconciliation Number / समाधान संख्या', required=True, tracking=True)
    reconciliation_date = fields.Date(string='Reconciliation Date / समाधान दिनाँक', required=True, 
                                      default=fields.Date.today, tracking=True)
    
    # Company/Organization Information
    company_id = fields.Many2one('res.company', string='Company / कंपनी', required=True, 
                                 default=lambda self: self.env.company, tracking=True)
    
    # Related Records
    survey_id = fields.Many2one('bhu.survey', string='Survey / सर्वे', required=True, tracking=True)
    payment_ids = fields.Many2many('bhu.post.award.payment', string='Related Payments / संबंधित भुगतान', 
                                  tracking=True)
    
    # Reconciliation Details
    reconciliation_type = fields.Selection([
        ('monthly', 'Monthly / मासिक'),
        ('quarterly', 'Quarterly / त्रैमासिक'),
        ('annual', 'Annual / वार्षिक'),
        ('ad_hoc', 'Ad-hoc / विशेष')
    ], string='Reconciliation Type / समाधान प्रकार', required=True, tracking=True)
    
    period_start = fields.Date(string='Period Start / अवधि प्रारंभ', required=True, tracking=True)
    period_end = fields.Date(string='Period End / अवधि समाप्ति', required=True, tracking=True)
    
    # Financial Summary
    total_payments = fields.Monetary(string='Total Payments / कुल भुगतान', 
                                    compute='_compute_financial_summary', store=True)
    total_amount = fields.Monetary(string='Total Amount / कुल राशि', 
                                  compute='_compute_financial_summary', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency / मुद्रा', 
                                 default=lambda self: self.env.company.currency_id, tracking=True)
    
    # Discrepancies
    discrepancy_count = fields.Integer(string='Discrepancies Count / विसंगतियों की संख्या', 
                                      compute='_compute_discrepancies', store=True)
    discrepancy_amount = fields.Monetary(string='Discrepancy Amount / विसंगति राशि', 
                                        compute='_compute_discrepancies', store=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft / मसौदा'),
        ('in_progress', 'In Progress / प्रगति में'),
        ('reviewed', 'Reviewed / समीक्षित'),
        ('approved', 'Approved / स्वीकृत'),
        ('completed', 'Completed / पूर्ण')
    ], string='Status / स्थिति', default='draft', tracking=True)
    
    # Review Details
    reviewed_by = fields.Many2one('res.users', string='Reviewed By / द्वारा समीक्षित', tracking=True)
    review_date = fields.Date(string='Review Date / समीक्षा दिनाँक', tracking=True)
    review_notes = fields.Text(string='Review Notes / समीक्षा नोट्स', tracking=True)
    
    # Approval Details
    approved_by = fields.Many2one('res.users', string='Approved By / द्वारा स्वीकृत', tracking=True)
    approval_date = fields.Date(string='Approval Date / स्वीकृति दिनाँक', tracking=True)
    approval_notes = fields.Text(string='Approval Notes / स्वीकृति नोट्स', tracking=True)
    
    # Reconciliation Notes
    reconciliation_notes = fields.Text(string='Reconciliation Notes / समाधान नोट्स', tracking=True)
    discrepancies_notes = fields.Text(string='Discrepancies Notes / विसंगति नोट्स', tracking=True)
    resolution_notes = fields.Text(string='Resolution Notes / समाधान नोट्स', tracking=True)
    
    # Attachments
    attachment_ids = fields.One2many('ir.attachment', 'res_id', string='Attachments / अनुलग्नक', 
                                   domain=[('res_model', '=', 'bhu.payment.reconciliation')])
    
    @api.depends('payment_ids', 'payment_ids.amount', 'payment_ids.state')
    def _compute_financial_summary(self):
        """Compute financial summary"""
        for record in self:
            payments = record.payment_ids.filtered(lambda p: p.state == 'paid')
            record.total_payments = len(payments)
            record.total_amount = sum(payments.mapped('amount'))
    
    @api.depends('payment_ids')
    def _compute_discrepancies(self):
        """Compute discrepancies"""
        for record in self:
            # This would need to be implemented based on specific business logic
            # For now, setting to 0
            record.discrepancy_count = 0
            record.discrepancy_amount = 0.0
    
    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        """Validate reconciliation period"""
        for record in self:
            if record.period_end < record.period_start:
                raise ValidationError(_('Period end cannot be before period start.'))
    
    @api.constrains('reconciliation_date', 'period_start', 'period_end')
    def _check_dates(self):
        """Validate reconciliation dates"""
        for record in self:
            if record.reconciliation_date < record.period_start:
                raise ValidationError(_('Reconciliation date cannot be before period start.'))
            if record.reconciliation_date > record.period_end:
                raise ValidationError(_('Reconciliation date cannot be after period end.'))
    
    def action_start_reconciliation(self):
        """Start the reconciliation process"""
        for record in self:
            if record.state == 'draft':
                record.write({'state': 'in_progress'})
                record.message_post(
                    body=_('Reconciliation process started'),
                    message_type='notification'
                )
    
    def action_review(self):
        """Mark reconciliation as reviewed"""
        for record in self:
            if record.state == 'in_progress':
                record.write({
                    'state': 'reviewed',
                    'reviewed_by': self.env.user.id,
                    'review_date': fields.Date.today()
                })
                record.message_post(
                    body=_('Reconciliation reviewed by %s') % self.env.user.name,
                    message_type='notification'
                )
    
    def action_approve(self):
        """Approve the reconciliation"""
        for record in self:
            if record.state == 'reviewed':
                record.write({
                    'state': 'approved',
                    'approved_by': self.env.user.id,
                    'approval_date': fields.Date.today()
                })
                record.message_post(
                    body=_('Reconciliation approved by %s') % self.env.user.name,
                    message_type='notification'
                )
    
    def action_complete(self):
        """Complete the reconciliation"""
        for record in self:
            if record.state == 'approved':
                record.write({'state': 'completed'})
                record.message_post(
                    body=_('Reconciliation completed'),
                    message_type='notification'
                )
    
    def action_view_payments(self):
        """View related payments"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments for %s') % self.name,
            'res_model': 'bhu.post.award.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payment_ids.ids)],
            'context': {'default_survey_id': self.survey_id.id}
        }
