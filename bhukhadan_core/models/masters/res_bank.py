# -*- coding: utf-8 -*-

from odoo import fields, models


class ResBank(models.Model):
    _inherit = 'res.bank'

    bhu_category = fields.Selection(
        selection=[
            ('private_sector', 'Private sector bank'),
            ('local_area_bank', 'Local area bank (LAB)'),
            ('small_finance_bank', 'Small finance bank (SFB)'),
            ('payments_bank', 'Payments bank (PB)'),
            ('public_sector', 'Public sector bank'),
            ('financial_institution', 'Financial institution'),
            ('regional_rural_bank', 'Regional rural bank (RRB)'),
        ],
        string='Indian bank category',
        index=True,
        help='Set for banks in the Indian master list (RBI-style groupings).',
    )
