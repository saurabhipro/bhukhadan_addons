# -*- coding: utf-8 -*-
"""Shared helpers for survey/mobile REST API controllers."""

import logging

_logger = logging.getLogger(__name__)


def normalize_s3_url(url):
    """Strip query params from presigned URLs so DB stores a stable object URL."""
    if not url:
        return ''
    return url.split('?')[0].strip()


def build_canonical_s3_url(bucket, region, s3_key):
    return f'https://{bucket}.s3.{region}.amazonaws.com/{s3_key}'


def resolve_survey_from_api(env, survey_id=None, survey_uuid=None):
    """Resolve bhu.survey from numeric id and/or survey_uuid (mobile offline flows)."""
    Survey = env['bhu.survey'].sudo()
    survey = Survey.browse()
    if survey_id:
        try:
            survey = Survey.browse(int(survey_id))
        except (TypeError, ValueError):
            survey = Survey.search([('survey_uuid', '=', str(survey_id))], limit=1)
    if not survey.exists() and survey_uuid:
        survey = Survey.search([('survey_uuid', '=', str(survey_uuid))], limit=1)
    return survey


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


def api_patwari_survey_access_domain(user):
    """Domain matching ir.rule on bhu.survey for Patwari (own surveys OR village patwari).

    Keeps HTTP list/detail behavior aligned with backend access after removal of
    res.users.village_ids.
    """
    return ['|', ('user_id', '=', user.id), ('village_id.user_id', '=', user.id)]


def api_mobile_user_village_ids(env, user):
    """Village ids for project/hierarchy mobile APIs (GET user/projects, department projects).

    Patwaris: ``bhu.village.user_id`` plus villages from **any survey they may access**
    (same rule as Patwari survey record rules: own surveys OR surveys in villages where
    this user is assigned Patwari). Also includes villages on projects that list this user
    in ``patwari_ids`` (covers UI project assignment).

    Other roles: ``bhu.village.user_id`` only.
    """
    # Odoo 18+: Environment has no ``.sudo()``; use superuser env via ``(su=True)``.
    sudo = env(su=True)
    ids = set(sudo['bhu.village'].search([('user_id', '=', user.id)]).ids)
    if getattr(user, 'bhuarjan_role', None) == 'patwari':
        ids.update(
            sudo['bhu.survey']
            .search(
                [
                    '|',
                    ('user_id', '=', user.id),
                    ('village_id.user_id', '=', user.id),
                    ('village_id', '!=', False),
                ]
            )
            .mapped('village_id')
            .ids
        )
        ids.update(
            sudo['bhu.project']
            .with_context(skip_project_domain_filter=True)
            .search([('patwari_ids', 'in', user.id)])
            .mapped('village_ids')
            .ids
        )
    return list(dict.fromkeys(ids))


def api_resolve_tehsil_id(env, village_id, tehsil_id=None):
    """Resolve tehsil from API payload or village master (mobile app often omits tehsil_id)."""
    if tehsil_id:
        try:
            tid = int(tehsil_id)
        except (TypeError, ValueError):
            tid = False
        if tid:
            tehsil = env['bhu.tehsil'].sudo().browse(tid)
            if tehsil.exists():
                return tid

    if not village_id:
        return False
    try:
        vid = int(village_id)
    except (TypeError, ValueError):
        return False
    village = env['bhu.village'].sudo().browse(vid)
    if village.exists() and village.tehsil_id:
        return village.tehsil_id.id
    return False


def api_mobile_user_geography(env, user):
    """Villages / tehsils / sub-divisions for GET /api/bhuarjan/users payloads.

    Mirrors former res.users M2M richness: role-based masters plus geography inferred from
    assigned/survey villages.
    """
    sudo = env(su=True)
    villages = sudo['bhu.village'].search([('user_id', '=', user.id)])
    if getattr(user, 'bhuarjan_role', None) == 'patwari':
        survey_villages = sudo['bhu.survey'].search(
            [
                '|',
                ('user_id', '=', user.id),
                ('village_id.user_id', '=', user.id),
                ('village_id', '!=', False),
            ]
        ).mapped('village_id')
        project_villages = (
            sudo['bhu.project']
            .with_context(skip_project_domain_filter=True)
            .search([('patwari_ids', 'in', user.id)])
            .mapped('village_ids')
        )
        villages = villages | survey_villages | project_villages

    tehsils = sudo['bhu.tehsil'].search([('user_id', '=', user.id)]) | villages.mapped('tehsil_id')
    subdivisions = (
        sudo['bhu.sub.division'].search([('user_id', '=', user.id)])
        | villages.mapped('sub_division_id')
    )
    return villages, tehsils, subdivisions


def api_mobile_survey_submitted_now():
    """Naive UTC datetime for survey submitted_date (Odoo-compatible)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


def api_mobile_resolve_survey_state(requested_state=None, default='approved'):
    """Map mobile/API survey state: app submit → approved (skip department approval)."""
    if requested_state is None:
        return default
    if requested_state == 'submitted':
        return 'approved'
    if requested_state in ('draft', 'rejected', 'approved'):
        return requested_state
    return default


def api_apply_mobile_auto_approve_vals(vals):
    """Mutate survey create/write vals from mobile API (auto-approve unless draft/rejected)."""
    state = api_mobile_resolve_survey_state(vals.get('state'))
    vals['state'] = state
    if state in ('submitted', 'approved') and not vals.get('submitted_date'):
        vals['submitted_date'] = api_mobile_survey_submitted_now()


def api_auto_approve_survey_after_mobile_upload(survey, user):
    """Finalize survey as approved after mobile upload (no department user step)."""
    if not survey or not survey.exists():
        return
    if survey.state in ('approved', 'rejected'):
        return
    if survey.state == 'draft':
        return
    write_vals = {'state': 'approved'}
    if not survey.submitted_date:
        write_vals['submitted_date'] = api_mobile_survey_submitted_now()
    survey.sudo().write(write_vals)
    survey.message_post(
        body='Survey auto-approved (mobile app upload) by %s'
        % (user.name if user else 'API'),
        message_type='notification',
    )


class SurveyAPIHelperMixin:
    """Mixin with shared helper methods for REST controllers."""
    def _get_selection_label(self, record, field_name, value):
        """Get the label for a selection field value"""
        if not value:
            return ''
        try:
            field = record._fields.get(field_name)
            if not field:
                return ''
            selection = field.selection
            # Handle callable selection (dynamic selection)
            if callable(selection):
                selection = selection(record)
            # Convert to dict and get label
            selection_dict = dict(selection) if selection else {}
            return selection_dict.get(value, '')
        except Exception:
            return ''
