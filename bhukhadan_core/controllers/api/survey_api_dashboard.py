# -*- coding: utf-8 -*-
"""Dashboard statistics"""
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


class SurveyAPIDashboardController(SurveyAPIHelperMixin, http.Controller):
    """BhuKhadan REST API — dashboard."""

    @http.route('/api/bhuarjan/dashboard/village', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_village_dashboard(self, **kwargs):
        """
        Get survey statistics dashboard for a village
        Query params: village_id (required)
        Returns: JSON with survey counts by state (total_surveys, approved, rejected, pending)
        Note: pending includes only submitted surveys (not rejected)
        """
        try:
            village_id = request.httprequest.args.get('village_id', type=int)
            
            if not village_id:
                return Response(
                    json.dumps({'error': 'village_id is required'}),
                    status=400,
                    content_type='application/json'
                )

            # Verify village exists
            village = request.env['bhu.village'].sudo().browse(village_id)
            if not village.exists():
                return Response(
                    json.dumps({'error': f'Village with ID {village_id} not found'}),
                    status=404,
                    content_type='application/json'
                )

            # Get all surveys for this village
            all_surveys = request.env['bhu.survey'].sudo().search([('village_id', '=', village_id)])
            
            # Count surveys by state
            total_surveys = len(all_surveys)
            submitted_count = len(all_surveys.filtered(lambda s: s.state == 'submitted'))
            approved_count = len(all_surveys.filtered(lambda s: s.state == 'approved'))
            rejected_count = len(all_surveys.filtered(lambda s: s.state == 'rejected'))
            
            # Pending = Only Submitted surveys (not rejected)
            pending_count = submitted_count

            # Build response
            dashboard_data = {
                'village_id': village_id,
                'village_name': village.name or '',
                'village_code': village.village_code or '',
                'statistics': {
                    'total_surveys': total_surveys,
                    'approved': approved_count,
                    'rejected': rejected_count,
                    'pending': pending_count
                }
            }

            return Response(
                json.dumps({
                    'success': True,
                    'data': dashboard_data
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_village_dashboard: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )
