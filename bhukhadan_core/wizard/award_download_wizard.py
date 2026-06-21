# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AwardDownloadWizard(models.TransientModel):
    _name = 'bhu.award.download.wizard'
    _description = 'Award Download Wizard (PDF/Excel only)'

    res_model = fields.Char(string='Model Name', required=True)
    res_id = fields.Integer(string='Record ID', required=True)
    report_xml_id = fields.Char(string='Report XML ID', required=True)
    filename = fields.Char(string='Filename')

    format = fields.Selection([
        ('pdf', 'PDF Format'),
        ('excel', 'Excel Format (.xlsx)'),
    ], string='Download Format', default='pdf', required=True)

    export_scope = fields.Selection(
        [
            ('all', '📋 All sections / सभी पत्रक (भूमि + परिसम्पत्ति + वृक्ष)'),
            ('land', '🧾 Land only (Part Ka) / केवल भूमि (भाग-1 क)'),
            ('asset', '🏠 Structure only (Part Kh) / केवल परिसम्पत्ति (भाग-1 ख)'),
            ('tree', '🌳 Trees only (Part Ga) / केवल वृक्ष (भाग-1 ग)'),
        ],
        string='Sections / पत्रक',
        default='all',
        required=True,
    )

    # True when opened from Section 23 "Generate award" (same UI as Award Simulator)
    section23_generate = fields.Boolean(string='Section 23 Generate', default=False)
    simple_download_dialog = fields.Boolean(
        string='Simple Download Dialog',
        default=False,
        help='When enabled, only format (PDF/Excel) is shown in popup.',
    )
    add_cover_letter = fields.Boolean(
        string='Add Cover Letter / कवर लेटर जोड़ें',
        default=False,
        help='Include executive summary cover page in Section 23 PDF.',
    )

    section23_sheet_variant = fields.Selection(
        [
            ('standard', 'Standard Award / मानक अवार्ड'),
            ('consolidated', 'Consolidated Award Sheet / समेकित अवार्ड शीट'),
            ('rr', 'R&R Award Sheet / पुनर्वास अवार्ड पत्रक'),
        ],
        string='Sheet Type / पत्रक प्रकार',
        default='standard',
        required=True,
    )
    section23_download_copy = fields.Selection(
        [
            ('unsigned', 'Unsigned Award / अनसाइंड अवार्ड'),
            ('signed', 'Signed Award / हस्ताक्षरित अवार्ड'),
        ],
        string='Download Type / डाउनलोड प्रकार',
        default='unsigned',
        required=True,
    )
    # Backward compatibility for stale web clients still sending this field in onchange payload.
    consolidated_award_sheet = fields.Boolean(
        string='Consolidated Award Sheet (Legacy)',
        default=False,
        help='Deprecated compatibility field. Kept to avoid RPC KeyError on cached clients.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') and self.env.context.get('active_id'):
            res.setdefault('res_model', self.env.context.get('active_model'))
            res.setdefault('res_id', self.env.context.get('active_id'))
        if self.env.context.get('default_section23_generate'):
            res['section23_generate'] = True
        if self.env.context.get('default_simple_download_dialog'):
            res['simple_download_dialog'] = True
        res.setdefault('section23_sheet_variant', 'standard')
        return res

    @api.onchange('section23_sheet_variant')
    def _onchange_section23_sheet_variant(self):
        for wizard in self:
            if wizard.section23_sheet_variant in ('consolidated', 'rr'):
                wizard.export_scope = 'all'

    def action_download(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_(
                "The selected record no longer exists. "
                "Please reopen the document and try download again."
            ))
        scope = (self.export_scope or 'all')
        if scope not in ('all', 'land', 'asset', 'tree'):
            scope = 'all'

        variant = self.section23_sheet_variant or 'standard'
        # Legacy toggle support (old wizard payload / stale browser assets)
        if self.consolidated_award_sheet and variant == 'standard':
            variant = 'consolidated'
        if variant not in ('standard', 'consolidated', 'rr'):
            variant = 'standard'

        # Simple download dialog path: return DB-cached file directly (no regeneration).
        if self.simple_download_dialog and self.res_model == 'bhu.section23.award':
            if self.section23_download_copy == 'signed':
                if not hasattr(record, 'action_download_signed_award_file'):
                    raise UserError(_('This record does not support signed downloads.'))
                signed_action = record.action_download_signed_award_file(
                    export_scope=scope,
                    variant=variant,
                    file_format=self.format,
                )
                return self._wrap_download_action_for_autoclose(signed_action)
            if not hasattr(record, 'action_download_cached_award_file'):
                raise UserError(_('This record does not support cached downloads.'))
            # If requested file is missing in DB cache, auto-prepare both PDF+Excel first.
            cache_exists = False
            if hasattr(record, '_s23_get_cached_attachment'):
                cache_exists = bool(record._s23_get_cached_attachment(scope, variant, self.format))
            if not cache_exists:
                if variant == 'standard' and hasattr(record, '_s23_prepare_standard_scope_cache'):
                    record._s23_prepare_standard_scope_cache(export_scope=scope)
                elif hasattr(record, '_s23_prepare_variant_cache'):
                    record._s23_prepare_variant_cache(variant=variant, export_scope=scope)
                    if hasattr(record, '_mark_variant_generated') and variant in ('consolidated', 'rr'):
                        record._mark_variant_generated(variant=variant)
            download_action = record.action_download_cached_award_file(
                export_scope=scope,
                file_format=self.format,
                variant=variant,
            )
            return self._wrap_download_action_for_autoclose(download_action)

        if self.section23_generate and self.res_model == 'bhu.section23.award':
            if not hasattr(record, 'apply_generate_from_download_wizard'):
                raise UserError(_('This record does not support the generate flow.'))
            return record.apply_generate_from_download_wizard(
                file_format=self.format,
                export_scope=scope,
                include_cover_letter=bool(self.add_cover_letter),
                generate_variant=variant,
            )
        
        # Section 23 alternate sheet downloads
        if self.res_model == 'bhu.section23.award' and variant in ('consolidated', 'rr'):
            if variant == 'consolidated':
                if self.format == 'pdf' and hasattr(record, 'action_download_consolidated_pdf'):
                    return record.action_download_consolidated_pdf()
                if self.format == 'excel' and hasattr(record, 'action_download_consolidated_excel'):
                    return record.action_download_consolidated_excel()
            if variant == 'rr':
                if self.format == 'pdf' and hasattr(record, 'action_download_rr_pdf'):
                    return record.action_download_rr_pdf()
                if self.format == 'excel' and hasattr(record, 'action_download_rr_excel'):
                    return record.action_download_rr_excel()

        if self.format == 'pdf':
            if self.res_model == 'bhu.section23.award' and hasattr(record, 'action_download_pdf_components'):
                return record.action_download_pdf_components(
                    export_scope=scope,
                    include_cover_letter=bool(self.add_cover_letter),
                )
            report = self.env.ref(self.report_xml_id)
            return report.report_action(record)
        if self.format == 'excel':
            # Keep wizard generic: support standard Excel hook and
            # Section 23 consolidated components Excel hook.
            if hasattr(record, 'action_download_excel'):
                return record.action_download_excel(export_scope=scope)
            if hasattr(record, 'action_download_excel_components'):
                return record.action_download_excel_components(export_scope=scope)
            raise UserError(_("Excel export is not supported for this report."))
        raise UserError(_("Selected download format is not supported."))

    def _wrap_download_action_for_autoclose(self, action):
        """For wizard downloads: trigger file, then close popup and refresh form."""
        if not isinstance(action, dict):
            return action
        if action.get('type') != 'ir.actions.act_url':
            return action
        return {
            'type': 'ir.actions.client',
            'tag': 'bhuarjan_s23_download_and_refresh',
            'params': {
                'url': action.get('url'),
            },
        }
