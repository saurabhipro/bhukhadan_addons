# -*- coding: utf-8 -*-
"""Reference data: channels, land types, trees"""
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

from .survey_api_helpers import SurveyAPIHelperMixin


class SurveyAPIReferenceController(SurveyAPIHelperMixin, http.Controller):
    """BhuKhadan REST API — masters / reference."""

    @http.route('/api/bhuarjan/land-types', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_land_types(self, **kwargs):
        """
        Get all land types
        Query params: limit, offset, active (optional filter - default True)
        Returns: JSON list of land types
        """
        try:
            # Get query parameters
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0
            active_filter = request.httprequest.args.get('active')
            
            # Build domain - filter by active if specified
            domain = []
            if active_filter is not None:
                active_bool = active_filter.lower() in ('true', '1', 'yes')
                domain.append(('active', '=', active_bool))
            else:
                # Default to active only
                domain.append(('active', '=', True))

            # Search land types
            land_types = request.env['bhu.land.type'].sudo().search(domain, limit=limit, offset=offset, order='name')

            # Build response
            land_types_data = []
            for land_type in land_types:
                land_types_data.append({
                    'id': land_type.id,
                    'name': land_type.name or '',
                    'code': land_type.code or '',
                    'description': land_type.description or '',
                    'active': land_type.active,
                })

            # Get total count
            total_count = request.env['bhu.land.type'].sudo().search_count(domain)

            return Response(
                json.dumps({
                    'success': True,
                    'data': land_types_data,
                    'total': total_count,
                    'limit': limit,
                    'offset': offset
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_all_land_types: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/trees', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_trees(self, **kwargs):
        """
        Get all tree masters with optional filters by name, development stage, and girth
        Query params: 
            - type (optional): Filter by tree type. Values: 'fruit_bearing' or 'non_fruit_bearing'
            - name (optional): Filter by tree name (partial match, case-insensitive)
            - development_stage (optional): Filter by development stage (for rate lookup)
                Values: 'undeveloped', 'semi_developed', 'fully_developed'
            - girth_cm (optional): Girth in cm to lookup rate (requires development_stage)
            - limit (optional, default 100)
            - offset (optional, default 0)
        Returns: JSON list of tree masters with rates (rate populated if development_stage and girth_cm provided)
        """
        try:
            # Get query parameters
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0
            name_filter = request.httprequest.args.get('name', '').strip()
            tree_type_filter = request.httprequest.args.get('type', '').strip().lower()
            development_stage = request.httprequest.args.get('development_stage', '').strip().lower()
            girth_cm = request.httprequest.args.get('girth_cm', type=float)
            
            # Validate tree_type if provided
            valid_tree_types = ['fruit_bearing', 'non_fruit_bearing']
            if tree_type_filter and tree_type_filter not in valid_tree_types:
                return Response(
                    json.dumps({
                        'error': f'Invalid type: {tree_type_filter}. Must be one of: {", ".join(valid_tree_types)}'
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Validate development_stage if provided
            valid_stages = ['undeveloped', 'semi_developed', 'fully_developed']
            if development_stage and development_stage not in valid_stages:
                return Response(
                    json.dumps({
                        'error': f'Invalid development_stage: {development_stage}. Must be one of: {", ".join(valid_stages)}'
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Build domain
            domain = []
            # Filter by tree_type
            if tree_type_filter:
                domain.append(('tree_type', '=', tree_type_filter))
            
            # Filter by name (partial match, case-insensitive)
            if name_filter:
                domain.append(('name', 'ilike', name_filter))

            # Search tree masters - sort by tree_type first, then by name
            trees = request.env['bhu.tree.master'].sudo().search(domain, limit=limit, offset=offset, order='tree_type, name')

            # Build response
            trees_data = []
            for tree in trees:
                tree_data = {
                    'id': tree.id,
                    'name': tree.name or '',
                    'tree_type': tree.tree_type,
                    'rate': None  # Rate will be determined from tree_rate_ids
                }
                
                # If development_stage and girth are specified, lookup rate from tree_rate_master
                # This works for both fruit-bearing and non-fruit-bearing trees now
                if development_stage and girth_cm:
                    rate_master = request.env['bhu.tree.rate.master']
                    tree_data['rate'] = rate_master.get_rate_for_tree(
                        tree.id,
                        girth_cm,
                        development_stage
                    )
                
                trees_data.append(tree_data)

            # Get total count
            total_count = request.env['bhu.tree.master'].sudo().search_count(domain)

            return Response(
                json.dumps({
                    'success': True,
                    'data': trees_data,
                    'total': total_count,
                    'count': len(trees_data),
                    'limit': limit,
                    'offset': offset,
                    'filters': {
                        'type': tree_type_filter if tree_type_filter else None,
                        'name': name_filter if name_filter else None,
                        'development_stage': development_stage if development_stage else None
                    }
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_all_trees: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

