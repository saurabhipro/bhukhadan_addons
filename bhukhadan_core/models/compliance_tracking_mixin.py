# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class ComplianceTrackingMixin(models.AbstractModel):
    """Mixin to track compliance dates and delays for notifications"""
    _name = 'bhu.compliance.tracking.mixin'
    _description = 'Compliance Tracking Mixin'

    # Actual dates - captured when state changes
    draft_date = fields.Datetime(string='Draft Date / प्रारूप दिनांक', 
                                 readonly=True, tracking=True,
                                 help='Date when record was created or reset to draft')
    submitted_date = fields.Datetime(string='Submitted Date / प्रस्तुत दिनांक', 
                                     readonly=True, tracking=True,
                                     help='Date when record was submitted to Collector')
    approved_date = fields.Datetime(string='Approved Date / अनुमोदित दिनांक', 
                                    readonly=True, tracking=True,
                                    help='Date when record was approved by Collector')
    sent_back_date = fields.Datetime(string='Sent Back Date / वापस भेजा गया दिनांक', 
                                     readonly=True, tracking=True,
                                     help='Date when record was sent back by Collector')

    # Expected/SLA dates - based on notification type and rules
    expected_submission_date = fields.Datetime(string='Expected Submission Date / अपेक्षित प्रस्तुत दिनांक',
                                               compute='_compute_expected_dates', store=True,
                                               help='Expected date by which record should be submitted')
    expected_approval_date = fields.Datetime(string='Expected Approval Date / अपेक्षित अनुमोदन दिनांक',
                                             compute='_compute_expected_dates', store=True,
                                             help='Expected date by which record should be approved')

    # Delay calculations (in days)
    submission_delay_days = fields.Integer(string='Submission Delay (Days) / प्रस्तुत विलंब (दिन)',
                                           compute='_compute_delays', store=True,
                                           help='Number of days delayed in submission (negative = early, positive = delayed)')
    approval_delay_days = fields.Integer(string='Approval Delay (Days) / अनुमोदन विलंब (दिन)',
                                         compute='_compute_delays', store=True,
                                         help='Number of days delayed in approval (negative = early, positive = delayed)')

    # Compliance status indicators
    is_submission_compliant = fields.Boolean(string='Submission Compliant / प्रस्तुत अनुपालन',
                                             compute='_compute_compliance_status', store=True,
                                             help='Green if submitted on time, Red if delayed')
    is_approval_compliant = fields.Boolean(string='Approval Compliant / अनुमोदन अनुपालन',
                                           compute='_compute_compliance_status', store=True,
                                           help='Green if approved on time, Red if delayed')
    overall_compliance_status = fields.Selection([
        ('compliant', 'Compliant / अनुपालन (Green)'),
        ('delayed', 'Delayed / विलंबित (Red)'),
        ('pending', 'Pending / लंबित (Yellow)'),
        ('not_started', 'Not Started / शुरू नहीं हुआ'),
    ], string='Overall Compliance Status / समग्र अनुपालन स्थिति',
       compute='_compute_compliance_status', store=True)

    # Days pending (for records in submitted state)
    days_pending_approval = fields.Integer(string='Days Pending Approval / अनुमोदन के लिए लंबित दिन',
                                           compute='_compute_delays', store=True,
                                           help='Number of days record has been pending approval')

    @api.depends('draft_date', 'submitted_date', 'state')
    def _compute_expected_dates(self):
        """Compute expected dates based on notification type and SLA rules"""
        for record in self:
            # Get SLA days based on notification type
            sla_days = record._get_sla_days()
            
            if record.draft_date:
                # Expected submission: draft_date + submission_sla_days
                if sla_days.get('submission_days'):
                    record.expected_submission_date = record.draft_date + relativedelta(days=sla_days['submission_days'])
                else:
                    record.expected_submission_date = False
                
                # Expected approval: draft_date + submission_sla_days + approval_sla_days
                if sla_days.get('submission_days') and sla_days.get('approval_days'):
                    total_days = sla_days['submission_days'] + sla_days['approval_days']
                    record.expected_approval_date = record.draft_date + relativedelta(days=total_days)
                else:
                    record.expected_approval_date = False
            else:
                record.expected_submission_date = False
                record.expected_approval_date = False

    def _get_sla_days(self):
        """Get SLA days based on notification type - Override in specific models"""
        # Default SLA (can be configured per notification type)
        return {
            'submission_days': 7,  # 7 days to submit after draft
            'approval_days': 5,    # 5 days to approve after submission
        }

    @api.depends('submitted_date', 'approved_date', 'expected_submission_date', 
                 'expected_approval_date', 'state')
    def _compute_delays(self):
        """Compute delay in days for submission and approval"""
        for record in self:
            now = fields.Datetime.now()
            
            # Submission delay
            if record.submitted_date and record.expected_submission_date:
                delta = record.submitted_date - record.expected_submission_date
                record.submission_delay_days = delta.days
            elif record.state in ['submitted', 'approved', 'send_back'] and record.expected_submission_date:
                # If submitted but no submitted_date, calculate from expected date
                if now > record.expected_submission_date:
                    delta = now - record.expected_submission_date
                    record.submission_delay_days = delta.days
                else:
                    record.submission_delay_days = 0
            else:
                record.submission_delay_days = 0

            # Approval delay
            if record.approved_date and record.expected_approval_date:
                delta = record.approved_date - record.expected_approval_date
                record.approval_delay_days = delta.days
            elif record.state == 'approved' and record.expected_approval_date:
                # If approved but no approved_date, calculate from expected date
                if now > record.expected_approval_date:
                    delta = now - record.expected_approval_date
                    record.approval_delay_days = delta.days
                else:
                    record.approval_delay_days = 0
            else:
                record.approval_delay_days = 0

            # Days pending approval
            if record.state == 'submitted' and record.submitted_date:
                delta = now - record.submitted_date
                record.days_pending_approval = delta.days
            else:
                record.days_pending_approval = 0

    @api.depends('submission_delay_days', 'approval_delay_days', 'state', 
                 'expected_submission_date', 'expected_approval_date')
    def _compute_compliance_status(self):
        """Compute compliance status (Green/Red indicators)"""
        for record in self:
            # Submission compliance
            if record.state in ['submitted', 'approved', 'send_back']:
                if record.submission_delay_days <= 0:
                    record.is_submission_compliant = True  # Green
                else:
                    record.is_submission_compliant = False  # Red
            else:
                # Check if past expected submission date
                if record.expected_submission_date and fields.Datetime.now() > record.expected_submission_date:
                    record.is_submission_compliant = False  # Red
                else:
                    record.is_submission_compliant = True  # Green (not yet due)

            # Approval compliance
            if record.state == 'approved':
                if record.approval_delay_days <= 0:
                    record.is_approval_compliant = True  # Green
                else:
                    record.is_approval_compliant = False  # Red
            elif record.state == 'submitted':
                # Check if past expected approval date
                if record.expected_approval_date and fields.Datetime.now() > record.expected_approval_date:
                    record.is_approval_compliant = False  # Red
                else:
                    record.is_approval_compliant = True  # Yellow (pending but not overdue)
            else:
                record.is_approval_compliant = True  # N/A

            # Overall compliance status
            if record.state == 'draft':
                record.overall_compliance_status = 'not_started'
            elif record.state == 'submitted':
                if record.is_submission_compliant and record.is_approval_compliant:
                    record.overall_compliance_status = 'pending'  # Yellow
                else:
                    record.overall_compliance_status = 'delayed'  # Red
            elif record.state == 'approved':
                if record.is_submission_compliant and record.is_approval_compliant:
                    record.overall_compliance_status = 'compliant'  # Green
                else:
                    record.overall_compliance_status = 'delayed'  # Red
            elif record.state == 'send_back':
                record.overall_compliance_status = 'delayed'  # Red
            else:
                record.overall_compliance_status = 'not_started'

    def _update_state_date(self, state):
        """Update the date field when state changes"""
        date_field_map = {
            'draft': 'draft_date',
            'submitted': 'submitted_date',
            'approved': 'approved_date',
            'send_back': 'sent_back_date',
        }
        
        if state in date_field_map:
            field_name = date_field_map[state]
            # Only update if not already set (preserve first occurrence)
            if not self[field_name]:
                self[field_name] = fields.Datetime.now()

