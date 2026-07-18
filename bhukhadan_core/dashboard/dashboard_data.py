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

    @api.model
    def ensure_sample_master_scope_xml(self):
        """Create baseline sample master scope via XML function import."""
        Department = self.env['bhu.department'].sudo()
        Project = self.env['bhu.project'].sudo()
        Village = self.env['bhu.village'].sudo()
        Tehsil = self.env['bhu.tehsil'].sudo()
        District = self.env['bhu.district'].sudo()

        dept = Department.search([('name', '=', 'Coal India Ltd.')], limit=1)
        if not dept:
            dept = Department.create({
                'name': 'Coal India Ltd.',
                'code': 'CIL',
                'icon': 'fa fa-industry',
                'description': 'Sample department for dashboard scope.',
            })

        village = Village.search([('name', '=', 'Hardibazar')], limit=1)
        if not village:
            tehsil = Tehsil.search([], limit=1)
            district = tehsil.district_id if tehsil and tehsil.district_id else District.search([], limit=1)
            vals = {
                'name': 'Hardibazar',
                'village_code': 'HARDIBAZAR',
                'village_type': 'rural',
            }
            if district:
                vals['district_id'] = district.id
            if tehsil:
                vals['tehsil_id'] = tehsil.id
            village = Village.create(vals)

        project = Project.search([
            ('name', '=', 'SECL Korba'),
            ('department_id', '=', dept.id),
        ], limit=1)
        if not project:
            project = Project.create({
                'name': 'SECL Korba',
                'code': 'SECL-KORBA',
                'department_id': dept.id,
                'state': 'active',
            })

        if village and village.id not in project.village_ids.ids:
            project.write({'village_ids': [(4, village.id)]})
        return True

    @api.model
    def apply_coal_runtime_gating(self):
        """Disable legacy NH/Railway law sections from active runtime use."""
        Section = self.env['bhu.section.master'].sudo()
        Law = self.env['bhu.law.master'].sudo()
        Project = self.env['bhu.project'].sudo()

        legacy_section_domain = [
            '|', '|',
            ('name', 'ilike', 'Railways'),
            ('name', 'ilike', '(NH)'),
            ('name', 'ilike', 'Sec 3A'),
        ]
        legacy_sections = Section.search(legacy_section_domain)
        if legacy_sections:
            legacy_sections.write({'active': False})

        legacy_laws = Law.search([
            '|',
            ('name', 'ilike', 'Railway'),
            ('name', 'ilike', 'National Highway'),
        ])
        if legacy_laws:
            legacy_laws.write({'active': False})

        # Section Master sync for coal-only mode:
        # keep only Coal Act sections active, hide legacy LARR/CGLRC/NH/Railways.
        coal_section_xmlids = [
            'bhukhadan_core.section_coal_surveys',
            'bhukhadan_core.section_coal_4',
            'bhukhadan_core.section_coal_7',
            'bhukhadan_core.section_coal_8',
            'bhukhadan_core.section_coal_9',
            'bhukhadan_core.section_coal_11',
            'bhukhadan_core.section_coal_land_records',
            'bhukhadan_core.section_coal_drrc',
            'bhukhadan_core.section_coal_asset_survey',
            'bhukhadan_core.section_coal_conduct_asset_survey',
            'bhukhadan_core.section_coal_compensation',
            'bhukhadan_core.section_coal_award',
        ]
        coal_sections = self.env['bhu.section.master'].sudo()
        for xmlid in coal_section_xmlids:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec and rec._name == 'bhu.section.master':
                coal_sections |= rec
        if coal_sections:
            (Section.search([('id', 'not in', coal_sections.ids)])).write({'active': False})
            coal_sections.write({'active': True})

        # Ensure existing projects without a configured law get Coal Act by default.
        coal_law = Law.search([('name', '=', 'Coal Bearing Areas (A&D) Act, 1957')], limit=1)
        if coal_law:
            Project.search([('law_master_id', '=', False)]).write({'law_master_id': coal_law.id})
            # Coal-only migration guard: remap legacy project laws to Coal law.
            legacy_projects = Project.search([
                ('law_master_id', '!=', False),
                '|', '|', '|',
                ('law_master_id.name', 'ilike', 'cglrc'),
                ('law_master_id.name', 'ilike', '247'),
                ('law_master_id.name', 'ilike', 'railway'),
                ('law_master_id.name', 'ilike', 'national highway'),
            ])
            if legacy_projects:
                legacy_projects.write({'law_master_id': coal_law.id})
        return True
