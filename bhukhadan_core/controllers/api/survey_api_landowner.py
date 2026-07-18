# -*- coding: utf-8 -*-
"""Landowner REST API (create, list, update)."""
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


class SurveyAPILandownerController(SurveyAPIHelperMixin, http.Controller):
    """Landowner REST API (/api/bhuarjan/landowner*). Form 10 PDF: survey_form10_pdf_api."""

    @http.route(['/api/bhuarjan/landowner', '/api/bhuarjan/landowners'], type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def create_landowner(self, **kwargs):
        """
        Create a new landowner
        Accepts: JSON data with landowner fields
        Returns: Created landowner details
        """
        try:
            # Parse request data
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')

            # Prepare landowner values
            # Convert string IDs to integers if provided as strings
            village_id = data.get('village_id')
            if village_id:
                try:
                    village_id = int(village_id) if isinstance(village_id, str) else village_id
                except (ValueError, TypeError):
                    village_id = None
            
            landowner_vals = {
                'name': data.get('name'),
                'father_name': data.get('father_name'),
                'mother_name': data.get('mother_name'),
                'spouse_name': data.get('spouse_name'),
                'caste': data.get('caste'),
                'phone': data.get('phone'),
                'village_id': village_id,
                'rakba': data.get('rakba'),
                'aadhar_number': data.get('aadhar_number'),
                'bank_name': data.get('bank_name'),
                'bank_branch': data.get('bank_branch'),
                'account_number': data.get('account_number'),
                'ifsc_code': data.get('ifsc_code'),
                'account_holder_name': data.get('account_holder_name'),
            }
            
            # Remove None values for ID fields only (to avoid invalid references)
            landowner_vals = {k: v for k, v in landowner_vals.items()
                            if v is not None or k not in ['village_id']}

            # Handle document uploads if provided (base64 encoded)
            if data.get('aadhar_card'):
                try:
                    aadhar_data = data['aadhar_card']
                    if isinstance(aadhar_data, str):
                        if ',' in aadhar_data:
                            aadhar_data = aadhar_data.split(',')[1]
                        landowner_vals['aadhar_card'] = base64.b64decode(aadhar_data)
                except Exception as e:
                    _logger.warning(f"Error processing Aadhar card: {str(e)}")

            if data.get('pan_card'):
                try:
                    pan_data = data['pan_card']
                    if isinstance(pan_data, str):
                        if ',' in pan_data:
                            pan_data = pan_data.split(',')[1]
                        landowner_vals['pan_card'] = base64.b64decode(pan_data)
                except Exception as e:
                    _logger.warning(f"Error processing PAN card: {str(e)}")

            # Create landowner
            landowner = request.env['bhu.landowner'].sudo().create(landowner_vals)

            # Return created landowner details
            return Response(
                json.dumps({
                    'success': True,
                    'data': {
                        'id': landowner.id,
                        'name': landowner.name,
                        'father_name': landowner.father_name or '',
                        'mother_name': landowner.mother_name or '',
                        'spouse_name': landowner.spouse_name or '',
                        'caste': landowner.caste or '',
                        'aadhar_number': landowner.aadhar_number or '',
                        'phone': landowner.phone or '',
                        'village_id': landowner.village_id.id if landowner.village_id else None,
                        'village_name': landowner.village_id.name if landowner.village_id else '',
                        'rakba': landowner.rakba or '',
                    }
                }),
                status=201,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in create_landowner: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/landowners', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_landowners(self, **kwargs):
        """
        Get landowners based on survey_id and/or village_id (both optional)
        Query params: survey_id (optional), village_id (optional), limit (optional, default 100), offset (optional, default 0)
        Returns: JSON list of landowners
        """
        try:
            survey_id = request.httprequest.args.get('survey_id', type=int)
            village_id = request.httprequest.args.get('village_id', type=int)
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0

            domain = []
            
            # Filter by survey_id if provided
            if survey_id:
                survey = request.env['bhu.survey'].sudo().browse(survey_id)
                if not survey.exists():
                    return Response(
                        json.dumps({'error': f'Survey with ID {survey_id} not found'}),
                        status=404,
                        content_type='application/json'
                    )
                # Get landowners from the survey
                domain.append(('survey_id', '=', survey_id))
            
            # Filter by village_id if provided
            if village_id:
                village = request.env['bhu.village'].sudo().browse(village_id)
                if not village.exists():
                    return Response(
                        json.dumps({'error': f'Village with ID {village_id} not found'}),
                        status=404,
                        content_type='application/json'
                    )
                domain.append(('village_id', '=', village_id))

            landowners = request.env['bhu.landowner'].sudo().search(domain, limit=limit, offset=offset, order='name')

            landowners_data = []
            for landowner in landowners:
                landowners_data.append({
                    'id': landowner.id,
                    'name': landowner.name or '',
                    'father_name': landowner.father_name or '',
                    'mother_name': landowner.mother_name or '',
                    'spouse_name': landowner.spouse_name or '',
                    'caste': landowner.caste or '',
                    'phone': landowner.phone or '',
                    'village_id': landowner.village_id.id if landowner.village_id else None,
                    'village_name': landowner.village_id.name if landowner.village_id else '',
                    'rakba': landowner.rakba or '',
                    'aadhar_number': landowner.aadhar_number or '',
                    'bank_name': landowner.bank_name or '',
                    'bank_branch': landowner.bank_branch or '',
                    'account_number': landowner.account_number or '',
                    'ifsc_code': landowner.ifsc_code or '',
                    'account_holder_name': landowner.account_holder_name or '',
                    'survey_id': landowner.survey_id.id if landowner.survey_id else None,
                })

            total_count = request.env['bhu.landowner'].sudo().search_count(domain)

            return Response(
                json.dumps({
                    'success': True,
                    'data': landowners_data,
                    'total': total_count,
                    'limit': limit,
                    'offset': offset
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_landowners: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/landowner/<int:landowner_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    @check_permission
    def update_landowner(self, landowner_id, **kwargs):
        """
        Update an existing landowner
        Path param: landowner_id (required)
        Accepts: JSON data with landowner fields to update
        Returns: Updated landowner details
        """
        try:
            # Parse request data
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            
            # Find the landowner
            landowner = request.env['bhu.landowner'].sudo().browse(landowner_id)
            if not landowner.exists():
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'NOT_FOUND',
                        'error_code': 'LANDOWNER_NOT_FOUND',
                        'message': f'Landowner with ID {landowner_id} not found',
                        'fields': ['landowner_id']
                    }),
                    status=404,
                    content_type='application/json'
                )
            
            # Prepare landowner values for update
            # Convert string IDs to integers if provided as strings
            village_id = data.get('village_id')
            if village_id is not None:
                try:
                    village_id = int(village_id) if isinstance(village_id, str) else village_id
                except (ValueError, TypeError):
                    village_id = None
            
            # Build update values - only include fields that are provided in the request
            landowner_vals = {}
            
            # Text fields - include if provided (even if empty string)
            if 'name' in data:
                landowner_vals['name'] = data.get('name')
            if 'father_name' in data:
                landowner_vals['father_name'] = data.get('father_name')
            if 'mother_name' in data:
                landowner_vals['mother_name'] = data.get('mother_name')
            if 'spouse_name' in data:
                landowner_vals['spouse_name'] = data.get('spouse_name')
            if 'caste' in data:
                landowner_vals['caste'] = data.get('caste')
            if 'phone' in data:
                landowner_vals['phone'] = data.get('phone')
            if 'aadhar_number' in data:
                landowner_vals['aadhar_number'] = data.get('aadhar_number')
            if 'rakba' in data:
                landowner_vals['rakba'] = data.get('rakba')
            if 'bank_name' in data:
                landowner_vals['bank_name'] = data.get('bank_name')
            if 'bank_branch' in data:
                landowner_vals['bank_branch'] = data.get('bank_branch')
            if 'account_number' in data:
                landowner_vals['account_number'] = data.get('account_number')
            if 'ifsc_code' in data:
                landowner_vals['ifsc_code'] = data.get('ifsc_code')
            if 'account_holder_name' in data:
                landowner_vals['account_holder_name'] = data.get('account_holder_name')
            
            # Integer and selection fields - age and gender removed
            
            # ID fields - only include if provided and valid
            if village_id is not None:
                # Validate village exists
                village = request.env['bhu.village'].sudo().browse(village_id)
                if village.exists():
                    landowner_vals['village_id'] = village_id
                else:
                    return Response(
                        json.dumps({
                            'success': False,
                            'error': 'VALIDATION_ERROR',
                            'error_code': 'INVALID_VILLAGE_ID',
                            'message': f'Village with ID {village_id} not found',
                            'fields': ['village_id']
                        }),
                        status=400,
                        content_type='application/json'
                    )
            
            # Handle document uploads if provided (base64 encoded)
            if 'aadhar_card' in data and data.get('aadhar_card'):
                try:
                    aadhar_data = data['aadhar_card']
                    if isinstance(aadhar_data, str):
                        if ',' in aadhar_data:
                            aadhar_data = aadhar_data.split(',')[1]
                        landowner_vals['aadhar_card'] = base64.b64decode(aadhar_data)
                except Exception as e:
                    _logger.warning(f"Error processing Aadhar card: {str(e)}")
            
            if 'pan_card' in data and data.get('pan_card'):
                try:
                    pan_data = data['pan_card']
                    if isinstance(pan_data, str):
                        if ',' in pan_data:
                            pan_data = pan_data.split(',')[1]
                        landowner_vals['pan_card'] = base64.b64decode(pan_data)
                except Exception as e:
                    _logger.warning(f"Error processing PAN card: {str(e)}")
            
            # Check if there's anything to update
            if not landowner_vals:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'NO_FIELDS_TO_UPDATE',
                        'message': 'No valid fields provided for update',
                        'fields': []
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Update landowner
            try:
                landowner.write(landowner_vals)
            except ValidationError as ve:
                # Extract field names from validation error if possible
                error_msg = str(ve)
                fields_list = []
                
                # Try to identify which field caused the error
                if 'aadhar' in error_msg.lower():
                    fields_list.append('aadhar_number')
                elif 'account' in error_msg.lower():
                    fields_list.append('account_number')
                elif 'ifsc' in error_msg.lower():
                    fields_list.append('ifsc_code')
                # Age and gender fields removed
                
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'MODEL_VALIDATION_FAILED',
                        'message': error_msg,
                        'fields': fields_list if fields_list else []
                    }),
                    status=400,
                    content_type='application/json'
                )
            except Exception as e:
                _logger.error(f"Error updating landowner: {str(e)}", exc_info=True)
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'UPDATE_FAILED',
                        'error_code': 'UPDATE_ERROR',
                        'message': f'Failed to update landowner: {str(e)}',
                        'fields': []
                    }),
                    status=500,
                    content_type='application/json'
                )
            
            # Return updated landowner details
            return Response(
                json.dumps({
                    'success': True,
                    'data': {
                        'id': landowner.id,
                        'name': landowner.name,
                        'father_name': landowner.father_name or '',
                        'mother_name': landowner.mother_name or '',
                        'spouse_name': landowner.spouse_name or '',
                        'caste': landowner.caste or '',
                        'aadhar_number': landowner.aadhar_number or '',
                        'phone': landowner.phone or '',
                        'village_id': landowner.village_id.id if landowner.village_id else None,
                        'village_name': landowner.village_id.name if landowner.village_id else '',
                        'rakba': landowner.rakba or '',
                        'bank_name': landowner.bank_name or '',
                        'bank_branch': landowner.bank_branch or '',
                        'account_number': landowner.account_number or '',
                        'ifsc_code': landowner.ifsc_code or '',
                        'account_holder_name': landowner.account_holder_name or '',
                    }
                }),
                status=200,
                content_type='application/json'
            )
            
        except json.JSONDecodeError:
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'INVALID_JSON',
                    'error_code': 'INVALID_JSON',
                    'message': 'Invalid JSON in request body',
                    'fields': []
                }),
                status=400,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error in update_landowner: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'SERVER_ERROR',
                    'error_code': 'INTERNAL_ERROR',
                    'message': f'Internal server error: {str(e)}',
                    'fields': []
                }),
                status=500,
                content_type='application/json'
            )

