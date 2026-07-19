# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def normalize_s3_url(url):
    """Strip query params from presigned URLs so DB stores a stable object URL."""
    if not url:
        return ''
    return url.split('?')[0].strip()


def build_canonical_s3_url(bucket, region, s3_key):
    return f'https://{bucket}.s3.{region}.amazonaws.com/{s3_key}'


def register_survey_photos(env, survey, photos_data):
    """Create or update bhu.survey.photo rows for a survey (dedupe by canonical S3 URL)."""
    if not survey or not survey.exists():
        return []
    Photo = env['bhu.survey.photo'].sudo()
    photo_type_model = env['bhu.photo.type'].sudo()
    settings = env['bhuarjan.settings.master'].sudo().search([('active', '=', True)], limit=1)
    registered = []

    for photo in photos_data or []:
        if not isinstance(photo, dict):
            continue

        raw_url = photo.get('s3_url') or ''
        s3_key = photo.get('s3_key') or ''
        filename = photo.get('filename') or photo.get('file_name') or ''

        if not raw_url and s3_key and settings and settings.s3_bucket_name:
            region = settings.aws_region or 'ap-south-1'
            raw_url = build_canonical_s3_url(settings.s3_bucket_name, region, s3_key)

        s3_url = normalize_s3_url(raw_url)
        if not s3_url:
            continue

        if not filename:
            filename = s3_url.rsplit('/', 1)[-1] or 'photo.jpg'

        existing = Photo.search([
            ('survey_id', '=', survey.id),
            '|', ('s3_url', '=', s3_url), ('s3_url', 'like', s3_url + '?%'),
        ], limit=1)

        vals = {
            'filename': filename,
            'file_size': int(photo.get('file_size') or 0),
        }
        if photo.get('latitude') is not None:
            vals['latitude'] = photo.get('latitude')
        if photo.get('longitude') is not None:
            vals['longitude'] = photo.get('longitude')

        photo_type_id = photo.get('photo_type_id')
        if photo_type_id:
            pt = photo_type_model.browse(int(photo_type_id))
            if pt.exists():
                vals['photo_type_id'] = pt.id
            else:
                _logger.warning(
                    'Ignoring invalid photo_type_id=%s for survey %s',
                    photo_type_id, survey.id,
                )

        if existing:
            existing.write(vals)
            registered.append(existing)
        else:
            vals.update({'survey_id': survey.id, 's3_url': s3_url})
            registered.append(Photo.create(vals))

    return registered
