# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.auth_oauth.controllers.main import OAuthLogin


class BhuWebLoginFix(OAuthLogin):
    """Ensure /web/login stays in website context when auth_oauth is installed."""

    @http.route(website=True, auth="public", sitemap=False)
    def web_login(self, *args, **kw):
        return super().web_login(*args, **kw)
