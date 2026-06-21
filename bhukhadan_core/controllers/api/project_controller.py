# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json


class ProjectController(http.Controller):

    @http.route('/bhuarjan/project/switch', type='json', auth='user', methods=['POST'])
    def switch_project(self, project_id=None):
        """Switch current project for the user"""
        if project_id:
            # Store project ID in user's session
            request.session['bhuarjan_current_project_id'] = str(project_id)
            return {'success': True, 'project_id': project_id}
        return {'success': False}

    @http.route('/bhuarjan/project/current', type='json', auth='user', methods=['GET'])
    def get_current_project(self):
        """Get current project ID from session"""
        project_id = request.session.get('bhuarjan_current_project_id', '0')
        return {'project_id': project_id}

    @http.route('/bhuarjan/project/list', type='json', auth='user', methods=['GET'])
    def get_project_list(self):
        """Get list of available projects"""
        projects = request.env['bhu.project'].search([])
        project_list = []
        for project in projects:
            project_list.append({
                'id': project.id,
                'name': project.name,
                'description': project.description or ''
            })
        return {'projects': project_list}
