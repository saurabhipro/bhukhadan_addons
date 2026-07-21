# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class DashboardHelpers(models.AbstractModel):
    """Generic helper methods for dashboard counts"""
    _name = 'bhuarjan.dashboard.helpers'
    _description = 'Dashboard Helper Methods'

    @api.model
    def _get_model_count_by_status(self, model_name, base_domain, status=None, state_field='state'):
        """Generic method to get count by status for any model
        Args:
            model_name: Model name (e.g., 'bhu.survey')
            base_domain: Base domain to filter by
            status: Status value, list of statuses, or None for total count
                   (e.g., 'approved', ['approved', 'rejected'], or None)
            state_field: Field name for state (default: 'state')
        Returns:
            int: Count of records matching the domain and status
        """
        if not base_domain:
            base_domain = []
        
        if status is None:
            # Return total count without status filter
            return self.env[model_name].search_count(base_domain)
        
        if isinstance(status, list):
            status_domain = [(state_field, 'in', status)]
        else:
            status_domain = [(state_field, '=', status)]
        
        return self.env[model_name].search_count(base_domain + status_domain)
    
    @api.model
    def _get_section_counts(self, model_name, base_domain, state_field='state', states=None):
        """Generic method to get all state counts for a section
        Args:
            model_name: Model name (e.g., 'bhu.section4.notification')
            base_domain: Base domain to filter by
            state_field: Field name for state (default: 'state')
            states: List of states to count (default: ['draft', 'submitted', 'approved', 'send_back'])
        Returns:
            dict: Dictionary with total and counts for each state
        """
        if states is None:
            states = ['draft', 'submitted', 'approved', 'send_back']
        
        if not base_domain:
            base_domain = []
        
        total = self.env[model_name].search_count(base_domain)
        counts = {}
        for state in states:
            counts[f'{state}'] = self._get_model_count_by_status(model_name, base_domain, state, state_field)
        
        return {
            'total': total,
            **counts
        }

    @api.model
    def _award_domain_from_voucher_domain(self, base_domain):
        """Map voucher dashboard domain to Section 23 award domain (one voucher per award)."""
        award_domain = []
        for term in base_domain or []:
            if isinstance(term, (list, tuple)) and len(term) >= 3 and term[0] in (
                'project_id', 'village_id', 'department_id',
            ):
                award_domain.append(term)
        return award_domain

    @api.model
    def _get_payment_voucher_counts(self, base_domain):
        """Payment voucher exists or not — no approval workflow on the voucher itself."""
        if not base_domain:
            base_domain = []
        Award = self.env['bhu.section23.award']
        Voucher = self.env['bhu.payment.voucher']
        awards = Award.search(self._award_domain_from_voucher_domain(base_domain))
        vouchers = Voucher.search(base_domain + ([('award_id', 'in', awards.ids)] if awards else []))
        generated = len(vouchers)
        not_created = max(0, len(awards) - generated)
        return {
            'total': generated,
            'draft': not_created,
            'generated': generated,
            'pending_award': not_created,
            'award_total': len(awards),
        }

    @api.model
    def _payment_file_amount_summary(self, base_domain):
        """Compare total payment file amount vs total voucher payable (no approval workflow)."""
        if not base_domain:
            base_domain = []
        Voucher = self.env['bhu.payment.voucher']
        Export = self.env['bhu.payment.voucher.export']
        vouchers = Voucher.search(base_domain)
        voucher_amount = sum(float(v.total_determined or 0.0) for v in vouchers)
        exports = Export.search([('voucher_id', 'in', vouchers.ids)]) if vouchers else Export.browse()
        file_amount = sum(float(e.amount or 0.0) for e in exports)
        pending_amount = max(0.0, voucher_amount - file_amount)
        epsilon = 0.01
        is_complete = voucher_amount > epsilon and pending_amount <= epsilon
        completion_percent = 0.0
        if voucher_amount > epsilon:
            completion_percent = min(100.0, round(100.0 * file_amount / voucher_amount, 1))
        return {
            'voucher_amount': voucher_amount,
            'file_amount': file_amount,
            'pending_amount': pending_amount,
            'file_count': len(exports),
            'is_complete': is_complete,
            'has_voucher': bool(vouchers),
            'completion_percent': completion_percent,
        }

    @api.model
    def _get_payment_file_counts(self, base_domain):
        """Payment files — complete when filed amount equals voucher payable total."""
        summary = self._payment_file_amount_summary(base_domain)
        pending_flag = 1 if summary['has_voucher'] and not summary['is_complete'] else 0
        return {
            'total': summary['file_count'],
            'draft': pending_flag,
            'generated': 1 if summary['is_complete'] else 0,
            'voucher_amount': summary['voucher_amount'],
            'file_amount': summary['file_amount'],
            'pending_amount': summary['pending_amount'],
            'is_complete': summary['is_complete'],
            'completion_percent': summary['completion_percent'],
        }

    @api.model
    def _get_payment_voucher_info(self, domain):
        """Section info — voucher is generated or not (no approval step)."""
        Award = self.env['bhu.section23.award']
        Voucher = self.env['bhu.payment.voucher']
        awards = Award.search(self._award_domain_from_voucher_domain(domain), order='create_date asc')
        vouchers = Voucher.search(domain, order='create_date asc')
        by_award = {v.award_id.id: v for v in vouchers}
        awards_without_voucher = awards.filtered(lambda a: a.id not in by_award)
        first_document = vouchers[:1]
        first_award_without_voucher = awards_without_voucher[:1]
        all_generated = bool(awards) and len(vouchers) >= len(awards)
        return {
            'total': len(vouchers),
            'draft_count': len(awards_without_voucher),
            'submitted_count': 0,
            'approved_count': len(vouchers),
            'rejected_count': 0,
            'send_back_count': 0,
            'all_approved': all_generated,
            'is_completed': all_generated,
            'first_pending_id': False,
            'first_document_id': first_document.id if first_document else False,
            'first_award_id': first_award_without_voucher.id if first_award_without_voucher else False,
            'has_voucher': bool(vouchers),
        }

    @api.model
    def _get_payment_file_info(self, domain):
        """Section info — complete when payment file total amount = voucher total."""
        summary = self._payment_file_amount_summary(domain)
        Export = self.env['bhu.payment.voucher.export']
        Voucher = self.env['bhu.payment.voucher']
        exports = Export.search(domain, order='create_date asc')
        vouchers = Voucher.search(domain, order='create_date asc')
        first_document = exports[:1]
        first_voucher = vouchers[:1]
        return {
            'total': summary['file_count'],
            'draft_count': 1 if summary['has_voucher'] and not summary['is_complete'] else 0,
            'submitted_count': 0,
            'approved_count': 1 if summary['is_complete'] else 0,
            'rejected_count': 0,
            'send_back_count': 0,
            'all_approved': summary['is_complete'],
            'is_completed': summary['is_complete'],
            'first_pending_id': first_voucher.id if summary['has_voucher'] and not summary['is_complete'] else False,
            'first_document_id': first_document.id if first_document else False,
            'voucher_amount': summary['voucher_amount'],
            'file_amount': summary['file_amount'],
            'pending_amount': summary['pending_amount'],
        }

    @api.model
    def _get_simple_section_counts(self, model_name, base_domain):
        """Simple count method for sections without workflow states
        Args:
            model_name: Model name (e.g., 'bhu.section4.notification')
            base_domain: Base domain to filter by
        Returns:
            dict: Dictionary with total count only (no state breakdown)
        """
        if not base_domain:
            base_domain = []
        
        total = self.env[model_name].search_count(base_domain)
        
        return {
            'total': total,
            'draft': 0,
            'submitted': 0,
            'approved': 0,
            'send_back': 0,
        }
    
    @api.model
    def _get_survey_counts(self, base_domain):
        """Get all survey counts with completion percentage
        Args:
            base_domain: Base domain to filter surveys (can be empty list for all)
        Returns:
            dict: Dictionary with all survey counts and completion percentage
        """
        if not base_domain:
            base_domain = []
        
        total = self._get_model_count_by_status('bhu.survey', base_domain, None)
        draft = self._get_model_count_by_status('bhu.survey', base_domain, 'draft')
        submitted = self._get_model_count_by_status('bhu.survey', base_domain, 'submitted')
        approved = self._get_model_count_by_status('bhu.survey', base_domain, 'approved')
        rejected = self._get_model_count_by_status('bhu.survey', base_domain, 'rejected')
        total_done = self._get_model_count_by_status('bhu.survey', base_domain, ['approved', 'rejected'])
        pending = self._get_model_count_by_status('bhu.survey', base_domain, ['submitted', 'rejected'])
        
        # Calculate completion percentage
        # For surveys: completion = (approved + rejected) / total
        # If all are approved or rejected, it's 100%
        completion_percent = 0
        if total > 0:
            completion_percent = round(((approved + rejected) / total) * 100, 1)
            # Ensure it's between 0 and 100
            completion_percent = max(0.0, min(100.0, completion_percent))
        
        return {
            'total': total,
            'draft': draft,
            'submitted': submitted,
            'approved': approved,
            'rejected': rejected,
            'total_done': total_done,
            'pending': pending,
            'completion_percent': completion_percent,
        }

