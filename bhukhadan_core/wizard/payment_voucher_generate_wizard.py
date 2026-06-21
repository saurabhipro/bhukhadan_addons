# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PaymentVoucherGenerateWizard(models.TransientModel):
    _name = 'bhu.payment.voucher.generate.wizard'
    _description = 'Confirm bulk payment file generation'

    voucher_id = fields.Many2one(
        'bhu.payment.voucher',
        string='Payment Voucher',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(related='voucher_id.currency_id', readonly=True)
    khasra_count = fields.Integer(string='Khasra rows', readonly=True)
    beneficiary_count = fields.Integer(string='Beneficiary rows', readonly=True)
    total_amount = fields.Monetary(
        string='Total payment',
        currency_field='currency_id',
        readonly=True,
    )
    khasra_summary = fields.Char(string='Khasras', readonly=True)
    preview_html = fields.Html(string='Summary', sanitize=False, readonly=True)
    delivery_mode = fields.Selection(
        [
            ('excel', 'Download bank Excel only / केवल Excel डाउनलोड'),
            ('indusind', 'IndusInd Online Authorisation only / केवल IndusInd ऑनलाइन'),
            ('both', 'Excel + IndusInd Online Authorisation / Excel + IndusInd दोनों'),
        ],
        string='Proceed with',
        default='excel',
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        voucher = self.env['bhu.payment.voucher'].browse(
            self.env.context.get('default_voucher_id')
            or self.env.context.get('active_id')
        ).exists()
        if not voucher:
            return res
        preview = voucher._prepare_bulk_export_preview()
        res.update({
            'voucher_id': voucher.id,
            'khasra_count': preview['khasra_count'],
            'beneficiary_count': preview['beneficiary_count'],
            'total_amount': preview['total_amount'],
            'khasra_summary': preview['khasra_summary'],
            'preview_html': preview['preview_html'],
        })
        return res

    def action_confirm_generate(self):
        self.ensure_one()
        return self.voucher_id._execute_bulk_payment_file_generation(self.delivery_mode)
