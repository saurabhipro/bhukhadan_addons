# -*- coding: utf-8 -*-
"""Survey read: create (POST), get, list, photo delete"""
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

from odoo.osv.expression import AND

from .survey_api_helpers import (
    SurveyAPIHelperMixin,
    api_apply_mobile_auto_approve_vals,
    api_auto_approve_survey_after_mobile_upload,
    api_mobile_user_village_ids,
    api_patwari_survey_access_domain,
    api_resolve_tehsil_id,
)


class SurveyAPISurveyReadController(SurveyAPIHelperMixin, http.Controller):
    """BhuKhadan REST API — survey read & create."""

    @http.route('/api/bhuarjan/survey', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def create_survey(self, **kwargs):
        """
        Create a new survey
        Accepts: JSON data with survey fields
        Returns: Created survey details
        """
        try:
            # Parse request data
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            
            # Validate that at least one landowner is provided
            landowner_ids = data.get('landowner_ids', [])
            if not landowner_ids or (isinstance(landowner_ids, list) and len(landowner_ids) == 0):
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'MISSING_LANDOWNERS',
                        'message': 'At least one landowner is required to create a survey',
                        'fields': ['landowner_ids']
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Validate that all landowner IDs exist and are valid
            if isinstance(landowner_ids, list):
                invalid_ids = []
                valid_ids = []
                for landowner_id in landowner_ids:
                    if not isinstance(landowner_id, int):
                        invalid_ids.append(f"{landowner_id} (not an integer)")
                    else:
                        landowner = request.env['bhu.landowner'].sudo().browse(landowner_id)
                        if not landowner.exists():
                            invalid_ids.append(str(landowner_id))
                        else:
                            valid_ids.append(landowner_id)
                
                if invalid_ids:
                    return Response(
                        json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'INVALID_LANDOWNER_IDS',
                        'message': f'The following landowner ID(s) do not exist or are invalid: {", ".join(invalid_ids)}',
                        'fields': ['landowner_ids']
                        }),
                        status=400,
                        content_type='application/json'
                    )
                
                # Use only valid IDs
                landowner_ids = valid_ids
            
            # Validate required fields
            required_fields = {
                'project_id': 'Project',
                'village_id': 'Village',
                'department_id': 'Department',
                'khasra_number': 'Khasra Number',
                'total_area': 'Total Area',
                'acquired_area': 'Acquired Area'
            }
            
            missing_field_names = []
            missing_field_labels = []
            for field, label in required_fields.items():
                if field not in data or data.get(field) is None or data.get(field) == '':
                    missing_field_names.append(field)
                    missing_field_labels.append(label)
            
            if missing_field_names:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'MISSING_REQUIRED_FIELDS',
                        'message': f'The following required fields are missing: {", ".join(missing_field_labels)}',
                        'fields': missing_field_names
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Validate that referenced IDs exist
            validation_errors = []
            invalid_fields = []
            
            # Validate project_id
            if data.get('project_id'):
                project = request.env['bhu.project'].sudo().browse(data['project_id'])
                if not project.exists():
                    validation_errors.append(f'Project ID {data["project_id"]} does not exist')
                    invalid_fields.append('project_id')
            
            # Validate village_id
            if data.get('village_id'):
                village = request.env['bhu.village'].sudo().browse(data['village_id'])
                if not village.exists():
                    validation_errors.append(f'Village ID {data["village_id"]} does not exist')
                    invalid_fields.append('village_id')
            
            # Validate department_id
            if data.get('department_id'):
                department = request.env['bhu.department'].sudo().browse(data['department_id'])
                if not department.exists():
                    validation_errors.append(f'Department ID {data["department_id"]} does not exist')
                    invalid_fields.append('department_id')
            
            # Validate tehsil_id
            if data.get('tehsil_id'):
                tehsil = request.env['bhu.tehsil'].sudo().browse(data['tehsil_id'])
                if not tehsil.exists():
                    validation_errors.append(f'Tehsil ID {data["tehsil_id"]} does not exist')
                    invalid_fields.append('tehsil_id')
            
            if validation_errors:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'INVALID_REFERENCE_IDS',
                        'message': '; '.join(validation_errors),
                        'fields': invalid_fields
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            # Get default user (admin) or use provided user_id
            user_id = data.get('user_id')
            if not user_id:
                # Use admin user as default
                admin_user = request.env['res.users'].sudo().search([('login', '=', 'admin')], limit=1)
                user_id = admin_user.id if admin_user else 2  # Fallback to user ID 2 (usually admin)
            
            # Handle crop_type - accept crop_type (ID) and map to crop_type_id in model
            crop_type_id = None
            if 'crop_type' in data:
                crop_type_value = data.get('crop_type')
                if isinstance(crop_type_value, int):
                    # If it's an integer, treat it as land type ID
                    # Validate that the land type exists
                    land_type = request.env['bhu.land.type'].sudo().browse(crop_type_value)
                    if land_type.exists():
                        crop_type_id = crop_type_value
                    else:
                        return Response(
                            json.dumps({
                                'error': f'Invalid crop_type: Land type with ID {crop_type_value} does not exist'
                            }),
                            status=400,
                            content_type='application/json'
                        )
                elif isinstance(crop_type_value, str):
                    # Backward compatibility: map old crop_type string to land type ID
                    crop_type_str = crop_type_value.lower()
                    if crop_type_str in ('single', 'single1'):
                        single_crop = request.env['bhu.land.type'].sudo().search([
                            ('code', '=', 'SINGLE_CROP')
                        ], limit=1)
                        crop_type_id = single_crop.id if single_crop else None
                    elif crop_type_str in ('double', 'double1'):
                        double_crop = request.env['bhu.land.type'].sudo().search([
                            ('code', '=', 'DOUBLE_CROP')
                        ], limit=1)
                        crop_type_id = double_crop.id if double_crop else None
            elif 'crop_type_id' in data:
                # Also support crop_type_id for backward compatibility
                crop_type_id_value = data.get('crop_type_id')
                if crop_type_id_value:
                    # Validate that the land type exists
                    land_type = request.env['bhu.land.type'].sudo().browse(crop_type_id_value)
                    if land_type.exists():
                        crop_type_id = crop_type_id_value
                    else:
                        return Response(
                            json.dumps({
                                'error': f'Invalid crop_type_id: Land type with ID {crop_type_id_value} does not exist'
                            }),
                            status=400,
                            content_type='application/json'
                        )
            
            # Validate area values before creating survey
            total_area = data.get('total_area', 0.0)
            acquired_area = data.get('acquired_area', 0.0)
            
            # Area validation checks with clear error messages
            if total_area is None or total_area <= 0:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'INVALID_TOTAL_AREA',
                        'message': f'Total Area must be greater than 0. Provided value: {total_area}',
                        'fields': ['total_area']
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            if acquired_area is None or acquired_area <= 0:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'INVALID_ACQUIRED_AREA',
                        'message': f'Acquired Area must be greater than 0. Provided value: {acquired_area}',
                        'fields': ['acquired_area']
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            if acquired_area > total_area:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'VALIDATION_ERROR',
                        'error_code': 'ACQUIRED_AREA_EXCEEDS_TOTAL',
                        'message': f'Acquired Area ({acquired_area} hectares) cannot be greater than Total Area ({total_area} hectares).',
                        'fields': ['acquired_area', 'total_area']
                    }),
                    status=400,
                    content_type='application/json'
                )
            
            resolved_tehsil_id = api_resolve_tehsil_id(
                request.env,
                data.get('village_id'),
                data.get('tehsil_id'),
            )

            # Prepare survey values
            survey_vals = {
                'user_id': user_id,
                'project_id': data.get('project_id'),
                'village_id': data.get('village_id'),
                'department_id': data.get('department_id'),
                'tehsil_id': resolved_tehsil_id or False,
                'survey_type': data.get('survey_type', 'rural'),
                'khasra_number': data.get('khasra_number'),
                'total_area': total_area,
                'acquired_area': acquired_area,
                'has_traded_land': data.get('has_traded_land', 'no'),
                'traded_land_area': data.get('traded_land_area', 0.0),
                'distance_from_main_road': data.get('distance_from_main_road', 0.0),
                'irrigation_type': data.get('irrigation_type', 'irrigated'),
                'has_house': data.get('has_house', 'no'),
                'house_area': data.get('house_area', 0.0),
                'has_shed': data.get('has_shed', 'no'),
                'shed_area': data.get('shed_area', 0.0),
                'has_well': data.get('has_well', 'no'),
                'well_count': data.get('well_count', 1) if data.get('has_well') == 'yes' else 0,
                'has_tubewell': data.get('has_tubewell', 'no'),
                'tubewell_count': data.get('tubewell_count', 1) if data.get('has_tubewell') == 'yes' else 0,
                'has_pond': data.get('has_pond', 'no'),
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'location_accuracy': data.get('location_accuracy'),
                'location_timestamp': data.get('location_timestamp'),
                'remarks': data.get('remarks'),
                # Mobile app: auto-approved (no department approval queue)
                'state': data.get('state', 'approved'),
            }
            api_apply_mobile_auto_approve_vals(survey_vals)
            
            # Set crop_type_id only if it has a valid value (not None)
            if crop_type_id:
                survey_vals['crop_type_id'] = crop_type_id
            
            # Explicitly remove crop_type from survey_vals if it exists (shouldn't happen, but safety check)
            survey_vals.pop('crop_type', None)
            
            # Handle survey_date - only set if explicitly provided, otherwise use model default (today's date)
            if 'survey_date' in data and data.get('survey_date'):
                survey_vals['survey_date'] = data.get('survey_date')
            
            # Handle well_type separately - convert 'false' string to False
            if 'well_type' in data:
                well_type_value = data.get('well_type')
                if well_type_value == 'false' or well_type_value is False or well_type_value is None or well_type_value == '':
                    survey_vals['well_type'] = False
                elif well_type_value in ['kaccha', 'pakka']:
                    survey_vals['well_type'] = well_type_value
                # If invalid, don't set it (will use default or existing value)
            
            # Handle house_type - convert 'false' string to False
            if 'house_type' in data:
                house_type_value = data.get('house_type')
                if house_type_value == 'false' or house_type_value is False or house_type_value is None or house_type_value == '':
                    survey_vals['house_type'] = False
                elif house_type_value in ['kaccha', 'pakka']:
                    survey_vals['house_type'] = house_type_value
                # If invalid, don't set it (will use default or existing value)
            
            # If has_house is 'no', ensure house_type is False
            if survey_vals.get('has_house') == 'no':
                survey_vals['house_type'] = False
                if 'house_area' not in survey_vals:
                    survey_vals['house_area'] = 0.0
            
            # If has_well is 'no', ensure well_type is False
            if survey_vals.get('has_well') == 'no':
                survey_vals['well_type'] = False
                if 'well_count' not in survey_vals:
                    survey_vals['well_count'] = 0

            # Handle survey image if provided (base64 encoded)
            if data.get('survey_image'):
                try:
                    image_data = data['survey_image']
                    if isinstance(image_data, str):
                        # Remove data URL prefix if present
                        if ',' in image_data:
                            image_data = image_data.split(',')[1]
                        survey_vals['survey_image'] = base64.b64decode(image_data)
                        survey_vals['survey_image_filename'] = data.get('survey_image_filename', 'survey_image.jpg')
                except Exception as e:
                    _logger.warning(f"Error processing survey image: {str(e)}")

            # VALIDATE ALL TREE LINES BEFORE CREATING SURVEY
            # Handle tree lines (new format: supports fruit-bearing and non-fruit-bearing trees)
            tree_line_vals = []
            
            # Support new format: tree_lines array with tree_type
            if 'tree_lines' in data and isinstance(data['tree_lines'], list):
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
                        # Handle girth_cm for all tree types
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
            
            # Backward compatibility: support old format with separate arrays
            if 'undeveloped_tree_lines' in data and isinstance(data['undeveloped_tree_lines'], list):
                for tree_line in data['undeveloped_tree_lines']:
                    if isinstance(tree_line, dict) and 'tree_master_id' in tree_line:
                        # Validate tree_master_id exists
                        tree_master = request.env['bhu.tree.master'].sudo().browse(tree_line['tree_master_id'])
                        if not tree_master.exists():
                            return Response(
                                json.dumps({
                                    'error': f'Tree master with ID {tree_line["tree_master_id"]} not found'
                                }),
                                status=400,
                                content_type='application/json'
                            )
                        tree_line_vals.append((0, 0, {
                            'tree_master_id': tree_line['tree_master_id'],
                            'development_stage': 'undeveloped',
                            'quantity': tree_line.get('quantity', 1)
                        }))
            
            if 'semi_developed_tree_lines' in data and isinstance(data['semi_developed_tree_lines'], list):
                for tree_line in data['semi_developed_tree_lines']:
                    if isinstance(tree_line, dict) and 'tree_master_id' in tree_line:
                        # Validate tree_master_id exists
                        tree_master = request.env['bhu.tree.master'].sudo().browse(tree_line['tree_master_id'])
                        if not tree_master.exists():
                            return Response(
                                json.dumps({
                                    'error': f'Tree master with ID {tree_line["tree_master_id"]} not found'
                                }),
                                status=400,
                                content_type='application/json'
                            )
                        tree_line_vals.append((0, 0, {
                            'tree_master_id': tree_line['tree_master_id'],
                            'development_stage': 'semi_developed',
                            'quantity': tree_line.get('quantity', 1)
                        }))
            
            if 'fully_developed_tree_lines' in data and isinstance(data['fully_developed_tree_lines'], list):
                for tree_line in data['fully_developed_tree_lines']:
                    if isinstance(tree_line, dict) and 'tree_master_id' in tree_line:
                        # Validate tree_master_id exists
                        tree_master = request.env['bhu.tree.master'].sudo().browse(tree_line['tree_master_id'])
                        if not tree_master.exists():
                            return Response(
                                json.dumps({
                                    'error': f'Tree master with ID {tree_line["tree_master_id"]} not found'
                                }),
                                status=400,
                                content_type='application/json'
                            )
                        tree_line_vals.append((0, 0, {
                            'tree_master_id': tree_line['tree_master_id'],
                            'development_stage': 'fully_developed',
                            'quantity': tree_line.get('quantity', 1)
                        }))
            
            # VALIDATE PHOTOS BEFORE CREATING SURVEY
            photo_vals = []
            if 'photos' in data and isinstance(data['photos'], list):
                _logger.info(f"Processing {len(data['photos'])} photos for new survey")
                for index, photo in enumerate(data['photos']):
                    if isinstance(photo, dict):
                        # s3_url is mandatory
                        if 's3_url' not in photo or not photo['s3_url']:
                            _logger.warning(f"Photo at index {index} missing s3_url, skipping")
                            continue
                        
                        # Validate photo_type_id if provided
                        photo_type_id = photo.get('photo_type_id')
                        photo_type = None
                        if photo_type_id:
                            photo_type = request.env['bhu.photo.type'].sudo().browse(photo_type_id)
                            if not photo_type.exists():
                                # Log warning but don't skip - just create without type? 
                                # Better to skip to avoid data inconsistency if type is important
                                _logger.warning(f"Invalid photo_type_id {photo_type_id} for photo at index {index}, using None")
                                photo_type_id = None
                        
                        # Extract filename from S3 URL if not provided
                        filename = photo.get('filename', '')
                        if not filename and photo['s3_url']:
                            try:
                                filename = photo['s3_url'].split('/')[-1].split('?')[0]
                            except Exception:
                                filename = 'photo_upload'
                        
                        # Build photo values
                        photo_data = {
                            's3_url': photo['s3_url'],
                            'filename': filename,
                            'file_size': photo.get('file_size', 0),
                            'latitude': photo.get('latitude'),
                            'longitude': photo.get('longitude')
                        }
                        
                        # Only add photo_type_id if it was provided and is valid
                        if photo_type_id:
                            photo_data['photo_type_id'] = photo_type_id
                        
                        photo_vals.append((0, 0, photo_data))
            else:
                _logger.info("No photos provided in 'photos' list")
            
            # ALL VALIDATIONS PASSED - NOW CREATE SURVEY
            # Include all related data in survey_vals for atomic creation
            # This ensures if any validation fails, nothing gets saved
            
            # Add landowners to survey_vals
            if isinstance(landowner_ids, list) and len(landowner_ids) > 0:
                survey_vals['landowner_ids'] = [(4, lid) for lid in landowner_ids]
            
            # Add tree lines to survey_vals
            if tree_line_vals:
                survey_vals['tree_line_ids'] = tree_line_vals
            
            # Add photos to survey_vals
            if photo_vals:
                survey_vals['photo_ids'] = photo_vals
            
            # Create survey with all related data atomically
            survey = request.env['bhu.survey'].sudo().create(survey_vals)
            api_auto_approve_survey_after_mobile_upload(survey, request.env.user)
            if not survey.photo_ids:
                request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)

            # Return created survey details
            return Response(
                json.dumps({
                    'success': True,
                    'data': {
                        'id': survey.id,
                        'name': survey.name,
                        'survey_uuid': survey.survey_uuid,
                        'khasra_number': survey.khasra_number,
                        'state': survey.state,
                    }
                }),
                status=201,
                content_type='application/json'
            )

        except ValidationError as ve:
            _logger.error(f"Validation error in create_survey: {str(ve)}", exc_info=True)
            # CRITICAL: Rollback transaction to ensure survey is NOT saved
            try:
                request.env.cr.rollback()
            except Exception as rollback_error:
                _logger.error(f"Error during rollback: {str(rollback_error)}", exc_info=True)
            
            # Extract clear error message from ValidationError
            error_message = str(ve)
            # If ValidationError has a name attribute (translated message), use it
            if hasattr(ve, 'name') and ve.name:
                error_message = ve.name
            # If it's a list of messages, join them
            elif isinstance(ve.args, tuple) and len(ve.args) > 0:
                if isinstance(ve.args[0], (list, tuple)):
                    error_message = '; '.join(str(msg) for msg in ve.args[0])
                else:
                    error_message = str(ve.args[0])
            
            # Try to identify which fields caused the validation error
            fields_list = []
            error_lower = error_message.lower()
            if 'khasra' in error_lower:
                fields_list.append('khasra_number')
            if 'area' in error_lower or 'acquired' in error_lower:
                fields_list.extend(['total_area', 'acquired_area'])
            if 'landowner' in error_lower:
                fields_list.append('landowner_ids')
            
            return Response(
                json.dumps({
                    'success': False,
                    'error': 'VALIDATION_ERROR',
                    'error_code': 'MODEL_VALIDATION_FAILED',
                    'message': error_message,
                    'fields': fields_list if fields_list else []
                }),
                status=400,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error in create_survey: {str(e)}", exc_info=True)
            # CRITICAL: Rollback transaction to ensure survey is NOT saved
            try:
                request.env.cr.rollback()
            except Exception as rollback_error:
                _logger.error(f"Error during rollback: {str(rollback_error)}", exc_info=True)
            
            # Try to extract meaningful error message from generic exceptions
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

    @http.route('/api/bhuarjan/survey/<int:survey_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_survey_details(self, survey_id, **kwargs):
        """
        Get detailed survey information
        Returns: JSON with complete survey details
        """
        try:
            survey = request.env['bhu.survey'].sudo().browse(survey_id)
            if not survey.exists():
                return Response(
                    json.dumps({'error': 'Survey not found'}),
                    status=404,
                    content_type='application/json'
                )

            request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)

            # Get survey image as base64 if exists
            survey_image = None
            if survey.survey_image:
                survey_image = base64.b64encode(survey.survey_image).decode('utf-8')

            # Build response data
            survey_data = {
                'id': survey.id,
                'name': survey.name,
                'survey_uuid': survey.survey_uuid,
                'project_id': survey.project_id.id if survey.project_id else None,
                'project_name': survey.project_id.name if survey.project_id else '',
                'village_id': survey.village_id.id if survey.village_id else None,
                'village_name': survey.village_id.name if survey.village_id else '',
                'department_id': survey.department_id.id if survey.department_id else None,
                'department_name': survey.department_id.name if survey.department_id else '',
                'tehsil_id': survey.tehsil_id.id if survey.tehsil_id else None,
                'tehsil_name': survey.tehsil_id.name if survey.tehsil_id else '',
                'district_name': survey.district_name or '',
                'survey_type': survey.survey_type or 'rural',
                'khasra_number': survey.khasra_number or '',
                'total_area': survey.total_area,
                'acquired_area': survey.acquired_area,
                'has_traded_land': survey.has_traded_land or 'no',
                'traded_land_area': survey.traded_land_area or 0.0,
                'distance_from_main_road': survey.distance_from_main_road or 0.0,
                'is_within_distance_for_award': bool(survey.is_within_distance_for_award),
                'survey_date': survey.survey_date.strftime('%Y-%m-%d') if survey.survey_date else None,
                'crop_type': survey.crop_type_id.id if survey.crop_type_id else None,
                'crop_type_name': survey.crop_type_id.name if survey.crop_type_id else '',
                'crop_type_code': survey.crop_type_id.code if survey.crop_type_id else '',
                'irrigation_type': survey.irrigation_type,
                'tree_lines': [{
                    'id': line.id,
                    'tree_type': line.tree_type,
                    'tree_master_id': line.tree_master_id.id,
                    'tree_name': line.tree_master_id.name,
                    'development_stage': line.development_stage,
                    'girth_cm': line.girth_cm,
                    'quantity': line.quantity
                } for line in survey.tree_line_ids],
                'photos': [{
                    'id': photo.id,
                    'display_name': photo.display_name or '',
                    'photo_type_id': photo.photo_type_id.id if photo.photo_type_id else None,
                    'photo_type_name': photo.photo_type_id.name if photo.photo_type_id else '',
                    's3_url': photo.s3_url or '',
                    'filename': photo.filename or '',
                    's3_filename_display': photo.s3_filename_display or '',
                    'file_size': photo.file_size or 0,
                    'latitude': photo.latitude,
                    'longitude': photo.longitude,
                    'sequence': photo.sequence or 10
                } for photo in survey.photo_ids],
                'has_house': survey.has_house,
                'house_type': survey.house_type,
                'house_area': survey.house_area,
                'has_shed': survey.has_shed,
                'shed_area': survey.shed_area,
                'has_well': survey.has_well,
                'well_type': survey.well_type,
                'well_count': survey.well_count or 0,
                'has_tubewell': survey.has_tubewell,
                'tubewell_count': survey.tubewell_count or 0,
                'has_pond': survey.has_pond,
                'latitude': survey.latitude,
                'longitude': survey.longitude,
                'location_accuracy': survey.location_accuracy,
                'location_timestamp': survey.location_timestamp.strftime('%Y-%m-%d %H:%M:%S') if survey.location_timestamp else None,
                'remarks': survey.remarks or '',
                'state': survey.state,
                'is_notification_4_generated': survey.is_notification_4_generated,
                'survey_image': survey_image,
                'landowner_ids': [{
                    'id': lo.id,
                    'name': lo.name,
                    'father_name': lo.father_name or '',
                    'spouse_name': lo.spouse_name or '',
                    'caste': lo.caste or '',
                    'aadhar_number': lo.aadhar_number or '',
                    'rakba': lo.rakba or '',
                    'phone': lo.phone or '',
                } for lo in survey.landowner_ids],
            }

            return Response(
                json.dumps({
                    'success': True,
                    'data': survey_data
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_survey_details for survey_id {survey_id}: {str(e)}", exc_info=True)
            import traceback
            error_trace = traceback.format_exc()
            _logger.error(f"Traceback: {error_trace}")
            return Response(
                json.dumps({
                    'error': str(e),
                    'message': f'Error retrieving survey details: {str(e)}',
                    'survey_id': survey_id
                }),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/photo/<int:photo_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @check_permission
    def delete_survey_photo(self, photo_id, **kwargs):
        """
        Delete a survey photo by ID
        Only allowed if survey is not approved
        """
        try:
            # Get photo record
            photo = request.env['bhu.survey.photo'].sudo().browse(photo_id)
            if not photo.exists():
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Photo not found',
                        'message': f'Photo with ID {photo_id} does not exist'
                    }),
                    status=404,
                    content_type='application/json'
                )
            
            # Check survey state
            if photo.survey_id.state == 'approved':
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'PERMISSION_DENIED',
                        'message': 'Cannot delete photo from an approved survey'
                    }),
                    status=403,
                    content_type='application/json'
                )
                
            # Delete photo
            photo.unlink()
            
            return Response(
                json.dumps({
                    'success': True,
                    'message': 'Photo deleted successfully',
                    'id': photo_id
                }),
                status=200,
                content_type='application/json'
            )
            
        except Exception as e:
            _logger.error(f"Error deleting photo {photo_id}: {str(e)}", exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e),
                    'message': 'Internal Server Error'
                }),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/surveys', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def list_surveys(self, **kwargs):
        """
        List surveys with optional filters
        Query params: project_id, village_id, state, limit, offset
        Returns: JSON list of surveys
        """
        try:
            # Get query parameters
            project_id = request.httprequest.args.get('project_id', type=int)
            village_id = request.httprequest.args.get('village_id', type=int)
            district_id = request.httprequest.args.get('district_id', type=int)
            tehsil_id = request.httprequest.args.get('tehsil_id', type=int)
            q = request.httprequest.args.get('q') or request.httprequest.args.get('search')
            state = request.httprequest.args.get('state')
            survey_type = request.httprequest.args.get('survey_type')
            limit = request.httprequest.args.get('limit', type=int) or 100
            offset = request.httprequest.args.get('offset', type=int) or 0

            # Build domain
            domain = []
            if project_id:
                domain.append(('project_id', '=', project_id))
            if village_id:
                domain.append(('village_id', '=', village_id))
            if district_id:
                domain.append(('village_id.district_id', '=', district_id))
            if tehsil_id:
                domain.append(('village_id.tehsil_id', '=', tehsil_id))
            if survey_type:
                domain.append(('survey_type', '=', survey_type))
            if state:
                # Handle special case: 'pending' means all surveys that are NOT approved
                if state.lower() == 'pending':
                    domain.append(('state', '!=', 'approved'))
                else:
                    domain.append(('state', '=', state))

            if q:
                domain.append(('khasra_number', 'ilike', q))

            # Patwari: backend ir.rule is (own surveys OR village.user_id = me).
            # The mobile app also lists villages from projects/surveys (user/projects API).
            # When the client filters by village_id from that list, allow all surveys in that
            # village so results match the selected village; otherwise list Surveys would stay
            # empty while Odoo tabs show rows for admins or when master village.user_id differs.
            current_user = getattr(request, 'user', None)
            if current_user and current_user.bhuarjan_role in current_user.BHUKHADAN_PATWARI_ROLES:
                if village_id:
                    allowed_villages = set(
                        api_mobile_user_village_ids(request.env, current_user)
                    )
                    if village_id not in allowed_villages:
                        return Response(
                            json.dumps({
                                'success': True,
                                'data': [],
                                'total': 0,
                                'limit': limit,
                                'offset': offset,
                            }),
                            status=200,
                            content_type='application/json',
                        )
                    # Scoped village is authorized — do not AND strict pat domain (already filtered).
                else:
                    pat = api_patwari_survey_access_domain(current_user)
                    domain = AND([pat, domain]) if domain else pat

            # Search surveys
            surveys = request.env['bhu.survey'].sudo().search(domain, limit=limit, offset=offset, order='create_date desc')

            # Build response
            surveys_data = []
            for survey in surveys:
                surveys_data.append({
                    'id': survey.id,
                    'name': survey.name,
                    'survey_uuid': survey.survey_uuid,
                    'khasra_number': survey.khasra_number or '',
                    'project_id': survey.project_id.id if survey.project_id else None,
                    'project_name': survey.project_id.name if survey.project_id else '',
                    'village_id': survey.village_id.id if survey.village_id else None,
                    'village_name': survey.village_id.name if survey.village_id else '',
                    'tehsil_id': survey.tehsil_id.id if survey.tehsil_id else None,
                    'tehsil_name': survey.tehsil_id.name if survey.tehsil_id else '',
                    'district_id': survey.company_id.id if survey.company_id else None,
                    'district_name': survey.company_id.name if survey.company_id else '',
                    'survey_type': survey.survey_type or 'rural',
                    'survey_date': survey.survey_date.strftime('%Y-%m-%d') if survey.survey_date else None,
                    'total_area': survey.total_area,
                    'acquired_area': survey.acquired_area,
                    'has_traded_land': survey.has_traded_land or 'no',
                    'traded_land_area': survey.traded_land_area or 0.0,
                    'distance_from_main_road': survey.distance_from_main_road or 0.0,
                    'is_within_distance_for_award': bool(survey.is_within_distance_for_award),
                    'state': survey.state or '',
                    'is_notification_4_generated': survey.is_notification_4_generated,
                    'surveyor_id': survey.user_id.id if survey.user_id else None,
                    'surveyor_name': survey.user_id.name if survey.user_id else '',
                    'landowners_count': len(survey.landowner_ids),
                    'images_count': len(survey.photo_ids),
                    'tree_count': sum(survey.tree_line_ids.mapped('quantity')),
                })

            # Get total count
            total_count = request.env['bhu.survey'].sudo().search_count(domain)

            return Response(
                json.dumps({
                    'success': True,
                    'data': surveys_data,
                    'total': total_count,
                    'limit': limit,
                    'offset': offset
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in list_surveys: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    # Form 10 PDF and Excel export endpoints have been moved to separate controllers:
    # - controllers/api/survey_form10_pdf_api.py for PDF exports
    # - controllers/api/survey_form10_excel_api.py for Excel exports
    # Old Excel export methods removed - use controllers/api/survey_form10_excel_api.py instead.

