# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.service import security


class BhuLoginAsController(http.Controller):
    """Allow leadership users to impersonate SDMs and Collectors for support / UAT."""

    def _can_impersonate(self, env):
        user = env.user
        return (
            user.has_group('base.group_system')
            or user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        )

    def _real_user(self):
        """User who started impersonation (for nested checks)."""
        impersonator_uid = request.session.get('impersonator_uid')
        if impersonator_uid:
            return request.env['res.users'].sudo().browse(impersonator_uid)
        return request.env.user

    def _validate_target_sdm(self, target):
        target = target.exists()
        if not target or not target.active:
            raise AccessError('Cannot login as an inactive user.')
        if not target._is_internal():
            raise AccessError('Cannot login as an external/portal user.')
        if not target.has_group('bhukhadan_core.group_bhuarjan_sdm'):
            raise AccessError('Selected user is not an SDM.')
        if target.has_group('base.group_system'):
            raise AccessError('Cannot login as a system administrator.')
        if target.has_group('bhukhadan_core.group_bhuarjan_admin'):
            raise AccessError('Cannot login as an application administrator.')
        SubDiv = request.env['bhu.sub.division'].sudo()
        if not SubDiv.search_count([('user_id', '=', target.id)]):
            raise AccessError('This user is not linked as SDM on any sub division.')

    def _validate_target_collector(self, target):
        target = target.exists()
        if not target or not target.active:
            raise AccessError('Cannot login as an inactive user.')
        if not target._is_internal():
            raise AccessError('Cannot login as an external/portal user.')
        is_collector = (
            target.has_group('bhukhadan_core.group_bhuarjan_collector')
            or target.has_group('bhukhadan_core.group_bhuarjan_additional_collector')
        )
        if not is_collector:
            raise AccessError('Selected user is not a Collector.')
        if target.has_group('base.group_system'):
            raise AccessError('Cannot login as a system administrator.')
        if target.has_group('bhukhadan_core.group_bhuarjan_admin'):
            raise AccessError('Cannot login as an application administrator.')
        if target.has_group('bhukhadan_core.group_bhuarjan_district_administrator'):
            raise AccessError('Cannot login as a district administrator.')
        if getattr(target, 'bhuarjan_role', None) in ('administrator', 'district_administrator'):
            raise AccessError('Cannot login as an administrator.')
        if not target.district_id:
            raise AccessError('This Collector is not linked to any district.')

    def _resolve_impersonation_kind(self, target):
        """Return 'collector' or 'sdm' — bhuarjan_role wins over overlapping groups."""
        target = target.exists()
        role = getattr(target, 'bhuarjan_role', None)
        if role in ('collector', 'additional_collector'):
            return 'collector'
        if role == 'sdm':
            return 'sdm'
        has_collector = (
            target.has_group('bhukhadan_core.group_bhuarjan_collector')
            or target.has_group('bhukhadan_core.group_bhuarjan_additional_collector')
        )
        has_sdm = target.has_group('bhukhadan_core.group_bhuarjan_sdm')
        if has_collector and not has_sdm:
            return 'collector'
        if has_sdm and not has_collector:
            return 'sdm'
        if has_collector and has_sdm:
            SubDiv = request.env['bhu.sub.division'].sudo()
            if SubDiv.search_count([('user_id', '=', target.id)]):
                return 'sdm'
            if target.district_id:
                return 'collector'
        return None

    def _validate_impersonation_target(self, target):
        """Pick SDM vs Collector validation based on role, not group order alone."""
        target = target.exists()
        kind = self._resolve_impersonation_kind(target)
        if kind == 'collector':
            self._validate_target_collector(target)
            return
        if kind == 'sdm':
            self._validate_target_sdm(target)
            return
        raise AccessError('Selected user cannot be impersonated.')

    def _apply_session_user(self, user):
        user = user.exists()
        if not user or not user.active:
            raise AccessError('Invalid user.')

        request.session.uid = user.id
        request.session.login = user.login
        request.session.context = dict(user.context_get())

        request.env.registry.clear_cache()
        env = request.env(user=user.id)
        request.session.session_token = security.compute_session_token(
            request.session, env
        )
        request.update_env(user=user.id)
        request.session.touch()
        request.session.is_dirty = True

    @http.route('/bhuarjan/login_as/<int:user_id>', type='http', auth='user')
    def login_as(self, user_id, redirect='/web', **kw):
        real = self._real_user()
        target = request.env['res.users'].browse(user_id)
        is_collector_target = self._resolve_impersonation_kind(target) == 'collector'
        if is_collector_target:
            if not (
                real.has_group('base.group_system')
                or real.has_group('bhukhadan_core.group_bhuarjan_admin')
            ):
                raise AccessError('Only Administrator can login as Collector.')
        elif not self._can_impersonate(real.env):
            raise AccessError('You are not allowed to login as another user.')

        self._validate_impersonation_target(target)

        if not request.session.get('impersonator_uid'):
            request.session['impersonator_uid'] = request.session.uid
            request.session['impersonator_login'] = request.session.login

        self._apply_session_user(target)
        return request.redirect(redirect or '/web')

    @http.route('/bhuarjan/login_as/back', type='http', auth='user')
    def login_as_back(self, redirect='/web', **kw):
        impersonator_uid = request.session.pop('impersonator_uid', None)
        request.session.pop('impersonator_login', None)
        if not impersonator_uid:
            raise AccessError('You are not impersonating another user.')

        original = request.env['res.users'].browse(impersonator_uid)
        self._apply_session_user(original)
        return request.redirect(redirect or '/web')
