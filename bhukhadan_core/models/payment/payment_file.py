# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
import logging
import re
import uuid
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False
    _logger.warning("xlsxwriter library not found. Excel export will not be available.")


class PaymentFile(models.Model):
    _name = 'bhu.payment.file'
    _description = 'Payment File / भुगतान फ़ाइल'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Payment File Number / भुगतान फ़ाइल संख्या', required=True, default='New', tracking=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True, tracking=True)
    award_id = fields.Many2one(
        'bhu.section23.award',
        string='Section 23 Award / धारा 23 अवार्ड',
        required=True,
        tracking=True,
        ondelete='cascade',
    )
    
    award_ref = fields.Char(string='Award Number / अवार्ड क्र.', related='award_id.name', store=True, readonly=True)
    
    # Case Details - removed as fields no longer exist in award model
    
    # District, Tehsil
    district_id = fields.Many2one('bhu.district', string='District / जिला', related='village_id.district_id', store=True, readonly=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील', related='village_id.tehsil_id', store=True, readonly=True)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', related='project_id.department_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.INR'))
    
    debit_account_number = fields.Char(string='Debit Account Number / डेबिट खाता संख्या', tracking=True)
    
    _sql_constraints = [
        ('unique_project_village_payment', 'unique(project_id, village_id)', 
         'A payment file already exists for this village and project!')
    ]
    
    # Payment Lines
    payment_line_ids = fields.One2many('bhu.payment.file.line', 'payment_file_id', string='Payment Lines / भुगतान पंक्तियां')
    
    # Totals
    total_compensation = fields.Float(string='Total Compensation / कुल मुआवजा', compute='_compute_totals', store=True, digits=(16, 2))
    total_net_payable = fields.Float(string='Total Net Payable / कुल शुद्ध देय', compute='_compute_totals', store=True, digits=(16, 2))
    total_net_payable_text = fields.Char(string='Total Net Payable (Text) / कुल शुद्ध देय (पाठ)', compute='_compute_totals', store=True)
    
    # File Generation
    generated_file = fields.Binary(string='Generated File / जेनरेट की गई फ़ाइल')
    generated_file_filename = fields.Char(string='File Name / फ़ाइल नाम')
    generation_date = fields.Date(string='Generation Date / जेनरेशन दिनांक', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft / प्रारूप'),
        ('generated', 'Generated / जेनरेट किया गया'),
    ], string='Status / स्थिति', default='draft', tracking=True)
    
    def amount_to_text(self, amount):
        """Convert amount to text (Indian system)"""
        try:
            # Try to use num2words for Indian format if available
            from num2words import num2words
            params = {'lang': 'en_IN'} 
            text = num2words(amount, **params).title()
            # Clean up currency format
            if 'Point' in text:
                text = text.replace('Point', 'Rupees And') + ' Paisa Only'
            else:
                 text += " Rupees Only"
            return text
        except ImportError:
            # Fallback to currency provider or standard method
            try:
                if self.currency_id:
                     # Odoo's default amount_to_text often uses standard international scale (Billions), 
                     # we might want to override or implement custom if num2words is missing
                    return self.currency_id.amount_to_text(amount)
                return str(amount)
            except:
                return str(amount)

    @api.model
    def default_get(self, fields_list):
        defaults = super(PaymentFile, self).default_get(fields_list)
        
        # Auto-populate from context if available
        if 'village_id' in defaults and not defaults.get('award_id'):
            village_id = defaults['village_id']
            # Look for active section 23 awards for this village
            # Prioritize submitted/approved awards
            awards = self.env['bhu.section23.award'].search([
                ('village_id', '=', village_id),
                ('state', 'in', ['submitted', 'approved'])
            ], order='state desc, create_date desc', limit=1)
            
            if awards:
                defaults['award_id'] = awards.id
                # Explicitly set project_id so it's not missing
                defaults['project_id'] = awards.project_id.id
                    
        return defaults

    @api.depends('payment_line_ids.compensation_amount', 'payment_line_ids.net_payable_amount')
    def _compute_totals(self):
        """Compute totals from payment lines"""
        for record in self:
            record.total_compensation = sum(record.payment_line_ids.mapped('compensation_amount'))
            record.total_net_payable = sum(record.payment_line_ids.mapped('net_payable_amount'))
            record.total_net_payable_text = record.amount_to_text(record.total_net_payable)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create payment file (internal / legacy sync only — use R&R payment voucher from UI)."""
        if not self.env.context.get('bhu_allow_payment_file_create'):
            raise UserError(_(
                'Do not create payment files here.\n\n'
                'Open the Section 23 award → generate R&R → Draft Payment Voucher → '
                'add bank details → Generate Payment file.\n\n'
                'Or use Payment File → Create on the dashboard after creating the voucher from the award.'
            ))
        # Just ensure name defaults to New if not set
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = 'New'
                
        records = super().create(vals_list)
        # Auto-populate payment lines from award compensation lines
        skip_populate = self.env.context.get('skip_payment_line_populate')
        for record in records:
            # Set default debit account from settings
            if not record.debit_account_number:
                settings = self.env['bhuarjan.settings.master'].get_settings_master()
                record.debit_account_number = settings.debit_account_number

            if skip_populate:
                continue
            if record.award_id and record.village_id:
                record._populate_payment_lines()
        return records
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village and award when project changes"""
        self.village_id = False
        self.award_id = False
        if self.project_id:
            return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        return {'domain': {'village_id': []}}
    
    @api.onchange('village_id')
    def _onchange_village_id(self):
        """Auto-populate award_id if village is selected"""
        if self.village_id:
            # Look for active section 23 awards for this village
            # We prioritize awards in 'submitted' or 'approved' state if possible
            awards = self.env['bhu.section23.award'].search([
                ('village_id', '=', self.village_id.id),
                ('state', 'in', ['submitted', 'approved'])
            ], order='state desc, create_date desc')
            if awards:
                self.award_id = awards[0].id
            
            # Also set project_id if not set and found in award
            if not self.project_id and self.award_id:
                self.project_id = self.award_id.project_id.id
            return {'domain': {'award_id': [('id', 'in', awards.ids)]}}
        return {'domain': {'award_id': []}}
    
    @api.onchange('award_id', 'village_id')
    def _onchange_award_village(self):
        """Auto-populate payment lines when award or village changes"""
        if self.award_id:
            # Keep file context aligned with selected award
            if not self.project_id:
                self.project_id = self.award_id.project_id.id
            if not self.village_id:
                self.village_id = self.award_id.village_id.id
        if self.award_id and self.village_id:
            self._populate_payment_lines()
    
    def _populate_payment_lines(self):
        """Populate payment lines using simulator-equivalent grouped logic.

        One row per beneficiary group, total based on paid_compensation
        (fallback to total_compensation), khasras combined and sorted.
        """
        self.ensure_one()
        if not self.award_id or not self.village_id:
            return

        def _khasra_sort_key(khasra):
            text = (khasra or '').strip()
            if not text:
                return (1, 10**12, 10**12, '')
            parts = text.split('/', 1)
            main = int(parts[0]) if parts[0].isdigit() else 10**12
            sub = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10**12
            return (0, main, sub, text)

        grouped_data = self.award_id.get_land_compensation_grouped_data()

        # Clear existing lines
        self.payment_line_ids = [(5, 0, 0)]

        # Create payment lines
        line_vals = []
        serial = 1

        for group in grouped_data:
            lines = group.get('lines', [])
            landowner = group.get('landowner')
            if not landowner:
                owners = [line.get('landowner') for line in lines if line.get('landowner')]
                landowner = owners[0] if owners else False
            if not landowner:
                blocks = group.get('owner_blocks') or []
                if blocks and blocks[0].get('id'):
                    landowner = self.env['bhu.landowner'].browse(blocks[0]['id'])
            if not landowner:
                continue

            unique_khasras = sorted(
                {(line.get('khasra') or '').strip() for line in lines if line.get('khasra')},
                key=_khasra_sort_key,
            )
            group_paid = float(group.get('paid_compensation') or 0.0)
            group_total = float(group.get('total_compensation') or 0.0)
            line_paid_sum = sum(float((line.get('paid_compensation') or 0.0)) for line in lines)
            line_total_sum = sum(float((line.get('total_compensation') or 0.0)) for line in lines)
            amount = group_paid or group_total or line_paid_sum or line_total_sum or 0.0

            line_vals.append((0, 0, {
                'serial_number': serial,
                'award_serial_number': serial,
                'khasra_number': ', '.join(unique_khasras),
                'landowner_id': landowner.id,
                'bank_name': landowner.bank_name or '',
                'bank_branch': landowner.bank_branch or '',
                'account_number': landowner.account_number or '',
                'ifsc_code': landowner.ifsc_code or '',
                'compensation_amount': amount,
                'net_payable_amount': amount,
                'remark': '',
            }))
            serial += 1

        if line_vals:
            self.payment_line_ids = line_vals
    
    def action_generate_file(self):
        """Generate payment file (Excel/Annexure)"""
        self.ensure_one()
        
        # Generate Sequence Number if not already generated
        if self.name == 'New' or not self.name or self.name == 'Draft':
            sequence_number = False
            if self.project_id:
                sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                    'payment_file', self.project_id.id, village_id=self.village_id.id
                )
            
            if sequence_number:
                self.name = sequence_number
            else:
                self.name = self.env['ir.sequence'].next_by_code('bhu.payment.file') or 'New'

        if not self.payment_line_ids:
            self._populate_payment_lines()
            
        if not self.payment_line_ids:
            raise ValidationError(_('No compensation data found for this village and project in the selected Award.'))
        
        # Check library after sequence generation, so we don't fail before assigning name if library is missing (though library check is important)
        if not HAS_XLSXWRITER:
            raise ValidationError(_('xlsxwriter library is required for Excel export. Please install it: pip install xlsxwriter'))
        
        # Generate Excel file
        excel_file = self._generate_excel_file()
        
        # Save to record
        filename = f'Payment_File_{self.name}_{self.village_id.name or "Unknown"}.xlsx'
        self.write({
            'generated_file': base64.b64encode(excel_file),
            'generated_file_filename': filename,
            'state': 'generated',
            'generation_date': fields.Date.today()
        })
        
        # Create attachment for download
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(excel_file),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'bhu.payment.file',
            'res_id': self.id,
        })
        
        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_download_generated_file(self):
        """Download already generated payment file from form."""
        self.ensure_one()
        if not self.generated_file:
            raise UserError(_('Payment file is not generated yet. Please generate it first.'))

        return {
            'type': 'ir.actions.act_url',
            'url': (
                '/web/content/?model=bhu.payment.file'
                f'&id={self.id}'
                '&field=generated_file'
                '&filename_field=generated_file_filename'
                '&download=true'
            ),
            'target': 'self',
        }

    def action_open_bank_reconciliation(self):
        """Open one reconciliation screen for complete payment file."""
        self.ensure_one()
        # Always open a draft upload record so Process button is visible.
        reconciliation = self.env['bhu.payment.reconciliation.bank'].search(
            [
                ('payment_file_id', '=', self.id),
                ('state', '=', 'draft'),
            ],
            order='id desc',
            limit=1,
        )
        if not reconciliation:
            reconciliation = self.env['bhu.payment.reconciliation.bank'].create({
                'payment_file_id': self.id,
            })

        popup_view = self.env.ref('bhukhadan_core.view_payment_reconciliation_bank_popup_form', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Upload Bank Reconciliation'),
            'res_model': 'bhu.payment.reconciliation.bank',
            'view_mode': 'form',
            'views': [(popup_view.id, 'form')] if popup_view else [(False, 'form')],
            'res_id': reconciliation.id,
            'target': 'new',
        }

    def _map_sync_status(self, status_text):
        status = (status_text or '').strip().lower()
        if status in ('executed', 'settled', 'success', 'successful', 'paid', 'completed'):
            return 'settled'
        if status in ('failed', 'failure', 'error', 'rejected'):
            return 'failed'
        return 'pending'

    def _prepare_online_sync_results(self, lines, response_body):
        """Build line-wise sync results from API payload."""
        parsed = {}
        candidate_lists = []
        if isinstance(response_body, dict):
            for key in ('transactions', 'results', 'data', 'items', 'lines'):
                value = response_body.get(key)
                if isinstance(value, list):
                    candidate_lists.append(value)
            if not candidate_lists and isinstance(response_body.get('result'), list):
                candidate_lists.append(response_body.get('result'))
        elif isinstance(response_body, list):
            candidate_lists.append(response_body)

        matched = {}
        for entries in candidate_lists:
            for item in entries:
                if not isinstance(item, dict):
                    continue
                line_id = item.get('payment_line_id') or item.get('line_id') or item.get('id')
                if isinstance(line_id, str) and line_id.isdigit():
                    line_id = int(line_id)
                if not isinstance(line_id, int):
                    continue
                matched[line_id] = item

        for line in lines:
            item = matched.get(line.id, {})
            mapped_status = self._map_sync_status(
                item.get('status') or item.get('event_status') or item.get('state')
            )
            parsed[line.id] = {
                'status': mapped_status,
                'utr_number': (
                    item.get('utr_number') or item.get('utr') or item.get('rrn') or
                    item.get('transaction_id') or ''
                ),
                'reason': (
                    item.get('error') or item.get('reason_code') or item.get('reason') or
                    item.get('message') or item.get('event_status') or ''
                ),
                'raw': item,
            }
        return parsed

    def action_online_sync(self):
        """Call bank API and sync pending/failed payment lines."""
        self.ensure_one()

        sync_lines = self.payment_line_ids.filtered(
            lambda l: l.payment_status in ('pending', 'failed')
        )
        if not sync_lines:
            raise UserError(_('No pending or failed payment lines available for online sync.'))

        params = self.env['ir.config_parameter'].sudo()
        api_url = params.get_param('bhukhadan_core.indusind_api_url')
        bearer_token = params.get_param('bhukhadan_core.indusind_bearer_token')
        api_key = params.get_param('bhukhadan_core.indusind_api_key')
        client_id = params.get_param('bhukhadan_core.indusind_client_id')
        if not api_url:
            raise ValidationError(_(
                'IndusInd API is not configured. Please set `bhukhadan_core.indusind_api_url` in System Parameters.'
            ))

        try:
            import requests
        except ImportError:
            raise ValidationError(_("Python library 'requests' is required for online sync."))

        payload_transactions = []
        for line in sync_lines:
            payload_transactions.append({
                'payment_line_id': line.id,
                'external_ref_no': f"{self.name}_{uuid.uuid4().hex.upper()}",
                'beneficiary_name': line._get_beneficiary_display_name(),
                'account_number': line.account_number or '',
                'ifsc_code': line.ifsc_code or '',
                'amount': round(float(line.net_payable_amount or line.compensation_amount or 0.0), 2),
                'khasra': line.khasra_number or '',
            })

        headers = {'Content-Type': 'application/json'}
        if bearer_token:
            headers['Authorization'] = f'Bearer {bearer_token}'
        if api_key:
            headers['x-api-key'] = api_key
        if client_id:
            headers['x-client-id'] = client_id

        payload = {
            'reference_no': f"PFSYNC-{self.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            'payment_file_no': self.name or '',
            'project': self.project_id.name or '',
            'village': self.village_id.name or '',
            'transactions': payload_transactions,
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=45)
        except Exception as exc:
            raise ValidationError(_('Failed to connect to bank API: %s') % str(exc))

        if response.status_code >= 400:
            raise ValidationError(
                _('Bank API error (%s): %s') % (response.status_code, (response.text or '')[:500])
            )

        try:
            body = response.json()
        except Exception:
            body = {'message': (response.text or '')[:500]}

        sync_results = self._prepare_online_sync_results(sync_lines, body)

        reconciliation = self.env['bhu.payment.reconciliation.bank'].search(
            [
                ('payment_file_id', '=', self.id),
                ('state', 'in', ['draft', 'processed']),
            ],
            order='id desc',
            limit=1,
        )
        if not reconciliation:
            reconciliation = self.env['bhu.payment.reconciliation.bank'].create({
                'payment_file_id': self.id,
                'bank_file': base64.b64encode(b'{}'),
                'bank_file_filename': f'online_sync_{self.name or self.id}.json',
            })

        line_vals = []
        for line in sync_lines:
            result = sync_results.get(line.id, {})
            line_vals.append((0, 0, {
                'payment_line_id': line.id,
                'utr_number': result.get('utr_number') or '',
                'transaction_reference': f"SYNC-{line.id}",
                'beneficiary_account': line.account_number or '',
                'beneficiary_name': line._get_beneficiary_display_name(),
                'beneficiary_bank_code': line.ifsc_code or '',
                'credit_amount': float(line.net_payable_amount or line.compensation_amount or 0.0),
                'status': result.get('status') or 'pending',
                'event_status': (result.get('raw') or {}).get('event_status') or '',
                'error': result.get('reason') or '',
            }))
        if line_vals:
            reconciliation.write({'reconciliation_line_ids': line_vals, 'state': 'processed'})

        settled = len([r for r in sync_results.values() if r.get('status') == 'settled'])
        failed = len([r for r in sync_results.values() if r.get('status') == 'failed'])
        pending = len(sync_lines) - settled - failed
        message = _('Online sync completed. Settled: %s, Failed: %s, Pending: %s') % (
            settled, failed, pending
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Online Sync'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _generate_excel_file(self):
        """Generate bank bulk-upload Excel (11-column NEFT template)."""
        self.ensure_one()
        rows = []
        for line in self.payment_line_ids.sorted(key=lambda l: (l.serial_number, l.id)):
            export_line = line.voucher_export_line_id
            tx_uuid = (line.transaction_uuid or '').strip().replace('-', '').upper() or uuid.uuid4().hex.upper()
            external_ref = (
                (export_line.external_ref if export_line else '')
                or tx_uuid
            )
            rows.append({
                'amount': round(float(line.net_payable_amount or line.compensation_amount or 0.0), 2),
                'beneficiary_name': line._get_beneficiary_display_name(),
                'bank_name': (line.bank_name or '').strip(),
                'account_number': (line.account_number or '').strip().replace(' ', ''),
                'ifsc_code': (line.ifsc_code or '').strip().upper(),
                'external_ref': external_ref,
                'transaction_uuid': tx_uuid,
            })
        return self.generate_bank_excel_bytes(
            rows,
            debit_account=(self.debit_account_number or '').strip(),
            purpose_1=self.village_id.name or '',
            purpose_2=self.project_id.name or '',
        )

    @api.model
    def generate_bank_excel_bytes(self, payment_rows, debit_account='', purpose_1='', purpose_2=''):
        """Shared 11-column NEFT bulk upload Excel builder."""
        if not HAS_XLSXWRITER:
            raise ValidationError(_(
                'xlsxwriter library is required for Excel export. Please install it: pip install xlsxwriter'
            ))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Sheet1')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9D9D9',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        cell_format = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        amount_format = workbook.add_format({'border': 1, 'valign': 'vcenter', 'num_format': '#,##0.00'})

        headers = [
            'Bulk Transaction Type',
            'External Ref No',
            'Debit Account number',
            'Amount',
            'Beneficiary Name',
            'Beneficiary Bank Name',
            'Beneficiary Account Number',
            'IFSC',
            'Purpose 1',
            'Purpose 2',
            'Cheque Number',
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        row = 1
        for prow in payment_rows or []:
            amount = round(float(prow.get('amount') or 0.0), 2)
            tx_ref = (
                (prow.get('external_ref') or prow.get('transaction_uuid') or '').strip()
                or uuid.uuid4().hex.upper()
            )
            worksheet.write(row, 0, 'N', cell_format)
            worksheet.write(row, 1, tx_ref, cell_format)
            worksheet.write(row, 2, debit_account or '', cell_format)
            worksheet.write(row, 3, amount, amount_format)
            worksheet.write(row, 4, prow.get('beneficiary_name') or '', cell_format)
            worksheet.write(row, 5, (prow.get('bank_name') or '').strip(), cell_format)
            worksheet.write(row, 6, (prow.get('account_number') or '').strip().replace(' ', ''), cell_format)
            worksheet.write(row, 7, (prow.get('ifsc_code') or '').strip().upper(), cell_format)
            worksheet.write(row, 8, purpose_1 or '', cell_format)
            worksheet.write(row, 9, purpose_2 or '', cell_format)
            worksheet.write(row, 10, '', cell_format)
            row += 1

        col_widths = [22, 56, 22, 14, 30, 26, 24, 14, 18, 18, 14]
        for col, width in enumerate(col_widths):
            worksheet.set_column(col, col, width)
        worksheet.set_row(0, 28)

        workbook.close()
        output.seek(0)
        return output.read()

    @api.model
    def submit_indusind_online_authorisation(self, export, payment_rows, voucher, khasra_numbers=None):
        """Submit bulk payment for Online Authorisation in IndusInd corporate portal."""
        params = self.env['ir.config_parameter'].sudo()
        api_url = (
            params.get_param('bhukhadan_core.indusind_authorisation_api_url')
            or params.get_param('bhukhadan_core.indusind_api_url')
        )
        bearer_token = params.get_param('bhukhadan_core.indusind_bearer_token')
        api_key = params.get_param('bhukhadan_core.indusind_api_key')
        client_id = params.get_param('bhukhadan_core.indusind_client_id')
        if not api_url:
            raise ValidationError(_(
                'IndusInd API is not configured. Set `bhukhadan_core.indusind_authorisation_api_url` '
                'or `bhukhadan_core.indusind_api_url` in System Parameters.'
            ))

        try:
            import requests
        except ImportError:
            raise ValidationError(_("Python library 'requests' is required for IndusInd authorisation."))

        transactions = []
        for prow in payment_rows or []:
            transactions.append({
                'external_ref_no': (prow.get('external_ref') or uuid.uuid4().hex.upper()),
                'beneficiary_name': prow.get('beneficiary_name') or '',
                'bank_name': (prow.get('bank_name') or '').strip(),
                'account_number': (prow.get('account_number') or '').strip().replace(' ', ''),
                'ifsc_code': (prow.get('ifsc_code') or '').strip().upper(),
                'amount': round(float(prow.get('amount') or 0.0), 2),
            })

        headers = {'Content-Type': 'application/json'}
        if bearer_token:
            headers['Authorization'] = f'Bearer {bearer_token}'
        if api_key:
            headers['x-api-key'] = api_key
        if client_id:
            headers['x-client-id'] = client_id

        payload = {
            'request_type': 'online_authorisation',
            'reference_no': export.name or f"PVEXP-{export.id}",
            'voucher_ref': voucher.name or '',
            'debit_account_number': (voucher.debit_account_number or '').strip(),
            'project': voucher.project_id.name or '',
            'village': voucher.village_id.name or '',
            'khasras': list(khasra_numbers or []),
            'total_amount': round(float(export.amount or 0.0), 2),
            'transactions': transactions,
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        except Exception as exc:
            export.write({
                'indusind_authorisation_status': 'failed',
                'indusind_authorisation_message': str(exc)[:500],
            })
            raise ValidationError(_('Failed to connect to IndusInd API: %s') % str(exc))

        body_text = (response.text or '')[:2000]
        try:
            body = response.json()
        except Exception:
            body = {'message': body_text}

        if response.status_code >= 400:
            export.write({
                'indusind_authorisation_status': 'failed',
                'indusind_authorisation_message': body_text[:500],
            })
            raise ValidationError(
                _('IndusInd API error (%s): %s') % (response.status_code, body_text[:500])
            )

        auth_ref = (
            body.get('authorisation_ref')
            or body.get('reference_no')
            or body.get('batch_id')
            or body.get('transaction_id')
            or payload['reference_no']
        )
        message = (
            body.get('message')
            or body.get('status_message')
            or _('Online Authorisation submitted to IndusInd Portal.')
        )
        export.write({
            'indusind_authorisation_ref': str(auth_ref)[:120],
            'indusind_authorisation_status': 'submitted',
            'indusind_authorisation_message': str(message)[:500],
            'indusind_authorisation_date': fields.Datetime.now(),
        })
        return {
            'reference': auth_ref,
            'message': _('IndusInd Online Authorisation submitted (ref: %s).') % auth_ref,
            'raw': body,
        }

    def action_open_bank_details_wizard(self):
        """Open popup to update beneficiary bank details line-wise."""
        self.ensure_one()
        if not self.payment_line_ids:
            raise UserError(_('No payment lines found for this payment file.'))

        wizard_line_vals = []
        for line in self.payment_line_ids:
            wizard_line_vals.append((0, 0, {
                'payment_line_id': line.id,
                'serial_number': line.serial_number,
                'beneficiary_name': line._get_beneficiary_display_name(),
                'bank_name': line.bank_name or '',
                'bank_branch': line.bank_branch or '',
                'account_number': line.account_number or '',
                'ifsc_code': line.ifsc_code or '',
            }))

        wizard = self.env['bhu.payment.file.bank.details.wizard'].create({
            'payment_file_id': self.id,
            'line_ids': wizard_line_vals,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Update Beneficiary Bank Details'),
            'res_model': 'bhu.payment.file.bank.details.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def _get_bene_test_result(self):
        """Validate beneficiary bank details and return pass/fail counts."""
        self.ensure_one()
        ifsc_regex = re.compile(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$')
        passed = 0
        failed = 0

        for line in self.payment_line_ids:
            is_valid = True
            if not (line.bank_name or '').strip():
                is_valid = False
            if not (line.account_number or '').strip():
                is_valid = False
            if not ifsc_regex.match((line.ifsc_code or '').strip()):
                is_valid = False

            if is_valid:
                passed += 1
            else:
                failed += 1

        return passed, failed

    def action_bene_testing(self):
        """Run quick beneficiary bank-detail validation."""
        self.ensure_one()
        passed, failed = self._get_bene_test_result()
        total = len(self.payment_line_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Beneficiary Testing'),
                'message': _(
                    'Total: %(total)s | Passed: %(passed)s | Failed: %(failed)s'
                ) % {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                },
                'type': 'success' if failed == 0 else 'warning',
                'sticky': True,
            },
        }


class PaymentFileLine(models.Model):
    _name = 'bhu.payment.file.line'
    _description = 'Payment File Line / भुगतान फ़ाइल पंक्ति'
    _order = 'serial_number'

    payment_file_id = fields.Many2one('bhu.payment.file', string='Payment File', required=True, ondelete='cascade')
    transaction_uuid = fields.Char(
        string='Transaction UUID / लेनदेन UUID',
        copy=False,
        index=True,
        help='Pure 32-character hex UUID (no dashes). Bank Excel uses a separate readable External Ref No.',
    )
    voucher_export_id = fields.Many2one(
        'bhu.payment.voucher.export',
        string='Voucher export',
        ondelete='set null',
        copy=False,
        index=True,
    )
    voucher_export_line_id = fields.Many2one(
        'bhu.payment.voucher.export.line',
        string='Voucher export line',
        ondelete='set null',
        copy=False,
    )
    export_ref = fields.Char(
        string='Export ref',
        related='voucher_export_id.name',
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        'bhu.project',
        string='Project / परियोजना',
        related='payment_file_id.project_id',
        store=True,
        readonly=True,
    )
    village_id = fields.Many2one(
        'bhu.village',
        string='Village / ग्राम',
        related='payment_file_id.village_id',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        'bhu.department',
        string='Department / विभाग',
        related='payment_file_id.department_id',
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            'payment_file_line_transaction_uuid_unique',
            'unique(transaction_uuid)',
            'Transaction UUID must be unique across all payment lines.',
        ),
    ]
    # Serial Numbers
    serial_number = fields.Integer(string='Serial Number / स.क.', required=True, default=1)
    award_serial_number = fields.Integer(string='Award Serial Number / अवॉर्ड स.क.', required=True)
    khasra_number = fields.Char(string='Khasra Number / खसरा नंबर')
    
    # Landowner Details
    landowner_id = fields.Many2one('bhu.landowner', string='Landowner / भूमिस्वामी', required=False, ondelete='set null')
    landowner_name = fields.Char(string='Landowner Name / पक्षकार का नाम', related='landowner_id.name', store=True, readonly=True)
    father_husband_name = fields.Char(string='Father/Husband Name / पिता/पति का नाम', 
                                     related='landowner_id.father_name', store=True, readonly=True)
    beneficiary_override = fields.Char(
        string='Beneficiary name (override) / लाभार्थी नाम',
        help='Used for bank file when payee is not the linked landowner record (e.g. split payout).',
    )
    
    # Bank Details
    bank_name = fields.Char(string='Bank Name / बैंक का नाम', required=True)
    bank_branch = fields.Char(string='Branch / शाखा')
    account_number = fields.Char(string='Account Number / खाता क्रमांक', required=True)
    ifsc_code = fields.Char(string='IFSC Code / आईएफएससी कोड', required=True)
    
    # Payment Amounts
    compensation_amount = fields.Float(string='Compensation Amount / मुआवजा राशि', required=True, digits=(16, 2))
    net_payable_amount = fields.Float(string='Net Payable Amount / शुद्ध भुगतान की राशि', 
                                      compute='_compute_net_payable', store=True, digits=(16, 2))
    bene_status = fields.Selection(
        [('pass', 'Pass'), ('fail', 'Fail')],
        string='Bene Status',
        compute='_compute_bene_status',
        store=True,
    )

    # Bank reconciliation snapshot
    reconciliation_line_ids = fields.One2many(
        'bhu.payment.reconciliation.bank.line',
        'payment_line_id',
        string='Reconciliation Lines / समाधान पंक्तियां',
        readonly=True,
    )
    payment_status = fields.Selection(
        [
            ('pending', 'Pending / लंबित'),
            ('settled', 'Success / सफल'),
            ('failed', 'Failed / असफल'),
        ],
        string='Payment Status / भुगतान स्थिति',
        compute='_compute_reconciliation_snapshot',
        readonly=True,
    )
    utr_number = fields.Char(
        string='UTR Number / यूटीआर संख्या',
        compute='_compute_reconciliation_snapshot',
        readonly=True,
    )
    failure_reason_code = fields.Char(
        string='Failure Reason Code / विफलता कारण कोड',
        compute='_compute_reconciliation_snapshot',
        readonly=True,
    )
    
    currency_id = fields.Many2one('res.currency', string='Currency', related='payment_file_id.currency_id')
    
    # Remarks
    remark = fields.Text(string='Remark / रिमार्क')
    
    def _get_beneficiary_display_name(self):
        """Name sent to bank export / API (override when splitting by payee)."""
        self.ensure_one()
        o = (self.beneficiary_override or '').strip()
        if o:
            return o
        return (self.landowner_name or '').strip()

    @api.depends('compensation_amount')
    def _compute_net_payable(self):
        """Compute net payable amount"""
        for record in self:
            record.net_payable_amount = record.compensation_amount

    @api.depends('bank_name', 'bank_branch', 'account_number', 'ifsc_code')
    def _compute_bene_status(self):
        """Beneficiary bank detail status for quick list visibility."""
        ifsc_regex = re.compile(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$')
        for record in self:
            is_valid = True
            if not (record.bank_name or '').strip():
                is_valid = False
            acct = (record.account_number or '').strip().replace(' ', '')
            if not acct or (not acct.isdigit()) or len(acct) < 9 or len(acct) > 18:
                is_valid = False
            ifsc = (record.ifsc_code or '').strip().upper()
            if not ifsc_regex.match(ifsc):
                is_valid = False
            record.bene_status = 'pass' if is_valid else 'fail'

    @api.constrains('ifsc_code', 'account_number')
    def _check_bank_field_formats(self):
        """Validate IFSC and account number per standard conventions."""
        ifsc_regex = re.compile(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$')
        for record in self:
            ifsc = (record.ifsc_code or '').strip().upper()
            acct = (record.account_number or '').strip().replace(' ', '')
            if ifsc and not ifsc_regex.match(ifsc):
                raise ValidationError(_(
                    'Invalid IFSC Code "%s". Use standard format: 4 letters + 0 + 6 alphanumeric characters (e.g., SBIN0001234).'
                ) % (record.ifsc_code or ''))
            if acct and (not acct.isdigit() or len(acct) < 9 or len(acct) > 18):
                raise ValidationError(_(
                    'Invalid Account Number "%s". It must contain only digits and be between 9 and 18 characters.'
                ) % (record.account_number or ''))

    @api.depends(
        'reconciliation_line_ids',
        'reconciliation_line_ids.status',
        'reconciliation_line_ids.utr_number',
        'reconciliation_line_ids.error',
        'reconciliation_line_ids.event_status',
    )
    def _compute_reconciliation_snapshot(self):
        """Show latest reconciliation result directly on payment line."""
        for record in self:
            latest_line = record.reconciliation_line_ids.sorted('id', reverse=True)[:1]
            if latest_line:
                record.payment_status = latest_line.status or 'pending'
                record.utr_number = latest_line.utr_number or ''
                record.failure_reason_code = (
                    (latest_line.error or latest_line.event_status or '').strip()
                    if latest_line.status == 'failed'
                    else ''
                )
            else:
                record.payment_status = 'pending'
                record.utr_number = ''
                record.failure_reason_code = ''

    def action_open_bank_reconciliation(self):
        """Open bank reconciliation for this payment file to upload/process file."""
        self.ensure_one()
        if not self.payment_file_id:
            raise UserError(_('This payment line is not linked to a payment file.'))
        return self.payment_file_id.action_open_bank_reconciliation()

    def action_online_sync_line(self):
        """Sync only this payment line via parent payment file API."""
        self.ensure_one()
        if not self.payment_file_id:
            raise UserError(_('This payment line is not linked to a payment file.'))

        if self.payment_status not in ('pending', 'failed'):
            raise UserError(_('Only pending or failed lines can be synced online.'))

        params = self.env['ir.config_parameter'].sudo()
        api_url = params.get_param('bhukhadan_core.indusind_api_url')
        bearer_token = params.get_param('bhukhadan_core.indusind_bearer_token')
        api_key = params.get_param('bhukhadan_core.indusind_api_key')
        client_id = params.get_param('bhukhadan_core.indusind_client_id')
        if not api_url:
            raise ValidationError(_(
                'IndusInd API is not configured. Please set `bhukhadan_core.indusind_api_url` in System Parameters.'
            ))

        try:
            import requests
        except ImportError:
            raise ValidationError(_("Python library 'requests' is required for online sync."))

        headers = {'Content-Type': 'application/json'}
        if bearer_token:
            headers['Authorization'] = f'Bearer {bearer_token}'
        if api_key:
            headers['x-api-key'] = api_key
        if client_id:
            headers['x-client-id'] = client_id

        payload = {
            'reference_no': f"PFLINE-{self.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            'payment_file_no': self.payment_file_id.name or '',
            'project': self.payment_file_id.project_id.name or '',
            'village': self.payment_file_id.village_id.name or '',
            'transactions': [{
                'payment_line_id': self.id,
                'external_ref_no': f"{self.payment_file_id.name}_{uuid.uuid4().hex.upper()}",
                'beneficiary_name': self._get_beneficiary_display_name(),
                'account_number': self.account_number or '',
                'ifsc_code': self.ifsc_code or '',
                'amount': round(float(self.net_payable_amount or self.compensation_amount or 0.0), 2),
                'khasra': self.khasra_number or '',
            }],
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=45)
        except Exception as exc:
            raise ValidationError(_('Failed to connect to bank API: %s') % str(exc))

        if response.status_code >= 400:
            raise ValidationError(
                _('Bank API error (%s): %s') % (response.status_code, (response.text or '')[:500])
            )

        try:
            body = response.json()
        except Exception:
            body = {'message': (response.text or '')[:500]}

        result = self.payment_file_id._prepare_online_sync_results(self, body).get(self.id, {})
        reconciliation = self.env['bhu.payment.reconciliation.bank'].search(
            [
                ('payment_file_id', '=', self.payment_file_id.id),
                ('state', 'in', ['draft', 'processed']),
            ],
            order='id desc',
            limit=1,
        )
        if not reconciliation:
            reconciliation = self.env['bhu.payment.reconciliation.bank'].create({
                'payment_file_id': self.payment_file_id.id,
                'bank_file': base64.b64encode(b'{}'),
                'bank_file_filename': f'online_sync_{self.payment_file_id.name or self.payment_file_id.id}.json',
            })

        self.env['bhu.payment.reconciliation.bank.line'].create({
            'reconciliation_id': reconciliation.id,
            'payment_line_id': self.id,
            'utr_number': result.get('utr_number') or '',
            'transaction_reference': f"SYNC-{self.id}",
            'beneficiary_account': self.account_number or '',
            'beneficiary_name': self._get_beneficiary_display_name(),
            'beneficiary_bank_code': self.ifsc_code or '',
            'credit_amount': float(self.net_payable_amount or self.compensation_amount or 0.0),
            'status': result.get('status') or 'pending',
            'event_status': (result.get('raw') or {}).get('event_status') or '',
            'error': result.get('reason') or '',
        })
        reconciliation.state = 'processed'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Online Sync'),
                'message': _('Online sync completed for line %s.') % (self.award_serial_number or self.id),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_bank_reconciliation_bulk(self):
        """Open reconciliation upload once for selected payment lines."""
        if not self:
            raise UserError(_('Please select at least one payment line.'))

        payment_files = self.mapped('payment_file_id')
        if len(payment_files) != 1:
            raise UserError(_('Please select lines from one payment file only.'))

        return payment_files.action_open_bank_reconciliation()

    def action_open_bank_details_wizard_bulk(self):
        """Open bank-details update popup for selected payment lines."""
        if not self:
            raise UserError(_('Please select at least one payment line.'))

        payment_files = self.mapped('payment_file_id')
        if len(payment_files) != 1:
            raise UserError(_('Please select lines from one payment file only.'))

        wizard_line_vals = []
        for line in self:
            wizard_line_vals.append((0, 0, {
                'payment_line_id': line.id,
                'serial_number': line.serial_number,
                'beneficiary_name': line._get_beneficiary_display_name(),
                'bank_name': line.bank_name or '',
                'bank_branch': line.bank_branch or '',
                'account_number': line.account_number or '',
                'ifsc_code': line.ifsc_code or '',
            }))

        wizard = self.env['bhu.payment.file.bank.details.wizard'].create({
            'payment_file_id': payment_files.id,
            'line_ids': wizard_line_vals,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Update Beneficiary Bank Details'),
            'res_model': 'bhu.payment.file.bank.details.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_download_recon_template(self):
        """Download Excel template for bank reconciliation upload testing."""
        lines = self
        if not lines:
            active_ids = self.env.context.get('active_ids') or []
            if active_ids:
                lines = self.browse(active_ids)

        payment_files = lines.mapped('payment_file_id') if lines else self.env['bhu.payment.file']
        if len(payment_files) > 1:
            raise UserError(_('Please select lines from one payment file only to download a prefilled template.'))

        payment_file = payment_files[0] if payment_files else False
        filename_suffix = payment_file.name if payment_file else 'Sample'
        filename = f'Bank_Recon_Template_{filename_suffix}.xlsx'

        if not HAS_XLSXWRITER:
            raise ValidationError(_('xlsxwriter library is required for Excel template export.'))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('ReconTemplate')
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})
        amount_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})

        headers = [
            'UTR Number',
            'Transaction Reference',
            'Beneficiary Account',
            'Beneficiary Name',
            'Beneficiary Bank Code',
            'Credit Amount',
            'Status',
            'Event Status',
            'Error',
            'Payment Id',
            'Date',
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_fmt)

        row = 1
        if lines:
            for line in lines:
                export_line = line.voucher_export_line_id
                tx_ref = (
                    (export_line.external_ref if export_line else '')
                    or line.transaction_uuid
                    or ''
                )
                worksheet.write(row, 0, '', cell_fmt)
                worksheet.write(row, 1, tx_ref, cell_fmt)
                worksheet.write(row, 2, line.account_number or '', cell_fmt)
                worksheet.write(row, 3, line._get_beneficiary_display_name(), cell_fmt)
                worksheet.write(row, 4, line.ifsc_code or '', cell_fmt)
                worksheet.write_number(row, 5, float(line.net_payable_amount or line.compensation_amount or 0.0), amount_fmt)
                worksheet.write(row, 6, 'pending', cell_fmt)
                worksheet.write(row, 7, '', cell_fmt)
                worksheet.write(row, 8, '', cell_fmt)
                worksheet.write(row, 9, '', cell_fmt)
                worksheet.write(row, 10, str(fields.Date.today() or ''), cell_fmt)
                row += 1
        else:
            worksheet.write(row, 0, '', cell_fmt)
            worksheet.write(row, 1, '', cell_fmt)
            worksheet.write(row, 2, '', cell_fmt)
            worksheet.write(row, 3, '', cell_fmt)
            worksheet.write(row, 4, '', cell_fmt)
            worksheet.write_number(row, 5, 0.0, amount_fmt)
            worksheet.write(row, 6, 'pending', cell_fmt)
            worksheet.write(row, 7, '', cell_fmt)
            worksheet.write(row, 8, '', cell_fmt)
            worksheet.write(row, 9, '', cell_fmt)
            worksheet.write(row, 10, str(fields.Date.today() or ''), cell_fmt)

        worksheet.set_column('A:B', 24)
        worksheet.set_column('C:E', 28)
        worksheet.set_column('F:F', 16)
        worksheet.set_column('G:J', 20)
        worksheet.set_column('K:K', 14)

        workbook.close()
        output.seek(0)
        file_content = output.read()
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(file_content),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'bhu.payment.file.line',
            'res_id': lines[0].id if lines else False,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }


class PaymentFileBankDetailsWizard(models.TransientModel):
    _name = 'bhu.payment.file.bank.details.wizard'
    _description = 'Payment File Beneficiary Bank Details Wizard'

    payment_file_id = fields.Many2one('bhu.payment.file', string='Payment File', required=True, readonly=True)
    update_landowner_bank = fields.Boolean(
        string='Also update Landowner master bank details',
        default=True,
    )
    line_ids = fields.One2many(
        'bhu.payment.file.bank.details.wizard.line',
        'wizard_id',
        string='Beneficiaries',
    )

    def action_apply_updates(self):
        self.ensure_one()
        updates = 0
        skipped = []
        ifsc_regex = re.compile(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$')
        for line in self.line_ids:
            payment_line = line.payment_line_id
            if not payment_line:
                continue

            new_vals = {
                'bank_name': (line.bank_name or '').strip(),
                'bank_branch': (line.bank_branch or '').strip(),
                'account_number': (line.account_number or '').strip().replace(' ', ''),
                'ifsc_code': (line.ifsc_code or '').strip().upper(),
            }

            current_vals = {
                'bank_name': (payment_line.bank_name or '').strip(),
                'bank_branch': (payment_line.bank_branch or '').strip(),
                'account_number': (payment_line.account_number or '').strip().replace(' ', ''),
                'ifsc_code': (payment_line.ifsc_code or '').strip().upper(),
            }

            # Skip unchanged rows so existing bad rows don't block all updates.
            if new_vals == current_vals:
                continue

            if not ifsc_regex.match(new_vals['ifsc_code']):
                skipped.append(_(
                    'Sr %(sr)s (%(name)s): invalid IFSC "%(ifsc)s"'
                ) % {
                    'sr': line.serial_number or '-',
                    'name': line.beneficiary_name or '',
                    'ifsc': line.ifsc_code or '',
                })
                continue

            acct = new_vals['account_number']
            if (not acct.isdigit()) or len(acct) < 9 or len(acct) > 18:
                skipped.append(_(
                    'Sr %(sr)s (%(name)s): invalid account "%(acct)s"'
                ) % {
                    'sr': line.serial_number or '-',
                    'name': line.beneficiary_name or '',
                    'acct': line.account_number or '',
                })
                continue

            values = {
                'bank_name': new_vals['bank_name'],
                'bank_branch': new_vals['bank_branch'],
                'account_number': new_vals['account_number'],
                'ifsc_code': new_vals['ifsc_code'],
            }
            payment_line.write(values)
            updates += 1

            if self.update_landowner_bank and payment_line.landowner_id:
                payment_line.landowner_id.write(values)

        if skipped:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Bank Details Partially Updated'),
                    'message': _(
                        'Updated %(ok)s row(s). Skipped %(bad)s invalid row(s). Fix these and retry: %(rows)s'
                    ) % {
                        'ok': updates,
                        'bad': len(skipped),
                        'rows': '; '.join(skipped[:5]),
                    },
                    'type': 'warning',
                    'sticky': True,
                },
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Beneficiary Bank Details Updated'),
                'message': _('Updated %(count)s payment lines.') % {'count': updates},
                'type': 'success',
                'sticky': False,
            },
        }

    def action_run_bene_testing(self):
        self.ensure_one()
        ifsc_regex = re.compile(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$')
        passed = 0
        failed = 0

        for line in self.line_ids:
            is_valid = True
            if not (line.bank_name or '').strip():
                is_valid = False
            if not (line.account_number or '').strip():
                is_valid = False
            if not ifsc_regex.match((line.ifsc_code or '').strip()):
                is_valid = False

            line.bene_test_status = 'pass' if is_valid else 'fail'
            if is_valid:
                passed += 1
            else:
                failed += 1

        total = len(self.line_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Beneficiary Testing'),
                'message': _(
                    'Total: %(total)s | Passed: %(passed)s | Failed: %(failed)s'
                ) % {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                },
                'type': 'success' if failed == 0 else 'warning',
                'sticky': True,
            },
        }


class PaymentFileBankDetailsWizardLine(models.TransientModel):
    _name = 'bhu.payment.file.bank.details.wizard.line'
    _description = 'Payment File Beneficiary Bank Details Wizard Line'
    _order = 'serial_number, id'

    wizard_id = fields.Many2one('bhu.payment.file.bank.details.wizard', required=True, ondelete='cascade')
    payment_line_id = fields.Many2one('bhu.payment.file.line', string='Payment Line', readonly=True)
    serial_number = fields.Integer(string='Sr.', readonly=True)
    beneficiary_name = fields.Char(string='Beneficiary', readonly=True)
    bank_name = fields.Char(string='Bank Name', required=True)
    bank_branch = fields.Char(string='Bank Branch')
    account_number = fields.Char(string='Account Number', required=True)
    ifsc_code = fields.Char(string='IFSC Code', required=True)
    bene_test_status = fields.Selection(
        [('na', 'Not Tested'), ('pass', 'Pass'), ('fail', 'Fail')],
        string='Test Status',
        default='na',
    )
    bene_test_sign = fields.Char(string='Sign', compute='_compute_bene_test_sign')

    @api.depends('bene_test_status')
    def _compute_bene_test_sign(self):
        for record in self:
            if record.bene_test_status == 'pass':
                record.bene_test_sign = '✓'
            elif record.bene_test_status == 'fail':
                record.bene_test_sign = '✗'
            else:
                record.bene_test_sign = '-'

    @api.onchange('ifsc_code')
    def _onchange_ifsc_code_upper(self):
        for record in self:
            if record.ifsc_code:
                record.ifsc_code = record.ifsc_code.strip().upper()

    @api.onchange('account_number')
    def _onchange_account_number_trim(self):
        for record in self:
            if record.account_number:
                record.account_number = record.account_number.strip().replace(' ', '')

