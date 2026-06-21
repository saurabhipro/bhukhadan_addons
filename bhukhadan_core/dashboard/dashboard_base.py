# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class BhuKhadanDashboard(models.TransientModel):
    _name = 'bhuarjan.dashboard'
    _description = 'BhuKhadan Dashboard'
    _inherit = [
        'bhuarjan.dashboard.helpers',
        'bhuarjan.dashboard.counts',
        'bhuarjan.dashboard.actions',
        'bhuarjan.dashboard.data',
        'bhuarjan.dashboard.stats',
    ]

    current_datetime = fields.Char(string='Current Date & Time', compute='_compute_current_datetime', store=False)
    
    @api.model
    def default_get(self, fields_list):
        """Set default values including current datetime"""
        res = super().default_get(fields_list)
        return res
    
    @api.depends()
    def _compute_current_datetime(self):
        """Compute current date and time as formatted string"""
        from datetime import datetime
        for record in self:
            now = datetime.now()
            record.current_datetime = now.strftime('%Y-%m-%d %H:%M:%S') or 'Loading...'

    is_admin = fields.Boolean(string='Is Admin', compute='_compute_is_admin', store=False)
    
    @api.depends()
    def _compute_is_admin(self):
        """Check if current user is admin"""
        for record in self:
            try:
                record.is_admin = self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin') or self.env.user.has_group('base.group_system')
            except:
                record.is_admin = False

    # Master Data Counts
    total_districts = fields.Integer(string='Total Districts', readonly=True, default=0)
    total_sub_divisions = fields.Integer(string='Total Sub Divisions', readonly=True, default=0)
    total_tehsils = fields.Integer(string='Total Tehsils', readonly=True, default=0)
    total_villages = fields.Integer(string='Total Villages', readonly=True, default=0)
    total_projects = fields.Integer(string='Total Projects', readonly=True, default=0)
    total_departments = fields.Integer(string='Total Departments', readonly=True, default=0)
    total_landowners = fields.Integer(string='Total Landowners', readonly=True, default=0)
    total_rate_masters = fields.Integer(string='Total Land Rate Masters', readonly=True, default=0)
    
    # Survey Counts
    total_surveys = fields.Integer(string='Total Surveys', readonly=True, default=0)
    draft_surveys = fields.Integer(string='Draft Surveys', readonly=True, default=0)
    submitted_surveys = fields.Integer(string='Submitted Surveys', readonly=True, default=0)
    approved_surveys = fields.Integer(string='Approved Surveys', readonly=True, default=0)
    rejected_surveys = fields.Integer(string='Rejected Surveys', readonly=True, default=0)
    total_surveys_done = fields.Integer(string='Total Surveys Done', readonly=True, default=0)
    pending_surveys = fields.Integer(string='Pending Surveys', readonly=True, default=0)
    
    # Process Counts
    total_section4_notifications = fields.Integer(string='Section 4 Notifications', readonly=True, default=0)
    draft_section4 = fields.Integer(string='Draft Section 4', readonly=True, default=0)
    generated_section4 = fields.Integer(string='Generated Section 4', readonly=True, default=0)
    signed_section4 = fields.Integer(string='Signed Section 4', readonly=True, default=0)
    
    total_section11_reports = fields.Integer(string='Section 11 Reports', readonly=True, default=0)
    draft_section11 = fields.Integer(string='Draft Section 11', readonly=True, default=0)
    generated_section11 = fields.Integer(string='Generated Section 11', readonly=True, default=0)
    signed_section11 = fields.Integer(string='Signed Section 11', readonly=True, default=0)
    
    total_expert_committee_reports = fields.Integer(string='Expert Committee Reports', readonly=True, default=0)
    total_section15_objections = fields.Integer(string='Section 15 Objections', readonly=True, default=0)
    
    # Section 19 Notifications
    total_section19_notifications = fields.Integer(string='Section 19 Notifications', readonly=True, default=0)
    draft_section19 = fields.Integer(string='Draft Section 19', readonly=True, default=0)
    generated_section19 = fields.Integer(string='Generated Section 19', readonly=True, default=0)
    signed_section19 = fields.Integer(string='Signed Section 19', readonly=True, default=0)
    
    # SIA Team Counts
    total_sia_teams = fields.Integer(string='Total SIA Teams', readonly=True, default=0)
    draft_sia_teams = fields.Integer(string='Draft SIA Teams', readonly=True, default=0)
    submitted_sia_teams = fields.Integer(string='Submitted SIA Teams', readonly=True, default=0)
    approved_sia_teams = fields.Integer(string='Approved SIA Teams', readonly=True, default=0)
    send_back_sia_teams = fields.Integer(string='Send Back SIA Teams', readonly=True, default=0)
    
    # Payment File Counts
    total_payment_files = fields.Integer(string='Payment Files', readonly=True, default=0)
    draft_payment_files = fields.Integer(string='Draft Payment Files', readonly=True, default=0)
    generated_payment_files = fields.Integer(string='Generated Payment Files', readonly=True, default=0)
    
    # Payment Reconciliation Counts
    total_payment_reconciliations = fields.Integer(string='Payment Reconciliations', readonly=True, default=0)
    draft_reconciliations = fields.Integer(string='Draft Reconciliations', readonly=True, default=0)
    processed_reconciliations = fields.Integer(string='Processed Reconciliations', readonly=True, default=0)
    completed_reconciliations = fields.Integer(string='Completed Reconciliations', readonly=True, default=0)
    
    # Document Vault Counts
    total_documents = fields.Integer(string='Total Documents', readonly=True, default=0)
    
    # Active Mobile Users (based on JWT tokens)
    active_mobile_users = fields.Integer(string='Active Mobile Users', readonly=True, default=0,
                                        help='Number of unique users currently logged in via mobile channel')

    def _compute_all_counts(self):
        """Compute all counts for the dashboard"""
        for record in self:
            # Master Data Counts
            record.total_districts = self.env['bhu.district'].search_count([])
            record.total_sub_divisions = self.env['bhu.sub.division'].search_count([])
            record.total_tehsils = self.env['bhu.tehsil'].search_count([])
            record.total_villages = self.env['bhu.village'].search_count([])
            record.total_projects = self.env['bhu.project'].search_count([])
            record.total_departments = self.env['bhu.department'].search_count([])
            record.total_landowners = self.env['bhu.landowner'].search_count([])
            record.total_rate_masters = self.env['bhu.rate.master'].search_count([])
            
            # Survey Counts
            record.total_surveys = self.env['bhu.survey'].search_count([])
            record.draft_surveys = self.env['bhu.survey'].search_count([('state', '=', 'draft')])
            record.submitted_surveys = self.env['bhu.survey'].search_count([('state', '=', 'submitted')])
            record.approved_surveys = self.env['bhu.survey'].search_count([('state', '=', 'approved')])
            record.rejected_surveys = self.env['bhu.survey'].search_count([('state', '=', 'rejected')])
            # Total Surveys Done = Approved + Rejected
            record.total_surveys_done = record.approved_surveys + record.rejected_surveys
            # Pending = Submitted + Rejected
            record.pending_surveys = record.submitted_surveys + record.rejected_surveys
            
            # Section 4 Notifications
            record.total_section4_notifications = self.env['bhu.section4.notification'].search_count([])
            record.draft_section4 = self.env['bhu.section4.notification'].search_count([('state', '=', 'draft')])
            record.generated_section4 = self.env['bhu.section4.notification'].search_count([('state', '=', 'generated')])
            record.signed_section4 = self.env['bhu.section4.notification'].search_count([('state', '=', 'signed')])
            
            # Section 11 Reports
            record.total_section11_reports = self.env['bhu.section11.preliminary.report'].search_count([])
            record.draft_section11 = self.env['bhu.section11.preliminary.report'].search_count([('state', '=', 'draft')])
            record.generated_section11 = self.env['bhu.section11.preliminary.report'].search_count([('state', '=', 'generated')])
            record.signed_section11 = self.env['bhu.section11.preliminary.report'].search_count([('state', '=', 'signed')])
            
            # Expert Committee Reports
            record.total_expert_committee_reports = self.env['bhu.expert.committee.report'].search_count([])
            
            # Section 15 Objections
            record.total_section15_objections = self.env['bhu.section15.objection'].search_count([])
            
            # Section 19 Notifications
            record.total_section19_notifications = self.env['bhu.section19.notification'].search_count([])
            record.draft_section19 = self.env['bhu.section19.notification'].search_count([('state', '=', 'draft')])
            record.generated_section19 = self.env['bhu.section19.notification'].search_count([('state', '=', 'generated')])
            record.signed_section19 = self.env['bhu.section19.notification'].search_count([('state', '=', 'signed')])
            
            # SIA Teams
            record.total_sia_teams = self.env['bhu.sia.team'].search_count([])
            record.draft_sia_teams = self.env['bhu.sia.team'].search_count([('state', '=', 'draft')])
            record.submitted_sia_teams = self.env['bhu.sia.team'].search_count([('state', '=', 'submitted')])
            record.approved_sia_teams = self.env['bhu.sia.team'].search_count([('state', '=', 'approved')])
            record.send_back_sia_teams = self.env['bhu.sia.team'].search_count([('state', '=', 'send_back')])
            
            # Payment Files
            record.total_payment_files = self.env['bhu.payment.file'].search_count([])
            record.draft_payment_files = self.env['bhu.payment.file'].search_count([('state', '=', 'draft')])
            record.generated_payment_files = self.env['bhu.payment.file'].search_count([('state', '=', 'generated')])
            
            # Payment Reconciliations
            record.total_payment_reconciliations = self.env['bhu.payment.reconciliation.bank'].search_count([])
            record.draft_reconciliations = self.env['bhu.payment.reconciliation.bank'].search_count([('state', '=', 'draft')])
            record.processed_reconciliations = self.env['bhu.payment.reconciliation.bank'].search_count([('state', '=', 'processed')])
            record.completed_reconciliations = self.env['bhu.payment.reconciliation.bank'].search_count([('state', '=', 'completed')])
            
            # Document Vault
            record.total_documents = self.env['bhu.document.vault'].search_count([])
            
            # Active Mobile Users (mobile + legacy tokens without channel_type)
            mobile_tokens = self.env['jwt.token'].search([
                '|', ('channel_type', '=', 'mobile'), ('channel_type', '=', False),
            ])
            unique_mobile_users = len(set(mobile_tokens.mapped('user_id').ids))
            record.active_mobile_users = unique_mobile_users
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to compute and cache counts immediately"""
        counts = self._get_all_counts()
        allowed = set(self._fields)
        safe_counts = {k: v for k, v in counts.items() if k in allowed}

        for vals in vals_list:
            vals.update(safe_counts)

        records = super().create(vals_list)
        # Ensure computed fields are computed
        for record in records:
            record._compute_current_datetime()
            record._compute_is_admin()
        return records
    
    def read(self, fields=None, load='_classic_read'):
        """Override read to ensure values are computed if missing"""
        result = super().read(fields=fields, load=load)
        
        # If any record has zero values, refresh them
        for record_data in result:
            if record_data.get('total_districts', 0) == 0:
                # This record needs refreshing
                record = self.browse(record_data['id'])
                counts = self._get_all_counts()
                allowed = set(self._fields)
                record.write({k: v for k, v in counts.items() if k in allowed})
                # Re-read to get updated values
                result = super().read(fields=fields, load=load)
                break
        
        # Ensure computed fields are computed
        for record_data in result:
            record = self.browse(record_data['id'])
            record._compute_current_datetime()
            record._compute_is_admin()
        
        return result
    
    def action_refresh(self):
        """Refresh dashboard data"""
        counts = self._get_all_counts()
        allowed = set(self._fields)
        self.write({k: v for k, v in counts.items() if k in allowed})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dashboard Refreshed',
                'message': 'Dashboard data has been updated.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def name_get(self):
        """Return a name for the dashboard"""
        return [(record.id, 'Dashboard') for record in self]
    
    @api.model
    def action_open_dashboard(self):
        """Open dashboard - reuses existing record or creates new one with cached values"""
        # Try to find existing dashboard record (transient models persist until server restart)
        dashboard = self.search([], limit=1, order='create_date desc')
        
        if not dashboard:
            # Create new dashboard with pre-computed values
            dashboard = self.create({})
            # Ensure computed fields are computed
            dashboard._compute_current_datetime()
            dashboard._compute_is_admin()
            # Force recompute
            dashboard.invalidate_recordset(['current_datetime', 'is_admin'])
            dashboard._compute_current_datetime()
            dashboard._compute_is_admin()
        else:
            # Always refresh values to ensure they're up-to-date, but do it efficiently
            # Check if any key field is 0, which might indicate stale data
            needs_refresh = (
                dashboard.total_districts == 0 and 
                dashboard.total_surveys == 0 and 
                dashboard.total_section4_notifications == 0 and
                dashboard.total_payment_files == 0 and
                dashboard.total_rate_masters == 0
            )
            if needs_refresh:
                counts = self._get_all_counts()
                allowed = set(self._fields)
                dashboard.write({k: v for k, v in counts.items() if k in allowed})
        
        # Ensure values are always present (double-check)
        if dashboard.total_districts == 0 or dashboard.total_rate_masters == 0:
            counts = self._get_all_counts()
            allowed = set(self._fields)
            dashboard.write({k: v for k, v in counts.items() if k in allowed})
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard',
            'res_model': 'bhuarjan.dashboard',
            'view_mode': 'form',
            'res_id': dashboard.id,
            'target': 'current',
            'context': {'create': False, 'delete': False},
        }
