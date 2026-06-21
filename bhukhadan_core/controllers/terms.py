# -*- coding: utf-8 -*-

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request


class BhuKhadanTermsController(http.Controller):

    @http.route('/bhuarjan/terms/status', type='json', auth='user')
    def terms_status(self):
        """Return whether the logged-in user has accepted BhuKhadan terms."""
        user = request.env.user
        if not user or user._is_public():
            raise AccessError('Authentication required.')
        accepted = getattr(user, 'bhu_terms_accepted', None)
        if accepted is None:
            request.env.cr.execute(
                "SELECT bhu_terms_accepted FROM res_users WHERE id = %s",
                (user.id,),
            )
            row = request.env.cr.fetchone()
            accepted = bool(row and row[0])
        return {'accepted': bool(accepted)}

    @http.route('/bhuarjan/terms/accept', type='json', auth='user')
    def accept_terms(self):
        """Record that the logged-in user has accepted BhuKhadan terms."""
        user = request.env.user
        if not user or user._is_public():
            raise AccessError('Authentication required.')
        user.sudo().write({
            'bhu_terms_accepted': True,
            'bhu_terms_accepted_date': fields.Datetime.now(),
        })
        return {'ok': True}
