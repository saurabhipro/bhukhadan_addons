# -*- coding: utf-8 -*-
"""Survey REST API: create, read, update."""

import json
import logging

from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request, Response
from odoo.osv.expression import AND

from .main import check_permission
from odoo.addons.bhukhadan_core.utils.survey_api import (
    api_add_survey_house_owners,
    api_add_survey_landowners,
    api_add_survey_tree_lines,
    api_assert_survey_editable,
    api_build_survey_list_domain,
    api_build_survey_update_vals,
    api_build_survey_vals,
    api_json_error,
    api_patwari_survey_domain,
    api_resolve_survey,
    api_serialize_survey,
    api_user_can_access_survey,
    api_serialize_landowner,
    api_serialize_house_owner,
    api_serialize_tree_line,
)
from odoo.addons.bhukhadan_core.utils.survey_s3 import register_survey_photos

_logger = logging.getLogger(__name__)


class SurveyAPIController(http.Controller):

    def _current_user(self):
        return getattr(request, 'user', None) or request.env.user

    def _json_response(self, payload, status=200):
        return Response(json.dumps(payload), status=status, content_type='application/json')

    def _parse_json_body(self):
        return json.loads(request.httprequest.data.decode('utf-8') or '{}')

    def _list_request_args(self):
        """Merge JSON body and query-string params (query wins on conflict)."""
        merged = {}
        if request.httprequest.data:
            try:
                data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
                if isinstance(data, dict):
                    merged.update(data)
            except json.JSONDecodeError:
                pass
        for key in request.httprequest.args:
            merged[key] = request.httprequest.args.get(key)
        return merged

    @http.route('/api/bhukhadan/survey', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def create_survey(self, **kwargs):
        try:
            data = self._parse_json_body()
            user = self._current_user()
            user_id = data.get('user_id') or user.id
            survey_vals = api_build_survey_vals(request.env, data, user_id=user_id)
            survey = request.env['bhu.survey'].sudo().create(survey_vals)

            if data.get('photos'):
                register_survey_photos(request.env, survey, data['photos'])
                request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)

            return self._json_response({
                'success': True,
                'data': api_serialize_survey(
                    survey,
                    include_image=bool(data.get('include_survey_image')),
                ),
            }, status=201)
        except ValidationError as err:
            payload, status = api_json_error(str(err))
            return self._json_response(payload, status=status)
        except json.JSONDecodeError:
            payload, status = api_json_error('Invalid JSON body', error_code='INVALID_JSON')
            return self._json_response(payload, status=status)
        except Exception as err:
            _logger.exception('Survey create failed')
            return self._json_response({'success': False, 'error': str(err)}, status=500)

    @http.route('/api/bhukhadan/survey', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def list_surveys(self, **kwargs):
        try:
            args = self._list_request_args()
            domain = api_build_survey_list_domain(request.env, args)

            user = self._current_user()
            if user.bhuarjan_role in request.env['res.users'].BHUKHADAN_PATWARI_ROLES:
                pat_domain = api_patwari_survey_domain(user)
                domain = AND([pat_domain, domain]) if domain else pat_domain

            limit = int(args.get('limit') or 100)
            offset = int(args.get('offset') or 0)
            Survey = request.env['bhu.survey'].sudo()
            surveys = Survey.search(domain, limit=limit, offset=offset, order='create_date desc')
            total = Survey.search_count(domain)

            return self._json_response({
                'success': True,
                'data': [api_serialize_survey(s, summary=True) for s in surveys],
                'total': total,
                'limit': limit,
                'offset': offset,
            })
        except ValidationError as err:
            payload, status = api_json_error(str(err))
            return self._json_response(payload, status=status)
        except Exception as err:
            _logger.exception('Survey list failed')
            return self._json_response({'success': False, 'error': str(err)}, status=500)

    @http.route('/api/bhukhadan/survey/detail', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_survey_detail(self, **kwargs):
        args = request.httprequest.args
        survey = api_resolve_survey(
            request.env,
            survey_id=args.get('survey_id', type=int),
            survey_uuid=args.get('survey_uuid'),
        )
        if not survey.exists():
            payload, status = api_json_error('Survey not found', error_code='NOT_FOUND', status=404)
            return self._json_response(payload, status=status)
        return self._survey_detail_response(
            survey,
            include_image=args.get('include_survey_image', '').lower() in ('1', 'true', 'yes'),
        )

    @http.route('/api/bhukhadan/survey/<int:survey_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_survey(self, survey_id, **kwargs):
        survey = request.env['bhu.survey'].sudo().browse(survey_id)
        if not survey.exists():
            payload, status = api_json_error('Survey not found', error_code='NOT_FOUND', status=404)
            return self._json_response(payload, status=status)
        include_image = request.httprequest.args.get('include_survey_image', '').lower() in ('1', 'true', 'yes')
        return self._survey_detail_response(survey, include_image=include_image)

    def _survey_detail_response(self, survey, include_image=False):
        user = self._current_user()
        if not api_user_can_access_survey(user, survey):
            raise AccessError('You do not have access to this survey')
        request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)
        return self._json_response({
            'success': True,
            'data': api_serialize_survey(survey, include_image=include_image),
        })

    def _get_survey_for_mutation(self, survey_id):
        survey = request.env['bhu.survey'].sudo().browse(survey_id)
        if not survey.exists():
            payload, status = api_json_error('Survey not found', error_code='NOT_FOUND', status=404)
            return None, self._json_response(payload, status=status)
        user = self._current_user()
        if not api_user_can_access_survey(user, survey):
            raise AccessError('You do not have access to this survey')
        api_assert_survey_editable(survey)
        return survey, None

    def _has_survey_append_payload(self, data):
        return bool(
            data.get('landowners')
            or data.get('landowner_ids')
            or data.get('house_owners')
            or data.get('house_owner_ids')
            or data.get('tree_lines')
        )

    @http.route(
        '/api/bhukhadan/survey/<int:survey_id>/owners',
        type='http', auth='public', methods=['POST'], csrf=False,
    )
    @check_permission
    def add_survey_owners(self, survey_id, **kwargs):
        try:
            survey, error_response = self._get_survey_for_mutation(survey_id)
            if error_response:
                return error_response

            data = self._parse_json_body()
            if not self._has_survey_append_payload(data):
                payload, status = api_json_error(
                    'Provide at least one of: landowners[], landowner_ids[], '
                    'house_owners[], house_owner_ids[], tree_lines[]',
                )
                return self._json_response(payload, status=status)

            added_landowners = request.env['bhu.landowner'].sudo().browse()
            added_house_owners = request.env['bhu.house.owner'].sudo().browse()
            added_tree_lines = request.env['bhu.survey.tree.line'].sudo().browse()

            if data.get('landowners') or data.get('landowner_ids'):
                added_landowners = api_add_survey_landowners(request.env, survey, data)
            if data.get('house_owners') or data.get('house_owner_ids'):
                added_house_owners = api_add_survey_house_owners(request.env, survey, data)
            if data.get('tree_lines'):
                added_tree_lines = api_add_survey_tree_lines(request.env, survey, data)

            return self._json_response({
                'success': True,
                'message': 'Survey data added successfully',
                'data': {
                    'survey_id': survey.id,
                    'landowners': [api_serialize_landowner(lo) for lo in added_landowners],
                    'house_owners': [api_serialize_house_owner(ho) for ho in added_house_owners],
                    'tree_lines': [api_serialize_tree_line(line) for line in added_tree_lines],
                },
            }, status=201)
        except AccessError as err:
            return self._json_response({'success': False, 'error': str(err)}, status=403)
        except ValidationError as err:
            payload, status = api_json_error(str(err))
            return self._json_response(payload, status=status)
        except json.JSONDecodeError:
            payload, status = api_json_error('Invalid JSON body', error_code='INVALID_JSON')
            return self._json_response(payload, status=status)
        except Exception as err:
            _logger.exception('Add survey owners failed for %s', survey_id)
            return self._json_response({'success': False, 'error': str(err)}, status=500)

    @http.route('/api/bhukhadan/survey/<int:survey_id>', type='http', auth='public', methods=['PATCH'], csrf=False)
    @check_permission
    def update_survey(self, survey_id, **kwargs):
        try:
            survey = request.env['bhu.survey'].sudo().browse(survey_id)
            if not survey.exists():
                payload, status = api_json_error('Survey not found', error_code='NOT_FOUND', status=404)
                return self._json_response(payload, status=status)

            user = self._current_user()
            if not api_user_can_access_survey(user, survey):
                raise AccessError('You do not have access to this survey')

            data = self._parse_json_body()
            is_state_only = set(data.keys()) == {'state'}
            if not is_state_only and survey.state not in ('draft', 'submitted'):
                payload, status = api_json_error(
                    f'Survey cannot be edited in state "{survey.state}". Only draft or submitted surveys can be edited.',
                )
                return self._json_response(payload, status=status)

            if 'state' in data and data['state'] not in ('draft', 'submitted', 'approved', 'rejected'):
                payload, status = api_json_error('Invalid state value')
                return self._json_response(payload, status=status)

            update_vals = api_build_survey_update_vals(request.env, survey, data)
            if not update_vals and 'photos' not in data:
                payload, status = api_json_error('No valid fields to update')
                return self._json_response(payload, status=status)

            if update_vals:
                survey.write(update_vals)

            if data.get('photos'):
                register_survey_photos(request.env, survey, data['photos'])
            request.env['bhu.survey.photo'].sudo().sync_from_s3_for_survey(survey)

            return self._json_response({
                'success': True,
                'message': 'Survey updated successfully',
                'data': api_serialize_survey(
                    survey,
                    include_image=bool(data.get('include_survey_image')),
                ),
            })
        except AccessError as err:
            return self._json_response({'success': False, 'error': str(err)}, status=403)
        except ValidationError as err:
            payload, status = api_json_error(str(err))
            return self._json_response(payload, status=status)
        except json.JSONDecodeError:
            payload, status = api_json_error('Invalid JSON body', error_code='INVALID_JSON')
            return self._json_response(payload, status=status)
        except Exception as err:
            _logger.exception('Survey update failed for %s', survey_id)
            return self._json_response({'success': False, 'error': str(err)}, status=500)
