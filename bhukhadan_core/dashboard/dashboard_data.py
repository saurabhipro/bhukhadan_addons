# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class DashboardData(models.AbstractModel):
    """Dashboard data fetching methods"""
    _name = 'bhuarjan.dashboard.data'
    _description = 'Dashboard Data Methods'

    @api.model
    def get_all_departments(self):
        """Get all departments for dropdown - merged from sdm_dashboard with SDM filtering"""
        user = self.env.user
        # Department users see only their mapped department
        if user.has_group('bhukhadan_core.group_bhuarjan_department_user'):
            assigned_projects = self.env['bhu.project'].search([('department_user_ids', 'in', user.id)])
            if not assigned_projects:
                return []
            department_ids = [d for d in assigned_projects.mapped('department_id').ids if d]
            if not department_ids:
                return []
            departments = self.env['bhu.department'].search([('id', 'in', department_ids)])
        # Admin, system users, collectors, district administrators see all departments
        elif (user.has_group('bhukhadan_core.group_bhuarjan_admin') or 
              user.has_group('base.group_system') or
              user.has_group('bhukhadan_core.group_bhuarjan_collector') or
              user.has_group('bhukhadan_core.group_bhuarjan_additional_collector') or
              user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')):
            # Show all departments for admin/system/collector/district admin
            departments = self.env['bhu.department'].search([])
        else:
            # For SDM/Tehsildar users, only show departments where they have accessible projects
            if user.has_group('bhukhadan_core.group_bhuarjan_sdm'):
                project_ids = self._get_sdm_project_ids()
                assigned_projects = self.env['bhu.project'].browse(project_ids)
            else:
                assigned_projects = self.env['bhu.project'].search([
                    '|', '|',
                    ('sdm_ids', 'in', [user.id]),
                    ('tehsildar_ids', 'in', [user.id]),
                    ('sub_division_id.user_id', 'in', [user.id]),
                ])
            if assigned_projects:
                # Get unique department IDs from assigned projects
                department_ids = assigned_projects.mapped('department_id').ids
                if department_ids:
                    departments = self.env['bhu.department'].search([('id', 'in', department_ids)])
                else:
                    # No departments found, return empty list
                    return []
            else:
                # No assigned projects, return empty list
                return []
        return [{
            'id': dept.id,
            'name': dept.name,
            'code': dept.code or '',
            'icon': (dept.icon or '').strip(),
            'department_has_logo': bool(dept.department_logo),
        } for dept in departments]
    @api.model
    def get_all_projects(self, department_id=None):
        """Get projects accessible to current user, optionally filtered by department
        
        NOTE: This method is now handled by dashboard_stats.get_user_projects()
        which uses unified access logic. This method is kept for backward compatibility.
        
        Args:
            department_id: Optional department ID to filter by
            
        Returns:
            list: List of project dictionaries with 'id' and 'name'
        """
        # The unified method get_user_projects() from dashboard_stats will be used
        # when called on bhuarjan.dashboard model (which inherits from both)
        # This is a fallback for direct calls to dashboard_data model
        user = self.env.user
        domain = []
        # Filter by user's assigned projects (if not admin)
        if not user.has_group('bhukhadan_core.group_bhuarjan_admin') and not user.has_group('base.group_system'):
            # Get user's assigned projects
            assigned_projects = self.env['bhu.project'].search([
                '|',
                ('sdm_ids', 'in', user.id),
                ('tehsildar_ids', 'in', user.id)
            ])
            if assigned_projects:
                domain.append(('id', 'in', assigned_projects.ids))
            else:
                # No assigned projects, return empty list
                return []
        # Filter by department if provided
        if department_id:
            if domain:
                domain = ['&', ('department_id', '=', department_id)] + domain
            else:
                domain = [('department_id', '=', department_id)]
        projects = self.env["bhu.project"].search(domain)
        return projects.read(["id", "name"])
    
    @api.model
    def get_department_user_department(self):
        """Get the department for department user - first from user's department_id field, then from assigned projects"""
        user = self.env.user
        _logger.info(f"Getting department for user: {user.id} ({user.name})")
        # Check if user has department_user group
        has_group = user.has_group('bhukhadan_core.group_bhuarjan_department_user')
        _logger.info(f"User has department_user group: {has_group}")
        if not has_group:
            _logger.warning(f"User {user.id} ({user.name}) does not have department_user group")
            return None
        projects = self.env['bhu.project'].search([('department_user_ids', 'in', user.id)], limit=1)
        if not projects or not projects.department_id:
            return None
        dept = projects.department_id
        return {
            'id': dept.id,
            'name': dept.name,
            'code': dept.code or '',
            'icon': (dept.icon or '').strip(),
            'department_has_logo': bool(dept.department_logo),
        }
    @api.model
    def get_department_user_projects(self, department_id=None):
        """Get mapped projects for department user, optionally filtered by department"""
        user = self.env.user
        _logger.info(f"Getting projects for department user: {user.id} ({user.name})")
        if not user.has_group('bhukhadan_core.group_bhuarjan_department_user'):
            _logger.warning(f"User {user.id} does not have department_user group")
            return []
        domain = [('department_user_ids', 'in', user.id)]
        if department_id:
            domain = ['&', ('department_id', '=', int(department_id))] + domain
        projects = self.env['bhu.project'].search(domain)
        _logger.info(f"Found {len(projects)} projects for user {user.id}")
        # Read project data including department_id
        project_data = projects.read(["id", "name", "department_id"])
        # Log each project and its department
        for proj in project_data:
            dept_id = proj.get('department_id')
            if dept_id:
                dept_name = dept_id[1] if isinstance(dept_id, (list, tuple)) else 'Unknown'
                _logger.info(f"  Project: {proj['name']} (ID: {proj['id']}), Department: {dept_name}")
            else:
                _logger.warning(f"  Project: {proj['name']} (ID: {proj['id']}) has NO department")
        return project_data
    # NOTE: get_dashboard_stats() method has been moved to dashboard_stats.py
    # The unified method in dashboard_stats.py handles all dashboard types
    # This method is removed to avoid conflicts - dashboard_stats.get_dashboard_stats() will be used
    @api.model
    def get_role_based_dashboard_action(self):
        """Return the appropriate dashboard action based on user role.
        This method is called by RoleBasedDashboard client action to route users.
        """
        # Get current user
        user = self.env.user
        # Get sudoed user for field reading if necessary
        user_sudo = user.sudo()
        role = getattr(user_sudo, 'bhuarjan_role', False)
        
        # 1. Admin / System - Highest priority
        is_admin = role == 'administrator' or user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system')
        if is_admin:
            return {
                'type': 'ir.actions.client',
                'tag': 'bhukhadan_core.admin_dashboard',
                'name': 'Admin Dashboard',
            }
            
        # 2. Department User - High priority
        is_dept_by_role = role == 'department_user'
        is_dept_by_group = user.has_group('bhukhadan_core.group_bhuarjan_department_user')
        is_dept_by_project = self.env['bhu.project'].sudo().search_count([('department_user_ids', 'in', user.id)], limit=1) > 0
        
        if is_dept_by_role or is_dept_by_group or is_dept_by_project:
            return {
                'type': 'ir.actions.client',
                'tag': 'bhukhadan_core.department_dashboard',
                'name': 'Department User Dashboard',
            }
            
        # 3. Collector / Additional Collector
        is_collector = role in ['collector', 'additional_collector'] or \
                       user.has_group('bhukhadan_core.group_bhuarjan_collector') or \
                       user.has_group('bhukhadan_core.group_bhuarjan_additional_collector')
        if is_collector:
            return {
                'type': 'ir.actions.client',
                'tag': 'bhukhadan_core.collector_dashboard',
                'name': 'Collector Dashboard',
            }
            
        # 4. District Admin
        is_district_admin = role == 'district_administrator' or user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        if is_district_admin:
            return {
                'type': 'ir.actions.client',
                'tag': 'bhukhadan_core.district_dashboard',
                'name': 'District Admin Dashboard',
            }
            
        # 5. SDM / Patwari fallback
        is_sdm = role == 'sdm' or user.has_group('bhukhadan_core.group_bhuarjan_sdm')
        if is_sdm:
            return {
                'type': 'ir.actions.client',
                'tag': 'bhukhadan_core.sdm_dashboard_tag',
                'name': 'SDM Dashboard',
            }
            
        # Final fallback - Default to SDM dashboard for any other internal user
        return {
            'type': 'ir.actions.client',
            'tag': 'bhukhadan_core.sdm_dashboard_tag',
            'name': 'SDM Dashboard',
        }
    
    @api.model
    def save_dashboard_selection(self, project_id, village_id):
        """Save user's last selected project and village for bulk approval"""
        user = self.env.user
        
        # Store in user context or preferences
        self.env['ir.config_parameter'].sudo().set_param(
            f'bhukhadan_core.last_project.user_{user.id}', project_id or ''
        )
        self.env['ir.config_parameter'].sudo().set_param(
            f'bhukhadan_core.last_village.user_{user.id}', village_id or ''
        )
        return True
    
    @api.model
    def get_dashboard_selection(self):
        """Get user's last selected project and village for bulk approval"""
        user = self.env.user
        project_id = self.env['ir.config_parameter'].sudo().get_param(
            f'bhukhadan_core.last_project.user_{user.id}', default=False
        )
        village_id = self.env['ir.config_parameter'].sudo().get_param(
            f'bhukhadan_core.last_village.user_{user.id}', default=False
        )
        
        return {
            'project_id': int(project_id) if project_id and project_id.isdigit() else False,
            'village_id': int(village_id) if village_id and village_id.isdigit() else False,
        }
