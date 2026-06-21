# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup, escape
import logging
import base64
import os
from datetime import datetime

# Try to import boto3 for S3 operations
try:
    import boto3
    from botocore.exceptions import ClientError
    from botocore.config import Config
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

_logger = logging.getLogger(__name__)


class SurveyPhoto(models.Model):
    _name = 'bhu.survey.photo'
    _description = 'Survey Photo / सर्वे फोटो'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, create_date desc'

    survey_id = fields.Many2one('bhu.survey', string='Survey / सर्वे', required=True, 
                               ondelete='cascade', tracking=True)
    photo_type_id = fields.Many2one('bhu.photo.type', string='Photo Type / फोटो प्रकार', 
                                    required=False, tracking=True,
                                    help='Type of photo (e.g., Land, Well, House). Optional.')
    photo_type_name = fields.Char(related='photo_type_id.name', string='Photo Type Name', 
                                 readonly=True, store=True)
    s3_url = fields.Char(string='S3 URL / S3 यूआरएल', required=False, tracking=True,
                        index=False,  # Don't create index to avoid PostgreSQL row size limit
                        help='Full S3 URL of the uploaded photo. Will be automatically set when a file is uploaded.')
    filename = fields.Char(string='Filename / फ़ाइल नाम', tracking=True,
                          help='Original filename of the uploaded photo')
    file_size = fields.Integer(string='File Size (bytes) / फ़ाइल आकार', tracking=True,
                              help='Size of the file in bytes')
    sequence = fields.Integer(string='Sequence / क्रम', default=10, tracking=True,
                             help='Display order')
    active = fields.Boolean(string='Active / सक्रिय', default=True, tracking=True,
                           help='Set to false to archive the record')
    
    # Location Details
    latitude = fields.Float(string='Latitude / अक्षांश', digits=(10, 8), help='GPS Latitude coordinate', tracking=True)
    longitude = fields.Float(string='Longitude / देशांतर', digits=(11, 8), help='GPS Longitude coordinate', tracking=True)
    
    google_maps_url = fields.Char(string='Google Maps / गूगल मैप्स', compute='_compute_google_maps_url', store=True)

    @api.depends('latitude', 'longitude')
    def _compute_google_maps_url(self):
        for record in self:
            # Use provided lat/long or fallback to default testing coordinates
            lat = record.latitude or 28.43372368772261
            lon = record.longitude or 77.06891353643873
            
            record.google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"

    # Binary field for file upload
    file_upload = fields.Binary(string='Upload File / फ़ाइल अपलोड करें', 
                                help='Select a file to upload to S3. The file will be automatically uploaded and the S3 URL will be generated.')
    
    # Computed fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    # Short filename from S3 URL for display
    s3_filename_display = fields.Char(string='S3 File / S3 फ़ाइल', 
                                      compute='_compute_s3_filename_display',
                                      store=False,
                                      help='Short filename extracted from S3 URL')
    image_preview = fields.Html(
        string='Preview',
        compute='_compute_image_preview',
        sanitize=False,
    )

    @api.depends('s3_url')
    def _compute_image_preview(self):
        for record in self:
            url = (record.s3_url or '').split('?')[0]
            if url:
                record.image_preview = Markup(
                    f'<img src="{escape(url)}" alt="Survey photo" '
                    f'style="max-height:56px;max-width:88px;border-radius:4px;object-fit:cover;" />'
                )
            else:
                record.image_preview = Markup('')

    @api.depends('photo_type_id', 'filename', 'survey_id')
    def _compute_display_name(self):
        for record in self:
            if not record.survey_id:
                record.display_name = record.filename or _('Photo')
                continue
            survey_name = record.survey_id.name or "New"
            
            # Count existing photos for this survey to generate sequence number
            domain = [('survey_id', '=', record.survey_id.id)]
            
            if record.id and isinstance(record.id, int):
                # If record exists, count photos created before it
                domain.append(('id', '<', record.id))
                count = self.env['bhu.survey.photo'].search_count(domain) + 1
            else:
                # If record is new, count all existing photos and add 1
                count = self.env['bhu.survey.photo'].search_count(domain) + 1
            
            record.display_name = f"{survey_name}_{count}"

    @api.depends('s3_url')
    def _compute_s3_filename_display(self):
        """Extract just the filename from S3 URL for display"""
        for record in self:
            if record.s3_url:
                # Extract filename from URL (last part after /)
                filename = record.s3_url.split('/')[-1]
                # Remove query parameters if any
                filename = filename.split('?')[0]
                # Show just the filename, not the full path
                record.s3_filename_display = filename
            else:
                record.s3_filename_display = ''

    def _upload_file_to_s3(self, file_data, filename=None):
        """Helper method to upload file to S3"""
        if not HAS_BOTO3:
            raise ValidationError(_('boto3 library is not installed. Please install it to upload files to S3.'))
        
        if not self.survey_id:
            raise ValidationError(_('Please select a survey first before uploading a file.'))
        
        # Get S3 settings from settings master
        settings = self.env['bhuarjan.settings.master'].search([], limit=1)
        if not settings:
            raise ValidationError(_('S3 settings not configured. Please configure AWS settings in BhuKhadan Settings.'))
        
        if not all([settings.aws_access_key, settings.aws_secret_key, settings.s3_bucket_name, settings.aws_region]):
            raise ValidationError(_('S3 settings are incomplete. Please configure all AWS settings in BhuKhadan Settings.'))
        
        file_size = len(file_data)
        
        # Determine file extension and content type from file data or filename
        file_ext = '.jpg'
        content_type = 'image/jpeg'
        
        # Check file signature (magic bytes) to determine file type
        if file_data.startswith(b'\x89PNG\r\n\x1a\n'):
            file_ext = '.png'
            content_type = 'image/png'
        elif file_data.startswith(b'%PDF'):
            file_ext = '.pdf'
            content_type = 'application/pdf'
        elif file_data.startswith(b'\xff\xd8\xff'):
            file_ext = '.jpg'
            content_type = 'image/jpeg'
        
        # Use filename if available, otherwise generate one
        if filename:
            # Extract extension from filename if provided
            filename_ext = os.path.splitext(filename)[1]
            if filename_ext:
                file_ext = filename_ext
                # Update content type based on extension
                if file_ext.lower() == '.png':
                    content_type = 'image/png'
                elif file_ext.lower() == '.pdf':
                    content_type = 'application/pdf'
                elif file_ext.lower() in ['.jpg', '.jpeg']:
                    content_type = 'image/jpeg'
        else:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"photo_{timestamp}{file_ext}"
        
        # Generate S3 key
        survey_id = self.survey_id.id
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        s3_key = f"surveys/{survey_id}/{timestamp}{file_ext}"
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key,
            aws_secret_access_key=settings.aws_secret_key,
            region_name=settings.aws_region,
            config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'})
        )
        
        # Upload to S3
        s3_client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_data,
            ContentType=content_type
        )
        
        # Generate S3 URL
        s3_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        
        return {
            's3_url': s3_url,
            'filename': filename,
            'file_size': file_size
        }

    @api.onchange('file_upload')
    def _onchange_file_upload(self):
        """Upload file to S3 when file_upload is set"""
        if not self.file_upload:
            return
        
        try:
            # Decode base64 file
            file_data = base64.b64decode(self.file_upload)
            
            # Upload to S3
            result = self._upload_file_to_s3(file_data, self.filename)
            
            # Update fields
            self.s3_url = result['s3_url']
            self.filename = result['filename']
            self.file_size = result['file_size']
            
            # Clear the binary field after upload
            self.file_upload = False
            
            _logger.info(f"File uploaded to S3: {result['s3_url']}")
            
        except ValidationError:
            raise
        except ClientError as e:
            _logger.error(f"Error uploading file to S3: {str(e)}", exc_info=True)
            raise ValidationError(_('Error uploading file to S3: %s') % str(e))
        except Exception as e:
            _logger.error(f"Unexpected error uploading file: {str(e)}", exc_info=True)
            raise ValidationError(_('Error uploading file: %s') % str(e))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle file upload and normalize S3 URLs."""
        for vals in vals_list:
            if vals.get('s3_url'):
                vals['s3_url'] = vals['s3_url'].split('?')[0].strip()
            if vals.get('file_upload'):
                file_data = base64.b64decode(vals['file_upload'])
                # Create a temporary record to use the upload method
                temp_vals = vals.copy()
                temp_vals.pop('file_upload', None)  # Remove file_upload to avoid issues
                temp_record = self.new(temp_vals)
                result = temp_record._upload_file_to_s3(file_data, vals.get('filename'))
                vals['s3_url'] = result['s3_url']
                vals['filename'] = result['filename']
                vals['file_size'] = result['file_size']
                vals['file_upload'] = False  # Clear binary field
        
        return super().create(vals_list)

    def write(self, vals):
        """Override write to handle file upload and normalize S3 URLs."""
        if vals.get('s3_url'):
            vals['s3_url'] = vals['s3_url'].split('?')[0].strip()
        if vals.get('file_upload'):
            file_data = base64.b64decode(vals['file_upload'])
            result = self._upload_file_to_s3(file_data, vals.get('filename'))
            vals['s3_url'] = result['s3_url']
            vals['filename'] = result['filename']
            vals['file_size'] = result['file_size']
            vals['file_upload'] = False  # Clear binary field
        
        return super().write(vals)

    @api.model
    def _get_s3_settings(self):
        return self.env['bhuarjan.settings.master'].sudo().search([('active', '=', True)], limit=1)

    @api.model
    def _get_s3_client(self, settings):
        if not HAS_BOTO3 or not settings:
            return None, None
        if not all([settings.aws_access_key, settings.aws_secret_key, settings.s3_bucket_name]):
            return None, None
        region = settings.aws_region or 'ap-south-1'
        client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key,
            aws_secret_access_key=settings.aws_secret_key,
            region_name=region,
            config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}),
        )
        return client, region

    @api.model
    def _survey_s3_prefixes(self, survey):
        prefixes = {f'surveys/{survey.id}/'}
        if survey.survey_uuid:
            prefixes.add(f'surveys/{survey.survey_uuid}/')
        return prefixes

    @api.model
    def _relink_orphaned_photos(self, survey):
        """Attach photo rows whose S3 key path belongs to this survey."""
        sid = str(survey.id)
        orphans = self.sudo().search([
            ('survey_id', '!=', survey.id),
            ('s3_url', 'ilike', f'%/surveys/{sid}/%'),
        ])
        if orphans:
            orphans.write({'survey_id': survey.id})
        if survey.survey_uuid:
            uuid_orphans = self.sudo().search([
                ('survey_id', '!=', survey.id),
                ('s3_url', 'ilike', f'%/surveys/{survey.survey_uuid}/%'),
            ])
            if uuid_orphans:
                uuid_orphans.write({'survey_id': survey.id})

    @api.model
    def sync_from_s3_for_survey(self, survey):
        """Register S3 objects for this survey and relink mis-linked photo rows."""
        if not survey or not survey.exists():
            return self.browse()

        from odoo.addons.bhukhadan_core.controllers.api.survey_api_helpers import (
            build_canonical_s3_url,
            register_survey_photos,
        )

        self._relink_orphaned_photos(survey)

        settings = self._get_s3_settings()
        s3_client, region = self._get_s3_client(settings)
        if not s3_client or not settings:
            _logger.warning('S3 sync skipped for survey %s: settings or boto3 unavailable', survey.id)
            return self.browse()

        payloads = []
        seen_keys = set()
        for prefix in self._survey_s3_prefixes(survey):
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=settings.s3_bucket_name, Prefix=prefix):
                for obj in page.get('Contents') or []:
                    key = obj.get('Key') or ''
                    if not key or key.endswith('/') or key in seen_keys:
                        continue
                    seen_keys.add(key)
                    payloads.append({
                        's3_key': key,
                        's3_url': build_canonical_s3_url(settings.s3_bucket_name, region, key),
                        'filename': key.rsplit('/', 1)[-1],
                        'file_size': int(obj.get('Size') or 0),
                    })

        if payloads:
            register_survey_photos(self.env, survey, payloads)
        return survey.photo_ids

    @api.model
    def cron_sync_recent_survey_photos_from_s3(self):
        """Hourly job: sync S3 photos for recent surveys that have none in Odoo."""
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(days=120)
        surveys = self.env['bhu.survey'].sudo().search([
            ('create_date', '>=', cutoff),
        ])
        synced = 0
        for survey in surveys:
            before = len(survey.photo_ids)
            self.sync_from_s3_for_survey(survey)
            if len(survey.photo_ids) > before:
                synced += 1
        _logger.info('Survey photo cron: synced photos for %s survey(s)', synced)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        if not self.env.context.get('skip_photo_sync'):
            survey_ids = {
                term[2] for term in (domain or [])
                if isinstance(term, (list, tuple)) and len(term) == 3
                and term[0] == 'survey_id' and term[1] == '=' and term[2]
            }
            if len(survey_ids) == 1:
                survey = self.env['bhu.survey'].browse(next(iter(survey_ids)))
                if survey.exists():
                    self.sync_from_s3_for_survey(survey)
        return super().web_search_read(
            domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit,
        )

    @api.constrains('s3_url')
    def _check_s3_url_unique(self):
        """Check S3 URL uniqueness at application level (not database level to avoid index size issues)"""
        for record in self:
            if record.s3_url:
                duplicates = self.search([
                    ('s3_url', '=', record.s3_url),
                    ('id', '!=', record.id)
                ])
                if duplicates:
                    raise ValidationError(_('S3 URL must be unique! / S3 यूआरएल अद्वितीय होना चाहिए!'))
    
    # Note: Removed unique constraint on s3_url because:
    # 1. Long URLs can exceed PostgreSQL's index row size limit (8191 bytes)
    # 2. Uniqueness is now enforced at the application level via _check_s3_url_unique
    # 3. S3 URLs are already unique by design (they include timestamps and unique identifiers)
    # _sql_constraints = [
    #     ('s3_url_unique', 'unique(s3_url)', 'S3 URL must be unique! / S3 यूआरएल अद्वितीय होना चाहिए!')
    # ]

