# -*- coding: utf-8 -*-

import base64
import logging
import time
from datetime import datetime

from odoo import models, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def _generate_scope_without_download(self, export_scope='all', label=None, allow_regenerate=False):
        """Generate requested scope and update status without opening download UI."""
        self.ensure_one()
        self._s23_set_loader_progress(
            done=0,
            total=0,
            label=_('Preparing generation...'),
            active=True,
            flush=True,
        )
        gen_t0 = time.perf_counter()
        _logger.warning(
            "[S23 GENERATE START] award=%s id=%s scope=%s project=%s village=%s",
            self.name,
            self.id,
            export_scope,
            self.project_id.id if self.project_id else None,
            self.village_id.id if self.village_id else None,
        )
        had_consolidated = bool(self.consolidated_generated)
        had_rr = bool(self.rr_generated)
        self._validate_for_generate(
            require_sales_sort_rate=True,
            allow_when_fully_generated=bool(allow_regenerate),
        )
        t0 = time.perf_counter()
        self._sync_award_structure_lines()
        t_sync = time.perf_counter() - t0
        t1 = time.perf_counter()
        self._refresh_award_line_items(export_scope=export_scope, log_khasra=True)
        t_refresh = time.perf_counter() - t1
        t2 = time.perf_counter()
        self._s23_prepare_standard_scope_cache(export_scope=export_scope)
        t_cache = time.perf_counter() - t2
        # Base section change invalidates consolidated/R&R snapshots.
        self._s23_increment_loader_progress(
            step=1, label=_('Resetting dependent caches...'), flush=True, active=True
        )
        removed_count = self._s23_clear_variant_cache(variants=('consolidated', 'rr'))
        self.write({
            'consolidated_generated': False,
            'rr_generated': False,
        })
        self._s23_increment_loader_progress(
            step=1, label=_('Updating generation status...'), flush=True, active=True
        )
        self._mark_generated_scope(export_scope=export_scope)
        self._s23_set_loader_progress(
            label=_('Finalizing files...'),
            active=True,
            flush=True,
        )
        total_sec = time.perf_counter() - gen_t0
        _logger.warning(
            "[S23 GENERATE] award=%s id=%s scope=%s timings: sync=%.3fs refresh=%.3fs cache=%.3fs total=%.3fs",
            self.name, self.id, export_scope, t_sync, t_refresh, t_cache, total_sec
        )
        reset_note = ''
        if had_consolidated or had_rr:
            reset_note = _(
                ' Consolidated and R&R caches were reset. Please regenerate both before download.'
            )
        self.message_post(
            body=_("Section generated successfully. / पत्रक सफलतापूर्वक जेनरेट किया गया।") + reset_note
        )
        message = label or _('Section generated. Now use Download button for PDF/Excel.')
        if had_consolidated or had_rr:
            message = _(
                '%s Consolidated and R&R were reset and their cached files were deleted from DB (%s file(s)). '
                'Please regenerate Consolidated and R&R.'
            ) % (message, removed_count)
        current = self.get_loader_progress_current() or {}
        final_total = int(current.get('total') or 0)
        self._s23_set_loader_progress(
            done=final_total,
            total=final_total,
            label=_('Completed'),
            active=False,
            flush=True,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Generated'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_generate_land_award(self):
        self.ensure_one()
        return self._generate_scope_without_download(
            export_scope='land',
            label=_('Land award generated. Use Download Land Award for PDF/Excel.'),
        )

    def action_generate_tree_award(self):
        self.ensure_one()
        return self._generate_scope_without_download(
            export_scope='tree',
            label=_('Tree award generated. Use Download Tree Award for PDF/Excel.'),
        )

    def action_generate_asset_award(self):
        self.ensure_one()
        return self._generate_scope_without_download(
            export_scope='asset',
            label=_('Asset award generated. Use Download Asset Award for PDF/Excel.'),
        )

    def action_regenerate_land_award(self):
        self.ensure_one()
        return self._generate_scope_without_download(
            export_scope='land',
            label=_('Land award regenerated. Latest PDF/Excel cached and ready to download.'),
            allow_regenerate=True,
        )

    def action_regenerate_tree_award(self):
        self.ensure_one()
        return self._generate_scope_without_download(
            export_scope='tree',
            label=_('Tree award regenerated. Latest PDF/Excel cached and ready to download.'),
            allow_regenerate=True,
        )

    def action_regenerate_asset_award(self):
        self.ensure_one()
        return self._generate_scope_without_download(
            export_scope='asset',
            label=_('Asset award regenerated. Latest PDF/Excel cached and ready to download.'),
            allow_regenerate=True,
        )

    def _generate_variant_without_download(self, variant='consolidated'):
        self.ensure_one()
        self._ensure_all_components_generated()
        var = (variant or 'consolidated').lower()
        if var not in ('consolidated', 'rr'):
            var = 'consolidated'
        self._s23_prepare_variant_cache(variant=var, export_scope='all')
        self._mark_variant_generated(variant=var)
        lbl = _('Consolidated award generated. Download is ready from DB cache.')
        if var == 'rr':
            lbl = _('R&R award generated. Download is ready from DB cache.')
        self.message_post(body=lbl)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Generated'),
                'message': lbl,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_generate_consolidated_award(self):
        self.ensure_one()
        return self._generate_variant_without_download(variant='consolidated')

    def action_generate_rr_award(self):
        self.ensure_one()
        return self._generate_variant_without_download(variant='rr')

    def action_download_land_award(self):
        self.ensure_one()
        if not self.land_generated:
            raise ValidationError(_('Generate Land Award first, then download.'))
        return self._open_award_download_wizard(
            generate=False,
            export_scope='land',
            variant='standard',
            title=_('Download Land Award / भूमि अवार्ड डाउनलोड करें'),
            simple_download_dialog=True,
        )

    def action_download_tree_award(self):
        self.ensure_one()
        if not self.tree_generated:
            raise ValidationError(_('Generate Tree Award first, then download.'))
        return self._open_award_download_wizard(
            generate=False,
            export_scope='tree',
            variant='standard',
            title=_('Download Tree Award / वृक्ष अवार्ड डाउनलोड करें'),
            simple_download_dialog=True,
        )

    def action_download_asset_award(self):
        self.ensure_one()
        if not self.asset_generated:
            raise ValidationError(_('Generate Asset Award first, then download.'))
        return self._open_award_download_wizard(
            generate=False,
            export_scope='asset',
            variant='standard',
            title=_('Download Asset Award / परिसम्पत्ति अवार्ड डाउनलोड करें'),
            simple_download_dialog=True,
        )

    def action_download_standard_full_award(self):
        self.ensure_one()
        self._ensure_all_components_generated()
        return self._open_award_download_wizard(
            generate=False,
            export_scope='all',
            variant='standard',
            title=_('Download Standard Award (Full) / मानक अवार्ड (पूर्ण) डाउनलोड करें'),
            simple_download_dialog=True,
        )

    def action_download_consolidated_full_award(self):
        self.ensure_one()
        self._ensure_all_components_generated()
        if not self.consolidated_generated:
            raise ValidationError(_('Generate Consolidated Award first, then download.'))
        return self._open_award_download_wizard(
            generate=False,
            export_scope='all',
            variant='consolidated',
            title=_('Download Consolidated Award (Full) / समेकित अवार्ड (पूर्ण) डाउनलोड करें'),
            simple_download_dialog=True,
        )

    def action_download_rr_full_award(self):
        self.ensure_one()
        self._ensure_all_components_generated()
        if not self.rr_generated:
            raise ValidationError(_('Generate R&R Award first, then download.'))
        return self._open_award_download_wizard(
            generate=False,
            export_scope='all',
            variant='rr',
            title=_('Download R&R Award (Full) / पुनर्वास अवार्ड (पूर्ण) डाउनलोड करें'),
            simple_download_dialog=True,
        )

    def get_award_village_scope_summary(self):
        """Village + component totals (Section 23, for summary export)."""
        self.ensure_one()
        land_sum = sum(
            float(g.get('paid_compensation', 0) or g.get('total_compensation', 0) or 0)
            for g in self.get_land_compensation_grouped_data()
        )
        tree_sum = sum(float(g.get('total', 0) or 0) for g in self.get_tree_compensation_grouped_data())
        struct_sum = sum(float(g.get('total', 0) or 0) for g in self.get_structure_compensation_grouped_data())
        v = self.village_id
        return {
            'village': v.name if v else '',
            'project': self.project_id.name if self.project_id else '',
            'tehsil': v.tehsil_id.name if v and v.tehsil_id else '',
            'district': v.district_id.name if v and v.district_id else '',
            'land_total': land_sum,
            'tree_total': tree_sum,
            'structure_total': struct_sum,
            'grand_total': land_sum + tree_sum + struct_sum,
        }

    def _action_download_excel_village_only(self):
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        import io
        try:
            import xlsxwriter
        except ImportError:
            raise ValidationError(_("Python library 'xlsxwriter' is not installed."))
        s = self.get_award_village_scope_summary()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Village')
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'border': 1})
        label_fmt = workbook.add_format({'border': 1, 'bold': True})
        cell_fmt = workbook.add_format({'border': 1})
        money_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0', 'align': 'right'})
        row = 0
        sheet.merge_range(row, 0, row, 2, 'SECTION 23 VILLAGE SUMMARY / धारा 23 ग्राम सारांश', title_fmt)
        row += 2
        rows = [
            ('Village / ग्राम', s['village'], False),
            ('Project / परियोजना', s['project'], False),
            ('Tehsil / तहसील', s['tehsil'], False),
            ('District / जिला', s['district'], False),
            ('Land total (₹) / भूमि कुल', s['land_total'], True),
            ('Trees total (₹) / वृक्ष कुल', s['tree_total'], True),
            ('Structure total (₹) / परिसम्पत्ति कुल', s['structure_total'], True),
            ('Grand total (₹) / कुल', s['grand_total'], True),
        ]
        for label, val, is_money in rows:
            sheet.write(row, 0, label, label_fmt)
            if is_money:
                sheet.write_number(row, 1, float(val or 0.0), money_fmt)
            else:
                sheet.write(row, 1, val or '', cell_fmt)
            row += 1
        sheet.set_column(0, 0, 38)
        sheet.set_column(1, 1, 28)
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()
        attachment = self.env['ir.attachment'].create({
            'name': f"Section23_Village_Summary_{self.village_id.name or self.name or 'Export'}.xlsx",
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_download_excel(self, export_scope='all'):
        """Alias to keep wizard and buttons on the same simulator-format excel."""
        self.ensure_one()
        return self.action_download_excel_components(export_scope=export_scope)

    def action_download_pdf_components(self, export_scope='all', include_cover_letter=False):
        """Download Section 23 PDF with selected section scope."""
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        scope = export_scope or self.env.context.get('bhu_export_scope') or 'all'
        if scope not in ('all', 'land', 'asset', 'tree'):
            scope = 'all'
        report_action = self._get_section23_report_action()
        return report_action.with_context(
            s23_pdf_scope=scope,
            s23_include_cover=bool(include_cover_letter),
        ).report_action(self)

    def _validate_for_generate(self, require_sales_sort_rate=True, allow_when_fully_generated=False):
        """Pre-checks for opening/running generate flow.

        ``require_sales_sort_rate`` keeps the generator strict on rate entry.
        """
        self.ensure_one()
        # Ensure missing rate fields are auto-filled from village master first.
        # User-edited non-zero values are preserved (force=False).
        self._sync_rate_fields_from_master(force=False)
        # Avoid flushing parent award row here (can cause concurrent update retries
        # during regenerate). Flush only child line buffers if present.
        if self.award_survey_line_ids:
            self.award_survey_line_ids.flush_recordset()
        if self.award_structure_line_ids:
            self.award_structure_line_ids.flush_recordset()
        if (not allow_when_fully_generated) and self.land_generated and self.tree_generated and self.asset_generated:
            raise ValidationError(_(
                'All section awards are already generated for this Project and Village. '
                'Use Download options instead of generating again.'
            ))
        if not self.project_id:
            raise ValidationError(_('Please select a project first.'))
        if not self.village_id:
            raise ValidationError(_('Please select a village first.'))
        if not (self.case_number or '').strip():
            raise ValidationError(_(
                'Please enter the Case Number / प्रकरण क्रमांक before generating the award.'
            ))
        if self._requires_section4_for_award_generate() and not self._get_section4_approval_date():
            raise ValidationError(_(
                'Section 4 notification is not approved yet for this project and village.\n'
                'Please get the Section 4 approved before creating the award.\n\n'
                'इस प्रोजेक्ट और गाँव के लिए धारा 4 की अधिसूचना अभी स्वीकृत नहीं हुई है।\n'
                'अवार्ड बनाने से पहले कृपया धारा 4 की स्वीकृति प्राप्त करें।'
            ))
        if not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        if not self.award_survey_line_ids:
            raise ValidationError(_(
                'No surveys found for this village. Cannot generate award.\n'
                'इस गाँव के लिए कोई स्वीकृत सर्वेक्षण नहीं मिला। अवार्ड उत्पन्न नहीं किया जा सकता।'
            ))
        missing_lines = self.award_survey_line_ids.filtered(lambda l: not l.land_type)
        if missing_lines:
            survey_names = ', '.join([line.survey_id.name for line in missing_lines if line.survey_id][:5])
            if len(missing_lines) > 5:
                survey_names += '...'
            raise ValidationError(_(
                'Please select type (Village/Residential) for all surveys before generating award.\n'
                'Missing type selection for surveys: %s'
            ) % survey_names)
        bad_struct = self.award_structure_line_ids.filtered(lambda l: not l.survey_id)
        if bad_struct:
            raise ValidationError(_(
                'Select a khasra for every structure line before generating the award, or remove empty lines.\n'
                'अवार्ड जेनरेट करने से पहले हर संरचना पंक्ति के लिए खसरा चुनें, या खाली पंक्तियाँ हटा दें।'
            ))
        if require_sales_sort_rate:
            rate = float(self.avg_three_year_sales_sort_rate or 0.0)
            if rate <= 0.0:
                raise ValidationError(_(
                    'Please enter विगत तीन वर्षों का औसत बिक्री छांट दर (must be greater than zero) '
                    'before generating the award.\n'
                    'अवार्ड जेनरेट करने से पहले यह दर दर्ज करें।'
                ))
        mr_rate = float(self.rate_master_main_road_ha or 0.0)
        bmr_rate = float(self.rate_master_other_road_ha or 0.0)
        if mr_rate <= 0.0 or bmr_rate <= 0.0:
            raise ValidationError(_(
                'Please enter both MR Rate and BMR Rate (greater than zero) before generating the award.\n'
                'अवार्ड जेनरेट करने से पहले MR Rate और BMR Rate दोनों दर्ज करें।'
            ))
        if self.is_urban:
            if not (self.urban_body_type or '').strip():
                raise ValidationError(_(
                    'For Urban awards, please select Urban Body Type before generating the award.\n'
                    'नगरीय अवार्ड के लिए जेनरेट करने से पहले Urban Body Type चुनना आवश्यक है।'
                ))
            mr_sqm = float(self.rate_master_main_road_sqm or 0.0)
            bmr_sqm = float(self.rate_master_other_road_sqm or 0.0)
            if mr_sqm <= 0.0 or bmr_sqm <= 0.0:
                raise ValidationError(_(
                    'For Urban awards, please enter both MR and BMR rates in square meter (greater than zero).\n'
                    'नगरीय अवार्ड के लिए MR और BMR दोनों वर्गमीटर दरें दर्ज करना आवश्यक है।'
                ))

    def action_generate_award(self):
        """Generate all section scopes without download prompt."""
        self.ensure_one()
        return self._generate_scope_without_download(
            export_scope='all',
            label=_('All sections generated. Full Standard/Consolidated/R&R downloads are now enabled.'),
        )

    def apply_generate_from_download_wizard(self, file_format, export_scope='all', include_cover_letter=False, generate_variant='standard'):
        """Called from bhu.award.download.wizard when Section 23 generate is confirmed."""
        self.ensure_one()
        _logger.warning(
            "[S23 GENERATE WIZARD START] award=%s id=%s scope=%s variant=%s format=%s",
            self.name, self.id, export_scope, generate_variant, file_format
        )

        self._validate_for_generate(require_sales_sort_rate=True)
        self._sync_award_structure_lines()
        self._refresh_award_line_items(export_scope=export_scope or 'all', log_khasra=True)

        variant = generate_variant or 'standard'
        if variant not in ('standard', 'consolidated', 'rr'):
            variant = 'standard'

        if variant == 'consolidated':
            self._ensure_all_components_generated()
            self.write({'is_generated': True, 'state': 'approved'})
            self.message_post(body=_("Consolidated award generated and auto-approved. / समेकित अवार्ड जेनरेट किया गया और स्वतः अनुमोदित हुआ।"))
            if file_format == 'excel':
                return self.action_download_consolidated_excel()
            return self.action_download_consolidated_pdf()

        if variant == 'rr':
            self._ensure_all_components_generated()
            self.write({'is_generated': True, 'state': 'approved'})
            self.message_post(body=_("R&R award generated and auto-approved. / पुनर्वास अवार्ड जेनरेट किया गया और स्वतः अनुमोदित हुआ।"))
            if file_format == 'excel':
                return self.action_download_rr_excel()
            return self.action_download_rr_pdf()

        if file_format == 'excel':
            self._mark_generated_scope(export_scope=export_scope or 'all')
            self.message_post(body=_("Section award generated. / संबंधित पत्रक जेनरेट किया गया।"))
            return self.action_download_excel_components(export_scope=export_scope or 'all')

        if file_format != 'pdf':
            raise ValidationError(_('Unsupported format for generate.'))

        scope = export_scope or 'all'
        if scope not in ('all', 'land', 'asset', 'tree'):
            scope = 'all'

        report_action = self._get_section23_report_action()
        pdf_result = report_action.sudo().with_context(
            s23_pdf_scope=scope,
            s23_include_cover=bool(include_cover_letter),
        )._render_qweb_pdf(
            report_action.id,
            [self.id],
            data={},
        )
        if pdf_result:
            pdf_data = pdf_result[0] if isinstance(pdf_result, (tuple, list)) else pdf_result
            if isinstance(pdf_data, bytes):
                filename = (
                    f"Section23_Award_"
                    f"{(self.village_id.name or '').replace(' ', '_')}_"
                    f"{datetime.now().strftime('%Y%m%d')}.pdf"
                )
                self.write({
                    'award_document': base64.b64encode(pdf_data),
                    'award_document_filename': filename,
                })
                self._mark_generated_scope(export_scope=scope)
                self.message_post(body=_("Section award generated. / संबंधित पत्रक जेनरेट किया गया।"))
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{self._name}/{self.id}/award_document/{filename}?download=true',
                    'target': 'self',
                }

        self._mark_generated_scope(export_scope=scope)
        self.message_post(body=_("Section award generated. / संबंधित पत्रक जेनरेट किया गया।"))
        return report_action.with_context(
            s23_pdf_scope=scope,
            s23_include_cover=bool(include_cover_letter),
        ).report_action(self)

    def _get_section23_report_action(self):
        """Get Section 23 report action with safe fallback when xmlid is missing."""
        self.ensure_one()
        try:
            return self.env.ref('bhukhadan_core.action_report_section23_award')
        except Exception:
            report_action = self.env['ir.actions.report'].search([
                ('model', '=', 'bhu.section23.award'),
                ('report_name', '=', 'bhukhadan_core.section23_award_report'),
                ('report_type', '=', 'qweb-pdf'),
            ], limit=1)
            if report_action:
                return report_action
            raise ValidationError(_(
                'Section 23 report action is missing. Please upgrade module "bhuarjan" '
                'to load report xml id: bhukhadan_core.action_report_section23_award'
            ))

    def _sync_award_structure_lines(self):
        """Link survey-level structure entries to this award."""
        self.ensure_one()
        survey_ids = self.award_survey_line_ids.mapped('survey_id').ids
        if not survey_ids:
            return
        structure_lines = self.env['bhu.award.structure.details'].search([
            ('survey_id', 'in', survey_ids),
            ('award_id', '!=', self.id),
        ])
        if structure_lines:
            structure_lines.write({'award_id': self.id})

    def _refresh_award_line_items(self, export_scope='all', log_khasra=False):
        """Persist generated line-items so users can review rows from DB later.

        Optimized: for section-wise generation, only refresh requested scope.
        """
        self.ensure_one()
        self.award_line_item_ids.unlink()
        scope = (export_scope or 'all').lower()
        if scope not in ('all', 'land', 'tree', 'asset'):
            scope = 'all'

        def _safe_amount(val):
            try:
                if val in (None, False, ''):
                    return 0.0
                if isinstance(val, str):
                    val = val.replace(',', '').replace('₹', '').strip()
                return float(val)
            except Exception:
                return 0.0

        line_vals = []
        land_rows = self.get_land_compensation_data() if scope in ('all', 'land') else []
        tree_rows = self.get_tree_compensation_data() if scope in ('all', 'tree') else []
        asset_rows = self.get_structure_compensation_data() if scope in ('all', 'asset') else []
        # Progress row count should reflect visible/logical rows for land (khasra-level),
        # not internal owner-split calculation entries.
        land_khasra_from_lines = set(
            filter(None, (self.award_survey_line_ids.mapped('khasra_number') if self.award_survey_line_ids else []))
        )
        if land_khasra_from_lines:
            land_progress_rows = len(land_khasra_from_lines)
        else:
            land_progress_rows = len({
                (r.get('khasra') or '').strip()
                for r in land_rows
                if (r.get('khasra') or '').strip()
            }) if land_rows else 0
        tree_progress_rows = len(tree_rows)
        asset_progress_rows = len(asset_rows)
        total_rows = land_progress_rows + tree_progress_rows + asset_progress_rows
        # Keep final progress room for cache/upload/status phases after rows are processed.
        tail_steps = 6
        total_units = (total_rows + tail_steps) if total_rows > 0 else tail_steps
        processed_rows = 0
        self._s23_set_loader_progress(
            done=0,
            total=total_units,
            label=_('Processing award rows...'),
            active=True,
            flush=True,
        )

        def _bump_progress(label_text):
            nonlocal processed_rows
            processed_rows += 1
            if processed_rows == total_rows or processed_rows % 5 == 0:
                self._s23_set_loader_progress(
                    done=processed_rows,
                    total=total_units,
                    label=label_text,
                    active=True,
                    flush=True,
                )

        if scope in ('all', 'land'):
            seen_land_khasra = set()
            for row in land_rows:
                khasra = row.get('khasra', '')
                line_vals.append((0, 0, {
                    'line_type': 'land',
                    'landowner_name': row.get('landowner_name', ''),
                    'khasra_number': khasra,
                    'original_area': row.get('original_area', 0.0) or 0.0,
                    'acquired_area': row.get('acquired_area', 0.0) or 0.0,
                    'is_within_distance': bool(row.get('is_within_distance')),
                    'irrigated': bool(row.get('irrigated')),
                    'unirrigated': bool(row.get('unirrigated')),
                    'is_diverted': bool(row.get('is_diverted')),
                    'guide_line_rate': row.get('guide_line_rate', 0.0) or 0.0,
                    'basic_value': row.get('basic_value', 0.0) or 0.0,
                    'market_value': row.get('market_value', 0.0) or 0.0,
                    'solatium': row.get('solatium', 0.0) or 0.0,
                    'interest': row.get('interest', 0.0) or 0.0,
                    'total_compensation': row.get('total_compensation', 0.0) or 0.0,
                    'rehab_policy_amount': row.get('rehab_policy_amount', 0.0) or 0.0,
                    'paid_compensation': row.get('paid_compensation', 0.0) or 0.0,
                    'remark': row.get('remark', '') or '',
                }))
                k_key = (khasra or '').strip()
                if k_key and k_key not in seen_land_khasra:
                    seen_land_khasra.add(k_key)
                    _bump_progress(_('Processing land rows...'))
            if log_khasra:
                _logger.warning(
                    "[S23 GENERATE][LAND] award=%s id=%s rows=%s calc_entries=%s total_amount=%.2f",
                    self.name,
                    self.id,
                    land_progress_rows,
                    len(land_rows),
                    sum(_safe_amount(r.get('total_compensation', 0.0)) for r in land_rows),
                )

        if scope in ('all', 'tree'):
            for row in tree_rows:
                khasra = row.get('khasra', '')
                line_vals.append((0, 0, {
                    'line_type': 'tree',
                    'landowner_name': row.get('landowner_name', ''),
                    'khasra_number': khasra,
                    'total_compensation': row.get('total', 0.0) or 0.0,
                    'remark': row.get('tree_type', '') or '',
                }))
                _bump_progress(_('Processing tree rows...'))
            if log_khasra:
                _logger.warning(
                    "[S23 GENERATE][TREE] award=%s id=%s rows=%s total_amount=%.2f",
                    self.name,
                    self.id,
                    len(tree_rows),
                    sum(_safe_amount(r.get('total', 0.0)) for r in tree_rows),
                )

        if scope in ('all', 'asset'):
            for row in asset_rows:
                khasra = row.get('asset_khasra', '')
                line_vals.append((0, 0, {
                    'line_type': 'structure',
                    'landowner_name': row.get('landowner_name', ''),
                    'khasra_number': khasra,
                    'acquired_area': row.get('total_area', 0.0) or 0.0,
                    'guide_line_rate': row.get('market_value', 0.0) or 0.0,
                    'solatium': row.get('solatium', 0.0) or 0.0,
                    'interest': row.get('interest', 0.0) or 0.0,
                    'total_compensation': row.get('total', 0.0) or 0.0,
                    'remark': row.get('asset_type', '') or '',
                }))
                _bump_progress(_('Processing asset rows...'))
            if log_khasra:
                _logger.warning(
                    "[S23 GENERATE][ASSET] award=%s id=%s rows=%s total_amount=%.2f",
                    self.name,
                    self.id,
                    len(asset_rows),
                    sum(_safe_amount(r.get('total', 0.0)) for r in asset_rows),
                )

        if line_vals:
            self.write({'award_line_item_ids': line_vals})
        self._s23_set_loader_progress(
            done=total_rows,
            total=total_units,
            label=_('Rows processed. Preparing documents...'),
            active=True,
            flush=True,
        )
