# -*- coding: utf-8 -*-

import re

from odoo import models, fields, api, _


_UUID_RE = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE,
)


class BhuPaymentVoucherExportLine(models.Model):
    _name = 'bhu.payment.voucher.export.line'
    _description = 'Beneficiary row from R&R payment file export'
    _order = 'export_id desc, serial, id'

    export_id = fields.Many2one(
        'bhu.payment.voucher.export',
        string='Payment file export',
        required=True,
        ondelete='cascade',
        index=True,
    )
    voucher_id = fields.Many2one(
        related='export_id.voucher_id',
        store=True,
        readonly=True,
        index=True,
    )
    voucher_line_id = fields.Many2one(
        'bhu.payment.voucher.line',
        string='Khasra line',
        ondelete='set null',
        index=True,
    )
    serial = fields.Integer(string='Sr.', default=1)
    external_ref = fields.Char(string='External ref')
    transaction_uuid = fields.Char(
        string='Transaction UUID',
        index=True,
        copy=False,
        help='Pure 32-character hex UUID (no dashes). Readable voucher/khasra prefix is in External ref.',
    )
    khasra_number = fields.Char(string='Khasra / खसरा', index=True)
    beneficiary_name = fields.Char(string='Payee / लाभार्थी')
    bank_name = fields.Char(string='Bank / बैंक')
    account_number = fields.Char(string='Account / खाता')
    ifsc_code = fields.Char(string='IFSC')
    amount = fields.Monetary(string='Amount / राशि', currency_field='currency_id')
    currency_id = fields.Many2one(related='export_id.currency_id', readonly=True)
    payment_status = fields.Selection(
        [
            ('pending', 'Pending / लंबित'),
            ('settled', 'Success / सफल'),
            ('failed', 'Failed / असफल'),
        ],
        string='Payment status',
        default='pending',
        required=True,
        index=True,
    )
    utr_number = fields.Char(string='UTR')
    failure_reason = fields.Char(string='Failure reason')
    reconciled_date = fields.Datetime(string='Reconciled on')
    payment_file_line_id = fields.Many2one(
        'bhu.payment.file.line',
        string='Payment file line',
        ondelete='set null',
        copy=False,
        index=True,
    )

    def _apply_recon_status(self, recon_line):
        bank_status = (recon_line.status or '').lower()
        if bank_status in ('executed', 'settled', 'success', 'successful', 'paid', 'completed'):
            pay_status = 'settled'
        elif recon_line.error or bank_status in ('failed', 'failure', 'error', 'rejected'):
            pay_status = 'failed'
        else:
            pay_status = 'pending'
        self.write({
            'payment_status': pay_status,
            'utr_number': recon_line.utr_number or self.utr_number,
            'failure_reason': (
                (recon_line.error or recon_line.event_status or '')[:500]
                if pay_status == 'failed' else False
            ),
            'reconciled_date': fields.Datetime.now(),
        })
        return self

    def _normalize_account(self, account):
        return (account or '').strip().replace(' ', '')

    @api.model
    def _canonical_uuid_token(self, value):
        """Normalize any stored/bank ref to 32-char uppercase hex (no dashes)."""
        text = (value or '').strip()
        if not text:
            return ''
        match = _UUID_RE.search(text)
        if match:
            return match.group(0).replace('-', '').upper()
        hex_chunks = re.findall(r'[0-9a-fA-F]{32}', text)
        if hex_chunks:
            return hex_chunks[-1].upper()
        compact = re.sub(r'[^0-9a-fA-F]', '', text)
        if len(compact) >= 32:
            return compact[-32:].upper()
        return compact.upper()

    @api.model
    def _extract_uuid(self, value):
        return self._canonical_uuid_token(value)

    @api.model
    def _bank_ref_matches(self, stored_uuid, stored_external, bank_ref):
        """Match bank External Ref No against stored UUID and readable external ref."""
        bank_token = self._canonical_uuid_token(bank_ref)
        if not bank_token:
            return False
        uuid_token = self._canonical_uuid_token(stored_uuid)
        if uuid_token and bank_token == uuid_token:
            return True
        external_ref = (stored_external or '').strip()
        if external_ref and bank_ref == external_ref:
            return True
        if uuid_token and uuid_token in self._canonical_uuid_token(bank_ref):
            return True
        return bool(
            uuid_token
            and bank_token.endswith(uuid_token)
            and len(uuid_token) == 32
        )

    @api.model
    def _normalize_legacy_transaction_uuids(self):
        """Strip voucher/khasra prefixes and dashes from legacy transaction UUID values."""
        for model_name in ('bhu.payment.voucher.export.line', 'bhu.payment.file.line'):
            for rec in self.env[model_name].search([]):
                raw = (rec.transaction_uuid or '').strip()
                if not raw:
                    continue
                canonical = self._canonical_uuid_token(raw)
                if not canonical or len(canonical) != 32:
                    continue
                if canonical == raw.replace('-', '').upper():
                    if '-' in raw:
                        rec.transaction_uuid = canonical
                    continue
                rec.transaction_uuid = canonical
                if model_name == 'bhu.payment.voucher.export.line':
                    if not rec.external_ref:
                        rec.external_ref = raw[:120]
                else:
                    export_line = rec.voucher_export_line_id
                    if export_line and not export_line.external_ref:
                        export_line.external_ref = raw[:120]

    @api.model
    def sync_from_reconciliation_line(self, recon_line, project_id, village_id):
        """Match bank reconciliation row to a pending export beneficiary line."""
        if not recon_line or not project_id or not village_id:
            return self.browse()

        tx_ref = (recon_line.transaction_reference or recon_line.payment_id or '').strip()
        if tx_ref:
            candidates = self.search([
                ('voucher_id.project_id', '=', project_id),
                ('voucher_id.village_id', '=', village_id),
            ])
            by_uuid = candidates.filtered(
                lambda l: self._bank_ref_matches(l.transaction_uuid, l.external_ref, tx_ref)
            )[:1]
            if by_uuid:
                by_uuid._apply_recon_status(recon_line)
                return by_uuid

        account = self._normalize_account(recon_line.beneficiary_account)
        amount = round(float(recon_line.credit_amount or 0.0), 2)
        if not account or amount <= 0:
            return self.browse()

        candidates = self.search([
            ('voucher_id.project_id', '=', project_id),
            ('voucher_id.village_id', '=', village_id),
            ('payment_status', 'in', ('pending', 'failed')),
        ])
        matched = candidates.filtered(
            lambda l: l._normalize_account(l.account_number) == account
            and abs(float(l.amount or 0.0) - amount) < 0.01
        )
        if len(matched) > 1:
            matched = matched.filtered(lambda l: l.payment_status == 'pending') or matched
        matched = matched[:1]
        if not matched:
            return self.browse()

        matched._apply_recon_status(recon_line)
        return matched
