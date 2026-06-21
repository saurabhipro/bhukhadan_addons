# -*- coding: utf-8 -*-

import base64
import re

from odoo import models, api, _
from odoo.exceptions import ValidationError


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def _s23_cache_filename_for_user(self, export_scope='all', variant='standard', file_format='pdf'):
        self.ensure_one()
        village_tok = self._s23_filename_token(
            self.village_id.name if self.village_id else '',
            f'village_{self.village_id.id if self.village_id else self.id}',
        )
        loc_tok = self._s23_location_type_suffix()
        scope_key = (export_scope or 'all').lower()
        variant_key = (variant or 'standard').lower()
        if variant_key == 'consolidated':
            award_type_tok = 'Consolidated'
        elif variant_key == 'rr':
            award_type_tok = 'RR'
        else:
            scope_map = {
                'land': 'Land',
                'tree': 'Tree',
                'asset': 'Asset',
                'all': 'All',
            }
            award_type_tok = scope_map.get(scope_key, 'All')
        ext = 'pdf' if (file_format or 'pdf').lower() == 'pdf' else 'xlsx'
        return f"Sec23_Award_{award_type_tok}_{village_tok}_{loc_tok}.{ext}"

    def _s23_get_cached_attachment(self, export_scope='all', variant='standard', file_format='pdf'):
        self.ensure_one()
        cache_key = self._s23_cache_attachment_name(export_scope, variant, file_format)
        att = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('description', 'ilike', cache_key),
        ], order='create_date desc, id desc', limit=1)
        if att:
            return att
        # Backward-compatibility with older cache naming.
        legacy_name = "S23_CACHE__%s__%s__%s__%s.%s" % (
            (variant or 'standard').lower(),
            (export_scope or 'all').lower(),
            'pdf' if (file_format or 'pdf').lower() == 'pdf' else 'excel',
            self.id,
            'pdf' if (file_format or 'pdf').lower() == 'pdf' else 'xlsx',
        )
        return self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('name', '=', legacy_name),
        ], limit=1)

    def _s23_store_cached_attachment(self, binary_data, export_scope='all', variant='standard', file_format='pdf'):
        self.ensure_one()
        if not binary_data:
            return False
        cache_key = self._s23_cache_attachment_name(export_scope, variant, file_format)
        user_name = self._s23_cache_filename_for_user(export_scope, variant, file_format)
        mimetype = 'application/pdf' if (file_format or 'pdf') == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        old = self._s23_get_cached_attachment(export_scope, variant, file_format)
        if old:
            old.unlink()
        return self.env['ir.attachment'].create({
            'name': user_name,
            'type': 'binary',
            'datas': base64.b64encode(binary_data),
            'mimetype': mimetype,
            'res_model': self._name,
            'res_id': self.id,
            'description': f'S23 cached export ({variant}/{export_scope}/{file_format}) [{cache_key}]',
        })

    def _s23_clear_variant_cache(self, variants=None):
        """Delete cached files for selected variant(s) from DB."""
        self.ensure_one()
        variants = variants or ('consolidated', 'rr')
        vars_clean = tuple(v for v in variants if v in ('standard', 'consolidated', 'rr'))
        if not vars_clean:
            return 0
        atts = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ])
        to_remove = atts.filtered(
            lambda att: any(
                (f"s23_cache::{var}::" in ((att.description or '').lower())) or
                (f"S23_CACHE__{var}__" in (att.name or ''))
                for var in vars_clean
            )
        )
        count = len(to_remove)
        if to_remove:
            to_remove.unlink()
        return count

    @api.model
    def _extract_attachment_id_from_action(self, action):
        if not isinstance(action, dict):
            return False
        if action.get('type') != 'ir.actions.act_url':
            return False
        url = action.get('url') or ''
        if not url:
            return False
        match = re.search(r'/web/content/(\d+)', url)
        return int(match.group(1)) if match else False

    def _s23_render_pdf_bytes(self, export_scope='all'):
        self.ensure_one()
        scope = export_scope or 'all'
        if scope not in ('all', 'land', 'asset', 'tree'):
            scope = 'all'
        report_action = self._get_section23_report_action()
        pdf_result = report_action.sudo().with_context(
            s23_pdf_scope=scope,
            s23_include_cover=False,
        )._render_qweb_pdf(report_action.id, [self.id], data={})
        if not pdf_result:
            return b''
        return pdf_result[0] if isinstance(pdf_result, (tuple, list)) else pdf_result

    def _s23_render_variant_pdf_bytes(self, variant='standard', export_scope='all'):
        self.ensure_one()
        var = (variant or 'standard').lower()
        if var == 'standard':
            return self._s23_render_pdf_bytes(export_scope=export_scope)
        if var == 'consolidated':
            report_action = self.env.ref('bhukhadan_core.action_report_consolidated_award_sheet')
            pdf_result = report_action.sudo()._render_qweb_pdf(report_action.id, [self.id], data={})
            if not pdf_result:
                return b''
            return pdf_result[0] if isinstance(pdf_result, (tuple, list)) else pdf_result
        if var == 'rr':
            report_action = self.env.ref('bhukhadan_core.action_report_rr_award_sheet')
            pdf_result = report_action.sudo()._render_qweb_pdf(report_action.id, [self.id], data={})
            if not pdf_result:
                return b''
            return pdf_result[0] if isinstance(pdf_result, (tuple, list)) else pdf_result
        return b''

    def _s23_prepare_variant_cache(self, variant='standard', export_scope='all'):
        """Generate and cache BOTH PDF and Excel for a variant."""
        self.ensure_one()
        var = (variant or 'standard').lower()
        scope = export_scope or 'all'
        if scope not in ('all', 'land', 'asset', 'tree'):
            scope = 'all'
        if var not in ('standard', 'consolidated', 'rr'):
            var = 'standard'

        # Guard: if row phase already reached 100%, reserve post-processing units
        # so loader does not stay at 100% during PDF/Excel cache work.
        cur = self.get_loader_progress_current() or {}
        cur_done = int(cur.get('done') or 0)
        cur_total = int(cur.get('total') or 0)
        if cur_total <= cur_done:
            self._s23_set_loader_progress(
                done=cur_done,
                total=cur_done + 8,
                label=_('Starting document cache phase...'),
                active=True,
                flush=True,
            )

        self._s23_increment_loader_progress(
            step=1, label=_('Rendering PDF report...'), flush=True, active=True
        )
        pdf_bytes = self._s23_render_variant_pdf_bytes(variant=var, export_scope=scope)
        if pdf_bytes:
            self._s23_store_cached_attachment(
                pdf_bytes, export_scope=scope, variant=var, file_format='pdf'
            )
            self._s23_increment_loader_progress(
                step=1, label=_('Uploading PDF to DB cache...'), flush=True, active=True
            )

        excel_action = False
        self._s23_increment_loader_progress(
            step=1, label=_('Rendering Excel report...'), flush=True, active=True
        )
        if var == 'standard':
            excel_action = self.action_download_excel_components(export_scope=scope)
        elif var == 'consolidated':
            excel_action = self.action_download_consolidated_excel()
        elif var == 'rr':
            excel_action = self.action_download_rr_excel()

        excel_attachment_id = self._extract_attachment_id_from_action(excel_action)
        if excel_attachment_id:
            tmp_att = self.env['ir.attachment'].browse(excel_attachment_id)
            if tmp_att.exists() and tmp_att.datas:
                excel_bytes = base64.b64decode(tmp_att.datas)
                self._s23_store_cached_attachment(
                    excel_bytes, export_scope=scope, variant=var, file_format='excel'
                )
                self._s23_increment_loader_progress(
                    step=1, label=_('Uploading Excel to DB cache...'), flush=True, active=True
                )
                # Keep DB clean: remove temporary one created by exporter.
                tmp_att.unlink()
        self._s23_increment_loader_progress(
            step=1, label=_('Cache ready. Updating status...'), flush=True, active=True
        )

    def _s23_prepare_standard_scope_cache(self, export_scope='all'):
        """Generate and cache BOTH PDF and Excel for a standard scope."""
        self.ensure_one()
        self._s23_prepare_variant_cache(variant='standard', export_scope=export_scope)

    def action_download_cached_award_file(self, export_scope='all', file_format='pdf', variant='standard'):
        """Download pre-generated file from DB cache (no regeneration)."""
        self.ensure_one()
        scope = export_scope or 'all'
        fmt = (file_format or 'pdf').lower()
        var = (variant or 'standard').lower()
        if fmt not in ('pdf', 'excel'):
            fmt = 'pdf'
        if var not in ('standard', 'consolidated', 'rr'):
            var = 'standard'
        att = self._s23_get_cached_attachment(scope, var, fmt)
        if not att:
            raise ValidationError(_(
                'No cached %s file found for %s/%s. '
                'Please generate first and then download.'
            ) % (fmt.upper(), var.title(), scope.title()))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'self',
        }

    def _s23_signed_field_map(self, export_scope='all', variant='standard'):
        self.ensure_one()
        scope = (export_scope or 'all').lower()
        var = (variant or 'standard').lower()
        if var == 'consolidated':
            return ('signed_consolidated_award_document', 'signed_consolidated_award_filename', 'Consolidated')
        if var == 'rr':
            return ('signed_rr_award_document', 'signed_rr_award_filename', 'R&R')
        if scope == 'land':
            return ('signed_land_award_document', 'signed_land_award_filename', 'Land')
        if scope == 'tree':
            return ('signed_tree_award_document', 'signed_tree_award_filename', 'Tree')
        if scope == 'asset':
            return ('signed_asset_award_document', 'signed_asset_award_filename', 'Asset')
        return (False, False, False)

    def action_download_signed_award_file(self, export_scope='all', variant='standard', file_format='pdf'):
        """Download uploaded signed award PDF for selected section/variant."""
        self.ensure_one()
        fmt = (file_format or 'pdf').lower()
        if fmt != 'pdf':
            raise ValidationError(_(
                'Signed award is supported only for PDF downloads.'
            ))
        file_field, name_field, label = self._s23_signed_field_map(export_scope, variant)
        if not file_field:
            raise ValidationError(_(
                'Signed download is available only for Land, Tree, Asset, Consolidated, and R&R award sections.'
            ))
        binary_data = self[file_field]
        filename = (self[name_field] or f"Signed_{label}_Award.pdf") if name_field else f"Signed_{label}_Award.pdf"
        if not binary_data:
            raise ValidationError(_(
                'No signed %s award PDF is uploaded yet. Please upload it first.'
            ) % label)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/{file_field}/{filename}?download=true',
            'target': 'self',
        }
