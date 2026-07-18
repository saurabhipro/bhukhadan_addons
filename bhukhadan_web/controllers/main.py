from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.auth_oauth.controllers.main import OAuthLogin
from odoo.addons.website.controllers.main import WebsiteSession
import base64


class BhuKhadanLogin(OAuthLogin):
    """auth_oauth registers /web/login without website=True, which breaks website.layout."""

    @http.route(website=True, auth='public', sitemap=False)
    def web_login(self, *args, **kw):
        return super().web_login(*args, **kw)


class BhuKhadanWebsite(http.Controller):

    @http.route('/', type='http', auth='public', website=True, sitemap=True)
    def homepage(self, **kwargs):
        return request.render('bhukhadan_web.homepage')

    @http.route('/contact', type='http', auth='public', website=True, sitemap=True)
    def contact(self, **kwargs):
        return request.render('bhukhadan_web.contact_page')

    @http.route('/features', type='http', auth='public', website=True, sitemap=True)
    def features(self, **kwargs):
        return request.render('bhukhadan_web.features_page')

    @http.route('/acts', type='http', auth='public', website=True, sitemap=True)
    def acts(self, **kwargs):
        return request.render('bhukhadan_web.acts_page')

    @http.route('/mobile-app', type='http', auth='public', website=True, sitemap=True)
    def mobile_app(self, **kwargs):
        return request.render('bhukhadan_web.mobile_app_page')

    @http.route('/bhuarjan/mobile-app/download', type='http', auth='public', website=True)
    def mobile_app_download(self, **kwargs):
        Settings = request.env['bhuarjan.settings.master'].sudo()
        info = Settings.get_mobile_app_public_info()
        if not info.get('available'):
            return request.not_found()
        settings = Settings.search([('active', '=', True)], limit=1)
        if not settings:
            settings = Settings.search([], limit=1)
        data = base64.b64decode(settings.mobile_apk_file)
        filename = settings.mobile_apk_filename or 'bhukhadan.apk'
        if not filename.lower().endswith('.apk'):
            filename = '%s.apk' % filename.rsplit('.', 1)[0]
        return request.make_response(
            data,
            headers=[
                ('Content-Type', 'application/vnd.android.package-archive'),
                ('Content-Disposition', content_disposition(filename)),
                ('Content-Length', len(data)),
            ],
        )

    @http.route('/cookie-policy', type='http', auth='public', website=True, sitemap=True)
    def cookie_policy(self, **kwargs):
        return request.render('bhukhadan_web.cookie_policy_page')

    @http.route('/terms-and-conditions', type='http', auth='public', website=True, sitemap=True)
    def terms_and_conditions(self, **kwargs):
        return request.render('bhukhadan_web.terms_and_conditions_page')

    @http.route('/privacy-policy', type='http', auth='public', website=True, sitemap=True)
    def privacy_policy(self, **kwargs):
        return request.render('bhukhadan_web.privacy_policy_page')

    _CBA_GUIDE_PAGES = {
        '/features/cba': 'bhukhadan_web.cba_overview_page',
        '/features/cba/section-4': 'bhukhadan_web.cba_section4_page',
        '/features/cba/section-7': 'bhukhadan_web.cba_section7_page',
        '/features/cba/section-8': 'bhukhadan_web.cba_section8_page',
        '/features/cba/section-9': 'bhukhadan_web.cba_section9_page',
        '/features/cba/section-11': 'bhukhadan_web.cba_section11_page',
    }

    @http.route([
        '/features/cba',
        '/features/cba/section-4',
        '/features/cba/section-7',
        '/features/cba/section-8',
        '/features/cba/section-9',
        '/features/cba/section-11',
    ], type='http', auth='public', website=True, sitemap=True)
    def cba_guide(self, **kwargs):
        path = request.httprequest.path.rstrip('/') or '/'
        template = self._CBA_GUIDE_PAGES.get(path)
        if not template:
            return request.redirect('/features/cba')
        return request.render(template)

    @http.route('/contact/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def contact_submit(self, **post):
        name = post.get('name', '')
        email = post.get('email', '')
        phone = post.get('phone', '')
        message = post.get('message', '')
        if name and email:
            request.env['mail.message'].sudo().create({
                'body': f'<p><b>From:</b> {name} ({email})<br/>'
                        f'<b>Phone:</b> {phone}<br/>'
                        f'<b>Message:</b> {message}</p>',
                'message_type': 'comment',
                'subject': f'Website Contact: {name}',
                'subtype_id': request.env.ref('mail.mt_comment').id,
            })
        return request.render('bhukhadan_web.contact_thanks')

    @http.route('/logout', type='http', auth='public', website=True, sitemap=False)
    def logout(self, **kwargs):
        """Convenient public logout that always returns to the homepage."""
        request.session.logout(keep_db=True)
        return request.redirect('/')


class BhuKhadanSession(WebsiteSession):
    """Override Odoo's default logout so users land on our homepage instead of /odoo."""

    @http.route('/web/session/logout', type='http', auth='public', website=True, multilang=False, sitemap=False)
    def logout(self, redirect='/'):
        return super().logout(redirect=redirect)
