# -*- coding: utf-8 -*-
"""Survey PATCH/DELETE and photo uploads"""
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

from .survey_api_helpers import (
    SurveyAPIHelperMixin,
    api_apply_mobile_auto_approve_vals,
    api_auto_approve_survey_after_mobile_upload,
    api_mobile_survey_submitted_now,
    api_resolve_tehsil_id,
    register_survey_photos,
    build_canonical_s3_url,
)


class SurveyAPISurveyWriteController(SurveyAPIHelperMixin, http.Controller):
    """BhuKhadan REST API — survey write & photos."""

    @http.route('/api/bhuarjan/survey/<int:survey_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    @check_permission
    def update_survey(self, survey_id, **kwargs):
        """
        Update survey (PATCH) - only allowed if state is 'draft' or 'submitted'
        Request body: JSON with fields to update
        Returns: Updated survey data
        """
        try:
            survey = request.env['bhu.survey'].sudo().browse(survey_id)
            if not survey.exists():
                return Response(
                    json.dumps({'error': f'Survey with ID {survey_id} not found'}),
                    status=404,
                    content_type='application/json'
                )

            # Parse request data
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            
            # Check if survey can be edited (only draft and submitted states allow editing)
            # Exception: allow state updates regardless of current state
            is_state_update = 'state' in data
            has_other_fields = any(key != 'state' for key in data.keys())
            
            if has_other_fields and survey.state not in ('draft', 'submitted'):
                return Response(
                    json.dumps({
                        'error': f'Survey cannot be edited. Current state: {survey.state}. Only surveys in draft or submitted state can be edited. State updates are allowed regardless of current state.'
                    }),
                    status=400,
                    content_type='application/json'
                )

            # Handle state updates - validate and set submitted_date if needed
            if 'state' in data:
                new_state = data.get('state')
                valid_states = ['draft', 'submitted', 'approved', 'rejected']
                if new_state not in valid_states:
                    return Response(
                        json.dumps({
                            'error': 'Validation Error',
                            'message': f'Invalid state value. Valid states are: {", ".join(valid_states)}'
                        }),
                        status=400,
                        content_type='application/json'
                    )
                
                # App "submit" → auto-approve (no department approval)
                if new_state == 'submitted':
                    if not survey.khasra_number:
                        return Response(
                            json.dumps({
                                'error': 'Validation Error',
                                'message': 'Khasra number is required before submitting the survey.'
                            }),
                            status=400,
                            content_type='application/json'
                        )
                    data['state'] = 'approved'
                    if not survey.submitted_date and 'submitted_date' not in data:
                        data['submitted_date'] = api_mobile_survey_submitted_now()
                elif new_state == 'approved' and not survey.submitted_date and 'submitted_date' not in data:
                    data['submitted_date'] = api_mobile_survey_submitted_now()

            # List of fields that can be updated via API
            allowed_fields = [
                'project_id', 'department_id', 'village_id', 'tehsil_id', 'survey_date',
                'khasra_number', 'total_area', 'acquired_area', 'has_traded_land', 'traded_land_area',
                'distance_from_main_road',
                'crop_type_id', 'irrigation_type',
                'has_house', 'house_type', 'house_area', 'has_shed', 'shed_area',
                'has_well', 'well_type', 'well_count', 'has_tubewell', 'tubewell_count', 'has_pond',
                'landowner_ids', 'survey_image', 'survey_image_filename',
                'remarks', 'state', 'submitted_date'
            ]
            
            # Note: 'crop_type' is handled separately above and mapped to 'crop_type_id'

            # Handle crop_type - accept crop_type (ID) and map to crop_type_id in model
            if 'crop_type' in data:
                crop_type_value = data.get('crop_type')
                if isinstance(crop_type_value, int):
                    # If it's an integer, treat it as land type ID
                    data['crop_type_id'] = crop_type_value
                elif isinstance(crop_type_value, str):
                    # Backward compatibility: map old crop_type string to land type ID
                    crop_type_str = crop_type_value.lower()
                    if crop_type_str in ('single', 'single1'):
                        single_crop = request.env['bhu.land.type'].sudo().search([('code', '=', 'SINGLE_CROP')], limit=1)
                        data['crop_type_id'] = single_crop.id if single_crop else None
                    elif crop_type_str in ('double', 'double1'):
                        double_crop = request.env['bhu.land.type'].sudo().search([('code', '=', 'DOUBLE_CROP')], limit=1)
                        data['crop_type_id'] = double_crop.id if double_crop else None
                # Remove crop_type from data as we'll use crop_type_id internally
                data.pop('crop_type', None)
            elif 'crop_type_id' in data:
                # Also support crop_type_id for backward compatibility
                pass  # Keep it as is

            # Validate area values if they are being updated
            if 'total_area' in data or 'acquired_area' in data:
                # Get the values that will be used after update
                # If field is in data, use the new value; otherwise use existing value from survey
                total_area = data.get('total_area') if 'total_area' in data else survey.total_area
                acquired_area = data.get('acquired_area') if 'acquired_area' in data else survey.acquired_area
                
                # Validate total_area if it's being updated or if we need to check the relationship
                if 'total_area' in data:
                    if total_area is None or total_area <= 0:
                        return Response(
                            json.dumps({
                                'error': 'Validation Error',
                                'message': 'Total Area must be greater than 0.'
                            }),
                            status=400,
                            content_type='application/json'
                        )
                
                # Validate acquired_area if it's being updated or if we need to check the relationship
                if 'acquired_area' in data:
                    if acquired_area is None or acquired_area <= 0:
                        return Response(
                            json.dumps({
                                'error': 'Validation Error',
                                'message': 'Acquired Area must be greater than 0.'
                            }),
                            status=400,
                            content_type='application/json'
                        )
                
                # Validate relationship between areas (only if both values are available)
                if total_area is not None and acquired_area is not None:
                    if acquired_area > total_area:
                        return Response(
                            json.dumps({
                                'error': 'Validation Error',
                                'message': 'Acquired Area cannot be greater than Total Area.'
                            }),
                            status=400,
                            content_type='application/json'
                        )
            
            # Prepare update values
            update_vals = {}
            for field, value in data.items():
                if field in allowed_fields:
                    # Handle well_type - no conversion needed, use as is
                    # Handle Many2many fields (landowner_ids)
                    if field == 'landowner_ids' and isinstance(value, list):
                        update_vals[field] = [(6, 0, value)]  # Replace all
                    # Handle Many2one fields
                    elif field.endswith('_id') and value:
                        update_vals[field] = value
                    # Handle binary fields (survey_image)
                    elif field == 'survey_image' and value:
                        # If base64 encoded, decode it
                        if isinstance(value, str) and value.startswith('data:'):
                            # Extract base64 part
                            base64_data = value.split(',')[1] if ',' in value else value
                            update_vals[field] = base64.b64decode(base64_data)
                        else:
                            update_vals[field] = value
                    # Handle text fields (remarks) - allow None and empty strings
                    elif field in ['remarks']:
                        update_vals[field] = value if value is not None else ''
                    # Handle house_type - convert 'false' string to False
                    elif field == 'house_type':
                        if value == 'false' or value is False or value is None or value == '':
                            update_vals[field] = False
                        elif value in ['kaccha', 'pakka']:
                            update_vals[field] = value
                        else:
                            # Invalid value, skip it
                            _logger.warning(f"Invalid house_type value: {value}, skipping")
                    # Handle well_type - convert 'false' string to False
                    elif field == 'well_type':
                        if value == 'false' or value is False or value is None or value == '':
                            update_vals[field] = False
                        elif value in ['kaccha', 'pakka']:
                            update_vals[field] = value
                        else:
                            # Invalid value, skip it
                            _logger.warning(f"Invalid well_type value: {value}, skipping")
                    # Handle other fields
                    else:
                        update_vals[field] = value
                else:
                    _logger.warning(f"Field '{field}' is not allowed to be updated via API")
            
            # Handle house_type - convert 'false' string to False when has_house is 'no'
            if 'has_house' in update_vals:
                if update_vals['has_house'] == 'no':
                    # Clear house_type and house_area when there's no house
                    update_vals['house_type'] = False
                    if 'house_area' not in update_vals:
                        update_vals['house_area'] = 0.0
            elif 'house_type' in update_vals:
                # If house_type is sent as 'false' string, convert to False
                if update_vals['house_type'] == 'false' or update_vals['house_type'] is False:
                    update_vals['house_type'] = False
                # Also check if has_house is 'no' in existing survey
                if survey.has_house == 'no':
                    update_vals['house_type'] = False
            
            # Handle well_count and tubewell_count based on has_well and has_tubewell
            # If has_well is being set to 'no', reset well_count to 0 and clear well_type
            if 'has_well' in update_vals:
                if update_vals['has_well'] == 'no':
                    update_vals['well_count'] = 0
                    update_vals['well_type'] = False
                elif update_vals['has_well'] == 'yes' and 'well_count' not in update_vals:
                    # If well is set to yes but count not provided, default to 1
                    update_vals['well_count'] = 1
            elif 'well_type' in update_vals:
                # If well_type is sent as 'false' string, convert to False
                if update_vals['well_type'] == 'false' or update_vals['well_type'] is False:
                    update_vals['well_type'] = False
                # Also check if has_well is 'no' in existing survey
                if survey.has_well == 'no':
                    update_vals['well_type'] = False
            
            # If has_tubewell is being set to 'no', reset tubewell_count to 0
            if 'has_tubewell' in update_vals:
                if update_vals['has_tubewell'] == 'no':
                    update_vals['tubewell_count'] = 0
                elif update_vals['has_tubewell'] == 'yes' and 'tubewell_count' not in update_vals:
                    # If tubewell is set to yes but count not provided, default to 1
                    update_vals['tubewell_count'] = 1

            if not update_vals:
                return Response(
                    json.dumps({'error': 'No valid fields to update'}),
                    status=400,
                    content_type='application/json'
                )

            village_id = update_vals.get('village_id', survey.village_id.id)
            if village_id and not update_vals.get('tehsil_id'):
                resolved_tehsil = api_resolve_tehsil_id(
                    request.env,
                    village_id,
                    update_vals.get('tehsil_id'),
                )
                if resolved_tehsil:
                    update_vals['tehsil_id'] = resolved_tehsil

            api_apply_mobile_auto_approve_vals(update_vals)
            # Update the survey
            survey.write(update_vals)
            api_auto_approve_survey_after_mobile_upload(survey, request.env.user)
            
            # Handle tree lines (if provided - new format: supports fruit-bearing and non-fruit-bearing trees)
            if 'tree_lines' in data and isinstance(data['tree_lines'], list):
                tree_line_vals = []
                
                # If empty array is passed, delete all existing trees
                if len(data['tree_lines']) == 0:
                    survey.write({'tree_line_ids': [(5, 0, 0)]})  # Delete all trees
                else:
                    # Process tree lines
                    for tree_line in data['tree_lines']:
                        if isinstance(tree_line, dict):
                            # Support both tree_master_id (integer) and tree_name (string) for tree selection
                            tree_master_id = None
                            if 'tree_master_id' in tree_line and tree_line['tree_master_id']:
                                tree_master_id = tree_line['tree_master_id']
                            elif 'tree_name' in tree_line and tree_line['tree_name']:
                                # Look up tree by name
                                tree_master = request.env['bhu.tree.master'].sudo().search([
                                    ('name', '=', tree_line['tree_name'])
                                ], limit=1)
                                if tree_master:
                                    tree_master_id = tree_master.id
                                else:
                                    return Response(
                                        json.dumps({
                                            'error': f'Tree with name "{tree_line["tree_name"]}" not found in tree master'
                                        }),
                                        status=400,
                                        content_type='application/json'
                                    )
                            else:
                                return Response(
                                    json.dumps({
                                        'error': 'Either tree_master_id or tree_name must be provided for each tree line'
                                    }),
                                    status=400,
                                    content_type='application/json'
                                )
                            
                            # Get tree master to determine tree_type
                            tree_master = request.env['bhu.tree.master'].sudo().browse(tree_master_id)
                            if not tree_master.exists():
                                return Response(
                                    json.dumps({
                                        'error': f'Tree master with ID {tree_master_id} not found'
                                    }),
                                    status=400,
                                    content_type='application/json'
                                )
                            
                            # Get tree_type from tree_master or from request
                            tree_type = tree_line.get('tree_type') or tree_master.tree_type
                            if not tree_type:
                                return Response(
                                    json.dumps({
                                        'error': 'tree_type must be provided or tree_master must have a tree_type'
                                    }),
                                    status=400,
                                    content_type='application/json'
                                )
                            
                            # Validate tree_type matches tree_master
                            if tree_master.tree_type != tree_type:
                                return Response(
                                    json.dumps({
                                        'error': f'Tree type mismatch: tree_master "{tree_master.name}" is {tree_master.tree_type}, but provided tree_type is {tree_type}'
                                    }),
                                    status=400,
                                    content_type='application/json'
                                )
                            
                            # Prepare tree line values
                            tree_line_data = {
                                'tree_master_id': tree_master_id,
                                'tree_type': tree_type,
                                'quantity': tree_line.get('quantity', 1)
                            }
                            
                            # Handle development_stage - required for all tree types
                            development_stage = tree_line.get('development_stage')
                            if not development_stage:
                                return Response(
                                    json.dumps({
                                        'error': 'development_stage is required for all trees'
                                    }),
                                    status=400,
                                    content_type='application/json'
                                )
                            
                            # Validate development_stage
                            if development_stage not in ('undeveloped', 'semi_developed', 'fully_developed'):
                                return Response(
                                    json.dumps({
                                        'error': f'Invalid development_stage: {development_stage}. Must be one of: undeveloped, semi_developed, fully_developed'
                                    }),
                                    status=400,
                                    content_type='application/json'
                                )
                            tree_line_data['development_stage'] = development_stage
                            
                            # For non-fruit-bearing trees, handle girth_cm
                            if tree_type == 'non_fruit_bearing':
                                # Handle girth_cm for non-fruit-bearing trees
                                girth_cm = tree_line.get('girth_cm')
                                # girth_cm is optional - if provided, it must be > 0
                                # Check if girth_cm is explicitly provided (not None and not empty string)
                                if girth_cm is not None and girth_cm != '':
                                    try:
                                        girth_cm_float = float(girth_cm)
                                        if girth_cm_float <= 0:
                                            return Response(
                                                json.dumps({
                                                    'error': 'girth_cm must be greater than 0 if provided'
                                                }),
                                                status=400,
                                                content_type='application/json'
                                            )
                                        tree_line_data['girth_cm'] = girth_cm_float
                                    except (ValueError, TypeError):
                                        return Response(
                                            json.dumps({
                                                'error': 'girth_cm must be a valid number if provided'
                                            }),
                                            status=400,
                                            content_type='application/json'
                                        )
                                # Don't set girth_cm if not provided - Odoo will use default/False
                            
                            tree_line_vals.append((0, 0, tree_line_data))
                    
                    # Replace all tree lines with new ones
                    if tree_line_vals:
                        survey.write({'tree_line_ids': [(5, 0, 0)] + tree_line_vals})
            
            # Handle photos (if provided - adds new photos, doesn't replace existing)
            if 'photos' in data and isinstance(data['photos'], list):
                registered = register_survey_photos(request.env, survey, data['photos'])
                if registered:
                    _logger.info(
                        'PATCH survey %s: registered %s photo(s)',
                        survey.id, len(registered),
                    )
            if ('photos' in data) or not survey.photo_ids:
                request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)

            # Return updated survey data
            survey_data = {
                'id': survey.id,
                'name': survey.name or '',
                'survey_uuid': survey.survey_uuid or '',
                'project_id': survey.project_id.id if survey.project_id else None,
                'project_name': survey.project_id.name if survey.project_id else '',
                'department_id': survey.department_id.id if survey.department_id else None,
                'department_name': survey.department_id.name if survey.department_id else '',
                'village_id': survey.village_id.id if survey.village_id else None,
                'village_name': survey.village_id.name if survey.village_id else '',
                'tehsil_id': survey.tehsil_id.id if survey.tehsil_id else None,
                'tehsil_name': survey.tehsil_id.name if survey.tehsil_id else '',
                'survey_date': survey.survey_date.strftime('%Y-%m-%d') if survey.survey_date else '',
                'khasra_number': survey.khasra_number or '',
                'total_area': survey.total_area or 0.0,
                'acquired_area': survey.acquired_area or 0.0,
                'has_traded_land': survey.has_traded_land or 'no',
                'traded_land_area': survey.traded_land_area or 0.0,
                'distance_from_main_road': survey.distance_from_main_road or 0.0,
                'is_within_distance_for_award': bool(survey.is_within_distance_for_award),
                'crop_type': survey.crop_type_id.id if survey.crop_type_id else None,
                'crop_type_name': survey.crop_type_id.name if survey.crop_type_id else '',
                'crop_type_code': survey.crop_type_id.code if survey.crop_type_id else '',
                'irrigation_type': survey.irrigation_type or '',
                'tree_lines': [{
                    'id': line.id,
                    'tree_type': line.tree_type,
                    'tree_master_id': line.tree_master_id.id,
                    'tree_name': line.tree_master_id.name,
                    'development_stage': line.development_stage,
                    'girth_cm': line.girth_cm if line.tree_type == 'non_fruit_bearing' else None,
                    'quantity': line.quantity
                } for line in survey.tree_line_ids],
                'photos': [{
                    'id': photo.id,
                    'photo_type_id': photo.photo_type_id.id if photo.photo_type_id else None,
                    'photo_type_name': photo.photo_type_id.name if photo.photo_type_id else '',
                    's3_url': photo.s3_url or '',
                    'filename': photo.filename or '',
                    'file_size': photo.file_size or 0,
                    'latitude': photo.latitude or 0.0,
                    'longitude': photo.longitude or 0.0,
                    'sequence': photo.sequence or 10
                } for photo in survey.photo_ids],
                'has_house': survey.has_house or '',
                'house_type': survey.house_type or '',
                'house_area': survey.house_area or 0.0,
                'has_shed': survey.has_shed or '',
                'shed_area': survey.shed_area or 0.0,
                'has_well': survey.has_well or '',
                'well_type': survey.well_type or '',
                'has_tubewell': survey.has_tubewell or '',
                'has_pond': survey.has_pond or '',
                'landowner_ids': survey.landowner_ids.ids if survey.landowner_ids else [],
                'state': survey.state or 'submitted',
                'remarks': survey.remarks or '',
            }

            return Response(
                json.dumps({
                    'success': True,
                    'message': 'Survey updated successfully',
                    'data': survey_data
                }),
                status=200,
                content_type='application/json'
            )

        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error in update_survey: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'VALIDATION_ERROR',
                    'error_code': 'INVALID_JSON',
                    'message': 'Invalid JSON in request body. Please check your request format.'
                }),
                status=400,
                content_type='application/json'
            )
        except ValidationError as ve:
            _logger.error(f"Validation error in update_survey: {str(ve)}", exc_info=True)
            # Extract clear error message from ValidationError
            error_message = str(ve)
            if hasattr(ve, 'name') and ve.name:


                error_message = ve.name
            elif isinstance(ve.args, tuple) and len(ve.args) > 0:
                if isinstance(ve.args[0], (list, tuple)):
                    error_message = '; '.join(str(msg) for msg in ve.args[0])
                else:
                    error_message = str(ve.args[0])
            
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'VALIDATION_ERROR',
                    'error_code': 'MODEL_VALIDATION_FAILED',
                    'message': error_message
                }),
                status=400,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error in update_survey: {str(e)}", exc_info=True)
            error_message = str(e)
            error_type = type(e).__name__
            
            # Provide more descriptive messages for common errors
            if 'unique constraint' in error_message.lower() or 'duplicate' in error_message.lower():
                if 'khasra' in error_message.lower():
                    error_message = 'Khasra number already exists in this village for another survey.'
                else:
                    error_message = 'A record with these values already exists. Please check for duplicates.'
            elif 'foreign key' in error_message.lower():
                error_message = 'Invalid reference: One or more related records do not exist.'
            elif 'not null' in error_message.lower() or 'required' in error_message.lower():
                error_message = 'Required field is missing. Please check all required fields are provided.'
            
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'SERVER_ERROR',
                    'error_code': error_type.upper().replace(' ', '_'),
                    'message': error_message
                }),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/survey/<int:survey_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @check_permission
    def delete_survey(self, survey_id, **kwargs):
        """
        Delete a survey
        Only allowed if survey is in 'draft' or 'submitted' state
        Returns: Success message
        """
        try:
            survey = request.env['bhu.survey'].sudo().browse(survey_id)
            if not survey.exists():
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Survey not found',
                        'message': f'Survey with ID {survey_id} does not exist'
                    }),
                    status=404,
                    content_type='application/json'
                )

            # Check if survey can be deleted (only draft and submitted states allow deletion)
            if survey.state not in ('draft', 'submitted'):
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Survey cannot be deleted',
                        'message': f'Survey cannot be deleted. Current state: {survey.state}. Only surveys in draft or submitted state can be deleted.'
                    }),
                    status=400,
                    content_type='application/json'
                )

            # Store survey details for response
            survey_name = survey.name
            survey_khasra = survey.khasra_number

            # Delete the survey
            survey.unlink()

            return Response(
                json.dumps({
                    'success': True,
                    'message': 'Survey deleted successfully',
                    'data': {
                        'id': survey_id,
                        'name': survey_name,
                        'khasra_number': survey_khasra
                    }
                }),
                status=200,
                content_type='application/json'
            )

        except ValidationError as ve:
            _logger.error(f"Validation error in delete_survey: {str(ve)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'Validation Error',
                    'message': str(ve)
                }),
                status=400,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error in delete_survey: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/photo-types', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_all_photo_types(self, **kwargs):
        """
        Get all photo types
        Query params: limit, offset, active (optional filter - default True)
        Returns: JSON list of photo types
        """
        try:
            # Get query parameters
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0
            active_filter = request.httprequest.args.get('active')
            
            # Build domain
            domain = []
            if active_filter is not None:
                active_bool = active_filter.lower() in ('true', '1', 'yes')
                domain.append(('active', '=', active_bool))
            else:
                # Default to active only
                domain.append(('active', '=', True))

            # Search photo types
            photo_types = request.env['bhu.photo.type'].sudo().search(domain, limit=limit, offset=offset, order='sequence, name')

            # Build response
            photo_types_data = []
            for photo_type in photo_types:
                photo_types_data.append({
                    'id': photo_type.id,
                    'name': photo_type.name or '',
                    'code': photo_type.code or '',
                    'description': photo_type.description or '',
                    'sequence': photo_type.sequence or 10,
                    'active': photo_type.active
                })

            # Get total count
            total_count = request.env['bhu.photo.type'].sudo().search_count(domain)

            return Response(
                json.dumps({
                    'success': True,
                    'data': photo_types_data,
                    'total': total_count,
                    'count': len(photo_types_data),
                    'limit': limit,
                    'offset': offset
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_all_photo_types: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/survey/photos', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def add_survey_photos(self, **kwargs):
        """
        Add photos to a survey
        Query param: survey_id (required)
        Body: JSON with photos array
        Each photo must have: s3_url (required)
        Optional fields: photo_type_id, filename, file_size
        Returns: Success message with added photos
        """
        try:
            # Get survey_id from query parameters
            survey_id = request.httprequest.args.get('survey_id')
            if not survey_id:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Missing survey_id',
                        'message': 'survey_id query parameter is required'
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Log the received survey_id for debugging
            _logger.info(f"add_survey_photos: Received survey_id={survey_id}, type={type(survey_id)}")
            
            # Ensure survey_id is an integer
            try:
                survey_id = int(survey_id)
            except (ValueError, TypeError):
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Invalid survey_id',
                        'message': f'survey_id must be an integer, got: {survey_id}'
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Parse request data
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            
            # Validate survey exists
            survey = request.env['bhu.survey'].sudo().browse(survey_id)
            if not survey.exists():
                _logger.warning(f"add_survey_photos: Survey {survey_id} not found")
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Survey not found',
                        'message': f'Survey with ID {survey_id} does not exist'
                    }),
                    status=404,
                    content_type='application/json'
                )
            
            _logger.info(f"add_survey_photos: Survey {survey_id} found, name: {survey.name}")
            
            # Validate photos array
            if 'photos' not in data or not isinstance(data['photos'], list):
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Invalid request',
                        'message': 'photos array is required in request body'
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            if len(data['photos']) == 0:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Invalid request',
                        'message': 'At least one photo is required'
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            before_ids = set(survey.photo_ids.ids)

            # Build and register photo records (dedupe by canonical S3 URL)
            register_survey_photos(request.env, survey, data.get('photos'))
            request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)
            new_photos = survey.photo_ids.filtered(lambda p: p.id not in before_ids)
            if not new_photos:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Invalid photos',
                        'message': 'No valid photos provided. Each photo must have s3_url (or s3_key + prior presigned upload).'
                    }),
                    status=400,
                    content_type='application/json'
                )

            added_photos = [{
                'id': photo.id,
                'photo_type_id': photo.photo_type_id.id if photo.photo_type_id else None,
                'photo_type_name': photo.photo_type_id.name if photo.photo_type_id else None,
                's3_url': photo.s3_url,
                'filename': photo.filename or '',
                'latitude': photo.latitude,
                'longitude': photo.longitude,
            } for photo in new_photos]

            api_auto_approve_survey_after_mobile_upload(survey, request.env.user)
            
            return Response(
                json.dumps({
                    'success': True,
                    'message': f'Successfully added {len(new_photos)} photo(s) to survey',
                    'data': {
                        'survey_id': survey_id,
                        'added_photos': added_photos,
                        'total_photos': len(survey.photo_ids)
                    }
                }),
                status=200,
                content_type='application/json'
            )

        except json.JSONDecodeError:
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'VALIDATION_ERROR',
                    'error_code': 'INVALID_JSON',
                    'message': 'Request body must be valid JSON. Please check your request format.'
                }),
                status=400,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error in add_survey_photos: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                status=500,
                content_type='application/json'
            )

