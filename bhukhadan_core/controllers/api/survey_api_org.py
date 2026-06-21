# -*- coding: utf-8 -*-
"""Org hierarchy: users, departments, projects"""
from odoo import http
from odoo.http import request, Response
from odoo.exceptions import ValidationError
import json
import logging
import base64
import re
from .main import *

import datetime

_logger = logging.getLogger(__name__)

from .survey_api_helpers import SurveyAPIHelperMixin, api_mobile_user_geography, api_mobile_user_village_ids


class SurveyAPIOrgController(SurveyAPIHelperMixin, http.Controller):
    """BhuKhadan REST API — users & org."""

    @http.route('/api/bhuarjan/user/projects', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_user_projects(self, **kwargs):
        """
        Get departments, projects, and villages mapped to a specific user
        Structure: Departments -> Projects -> Villages (only user's villages)
        Query params: user_id (required)
        Returns: JSON with departments, their projects, and villages (filtered by user's villages)
        """
        try:
            # Get query parameters
            user_id = request.httprequest.args.get('user_id', type=int)

            if not user_id:
                return Response(
                    json.dumps({'error': 'user_id is required'}),
                    status=400,
                    content_type='application/json'
                )

            # Get user and their villages
            user = request.env['res.users'].sudo().browse(user_id)
            if not user.exists():
                return Response(
                    json.dumps({'error': f'User with ID {user_id} not found'}),
                    status=404,
                    content_type='application/json'
                )

            user_village_ids = api_mobile_user_village_ids(request.env, user)
            user_info = {
                'id': user.id,
                'name': user.name,
                'login': user.login,
                'bhuarjan_role': user.bhuarjan_role or '',
            }

            # Debug logging
            _logger.info(f"get_user_projects: User {user_id} has {len(user_village_ids)} villages: {user_village_ids}")

            # If user has no villages, return empty structure
            if not user_village_ids:
                _logger.warning(f"get_user_projects: User {user_id} has no villages assigned")
                response_data = {
                    'success': True,
                    'data': [],
                    'user': user_info
                }
                return Response(
                    json.dumps(response_data),
                    status=200,
                    content_type='application/json'
                )

            # Start from user's villages and build the hierarchy: Village -> Project -> Department
            # Structure: Department -> Projects -> Villages
            
            # Map: village_id -> list of projects that contain it
            village_project_map = {}  # {village_id: [project1, project2, ...]}
            
            # Map: project_id -> set of departments
            project_department_map = {}  # {project_id: [dept1, dept2, ...]}
            
            # For each user village, find projects that contain it using domain-based search with sudo
            # This ensures we bypass any record rules that might prevent patwari users from accessing projects
            # Use skip_project_domain_filter context to bypass the _search override in project model
            for village_id in user_village_ids:
                village = request.env['bhu.village'].sudo().browse(village_id)
                if not village.exists():
                    _logger.warning(f"get_user_projects: Village {village_id} does not exist")
                    continue
                
                # Find projects that contain this village using domain search with sudo
                # Use skip_project_domain_filter to bypass the _search override that filters by SDM/Tehsildar
                # This bypasses record rules and access restrictions
                projects_for_village = request.env['bhu.project'].sudo().with_context(
                    skip_project_domain_filter=True
                ).search([
                    ('village_ids', 'in', [village_id])
                ])
                
                village_project_map[village_id] = projects_for_village
                _logger.info(f"get_user_projects: Village {village_id} ({village.name}) is in {len(projects_for_village)} projects: {projects_for_village.ids}")
                
                # Additional debug: Check if any projects exist at all and if they have villages
                if not projects_for_village:
                    # Try to find all projects and check their village_ids
                    all_projects_debug = request.env['bhu.project'].sudo().with_context(
                        skip_project_domain_filter=True
                    ).search([])
                    _logger.warning(f"get_user_projects: No projects found for village {village_id}. Total projects in system: {len(all_projects_debug)}")
                    # Check a few projects to see if they have villages
                    for proj in all_projects_debug[:5]:  # Check first 5 projects
                        proj_village_ids = proj.sudo().village_ids.ids
                        _logger.info(f"get_user_projects: Debug - Project {proj.id} ({proj.name}) has villages: {proj_village_ids}")
                
                # For each project, get its departments (M2M + project.department_id)
                for project in projects_for_village:
                    if project.id not in project_department_map:
                        dept_ids = []
                        if project.department_id:
                            dept_ids.append(project.department_id.id)
                        m2m_depts = request.env['bhu.department'].sudo().search([
                            ('project_ids', 'in', project.id),
                        ])
                        dept_ids.extend(m2m_depts.ids)
                        project_department_map[project.id] = list(dict.fromkeys(dept_ids))
                        _logger.info(
                            f"get_user_projects: Project {project.id} ({project.name}) "
                            f"has {len(project_department_map[project.id])} departments: "
                            f"{project_department_map[project.id]}"
                        )
            
            # If no projects found for any village
            all_found_projects = set()
            for projects in village_project_map.values():
                all_found_projects.update(projects.ids)
            
            if not all_found_projects:
                _logger.warning(f"get_user_projects: No projects found for any of user's villages. User villages: {user_village_ids}")
                response_data = {
                    'success': True,
                    'data': [],
                    'user': user_info,
                    'debug': {
                        'user_village_ids': user_village_ids,
                        'message': 'No projects found containing user\'s villages. Please ensure villages are mapped to projects.'
                    }
                }
                return Response(
                    json.dumps(response_data),
                    status=200,
                    content_type='application/json'
                )
            
            # Build department -> projects -> villages structure
            departments_dict = {}  # department_id -> department data with projects
            projects_without_dept = {}  # project_id -> project data (for projects without departments)
            
            # Get all unique departments
            all_department_ids = set()
            for dept_ids in project_department_map.values():
                all_department_ids.update(dept_ids)
            
            # Initialize department entries
            for dept_id in all_department_ids:
                dept = request.env['bhu.department'].sudo().browse(dept_id)
                if dept.exists():
                    departments_dict[dept_id] = {
                        'id': dept.id,
                        'name': dept.name,
                        'code': dept.code or '',
                        'projects': {}
                    }
            
            # Build the structure: for each village, add it to its projects, and projects to departments
            for village_id in user_village_ids:
                village = request.env['bhu.village'].sudo().browse(village_id)
                if not village.exists():
                    continue
                
                # Build village data
                village_data = {
                    'id': village.id,
                    'name': village.name,
                    'village_code': village.village_code or '',
                    'village_uuid': village.village_uuid or '',
                    'district_id': village.district_id.id if village.district_id else None,
                    'district_name': village.district_id.name if village.district_id else '',
                    'tehsil_id': village.tehsil_id.id if village.tehsil_id else None,
                    'tehsil_name': village.tehsil_id.name if village.tehsil_id else '',
                    'pincode': village.pincode or '',
                }
                
                # Get projects for this village
                projects_for_village = village_project_map.get(village_id, [])
                
                for project in projects_for_village:
                    # Get departments for this project
                    dept_ids = project_department_map.get(project.id, [])
                    
                    if dept_ids:
                        # Add to departments
                        for dept_id in dept_ids:
                            if dept_id in departments_dict:
                                # Initialize project in department if not exists
                                if project.id not in departments_dict[dept_id]['projects']:
                                    departments_dict[dept_id]['projects'][project.id] = {
                                        'id': project.id,
                                        'name': project.name,
                                        'code': project.code or '',
                                        'project_uuid': project.project_uuid or '',
                                        'description': project.description or '',
                                        'state': project.state,
                                        'villages': []
                                    }
                                # Add village to project
                                departments_dict[dept_id]['projects'][project.id]['villages'].append(village_data)
                    else:
                        # Project has no departments - add to "No Department" list
                        if project.id not in projects_without_dept:
                            projects_without_dept[project.id] = {
                                'id': project.id,
                                'name': project.name,
                                'code': project.code or '',
                                'project_uuid': project.project_uuid or '',
                                'description': project.description or '',
                                'state': project.state,
                                'villages': []
                            }
                        projects_without_dept[project.id]['villages'].append(village_data)
            
            # Convert projects dict to list in each department
            for dept_id in departments_dict:
                departments_dict[dept_id]['projects'] = list(departments_dict[dept_id]['projects'].values())
            
            # Add "No Department" entry if needed
            if projects_without_dept:
                departments_dict[0] = {
                    'id': 0,
                    'name': 'No Department / कोई विभाग नहीं',
                    'code': 'NO_DEPT',
                    'projects': list(projects_without_dept.values())
                }

            # Convert to list and sort by department name (put "No Department" at the end)
            result = sorted(
                departments_dict.values(), 
                key=lambda x: (x['id'] == 0, x['name'])  # No Department (id=0) goes last
            )

            # Sort projects within each department by name
            for dept in result:
                dept['projects'].sort(key=lambda x: x['name'])
            
            _logger.info(f"get_user_projects: Returning {len(result)} departments with projects")

            response_data = {
                'success': True,
                'data': result,
                'user': user_info
            }

            return Response(
                json.dumps(response_data),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_user_projects: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/users', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_all_users(self, **kwargs):
        """
        Get all users with their details
        Query params: limit, offset, role (optional filter by bhuarjan_role)
        Returns: JSON list of users
        """
        try:
            # Get query parameters
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0
            role = request.httprequest.args.get('role')

            # Build domain
            domain = []
            if role:
                domain.append(('bhuarjan_role', '=', role))

            # Search users
            users = request.env['res.users'].sudo().search(domain, limit=limit, offset=offset, order='name')

            # Build response
            users_data = []
            for user in users:
                villages_rec, tehsils_rec, subdivisions_rec = api_mobile_user_geography(request.env, user)

                villages_data = []
                for village in villages_rec:
                    villages_data.append({
                        'id': village.id,
                        'name': village.name,
                        'village_code': village.village_code or '',
                    })

                tehsils_data = []
                for tehsil in tehsils_rec:
                    tehsils_data.append({
                        'id': tehsil.id,
                        'name': tehsil.name,
                    })

                sub_divisions_data = []
                for sub_div in subdivisions_rec:
                    sub_divisions_data.append({
                        'id': sub_div.id,
                        'name': sub_div.name,
                    })

                users_data.append({
                    'id': user.id,
                    'name': user.name,
                    'name_english': user.name_english or '',
                    'login': user.login,
                    'email': user.email or '',
                    'mobile': user.mobile or '',
                    'bhuarjan_role': user.bhuarjan_role or '',
                    'state_id': user.state_id.id if user.state_id else None,
                    'state_name': user.state_id.name if user.state_id else '',
                    'district_id': user.district_id.id if user.district_id else None,
                    'district_name': user.district_id.name if user.district_id else '',
                    'parent_id': user.parent_id.id if user.parent_id else None,
                    'parent_name': user.parent_id.name if user.parent_id else '',
                    'villages': villages_data,
                    'tehsils': tehsils_data,
                    'sub_divisions': sub_divisions_data,
                    'active': user.active,
                })

            # Get total count
            total_count = request.env['res.users'].sudo().search_count(domain)

            return Response(
                json.dumps({
                    'success': True,
                    'data': users_data,
                    'total': total_count,
                    'limit': limit,
                    'offset': offset
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_all_users: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/users/autocomplete', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def autocomplete_users(self, **kwargs):
        """
        Autocomplete API for users based on username/name
        Query params: q (search query - minimum 3 characters required), limit (optional, default: 20, max: 50)
        Returns: JSON list of matching users with id, name, login, email, mobile
        """
        try:
            # Get query parameters
            query = request.httprequest.args.get('q', '').strip()
            limit = min(request.httprequest.args.get('limit', type=int) or 20, 50)  # Default 20, max 50
            
            # Validate minimum query length
            if len(query) < 3:
                return Response(
                    json.dumps({
                        'success': True,
                        'data': [],
                        'message': 'Please enter at least 3 characters to search',
                        'total': 0
                    }),
                    status=200,
                    content_type='application/json'
                )
            
            # Build search domain - name, login, English name
            domain = [
                '|', '|',
                ('name', 'ilike', query),
                ('login', 'ilike', query),
                ('name_english', 'ilike', query),
            ]
            
            # Only search active users
            domain.append(('active', '=', True))
            
            # Search users
            users = request.env['res.users'].sudo().search(domain, limit=limit, order='name')
            
            # Build response - simplified user objects for autocomplete
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'name': user.name or '',
                    'name_english': user.name_english or '',
                    'login': user.login or '',
                    'email': user.email or '',
                    'mobile': user.mobile or '',
                    'display_name': f"{user.name} ({user.login})" if user.name and user.login else (user.name or user.login or ''),
                })
            
            # Get total count (for pagination info, but we limit results)
            total_count = request.env['res.users'].sudo().search_count(domain)
            
            return Response(
                json.dumps({
                    'success': True,
                    'data': users_data,
                    'total': total_count,
                    'limit': limit,
                    'query': query
                }),
                status=200,
                content_type='application/json'
            )
            
        except Exception as e:
            _logger.error(f"Error in autocomplete_users: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'Internal server error',
                    'message': str(e)
                }),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/departments', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_departments(self, **kwargs):
        """
        Get all departments
        Query params: limit, offset
        Returns: JSON list of departments
        """
        try:
            # Get query parameters
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0

            # Search departments
            departments = request.env['bhu.department'].sudo().search([], limit=limit, offset=offset, order='name')

            # Build response
            departments_data = []
            for dept in departments:
                departments_data.append({
                    'id': dept.id,
                    'name': dept.name,
                    'code': dept.code or '',
                    'description': dept.description or '',
                    'head_of_department': dept.head_of_department or '',
                    'contact_number': dept.contact_number or '',
                    'email': dept.email or '',
                    'address': dept.address or '',
                })

            # Get total count
            total_count = request.env['bhu.department'].sudo().search_count([])

            return Response(
                json.dumps({
                    'success': True,
                    'data': departments_data,
                    'total': total_count,
                    'limit': limit,
                    'offset': offset
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_all_departments: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/departments/<int:department_id>/projects', type='http', auth='public', methods=['GET'], csrf=False)
    def get_department_projects(self, department_id, **kwargs):
        """
        Get all projects in a department with village objects
        Path param: department_id (required)
        Query params: user_id (optional), limit, offset
        Returns: JSON list of projects with village objects (filtered by user if user_id provided)
        """
        try:
            # Validate department exists
            department = request.env['bhu.department'].sudo().browse(department_id)
            if not department.exists():
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Department not found',
                        'message': f'Department with ID {department_id} does not exist'
                    }),
                    status=404,
                    content_type='application/json'
                )

            # Get query parameters
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0
            user_id = request.httprequest.args.get('user_id', type=int)

            # Get user's villages if user_id is provided
            user_village_ids = []
            user_info = None
            if user_id:
                user = request.env['res.users'].sudo().browse(user_id)
                if not user.exists():
                    return Response(
                        json.dumps({
                            'success': False,
                            'error': 'User not found',
                            'message': f'User with ID {user_id} does not exist'
                        }),
                        status=404,
                        content_type='application/json'
                    )
                user_village_ids = api_mobile_user_village_ids(request.env, user)
                user_info = {
                    'id': user.id,
                    'name': user.name,
                    'login': user.login,
                    'bhuarjan_role': user.bhuarjan_role or '',
                }

            # Get projects from department
            projects = department.project_ids.sudo()
            total_count = len(projects)

            # Apply pagination
            paginated_projects = projects[offset:offset + limit] if projects else []

            # Build response
            projects_data = []
            for project in paginated_projects:
                # Filter villages based on user if user_id provided
                if user_id and user_village_ids:
                    project_villages = project.village_ids.filtered(
                        lambda v: v.id in user_village_ids
                    )
                else:
                    project_villages = project.village_ids
                
                # Build village objects
                villages_data = []
                for village in project_villages:
                    villages_data.append({
                        'id': village.id,
                        'name': village.name or '',
                        'village_code': village.village_code or '',
                        'village_uuid': village.village_uuid or '',
                        'district_id': village.district_id.id if village.district_id else None,
                        'district_name': village.district_id.name if village.district_id else '',
                        'tehsil_id': village.tehsil_id.id if village.tehsil_id else None,
                        'tehsil_name': village.tehsil_id.name if village.tehsil_id else '',
                        'pincode': village.pincode or '',
                    })
                
                projects_data.append({
                    'id': project.id,
                    'name': project.name or '',
                    'code': project.code or '',
                    'description': project.description or '',
                    'state': project.state or '',
                    'project_uuid': project.project_uuid or '',
                    'villages': villages_data,
                    'village_count': len(villages_data),
                })

            response_data = {
                'success': True,
                'data': projects_data,
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'department_id': department_id,
                'department_name': department.name or ''
            }
            
            # Include user info if user_id was provided
            if user_info:
                response_data['user'] = user_info

            return Response(
                json.dumps(response_data),
                status=200,
                content_type='application/json'
            )

        except ValueError as e:
            _logger.error(f"Error in get_department_projects: Invalid department_id: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'Invalid department ID',
                    'message': 'department_id must be a valid integer'
                }),
                status=400,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error in get_department_projects: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                status=500,
                content_type='application/json'
            )

