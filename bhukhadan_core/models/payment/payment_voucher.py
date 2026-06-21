# -*- coding: utf-8 -*-

import base64
import html as html_lib
import json
import re
import uuid

from markupsafe import Markup, escape

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
def bhu_match_res_bank(env, bank_name):
    """Map free-text bank name to a unique Indian master ``res.bank`` (must have ``bhu_category``)."""
    name = (bank_name or '').strip()
    if not name:
        return False
    Bank = env['res.bank']
    base_dom = [('bhu_category', '!=', False)]
    rec = Bank.search(base_dom + [('name', '=ilike', name)], limit=2)
    if len(rec) == 1:
        return rec.id
    rec = Bank.search(base_dom + [('name', 'ilike', name)], limit=2)
    if len(rec) == 1:
        return rec.id
    return False


IFSC_CODE_REGEX = re.compile(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$')


def bhu_validate_ifsc_code(ifsc_code, context_label=None):
    """Validate Indian IFSC format (4 letters + 0 + 6 alphanumeric)."""
    ifsc = (ifsc_code or '').strip().upper()
    if not ifsc:
        label = context_label or _('IFSC')
        raise ValidationError(_('Please enter %s code.') % label)
    if not IFSC_CODE_REGEX.match(ifsc):
        raise ValidationError(_(
            'Invalid IFSC "%(ifsc)s"%(ctx)s. '
            'Use format: 4 letters + 0 + 6 alphanumeric characters (e.g. SBIN0001234).'
        ) % {
            'ifsc': ifsc_code or '',
            'ctx': (' (%s)' % context_label) if context_label else '',
        })
    return ifsc


def bhu_validate_account_number(account_number, context_label=None):
    """Validate bank account number (digits only, 9–18 chars)."""
    acct = (account_number or '').strip().replace(' ', '')
    if not acct:
        label = context_label or _('account number')
        raise ValidationError(_('Please enter %s.') % label)
    if not acct.isdigit() or len(acct) < 9 or len(acct) > 18:
        raise ValidationError(_(
            'Invalid account number "%(acct)s"%(ctx)s. '
            'Use 9–18 digits only.'
        ) % {
            'acct': account_number or '',
            'ctx': (' (%s)' % context_label) if context_label else '',
        })
    return acct


class BhuPaymentVoucher(models.Model):
    _name = 'bhu.payment.voucher'
    _description = 'Draft R&R Payment Voucher / आरएंडआर भुगतान वाउचर (प्रारूप)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    _sql_constraints = [
        (
            'award_id_unique',
            'unique(award_id)',
            'Only one payment voucher is allowed per Section 23 award.',
        ),
    ]

    name = fields.Char(
        string='Reference / संदर्भ',
        required=True,
        default='New',
        tracking=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ('setup', 'Setup / बैंक जोड़ें'),
            ('ready', 'Ready / तैयार'),
            ('in_payment', 'In Payment / भुगतान में'),
            ('done', 'Completed / पूर्ण'),
        ],
        string='Status / स्थिति',
        compute='_compute_workflow_state',
        store=True,
        tracking=True,
    )
    award_id = fields.Many2one(
        'bhu.section23.award',
        string='Section 23 Award / धारा 23 अवार्ड',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        related='award_id.project_id',
        store=True,
        readonly=True,
    )
    village_id = fields.Many2one(
        related='award_id.village_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='award_id.project_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.ref('base.INR').id,
    )
    line_ids = fields.One2many(
        'bhu.payment.voucher.line',
        'voucher_id',
        string='Lines / पंक्तियाँ',
        copy=True,
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_line_count',
        store=False,
    )
    total_determined = fields.Monetary(
        string='Total Determined Compensation / निर्धारित कुल मुआवजा',
        compute='_compute_totals',
        currency_field='currency_id',
        store=False,
    )
    payment_file_id = fields.Many2one(
        'bhu.payment.file',
        string='Payment File / भुगतान फ़ाइल',
        readonly=True,
        copy=False,
        help='Legacy village-level payment file (optional). Per-khasra exports are tracked below.',
    )
    debit_account_number = fields.Char(
        string='Debit account / डेबिट खाता',
        help='Debit account number used in bank bulk upload Excel for this voucher.',
    )
    export_ids = fields.One2many(
        'bhu.payment.voucher.export',
        'voucher_id',
        string='Generated payment files / भुगतान फ़ाइलें',
        readonly=True,
    )
    export_count = fields.Integer(compute='_compute_export_stats', string='Files generated')
    pending_account_count = fields.Integer(compute='_compute_export_stats', string='Pending account')
    account_ready_count = fields.Integer(
        compute='_compute_export_stats',
        string='Ready to generate',
    )
    lines_file_generated_count = fields.Integer(
        compute='_compute_lines_file_generated_count',
        string='Lines with payment file',
    )
    payment_files_status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('completed', 'Completed'),
        ],
        string='Status / स्थिति',
        compute='_compute_payment_files_status',
        store=True,
        readonly=True,
        tracking=True,
    )
    lines_preview_html = fields.Html(
        string='Lines preview',
        compute='_compute_lines_preview_html',
        sanitize=False,
    )
    export_beneficiary_ids = fields.One2many(
        'bhu.payment.voucher.export.line',
        'voucher_id',
        string='Export beneficiary lines',
        readonly=True,
    )
    pending_payments_html = fields.Html(
        compute='_compute_payment_tracking_html',
        sanitize=False,
    )
    success_payments_html = fields.Html(
        compute='_compute_payment_tracking_html',
        sanitize=False,
    )
    failed_payments_html = fields.Html(
        compute='_compute_payment_tracking_html',
        sanitize=False,
    )
    pending_payment_count = fields.Integer(compute='_compute_payment_tracking_html')
    success_payment_count = fields.Integer(compute='_compute_payment_tracking_html')
    failed_payment_count = fields.Integer(compute='_compute_payment_tracking_html')
    notes = fields.Text(string='Notes / टिप्पणी')

    @api.depends('line_ids', 'line_ids.determined_total', 'line_ids.payout_mode',
                 'line_ids.split_ids', 'line_ids.split_ids.amount', 'line_ids.split_ids.percent_share')
    def _compute_totals(self):
        for rec in self:
            total = 0.0
            for line in rec.line_ids:
                if line.payout_mode == 'split' and line.split_ids:
                    total += sum(float(x.amount or 0.0) for x in line.split_ids)
                else:
                    total += float(line.determined_total or 0.0)
            rec.total_determined = total

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends(
        'line_ids',
        'line_ids.line_status',
        'pending_account_count',
        'export_count',
        'pending_payment_count',
        'success_payment_count',
        'failed_payment_count',
    )
    def _compute_workflow_state(self):
        """Auto status from bank setup → file generation → reconciliation."""
        for rec in self:
            if not rec.line_ids or rec.pending_account_count > 0:
                rec.state = 'setup'
            elif not rec.export_count:
                rec.state = 'ready'
            elif (
                rec.pending_payment_count == 0
                and rec.failed_payment_count == 0
                and rec.success_payment_count > 0
            ):
                rec.state = 'done'
            else:
                rec.state = 'in_payment'

    @api.model
    def _recompute_workflow_states(self):
        """Module upgrade: refresh stored workflow state for all vouchers."""
        self.search([])._compute_workflow_state()

    @api.model
    def _recompute_payment_files_status_all(self):
        """Module upgrade: refresh Pending / Completed on all vouchers."""
        self.search([])._compute_payment_files_status()

    @api.depends('line_ids', 'line_ids.line_status', 'export_ids')
    def _compute_export_stats(self):
        for rec in self:
            rec.export_count = len(rec.export_ids)
            rec.pending_account_count = len(
                rec.line_ids.filtered(lambda l: l.line_status == 'pending_account')
            )
            rec.account_ready_count = len(
                rec.line_ids.filtered(
                    lambda l: l.line_status == 'account_added' and not l.is_line_locked
                )
            )

    @api.depends('line_ids', 'line_ids.line_status')
    def _compute_lines_file_generated_count(self):
        for rec in self:
            rec.lines_file_generated_count = len(
                rec.line_ids.filtered(lambda l: l.line_status == 'file_generated')
            )

    @api.depends('line_ids', 'line_ids.line_status')
    def _compute_payment_files_status(self):
        """Completed only when every khasra line has a generated payment file."""
        for rec in self:
            lines = rec.line_ids
            generated = lines.filtered(lambda l: l.line_status == 'file_generated')
            if lines and len(generated) == len(lines):
                rec.payment_files_status = 'completed'
            else:
                rec.payment_files_status = 'pending'

    @api.depends(
        'line_ids', 'line_ids.rr_serial', 'line_ids.owner_display', 'line_ids.khasra_number',
        'line_ids.acquired_rakba', 'line_ids.determined_total', 'line_ids.line_status',
        'line_ids.payout_mode', 'line_ids.owner_count', 'line_ids.is_line_locked',
        'line_ids.payout_summary', 'line_ids.split_ids', 'line_ids.split_ids.bank_id',
        'line_ids.split_ids.bank_name', 'line_ids.export_id', 'line_ids.export_id.name',
        'line_ids.voucher_id.award_id.project_id', 'line_ids.voucher_id.award_id.village_id',
    )
    def _compute_lines_preview_html(self):
        status_labels = {
            'pending_account': ('Pending account', 'bhu_pv_st_pending', 'fa-clock-o'),
            'account_added': ('Account added', 'bhu_pv_st_account', 'fa-university'),
            'file_generated': ('File generated', 'bhu_pv_st_file', 'fa-file-excel-o'),
        }
        for rec in self:
            if not rec.line_ids:
                rec.lines_preview_html = Markup(
                    '<p class="text-muted mb-0">No R&amp;R lines on this voucher yet.</p>'
                )
                continue
            parts = [
                '<div class="table-responsive s23-preview-wrap s23-land-sim-table-wrap bhu_pv_preview_wrap">',
                '<table class="table table-sm s23-sim-table s23-sim-table-land bhu_pv_sim_table">',
                '<thead><tr>',
                '<th class="s23-sim-th s23-sortable-th bhu_pv_th_serial" scope="col" data-sort-type="num" title="Click to sort">'
                'क्र.<span class="s23-sort-indicator" aria-hidden="true"></span></th>',
                '<th class="s23-sim-th s23-sortable-th" scope="col" data-sort-type="text" title="Click to sort">'
                'Payee / भूस्वामी<span class="s23-sort-indicator" aria-hidden="true"></span></th>',
                '<th class="s23-sim-th s23-sortable-th bhu_pv_th_khasra" scope="col" data-sort-type="text" title="Click to sort">'
                'खसरा<span class="s23-sort-indicator" aria-hidden="true"></span></th>',
                '<th class="s23-sim-th s23-sortable-th" scope="col" data-sort-type="num" title="Click to sort">'
                'रकबा (हे.)<span class="s23-sort-indicator" aria-hidden="true"></span></th>',
                '<th class="s23-sim-th s23-sortable-th" scope="col" data-sort-type="num" title="Click to sort">'
                'Payable (8+9)<span class="s23-sort-indicator" aria-hidden="true"></span></th>',
                '<th class="s23-sim-th s23-sortable-th" scope="col" data-sort-type="num" title="Click to sort">'
                'Owners<span class="s23-sort-indicator" aria-hidden="true"></span></th>',
                '<th class="s23-sim-th s23-sortable-th" scope="col" data-sort-type="text" title="Click to sort">'
                'File ref / संदर्भ<span class="s23-sort-indicator" aria-hidden="true"></span></th>',
                '<th class="s23-sim-th" scope="col">Status</th>',
                '<th class="s23-sim-th" scope="col">Payout</th>',
                '<th class="s23-sim-th bhu_pv_th_actions" scope="col">Actions</th>',
                '</tr></thead><tbody>',
            ]
            for idx, line in enumerate(rec.line_ids.sorted(lambda l: (l.rr_serial, l.id))):
                st_label, st_cls, st_icon = status_labels.get(
                    line.line_status or 'pending_account',
                    ('—', 'bhu_pv_st_pending', 'fa-circle-o'),
                )
                payout = (line.payout_summary or '').strip()
                if not payout:
                    payout = 'Split %' if line.payout_mode == 'split' else 'One account'
                if line.payout_mode == 'split':
                    bank_names = line._get_split_bank_names()
                    if line.split_ids and bank_names:
                        payout_cls, payout_icon = 'bhu_pv_payout_split', 'fa-sitemap'
                    elif line.split_ids:
                        payout_cls, payout_icon = 'bhu_pv_payout_split', 'fa-users'
                    else:
                        payout_cls, payout_icon = 'bhu_pv_payout_split', 'fa-percent'
                elif line.bank_id or (line.bank_name or '').strip():
                    payout_cls, payout_icon = 'bhu_pv_payout_bank', 'fa-university'
                else:
                    payout_cls, payout_icon = 'bhu_pv_payout_empty', 'fa-plus-circle'
                locked = bool(line.is_line_locked)
                stripe_cls = 'bhu_pv_row_odd' if idx % 2 else 'bhu_pv_row_even'
                row_cls = f'bhu_pv_line_row {stripe_cls}'
                if locked:
                    row_cls += ' bhu_pv_line_row_locked'
                owner_html = line._get_payee_display_html()
                owner_title = html_lib.escape(line._get_payee_display_plain(), quote=True)
                action_parts = []
                if locked:
                    action_parts.append(
                        '<span class="bhu_pv_locked_tag" title="Payment file generated — click File ref to view">'
                        '<i class="fa fa-lock" aria-hidden="true"></i> Locked</span>'
                    )
                else:
                    action_parts.append(
                        f'<a href="#" role="button" class="btn btn-link btn-sm bhu_pv_line_edit_btn" '
                        f'data-line-id="{line.id}" title="Edit bank account or split" '
                        f'aria-label="Edit khasra {escape(line.khasra_number or "")}">'
                        f'<span class="fa fa-pencil" aria-hidden="true"></span>'
                        f'</a>'
                    )
                    if line.line_status == 'account_added':
                        action_parts.append(
                            f'<a href="#" role="button" class="btn btn-link btn-sm bhu_pv_line_remove_btn" '
                            f'data-line-id="{line.id}" title="Remove bank account (add again later)" '
                            f'aria-label="Remove account for khasra {escape(line.khasra_number or "")}">'
                            f'<span class="fa fa-trash-o" aria-hidden="true"></span>'
                            f'</a>'
                        )
                export_ref_cell = '<span class="text-muted">—</span>'
                row_export_id = ''
                if line.export_id:
                    export_ref = escape(line.export_id.name or '')
                    row_export_id = str(line.export_id.id)
                    export_ref_cell = (
                        f'<a href="#" role="button" class="bhu_pv_export_ref_link" '
                        f'data-export-id="{line.export_id.id}" data-voucher-line-id="{line.id}" '
                        f'title="View payment file lines for {export_ref}">{export_ref}</a>'
                    )
                khasra_attr = html_lib.escape((line.khasra_number or '').strip(), quote=True)
                parts.extend([
                    f'<tr class="{row_cls}" data-line-id="{line.id}" data-khasra="{khasra_attr}"'
                    f'{" data-export-id=\"" + row_export_id + "\"" if row_export_id else ""}>',
                    f'<td class="tabular-nums bhu_pv_td_serial">{line.rr_serial}</td>',
                    f'<td class="s23-wrap-cell bhu_pv_owner_cell" title="{owner_title}">'
                    f'{owner_html}</td>',
                    f'<td class="bhu_pv_td_khasra tabular-nums">{escape(line.khasra_number or "")}</td>',
                    f'<td class="tabular-nums">{line.acquired_rakba:.4f}</td>',
                    f'<td class="tabular-nums fw-bold">{line.determined_total:,.2f}</td>',
                    f'<td class="tabular-nums">{line.owner_count}</td>',
                    f'<td class="bhu_pv_export_ref_cell">{export_ref_cell}</td>',
                    f'<td><span class="bhu_pv_status_pill {st_cls}">'
                    f'<i class="fa {st_icon}" aria-hidden="true"></i>{escape(st_label)}</span></td>',
                    f'<td class="bhu_pv_payout_cell">'
                    f'<span class="bhu_pv_payout_chip {payout_cls}">'
                    f'<i class="fa {payout_icon}" aria-hidden="true"></i>{escape(payout)}</span></td>',
                    f'<td class="bhu_pv_td_actions">{"".join(action_parts)}</td>',
                    '</tr>',
                ])
            parts.append('</tbody></table></div>')
            rec.lines_preview_html = Markup(''.join(parts))

    @api.depends(
        'export_beneficiary_ids',
        'export_beneficiary_ids.payment_status',
        'export_ids',
    )
    def _compute_payment_tracking_html(self):
        for rec in self:
            beneficiaries = rec.export_beneficiary_ids
            rec.pending_payment_count = len(
                beneficiaries.filtered(lambda l: l.payment_status == 'pending')
            )
            rec.success_payment_count = len(
                beneficiaries.filtered(lambda l: l.payment_status == 'settled')
            )
            rec.failed_payment_count = len(
                beneficiaries.filtered(lambda l: l.payment_status == 'failed')
            )
            pending_html = rec._build_pending_export_files_html()
            rec.pending_payments_html = Markup(pending_html) if pending_html else Markup('')
            rec.success_payments_html = Markup('')
            rec.failed_payments_html = Markup('')

    @api.model
    def _payment_tracking_empty_html(self, message, icon='fa-file-excel-o'):
        """Styled empty state for payment tracking HTML panels."""
        icon_class = (icon or 'fa-file-excel-o').strip()
        if not icon_class.startswith('fa'):
            icon_class = 'fa-' + icon_class
        return (
            '<div class="bhu_pv_pay_empty_state text-center">'
            f'<div class="bhu_pv_pay_empty_icon" aria-hidden="true">'
            f'<i class="fa {escape(icon_class)}"></i></div>'
            f'<p class="bhu_pv_pay_empty_title">{escape(message)}</p>'
            '</div>'
        )

    def _build_pending_export_files_html(self):
        """File-level summary table (one row per generated Excel)."""
        self.ensure_one()
        exports = self.export_ids
        if not exports:
            return ''
        parts = [
            '<div class="bhu_pv_pay_files_block mb-3">',
            '<div class="bhu_pv_pay_files_title">Generated payment files / भुगतान फ़ाइलें</div>',
            '<div class="table-responsive s23-preview-wrap s23-land-sim-table-wrap bhu_pv_preview_wrap">',
            '<table class="table table-sm s23-sim-table s23-sim-table-land bhu_pv_sim_table bhu_pv_pay_table">',
            '<thead><tr>',
            '<th class="s23-sim-th">Reference</th>',
            '<th class="s23-sim-th">Rows</th>',
            '<th class="s23-sim-th">Khasras in file</th>',
            '<th class="s23-sim-th">Amount / राशि</th>',
            '<th class="s23-sim-th">Debit a/c</th>',
            '<th class="s23-sim-th">Status</th>',
            '<th class="s23-sim-th">Generated on</th>',
            '<th class="s23-sim-th">IndusInd ref</th>',
            '<th class="s23-sim-th bhu_pv_th_actions">Download</th>',
            '</tr></thead><tbody>',
        ]
        for idx, export in enumerate(exports):
            stripe_cls = 'bhu_pv_row_odd' if idx % 2 else 'bhu_pv_row_even'
            gen_date = fields.Datetime.to_string(export.generation_date) if export.generation_date else ''
            url = ''
            if export.generated_file:
                url = (
                    '/web/content/?model=bhu.payment.voucher.export'
                    f'&id={export.id}&field=generated_file'
                    '&filename_field=generated_file_filename&download=true'
                )
            dl_btn = (
                f'<a href="{url}" class="btn btn-link btn-sm bhu_pv_export_dl_btn" '
                f'title="Download Excel"><span class="fa fa-file-excel-o" aria-hidden="true"></span> '
                f'Download</a>'
            ) if url else ''
            parts.extend([
                f'<tr class="{stripe_cls} bhu_pv_export_file_row" data-export-id="{export.id}">',
                f'<td class="fw-semibold bhu_pv_export_ref_cell">'
                f'<a href="#" role="button" class="bhu_pv_export_ref_link" '
                f'data-export-id="{export.id}" title="Open payment file">'
                f'{escape(export.name or "")}</a></td>',
                f'<td class="tabular-nums">{export.khasra_count or 0}</td>',
                f'<td>{escape(export.khasra_summary or export.khasra_number or "")}</td>',
                f'<td class="tabular-nums fw-bold">{export.amount:,.2f}</td>',
                f'<td class="tabular-nums">{escape(export.debit_account_number or "")}</td>',
                f'<td><span class="bhu_pv_status_pill bhu_pv_st_file">'
                f'<i class="fa fa-file-excel-o" aria-hidden="true"></i>'
                f'Payment file generated</span></td>',
                f'<td class="tabular-nums">{escape(gen_date)}</td>',
                f'<td>{escape(export.indusind_authorisation_ref or "")}</td>',
                f'<td class="bhu_pv_td_actions">{dl_btn}</td>',
                '</tr>',
            ])
        parts.append('</tbody></table></div></div>')
        return ''.join(parts)

    def _build_beneficiary_payment_html(self, lines, pay_status):
        """HTML table for pending / success / failed beneficiary payment lines."""
        self.ensure_one()
        if not lines:
            empty_msg = {
                'pending': _('No pending payment lines yet. Generate a payment file to add rows here.'),
                'settled': _('No successful payments yet.'),
                'failed': _('No failed payments yet.'),
            }.get(pay_status, _('No rows.'))
            return self._payment_tracking_empty_html(empty_msg, 'fa-inbox')

        status_labels = {
            'pending': ('Pending', 'bhu_pv_st_pending', 'fa-clock-o'),
            'settled': ('Success', 'bhu_pv_st_file', 'fa-check-circle'),
            'failed': ('Failed', 'bhu_pv_st_failed', 'fa-times-circle'),
        }
        st_label, st_cls, st_icon = status_labels.get(pay_status, ('—', '', ''))

        parts = [
            '<div class="bhu_pv_pay_lines_block">',
            '<div class="bhu_pv_pay_files_title">Beneficiary lines / लाभार्थी पंक्तियाँ</div>',
            '<div class="table-responsive s23-preview-wrap s23-land-sim-table-wrap bhu_pv_preview_wrap">',
            '<table class="table table-sm s23-sim-table s23-sim-table-land bhu_pv_sim_table bhu_pv_pay_table">',
            '<thead><tr>',
            '<th class="s23-sim-th">File ref</th>',
            '<th class="s23-sim-th">Transaction UUID</th>',
            '<th class="s23-sim-th">Khasra / खसरा</th>',
            '<th class="s23-sim-th">Payee / लाभार्थी</th>',
            '<th class="s23-sim-th">Bank / बैंक</th>',
            '<th class="s23-sim-th">Account</th>',
            '<th class="s23-sim-th">IFSC</th>',
            '<th class="s23-sim-th">Amount / राशि</th>',
            '<th class="s23-sim-th">Status</th>',
            '<th class="s23-sim-th">UTR</th>',
        ]
        if pay_status == 'pending':
            parts.append('<th class="s23-sim-th bhu_pv_th_actions">Excel</th>')
        elif pay_status == 'failed':
            parts.append('<th class="s23-sim-th">Reason</th>')
        parts.append('</tr></thead><tbody>')

        for idx, line in enumerate(lines):
            stripe_cls = 'bhu_pv_row_odd' if idx % 2 else 'bhu_pv_row_even'
            export = line.export_id
            export_name = escape(export.name or '')
            download_cell = ''
            if pay_status == 'pending' and export and export.generated_file:
                url = (
                    '/web/content/?model=bhu.payment.voucher.export'
                    f'&id={export.id}&field=generated_file'
                    '&filename_field=generated_file_filename&download=true'
                )
                download_cell = (
                    f'<td class="bhu_pv_td_actions">'
                    f'<a href="{url}" class="btn btn-link btn-sm bhu_pv_export_dl_btn" '
                    f'title="Download Excel" target="_self">'
                    f'<span class="fa fa-download" aria-hidden="true"></span></a></td>'
                )
            reason_cell = ''
            if pay_status == 'failed':
                reason_cell = f'<td>{escape(line.failure_reason or "")}</td>'

            voucher_line_id = line.voucher_line_id.id if line.voucher_line_id else ''
            parts.extend([
                f'<tr class="{stripe_cls} bhu_pv_beneficiary_row" '
                f'data-export-id="{export.id if export else ""}" '
                f'data-voucher-line-id="{voucher_line_id}">',
                f'<td class="fw-semibold bhu_pv_export_ref_cell">'
                f'<a href="#" role="button" class="bhu_pv_export_ref_link" '
                f'data-export-id="{export.id if export else ""}" '
                f'data-voucher-line-id="{voucher_line_id}">{export_name}</a></td>',
                f'<td class="tabular-nums bhu_pv_tx_uuid">{escape(line.transaction_uuid or "")}</td>',
                f'<td>{escape(line.khasra_number or "")}</td>',
                f'<td class="bhu_pv_owner_cell">{escape(line.beneficiary_name or "")}</td>',
                f'<td>{escape(line.bank_name or "")}</td>',
                f'<td class="tabular-nums">{escape(line.account_number or "")}</td>',
                f'<td class="tabular-nums">{escape(line.ifsc_code or "")}</td>',
                f'<td class="tabular-nums fw-bold">{line.amount:,.2f}</td>',
                f'<td><span class="bhu_pv_status_pill {st_cls}">'
                f'<i class="fa {st_icon}" aria-hidden="true"></i>{escape(st_label)}</span></td>',
                f'<td class="tabular-nums">{escape(line.utr_number or "")}</td>',
                download_cell,
                reason_cell,
                '</tr>',
            ])
        parts.append('</tbody></table></div></div>')
        return ''.join(parts)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            award_id = vals.get('award_id')
            if award_id and self.search_count([('award_id', '=', award_id)]):
                existing = self.search([('award_id', '=', award_id)], limit=1)
                raise ValidationError(_(
                    'Only one payment voucher is allowed per Section 23 award. '
                    'Open the existing voucher: %s'
                ) % (existing.name,))
            if vals.get('name', 'New') in ('New', '', False):
                seq = self.env['ir.sequence'].next_by_code('bhu.payment.voucher')
                if not seq:
                    seq = 'PV/RR/MANUAL-%s' % fields.Datetime.now().strftime('%Y%m%d%H%M%S')
                vals['name'] = seq
        records = super().create(vals_list)
        for rec in records:
            rec._merge_duplicate_voucher_lines()
            rec._sync_line_col_amounts_from_rr()
        return records

    def _sync_line_col_amounts_from_rr(self, lines=None):
        """Refresh col 8 / col 9 / payable for voucher lines from current R&R award."""
        self.ensure_one()
        if not self.award_id:
            return
        self._merge_duplicate_voucher_lines()
        khasra_map = self.award_id._get_rr_khasra_payable_map()
        land_by_khasra = {}
        for row in self.award_id.get_land_compensation_data() or []:
            khasra = (row.get('khasra') or '').strip()
            if not khasra:
                continue
            area = float(row.get('acquired_area', 0.0) or 0.0)
            land_by_khasra[khasra] = land_by_khasra.get(khasra, 0.0) + area
        target = lines or self.line_ids.filtered(lambda l: not l.is_line_locked)
        for line in target:
            k = (line.khasra_number or '').strip()
            data = khasra_map.get(k)
            if not data:
                continue
            vals = {
                'rr_col8_amount': data['rr_col8_amount'],
                'rr_col9_amount': data['rr_col9_amount'],
                'determined_total': data['determined_total'],
            }
            if k in land_by_khasra:
                vals['acquired_rakba'] = land_by_khasra[k]
            line.write(vals)

    def _merge_duplicate_voucher_lines(self):
        """One voucher row per khasra + owner — sum rakba and payable amounts."""
        self.ensure_one()
        groups = {}
        for line in self.line_ids.sorted('id'):
            if line.is_line_locked or line.export_id or line.split_ids:
                continue
            khasra = (line.khasra_number or '').strip()
            if not khasra:
                continue
            owner = (line.owner_display or '').strip().lower()
            groups.setdefault((khasra.lower(), owner), []).append(line)

        for _key, lines in groups.items():
            if len(lines) <= 1:
                continue
            primary = lines[0]
            for candidate in lines:
                if candidate._bank_details_complete():
                    primary = candidate
                    break
            others = [l for l in lines if l.id != primary.id]
            primary.write({
                'acquired_rakba': sum(float(l.acquired_rakba or 0.0) for l in lines),
                'rr_col8_amount': sum(float(l.rr_col8_amount or 0.0) for l in lines),
                'rr_col9_amount': sum(float(l.rr_col9_amount or 0.0) for l in lines),
                'determined_total': sum(float(l.determined_total or 0.0) for l in lines),
            })
            self.env['bhu.payment.voucher.line'].browse([l.id for l in others]).unlink()

    @api.model
    def _merge_all_voucher_duplicate_lines(self):
        """Module upgrade: collapse duplicate khasra rows on existing vouchers."""
        for voucher in self.search([]):
            voucher._merge_duplicate_voucher_lines()

    def _payment_voucher_ui_snapshot(self):
        """Fresh HTML table + counters for client-side refresh after RPC edits."""
        self.ensure_one()
        self.invalidate_recordset([
            'lines_preview_html',
            'account_ready_count',
            'pending_account_count',
            'export_count',
            'line_count',
            'lines_file_generated_count',
            'payment_files_status',
        ])
        return {
            'voucher_id': self.id,
            'lines_preview_html': str(self.lines_preview_html or ''),
            'account_ready_count': self.account_ready_count,
            'pending_account_count': self.pending_account_count,
            'export_count': self.export_count,
            'line_count': self.line_count,
            'lines_file_generated_count': self.lines_file_generated_count,
            'payment_files_status': self.payment_files_status or 'pending',
        }

    def _get_ready_export_lines(self):
        """Voucher lines ready for bulk bank file generation."""
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.line_status == 'account_added' and not l.is_line_locked
        )

    def _prepare_bulk_export_preview(self):
        """Summary for generate confirmation wizard."""
        self.ensure_one()
        lines = self._get_ready_export_lines().sorted(lambda l: (l.rr_serial, l.id))
        if not lines:
            raise UserError(_(
                'No khasra rows are ready. Add bank details until status is '
                '"Account added", then try again.'
            ))
        if not (self.debit_account_number or '').strip():
            raise UserError(_('Please enter the debit account number on this voucher first.'))

        all_rows = []
        total_amount = 0.0
        table_rows = []
        for idx, line in enumerate(lines, start=1):
            line._validate_payout()
            row_data = line._get_bank_export_rows()
            if not row_data:
                raise UserError(_('No bank rows to export for khasra %s.') % (line.khasra_number or '-'))
            all_rows.extend(row_data)
            line_total = sum(float(r.get('amount') or 0.0) for r in row_data)
            total_amount += line_total
            accounts = []
            ifscs = []
            for r in row_data:
                ac = (r.get('account_number') or '').strip()
                if ac and ac not in accounts:
                    accounts.append(ac)
                ifsc = (r.get('ifsc_code') or '').strip().upper()
                if ifsc and ifsc not in ifscs:
                    ifscs.append(ifsc)
            if len(accounts) == 1:
                account_cell = escape(accounts[0])
            elif len(accounts) > 1:
                account_cell = escape(', '.join(accounts))
            else:
                account_cell = '<span class="text-muted">—</span>'
            if len(ifscs) == 1:
                ifsc_cell = escape(ifscs[0])
            elif len(ifscs) > 1:
                ifsc_cell = escape(', '.join(ifscs))
            else:
                ifsc_cell = '<span class="text-muted">—</span>'
            stripe_cls = 'bhu_pv_row_odd' if idx % 2 else 'bhu_pv_row_even'
            table_rows.append(
                f'<tr class="{stripe_cls}">'
                f'<td class="text-center tabular-nums fw-bold">{idx}</td>'
                f'<td class="text-center">{escape(line.khasra_number or "")}</td>'
                f'<td class="bhu_pv_owner_cell">{line._get_payee_display_html()}</td>'
                f'<td class="tabular-nums bhu_pv_gen_acct">{account_cell}</td>'
                f'<td class="tabular-nums bhu_pv_gen_ifsc">{ifsc_cell}</td>'
                f'<td class="text-end tabular-nums fw-bold">{line_total:,.2f}</td>'
                f'<td class="text-center tabular-nums">{len(row_data)}</td>'
                '</tr>'
            )

        khasras = lines.mapped('khasra_number')
        preview_html = Markup(
            '<div class="table-responsive bhu_pv_gen_preview_wrap">'
            '<table class="table table-sm bhu_pv_gen_preview_table mb-0">'
            '<thead><tr>'
            '<th class="bhu_pv_gen_preview_th text-center">क्र.</th>'
            '<th class="bhu_pv_gen_preview_th text-center">खसरा</th>'
            '<th class="bhu_pv_gen_preview_th">Payee / भूस्वामी</th>'
            '<th class="bhu_pv_gen_preview_th">Account / खाता</th>'
            '<th class="bhu_pv_gen_preview_th">IFSC</th>'
            '<th class="bhu_pv_gen_preview_th text-end">Amount / राशि</th>'
            '<th class="bhu_pv_gen_preview_th text-center">Beneficiaries</th>'
            '</tr></thead><tbody>'
            + ''.join(table_rows)
            + '</tbody></table></div>'
        )
        return {
            'lines': lines,
            'all_rows': all_rows,
            'total_amount': round(total_amount, 2),
            'khasra_count': len(lines),
            'beneficiary_count': len(all_rows),
            'khasra_summary': ', '.join(khasras),
            'preview_html': preview_html,
        }

    def action_generate_payment_files(self):
        """Open confirmation wizard before generating bank Excel / IndusInd authorisation."""
        self.ensure_one()
        self._prepare_bulk_export_preview()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Payment File'),
            'res_model': 'bhu.payment.voucher.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_voucher_id': self.id},
        }

    def _execute_bulk_payment_file_generation(self, delivery_mode):
        """Create export, optional IndusInd authorisation, optional Excel download."""
        self.ensure_one()
        preview = self._prepare_bulk_export_preview()
        lines = preview['lines']
        all_rows = preview['all_rows']
        total_amount = preview['total_amount']

        export = False
        messages = []

        if delivery_mode in ('excel', 'both'):
            excel_bytes = self.env['bhu.payment.file'].generate_bank_excel_bytes(
                all_rows,
                debit_account=(self.debit_account_number or '').strip(),
                purpose_1=self.village_id.name or '',
                purpose_2=self.project_id.name or '',
            )
            khasra_label = '_'.join(
                (k or 'NA').replace('/', '-') for k in lines.mapped('khasra_number')[:5]
            )
            if len(lines) > 5:
                khasra_label += '_plus%d' % (len(lines) - 5)
            fname = f"Payment_{self.name}_{khasra_label}.xlsx"
            export = self.env['bhu.payment.voucher.export'].create({
                'voucher_id': self.id,
                'voucher_line_id': lines[0].id if len(lines) == 1 else False,
                'voucher_line_ids': [(6, 0, lines.ids)],
                'amount': total_amount,
                'debit_account_number': self.debit_account_number or '',
                'generated_file': base64.b64encode(excel_bytes),
                'generated_file_filename': fname,
            })
            lines.write({'export_id': export.id})
            export.create_beneficiary_lines(all_rows)
            messages.append(_('Bank Excel file %s created.') % export.name)

        if delivery_mode in ('indusind', 'both'):
            if not export:
                export = self.env['bhu.payment.voucher.export'].create({
                    'voucher_id': self.id,
                    'voucher_line_id': lines[0].id if len(lines) == 1 else False,
                    'voucher_line_ids': [(6, 0, lines.ids)],
                    'amount': total_amount,
                    'debit_account_number': self.debit_account_number or '',
                })
                lines.write({'export_id': export.id})
                export.create_beneficiary_lines(all_rows)
            auth_result = self.env['bhu.payment.file'].submit_indusind_online_authorisation(
                export=export,
                payment_rows=all_rows,
                voucher=self,
                khasra_numbers=lines.mapped('khasra_number'),
            )
            messages.append(auth_result.get('message') or _('IndusInd Online Authorisation submitted.'))

        self.message_post(
            body=_(
                'Payment file generation for %(count)s khasra(s): %(khasras)s.<br/>%(detail)s'
            ) % {
                'count': len(lines),
                'khasras': ', '.join(lines.mapped('khasra_number')),
                'detail': '<br/>'.join(messages),
            },
            message_type='notification',
        )

        if delivery_mode in ('excel', 'both') and export:
            return export.action_download()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payment file generated'),
                'message': ' '.join(messages),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def _prepare_payment_file_line_commands(self):
        """Build ``bhu.payment.file.line`` rows: one per voucher line, or one per split."""
        self.ensure_one()
        cmds = []
        serial = 1
        for vline in self.line_ids.sorted(lambda l: (l.rr_serial, l.id)):
            if vline.payout_mode == 'split' and vline.split_ids:
                part = 1
                for sp in vline.split_ids:
                    remark = _(
                        'Voucher %(voucher)s · Khasra %(khasra)s · split %(part)s'
                    ) % {
                        'voucher': self.name,
                        'khasra': vline.khasra_number or '-',
                        'part': part,
                    }
                    if sp.note:
                        remark = '%s — %s' % (remark, sp.note)
                    lo_id = sp.split_landowner_id.id if sp.split_landowner_id else (
                        vline.landowner_id.id if vline.landowner_id else False
                    )
                    bene = (sp.payee_display_name or '').strip() or (vline.owner_display or '')[:120]
                    cmds.append((0, 0, {
                        'serial_number': serial,
                        'award_serial_number': vline.rr_serial,
                        'khasra_number': vline.khasra_number or '',
                        'landowner_id': lo_id,
                        'beneficiary_override': bene[:240] if bene else False,
                        'bank_name': (sp.bank_id.name or sp.bank_name or '').strip(),
                        'bank_branch': (sp.bank_branch or '').strip(),
                        'account_number': (sp.account_number or '').strip().replace(' ', ''),
                        'ifsc_code': (sp.ifsc_code or '').strip().upper(),
                        'compensation_amount': float(sp.amount or 0.0),
                        'net_payable_amount': float(sp.amount or 0.0),
                        'remark': remark,
                    }))
                    serial += 1
                    part += 1
            else:
                remark = _(
                    'Voucher %(voucher)s · %(owner)s · Khasra %(khasra)s'
                ) % {
                    'voucher': self.name,
                    'owner': (vline.owner_display or '')[:120],
                    'khasra': vline.khasra_number or '-',
                }
                lo_id = vline.landowner_id.id if vline.landowner_id else False
                cmds.append((0, 0, {
                    'serial_number': serial,
                    'award_serial_number': vline.rr_serial,
                    'khasra_number': vline.khasra_number or '',
                    'landowner_id': lo_id,
                    'beneficiary_override': False,
                    'bank_name': (vline.bank_id.name or vline.bank_name or '').strip(),
                    'bank_branch': (vline.bank_branch or '').strip(),
                    'account_number': (vline.account_number or '').strip().replace(' ', ''),
                    'ifsc_code': (vline.ifsc_code or '').strip().upper(),
                    'compensation_amount': float(vline.determined_total or 0.0),
                    'net_payable_amount': float(vline.determined_total or 0.0),
                    'remark': remark,
                }))
                serial += 1
        return cmds

    def action_create_or_sync_payment_file(self):
        """Create or replace draft payment file lines from this voucher (bank + splits)."""
        self.ensure_one()
        line_cmds = self._prepare_payment_file_line_commands()
        if not line_cmds:
            raise UserError(_('No payment lines could be built from this voucher.'))

        PaymentFile = self.env['bhu.payment.file']
        payment_file = PaymentFile.search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
        ], limit=1)

        if payment_file and payment_file.state == 'generated':
            raise UserError(_(
                'Payment file "%s" is already generated. You cannot overwrite it from a voucher. '
                'Create a correction flow or use a new cycle if your process allows.'
            ) % (payment_file.name,))

        if payment_file and payment_file.award_id and payment_file.award_id != self.award_id:
            raise UserError(_(
                'A draft payment file already exists for this village linked to another award (%s). '
                'Open or clear that file before syncing this voucher.'
            ) % (payment_file.award_id.display_name,))

        if not payment_file:
            payment_file = PaymentFile.with_context(
                skip_payment_line_populate=True,
                bhu_allow_payment_file_create=True,
            ).create({
                'name': 'New',
                'project_id': self.project_id.id,
                'village_id': self.village_id.id,
                'award_id': self.award_id.id,
            })

        payment_file.write({
            'award_id': self.award_id.id,
            'payment_line_ids': [(5, 0, 0)] + line_cmds,
        })
        self.payment_file_id = payment_file.id
        self.message_post(
            body=_('Payment file updated from voucher: %s') % (payment_file.display_name,),
            message_type='notification',
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment File'),
            'res_model': 'bhu.payment.file',
            'view_mode': 'form',
            'res_id': payment_file.id,
            'target': 'current',
        }

    def action_download_bank_file(self):
        """Generate (if needed) and download bank bulk-payment Excel."""
        self.ensure_one()
        if not self.payment_file_id:
            raise UserError(_('Create / update the payment file first from this voucher.'))
        payment_file = self.payment_file_id
        if payment_file.state != 'generated' or not payment_file.generated_file:
            return payment_file.action_generate_file()
        return payment_file.action_download_generated_file()


class BhuPaymentVoucherLine(models.Model):
    _name = 'bhu.payment.voucher.line'
    _description = 'R&R Payment Voucher Line'
    _order = 'rr_serial, id'

    voucher_id = fields.Many2one(
        'bhu.payment.voucher',
        string='Voucher',
        required=True,
        ondelete='cascade',
        index=True,
    )
    rr_serial = fields.Integer(
        string='Serial / क्र.',
        required=True,
        help='Serial number as per R&R award grouping.',
    )
    owner_display = fields.Char(
        string='Bhūswāmī / भूस्वामी',
        required=True,
    )
    landowner_id = fields.Many2one(
        'bhu.landowner',
        string='Landowner Record',
        ondelete='set null',
    )
    khasra_number = fields.Char(
        string='Khasra / खसरा',
        required=True,
    )
    acquired_rakba = fields.Float(
        string='Acquired rakba (ha)',
        digits=(16, 4),
        help='Acquired area for this khasra line in hectares (from R&R land data).',
    )
    determined_total = fields.Monetary(
        string='Total payable (Col 8 + 9) / कुल देय',
        required=True,
        currency_field='currency_id',
        help='R&R column 8 + column 9 — amount sent to bank for this khasra.',
    )
    rr_col8_amount = fields.Monetary(
        string='R&R Col 8 / निर्धारित कुल',
        currency_field='currency_id',
        readonly=True,
    )
    rr_col9_amount = fields.Monetary(
        string='R&R Col 9 / अतिरिक्त',
        currency_field='currency_id',
        readonly=True,
    )
    line_status = fields.Selection(
        [
            ('pending_account', 'Pending account / खाता लंबित'),
            ('account_added', 'Account added / खाता जोड़ा गया'),
            ('file_generated', 'Payment file generated / फ़ाइल तैयार'),
        ],
        string='Status / स्थिति',
        compute='_compute_line_status',
        store=True,
    )
    is_line_locked = fields.Boolean(
        string='Locked',
        compute='_compute_line_status',
        store=True,
        help='Row is locked after a bank payment file is generated.',
    )
    export_id = fields.Many2one(
        'bhu.payment.voucher.export',
        string='Payment file export',
        readonly=True,
        copy=False,
    )
    export_ref = fields.Char(
        string='File ref / संदर्भ',
        related='export_id.name',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='voucher_id.currency_id',
        store=True,
        readonly=True,
    )

    allow_split = fields.Boolean(
        string='Multi-owner khasra / बहु-भूस्वामी खसरा',
        compute='_compute_allow_split',
        store=False,
        help='Hint: this khasra has more than one landowner on surveys — splitting is often useful.',
    )
    owner_count = fields.Integer(
        string='Owner count / भूस्वामी सं.',
        compute='_compute_owner_count',
        store=False,
        help='Number of landowners on this khasra (from survey links or owner banner text).',
    )
    payout_mode = fields.Selection(
        [
            ('single', 'One account / एक खाता'),
            ('split', 'Split by % / प्रतिशत विभाजन'),
        ],
        string='Payout',
        default='single',
        required=True,
    )
    split_status_hint = fields.Char(
        string='Split % check',
        compute='_compute_split_status_hint',
    )
    payout_summary = fields.Char(
        string='Summary',
        compute='_compute_payout_summary',
    )
    line_editor_html = fields.Html(
        string='Line editor',
        compute='_compute_line_editor_html',
        sanitize=False,
    )
    khasra_landowner_ids = fields.Many2many(
        'bhu.landowner',
        string='Khasra landowners',
        compute='_compute_khasra_landowner_ids',
        help='Landowners on surveys for this khasra — used to filter split payee links.',
    )
    split_ids = fields.One2many(
        'bhu.payment.voucher.line.split',
        'voucher_line_id',
        string='Split bank accounts / विभाजित खाते',
    )

    beneficiary_address = fields.Text(
        string='Address / पता',
    )
    bank_id = fields.Many2one(
        'res.bank',
        string='Bank',
        domain="[('bhu_category', '!=', False)]",
        help='Scheduled commercial / payments banks (Indian master list).',
    )
    bank_name = fields.Char(
        string='Bank name / बैंक',
        help='Synced from bank selection; kept for export and legacy rows.',
    )
    bank_branch = fields.Char(
        string='Branch / शाखा',
        help='Optional. IFSC identifies branch for NEFT; not required on the voucher.',
    )
    account_number = fields.Char(string='Account number / खाता क्रमांक')
    ifsc_code = fields.Char(string='IFSC / आईएफएससी')

    @api.model_create_multi
    def create(self, vals_list):
        out = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('bank_id'):
                bank = self.env['res.bank'].browse(vals['bank_id'])
                if bank.exists():
                    vals['bank_name'] = bank.name
            out.append(vals)
        return super().create(out)

    def write(self, vals):
        locked = self.filtered('is_line_locked')
        if locked and vals:
            raise UserError(_(
                'Khasra line(s) %s are locked after payment file generation. '
                'You cannot edit bank details anymore.'
            ) % ', '.join(locked.mapped('khasra_number')))
        vals = dict(vals)
        if vals.get('bank_id'):
            bank = self.env['res.bank'].browse(vals['bank_id'])
            if bank.exists():
                vals['bank_name'] = bank.name
        return super().write(vals)

    @api.depends(
        'export_id', 'export_id.generated_file',
        'payout_mode', 'bank_id', 'bank_name', 'account_number', 'ifsc_code',
        'split_ids', 'split_ids.bank_id', 'split_ids.bank_name',
        'split_ids.account_number', 'split_ids.ifsc_code',
    )
    def _compute_line_status(self):
        for line in self:
            if line.export_id and line.export_id.generated_file:
                line.line_status = 'file_generated'
                line.is_line_locked = True
            elif line._bank_details_complete():
                line.line_status = 'account_added'
                line.is_line_locked = False
            else:
                line.line_status = 'pending_account'
                line.is_line_locked = False

    def _bank_details_complete(self):
        """True when single or split payout has enough bank data to generate a file."""
        self.ensure_one()
        if self.payout_mode == 'split':
            if len(self.split_ids) < 2:
                return False
            for sp in self.split_ids:
                if not sp.bank_id and not (sp.bank_name or '').strip():
                    return False
                if not (sp.account_number or '').strip() or not (sp.ifsc_code or '').strip():
                    return False
            return True
        return bool(
            (self.bank_id or (self.bank_name or '').strip())
            and (self.account_number or '').strip()
            and (self.ifsc_code or '').strip()
        )

    def _new_bank_transaction_uuid(self):
        """Pure 32-char hex UUID (no dashes, no voucher prefix)."""
        return uuid.uuid4().hex.upper()

    def _make_bank_external_ref(self, tx_uuid, split_idx=None):
        """Readable External Ref No for bank Excel (voucher + khasra + UUID)."""
        self.ensure_one()
        voucher_name = (self.voucher_id.name or 'PV').strip()
        khasra = (self.khasra_number or 'K').strip()
        if split_idx:
            return f"{voucher_name}_{khasra}_{split_idx}_{tx_uuid}"
        return f"{voucher_name}_{khasra}_{tx_uuid}"

    def _get_bank_export_rows(self):
        """Rows for bank Excel — one per beneficiary (single or split)."""
        self.ensure_one()
        rows = []
        if self.payout_mode == 'split' and self.split_ids:
            for idx, sp in enumerate(self.split_ids, start=1):
                tx_uuid = self._new_bank_transaction_uuid()
                external_ref = self._make_bank_external_ref(tx_uuid, split_idx=idx)
                lo_id = sp.split_landowner_id.id if sp.split_landowner_id else (
                    self.landowner_id.id if self.landowner_id else False
                )
                rows.append({
                    'amount': round(float(sp.amount or 0.0), 2),
                    'beneficiary_name': (sp.payee_display_name or self.owner_display or '')[:120],
                    'bank_name': (sp.bank_id.name or sp.bank_name or '').strip(),
                    'account_number': (sp.account_number or '').strip().replace(' ', ''),
                    'ifsc_code': (sp.ifsc_code or '').strip().upper(),
                    'external_ref': external_ref,
                    'transaction_uuid': tx_uuid,
                    'khasra_number': self.khasra_number or '',
                    'voucher_line_id': self.id,
                    'landowner_id': lo_id,
                })
        else:
            tx_uuid = self._new_bank_transaction_uuid()
            external_ref = self._make_bank_external_ref(tx_uuid)
            rows.append({
                'amount': round(float(self.determined_total or 0.0), 2),
                'beneficiary_name': (self.owner_display or '')[:120],
                'bank_name': (self.bank_id.name or self.bank_name or '').strip(),
                'account_number': (self.account_number or '').strip().replace(' ', ''),
                'ifsc_code': (self.ifsc_code or '').strip().upper(),
                'external_ref': external_ref,
                'transaction_uuid': tx_uuid,
                'khasra_number': self.khasra_number or '',
                'voucher_line_id': self.id,
                'landowner_id': self.landowner_id.id if self.landowner_id else False,
            })
        return rows

    def action_generate_payment_file(self):
        """Generate bank Excel for this khasra row only."""
        self.ensure_one()
        if self.is_line_locked:
            raise UserError(_(
                'Payment file already generated for khasra %s. Download it from the Payment Files tab.'
            ) % (self.khasra_number or '-'))
        self._validate_payout()
        voucher = self.voucher_id
        rows = self._get_bank_export_rows()
        if not rows:
            raise UserError(_('No bank rows to export for khasra %s.') % (self.khasra_number or '-'))

        excel_bytes = self.env['bhu.payment.file'].generate_bank_excel_bytes(
            rows,
            debit_account=(voucher.debit_account_number or '').strip(),
            purpose_1=voucher.village_id.name or '',
            purpose_2=voucher.project_id.name or '',
        )
        fname = f"Payment_{voucher.name}_Khasra_{(self.khasra_number or 'NA').replace('/', '-')}.xlsx"
        export = self.env['bhu.payment.voucher.export'].create({
            'voucher_id': voucher.id,
            'voucher_line_id': self.id,
            'voucher_line_ids': [(6, 0, self.ids)],
            'amount': self.determined_total,
            'debit_account_number': voucher.debit_account_number or '',
            'generated_file': base64.b64encode(excel_bytes),
            'generated_file_filename': fname,
        })
        self.export_id = export.id
        export.create_beneficiary_lines(rows)
        voucher.message_post(
            body=_('Payment file generated for khasra %(k)s: %(ref)s') % {
                'k': self.khasra_number or '-',
                'ref': export.name,
            },
            message_type='notification',
        )
        return export.action_download()

    def action_download_payment_file(self):
        self.ensure_one()
        if not self.export_id:
            raise UserError(_('No payment file export found for this khasra line.'))
        return self.export_id.action_download()

    def _get_line_editor_banks(self):
        """Indian master banks for HTML editor dropdowns."""
        banks = self.env['res.bank'].search(
            [('bhu_category', '!=', False)],
            order='name',
        )
        return [{'id': b.id, 'name': b.name} for b in banks]

    def _get_line_editor_split_rows(self):
        """Split rows for HTML editor (existing lines or default payees, no add-line)."""
        self.ensure_one()
        if self.split_ids:
            return [{
                'id': sp.id,
                'landowner_id': sp.split_landowner_id.id or False,
                'payee_name': (sp.payee_display_name or sp.payee_name or '').strip(),
                'percent_share': float(sp.percent_share or 0.0),
                'amount': float(sp.amount or 0.0),
                'bank_id': sp.bank_id.id or False,
                'account_number': (sp.account_number or '').strip(),
                'ifsc_code': (sp.ifsc_code or '').strip(),
            } for sp in self.split_ids]
        rows = []
        for _cmd, _x, vals in self._prepare_default_split_commands():
            owner_id = vals.get('split_landowner_id')
            if hasattr(owner_id, 'id'):
                owner_id = owner_id.id
            rows.append({
                'id': False,
                'landowner_id': owner_id or False,
                'payee_name': (vals.get('payee_name') or '').strip(),
                'percent_share': float(vals.get('percent_share') or 0.0),
                'amount': round(
                    float(self.determined_total or 0.0)
                    * float(vals.get('percent_share') or 0.0) / 100.0,
                    2,
                ),
                'bank_id': vals.get('bank_id') or False,
                'account_number': (vals.get('account_number') or '').strip(),
                'ifsc_code': (vals.get('ifsc_code') or '').strip(),
            })
        return rows

    @api.depends(
        'is_line_locked',
        'payout_mode',
        'khasra_number',
        'owner_display',
        'determined_total',
        'currency_id',
        'allow_split',
        'bank_id',
        'account_number',
        'ifsc_code',
        'split_ids',
        'split_ids.percent_share',
        'split_ids.amount',
        'split_ids.bank_id',
        'split_ids.account_number',
        'split_ids.ifsc_code',
        'split_ids.split_landowner_id',
        'split_ids.payee_name',
    )
    def _compute_line_editor_html(self):
        for line in self:
            if line.is_line_locked:
                line.line_editor_html = False
                continue
            payable = float(line.determined_total or 0.0)
            splits = line._get_line_editor_split_rows()
            total_p = sum(s['percent_share'] for s in splits)
            if line.payout_mode == 'split' and splits and abs(total_p - 100.0) <= 0.02:
                status_cls = 'bhu_pv_le_status_ok'
                status_text = _('OK — 100%% · ₹ %s') % f'{payable:,.2f}'
            elif line.payout_mode == 'split' and splits:
                status_cls = 'bhu_pv_le_status_warn'
                status_text = _('Percent total is %s (must be 100).') % round(total_p, 2)
            else:
                status_cls = 'bhu_pv_le_status_neutral'
                status_text = ''
            config = {
                'line_id': line.id,
                'khasra': line.khasra_number or '',
                'owner': line._get_payee_display_plain() or line.owner_display or '',
                'payable': payable,
                'currency_symbol': line.currency_id.symbol or '₹',
                'allow_split': bool(line.allow_split),
                'payout_mode': line.payout_mode or 'single',
                'bank_id': line.bank_id.id or False,
                'account_number': (line.account_number or '').strip(),
                'ifsc_code': (line.ifsc_code or '').strip(),
                'banks': line._get_line_editor_banks(),
                'splits': splits,
                'status_text': status_text,
                'status_class': status_cls,
                'has_account': line._bank_details_complete(),
            }
            line.line_editor_html = Markup(line._render_line_editor_html(config))

    def _render_line_editor_html(self, config):
        """Compact HTML editor for bank / split payout (no add-line)."""
        cfg_json = json.dumps(config, ensure_ascii=False)
        cfg_json = cfg_json.replace('<', '\\u003c').replace('>', '\\u003e')
        khasra = escape(config.get('khasra') or '')
        owner = escape(config.get('owner') or '')
        payable = float(config.get('payable') or 0.0)
        sym = escape(config.get('currency_symbol') or '₹')
        mode = config.get('payout_mode') or 'single'
        allow_split = config.get('allow_split')
        hint = ''
        if allow_split:
            hint = (
                '<div class="bhu_pv_le_hint" role="note">'
                '<i class="fa fa-info-circle" aria-hidden="true"></i> '
                'Several landowners on this khasra — use <strong>Split by %</strong> if needed.'
                '</div>'
            )
        single_on = ' is-on' if mode == 'single' else ''
        split_on = ' is-on' if mode == 'split' else ''
        split_panel_cls = '' if mode == 'split' else ' d-none'
        single_panel_cls = '' if mode == 'single' else ' d-none'
        split_disabled = '' if allow_split else ' disabled'
        status_cls = escape(config.get('status_class') or 'bhu_pv_le_status_neutral')
        status_text = escape(config.get('status_text') or '')
        status_block = (
            f'<div class="bhu_pv_le_status {status_cls}" data-role="split-status">{status_text}</div>'
            if status_text
            else '<div class="bhu_pv_le_status bhu_pv_le_status_neutral d-none" data-role="split-status"></div>'
        )
        bank_options = ['<option value="">Select bank…</option>']
        sel_bank = config.get('bank_id')
        for bank in config.get('banks') or []:
            bid = bank['id']
            sel = ' selected' if sel_bank and int(sel_bank) == int(bid) else ''
            bank_options.append(
                f'<option value="{int(bid)}"{sel}>{escape(bank["name"])}</option>'
            )
        acct = escape(config.get('account_number') or '')
        ifsc = escape(config.get('ifsc_code') or '')
        split_rows_html = []
        for row in config.get('splits') or []:
            rid = row.get('id')
            split_id_attr = str(int(rid)) if rid else ''
            payee = escape(row.get('payee_name') or '')
            pct = float(row.get('percent_share') or 0.0)
            amt = float(row.get('amount') or 0.0)
            row_bank = row.get('bank_id')
            row_opts = ['<option value="">Bank…</option>']
            for bank in config.get('banks') or []:
                bid = bank['id']
                sel = ' selected' if row_bank and int(row_bank) == int(bid) else ''
                row_opts.append(
                    f'<option value="{int(bid)}"{sel}>{escape(bank["name"])}</option>'
                )
            split_rows_html.append(
                '<tr class="bhu_pv_le_split_row" '
                f'data-split-id="{escape(split_id_attr)}" '
                f'data-landowner-id="{int(row.get("landowner_id") or 0)}">'
                f'<td class="bhu_pv_le_payee" title="{payee}">{payee}</td>'
                f'<td class="bhu_pv_le_pct"><input type="number" class="bhu_pv_le_input bhu_pv_le_pct_in" '
                f'min="0" max="100" step="0.01" value="{pct:.2f}"/></td>'
                f'<td class="bhu_pv_le_amt tabular-nums" data-role="amount">{sym}{amt:,.2f}</td>'
                f'<td class="bhu_pv_le_bank"><select class="bhu_pv_le_input bhu_pv_le_bank_sel">'
                f'{"".join(row_opts)}</select></td>'
                f'<td class="bhu_pv_le_acct"><input type="text" class="bhu_pv_le_input bhu_pv_le_acct_in" '
                f'value="{escape(row.get("account_number") or "")}" placeholder="Account"/></td>'
                f'<td class="bhu_pv_le_ifsc"><input type="text" class="bhu_pv_le_input bhu_pv_le_ifsc_in" '
                f'value="{escape(row.get("ifsc_code") or "")}" placeholder="IFSC"/></td>'
                '</tr>'
            )
        splits_body = ''.join(split_rows_html) or (
            '<tr><td colspan="6" class="text-muted text-center py-2">No payees — switch to Split by %</td></tr>'
        )
        clear_block = ''
        if config.get('has_account'):
            clear_block = (
                '<div class="bhu_pv_le_actions">'
                '<button type="button" class="btn btn-sm btn-outline-danger bhu_pv_le_clear_btn" '
                'title="Clear bank details so you can enter them again">'
                '<i class="fa fa-trash-o" aria-hidden="true"></i> Remove account</button>'
                '</div>'
            )
        return (
            f'<div class="bhu_pv_line_editor" data-line-id="{int(config.get("line_id") or 0)}">'
            f'<script type="application/json" class="bhu_pv_le_config">{cfg_json}</script>'
            '<div class="bhu_pv_le_head">'
            f'<div class="bhu_pv_le_khasra">Khasra <strong>{khasra}</strong></div>'
            f'<div class="bhu_pv_le_payable">{sym}<strong>{payable:,.2f}</strong></div>'
            '</div>'
            f'<div class="bhu_pv_le_owner" title="{owner}">{owner}</div>'
            f'{hint}'
            '<div class="bhu_pv_le_modes" role="group" aria-label="Payout type">'
            f'<button type="button" class="bhu_pv_le_mode{single_on}" data-mode="single">'
            'One account</button>'
            f'<button type="button" class="bhu_pv_le_mode{split_on}" data-mode="split"{split_disabled}>'
            'Split by %</button>'
            '</div>'
            f'<div class="bhu_pv_le_panel bhu_pv_le_single{single_panel_cls}" data-panel="single">'
            '<div class="bhu_pv_le_card">'
            '<div class="bhu_pv_le_card_title">Bank details</div>'
            '<label class="bhu_pv_le_lbl">Bank</label>'
            f'<select class="bhu_pv_le_input bhu_pv_le_single_bank" data-role="single-bank">'
            f'{"".join(bank_options)}</select>'
            '<div class="bhu_pv_le_row2">'
            '<div><label class="bhu_pv_le_lbl">Account</label>'
            f'<input type="text" class="bhu_pv_le_input bhu_pv_le_single_acct" value="{acct}" '
            'placeholder="Account number"/></div>'
            '<div><label class="bhu_pv_le_lbl">IFSC</label>'
            f'<input type="text" class="bhu_pv_le_input bhu_pv_le_single_ifsc" value="{ifsc}" '
            'placeholder="IFSC code"/></div>'
            '</div></div></div>'
            f'<div class="bhu_pv_le_panel bhu_pv_le_split{split_panel_cls}" data-panel="split">'
            '<div class="bhu_pv_le_card">'
            '<div class="bhu_pv_le_card_title">Split by %</div>'
            f'{status_block}'
            '<div class="bhu_pv_le_table_wrap"><table class="bhu_pv_le_table">'
            '<thead><tr>'
            '<th>Payee</th><th>%</th><th>Amount</th><th>Bank</th><th>Account</th><th>IFSC</th>'
            '</tr></thead>'
            f'<tbody data-role="split-body">{splits_body}</tbody>'
            f'<tfoot><tr><td colspan="2" class="text-end fw-bold">Total</td>'
            f'<td class="tabular-nums fw-bold" data-role="split-total">{sym}{payable:,.2f}</td>'
            '<td colspan="3"></td></tr></tfoot>'
            '</table></div></div></div>'
            f'{clear_block}'
            '</div>'
        )

    def clear_bank_account_details(self):
        """Reset bank / split on this khasra line (back to Pending account)."""
        self.ensure_one()
        if self.is_line_locked:
            raise UserError(_(
                'Khasra %s is locked — payment file already generated.'
            ) % (self.khasra_number or '-'))
        self.write({
            'payout_mode': 'single',
            'bank_id': False,
            'bank_name': False,
            'account_number': False,
            'ifsc_code': False,
            'split_ids': [(5, 0, 0)],
        })
        if self.voucher_id:
            self.voucher_id.invalidate_recordset(['lines_preview_html', 'account_ready_count'])

    @api.model
    def clear_line_account(self, line_id):
        """RPC: remove saved bank account from a khasra line."""
        line = self.browse(int(line_id)).exists()
        if not line:
            raise UserError(_('This khasra line no longer exists.'))
        line.clear_bank_account_details()
        voucher = line.voucher_id
        if voucher:
            return voucher._payment_voucher_ui_snapshot()
        return {}

    @api.model
    def apply_line_editor_payload(self, line_id, payload):
        """Persist HTML editor values (same rules as standard form)."""
        line = self.browse(int(line_id)).exists()
        if not line:
            raise UserError(_('This khasra line no longer exists.'))
        if line.is_line_locked:
            raise UserError(_(
                'Khasra %s is locked — payment file already generated.'
            ) % (line.khasra_number or '-'))
        payload = payload or {}
        payout_mode = payload.get('payout_mode') or 'single'
        if payout_mode == 'single':
            bank_id = payload.get('bank_id')
            line.write({
                'payout_mode': 'single',
                'bank_id': int(bank_id) if bank_id else False,
                'account_number': bhu_validate_account_number(
                    payload.get('account_number'),
                    _('khasra %s account') % (line.khasra_number or '-'),
                ),
                'ifsc_code': bhu_validate_ifsc_code(
                    payload.get('ifsc_code'),
                    _('khasra %s IFSC') % (line.khasra_number or '-'),
                ),
                'split_ids': [(5, 0, 0)],
            })
        else:
            splits_in = payload.get('splits') or []
            if len(splits_in) < 2:
                raise UserError(_(
                    'Khasra %(k)s: split mode needs at least two payee rows. '
                    'Close this window, open the khasra again, then save.'
                ) % {'k': line.khasra_number or '-'})
            split_cmds = [(5, 0, 0)]
            for row in splits_in:
                payee = (row.get('payee_name') or '').strip() or _('payee')
                vals = {
                    'split_landowner_id': int(row['landowner_id']) if row.get('landowner_id') else False,
                    'payee_name': payee,
                    'percent_share': float(row.get('percent_share') or 0.0),
                    'bank_id': int(row['bank_id']) if row.get('bank_id') else False,
                    'account_number': bhu_validate_account_number(
                        row.get('account_number'),
                        payee,
                    ),
                    'ifsc_code': bhu_validate_ifsc_code(
                        row.get('ifsc_code'),
                        payee,
                    ),
                }
                sid = row.get('id')
                if sid and int(sid):
                    split_cmds.append((1, int(sid), vals))
                else:
                    split_cmds.append((0, 0, vals))
            line.write({
                'payout_mode': 'split',
                'bank_id': False,
                'bank_name': False,
                'account_number': False,
                'ifsc_code': False,
                'split_ids': split_cmds,
            })
        line._validate_payout()
        voucher = line.voucher_id
        if voucher:
            return voucher._payment_voucher_ui_snapshot()
        return {}

    @api.model
    def line_editor_split_defaults(self, line_id):
        """Default payee rows when user switches to split in HTML editor."""
        line = self.browse(int(line_id)).exists()
        if not line:
            return []
        return line._get_line_editor_split_rows()

    def action_open_line_editor(self):
        """Open line popup — edit bank/split, or read-only details when locked."""
        self.ensure_one()
        locked = self.is_line_locked
        if not locked and not float(self.rr_col8_amount or 0.0) and self.voucher_id.award_id:
            self.voucher_id._sync_line_col_amounts_from_rr(self)
        if not locked and self.payout_mode == 'split' and not self.split_ids:
            self.split_ids = self._prepare_default_split_commands()
        view = self.env.ref('bhukhadan_core.view_bhu_payment_voucher_line_form')
        title = (
            _('Khasra %s — details') % (self.khasra_number or '-')
            if locked
            else _('Khasra %s — account / split') % (self.khasra_number or '-')
        )
        action = {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'bhu.payment.voucher.line',
            'view_mode': 'form',
            'view_id': view.id,
            'views': [(view.id, 'form')],
            'res_id': self.id,
            'target': 'new',
        }
        if locked:
            action['flags'] = {'mode': 'readonly'}
        return action

    @api.onchange('bank_id')
    def _onchange_bank_id_voucher_line(self):
        if self.bank_id:
            self.bank_name = self.bank_id.name

    @api.depends('split_ids.percent_share', 'payout_mode', 'determined_total')
    def _compute_split_status_hint(self):
        for line in self:
            if line.payout_mode != 'split':
                line.split_status_hint = ''
                continue
            total_p = sum(float(x.percent_share or 0.0) for x in line.split_ids)
            if not line.split_ids:
                line.split_status_hint = _('Add payee rows — percentages must total 100.')
            elif abs(total_p - 100.0) > 0.02:
                line.split_status_hint = _('Percent total is %s (must be 100).') % round(total_p, 2)
            else:
                amt = sum(float(x.amount or 0.0) for x in line.split_ids)
                line.split_status_hint = _('OK — 100 percent · ₹ %s') % round(amt, 2)

    @api.depends(
        'payout_mode',
        'khasra_number',
        'determined_total',
        'bank_id',
        'bank_name',
        'split_ids',
        'split_ids.percent_share',
        'split_ids.amount',
        'split_ids.bank_id',
        'split_ids.bank_name',
    )
    def _compute_payout_summary(self):
        """Short payout label for the lines table (no bank names — saves column width)."""
        for line in self:
            if line.payout_mode == 'split':
                n = len(line.split_ids)
                if not n:
                    line.payout_summary = _('Split % — add payees')
                    continue
                bank_names = line._get_split_bank_names()
                if bank_names:
                    nb = len(bank_names)
                    if nb == 1:
                        line.payout_summary = _('%s payees · 1 bank') % n
                    else:
                        line.payout_summary = _('%s payees · %s banks') % (n, nb)
                else:
                    line.payout_summary = _('%s payees · percent split') % n
            elif (line.bank_id or (line.bank_name or '').strip()):
                line.payout_summary = _('One account')
            else:
                line.payout_summary = _('Add bank details')

    def _get_split_bank_names(self):
        """Unique bank names from split payee rows (multi-bank splits)."""
        self.ensure_one()
        names = []
        seen = set()
        for sp in self.split_ids:
            name = (sp.bank_id.name if sp.bank_id else (sp.bank_name or '')).strip()
            if not name:
                continue
            key = name.lower()
            if key not in seen:
                seen.add(key)
                names.append(name)
        return names

    @api.depends(
        'khasra_number',
        'owner_display',
        'voucher_id.award_id',
        'voucher_id.award_id.project_id',
        'voucher_id.award_id.village_id',
    )
    def _compute_owner_count(self):
        for line in self:
            line.owner_count = line._get_khasra_owner_count()

    @api.depends(
        'khasra_number',
        'voucher_id.award_id',
        'voucher_id.award_id.project_id',
        'voucher_id.award_id.village_id',
    )
    def _compute_allow_split(self):
        for line in self:
            line.allow_split = line._get_khasra_owner_count() > 1

    def _get_khasra_surveys(self):
        self.ensure_one()
        award = self.voucher_id.award_id
        if not award or not (self.khasra_number or '').strip():
            return self.env['bhu.survey']
        return self.env['bhu.survey'].search([
            ('project_id', '=', award.project_id.id),
            ('village_id', '=', award.village_id.id),
            ('khasra_number', '=', self.khasra_number.strip()),
        ])

    def _get_khasra_landowners(self):
        """Landowners linked to this khasra on project surveys."""
        self.ensure_one()
        owner_ids = []
        seen = set()
        for owner in self._get_khasra_surveys().mapped('landowner_ids'):
            if owner.id not in seen:
                seen.add(owner.id)
                owner_ids.append(owner.id)
        return self.env['bhu.landowner'].browse(owner_ids)

    def _format_payee_owner_block(self, index, name, father_name='', spouse_name='', address=''):
        """One numbered payee line (name, relation, address) for HTML tables."""
        name = (name or '').strip()
        if not name:
            return ''
        block = f'{index}. {name}'
        father = (father_name or '').strip()
        spouse = (spouse_name or '').strip()
        if father:
            block += f' पिता {father}'
        elif spouse:
            block += f' पति {spouse}'
        addr = (address or '').strip()
        if addr:
            block += f' निवासी: {addr}'
        return block

    def _get_payee_display_lines(self):
        """All landowners for this khasra — one text block per owner."""
        self.ensure_one()
        owners = self._get_khasra_landowners()
        if owners:
            lines = []
            for idx, owner in enumerate(owners, 1):
                block = self._format_payee_owner_block(
                    idx,
                    owner.name,
                    owner.father_name,
                    owner.spouse_name,
                    owner.owner_address,
                )
                if block:
                    lines.append(block)
            if lines:
                return lines
        text = (self.owner_display or '').strip()
        if not text:
            return []
        parts = [p.strip() for p in re.split(r'(?=\d+\.\s)', text) if p.strip()]
        if len(parts) > 1:
            return parts
        if '\n' in text:
            return [ln.strip() for ln in text.splitlines() if ln.strip()]
        return [text]

    def _get_payee_display_plain(self):
        return '\n'.join(self._get_payee_display_lines())

    def _get_payee_display_html(self):
        lines = self._get_payee_display_lines()
        if not lines:
            return Markup('')
        return Markup('<br/>'.join(escape(line) for line in lines))

    def _parse_owner_names_from_display(self):
        """Extract individual payee names from the combined owner banner text."""
        self.ensure_one()
        text = (self.owner_display or '').strip()
        if not text:
            return []
        names = []
        for part in text.split(','):
            part = part.strip()
            if not part:
                continue
            lower = part.lower()
            if lower.startswith('पिता ') or lower.startswith('pita '):
                continue
            if lower.startswith('पति ') or lower.startswith('pati '):
                continue
            if lower.startswith('जाति') or lower.startswith('jati'):
                continue
            names.append(part)
        return names

    def _split_percent_shares(self, count):
        """Return *count* percentage shares that total 100."""
        if count <= 0:
            return []
        if count == 1:
            return [100.0]
        base = round(100.0 / count, 2)
        shares = [base] * count
        shares[-1] = round(100.0 - sum(shares[:-1]), 2)
        return shares

    def _prepare_split_line_vals(self, owner=None, payee_name='', percent_share=0.0):
        vals = {
            'percent_share': percent_share,
            'payee_name': payee_name or '',
        }
        if owner:
            vals['split_landowner_id'] = owner.id
            vals['payee_name'] = owner.name or payee_name or ''
            if owner.bank_name:
                vals['bank_id'] = bhu_match_res_bank(self.env, owner.bank_name) or False
                vals['bank_name'] = owner.bank_name or ''
                vals['bank_branch'] = owner.bank_branch or ''
                vals['account_number'] = owner.account_number or ''
                vals['ifsc_code'] = owner.ifsc_code or ''
            if owner.owner_address:
                vals['beneficiary_address'] = owner.owner_address
        return vals

    def _prepare_default_split_commands(self):
        """One split row per khasra landowner (equal %), else parse owner banner names."""
        self.ensure_one()
        owners = self._get_khasra_landowners()
        if owners:
            shares = self._split_percent_shares(len(owners))
            return [
                (0, 0, self._prepare_split_line_vals(owner=owner, percent_share=pct))
                for owner, pct in zip(owners, shares)
            ]

        names = self._parse_owner_names_from_display()
        if len(names) >= 2:
            shares = self._split_percent_shares(len(names))
            return [
                (0, 0, self._prepare_split_line_vals(payee_name=name, percent_share=pct))
                for name, pct in zip(names, shares)
            ]

        return [
            (0, 0, {'percent_share': 50.0}),
            (0, 0, {'percent_share': 50.0}),
        ]

    def _get_khasra_owner_count(self):
        self.ensure_one()
        count = len(self._get_khasra_landowners())
        if count > 1:
            return count
        parsed = len(self._parse_owner_names_from_display())
        return parsed if parsed > 1 else count

    @api.depends('khasra_number', 'voucher_id.award_id', 'voucher_id.award_id.project_id', 'voucher_id.award_id.village_id')
    def _compute_khasra_landowner_ids(self):
        for line in self:
            line.khasra_landowner_ids = line._get_khasra_landowners()

    @api.onchange('payout_mode')
    def _onchange_payout_mode(self):
        if self.is_line_locked:
            return
        if self.payout_mode == 'single':
            self.split_ids = [(5, 0, 0)]
        elif self.payout_mode == 'split' and not self.split_ids:
            self.split_ids = self._prepare_default_split_commands()

    @api.constrains('payout_mode', 'split_ids')
    def _check_payout_mode_vs_splits(self):
        for line in self:
            if line.payout_mode == 'split':
                if len(line.split_ids) < 2:
                    raise ValidationError(_(
                        'Khasra %(k)s: split mode needs at least two payee rows.'
                    ) % {'k': line.khasra_number or '-'})
            else:
                if line.split_ids:
                    raise ValidationError(_(
                        'Switch to split mode or remove split rows for khasra %s.'
                    ) % (line.khasra_number or '-'))

    @api.constrains('split_ids', 'determined_total', 'payout_mode')
    def _check_split_percent_total(self):
        for line in self:
            if line.payout_mode != 'split' or not line.split_ids:
                continue
            total_p = sum(float(x.percent_share or 0.0) for x in line.split_ids)
            if abs(total_p - 100.0) > 0.02:
                raise ValidationError(_(
                    'Khasra %(k)s: split percentages must total 100%% (currently %(p)s%%).'
                ) % {'k': line.khasra_number or '-', 'p': round(total_p, 2)})
            total_a = sum(float(x.amount or 0.0) for x in line.split_ids)
            if abs(total_a - float(line.determined_total or 0.0)) > 0.12:
                raise ValidationError(_(
                    'Khasra %(k)s: split amounts (₹%(a)s) must match determined total (₹%(d)s).'
                ) % {
                    'k': line.khasra_number or '-',
                    'a': round(total_a, 2),
                    'd': round(float(line.determined_total or 0.0), 2),
                })

    def _validate_payout(self):
        self.ensure_one()
        if self.payout_mode == 'split':
            for sp in self.split_ids:
                sp._validate_bank_required()
                if not sp.split_landowner_id and not (sp.payee_name or '').strip():
                    raise ValidationError(_(
                        'Khasra %(k)s: each payee needs a name or a linked landowner.'
                    ) % {'k': self.khasra_number or '-'})
            return
        if not self.bank_id and not (self.bank_name or '').strip():
            raise ValidationError(_(
                'Please select a bank for khasra %s (required for payment file).'
            ) % (self.khasra_number or '-'))
        ctx = _('khasra %s') % (self.khasra_number or '-')
        bhu_validate_account_number(self.account_number, ctx)
        bhu_validate_ifsc_code(self.ifsc_code, ctx)


class BhuPaymentVoucherLineSplit(models.Model):
    _name = 'bhu.payment.voucher.line.split'
    _description = 'R&R Payment Voucher Line Split'
    _order = 'id'

    voucher_line_id = fields.Many2one(
        'bhu.payment.voucher.line',
        string='Voucher Line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    percent_share = fields.Float(
        string='Share % / हिस्सा %',
        digits=(5, 2),
        default=0.0,
        help='Percent of this khasra line’s determined compensation (all payee rows must total 100%).',
    )
    amount = fields.Monetary(
        string='Amount (computed) / राशि',
        compute='_compute_amount_from_percent',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='voucher_line_id.currency_id',
        store=True,
        readonly=True,
    )
    split_landowner_id = fields.Many2one(
        'bhu.landowner',
        string='Landowner / भूस्वामी',
        ondelete='set null',
        help='Optional: link to master record if payee is a registered landowner.',
    )
    payee_name = fields.Char(
        string='Payee name / लाभार्थी का नाम',
        help='Shown on bank file when no landowner is linked.',
    )
    payee_display_name = fields.Char(
        string='Payee (resolved)',
        compute='_compute_payee_display_name',
    )
    beneficiary_address = fields.Text(string='Address / पता')
    bank_id = fields.Many2one(
        'res.bank',
        string='Bank',
        domain="[('bhu_category', '!=', False)]",
    )
    bank_name = fields.Char(
        string='Bank name / बैंक',
        help='Synced from bank selection; kept for export.',
    )
    bank_branch = fields.Char(
        string='Branch / शाखा',
        help='Optional on split rows when IFSC is provided.',
    )
    account_number = fields.Char(string='Account number / खाता क्रमांक')
    ifsc_code = fields.Char(string='IFSC / आईएफएससी')
    note = fields.Char(string='Note')

    @api.model_create_multi
    def create(self, vals_list):
        out = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('voucher_line_id'):
                line = self.env['bhu.payment.voucher.line'].browse(vals['voucher_line_id'])
                if line.is_line_locked:
                    raise UserError(_(
                        'Cannot add split rows — khasra %s is locked.'
                    ) % (line.khasra_number or '-'))
            if vals.get('bank_id'):
                bank = self.env['res.bank'].browse(vals['bank_id'])
                if bank.exists():
                    vals['bank_name'] = bank.name
            out.append(vals)
        return super().create(out)

    def write(self, vals):
        locked = self.mapped('voucher_line_id').filtered('is_line_locked')
        if locked and vals:
            raise UserError(_(
                'Cannot edit split rows — khasra %s is locked after payment file generation.'
            ) % ', '.join(locked.mapped('khasra_number')))
        vals = dict(vals)
        if vals.get('bank_id'):
            bank = self.env['res.bank'].browse(vals['bank_id'])
            if bank.exists():
                vals['bank_name'] = bank.name
        return super().write(vals)

    @api.onchange('bank_id')
    def _onchange_bank_id_split(self):
        if self.bank_id:
            self.bank_name = self.bank_id.name

    @api.onchange('split_landowner_id')
    def _onchange_split_landowner_id(self):
        if self.split_landowner_id:
            owner = self.split_landowner_id
            self.payee_name = owner.name or ''
            if owner.bank_name:
                self.bank_id = bhu_match_res_bank(self.env, owner.bank_name) or False
                self.bank_name = owner.bank_name or ''
                self.bank_branch = owner.bank_branch or ''
                self.account_number = owner.account_number or ''
                self.ifsc_code = owner.ifsc_code or ''
            if owner.owner_address:
                self.beneficiary_address = owner.owner_address

    @api.depends('split_landowner_id', 'payee_name')
    def _compute_payee_display_name(self):
        for rec in self:
            if rec.split_landowner_id:
                rec.payee_display_name = rec.split_landowner_id.name or ''
            else:
                rec.payee_display_name = (rec.payee_name or '').strip()

    @api.depends('percent_share', 'voucher_line_id.determined_total')
    def _compute_amount_from_percent(self):
        for rec in self:
            base = float(rec.voucher_line_id.determined_total or 0.0)
            rec.amount = round(base * float(rec.percent_share or 0.0) / 100.0, 2)

    @api.constrains('percent_share', 'voucher_line_id')
    def _check_percent_share_positive(self):
        for rec in self:
            if rec.voucher_line_id and rec.voucher_line_id.payout_mode == 'split':
                if float(rec.percent_share or 0.0) <= 0:
                    raise ValidationError(_(
                        'Each payee row must have a share percent greater than zero.'
                    ))

    def _validate_bank_required(self):
        self.ensure_one()
        if not self.bank_id and not (self.bank_name or '').strip():
            raise ValidationError(_('Each payee row must have a bank selected.'))
        ctx = (self.payee_name or self.payee_display_name or _('payee')).strip()
        bhu_validate_account_number(self.account_number, ctx)
        bhu_validate_ifsc_code(self.ifsc_code, ctx)


class Section23AwardPaymentVoucher(models.Model):
    _inherit = 'bhu.section23.award'

    payment_voucher_ids = fields.One2many(
        'bhu.payment.voucher',
        'award_id',
        string='Draft Payment Vouchers',
        readonly=True,
    )
    payment_voucher_count = fields.Integer(
        compute='_compute_payment_voucher_count',
        string='Payment Vouchers',
    )

    @api.depends('payment_voucher_ids')
    def _compute_payment_voucher_count(self):
        for rec in self:
            rec.payment_voucher_count = len(rec.payment_voucher_ids)

    def _get_rr_khasra_payable_map(self):
        """Map khasra → col 8, col 9, and payable (8+9) from R&R award."""
        self.ensure_one()
        rr_groups = self.get_rr_award_data() or []
        owner_by_khasra = {}
        for grp in self.get_consolidated_award_data() or []:
            owner_text = (grp.get('owner_details') or '').strip()
            for kline in grp.get('khasra_lines') or []:
                k = (kline.get('khasra') or '').strip()
                if k and owner_text:
                    owner_by_khasra[k] = owner_text

        khasra_entries = {}
        for rr_group in rr_groups:
            owner_heading = (rr_group.get('owner_text') or '').strip()
            rr_lines = rr_group.get('lines') or []
            group_col8 = float(rr_group.get('owner_determined_compensation', 0.0) or 0.0)
            group_col9 = float(rr_group.get('owner_final_compensation', 0.0) or 0.0)
            for rr_line in rr_lines:
                khasra = (rr_line.get('khasra') or '').strip()
                if not khasra:
                    continue
                if len(rr_lines) == 1:
                    col8, col9 = group_col8, group_col9
                else:
                    col8 = (
                        float(rr_line.get('land_compensation', 0.0) or 0.0) +
                        float(rr_line.get('asset_compensation', 0.0) or 0.0) +
                        float(rr_line.get('tree_compensation', 0.0) or 0.0)
                    )
                    col9 = group_col9 * (col8 / group_col8) if group_col8 else 0.0
                payable = round(col8 + col9, 2)
                prev = khasra_entries.get(khasra)
                owner_text = owner_by_khasra.get(khasra) or owner_heading
                if prev:
                    khasra_entries[khasra] = {
                        'owner_display': prev['owner_display'] or owner_text,
                        'rr_col8_amount': round(prev['rr_col8_amount'] + col8, 2),
                        'rr_col9_amount': round(prev['rr_col9_amount'] + col9, 2),
                        'determined_total': round(prev['determined_total'] + payable, 2),
                    }
                else:
                    khasra_entries[khasra] = {
                        'owner_display': owner_text,
                        'rr_col8_amount': round(col8, 2),
                        'rr_col9_amount': round(col9, 2),
                        'determined_total': payable,
                    }
        return khasra_entries

    def _prepare_payment_voucher_line_commands(self):
        """Build voucher lines from R&R columns 8 + 9 (one row per khasra)."""
        self.ensure_one()
        khasra_entries = self._get_rr_khasra_payable_map()
        if not khasra_entries:
            return []

        land_by_khasra = {}
        for row in self.get_land_compensation_data() or []:
            khasra = (row.get('khasra') or '').strip()
            if not khasra:
                continue
            area = float(row.get('acquired_area', 0.0) or 0.0)
            if khasra not in land_by_khasra:
                land_by_khasra[khasra] = dict(row)
            else:
                land_by_khasra[khasra]['acquired_area'] = (
                    float(land_by_khasra[khasra].get('acquired_area', 0.0) or 0.0) + area
                )

        cmds = []
        serial = 1
        for khasra in sorted(khasra_entries.keys()):
            bucket = khasra_entries[khasra]
            land_row = land_by_khasra.get(khasra) or {}
            lo = land_row.get('landowner')
            lo_id = lo.id if lo else False
            addr = land_row.get('address') or ''
            if lo:
                addr = addr or (lo.owner_address or '')
            bank_name = lo.bank_name if lo else ''
            bank_branch = lo.bank_branch if lo else ''
            account_number = lo.account_number if lo else ''
            ifsc_code = lo.ifsc_code if lo else ''
            bank_id = bhu_match_res_bank(self.env, bank_name)
            cmds.append((0, 0, {
                'rr_serial': serial,
                'owner_display': bucket['owner_display'],
                'landowner_id': lo_id,
                'khasra_number': khasra,
                'acquired_rakba': float(land_row.get('acquired_area', 0.0) or 0.0),
                'rr_col8_amount': bucket['rr_col8_amount'],
                'rr_col9_amount': bucket['rr_col9_amount'],
                'determined_total': bucket['determined_total'],
                'beneficiary_address': addr,
                'bank_id': bank_id or False,
                'bank_name': bank_name or '',
                'bank_branch': bank_branch or '',
                'account_number': account_number or '',
                'ifsc_code': ifsc_code or '',
            }))
            serial += 1
        return cmds

    def action_create_draft_rr_payment_voucher(self):
        """Open a new draft payment voucher prefilled like the R&R award table."""
        self.ensure_one()
        if not self.rr_generated:
            raise ValidationError(_('Generate the R&R award first, then create a draft payment voucher.'))
        existing = self.env['bhu.payment.voucher'].search([
            ('award_id', '=', self.id),
        ], order='create_date desc, id desc', limit=1)
        if existing:
            existing._merge_duplicate_voucher_lines()
            return {
                'type': 'ir.actions.act_window',
                'name': _('Payment Voucher'),
                'res_model': 'bhu.payment.voucher',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'res_id': existing.id,
                'target': 'current',
            }
        cmds = self._prepare_payment_voucher_line_commands()
        if not cmds:
            raise ValidationError(_('No R&R compensation lines found for this award.'))
        voucher = self.env['bhu.payment.voucher'].create({
            'award_id': self.id,
            'line_ids': cmds,
        })
        voucher._merge_duplicate_voucher_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment Voucher'),
            'res_model': 'bhu.payment.voucher',
            'view_mode': 'form',
            'res_id': voucher.id,
            'target': 'current',
        }

    def action_open_payment_vouchers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment Vouchers'),
            'res_model': 'bhu.payment.voucher',
            'view_mode': 'list,form',
            'domain': [('award_id', '=', self.id)],
            'context': {'default_award_id': self.id},
        }
