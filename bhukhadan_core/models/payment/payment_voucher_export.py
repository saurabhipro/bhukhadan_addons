# -*- coding: utf-8 -*-

import base64
import uuid

from odoo import models, fields, api, _


class BhuPaymentVoucherExport(models.Model):
    _name = 'bhu.payment.voucher.export'
    _description = 'Bank payment file export from R&R voucher'
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference / संदर्भ',
        required=True,
        default='New',
        copy=False,
    )
    voucher_id = fields.Many2one(
        'bhu.payment.voucher',
        string='Payment Voucher',
        required=True,
        ondelete='cascade',
        index=True,
    )
    voucher_line_id = fields.Many2one(
        'bhu.payment.voucher.line',
        string='Voucher Line',
        ondelete='cascade',
        index=True,
    )
    voucher_line_ids = fields.Many2many(
        'bhu.payment.voucher.line',
        'bhu_payment_voucher_export_line_rel',
        'export_id',
        'line_id',
        string='Voucher lines',
    )
    project_id = fields.Many2one(related='voucher_id.project_id', store=True, readonly=True)
    village_id = fields.Many2one(related='voucher_id.village_id', store=True, readonly=True)
    award_id = fields.Many2one(related='voucher_id.award_id', store=True, readonly=True)
    khasra_count = fields.Integer(
        string='Khasra rows / खसरा पंक्तियाँ',
        compute='_compute_export_display',
        store=True,
    )
    khasra_summary = fields.Char(
        string='Khasras in file / फ़ाइल में खसरे',
        compute='_compute_export_display',
        store=True,
    )
    khasra_number = fields.Char(
        string='Khasra / खसरा',
        compute='_compute_export_display',
        store=True,
        help='Legacy display field — use khasra_summary on views.',
    )
    owner_display = fields.Char(
        string='Payee / भूस्वामी',
        compute='_compute_export_display',
        store=True,
    )
    currency_id = fields.Many2one(related='voucher_id.currency_id', readonly=True)
    amount = fields.Monetary(string='Amount / राशि', currency_field='currency_id')
    debit_account_number = fields.Char(string='Debit account / डेबिट खाता')
    state = fields.Selection(
        [
            ('generated', 'Payment file generated / भुगतान फ़ाइल तैयार'),
        ],
        string='Status / स्थिति',
        default='generated',
        required=True,
    )
    generated_file = fields.Binary(string='Bank Excel / बैंक Excel', attachment=True)
    generated_file_filename = fields.Char(string='Filename')
    generation_date = fields.Datetime(string='Generated on / दिनांक', default=fields.Datetime.now)
    indusind_authorisation_ref = fields.Char(string='IndusInd auth ref', readonly=True, copy=False)
    indusind_authorisation_status = fields.Selection(
        [
            ('submitted', 'Submitted to IndusInd'),
            ('failed', 'IndusInd failed'),
        ],
        string='IndusInd status',
        readonly=True,
        copy=False,
    )
    indusind_authorisation_message = fields.Char(string='IndusInd message', readonly=True, copy=False)
    indusind_authorisation_date = fields.Datetime(string='IndusInd submitted on', readonly=True, copy=False)
    export_line_ids = fields.One2many(
        'bhu.payment.voucher.export.line',
        'export_id',
        string='Beneficiary lines',
        readonly=True,
    )
    pending_line_count = fields.Integer(compute='_compute_line_stats', string='Pending lines')
    success_line_count = fields.Integer(compute='_compute_line_stats', string='Success lines')
    failed_line_count = fields.Integer(compute='_compute_line_stats', string='Failed lines')

    @api.depends('export_line_ids', 'export_line_ids.payment_status')
    def _compute_line_stats(self):
        for rec in self:
            lines = rec.export_line_ids
            rec.pending_line_count = len(lines.filtered(lambda l: l.payment_status == 'pending'))
            rec.success_line_count = len(lines.filtered(lambda l: l.payment_status == 'settled'))
            rec.failed_line_count = len(lines.filtered(lambda l: l.payment_status == 'failed'))

    def create_beneficiary_lines(self, payment_rows):
        """One pending row per Excel beneficiary line."""
        self.ensure_one()
        ExportLine = self.env['bhu.payment.voucher.export.line']
        serial = max(self.export_line_ids.mapped('serial') or [0]) + 1
        for prow in payment_rows or []:
            tx_uuid = (
                (prow.get('transaction_uuid') or uuid.uuid4().hex.upper())
                .strip()
                .replace('-', '')
                .upper()
            )
            external_ref = (prow.get('external_ref') or tx_uuid)[:120]
            ExportLine.create({
                'export_id': self.id,
                'serial': serial,
                'external_ref': external_ref,
                'transaction_uuid': tx_uuid,
                'khasra_number': (prow.get('khasra_number') or '')[:64],
                'voucher_line_id': prow.get('voucher_line_id') or False,
                'beneficiary_name': (prow.get('beneficiary_name') or '')[:240],
                'bank_name': (prow.get('bank_name') or '')[:120],
                'account_number': (prow.get('account_number') or '').replace(' ', '')[:64],
                'ifsc_code': (prow.get('ifsc_code') or '')[:16],
                'amount': round(float(prow.get('amount') or 0.0), 2),
                'payment_status': 'pending',
            })
            serial += 1
        self.sync_to_payment_file_lines(payment_rows)

    def _ensure_payment_file(self):
        """Get or create village payment file header for reconciliation tracking."""
        self.ensure_one()
        voucher = self.voucher_id
        PaymentFile = self.env['bhu.payment.file']
        payment_file = voucher.payment_file_id
        if not payment_file:
            payment_file = PaymentFile.search([
                ('project_id', '=', voucher.project_id.id),
                ('village_id', '=', voucher.village_id.id),
            ], limit=1)
        if not payment_file:
            payment_file = PaymentFile.with_context(
                skip_payment_line_populate=True,
                bhu_allow_payment_file_create=True,
            ).create({
                'name': 'New',
                'project_id': voucher.project_id.id,
                'village_id': voucher.village_id.id,
                'award_id': voucher.award_id.id,
                'debit_account_number': (
                    voucher.debit_account_number or self.debit_account_number or ''
                ),
            })
        elif payment_file.award_id != voucher.award_id:
            payment_file.award_id = voucher.award_id.id
        debit = voucher.debit_account_number or self.debit_account_number or ''
        if debit and payment_file.debit_account_number != debit:
            payment_file.debit_account_number = debit
        if voucher.payment_file_id != payment_file:
            voucher.payment_file_id = payment_file.id
        return payment_file

    def sync_to_payment_file_lines(self, payment_rows):
        """Create ``bhu.payment.file.line`` rows for Payment Lines menu + reconciliation."""
        self.ensure_one()
        if not payment_rows:
            return self.env['bhu.payment.file.line']

        payment_file = self._ensure_payment_file()
        PaymentLine = self.env['bhu.payment.file.line']
        VoucherLine = self.env['bhu.payment.voucher.line']
        export_lines = self.export_line_ids
        next_serial = max(payment_file.payment_line_ids.mapped('serial_number') or [0]) + 1
        created = PaymentLine.browse()

        for prow in payment_rows:
            tx_uuid = (
                (prow.get('transaction_uuid') or uuid.uuid4().hex.upper())
                .strip()
                .replace('-', '')
                .upper()
            )
            if PaymentLine.search_count([('transaction_uuid', '=', tx_uuid)]):
                continue

            vline = VoucherLine.browse(prow.get('voucher_line_id')) if prow.get('voucher_line_id') else VoucherLine.browse()
            export_line = export_lines.filtered(
                lambda l: l.transaction_uuid == tx_uuid
            )[:1]
            lo_id = prow.get('landowner_id') or (vline.landowner_id.id if vline and vline.landowner_id else False)
            bene = (prow.get('beneficiary_name') or '')[:240]
            owner_text = (vline.owner_display or '')[:240] if vline else ''
            pf_line = PaymentLine.create({
                'payment_file_id': payment_file.id,
                'serial_number': next_serial,
                'award_serial_number': vline.rr_serial if vline else next_serial,
                'khasra_number': (prow.get('khasra_number') or '')[:64],
                'landowner_id': lo_id or False,
                'beneficiary_override': bene if bene and bene != owner_text else False,
                'bank_name': (prow.get('bank_name') or '').strip() or '-',
                'account_number': (prow.get('account_number') or '').replace(' ', ''),
                'ifsc_code': (prow.get('ifsc_code') or '').upper(),
                'compensation_amount': round(float(prow.get('amount') or 0.0), 2),
                'transaction_uuid': tx_uuid,
                'voucher_export_id': self.id,
                'voucher_export_line_id': export_line.id if export_line else False,
                'remark': _(
                    'Export %(export)s · Voucher %(voucher)s · Khasra %(khasra)s'
                ) % {
                    'export': self.name,
                    'voucher': self.voucher_id.name,
                    'khasra': prow.get('khasra_number') or '-',
                },
            })
            if export_line:
                export_line.payment_file_line_id = pf_line.id
            created |= pf_line
            next_serial += 1
        return created

    @api.model
    def _backfill_payment_file_lines_from_exports(self):
        """Create payment file lines for exports created before sync was added."""
        ExportLine = self.env['bhu.payment.voucher.export.line']
        missing = ExportLine.search([('payment_file_line_id', '=', False)])
        for export in missing.mapped('export_id'):
            rows = []
            for line in export.export_line_ids.sorted('serial'):
                rows.append({
                    'transaction_uuid': line.transaction_uuid or line.external_ref or str(uuid.uuid4()),
                    'external_ref': line.transaction_uuid or line.external_ref,
                    'amount': line.amount,
                    'beneficiary_name': line.beneficiary_name,
                    'bank_name': line.bank_name,
                    'account_number': line.account_number,
                    'ifsc_code': line.ifsc_code,
                    'khasra_number': line.khasra_number,
                    'voucher_line_id': line.voucher_line_id.id if line.voucher_line_id else False,
                    'landowner_id': (
                        line.voucher_line_id.landowner_id.id
                        if line.voucher_line_id and line.voucher_line_id.landowner_id
                        else False
                    ),
                })
            if rows:
                export.sync_to_payment_file_lines(rows)

    @api.depends('voucher_line_ids', 'voucher_line_ids.khasra_number', 'voucher_line_ids.owner_display',
                 'voucher_line_id', 'voucher_line_id.khasra_number', 'voucher_line_id.owner_display')
    def _compute_export_display(self):
        for rec in self:
            lines = rec.voucher_line_ids
            if not lines and rec.voucher_line_id:
                lines = rec.voucher_line_id
            if lines:
                khasras = []
                seen = set()
                for k in lines.mapped('khasra_number'):
                    k = (k or '').strip()
                    if k and k not in seen:
                        seen.add(k)
                        khasras.append(k)
                rec.khasra_count = len(lines)
                rec.khasra_number = ', '.join(khasras)
                if len(khasras) == 1:
                    rec.khasra_summary = khasras[0]
                elif len(khasras) <= 6:
                    rec.khasra_summary = ', '.join(khasras)
                else:
                    rec.khasra_summary = _('%s khasras: %s, …') % (
                        len(khasras), ', '.join(khasras[:5])
                    )
                if len(lines) == 1:
                    rec.owner_display = lines[0].owner_display or ''
                else:
                    rec.owner_display = _('%s payee rows in this file') % len(lines)
            else:
                rec.khasra_count = 0
                rec.khasra_number = ''
                rec.khasra_summary = ''
                rec.owner_display = ''

    @api.model
    def _next_export_ref(self):
        """Return a unique payment file reference."""
        for _attempt in range(20):
            ref = self.env['ir.sequence'].next_by_code('bhu.payment.voucher.export')
            if not ref:
                ref = 'PVEXP-%s' % fields.Datetime.now().strftime('%Y%m%d%H%M%S%f')
            if not self.search_count([('name', '=', ref)]):
                return ref
        raise UserError(_('Could not allocate a unique payment file reference. Please try again.'))

    @api.model
    def _renumber_duplicate_exports(self):
        """Assign fresh refs when legacy data reused the same export name."""
        grouped = {}
        for export in self.with_context(active_test=False).search([], order='id'):
            grouped.setdefault(export.name or '', []).append(export)
        for _name, exports in grouped.items():
            if len(exports) <= 1:
                continue
            for export in exports[1:]:
                export.name = self._next_export_ref()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') in ('New', '', False):
                vals['name'] = self._next_export_ref()
            if vals.get('voucher_line_id') and not vals.get('voucher_line_ids'):
                vals['voucher_line_ids'] = [(4, vals['voucher_line_id'])]
        return super().create(vals_list)

    def action_download(self):
        self.ensure_one()
        if not self.generated_file:
            raise UserError(_('No bank file is attached to this export.'))
        return {
            'type': 'ir.actions.act_url',
            'url': (
                '/web/content/?model=bhu.payment.voucher.export'
                f'&id={self.id}'
                '&field=generated_file'
                '&filename_field=generated_file_filename'
                '&download=true'
            ),
            'target': 'self',
        }
