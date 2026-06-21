# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class DashboardCounts(models.AbstractModel):
    """Dashboard count calculation methods"""
    _name = 'bhuarjan.dashboard.counts'
    _description = 'Dashboard Count Methods'

    @api.model
    def _get_all_counts(self, project_id=None, village_id=None, department_id=None):
        """Get all counts - cached computation"""
        # Build domain filters
        project_domain = [('project_id', '=', project_id)] if project_id else []
        village_domain = []
        
        # Handle village filtering - simplified logic
        if village_id:
            # Village is selected - always filter by village
            # If project is also selected, the domain will combine both (AND condition)
            village_domain = [('village_id', '=', village_id)]
        elif project_id:
            # Project selected but no village - show ALL surveys for this project
            # Don't restrict to project.village_ids because some villages might have surveys
            # but not be in the Many2many relationship (like Jurda)
            # Just filter by project_id - the surveys will naturally be for villages in that project
            village_domain = []  # No village filter - show all villages with surveys in this project
        
        # If department is selected but no project, filter projects by department
        if department_id and not project_id:
            department_projects = self.env['bhu.project'].search([('department_id', '=', department_id)])
            if department_projects:
                project_ids = department_projects.ids
                project_domain = [('project_id', 'in', project_ids)]
            else:
                # No projects for this department, return zeros for project-related counts
                project_domain = [('project_id', '=', False)]  # This will return 0 results
        
        # Base domains for sections - combine project and village filters
        # Note: expert_committee_report and sia_team don't have village_id field, so exclude village_domain for them
        has_filters = (project_id or village_id or department_id)
        section4_base = project_domain + village_domain if has_filters else []
        section11_base = project_domain + village_domain if has_filters else []
        section19_base = project_domain + village_domain if has_filters else []
        section15_base = project_domain + village_domain if has_filters else []
        # Expert and SIA don't have village_id - only use project_domain
        expert_base = project_domain if (project_id or department_id) else []
        sia_base = project_domain if (project_id or department_id) else []
        payment_base = project_domain + village_domain if has_filters else []
        reconciliation_base = project_domain + village_domain if has_filters else []

        # Survey domain - combine project and village filters properly
        survey_base = []
        if project_id or village_id or department_id:
            if project_domain and village_domain:
                survey_base = project_domain + village_domain
            elif project_domain:
                survey_base = project_domain
            elif village_domain:
                survey_base = village_domain
            else:
                survey_base = project_domain

        # Section workflows use different state sets — align with dashboard_base._compute_all_counts
        section4_counts = self._get_section_counts(
            'bhu.section4.notification', section4_base, states=['draft', 'generated', 'signed']
        )
        section11_counts = self._get_section_counts(
            'bhu.section11.preliminary.report', section11_base, states=['draft', 'generated', 'signed']
        )
        section19_counts = self._get_section_counts(
            'bhu.section19.notification', section19_base, states=['draft', 'generated', 'signed']
        )
        sia_counts = self._get_section_counts(
            'bhu.sia.team', sia_base, states=['draft', 'submitted', 'approved', 'send_back']
        )
        survey_counts = self._get_survey_counts(survey_base)

        return {
            # Master data (always global — matches legacy dashboard KPIs)
            'total_districts': self.env['bhu.district'].search_count([]),
            'total_sub_divisions': self.env['bhu.sub.division'].search_count([]),
            'total_tehsils': self.env['bhu.tehsil'].search_count([]),
            'total_villages': self.env['bhu.village'].search_count([]),
            'total_projects': self.env['bhu.project'].search_count([]),
            'total_departments': self.env['bhu.department'].search_count([]),
            'total_landowners': self.env['bhu.landowner'].search_count([]),
            'total_rate_masters': self.env['bhu.rate.master'].search_count([]),

            # Surveys (filtered when project/village/department scope applies)
            'total_surveys': survey_counts['total'],
            'draft_surveys': survey_counts['draft'],
            'submitted_surveys': survey_counts['submitted'],
            'approved_surveys': survey_counts['approved'],
            'rejected_surveys': survey_counts['rejected'],
            'total_surveys_done': survey_counts['total_done'],
            'pending_surveys': survey_counts['pending'],

            # Sections — field names must match bhuarjan.dashboard (dashboard_base.py)
            'total_section4_notifications': section4_counts['total'],
            'draft_section4': section4_counts['draft'],
            'generated_section4': section4_counts['generated'],
            'signed_section4': section4_counts['signed'],

            'total_section11_reports': section11_counts['total'],
            'draft_section11': section11_counts['draft'],
            'generated_section11': section11_counts['generated'],
            'signed_section11': section11_counts['signed'],

            'total_expert_committee_reports': self.env['bhu.expert.committee.report'].search_count(expert_base),

            'total_section15_objections': self.env['bhu.section15.objection'].search_count(section15_base),

            'total_section19_notifications': section19_counts['total'],
            'draft_section19': section19_counts['draft'],
            'generated_section19': section19_counts['generated'],
            'signed_section19': section19_counts['signed'],

            'total_sia_teams': sia_counts['total'],
            'draft_sia_teams': sia_counts['draft'],
            'submitted_sia_teams': sia_counts['submitted'],
            'approved_sia_teams': sia_counts['approved'],
            'send_back_sia_teams': sia_counts['send_back'],

            'total_payment_files': self.env['bhu.payment.file'].search_count(payment_base),
            'draft_payment_files': self.env['bhu.payment.file'].search_count(
                payment_base + [('state', '=', 'draft')]
            ),
            'generated_payment_files': self.env['bhu.payment.file'].search_count(
                payment_base + [('state', '=', 'generated')]
            ),

            'total_payment_reconciliations': self.env['bhu.payment.reconciliation.bank'].search_count(
                reconciliation_base
            ),
            'draft_reconciliations': self.env['bhu.payment.reconciliation.bank'].search_count(
                reconciliation_base + [('state', '=', 'draft')]
            ),
            'processed_reconciliations': self.env['bhu.payment.reconciliation.bank'].search_count(
                reconciliation_base + [('state', '=', 'processed')]
            ),
            'completed_reconciliations': self.env['bhu.payment.reconciliation.bank'].search_count(
                reconciliation_base + [('state', '=', 'completed')]
            ),

            'total_documents': self.env['bhu.document.vault'].search_count([]),

            'active_mobile_users': len(set(self.env['jwt.token'].search([
                '|', ('channel_type', '=', 'mobile'), ('channel_type', '=', False),
            ]).mapped('user_id').ids)),
        }

