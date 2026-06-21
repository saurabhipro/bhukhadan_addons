# -*- coding: utf-8 -*-

import json
import logging
from datetime import timedelta, timezone
import datetime

from odoo import http
from odoo.http import request, Response

from .survey_api_helpers import register_survey_photos, build_canonical_s3_url, resolve_survey_from_api

# Try to import boto3 for S3 operations
try:
    import boto3
    from botocore.exceptions import ClientError
    from botocore.config import Config
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    _logger = logging.getLogger(__name__)
    _logger.warning("boto3 library not found. S3 presigned URL generation will not be available.")


class FileUploadAPIController(http.Controller):
    """File Upload API Controller for S3 presigned URLs"""

    _logger = logging.getLogger(__name__)

    @http.route('/api/bhuarjan/s3/presigned-urls', type='http', auth='public', methods=['POST'], csrf=False)
    def generate_s3_presigned_urls(self, **kwargs):
        """
        Generate S3 presigned URLs for file upload (supports single or multiple files)
        Accepts: JSON data with file_names (list) or file_name (string) and survey_id
        Returns: Presigned URLs for S3 upload
        
        Request Body:
        {
            "survey_id": 257,
            "file_names": ["image1.jpg", "document1.pdf"]
        }
        
        OR
        
        {
            "survey_id": 257,
            "file_name": "image1.jpg"
        }
        
        Response:
        {
            "success": true,
            "data": {
                "file_name": "image1.jpg",
                "presigned_url": "https://bhukhadan_core.s3.ap-south-1.amazonaws.com/surveys/257/image1.jpg?X-Amz-Algorithm=...",
                "content_type": "image/jpeg",
                "s3_key": "surveys/257/image1.jpg",
                "bucket_name": "bhuarjan",
                "region": "ap-south-1",
                "expires_in": 3600,
                "expires_at": "2025-11-19T12:00:00+00:00"
            }
        }
        """
        try:
            if not HAS_BOTO3:
                return Response(
                    json.dumps({'error': 'boto3 library is not installed. Please install it to use S3 presigned URLs.'}),
                    status=500,
                    content_type='application/json'
                )
            
            # Parse request data
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            
            # Support both single file_name and multiple file_names
            file_names = data.get('file_names', [])
            file_name = data.get('file_name')
            survey_id = data.get('survey_id')
            survey_uuid = data.get('survey_uuid')
            
            # Track if single file was provided
            is_single_file = False
            
            # If single file_name provided, convert to list
            if file_name and not file_names:
                file_names = [file_name]
                is_single_file = True
            
            if not file_names or not isinstance(file_names, list) or len(file_names) == 0:
                return Response(
                    json.dumps({'error': 'file_names (list) or file_name (string) is required'}),
                    status=400,
                    content_type='application/json'
                )
            
            if not survey_id and not survey_uuid:
                return Response(
                    json.dumps({'error': 'survey_id or survey_uuid is required'}),
                    status=400,
                    content_type='application/json'
                )
            
            survey = resolve_survey_from_api(request.env, survey_id, survey_uuid)
            if not survey.exists():
                return Response(
                    json.dumps({'error': 'Survey not found'}),
                    status=404,
                    content_type='application/json'
                )
            
            # Get AWS settings from global settings master
            settings_master = request.env['bhuarjan.settings.master'].sudo().search([
                ('active', '=', True)
            ], limit=1)
            
            if not settings_master:
                return Response(
                    json.dumps({'error': 'AWS settings not found. Please configure AWS settings in BhuKhadan Settings Master.'}),
                    status=404,
                    content_type='application/json'
                )
            
            if not settings_master.s3_bucket_name:
                return Response(
                    json.dumps({'error': 'S3 bucket name is not configured in settings'}),
                    status=400,
                    content_type='application/json'
                )
            
            if not settings_master.aws_access_key or not settings_master.aws_secret_key:
                return Response(
                    json.dumps({'error': 'AWS credentials are not configured in settings'}),
                    status=400,
                    content_type='application/json'
                )
            
            # Get AWS region (default to ap-south-1 if not set)
            aws_region = settings_master.aws_region or 'ap-south-1'
            
            # Create S3 client with proper region configuration
            # Use endpoint_url to ensure the region is included in the hostname
            # This ensures the presigned URL signature is calculated correctly
            endpoint_url = f'https://s3.{aws_region}.amazonaws.com'
            s3_config = Config(
                region_name=aws_region,
                signature_version='s3v4',
                s3={
                    'addressing_style': 'virtual'
                }
            )
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings_master.aws_access_key,
                aws_secret_access_key=settings_master.aws_secret_key,
                region_name=aws_region,
                endpoint_url=endpoint_url,
                config=s3_config
            )
            
            # Generate presigned URL (valid for 1 hour)
            expiration = timedelta(hours=1)
            expires_at = datetime.datetime.now(timezone.utc) + expiration
            
            # Generate presigned URLs for all files
            presigned_urls = []
            errors = []
            
            for file_name in file_names:
                try:
                    # Generate S3 key (path) for the file
                    s3_key = f"surveys/{survey.id}/{file_name}"
                    
                    # Determine content type based on file extension
                    content_type = 'application/octet-stream'  # default
                    file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
                    content_type_map = {
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'png': 'image/png',
                        'gif': 'image/gif',
                        'pdf': 'application/pdf',
                        'doc': 'application/msword',
                        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'xls': 'application/vnd.ms-excel',
                        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    }
                    if file_ext in content_type_map:
                        content_type = content_type_map[file_ext]
                    
                    # Generate presigned URL for PUT operation
                    # The endpoint_url and config ensure the region is included in the hostname
                    # and the signature is calculated correctly
                    presigned_url = s3_client.generate_presigned_url(
                        'put_object',
                        Params={
                            'Bucket': settings_master.s3_bucket_name,
                            'Key': s3_key,
                            'ContentType': content_type
                        },
                        ExpiresIn=int(expiration.total_seconds())
                    )

                    canonical_s3_url = build_canonical_s3_url(
                        settings_master.s3_bucket_name, aws_region, s3_key,
                    )

                    # Pre-register photo on survey so web table shows it after S3 upload
                    register_survey_photos(request.env, survey, [{
                        's3_url': canonical_s3_url,
                        'filename': file_name,
                        's3_key': s3_key,
                    }])
                    
                    presigned_urls.append({
                        'file_name': file_name,
                        'presigned_url': presigned_url,
                        's3_url': canonical_s3_url,
                        's3_key': s3_key,
                        'bucket_name': settings_master.s3_bucket_name,
                        'content_type': content_type,
                        'expires_in': int(expiration.total_seconds()),
                        'expires_at': expires_at.isoformat(),
                        'region': aws_region
                    })
                    
                except ClientError as e:
                    error_msg = f"Error generating presigned URL for {file_name}: {str(e)}"
                    self._logger.error(error_msg, exc_info=True)
                    errors.append({
                        'file_name': file_name,
                        'error': str(e)
                    })
                except Exception as e:
                    error_msg = f"Unexpected error for {file_name}: {str(e)}"
                    self._logger.error(error_msg, exc_info=True)
                    errors.append({
                        'file_name': file_name,
                        'error': str(e)
                    })
            
            # Return response
            # If single file, return simplified response for backward compatibility
            if is_single_file and len(presigned_urls) == 1:
                return Response(
                    json.dumps({
                        'success': True,
                        'data': presigned_urls[0]
                    }),
                    status=200,
                    content_type='application/json'
                )
            
            # Multiple files response
            response_data = {
                'success': True,
                'data': {
                    'presigned_urls': presigned_urls,
                    'total_files': len(file_names),
                    'successful': len(presigned_urls),
                    'failed': len(errors),
                    'survey_id': survey_id
                }
            }
            
            if errors:
                response_data['data']['errors'] = errors
            
            response_data['data']['survey_id'] = survey.id
            
            return Response(
                json.dumps(response_data),
                status=200,
                content_type='application/json'
            )
            
        except Exception as e:
            self._logger.error(f"Error in generate_s3_presigned_urls: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/survey/images', type='http', auth='public', methods=['GET'], csrf=False)
    def get_survey_images(self, **kwargs):
        """
        Get all images from S3 for a specific survey
        
        Query Parameters:
        - survey_id (required): Survey ID
        - photo_type_id (optional): Filter by photo type ID
        
        Returns: List of images with metadata
        
        Example Response:
        {
            "success": true,
            "data": {
                "survey_id": 257,
                "total_images": 3,
                "images": [
                    {
                        "id": 1,
                        "photo_type_id": 1,
                        "photo_type_name": "Land",
                        "s3_url": "https://bhukhadan_core.s3.ap-south-1.amazonaws.com/surveys/257/image1.jpg",
                        "filename": "image1.jpg",
                        "file_size": 245678,
                        "sequence": 10
                    }
                ]
            }
        }
        """
        try:
            survey_id = kwargs.get('survey_id')
            survey_uuid = kwargs.get('survey_uuid')
            if not survey_id and not survey_uuid:
                return Response(
                    json.dumps({'error': 'survey_id or survey_uuid is required'}),
                    status=400,
                    content_type='application/json'
                )

            survey = resolve_survey_from_api(request.env, survey_id, survey_uuid)
            if not survey.exists():
                return Response(
                    json.dumps({'error': 'Survey not found'}),
                    status=404,
                    content_type='application/json'
                )

            Photo = request.env['bhu.survey.photo'].sudo()
            before = len(survey.photo_ids)
            Photo.sync_from_s3_for_survey(survey)
            registered_count = max(len(survey.photo_ids) - before, 0)

            # Get query parameters
            photo_type_id = kwargs.get('photo_type_id')
            active_only = kwargs.get('active_only', 'true').lower() == 'true'
            
            # Build domain
            domain = [('survey_id', '=', survey.id)]
            if photo_type_id:
                try:
                    domain.append(('photo_type_id', '=', int(photo_type_id)))
                except ValueError:
                    return Response(
                        json.dumps({'error': 'Invalid photo_type_id. Must be an integer.'}),
                        status=400,
                        content_type='application/json'
                    )
            if active_only:
                domain.append(('active', '=', True))
            
            # Get photos
            photos = request.env['bhu.survey.photo'].sudo().search(domain, order='sequence, create_date desc')
            
            # Format response
            images = []
            for photo in photos:
                images.append({
                    'id': photo.id,
                    'photo_type_id': photo.photo_type_id.id if photo.photo_type_id else None,
                    'photo_type_name': photo.photo_type_id.name if photo.photo_type_id else None,
                    's3_url': photo.s3_url,
                    'filename': photo.filename or '',
                    'file_size': photo.file_size or 0,
                    'latitude': photo.latitude,
                    'longitude': photo.longitude,
                    'sequence': photo.sequence
                })
            
            response_data = {
                'success': True,
                'data': {
                    'survey_id': survey.id,
                    'synced_from_s3': registered_count,
                    'total_images': len(images),
                    'images': images
                }
            }
            
            return Response(
                json.dumps(response_data),
                status=200,
                content_type='application/json'
            )
            
        except Exception as e:
            self._logger.error(f"Error in get_survey_images: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/survey/photos/sync-from-s3', type='http', auth='public', methods=['POST'], csrf=False)
    def sync_survey_photos_from_s3(self, **kwargs):
        """Register S3 objects under surveys/<id>/ that are not yet in bhu.survey.photo."""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            survey_id = kwargs.get('survey_id') or data.get('survey_id')
            survey_uuid = kwargs.get('survey_uuid') or data.get('survey_uuid')
            if not survey_id and not survey_uuid:
                return Response(
                    json.dumps({'error': 'survey_id or survey_uuid is required'}),
                    status=400,
                    content_type='application/json',
                )

            survey = resolve_survey_from_api(request.env, survey_id, survey_uuid)
            if not survey.exists():
                return Response(
                    json.dumps({'error': 'Survey not found'}),
                    status=404,
                    content_type='application/json',
                )

            before = len(survey.photo_ids)
            request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)
            registered_count = max(len(survey.photo_ids) - before, 0)
            return Response(
                json.dumps({
                    'success': True,
                    'message': f'Synced {registered_count} photo(s) for survey {survey.id}',
                    'data': {
                        'survey_id': survey.id,
                        'registered_count': registered_count,
                        'total_photos': len(survey.photo_ids),
                    },
                }),
                status=200,
                content_type='application/json',
            )
        except Exception as e:
            self._logger.error(f"Error in sync_survey_photos_from_s3: {e}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json',
            )

