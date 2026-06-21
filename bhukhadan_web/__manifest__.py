{
    'name': 'BhuKhadan Web',
    'version': '18.0.1.2.8',
    'summary': 'Public website for BhuKhadan — Coal Bearing & Land Acquisition Management System.',
    'description': 'Public-facing website for the BhuKhadan LAMS platform, '
                   'covering CBA(A&D) Act 1957 coal-bearing land acquisition workflows.',
    'category': 'Website',
    'website': 'bhuarjan.com',
    'depends': ['website', 'bhukhadan_core'],
    'data': [
        'views/website_menu.xml',
        'views/website_templates.xml',
        'views/cba_templates.xml',
        'views/cba_guide_menus.xml',
        'views/acts_templates.xml',
        'views/login_templates.xml',
        'views/legal_pages.xml',
        'views/mobile_app_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bhukhadan_web/static/src/css/bhuarjan_website.css',
            'bhukhadan_web/static/src/js/bhuarjan_website.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
