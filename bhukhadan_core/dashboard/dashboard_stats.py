# -*- coding: utf-8 -*-

import logging
import re
from collections import defaultdict
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


def _management_parse_project_cost(val):
    """Best-effort INR scale from free-text project total cost (same spirit as group dashboard JS)."""
    if not val:
        return 0.0
    s = str(val).lower().replace(',', '')
    mult = 1.0
    if 'lakh' in s:
        mult = 100000.0
    if 'crore' in s or re.search(r'\bcr\b', s):
        mult = 10000000.0
    nums = re.findall(r'[\d.]+', s)
    if not nums:
        return 0.0
    try:
        return float(nums[0]) * mult
    except (TypeError, ValueError):
        return 0.0


def _completion_pct_from_pipeline_dots(dots):
    """Share of ``done`` dots among applicable (non-``na``) pipeline dots."""
    if not dots:
        return 0.0
    applicable = [d for d in dots if d.get('kind') != 'na']
    if not applicable:
        return 0.0
    done = sum(1 for d in applicable if d.get('kind') == 'done')
    return round(100.0 * done / len(applicable), 1)


_PIPELINE_STAGE_ORDER = (
    'survey', 'section4', 'sia_team',
    'section8', 'section9', 'section11', 'section15', 'section19', 'section21', 'section23',
    'payment_voucher', 'payment_file',
)

_PIPELINE_STAGE_LABELS = {
    'survey': 'Form 10',
    'section4': 'Sec 4(i)',
    'sia_team': 'Sec 7(i)',
    'section8': 'Sec 8',
    'section9': 'Sec 9(i)',
    'section11': 'Sec 11(i)',
    'section15': 'Post-1',
    'section19': 'Post-2',
    'section21': 'Post-3',
    'section23': 'Post-5/6',
    'payment_voucher': 'Pay Voucher',
    'payment_file': 'Pay File',
}


def _subdiv_portfolio_summary(projects):
    """Aggregate KPIs for one sub-division block on the pipeline dashboard."""
    tehsils = set()
    dept_ids = set()
    village_total = 0
    survey_total = 0
    pct_sum = 0.0
    best_stage_idx = -1

    for pr in projects or []:
        village_total += int(pr.get('village_count') or 0)
        survey_total += int(pr.get('survey_count') or 0) or sum(
            int(v.get('survey_count') or 0) for v in (pr.get('villages') or [])
        )
        pct_sum += float(pr.get('pipeline_pct') or 0)
        dept_id = pr.get('department_id')
        if dept_id:
            dept_ids.add(dept_id)
        tehsil_str = (pr.get('tehsil') or '').strip()
        for part in tehsil_str.split(','):
            name = part.strip()
            if name:
                tehsils.add(name)
        dots = pr.get('dots') or []
        for idx, sid in enumerate(_PIPELINE_STAGE_ORDER):
            kind = next((d.get('kind') for d in dots if d.get('id') == sid), None)
            if kind in ('done', 'active'):
                best_stage_idx = max(best_stage_idx, idx)

    project_count = len(projects or [])
    latest = (
        _PIPELINE_STAGE_LABELS.get(_PIPELINE_STAGE_ORDER[best_stage_idx], '—')
        if best_stage_idx >= 0
        else '—'
    )
    return {
        'project_count': project_count,
        'village_count': village_total,
        'tehsil_count': len(tehsils),
        'department_count': len(dept_ids),
        'survey_count': survey_total,
        'latest_section': latest,
        'avg_pipeline_pct': round(pct_sum / project_count, 1) if project_count else 0.0,
    }


class DashboardStats(models.AbstractModel):
    """Unified Dashboard Statistics - Handles all dashboard types (SDM, Collector, Admin, Department, etc.)"""
    _name = 'bhuarjan.dashboard.stats'
    _description = 'Dashboard Statistics Methods'

    # ========== CONFIGURATION: Dashboard Type Settings ==========
    # 
    # This configuration determines how different user roles access dashboard data.
    # Modify these groups to change which users can see all projects vs filtered projects.
    #
    # CONFIGURATION GUIDE:
    # 1. can_see_all_projects: Users in these groups can see ALL projects (no filtering)
    #    - Typically: Admin, System, Collector roles
    # 2. sdm_groups: Users in these groups see only their assigned projects (via sdm_ids)
    #    - Typically: SDM (Sub-Divisional Magistrate) role
    # 3. tehsildar_groups: Users in these groups see projects assigned via sdm_ids OR tehsildar_ids
    #    - Add tehsildar-specific groups here if needed
    # 4. department_groups: Users in these groups see projects based on their department
    #    - Typically: Department User role
    #
    # To add a new dashboard type:
    # 1. Add the user group to the appropriate list above
    # 2. Update _get_user_project_access() method if custom logic is needed
    # 3. The get_dashboard_stats() method will automatically handle the new type
    #
    DASHBOARD_CONFIG = {
        'can_see_all_projects': [
            'bhukhadan_core.group_bhuarjan_admin',           # Admin users
            'base.group_system',                        # System users
            'bhukhadan_core.group_bhuarjan_collector',       # Collector users
            'bhukhadan_core.group_bhuarjan_additional_collector',  # Additional Collector users
            'bhukhadan_core.group_bhuarjan_district_administrator',  # District Administrator users
            'bhukhadan_core.group_coal_hq_reviewer',
            'bhukhadan_core.group_coal_moc_liaison',
        ],
        'sdm_groups': [
            'bhukhadan_core.group_bhuarjan_sdm',             # SDM users
            'bhukhadan_core.group_coal_area_officer',
            'bhukhadan_core.group_coal_section9_officer',
        ],
        'tehsildar_groups': [
            'bhukhadan_core.group_bhuarjan_tahsildar',
        ],
        'department_groups': [
            'bhukhadan_core.group_bhuarjan_department_user',  # Department users
            'bhukhadan_core.group_coal_asc_member',
            'bhukhadan_core.group_coal_drrc_member',
        ],
    }

    # Models that have village_id field (for filtering)
    MODELS_WITH_VILLAGE = [
        'bhu.survey',
        'bhu.section4.notification',
        'bhu.section11.preliminary.report',
        'bhu.section15.objection',
        'bhu.section19.notification',
        'bhu.section9.notification',
        'bhu.section21.notification',
        'bhu.payment.file',
        'bhu.payment.voucher',
        'bhu.payment.voucher.export',
        'bhu.payment.reconciliation.bank',
    ]

    # Models that don't have village_id field (only project filtering)
    MODELS_WITHOUT_VILLAGE = [
        'bhu.expert.committee.report',
        'bhu.sia.team',
    ]

    # ========== Helper Methods ==========

    @api.model
    def _get_sdm_project_ids(self, user=None):
        """Project IDs an SDM may access (matches SDM pipeline dashboard rules).

        Union of:
        - projects with this user in ``sdm_ids``;
        - all projects on sub divisions where ``bhu.sub.division.user_id`` is this SDM.
        """
        user = user or self.env.user
        Project = self.env['bhu.project']
        sdm_assigned = Project.search([('sdm_ids', 'in', [user.id])])
        project_ids = set(sdm_assigned.ids)
        owned_subdivs = self.env['bhu.sub.division'].search([('user_id', '=', user.id)])
        if owned_subdivs:
            owned_projects = Project.search([
                ('sub_division_id', 'in', owned_subdivs.ids),
            ])
            project_ids.update(owned_projects.ids)
        return list(project_ids)

    @api.model
    def _get_user_project_access(self):
        """Determine what projects the current user can access based on their role
        
        Returns:
            dict: {
                'can_see_all': bool,  # True if user can see all projects
                'project_ids': list,   # List of project IDs user can access (None if can_see_all)
                'user_type': str,     # 'admin', 'collector', 'sdm', 'tehsildar', 'department', 'other'
            }
        """
        user = self.env.user
        config = self.DASHBOARD_CONFIG
        
        # Check if user can see all projects
        can_see_all = any(user.has_group(group) for group in config['can_see_all_projects'])
        
        if can_see_all:
            # Determine user type in priority order
            if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
                user_type = 'admin'
            elif user.has_group('bhukhadan_core.group_bhuarjan_department_user'):
                user_type = 'department'
            elif user.has_group('bhukhadan_core.group_bhuarjan_district_administrator'):
                user_type = 'district_admin'
            else:
                user_type = 'collector'
            
            return {
                'can_see_all': True,
                'project_ids': None,
                'user_type': user_type,
            }
        
        # Check if user is SDM
        if any(user.has_group(group) for group in config['sdm_groups']):
            return {
                'can_see_all': False,
                'project_ids': self._get_sdm_project_ids(user),
                'user_type': 'sdm',
            }
        
        # Check if user is Tehsildar or has assigned projects
        assigned_projects = self.env['bhu.project'].search([
            '|', '|',
            ('sdm_ids', 'in', [user.id]),
            ('tehsildar_ids', 'in', [user.id]),
            ('sub_division_id.user_id', 'in', [user.id]),
        ])
        
        if assigned_projects:
            return {
                'can_see_all': False,
                'project_ids': assigned_projects.ids,
                'user_type': 'tehsildar',
            }
        
        # Department user
        if any(user.has_group(group) for group in config['department_groups']):
            assigned_projects = self.env['bhu.project'].search([
                ('department_user_ids', 'in', [user.id]),
            ])
            return {
                'can_see_all': False,
                'project_ids': assigned_projects.ids,
                'user_type': 'department',
            }
        
        return {
            'can_see_all': False,
            'project_ids': [],
            'user_type': 'other',
        }

    @api.model
    def _build_filter_domains(self, department_id=None, project_id=None, village_id=None):
        """Build filter domains based on user access and provided filters
        
        Args:
            department_id: Optional department ID to filter by
            project_id: Optional project ID to filter by
            village_id: Optional village ID to filter by
            
        Returns:
            dict: {
                'project_domain': list,      # Domain for project filtering
                'village_domain': list,      # Domain for village filtering
                'final_domain': list,        # Combined domain for models with village_id
                'domain_without_village': list,  # Domain for models without village_id
                'project_ids_from_domain': list,  # List of project IDs for completion calculations
            }
        """
        user_access = self._get_user_project_access()
        project_domain = []
        village_domain = []
        
        # Build project domain based on user access
        if user_access['can_see_all']:
            # Admin/Collector: can filter by department/project, but no restriction
            if project_id:
                # If project is explicitly selected, always filter by it (even if village is also selected)
                project_domain = [('project_id', '=', project_id)]
            elif department_id:
                # Filter by department if no specific project selected
                dept_projects = self.env['bhu.project'].search([('department_id', '=', department_id)])
                project_domain = [('project_id', 'in', dept_projects.ids)] if dept_projects else [('project_id', '=', False)]
            # else: no project domain filter (show all)
        else:
            # User has project restrictions
            project_ids = user_access['project_ids'] or []
            
            if project_ids:
                # User has assigned projects
                if department_id and not project_id:
                    # Filter by department within assigned projects
                    dept_projects = self.env['bhu.project'].search([
                        ('department_id', '=', department_id),
                        ('id', 'in', project_ids)
                    ])
                    project_domain = [('project_id', 'in', dept_projects.ids)] if dept_projects else [('project_id', '=', False)]
                elif project_id:
                    # Filter by specific project if user has access
                    project_domain = [('project_id', '=', project_id)] if project_id in project_ids else [('project_id', '=', False)]
                else:
                    # Filter by all assigned projects
                    project_domain = [('project_id', 'in', project_ids)]
            else:
                # No assigned projects
                project_domain = [('project_id', '=', False)]
        
        # Build village domain
        if village_id:
            village_domain = [('village_id', '=', village_id)]
        
        # Combine domains - IMPORTANT: Always combine project and village if both exist
        # CRITICAL: When village is selected, we MUST preserve project filter if project was selected
        # This ensures that when user selects a project, then selects a village, both filters apply
        
        # Log domain combination for debugging
        _logger.info(f"Domain Building - project_id={project_id}, village_id={village_id}, project_domain={project_domain}, village_domain={village_domain}")
        
        if project_domain and village_domain:
            # Both project and village filters - combine with AND (this is the expected case)
            final_domain = project_domain + village_domain
            _logger.info(f"Domain Building - Combined both: {final_domain}")
        elif project_domain:
            # Only project filter (no village selected)
            final_domain = project_domain
            _logger.info(f"Domain Building - Project only: {final_domain}")
        elif village_domain:
            # Only village filter (no project selected) - this should still work
            final_domain = village_domain
            _logger.info(f"Domain Building - Village only: {final_domain}")
        else:
            # No filters
            final_domain = []
            _logger.info(f"Domain Building - No filters")
        
        # Domain for models without village_id (only project filter, no village)
        # Ensure we use empty list if project_domain is empty or falsy
        domain_without_village = project_domain if project_domain else []
        _logger.info(f"Domain Building - domain_without_village for Section 8: {domain_without_village}")
        
        # Domain for models with village_ids M2M (Expert, SIA)
        # These models handle multiple villages, so we need to check if the filtered village is IN the record's villages
        m2m_village_domain = list(domain_without_village)  # Start with project filter
        if village_domain:
            # Extract village_id from domain [('village_id', '=', ID)]
            v_id = None
            for item in village_domain:
                if isinstance(item, (list, tuple)) and item[0] == 'village_id' and item[1] == '=':
                    v_id = item[2]
                    break
            
            if v_id:
                # Add M2M check for village
                m2m_village_domain.append(('village_ids', 'in', [v_id]))
        
        _logger.info(f"Domain Building - m2m_village_domain for Expert/SIA: {m2m_village_domain}")

        # Extract project IDs for completion calculations
        project_ids_from_domain = self._extract_project_ids(project_id, project_domain, department_id, user_access)
        
        return {
            'project_domain': project_domain,
            'village_domain': village_domain,
            'final_domain': final_domain,
            'domain_without_village': domain_without_village,
            'm2m_village_domain': m2m_village_domain,
            'project_ids_from_domain': project_ids_from_domain,
        }

    @api.model
    def _extract_project_ids(self, project_id, project_domain, department_id, user_access):
        """Extract project IDs from filters for completion calculations"""
        project_ids_from_domain = []
        
        if project_id:
            project_ids_from_domain = [project_id]
        elif project_domain:
            # Extract from domain like [('project_id', 'in', [1, 2, 3])] or [('project_id', '=', 1)]
            for condition in project_domain:
                if isinstance(condition, (list, tuple)) and len(condition) >= 3:
                    field, operator, value = condition[0], condition[1], condition[2]
                    if field == 'project_id':
                        if operator == '=':
                            project_ids_from_domain = [value] if value else []
                        elif operator == 'in' and isinstance(value, list):
                            project_ids_from_domain = value
                        break
        
        if not project_ids_from_domain:
            if department_id:
                dept_projects = self.env['bhu.project'].search([('department_id', '=', department_id)])
                project_ids_from_domain = dept_projects.ids
            else:
                if user_access['project_ids'] is not None and user_access['project_ids']:
                    project_ids_from_domain = user_access['project_ids']
                else:
                    all_projects = self.env['bhu.project'].search([])
                    project_ids_from_domain = all_projects.ids
        
        return project_ids_from_domain

    @api.model
    def _get_section_info(self, model_name, domain, state_field='state', is_survey=False, pending_state='submitted'):
        """Get detailed section information including first pending document
        
        Args:
            model_name: Model name (e.g., 'bhu.survey')
            domain: Domain to filter records
            state_field: Field name for state (default: 'state')
            is_survey: Whether this is a survey (different completion logic)
            pending_state: State to consider as pending (default: 'submitted')
            
        Returns:
            dict: Section information with counts and status
        """
        records = self.env[model_name].search(domain, order='create_date asc')
        total = len(records)
        
        submitted = records.filtered(lambda r: getattr(r, state_field, False) == 'submitted')
        approved = records.filtered(lambda r: getattr(r, state_field, False) == 'approved')
        rejected = records.filtered(lambda r: getattr(r, state_field, False) == 'rejected')
        send_back = records.filtered(lambda r: getattr(r, state_field, False) == 'send_back')
        draft = records.filtered(lambda r: getattr(r, state_field, False) == 'draft')
        
        all_approved = total > 0 and len(approved) == total
        
        # Completion logic: surveys need approved OR rejected, others need all approved
        if is_survey:
            is_completed = total > 0 and len(submitted) == 0 and len(draft) == 0 and (len(approved) + len(rejected) == total)
        else:
            is_completed = all_approved
        
        # Pick first pending based on pending_state
        if pending_state == 'submitted':
            first_pending = submitted[0] if submitted else False
        elif pending_state == 'draft':
            # For CGLRC 247, draft records are considered pending SDM approval
            first_pending = draft[0] if draft else False
        else:
            first_pending = submitted[0] if submitted else False

        first_document = records[0] if records else False
        
        return {
            'total': total,
            'draft_count': len(draft),
            'submitted_count': len(submitted),
            'approved_count': len(approved),
            'rejected_count': len(rejected),
            'send_back_count': len(send_back),
            'all_approved': all_approved,
            'is_completed': is_completed,
            'first_pending_id': first_pending.id if first_pending else False,
            'first_document_id': first_document.id if first_document else False,
        }

    @api.model
    def _calculate_completion_percentage(self, approved, rejected, total, is_survey=False):
        """Calculate completion percentage
        
        Args:
            approved: Number of approved items
            rejected: Number of rejected items
            total: Total number of items
            is_survey: Whether this is a survey (different calculation)
            
        Returns:
            float: Completion percentage (0-100)
        """
        if total == 0:
            return 0.0
        
        if is_survey:
            # For surveys: completion = (approved + rejected) / total
            # If all are approved or rejected, it's 100%
            completion = ((approved + rejected) / total) * 100
        else:
            # For other sections: completion = approved / total
            # If all are approved, it's 100%
            completion = (approved / total) * 100
        
        # Ensure it's between 0 and 100, and round to 1 decimal place
        completion = max(0.0, min(100.0, completion))
        return round(completion, 1)

    @api.model
    def _calculate_village_based_completion(self, model_name, project_ids_list, total_villages, state_field='state', approved_state='approved'):
        """Calculate completion based on villages with approved notifications vs total villages
        
        Args:
            model_name: Model name to check
            project_ids_list: List of project IDs
            total_villages: Total number of villages in projects
            state_field: Field name for state
            approved_state: State value for approved
            
        Returns:
            float: Completion percentage
        """
        if not project_ids_list or total_villages == 0:
            return 0.0
        
        approved_notifications = self.env[model_name].search([
            ('project_id', 'in', project_ids_list),
            (state_field, '=', approved_state)
        ])
        
        villages_with_approved = set(approved_notifications.mapped('village_id').ids)
        
        return round((len(villages_with_approved) / total_villages) * 100, 1) if total_villages > 0 else 0.0

    @api.model
    def _get_total_villages(self, project_ids_list):
        """Get total unique villages across projects"""
        if not project_ids_list:
            return 0
        
        projects = self.env['bhu.project'].browse(project_ids_list)
        all_village_ids = []
        for project in projects:
            all_village_ids.extend(project.village_ids.ids)
        
        return len(set(all_village_ids))

    @api.model
    def _get_all_section_counts(self, domains):
        """Get counts for all sections using generic methods
        
        Args:
            domains: dict with 'with_village' and 'without_village' domains
            
        Returns:
            dict: All section counts
        """
        domain_with_village = domains['final_domain']
        domain_without_village = domains['domain_without_village']
        m2m_village_domain = domains.get('m2m_village_domain', domain_without_village)  # Fallback just in case
        
        # Get counts using generic methods
        # Get counts using generic methods
        # Include 'generated' and 'signed' states for all workflow sections
        workflow_states = ['draft', 'submitted', 'approved', 'send_back', 'generated', 'signed']
        
        counts = {
            'survey': self._get_survey_counts(domain_with_village),
            'section4': self._get_section_counts('bhu.section4.notification', domain_with_village, states=workflow_states),
            'section11': self._get_section_counts('bhu.section11.preliminary.report', domain_with_village, states=workflow_states),
            'section15': self._get_section_counts('bhu.section15.objection', domain_with_village, states=workflow_states),
            'section19': self._get_section_counts('bhu.section19.notification', domain_with_village, states=workflow_states),
            'expert': self._get_section_counts('bhu.expert.committee.report', domain_without_village, states=workflow_states),
            'sia': self._get_section_counts('bhu.sia.team', domain_without_village, states=workflow_states),
            'section8': self._get_section_counts('bhu.section8', domain_without_village, state_field='state', states=['draft', 'approved', 'rejected']),  # Section 8 is per project, not per village
            'section9': self._get_section_counts('bhu.section9.notification', domain_with_village, states=workflow_states),
            # Railway Act Sections (all have village_id)
            # Sections 20A and 20E have no workflow - simple count only
            'section20a_railways': self._get_simple_section_counts('bhu.section20a.railways', domain_with_village),
            'section20d_railways': self._get_section_counts('bhu.section20d.railways', domain_with_village, states=workflow_states),
            'section20e_railways': self._get_simple_section_counts('bhu.section20e.railways', domain_with_village),
            # National Highway Act Sections (all have village_id)
            # Sections 3A and 3D have no workflow - simple count only
            'section3a_nh': self._get_simple_section_counts('bhu.section3a.nh', domain_with_village),
            'section3c_nh': self._get_section_counts('bhu.section3c.nh', domain_with_village, states=workflow_states),
            'section3d_nh': self._get_simple_section_counts('bhu.section3d.nh', domain_with_village),
            # Section 23 Award (has village_id)
            'section23_award': self._get_section_counts('bhu.section23.award', domain_with_village, states=workflow_states),
            # Payment Voucher + Payment File (generated bank exports)
            'payment_voucher': self._get_payment_voucher_counts(domain_with_village),
            'payment_file': self._get_payment_file_counts(domain_with_village),
            # Payment Reconciliation (has village_id)
            'reconciliation': self._get_section_counts('bhu.payment.reconciliation.bank', domain_with_village, states=['draft', 'processed', 'completed']),
            # CGLRC Section 247 Sections
            'section247_1_cglrc': self._get_section_counts('bhu.section247_1.cglrc', domain_with_village, states=workflow_states),
            'section247_2_cglrc': self._get_section_counts('bhu.section247_2.cglrc', domain_with_village, states=workflow_states),
            'section247_3_cglrc': self._get_section_counts('bhu.section247_3.cglrc', domain_with_village, states=workflow_states),
        }
        
        # Section 21 Notification uses standard workflow states (draft, submitted, approved, send_back)
        section21_total = self._get_model_count_by_status('bhu.section21.notification', domain_with_village, None)
        _logger.info(f"Section 21 counts - domain: {domain_with_village}, total: {section21_total}")
        counts['draft_award'] = {
            'total': section21_total,
            'approved': self._get_model_count_by_status('bhu.section21.notification', domain_with_village, 'approved'),
            'draft': self._get_model_count_by_status('bhu.section21.notification', domain_with_village, 'draft'),
            'submitted': self._get_model_count_by_status('bhu.section21.notification', domain_with_village, 'submitted'),
            'send_back': self._get_model_count_by_status('bhu.section21.notification', domain_with_village, 'send_back'),
        }
        
        # Log Section 23 Award counts
        section23_total = counts['section23_award']['total']
        _logger.info(f"Section 23 Award counts - domain: {domain_with_village}, total: {section23_total}")
        
        return counts

    # ========== Public API Methods ==========

    @api.model
    def is_collector_user(self):
        """Check if current user is Collector"""
        user = self.env.user
        return (user.has_group('bhukhadan_core.group_bhuarjan_collector') or
                user.has_group('bhukhadan_core.group_bhuarjan_additional_collector') or
                user.has_group('bhukhadan_core.group_bhuarjan_admin') or
                user.has_group('base.group_system'))

    @api.model
    def is_sdm_user(self):
        """Check if current user is SDM"""
        user = self.env.user
        return (user.has_group('bhukhadan_core.group_bhuarjan_sdm') or
                user.has_group('bhukhadan_core.group_bhuarjan_admin') or
                user.has_group('base.group_system'))

    @api.model
    def get_dashboard_stats(self, department_id=None, project_id=None, village_id=None, filters=None):
        """Get unified dashboard statistics for all dashboard types
        
        This method works for:
        - SDM Dashboard
        - Collector Dashboard
        - Admin Dashboard
        - Department Dashboard
        - District Admin Dashboard
        - Any other dashboard type
        
        Supports both calling styles:
        1. Individual parameters: get_dashboard_stats(department_id, project_id, village_id)
        2. Filters dict: get_dashboard_stats(filters={'department_id': 1, 'project_id': 2})
        
        Args:
            department_id: Optional department ID to filter by (if called with individual params)
            project_id: Optional project ID to filter by (if called with individual params)
            village_id: Optional village ID to filter by (if called with individual params)
            filters: Optional dict with keys 'department_id', 'project_id', 'village_id' (legacy style)
            
        Returns:
            dict: Complete dashboard statistics
        """
        try:
            # Handle both calling styles: individual params or filters dict
            if filters is not None and isinstance(filters, dict):
                # Legacy style: called with filters dict
                department_id = filters.get('department_id') or department_id
                project_id = filters.get('project_id') or project_id
                village_id = filters.get('village_id') or village_id
                # Convert to int if they exist
                if department_id:
                    try:
                        department_id = int(department_id)
                    except (ValueError, TypeError):
                        department_id = None
                if project_id:
                    try:
                        project_id = int(project_id)
                    except (ValueError, TypeError):
                        project_id = None
                if village_id:
                    try:
                        village_id = int(village_id)
                    except (ValueError, TypeError):
                        village_id = None
            
            # Build filter domains based on user access
            domains = self._build_filter_domains(department_id, project_id, village_id)
            
            # Log the filters and domains for debugging
            _logger.info(f"Dashboard Stats - Input Filters: department_id={department_id}, project_id={project_id}, village_id={village_id}")
            _logger.info(f"Dashboard Stats - Built Domains: project_domain={domains['project_domain']}, village_domain={domains['village_domain']}, final_domain={domains['final_domain']}")
            
            # Get user info
            user_access = self._get_user_project_access()
            is_collector = self.is_collector_user()
            _logger.info(f"Dashboard Stats - User access: can_see_all={user_access['can_see_all']}, user_type={user_access['user_type']}, project_ids={user_access['project_ids']}")
            
            # Debug: Test survey query directly
            if domains['final_domain']:
                test_surveys = self.env['bhu.survey'].search(domains['final_domain'], limit=10)
                _logger.info(f"Dashboard Stats - Test query found {len(test_surveys)} surveys with domain {domains['final_domain']}")
                if test_surveys:
                    _logger.info(f"Dashboard Stats - Sample survey IDs: {test_surveys.mapped('id')}")
            
            # Get project exemption status and allowed sections
            is_project_exempt = False
            is_displacement = False
            allowed_section_names = []  # List of section names allowed for this project
            if project_id:
                project = self.env['bhu.project'].browse(project_id)
                if project.exists():
                    is_project_exempt = project.is_sia_exempt or False
                    is_displacement = project.is_displacement or False
                    # Get sections from project's law
                    if project.law_master_id and project.law_master_id.section_ids:
                        allowed_section_names = list(project.law_master_id.section_ids.mapped('name'))
                        _logger.info(f"Dashboard Stats - Project {project_id} has law '{project.law_master_id.name}' with sections: {allowed_section_names}")
                        # Coal-only runtime: do not surface NH/Railway section tracks.
                        allowed_section_names = [
                            n for n in allowed_section_names
                            if '(Railways)' not in n and '(NH)' not in n
                        ]
                        # Coal dashboard label bridge
                        if 'Sec 4(i) Notification of intention to prospect' in allowed_section_names:
                            allowed_section_names.extend([
                                'Sec 4(i) Notification of intention to prospect',
                                'Sec 7(i) Notification of intention to acquire land',
                                'Sec 8 Objections',
                                'Sec 9(i) Declaration of acquisition',
                                'Sec 11(i) Vesting order',
                                'Post-Gazette Step 1 Land Records',
                                'Post-Gazette Step 2 DRRC Meeting',
                                'Post-Gazette Step 3 Asset Survey Committee Formation',
                                'Post-Gazette Step 4 Conduct Asset Survey',
                                'Post-Gazette Step 5 Land Compensation & Award',
                                'Post-Gazette Step 6 Structure/Asset Assessment & Award',
                            ])
                    # Coal-only safety fallback when project law is not configured.
                    if not allowed_section_names:
                        allowed_section_names = [
                            'Surveys (Coal Act)',
                            'Surveys',
                            'Sec 4(i) Notification of intention to prospect',
                            'Sec 7(i) Notification of intention to acquire land',
                            'Sec 8 Objections',
                            'Sec 9(i) Declaration of acquisition',
                            'Sec 11(i) Vesting order',
                            'Post-Gazette Step 1 Land Records',
                            'Post-Gazette Step 2 DRRC Meeting',
                            'Post-Gazette Step 3 Asset Survey Committee Formation',
                            'Post-Gazette Step 4 Conduct Asset Survey',
                            'Post-Gazette Step 5 Land Compensation & Award',
                            'Post-Gazette Step 6 Structure/Asset Assessment & Award',
                            'Payment Voucher',
                            'Payment File',
                            'Payment Reconciliation',
                        ]
            
            # Get total villages for completion calculations
            total_villages = self._get_total_villages(domains['project_ids_from_domain'])
            
            # Get all section counts
            counts = self._get_all_section_counts(domains)
            
            # Log survey counts for debugging
            # Log survey counts for debugging
            _logger.info(f"Dashboard Stats - Survey counts: total={counts['survey']['total']}, approved={counts['survey']['approved']}, domain={domains['final_domain']}")
            
            # Log Section 4 counts significantly
            try:
                _logger.info(f"Dashboard Stats - Section 4 counts: "
                             f"total={counts['section4']['total']},"
                             f"draft={counts['section4']['draft']},"
                             f"generated={counts['section4'].get('generated', 0)},"
                             f"submitted={counts['section4']['submitted']},"
                             f"Domain={domains['final_domain']}")
                if domains['final_domain']:
                    sec4_recs = self.env['bhu.section4.notification'].search(domains['final_domain'])
                    if sec4_recs:
                        _logger.info(f"Dashboard Stats - FOUND Section 4 IDs: {sec4_recs.ids}, States: {sec4_recs.mapped('state')}")
                    else:
                        _logger.info("Dashboard Stats - NO Section 4 records found with this domain.")
            except Exception as e:
                 _logger.error(f"Error logging section 4 stats: {e}")
            
            # Debug Section 8 specifically
            _logger.info(f"Dashboard Stats - Section 8 domain_without_village: {domains['domain_without_village']}")
            _logger.info(f"Dashboard Stats - Section 8 counts: total={counts.get('section8', {}).get('total', 0)}, draft={counts.get('section8', {}).get('draft', 0)}, approved={counts.get('section8', {}).get('approved', 0)}, rejected={counts.get('section8', {}).get('rejected', 0)}")
            # Test Section 8 query directly
            test_section8 = self.env['bhu.section8'].search(domains['domain_without_village'] if domains['domain_without_village'] else [])
            _logger.info(f"Dashboard Stats - Direct Section 8 query found {len(test_section8)} records with domain {domains['domain_without_village']}")
            if test_section8:
                _logger.info(f"Dashboard Stats - Section 8 record IDs: {test_section8.mapped('id')}, projects: {test_section8.mapped('project_id.id')}, states: {test_section8.mapped('state')}")
            
            # Debug: Test the domain directly to verify it's working
            if domains['final_domain']:
                test_surveys = self.env['bhu.survey'].search(domains['final_domain'], limit=10)
                test_count = len(test_surveys)
                _logger.info(f"Dashboard Stats - Direct test: Found {test_count} surveys with domain {domains['final_domain']}")
                if test_surveys:
                    _logger.info(f"Dashboard Stats - Sample survey IDs: {test_surveys.mapped('id')}, villages: {test_surveys.mapped('village_id.id')}")
                else:
                    # Try without village filter to see if project filter works
                    if domains['project_domain']:
                        test_without_village = self.env['bhu.survey'].search(domains['project_domain'], limit=10)
                        _logger.info(f"Dashboard Stats - Without village filter: Found {len(test_without_village)} surveys with project domain {domains['project_domain']}")
            
            # Build response with all statistics
            result = {
                'is_collector': is_collector,
                'is_sdm': self.is_sdm_user(),
                'is_admin': user_access['user_type'] == 'admin',
                'is_project_exempt': is_project_exempt,
                'is_displacement': is_displacement,
                'user_type': user_access['user_type'],
                'allowed_section_names': allowed_section_names,  # Sections mapped to project's law
                
                # Surveys
                'survey_total': counts['survey']['total'],
                'survey_draft': counts['survey']['draft'],
                'survey_submitted': counts['survey']['submitted'],
                'survey_approved': counts['survey']['approved'],
                'survey_rejected': counts['survey']['rejected'],
                'survey_completion_percent': counts['survey']['completion_percent'],
                'survey_info': self._get_section_info('bhu.survey', domains['final_domain'], 'state', is_survey=True),
                
                # Section 4 (has village_id)
                'section4_total': counts['section4']['total'],
                'section4_draft': counts['section4']['draft'],
                'section4_submitted': counts['section4']['submitted'],
                'section4_approved': counts['section4']['approved'],
                'section4_send_back': counts['section4']['send_back'],
                'section4_generated': counts['section4'].get('generated', 0),
                'section4_signed': counts['section4'].get('signed', 0),
                'section4_completion_percent': self._calculate_village_based_completion(
                    'bhu.section4.notification', domains['project_ids_from_domain'], total_villages
                ) if domains['project_ids_from_domain'] else 0.0,
                'section4_info': self._get_section_info('bhu.section4.notification', domains['final_domain']),
                
                # Section 11 (has village_id)
                'section11_total': counts['section11']['total'],
                'section11_draft': counts['section11']['draft'],
                'section11_submitted': counts['section11']['submitted'],
                'section11_approved': counts['section11']['approved'],
                'section11_send_back': counts['section11']['send_back'],
                'section11_generated': counts['section11'].get('generated', 0),
                'section11_signed': counts['section11'].get('signed', 0),
                'section11_completion_percent': self._calculate_village_based_completion(
                    'bhu.section11.preliminary.report', domains['project_ids_from_domain'], total_villages
                ) if domains['project_ids_from_domain'] else 0.0,
                'section11_info': self._get_section_info('bhu.section11.preliminary.report', domains['final_domain']),
                
                # Section 15 (has village_id)
                'section15_total': counts['section15']['total'],
                'section15_draft': counts['section15']['draft'],
                'section15_submitted': counts['section15']['submitted'],
                'section15_approved': counts['section15']['approved'],
                'section15_send_back': counts['section15']['send_back'],
                'section15_completion_percent': self._calculate_completion_percentage(
                    counts['section15']['approved'], 0, counts['section15']['total'], is_survey=False
                ),
                'section15_info': self._get_section_info('bhu.section15.objection', domains['final_domain']),
                
                # Section 19 (has village_id)
                'section19_total': counts['section19']['total'],
                'section19_draft': counts['section19']['draft'],
                'section19_submitted': counts['section19']['submitted'],
                'section19_approved': counts['section19']['approved'],
                'section19_send_back': counts['section19']['send_back'],
                'section19_generated': counts['section19'].get('generated', 0),
                'section19_signed': counts['section19'].get('signed', 0),
                'section19_completion_percent': self._calculate_village_based_completion(
                    'bhu.section19.notification', domains['project_ids_from_domain'], total_villages
                ) if domains['project_ids_from_domain'] else 0.0,
                'section19_info': self._get_section_info('bhu.section19.notification', domains['final_domain']),
                
                # Expert Committee (uses m2m_village_domain)
                'expert_total': counts['expert']['total'],
                'expert_draft': counts['expert']['draft'],
                'expert_submitted': counts['expert']['submitted'],
                'expert_approved': counts['expert']['approved'],
                'expert_send_back': counts['expert']['send_back'],
                'expert_completion_percent': self._calculate_completion_percentage(
                    counts['expert']['approved'], 0, counts['expert']['total'], is_survey=False
                ),
                'expert_info': self._get_section_info('bhu.expert.committee.report', domains['domain_without_village']),
                
                # SIA Teams (uses m2m_village_domain)
                'sia_total': counts['sia']['total'],
                'sia_draft': counts['sia']['draft'],
                'sia_submitted': counts['sia']['submitted'],
                'sia_approved': counts['sia']['approved'],
                'sia_send_back': counts['sia']['send_back'],
                'sia_completion_percent': self._calculate_completion_percentage(
                    counts['sia']['approved'], 0, counts['sia']['total'], is_survey=False
                ),
                'sia_info': self._get_section_info('bhu.sia.team', domains['domain_without_village']),
                
                # Section 8 (NO village_id - use domain_without_village, per project)
                'section8_total': counts['section8']['total'],
                'section8_draft': counts['section8']['draft'],
                'section8_approved': counts['section8']['approved'],
                'section8_rejected': counts['section8']['rejected'],
                'section8_completion_percent': self._calculate_completion_percentage(
                    counts['section8']['approved'], counts['section8']['rejected'], counts['section8']['total'], is_survey=False
                ),
                'section8_info': self._get_section_info('bhu.section8', domains['domain_without_village']),

                # Section 9 (Coal Act)
                'section9_total': counts['section9']['total'],
                'section9_draft': counts['section9']['draft'],
                'section9_submitted': counts['section9']['submitted'],
                'section9_approved': counts['section9']['approved'],
                'section9_send_back': counts['section9']['send_back'],
                'section9_completion_percent': self._calculate_village_based_completion(
                    'bhu.section9.notification', domains['project_ids_from_domain'], total_villages
                ) if domains['project_ids_from_domain'] else 0.0,
                'section9_info': self._get_section_info('bhu.section9.notification', domains['final_domain']),
                
                # Draft Award
                'draft_award_total': counts['draft_award']['total'],
                'draft_award_draft': counts['draft_award']['draft'],
                'draft_award_submitted': counts['draft_award']['submitted'],
                'draft_award_approved': counts['draft_award']['approved'],
                'draft_award_send_back': counts['draft_award']['send_back'],
                'draft_award_completion_percent': self._calculate_completion_percentage(
                    counts['draft_award']['approved'], 0, counts['draft_award']['total'], is_survey=False
                ),
                'draft_award_info': self._get_section_info('bhu.section21.notification', domains['final_domain']),
                
                # Railway Act Sections (all have village_id)
                # Section 20A - No workflow, just total count
                'section20a_railways_total': counts['section20a_railways']['total'],
                'section20a_railways_draft': 0,
                'section20a_railways_submitted': 0,
                'section20a_railways_approved': 0,
                'section20a_railways_send_back': 0,
                'section20a_railways_completion_percent': 0.0,
                'section20a_railways_info': {
                    'total': counts['section20a_railways']['total'],
                    'draft_count': 0,
                    'submitted_count': 0,
                    'approved_count': 0,
                    'rejected_count': 0,
                    'send_back_count': 0,
                    'all_approved': True,
                    'is_completed': True,
                    'first_pending_id': False,
                    'first_document_id': False,
                },
                
                'section20d_railways_total': counts['section20d_railways']['total'],
                'section20d_railways_draft': counts['section20d_railways']['draft'],
                'section20d_railways_submitted': counts['section20d_railways']['submitted'],
                'section20d_railways_approved': counts['section20d_railways']['approved'],
                'section20d_railways_send_back': counts['section20d_railways']['send_back'],
                'section20d_railways_completion_percent': self._calculate_completion_percentage(
                    counts['section20d_railways']['approved'], 0, counts['section20d_railways']['total'], is_survey=False
                ),
                'section20d_railways_info': self._get_section_info('bhu.section20d.railways', domains['final_domain']),
                
                # Section 20E - No workflow, just total count
                'section20e_railways_total': counts['section20e_railways']['total'],
                'section20e_railways_draft': 0,
                'section20e_railways_submitted': 0,
                'section20e_railways_approved': 0,
                'section20e_railways_send_back': 0,
                'section20e_railways_completion_percent': 0.0,
                'section20e_railways_info': {
                    'total': counts['section20e_railways']['total'],
                    'draft_count': 0,
                    'submitted_count': 0,
                    'approved_count': 0,
                    'rejected_count': 0,
                    'send_back_count': 0,
                    'all_approved': True,
                    'is_completed': True,
                    'first_pending_id': False,
                    'first_document_id': False,
                },
                
                # National Highway Act Sections (all have village_id)
                # Section 3A - No workflow, just total count
                'section3a_nh_total': counts['section3a_nh']['total'],
                'section3a_nh_draft': 0,
                'section3a_nh_submitted': 0,
                'section3a_nh_approved': 0,
                'section3a_nh_send_back': 0,
                'section3a_nh_completion_percent': 0.0,
                'section3a_nh_info': {
                    'total': counts['section3a_nh']['total'],
                    'draft_count': 0,
                    'submitted_count': 0,
                    'approved_count': 0,
                    'rejected_count': 0,
                    'send_back_count': 0,
                    'all_approved': True,
                    'is_completed': True,
                    'first_pending_id': False,
                    'first_document_id': False,
                },
                
                'section3c_nh_total': counts['section3c_nh']['total'],
                'section3c_nh_draft': counts['section3c_nh']['draft'],
                'section3c_nh_submitted': counts['section3c_nh']['submitted'],
                'section3c_nh_approved': counts['section3c_nh']['approved'],
                'section3c_nh_send_back': counts['section3c_nh']['send_back'],
                'section3c_nh_completion_percent': self._calculate_completion_percentage(
                    counts['section3c_nh']['approved'], 0, counts['section3c_nh']['total'], is_survey=False
                ),
                'section3c_nh_info': self._get_section_info('bhu.section3c.nh', domains['final_domain']),
                
                # Section 3D - No workflow, just total count
                'section3d_nh_total': counts['section3d_nh']['total'],
                'section3d_nh_draft': 0,
                'section3d_nh_submitted': 0,
                'section3d_nh_approved': 0,
                'section3d_nh_send_back': 0,
                'section3d_nh_completion_percent': 0.0,
                'section3d_nh_info': {
                    'total': counts['section3d_nh']['total'],
                    'draft_count': 0,
                    'submitted_count': 0,
                    'approved_count': 0,
                    'rejected_count': 0,
                    'send_back_count': 0,
                    'all_approved': True,
                    'is_completed': True,
                    'first_pending_id': False,
                    'first_document_id': False,
                },
                
                # Section 23 Award (has village_id)
                'section23_award_total': counts['section23_award']['total'],
                'section23_award_draft': counts['section23_award']['draft'],
                'section23_award_submitted': counts['section23_award']['submitted'],
                'section23_award_approved': counts['section23_award']['approved'],
                'section23_award_send_back': counts['section23_award']['send_back'],
                'section23_award_completion_percent': self._calculate_completion_percentage(
                    counts['section23_award']['approved'], 0, counts['section23_award']['total'], is_survey=False
                ),
                'section23_award_info': self._get_section_info('bhu.section23.award', domains['final_domain'], pending_state='draft'),

                # Payment Voucher (R&R draft voucher — edit bank details)
                'payment_voucher_total': counts['payment_voucher']['total'],
                'payment_voucher_draft': counts['payment_voucher']['draft'],
                'payment_voucher_generated': counts['payment_voucher']['generated'],
                'payment_voucher_completion_percent': self._calculate_completion_percentage(
                    counts['payment_voucher']['generated'],
                    0,
                    counts['payment_voucher'].get('award_total') or counts['payment_voucher']['total'],
                    is_survey=False,
                ),
                'payment_voucher_info': self._get_payment_voucher_info(domains['final_domain']),

                # Payment File (bank Excel generated from voucher)
                'payment_file_total': counts['payment_file']['total'],
                'payment_file_draft': counts['payment_file']['draft'],
                'payment_file_generated': counts['payment_file']['generated'],
                'payment_file_completion_percent': counts['payment_file'].get(
                    'completion_percent', 0
                ),
                'payment_file_voucher_amount': counts['payment_file'].get('voucher_amount', 0),
                'payment_file_paid_amount': counts['payment_file'].get('file_amount', 0),
                'payment_file_pending_amount': counts['payment_file'].get('pending_amount', 0),
                'payment_file_info': self._get_payment_file_info(domains['final_domain']),

                # Reconciliation (has village_id)
                'reconciliation_total': counts['reconciliation']['total'],
                'reconciliation_draft': counts['reconciliation']['draft'],
                'reconciliation_processed': counts['reconciliation']['processed'],
                'reconciliation_completed': counts['reconciliation']['completed'],
                'reconciliation_completion_percent': self._calculate_completion_percentage(
                    counts['reconciliation']['completed'], 0, counts['reconciliation']['total'], is_survey=False
                ),
                'reconciliation_info': self._get_section_info('bhu.payment.reconciliation.bank', domains['final_domain'], state_field='state'),

                # CGLRC Section 247
                'section247_1_cglrc_total': counts['section247_1_cglrc']['total'],
                'section247_1_cglrc_draft': counts['section247_1_cglrc']['draft'],
                'section247_1_cglrc_approved': counts['section247_1_cglrc']['approved'],
                'section247_1_cglrc_completion_percent': self._calculate_completion_percentage(
                    counts['section247_1_cglrc']['approved'], 0, counts['section247_1_cglrc']['total'], is_survey=False
                ),
                'section247_1_cglrc_info': self._get_section_info('bhu.section247_1.cglrc', domains['final_domain'], pending_state='draft'),

                'section247_2_cglrc_total': counts['section247_2_cglrc']['total'],
                'section247_2_cglrc_draft': counts['section247_2_cglrc']['draft'],
                'section247_2_cglrc_approved': counts['section247_2_cglrc']['approved'],
                'section247_2_cglrc_completion_percent': self._calculate_completion_percentage(
                    counts['section247_2_cglrc']['approved'], 0, counts['section247_2_cglrc']['total'], is_survey=False
                ),
                'section247_2_cglrc_info': self._get_section_info('bhu.section247_2.cglrc', domains['final_domain'], pending_state='draft'),

                'section247_3_cglrc_total': counts['section247_3_cglrc']['total'],
                'section247_3_cglrc_draft': counts['section247_3_cglrc']['draft'],
                'section247_3_cglrc_approved': counts['section247_3_cglrc']['approved'],
                'section247_3_cglrc_completion_percent': self._calculate_completion_percentage(
                    counts['section247_3_cglrc']['approved'], 0, counts['section247_3_cglrc']['total'], is_survey=False
                ),
                'section247_3_cglrc_info': self._get_section_info('bhu.section247_3.cglrc', domains['final_domain'], pending_state='draft'),

            }
            
            return result
            
        except Exception as e:
            _logger.error(f"Error getting dashboard stats: {e}", exc_info=True)
            # Return zeros on error
            return self._get_empty_stats()

    @api.model
    def _get_empty_stats(self):
        """Return empty stats structure for error cases"""
        is_collector = self.is_collector_user()
        empty_info = {
            'total': 0, 'submitted_count': 0, 'approved_count': 0, 'rejected_count': 0,
            'send_back_count': 0, 'all_approved': True, 'is_completed': True,
            'first_pending_id': False, 'first_document_id': False,
        }
        
        return {
            'is_collector': is_collector,
            'is_sdm': self.is_sdm_user(),
            'is_project_exempt': False,
            'user_type': 'other',
            'allowed_section_names': [],  # Empty list when no project selected
            'survey_total': 0, 'survey_draft': 0, 'survey_submitted': 0, 'survey_approved': 0, 'survey_rejected': 0,
            'survey_completion_percent': 0, 'survey_info': empty_info.copy(),
            'section4_total': 0, 'section4_draft': 0, 'section4_submitted': 0, 'section4_approved': 0, 'section4_send_back': 0,
            'section4_completion_percent': 0, 'section4_info': empty_info.copy(),
            'section11_total': 0, 'section11_draft': 0, 'section11_submitted': 0, 'section11_approved': 0, 'section11_send_back': 0,
            'section11_completion_percent': 0, 'section11_info': empty_info.copy(),
            'section15_total': 0, 'section15_draft': 0, 'section15_submitted': 0, 'section15_approved': 0, 'section15_send_back': 0,
            'section15_completion_percent': 0, 'section15_info': empty_info.copy(),
            'section19_total': 0, 'section19_draft': 0, 'section19_submitted': 0, 'section19_approved': 0, 'section19_send_back': 0,
            'section19_completion_percent': 0, 'section19_info': empty_info.copy(),
            'expert_total': 0, 'expert_draft': 0, 'expert_submitted': 0, 'expert_approved': 0, 'expert_send_back': 0,
            'expert_completion_percent': 0, 'expert_info': empty_info.copy(),
            'sia_total': 0, 'sia_draft': 0, 'sia_submitted': 0, 'sia_approved': 0, 'sia_send_back': 0,
            'sia_completion_percent': 0, 'sia_info': empty_info.copy(),
            'section8_total': 0, 'section8_draft': 0, 'section8_approved': 0, 'section8_rejected': 0,
            'section8_completion_percent': 0, 'section8_info': empty_info.copy(),
            'section9_total': 0, 'section9_draft': 0, 'section9_submitted': 0, 'section9_approved': 0, 'section9_send_back': 0,
            'section9_completion_percent': 0, 'section9_info': empty_info.copy(),
            'draft_award_total': 0, 'draft_award_draft': 0, 'draft_award_submitted': 0, 'draft_award_approved': 0, 'draft_award_send_back': 0,
            'draft_award_completion_percent': 0, 'draft_award_info': empty_info.copy(),
            # Railway Act Sections
            'section20a_railways_total': 0, 'section20a_railways_draft': 0, 'section20a_railways_submitted': 0,
            'section20a_railways_approved': 0, 'section20a_railways_send_back': 0, 'section20a_railways_completion_percent': 0,
            'section20a_railways_info': empty_info.copy(),
            'section20d_railways_total': 0, 'section20d_railways_draft': 0, 'section20d_railways_submitted': 0,
            'section20d_railways_approved': 0, 'section20d_railways_send_back': 0, 'section20d_railways_completion_percent': 0,
            'section20d_railways_info': empty_info.copy(),
            'section20e_railways_total': 0, 'section20e_railways_draft': 0, 'section20e_railways_submitted': 0,
            'section20e_railways_approved': 0, 'section20e_railways_send_back': 0, 'section20e_railways_completion_percent': 0,
            'section20e_railways_info': empty_info.copy(),
            # National Highway Act Sections
            'section3a_nh_total': 0, 'section3a_nh_draft': 0, 'section3a_nh_submitted': 0,
            'section3a_nh_approved': 0, 'section3a_nh_send_back': 0, 'section3a_nh_completion_percent': 0,
            'section3a_nh_info': empty_info.copy(),
            'section3c_nh_total': 0, 'section3c_nh_draft': 0, 'section3c_nh_submitted': 0,
            'section3c_nh_approved': 0, 'section3c_nh_send_back': 0, 'section3c_nh_completion_percent': 0,
            'section3c_nh_info': empty_info.copy(),
            'section3d_nh_total': 0, 'section3d_nh_draft': 0, 'section3d_nh_submitted': 0,
            'section3d_nh_approved': 0, 'section3d_nh_send_back': 0, 'section3d_nh_completion_percent': 0,
            'section3d_nh_info': empty_info.copy(),
            # Section 23 Award
            'section23_award_total': 0, 'section23_award_draft': 0, 'section23_award_submitted': 0,
            'section23_award_approved': 0, 'section23_award_send_back': 0, 'section23_award_completion_percent': 0,
            'section23_award_info': empty_info.copy(),
            # CGLRC Section 247
            'section247_1_cglrc_total': 0, 'section247_1_cglrc_draft': 0,
            'section247_1_cglrc_approved': 0, 'section247_1_cglrc_completion_percent': 0,
            'section247_1_cglrc_info': empty_info.copy(),
            'section247_2_cglrc_total': 0, 'section247_2_cglrc_draft': 0,
            'section247_2_cglrc_approved': 0, 'section247_2_cglrc_completion_percent': 0,
            'section247_2_cglrc_info': empty_info.copy(),
            'section247_3_cglrc_total': 0, 'section247_3_cglrc_draft': 0,
            'section247_3_cglrc_approved': 0, 'section247_3_cglrc_completion_percent': 0,
            'section247_3_cglrc_info': empty_info.copy(),
            # Payment Voucher
            'payment_voucher_total': 0, 'payment_voucher_draft': 0, 'payment_voucher_generated': 0,
            'payment_voucher_completion_percent': 0, 'payment_voucher_info': empty_info.copy(),
            # Payment File
            'payment_file_total': 0, 'payment_file_draft': 0, 'payment_file_generated': 0,
            'payment_file_completion_percent': 0, 'payment_file_info': empty_info.copy(),
            # Reconciliation
            'reconciliation_total': 0, 'reconciliation_draft': 0, 'reconciliation_processed': 0, 'reconciliation_completed': 0,
            'reconciliation_completion_percent': 0, 'reconciliation_info': empty_info.copy(),
        }

    # ========== Generic Data Methods ==========
    
    @api.model
    def get_user_projects(self, department_id=None):
        """Get projects accessible to current user, optionally filtered by department
        
        This method automatically determines user access based on their role:
        - Admin/Collector: See all projects
        - SDM/Tehsildar: See only assigned projects
        - Department User: See projects in their department
        - Others: See only assigned projects
        
        Args:
            department_id: Optional department ID to filter by (can be int, string, or None)
            
        Returns:
            list: List of project dicts with 'id', 'name', and 'code' (code may be false)
        """
        # Convert department_id to int if provided
        dept_id = None
        if department_id:
            try:
                dept_id = int(department_id)
            except (ValueError, TypeError):
                _logger.warning(f"Invalid department_id provided: {department_id}, ignoring filter")
                dept_id = None
        
        user_access = self._get_user_project_access()
        _logger.info(f"get_user_projects called - user: {self.env.user.name} (ID: {self.env.user.id}), "
                    f"can_see_all: {user_access['can_see_all']}, department_id: {dept_id}")
        
        domain = []
        
        if user_access['can_see_all']:
            # Admin/Collector/District Admin: can see all, optionally filter by department
            if dept_id:
                domain = [('department_id', '=', dept_id)]
            projects = self.env['bhu.project'].search(domain)
            _logger.info(f"Found {len(projects)} projects (can_see_all=True, dept_filter={dept_id})")
        else:
            # User has project restrictions
            project_ids = user_access['project_ids'] or []
            if project_ids:
                domain = [('id', 'in', project_ids)]
                if dept_id:
                    domain = ['&', ('department_id', '=', dept_id)] + domain
                projects = self.env['bhu.project'].search(domain)
                _logger.info(f"Found {len(projects)} projects (restricted access, dept_filter={dept_id})")
            else:
                _logger.warning(f"No project_ids found for user {self.env.user.name} (ID: {self.env.user.id})")
                return []
        
        result = projects.read(["id", "name", "code"])
        _logger.info(f"Returning {len(result)} projects: {[p['name'] for p in result]}")
        return result
    
    @api.model
    def get_villages_by_project(self, project_id):
        """Get villages for a specific project.

        Each dict includes ``display_code``: ``village_code`` from master when set, otherwise a
        stable per-project fallback ``V1``, ``V2``, … (sorted by village name, id) so the
        dashboard dropdown always shows a bracket code like projects do.
        """
        try:
            pid = int(project_id)
        except (TypeError, ValueError):
            return []
        project = self.env["bhu.project"].browse(pid)
        if not project.exists():
            return []
        villages = project.village_ids.sorted(key=lambda v: ((v.name or "").lower(), v.id))
        out = []
        for idx, village in enumerate(villages, start=1):
            row = village.read(["id", "name", "village_type", "village_code"])[0]
            master_code = (row.get("village_code") or "").strip()
            code = master_code or f"V{idx}"
            row["display_code"] = code
            vname = (row.get("name") or "").strip()
            row["dropdown_label"] = f"[{code}] {vname}".strip() if vname else f"[{code}]"
            out.append(row)
        return out

    @api.model
    def get_survey_trend_data(self, company_ids=None):
        """Survey counts by day (30d), week (12w), month (12m) for chart widgets."""
        from datetime import date, timedelta

        Survey = self.env["bhu.survey"]
        today = date.today()

        def _count(domain_extra):
            base = [("company_id", "in", company_ids)] if company_ids else []
            return Survey.search_count(base + domain_extra)

        daily = []
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            daily.append({
                "label": d.strftime("%d %b"),
                "value": _count([("survey_date", "=", d.isoformat())]),
                "iso": d.isoformat(),
            })

        weekly = []
        week_start = today - timedelta(days=today.weekday())
        for i in range(11, -1, -1):
            ws = week_start - timedelta(weeks=i)
            we = ws + timedelta(days=6)
            weekly.append({
                "label": ws.strftime("%d %b"),
                "value": _count([
                    ("survey_date", ">=", ws.isoformat()),
                    ("survey_date", "<=", we.isoformat()),
                ]),
                "iso": ws.isoformat(),
            })

        monthly = []
        for i in range(11, -1, -1):
            month_dt = date(today.year, today.month, 1)
            total_months = month_dt.month - i - 1
            year_offset, month_offset = divmod(total_months, 12)
            ms = date(month_dt.year + year_offset, month_offset + 1, 1)
            if ms.month == 12:
                me = date(ms.year + 1, 1, 1) - timedelta(days=1)
            else:
                me = date(ms.year, ms.month + 1, 1) - timedelta(days=1)
            monthly.append({
                "label": ms.strftime("%b %Y"),
                "value": _count([
                    ("survey_date", ">=", ms.isoformat()),
                    ("survey_date", "<=", me.isoformat()),
                ]),
                "iso": ms.isoformat(),
            })

        return {"daily": daily, "weekly": weekly, "monthly": monthly}

    @api.model
    def get_management_dashboard_data(
        self,
        company_ids=None,
        department_id=None,
        project_id=None,
        date_from=None,
        date_to=None,
    ):
        """Executive summary — optional filters: department, project, survey_date range."""

        def _intval(v):
            if v is None or v is False:
                return None
            if isinstance(v, int):
                return v
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        def _trim_date_str(s):
            if not s or not isinstance(s, str):
                return None
            s = s.strip()
            return s[:10] if len(s) >= 10 else s if s else None

        stage_labels = {
            'initial': _('Initial'),
            'sia': _('SIA'),
            'section4': _('Section 4'),
            'section11': _('Section 11'),
            'section19': _('Section 19'),
            'section21': _('Section 21'),
            'award': _('Sec. 23 Award'),
        }
        expected_days_map = {
            'initial': 90,
            'sia': 180,
            'section4': 210,
            'section11': 365,
            'section19': 455,
            'section21': 545,
            'award': 730,
        }

        cid_list = [int(x) for x in (company_ids or []) if x]
        if not cid_list:
            cid_list = [self.env.company.id]

        dept_f = _intval(department_id)
        proj_single = _intval(project_id)
        df = _trim_date_str(date_from)
        dt = _trim_date_str(date_to)

        Project = self.env['bhu.project']
        Survey = self.env['bhu.survey']
        Department = self.env['bhu.department']
        Award23 = self.env['bhu.section23.award']
        BankRecon = self.env['bhu.payment.reconciliation.bank']

        # --- Dropdown meta (whole company portfolio; client narrows project list by dept)
        meta_departments = [{'id': d.id, 'name': d.display_name} for d in Department.search([], order='name', limit=500)]
        meta_projects = []
        for p in Project.search([('company_id', 'in', cid_list)], order='name', limit=800):
            meta_projects.append({
                'id': p.id,
                'name': p.display_name or p.name or '',
                'department_id': p.department_id.id if p.department_id else False,
                'department_name': p.department_id.display_name if p.department_id else '',
            })

        proj_domain = [('company_id', 'in', cid_list)]
        if dept_f:
            proj_domain.append(('department_id', '=', dept_f))
        if proj_single:
            proj_domain.append(('id', '=', proj_single))

        projects = Project.search(proj_domain, limit=260, order='create_date desc')
        project_ids = projects.ids

        stage_map = Project.get_acquisition_stage_map(project_ids) if project_ids else {}

        survey_domain = [('company_id', 'in', cid_list)]
        if project_ids:
            survey_domain.append(('project_id', 'in', project_ids))
        else:
            survey_domain.append(('id', '=', False))
        if df:
            survey_domain.append(('survey_date', '>=', df))
        if dt:
            survey_domain.append(('survey_date', '<=', dt))

        survey_count_map = {}
        if project_ids:
            for row in Survey.read_group(
                    survey_domain + [('project_id', 'in', project_ids)],
                    ['project_id'],
                    ['project_id'],
                    lazy=False,
            ):
                pr = row.get('project_id')
                if isinstance(pr, (list, tuple)) and pr[0]:
                    survey_count_map[pr[0]] = int(row.get('__count') or 0)

        filters_active = bool(dept_f or proj_single or df or dt)

        # --- Rollups by stage
        stage_distribution = {'initial': 0, 'sia': 0, 'section4': 0, 'section11': 0,
                              'section19': 0, 'section21': 0, 'award': 0}
        on_track = 0
        delayed_count = 0
        delayed_projects = []
        today = fields.Date.context_today(self)

        proj_state_sel = Project._fields['state'].selection
        if callable(proj_state_sel):
            proj_state_sel = proj_state_sel(Project)
        proj_state_selection = dict(proj_state_sel)

        for p in projects:
            st_key = stage_map.get(p.id, 'initial')
            if st_key in stage_distribution:
                stage_distribution[st_key] += 1

            cd = fields.Date.to_date(p.create_date) if p.create_date else today
            days_since = max((today - cd).days, 0)
            expected = expected_days_map.get(st_key, 90)
            delay_days = days_since - expected
            if delay_days > 0:
                delayed_count += 1
                delayed_projects.append({
                    'id': p.id,
                    'name': p.name or '',
                    'code': p.code or '',
                    'department': p.department_id.display_name if p.department_id else '',
                    'stage': st_key,
                    'stage_label': stage_labels.get(st_key, st_key),
                    'delay_days': int(delay_days),
                    'days_since_creation': int(days_since),
                    'expected_days': int(expected),
                })
            else:
                on_track += 1

        delayed_projects.sort(key=lambda r: r['delay_days'], reverse=True)
        delayed_projects = delayed_projects[:15]

        total_budget_inr = 0.0
        projects_overview = []
        for p in projects:
            total_budget_inr += _management_parse_project_cost(p.total_cost)
            dept_name = p.department_id.display_name if p.department_id else ''
            dist_name = p.district_id.display_name if p.district_id else ''
            st_key = stage_map.get(p.id, 'initial')
            projects_overview.append({
                'id': p.id,
                'name': p.name or '',
                'code': p.code or '',
                'department': dept_name,
                'district': dist_name,
                'project_state': p.state,
                'project_state_label': proj_state_selection.get(p.state, p.state or ''),
                'stage_key': st_key,
                'stage_label': stage_labels.get(st_key, st_key),
                'survey_count': int(survey_count_map.get(p.id, 0)),
            })

        if project_ids:
            sec23_total = Award23.search_count([('project_id', 'in', project_ids)])
            sec23_generated = Award23.search_count([
                ('project_id', 'in', project_ids),
                ('state', '=', 'approved'),
            ])
            recon_completed = BankRecon.search_count([
                ('project_id', 'in', project_ids),
                ('state', '=', 'completed'),
            ])
        else:
            sec23_total = sec23_generated = recon_completed = 0

        arb_open = 0
        if 'bharat.arbitration.grievance' in self.env:
            try:
                arb_open = self.env['bharat.arbitration.grievance'].search_count([
                    ('state', 'in', ('draft', 'registered', 'scheduled', 'heard')),
                ])
            except Exception:
                arb_open = 0

        surveys_total = Survey.search_count(survey_domain)

        pat_groups = Survey.read_group(
            survey_domain,
            ['user_id'],
            ['user_id'],
            lazy=False,
        )
        pat_groups.sort(key=lambda r: r.get('__count', 0), reverse=True)

        patwari_leaderboard = []
        for row in pat_groups[:10]:
            u = row.get('user_id')
            cnt = int(row.get('__count') or 0)
            if not u:
                patwari_leaderboard.append({'user_id': None, 'name': _('Unassigned'), 'survey_count': cnt})
            elif isinstance(u, (list, tuple)) and len(u) >= 2:
                patwari_leaderboard.append({'user_id': u[0], 'name': u[1], 'survey_count': cnt})

        dept_proj = Project.read_group(
            proj_domain,
            ['department_id'],
            ['department_id'],
            lazy=False,
        )
        dept_srv = Survey.read_group(
            survey_domain,
            ['department_id'],
            ['department_id'],
            lazy=False,
        )
        by_dept = {}
        for row in dept_proj:
            d = row.get('department_id')
            key = d[0] if isinstance(d, (list, tuple)) and d else None
            label = d[1] if isinstance(d, (list, tuple)) and len(d) > 1 else ''
            slot = by_dept.setdefault(key, {'id': key, 'name': label or _('No department'), 'projects': 0, 'surveys': 0})
            slot['projects'] += int(row.get('__count') or 0)
            if label:
                slot['name'] = label
        for row in dept_srv:
            d = row.get('department_id')
            key = d[0] if isinstance(d, (list, tuple)) and d else None
            label = d[1] if isinstance(d, (list, tuple)) and len(d) > 1 else _('No department')
            slot = by_dept.setdefault(key, {'id': key, 'name': label, 'projects': 0, 'surveys': 0})
            slot['surveys'] += int(row.get('__count') or 0)
            if slot['name'] == _('No department') and label:
                slot['name'] = label

        department_stats = sorted(
            by_dept.values(),
            key=lambda r: -(r['projects'] + r['surveys']),
        )

        project_survey_bars = []
        for row in sorted(
                projects_overview,
                key=lambda r: int(r.get('survey_count') or 0),
                reverse=True,
        )[:14]:
            project_survey_bars.append({
                'project_id': row['id'],
                'name': row['name'] or _('Project'),
                'survey_count': int(row.get('survey_count') or 0),
            })
        if not project_survey_bars:
            project_survey_bars = [{'project_id': None, 'name': _('No projects'), 'survey_count': 0}]

        project_arbitration_bars = []
        if 'bharat.arbitration.grievance' in self.env and project_ids:
            Grievance = self.env['bharat.arbitration.grievance']
            try:
                for g_row in Grievance.read_group(
                        [('project_id', 'in', project_ids)],
                        ['project_id'],
                        ['project_id'],
                        lazy=False,
                ):
                    pr = g_row.get('project_id')
                    cnt = int(g_row.get('__count') or 0)
                    if isinstance(pr, (list, tuple)) and pr[0] and cnt:
                        nm = pr[1] if len(pr) > 1 else (_('Project #%s') % pr[0])
                        project_arbitration_bars.append({
                            'project_id': pr[0],
                            'name': nm or (_('Project #%s') % pr[0]),
                            'grievance_count': cnt,
                        })
            except Exception:
                project_arbitration_bars = []
        project_arbitration_bars.sort(key=lambda r: r['grievance_count'], reverse=True)
        project_arbitration_bars = project_arbitration_bars[:14]
        if not project_arbitration_bars:
            project_arbitration_bars = [{'project_id': None, 'name': _('No arbitrations'), 'grievance_count': 0}]

        sdm_project_totals = defaultdict(int)
        sdm_names = {}
        for p in projects:
            if p.sdm_ids:
                for u in p.sdm_ids:
                    sdm_project_totals[u.id] += 1
                    sdm_names[u.id] = u.display_name or u.name or _('User #%s') % u.id
            else:
                sdm_project_totals[0] += 1
                sdm_names.setdefault(0, _('Unassigned'))
        sdm_project_bars = [
            {'user_id': uid, 'name': sdm_names.get(uid, str(uid)), 'project_count': c}
            for uid, c in sorted(sdm_project_totals.items(), key=lambda kv: kv[1], reverse=True)
        ][:14]
        if not sdm_project_bars:
            sdm_project_bars = [{'user_id': None, 'name': _('No data'), 'project_count': 0}]

        def _fmt_inr(n):
            try:
                n = float(n)
            except (TypeError, ValueError):
                return '0'
            if n >= 1e7:
                return '%.2f Cr' % (n / 1e7,)
            if n >= 1e5:
                return '%.2f L' % (n / 1e5,)
            return '{:,.0f}'.format(n)

        return {
            'meta': {
                'departments': meta_departments,
                'projects': meta_projects,
            },
            'filter_echo': {
                'department_id': dept_f,
                'project_id': proj_single,
                'date_from': df,
                'date_to': dt,
                'filters_active': filters_active,
            },
            'kpis': {
                'total_projects': len(projects),
                'on_track_projects': int(on_track),
                'delayed_projects': int(delayed_count),
                'surveys_total': int(surveys_total),
                'total_budget_inr': round(total_budget_inr, 2),
                'total_budget_display': _fmt_inr(total_budget_inr),
                'section23_awards': int(sec23_total),
                'section23_generated': int(sec23_generated),
                'reconciliation_completed': int(recon_completed),
                'land_arbitration_open': int(arb_open),
                'filters_active': filters_active,
            },
            'stage_labels': stage_labels,
            'stage_distribution': stage_distribution,
            'patwari_leaderboard': patwari_leaderboard,
            'department_stats': department_stats,
            'project_survey_bars': project_survey_bars,
            'project_arbitration_bars': project_arbitration_bars,
            'sdm_project_bars': sdm_project_bars,
            'projects_overview': projects_overview,
        }

    @api.model
    def get_sdm_pipeline_dashboard_data(self, company_ids=None):
        """Subdivision-centric pipeline overview for SDMs (scoped) and leadership (all).

        Returns subdivisions with nested projects and villages; each row includes nine-dot
        pipeline data and optional completion percentages (computed client-side from dots
        or here as ``pipeline_pct``).
        """
        user = self.env.user
        allowed = (
            user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('base.group_system')
            or user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
            or user.has_group('bhukhadan_core.group_bhuarjan_sdm')
        )
        if not allowed:
            raise AccessError(_('You do not have access to the SDM Pipeline Dashboard.'))

        can_see_all_subdiv = (
            user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('base.group_system')
            or user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        )
        can_impersonate_collector = (
            user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('base.group_system')
        )

        Project = self.env['bhu.project'].sudo()
        SubDiv = self.env['bhu.sub.division'].sudo()

        cids = list(company_ids or [])
        if not cids:
            cids = list(self.env.context.get('allowed_company_ids') or []) or user.company_ids.ids

        proj_company_domain = [('company_id', 'in', cids)] if cids else []

        sdm_accessible = Project.browse()
        if not can_see_all_subdiv:
            # Same rules as main dashboard dropdowns: sdm_ids + all projects on owned sub divisions.
            accessible_ids = self._get_sdm_project_ids(user)
            sdm_accessible = Project.search([('id', 'in', accessible_ids)]) if accessible_ids else Project.browse()
            if sdm_accessible:
                cids = list(set(cids) | set(sdm_accessible.mapped('company_id').ids))
                proj_company_domain = [('company_id', 'in', cids)] if cids else []

        if can_see_all_subdiv:
            subdivisions = SubDiv.search([])
            # Leadership: show full sub-division portfolio (not only active-company subset).
            proj_company_domain = []
        else:
            owned_subdivs = SubDiv.search([('user_id', '=', user.id)])
            subdivisions = owned_subdivs | sdm_accessible.sub_division_id

        subdivisions = subdivisions.sorted(
            key=lambda r: ((r.state_id.name or ''), (r.district_id.name or ''), (r.name or ''))
        )

        district_collector_map = self._get_district_collector_map()

        subdiv_payload = []
        all_project_ids = []
        pairs = []

        for sd in subdivisions:
            if can_see_all_subdiv:
                projects = Project.search(
                    [('sub_division_id', 'in', sd.ids)] + proj_company_domain,
                    order='name asc',
                )
            else:
                if sd.user_id == user:
                    # Same query as leadership for this sub division (sudo; record rules also allow sub_division SDM).
                    projects = Project.search(
                        [('sub_division_id', 'in', sd.ids)],
                        order='name asc',
                    )
                else:
                    projects = sdm_accessible.filtered(
                        lambda p: sd.id in p.sub_division_id.ids
                    )
                    extra = sdm_accessible.filtered(
                        lambda p: (
                            not p.sub_division_id
                            and p.district_id
                            and p.district_id == sd.district_id
                        )
                    )
                    projects = (projects | extra).sorted(
                        key=lambda p: ((p.name or ''), p.id)
                    )
            proj_rows = []
            for p in projects:
                all_project_ids.append(p.id)
                villages_data = []
                for v in p.village_ids.sorted(lambda x: (x.name or '', x.id)):
                    pairs.append([p.id, v.id])
                    pat = v.user_id
                    pat_phone = ''
                    if pat:
                        pat_phone = (pat.mobile or '').strip() or (pat.phone or '').strip()
                    villages_data.append({
                        'id': v.id,
                        'name': v.display_name or v.name or '',
                        'code': v.village_code or '',
                        'patwari_name': pat.display_name if pat else '',
                        'patwari_mobile': pat_phone,
                    })
                sd_names = [n for n in p.sub_division_id.mapped('name') if n]
                tehsil_names = [n for n in p.tehsil_ids.mapped('name') if n]
                alloc_tehsil = (p.allocated_tehsil or '').strip()
                sub_division_display = ', '.join(dict.fromkeys([x.strip() for x in sd_names if x.strip()]))
                # Domain guarantees this SD links the project; master list sometimes omits M2M sync — still show card SD.
                if not sub_division_display:
                    sub_division_display = (sd.name or '').strip()

                district_display = ''
                if p.district_id:
                    district_display = (
                        (p.district_id.display_name or p.district_id.name or '')
                    ).strip()
                if not district_display:
                    district_display = (sd.district_id.name if sd.district_id else '') or ''

                tehsil_display = ', '.join(dict.fromkeys([x.strip() for x in tehsil_names if x.strip()]))
                if not tehsil_display:
                    tehsil_display = alloc_tehsil
                if not tehsil_display and p.village_ids:
                    vt = []
                    for vil in p.village_ids:
                        if vil.tehsil_id and vil.tehsil_id.name:
                            vt.append(vil.tehsil_id.name.strip())
                    tehsil_display = ', '.join(dict.fromkeys(vt))

                dept = p.department_id
                proj_rows.append({
                    'id': p.id,
                    'name': p.name or '',
                    'code': p.code or '',
                    'sub_division': sub_division_display,
                    'tehsil': tehsil_display,
                    'department': dept.display_name if dept else '',
                    'department_id': dept.id if dept else False,
                    'department_has_logo': bool(dept and dept.department_logo),
                    'department_icon': (dept.icon or '').strip() if dept else '',
                    'district': district_display,
                    'state': p.state,
                    'village_count': len(p.village_ids),
                    'villages': villages_data,
                })
            collector = district_collector_map.get(sd.district_id.id) if sd.district_id else False
            district_name = sd.district_id.name if sd.district_id else ''
            subdiv_payload.append({
                'id': sd.id,
                'name': sd.name or '',
                'district_name': district_name,
                'district_id': sd.district_id.id if sd.district_id else False,
                'state_name': sd.state_id.name if sd.state_id else '',
                'sdm_user': sd.user_id.display_name if sd.user_id else '',
                'sdm_user_id': sd.user_id.id if sd.user_id else False,
                'collector_user': self._collector_display_label(collector, district_name),
                'collector_user_id': collector.id if collector else False,
                'projects': proj_rows,
                'project_count': len(proj_rows),
            })

        uniq_project_ids = list(dict.fromkeys(all_project_ids))
        dots_by_project = Project.get_pipeline_dots_for_dashboard(uniq_project_ids)
        village_dots = Project.get_village_pipeline_dots_for_dashboard(pairs)

        Survey = self.env['bhu.survey'].sudo()
        survey_count_map = {}
        if uniq_project_ids:
            for row in Survey.read_group(
                    [('project_id', 'in', uniq_project_ids)],
                    ['project_id', 'village_id'],
                    ['project_id', 'village_id'],
                    lazy=False,
            ):
                pr = row.get('project_id')
                vil = row.get('village_id')
                if (
                    isinstance(pr, (list, tuple)) and pr[0]
                    and isinstance(vil, (list, tuple)) and vil[0]
                ):
                    survey_count_map['%s_%s' % (pr[0], vil[0])] = int(row.get('__count') or 0)

        dots_by_pid = {}
        for pid in uniq_project_ids:
            row = dots_by_project.get(pid)
            if row is None:
                row = dots_by_project.get(str(pid))
            dots_by_pid[pid] = list(row or [])

        for block in subdiv_payload:
            for pr in block['projects']:
                pid = pr['id']
                pr['dots'] = dots_by_pid.get(pid, [])
                pr['pipeline_pct'] = _completion_pct_from_pipeline_dots(pr['dots'])
                project_survey_total = 0
                for v in pr['villages']:
                    key = '%s_%s' % (pid, v['id'])
                    vd = village_dots.get(key) or []
                    v['dots'] = list(vd)
                    v['pipeline_pct'] = _completion_pct_from_pipeline_dots(v['dots'])
                    v['survey_count'] = survey_count_map.get(key, 0)
                    project_survey_total += v['survey_count']
                pr['survey_count'] = project_survey_total
            block['summary'] = _subdiv_portfolio_summary(block['projects'])

        collectors_payload = []
        seen_collector_ids = set()
        for d_id, col in district_collector_map.items():
            if col.id in seen_collector_ids:
                continue
            seen_collector_ids.add(col.id)
            district = self.env['bhu.district'].browse(d_id)
            collectors_payload.append({
                'id': col.id,
                'label': self._collector_display_label(col, district.name if district else ''),
                'district_name': district.name if district else '',
            })

        return {
            'is_admin_view': can_see_all_subdiv,
            'can_impersonate_sdm': can_see_all_subdiv,
            'can_impersonate_collector': can_impersonate_collector,
            'collectors': collectors_payload,
            'subdivisions': subdiv_payload,
            'totals': {
                'subdivisions': len(subdiv_payload),
                'projects': len(uniq_project_ids),
                'villages': len(pairs),
            },
        }

    @api.model
    def get_pipeline_stage_window_action(self, stage_id, project_id, village_id=False):
        """Pipeline dot click → proper section list/form (not generic dashboard URL)."""
        return self.env['bhuarjan.dashboard.actions'].get_pipeline_stage_window_action(
            stage_id, project_id, village_id
        )

    @api.model
    def open_document_vault_navigator_for_project(self, project_id):
        """Open Doc Vault Viewer scoped to a project (used from SDM pipeline dashboard)."""
        pid = int(project_id or 0)
        if not pid:
            raise UserError(_('Project is required to open the document viewer.'))
        if not self.env['bhu.project'].browse(pid).exists():
            raise UserError(_('Project not found.'))
        Navigator = self.env['bhu.document.vault.navigator']
        return Navigator.with_context(active_project_id=pid).action_open_navigator()

    @api.model
    def get_login_as_sdm_url(self, user_id, redirect='/web'):
        """Return login-as URL for a sub-division SDM (leadership only)."""
        self._assert_can_impersonate()

        target = self.env['res.users'].browse(int(user_id))
        if not target.exists() or not target.active:
            raise UserError(_('SDM user not found or inactive.'))
        if not target.has_group('bhukhadan_core.group_bhuarjan_sdm'):
            raise UserError(_('Selected user is not an SDM.'))
        SubDiv = self.env['bhu.sub.division'].sudo()
        if not SubDiv.search_count([('user_id', '=', target.id)]):
            raise UserError(_('This user is not linked as SDM on any sub division.'))

        safe_redirect = (redirect or '/web').strip()
        if not safe_redirect.startswith('/'):
            safe_redirect = '/web'
        return '/bhuarjan/login_as/%s?redirect=%s' % (target.id, quote(safe_redirect))

    @api.model
    def _is_impersonatable_collector_user(self, user):
        """True for district Collectors only — never admins / district admins."""
        user = user.exists()
        if not user or not user.active or not user.district_id:
            return False
        if user.has_group('base.group_system') or user.has_group('bhukhadan_core.group_bhuarjan_admin'):
            return False
        if user.has_group('bhukhadan_core.group_bhuarjan_district_administrator'):
            return False
        if user.bhuarjan_role in ('administrator', 'district_administrator'):
            return False
        return (
            user.has_group('bhukhadan_core.group_bhuarjan_collector')
            or user.has_group('bhukhadan_core.group_bhuarjan_additional_collector')
        )

    @api.model
    def _collector_display_label(self, collector, district_name=''):
        """Human label for pipeline UI, e.g. Collector Raigarh."""
        if not collector:
            district_name = (district_name or '').strip()
            return f'Collector {district_name}'.strip() if district_name else 'Collector'
        name = (collector.display_name or '').strip()
        district_name = (district_name or '').strip()
        if name and 'collector' in name.lower():
            return name
        if district_name:
            return f'Collector {district_name}'
        return name or 'Collector'

    @api.model
    def _get_district_collector_map(self):
        """Map district id → primary Collector user (for impersonation UI)."""
        Users = self.env['res.users'].sudo()
        collector_group = self.env.ref('bhukhadan_core.group_bhuarjan_collector', raise_if_not_found=False)
        addl_group = self.env.ref('bhukhadan_core.group_bhuarjan_additional_collector', raise_if_not_found=False)
        group_ids = [g.id for g in (collector_group, addl_group) if g]
        if not group_ids:
            return {}

        collectors = Users.search([
            ('active', '=', True),
            ('district_id', '!=', False),
            ('groups_id', 'in', group_ids),
        ])
        district_map = {}
        for col in collectors.sorted(
            key=lambda u: (
                0 if u.has_group('bhukhadan_core.group_bhuarjan_collector') else 1,
                0 if u.bhuarjan_role == 'collector' else 1,
                (u.name or ''),
                u.id,
            )
        ):
            if not self._is_impersonatable_collector_user(col):
                continue
            d_id = col.district_id.id
            if d_id not in district_map:
                district_map[d_id] = col
        return district_map

    @api.model
    def _assert_can_impersonate(self):
        user = self.env.user
        allowed = (
            user.has_group('base.group_system')
            or user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        )
        if not allowed:
            raise AccessError(_('You are not allowed to login as another user.'))

    @api.model
    def _assert_can_impersonate_collector(self):
        user = self.env.user
        if not (
            user.has_group('base.group_system')
            or user.has_group('bhukhadan_core.group_bhuarjan_admin')
        ):
            raise AccessError(_('Only Administrator can login as Collector.'))

    @api.model
    def get_login_as_collector_url(self, user_id, redirect='/web'):
        """Return login-as URL for a district Collector (administrator only)."""
        self._assert_can_impersonate_collector()

        target = self.env['res.users'].browse(int(user_id))
        if not target.exists() or not target.active:
            raise UserError(_('Collector user not found or inactive.'))
        if not self._is_impersonatable_collector_user(target):
            raise UserError(_('Selected user is not a Collector.'))

        safe_redirect = (redirect or '/web').strip()
        if not safe_redirect.startswith('/'):
            safe_redirect = '/web'
        return '/bhuarjan/login_as/%s?redirect=%s' % (target.id, quote(safe_redirect))

    # ========== Legacy Methods (for backward compatibility) ==========
    # These methods redirect to generic methods above
    
    @api.model
    def get_sdm_dashboard_stats(self, department_id=None, project_id=None, village_id=None):
        """Legacy method name - redirects to get_dashboard_stats for backward compatibility"""
        return self.get_dashboard_stats(department_id, project_id, village_id)
    
    @api.model
    def get_all_projects_sdm(self):
        """Legacy method - redirects to get_user_projects()"""
        return self.get_user_projects()
    
    @api.model
    def get_all_projects_sdm_filtered(self, department_id=None):
        """Legacy method - redirects to get_user_projects(department_id)"""
        return self.get_user_projects(department_id)
    
    @api.model
    def get_villages_by_project_sdm(self, project_id):
        """Legacy method - redirects to get_villages_by_project(project_id)"""
        return self.get_villages_by_project(project_id)

