# -*- coding: utf-8 -*-

import base64

from odoo import api, fields, models, _


class DocumentVaultNavigator(models.Model):
    _name = 'bhu.document.vault.navigator'
    _description = 'Document Vault Navigator'

    name = fields.Char(string='Name', default='Document Vault Navigator')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, index=True)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग')
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना')
    village_id = fields.Many2one(
        'bhu.village',
        string='Village / ग्राम',
        domain="[('project_ids', 'in', project_id)]",
    )
    section_line_ids = fields.One2many(
        'bhu.document.vault.navigator.line',
        'navigator_id',
        string='Sections',
        copy=False,
    )
    step_display_line_ids = fields.One2many(
        'bhu.document.vault.navigator.line',
        'navigator_display_id',
        string='Step Display Lines',
        copy=False,
    )
    selected_document_id = fields.Many2one('bhu.document.vault', string='Selected Document')
    selected_attachment_id = fields.Many2one('ir.attachment', string='Selected Attachment')
    selected_source_model = fields.Char(string='Selected Source Model')
    selected_source_record_id = fields.Integer(string='Selected Source Record ID')
    selected_source_file_field = fields.Char(string='Selected Source File Field')
    selected_source_filename_field = fields.Char(string='Selected Source Filename Field')
    selected_document_file = fields.Binary(string='PDF Preview', compute='_compute_selected_preview', readonly=True)
    selected_document_filename = fields.Char(string='Filename', compute='_compute_selected_preview', readonly=True)
    selected_preview_revision = fields.Integer(
        string='Preview Revision',
        default=0,
        help='Incremented on each section/variant selection so the PDF iframe reloads.',
    )
    selected_document_hint = fields.Html(
        string='Preview Hint',
        compute='_compute_selected_document_hint',
        sanitize=False,
    )
    show_left_panel = fields.Boolean(string='Show Sections Panel', default=True)
    focused_step_no = fields.Integer(string='Focused Step')
    active_variant_line_id = fields.Integer(
        string='Active Variant Line ID',
        help='Plain ID reference (not a Many2one) so deleted lines never crash the viewer.',
    )
    show_variant_bar = fields.Boolean(compute='_compute_variant_ui')
    focused_variant_line_ids = fields.One2many(
        'bhu.document.vault.navigator.line',
        compute='_compute_focused_variant_line_ids',
        string='Focused Step Variants',
    )
    nav_stats_html = fields.Html(string='Navigator Stats', compute='_compute_nav_stats', sanitize=False)

    _FORM10_SOURCE_MODEL = 'bhu.docvault.form10'

    # Dashboard-aligned section order (matches unified_dashboard.js step cards).
    _DASHBOARD_ORDER_LARR = (
        'Surveys',
        '(Sec 4) Create SIA Team',
        '(Sec 4) Section 4 Notifications',
        'Expert Group',
        'Section 8',
        'Section 11 Notifications',
        '(Sec 15) Objections',
        'Section 18 R and R Scheme',
        '(Sec 19) Section 19 Notifications',
        'Sec 21 notice',
        'Section 23 Award',
        'Payment Voucher',
        'Payment File',
        'Payment Reconciliation',
    )
    _DASHBOARD_ORDER_COAL = (
        'Surveys (Coal Act)',
        '(Sec 4) CBA Notification',
        '(Sec 7) Land Schedule',
        '(Sec 8) Objection Decision',
        '(Sec 9) Declaration',
        'Land Records',
        'DRRC',
        'Asset Survey',
        'Compensation',
        'Award (Coal Act)',
        'Payment Voucher',
        'Payment File',
        'Payment Reconciliation',
    )
    _PAYMENT_SECTIONS = frozenset({'Payment Voucher', 'Payment File', 'Payment Reconciliation'})
    _PROJECT_LEVEL_MODELS = frozenset({
        'bhu.section4.notification',
        'bhu.expert.committee.report',
        'bhu.section8',
        'bhu.section18.rr.scheme',
    })

    @api.depends('focused_step_no', 'section_line_ids', 'section_line_ids.step_no')
    def _compute_variant_ui(self):
        for nav in self:
            step = nav.focused_step_no
            if not step:
                nav.show_variant_bar = False
                continue
            count = sum(
                1 for line in nav.section_line_ids
                if line.step_no == step and not line.is_step_display_row
            )
            nav.show_variant_bar = count > 1

    @api.depends('focused_step_no', 'section_line_ids', 'section_line_ids.step_no', 'section_line_ids.is_step_display_row')
    def _compute_focused_variant_line_ids(self):
        for nav in self:
            step = nav.focused_step_no
            if not step:
                nav.focused_variant_line_ids = self.env['bhu.document.vault.navigator.line']
                continue
            nav.focused_variant_line_ids = nav.section_line_ids.filtered(
                lambda line: line.step_no == step and not line.is_step_display_row
            )

    @api.depends('section_line_ids', 'section_line_ids.is_available', 'section_line_ids.is_step_display_row',
                 'section_line_ids.source_model', 'section_line_ids.source_record_id', 'section_line_ids.source_file_field',
                 'section_line_ids.attachment_id', 'section_line_ids.document_id')
    def _compute_nav_stats(self):
        for nav in self:
            steps = nav.section_line_ids.filtered('is_step_display_row')
            variants = nav.section_line_ids.filtered(lambda line: not line.is_step_display_row)
            step_count = len(steps)
            available = sum(1 for line in variants if line._line_is_available())
            total = len(variants)
            nav.nav_stats_html = _(
                '<div class="o_docvault_stats_bar">'
                '<span class="o_docvault_stat"><i class="fa fa-th-list"></i> %(steps)s steps</span>'
                '<span class="o_docvault_stat o_docvault_stat--ok"><i class="fa fa-file-pdf-o"></i> '
                '%(available)s / %(total)s documents ready</span>'
                '</div>'
            ) % {'steps': step_count, 'available': available, 'total': total}

    def _selection_vals(self, line):
        if not line or not line._line_is_available():
            return {
                'selected_document_id': False,
                'selected_attachment_id': False,
                'selected_source_model': False,
                'selected_source_record_id': False,
                'selected_source_file_field': False,
                'selected_source_filename_field': False,
            }
        if line.source_model == self._FORM10_SOURCE_MODEL:
            return {
                'selected_document_id': False,
                'selected_attachment_id': False,
                'selected_source_model': self._FORM10_SOURCE_MODEL,
                'selected_source_record_id': line.navigator_id.project_id.id if line.navigator_id.project_id else False,
                'selected_source_file_field': 'bulk_pdf',
                'selected_source_filename_field': False,
            }
        return {
            'selected_document_id': line.document_id.id if line.document_id else False,
            'selected_attachment_id': line.attachment_id.id if line.attachment_id else False,
            'selected_source_model': line.source_model or False,
            'selected_source_record_id': line.source_record_id or False,
            'selected_source_file_field': line.source_file_field or False,
            'selected_source_filename_field': line.source_filename_field or False,
        }

    def _apply_line_selection(self, line):
        self.ensure_one()
        if self.env.context.get('docvault_skip_selection_write'):
            for key, value in self._selection_vals(line).items():
                self[key] = value
            return
        self.with_context(docvault_skip_selection_write=True).write(self._selection_vals(line))

    def _get_active_variant_line(self):
        self.ensure_one()
        line_id = self.active_variant_line_id or 0
        if not line_id:
            return self.env['bhu.document.vault.navigator.line']
        line = self.env['bhu.document.vault.navigator.line'].browse(line_id)
        if not line.exists() or line.navigator_id.id != self.id:
            return self.env['bhu.document.vault.navigator.line']
        return line

    def _step_variant_lines(self, step_no):
        self.ensure_one()
        variants = self.section_line_ids.filtered(
            lambda line: line.step_no == step_no and not line.is_step_display_row
        )
        if not variants:
            variants = self.section_line_ids.filtered(lambda line: line.step_no == step_no)
        return variants

    def _notify_missing_document_nav(self, message=None):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Not Available'),
                'message': message or _(
                    'This section is not generated yet, or no PDF is available for this section.'
                ),
                'type': 'warning',
                'sticky': False,
            },
        }

    def _match_variant_label(self, line, label):
        return (line.variant_label or '').strip().lower() == (label or '').strip().lower()

    def _apply_step_selection(self, step_no, variant_label=None):
        """Select a step/variant by step number — never relies on stale client line IDs."""
        self.ensure_one()
        self._sanitize_stale_selection()
        step_no = int(step_no)
        variants = self._step_variant_lines(step_no)
        if not variants:
            return self._notify_missing_document_nav()
        preferred = self.env['bhu.document.vault.navigator.line']
        if variant_label:
            preferred = variants.filtered(
                lambda line: self._match_variant_label(line, variant_label)
            )[:1]
        if not preferred:
            active = self._get_active_variant_line()
            if active and active.step_no == step_no and active in variants and active._line_is_available():
                preferred = active
        if not preferred:
            preferred = self._pick_default_line(variants)
        if not preferred or not preferred._line_is_available():
            self.with_context(docvault_skip_selection_write=True).write({
                'focused_step_no': step_no,
                'selected_preview_revision': (self.selected_preview_revision or 0) + 1,
                **self._selection_vals(False),
            })
            self._clear_active_variant_line_id()
            return self._notify_missing_document_nav()
        pick = preferred
        write_vals = {
            'focused_step_no': step_no,
            'selected_preview_revision': (self.selected_preview_revision or 0) + 1,
            'active_variant_line_id': pick.id,
            **self._selection_vals(pick),
        }
        self.with_context(docvault_skip_selection_write=True).write(write_vals)
        return True

    def action_select_step_by_step_no(self, step_no):
        self.ensure_one()
        result = self._apply_step_selection(step_no)
        return result if isinstance(result, dict) else True

    def action_select_variant_label(self, step_no, variant_label):
        self.ensure_one()
        result = self._apply_step_selection(step_no, variant_label=variant_label or False)
        return result if isinstance(result, dict) else True

    def _clear_active_variant_line_id(self):
        """ORM writes False as 0 for Integer; use SQL NULL (legacy FK safe)."""
        ids = self.ids
        if not ids:
            return
        self.env.cr.execute("""
            UPDATE bhu_document_vault_navigator
               SET active_variant_line_id = NULL
             WHERE id IN %s
        """, [tuple(ids)])
        self.invalidate_recordset(['active_variant_line_id'])

    def _normalize_active_variant_line_val(self, line_id, navigator_ids=None):
        if not line_id:
            return None
        line = self.env['bhu.document.vault.navigator.line'].browse(int(line_id))
        if not line.exists():
            return None
        if navigator_ids and line.navigator_id.id not in navigator_ids:
            return None
        return line.id

    def write(self, vals):
        vals = dict(vals)
        clear_active = False
        active_line_touched = 'active_variant_line_id' in vals
        if active_line_touched:
            normalized = self._normalize_active_variant_line_val(
                vals['active_variant_line_id'], self.ids,
            )
            if normalized is None:
                clear_active = True
                del vals['active_variant_line_id']
            else:
                vals['active_variant_line_id'] = normalized
        res = super().write(vals) if vals else True
        if clear_active:
            self._clear_active_variant_line_id()
        if self.env.context.get('docvault_skip_selection_write'):
            return res
        if active_line_touched or clear_active:
            for nav in self:
                line = nav._get_active_variant_line()
                if line and line._line_is_available():
                    nav._apply_line_selection(line)
                else:
                    nav._apply_line_selection(False)
        return res

    def _sanitize_stale_selection(self):
        """Clear broken Many2one refs left after section lines are rebuilt."""
        ids = self.ids
        if not ids:
            return
        self.env.cr.execute("""
            UPDATE bhu_document_vault_navigator AS n
               SET active_variant_line_id = NULL
             WHERE n.id IN %s
               AND n.active_variant_line_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1
                     FROM bhu_document_vault_navigator_line AS l
                    WHERE l.id = n.active_variant_line_id
               )
        """, [tuple(ids)])
        self.invalidate_recordset(['active_variant_line_id'])

    def read(self, fields=None, load='_classic_read'):
        if self.ids and (fields is None or 'active_variant_line_id' in fields):
            self._sanitize_stale_selection()
        return super().read(fields=fields, load=load)

    def _sync_display_line_links(self):
        """Ensure one display row per step is linked for the left panel list."""
        for nav in self:
            for line in nav.section_line_ids.filtered('is_step_display_row'):
                if line.navigator_display_id.id != nav.id:
                    line.navigator_display_id = nav.id

    def action_toggle_left_panel(self):
        for rec in self:
            rec.show_left_panel = not rec.show_left_panel
        return True

    def _form10_surveys(self):
        self.ensure_one()
        if not (self.project_id and self.village_id):
            return self.env['bhu.survey']
        return self.env['bhu.survey'].sudo().search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', '!=', 'rejected'),
        ], order='id asc')

    def _render_form10_pdf_for_scope(self):
        self.ensure_one()
        surveys = self._form10_surveys()
        if not surveys:
            return False, False
        report = self.env.ref('bhukhadan_core.action_report_form10_bulk_table').sudo()
        pdf_content, _report_type = report._render_qweb_pdf(report.report_name, res_ids=surveys.ids)
        export_utils = self.env.get('form10.export.utils')
        if export_utils:
            filename = export_utils.sudo().generate_form10_filename(surveys)
        else:
            filename = 'Form10_%s_%s.pdf' % (
                (self.project_id.name or 'project').replace(' ', '_'),
                (self.village_id.name or 'village').replace(' ', '_'),
            )
        return pdf_content, filename

    @api.depends(
        'selected_document_id',
        'selected_attachment_id',
        'selected_source_model',
        'selected_source_record_id',
        'selected_source_file_field',
        'selected_source_filename_field',
        'project_id',
        'village_id',
    )
    def _compute_selected_preview(self):
        for rec in self:
            rec.selected_document_file = False
            rec.selected_document_filename = False
            if rec.selected_document_id:
                rec.selected_document_file = rec.selected_document_id.document_file
                rec.selected_document_filename = rec.selected_document_id.document_filename
            elif rec.selected_attachment_id:
                rec.selected_document_file = rec.selected_attachment_id.datas
                rec.selected_document_filename = rec.selected_attachment_id.name
            elif rec.selected_source_model == self._FORM10_SOURCE_MODEL:
                pdf_bytes, filename = rec._render_form10_pdf_for_scope()
                if pdf_bytes:
                    rec.selected_document_file = base64.b64encode(pdf_bytes)
                    rec.selected_document_filename = filename
            elif rec.selected_source_model and rec.selected_source_record_id and rec.selected_source_file_field:
                src = self.env[rec.selected_source_model].sudo().browse(rec.selected_source_record_id)
                if src.exists():
                    rec.selected_document_file = src[rec.selected_source_file_field]
                    if rec.selected_source_filename_field:
                        rec.selected_document_filename = src[rec.selected_source_filename_field]
                    if not rec.selected_document_filename:
                        rec.selected_document_filename = '%s_%s.pdf' % (rec.selected_source_model.replace('.', '_'), rec.selected_source_record_id)

    @api.depends('selected_document_id', 'selected_attachment_id', 'selected_source_model', 'selected_source_record_id', 'selected_source_file_field')
    def _compute_selected_document_hint(self):
        for rec in self:
            has_preview = bool(
                rec.selected_document_id
                or rec.selected_attachment_id
                or rec.selected_source_model == self._FORM10_SOURCE_MODEL
                or (rec.selected_source_model and rec.selected_source_record_id and rec.selected_source_file_field)
            )
            if has_preview:
                rec.selected_document_hint = ''
            else:
                rec.selected_document_hint = _(
                    '<div class="o_docvault_empty_hint">'
                    '<div class="o_docvault_empty_icon"><i class="fa fa-file-pdf-o"></i></div>'
                    '<h3>Select a workflow section</h3>'
                    '<p>Choose a step from the left panel. The signed PDF for that section will open here.</p>'
                    '<div class="o_docvault_empty_tip"><i class="fa fa-hand-o-left"></i> Click any section row to preview</div>'
                    '</div>'
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._apply_default_scope_if_needed()
            rec._refresh_section_lines()
        return records

    def _apply_default_scope_if_needed(self):
        self.ensure_one()
        # Keep department aligned with selected project.
        if self.project_id and self.project_id.department_id:
            self.department_id = self.project_id.department_id.id

        # If project is selected but village is missing, use the first village of that project.
        if self.project_id and not self.village_id and self.project_id.village_ids:
            self.village_id = self.project_id.village_ids[0].id

        # If both are present, scope is ready.
        if self.project_id and self.village_id:
            return

        # Prefer latest Section 23 award scope (primary generated source).
        latest_award = self.env['bhu.section23.award'].search([], order='create_date desc, id desc', limit=1)
        if latest_award and latest_award.project_id and latest_award.village_id:
            self.department_id = latest_award.project_id.department_id.id if latest_award.project_id.department_id else False
            self.project_id = latest_award.project_id.id
            self.village_id = latest_award.village_id.id
            return

        # Secondary fallback: latest manual document-vault row if available.
        latest_doc = self.env['bhu.document.vault'].search([], order='signed_date desc, create_date desc', limit=1)
        if latest_doc and latest_doc.project_id and latest_doc.village_id:
            self.department_id = latest_doc.project_id.department_id.id if latest_doc.project_id.department_id else False
            self.project_id = latest_doc.project_id.id
            self.village_id = latest_doc.village_id.id
            return

        # Fallback to first available project having villages.
        fallback_project = self.env['bhu.project'].search([('village_ids', '!=', False)], order='id asc', limit=1)
        if fallback_project:
            self.department_id = fallback_project.department_id.id if fallback_project.department_id else False
            self.project_id = fallback_project.id
            self.village_id = fallback_project.village_ids[:1].id or False

    @api.onchange('department_id')
    def _onchange_department_id(self):
        self.project_id = False
        self.village_id = False
        self.focused_step_no = False
        self.active_variant_line_id = False
        self.selected_document_id = False
        self.selected_attachment_id = False
        self.selected_source_model = False
        self.selected_source_record_id = False
        self.selected_source_file_field = False
        self.selected_source_filename_field = False
        self.section_line_ids = [(5, 0, 0)]
        if self.department_id:
            return {'domain': {'project_id': [('department_id', '=', self.department_id.id)], 'village_id': []}}
        return {'domain': {'project_id': [], 'village_id': []}}

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.project_id.department_id:
            self.department_id = self.project_id.department_id.id
        self.village_id = False
        self.focused_step_no = False
        self.active_variant_line_id = False
        self.selected_document_id = False
        self.selected_attachment_id = False
        self.selected_source_model = False
        self.selected_source_record_id = False
        self.selected_source_file_field = False
        self.selected_source_filename_field = False
        self.section_line_ids = [(5, 0, 0)]
        project_domain = []
        if self.department_id:
            project_domain.append(('department_id', '=', self.department_id.id))
        village_domain = [('id', 'in', self.project_id.village_ids.ids)] if self.project_id and self.project_id.village_ids else []
        return {'domain': {'project_id': project_domain, 'village_id': village_domain}}

    @api.onchange('village_id')
    def _onchange_village_id(self):
        self.focused_step_no = False
        self.active_variant_line_id = False
        self.selected_document_id = False
        self.selected_attachment_id = False
        self.selected_source_model = False
        self.selected_source_record_id = False
        self.selected_source_file_field = False
        self.selected_source_filename_field = False
        self.section_line_ids = [(5, 0, 0)]

    @api.model
    def action_open_navigator(self):
        navigator = self.search([('user_id', '=', self.env.user.id)], limit=1, order='id desc')
        if not navigator:
            navigator = self.create({'user_id': self.env.user.id})
        navigator._sanitize_stale_selection()
        ctx = self.env.context
        scope_vals = {}
        if ctx.get('active_department_id'):
            scope_vals['department_id'] = int(ctx['active_department_id'])
        if ctx.get('active_project_id'):
            scope_vals['project_id'] = int(ctx['active_project_id'])
        if ctx.get('active_village_id'):
            scope_vals['village_id'] = int(ctx['active_village_id'])
        if scope_vals:
            if 'department_id' not in scope_vals and scope_vals.get('project_id'):
                project = self.env['bhu.project'].browse(scope_vals['project_id'])
                if project.exists() and project.department_id:
                    scope_vals['department_id'] = project.department_id.id
            navigator.write(scope_vals)
        else:
            if navigator.project_id and navigator.project_id.department_id:
                navigator.department_id = navigator.project_id.department_id.id
            navigator._apply_default_scope_if_needed()
        navigator._refresh_section_lines()
        return navigator._action_open_self()

    def _action_open_self(self):
        self.ensure_one()
        try:
            view_id = self.env.ref('bhukhadan_core.view_document_vault_navigator_form').id
        except Exception:
            view_id = False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Document Vault Navigator'),
            'res_model': 'bhu.document.vault.navigator',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_id': self.id,
            'target': 'current',
            'context': {'create': False, 'delete': False},
        }

    def action_refresh_sections(self):
        self.ensure_one()
        self.write({
            'department_id': self.department_id.id,
            'project_id': self.project_id.id,
            'village_id': self.village_id.id,
        })
        self._sanitize_stale_selection()
        self._refresh_section_lines()
        return self._action_open_self()

    def action_open_selected_document(self):
        self.ensure_one()
        if self.selected_document_id:
            return self.selected_document_id.action_preview()
        if self.selected_attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s' % self.selected_attachment_id.id,
                'target': 'new',
            }
        if self.selected_source_model and self.selected_source_record_id and self.selected_source_file_field:
            src = self.env[self.selected_source_model].sudo().browse(self.selected_source_record_id)
            if src.exists() and src[self.selected_source_file_field]:
                filename = src[self.selected_source_filename_field] if self.selected_source_filename_field else 'document.pdf'
                return {
                    'type': 'ir.actions.act_url',
                    'url': '/web/content/%s/%s/%s/%s' % (
                        self.selected_source_model,
                        src.id,
                        self.selected_source_file_field,
                        filename or 'document.pdf',
                    ),
                    'target': 'new',
                }
        return False

    def _get_latest_cached_attachment(self, res_model, res_ids, name_like):
        """Generic cached attachment lookup used by navigator."""
        self.ensure_one()
        if not res_ids:
            return False
        return self.env['ir.attachment'].search([
            ('res_model', '=', res_model),
            ('res_id', 'in', res_ids),
            ('name', 'ilike', name_like),
            ('type', '=', 'binary'),
        ], order='create_date desc, id desc', limit=1)

    def _get_latest_award_cache_attachment(self, scope='all', variant='standard'):
        """Read latest generated award cache (currently Section 23 format)."""
        self.ensure_one()
        awards = self.env['bhu.section23.award'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
        ], order='create_date desc')
        if not awards:
            return False
        var = (variant or 'standard').lower()
        scp = (scope or 'all').lower()
        key_like = "s23_cache::%s::%s::pdf" % (var, scp)
        att = self.env['ir.attachment'].search([
            ('res_model', '=', 'bhu.section23.award'),
            ('res_id', 'in', awards.ids),
            ('description', 'ilike', key_like),
            ('type', '=', 'binary'),
        ], order='create_date desc, id desc', limit=1)
        if att:
            return att
        # Backward compatibility for older technical names.
        legacy_like = "S23_CACHE__%s__%s__pdf__" % (var, scp)
        return self._get_latest_cached_attachment('bhu.section23.award', awards.ids, legacy_like)

    def _get_latest_payment_attachment(self):
        self.ensure_one()
        payments = self.env['bhu.payment.file'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
        ], order='generation_date desc, create_date desc')
        if not payments:
            return False
        # Prefer PDF attachment if any external process has uploaded it.
        att = self.env['ir.attachment'].search([
            ('res_model', '=', 'bhu.payment.file'),
            ('res_id', 'in', payments.ids),
            ('mimetype', 'ilike', 'pdf'),
            ('type', '=', 'binary'),
        ], order='create_date desc, id desc', limit=1)
        if att:
            return att
        # Fallback to generated xlsx attachment if present.
        return self.env['ir.attachment'].search([
            ('res_model', '=', 'bhu.payment.file'),
            ('res_id', 'in', payments.ids),
            ('type', '=', 'binary'),
        ], order='create_date desc, id desc', limit=1)

    def _get_allowed_section_names(self):
        self.ensure_one()
        if not self.project_id or not self.project_id.law_master_id:
            return []
        return list(self.project_id.law_master_id.section_ids.mapped('name'))

    def _get_dashboard_section_order(self):
        self.ensure_one()
        allowed = set(self._get_allowed_section_names())
        if '(Sec 4) CBA Notification' in allowed:
            template = self._DASHBOARD_ORDER_COAL
        else:
            template = self._DASHBOARD_ORDER_LARR
        return [
            name for name in template
            if name in self._PAYMENT_SECTIONS or name in allowed
        ]

    def _line_sort_key(self, line):
        return (line.step_no or 0, line.section_label or '', line.variant_label or '')

    def _pick_default_line(self, lines):
        if not lines:
            return self.env['bhu.document.vault.navigator.line']
        available = [line for line in lines if line._line_is_available()]
        pool = available or list(lines)
        return min(pool, key=self._line_sort_key)

    def _finalize_section_line_selection(self, lines):
        self.ensure_one()
        line_list = list(lines) if lines else []
        if not line_list:
            self.with_context(docvault_skip_selection_write=True).write({
                'focused_step_no': False,
                **self._selection_vals(False),
            })
            self._clear_active_variant_line_id()
            return
        form10_lines = [
            line for line in line_list
            if line.step_no == 1 and not line.is_step_display_row and line._line_is_available()
        ]
        if form10_lines:
            preferred = form10_lines[0]
            pick = preferred
        else:
            content_lines = [line for line in line_list if not line.is_step_display_row]
            first_line = self._pick_default_line(content_lines or line_list)
            step_variants = [
                line for line in line_list
                if line.step_no == first_line.step_no and not line.is_step_display_row
            ] or [line for line in line_list if line.step_no == first_line.step_no]
            preferred = self._pick_default_line(step_variants)
            pick = preferred if preferred and preferred._line_is_available() else False
        safe_preferred = preferred if preferred and preferred.exists() else self.env['bhu.document.vault.navigator.line']
        self.with_context(docvault_skip_selection_write=True).write({
            'focused_step_no': safe_preferred.step_no if safe_preferred else False,
            **self._selection_vals(pick if pick and pick.exists() else False),
        })
        if safe_preferred:
            self.with_context(docvault_skip_selection_write=True).write({
                'active_variant_line_id': safe_preferred.id,
            })
        else:
            self._clear_active_variant_line_id()

    def _append_step_display_row(self, commands, step, seen_steps, section_label):
        """Left-panel summary row only (not a PDF variant)."""
        if step in seen_steps:
            return
        seen_steps.add(step)
        icon, theme = self.env['bhu.document.vault.navigator.line']._section_style_for_label(section_label)
        commands.append((0, 0, {
            'step_no': step,
            'section_label': section_label,
            'variant_label': False,
            'step_label': _("Step %s") % step,
            'section_icon': icon,
            'section_theme': theme,
            'document_id': False,
            'attachment_id': False,
            'signed_date': False,
            'document_type': False,
            'source_model': False,
            'source_record_id': False,
            'source_file_field': False,
            'source_filename_field': False,
            'document_count': 0,
            'is_available': False,
            'is_step_display_row': True,
            'navigator_display_id': self.id,
        }))

    def _variant_line_vals(self, step, section_label, variant_label=False):
        """PDF variant row — never shown as the left-panel step card."""
        icon, theme = self.env['bhu.document.vault.navigator.line']._section_style_for_label(section_label)
        return {
            'step_no': step,
            'section_label': section_label,
            'variant_label': variant_label or False,
            'step_label': _("Step %s") % step,
            'section_icon': icon,
            'section_theme': theme,
            'document_id': False,
            'attachment_id': False,
            'signed_date': False,
            'document_type': False,
            'source_model': False,
            'source_record_id': False,
            'source_file_field': False,
            'source_filename_field': False,
            'is_step_display_row': False,
            'navigator_display_id': False,
        }

    def _sync_display_row_stats(self):
        """Update display-row doc counts from sibling variant rows."""
        for nav in self:
            for display in nav.section_line_ids.filtered('is_step_display_row'):
                variants = nav.section_line_ids.filtered(
                    lambda line: line.step_no == display.step_no and not line.is_step_display_row
                )
                for variant in variants:
                    avail = variant._line_is_available()
                    if variant.is_available != avail:
                        variant.write({'is_available': avail})
                available = sum(1 for variant in variants if variant._line_is_available())
                display.write({
                    'document_count': available,
                    'is_available': bool(available),
                })

    def _display_flag_for_step(self, step, seen_steps):
        if step in seen_steps:
            return False
        seen_steps.add(step)
        return True

    def _base_line_vals(self, step, section_label, variant_label, seen_steps):
        is_display = self._display_flag_for_step(step, seen_steps)
        icon, theme = self.env['bhu.document.vault.navigator.line']._section_style_for_label(section_label)
        vals = {
            'step_no': step,
            'section_label': section_label,
            'variant_label': variant_label or False,
            'step_label': _("Step %s") % step,
            'section_icon': icon,
            'section_theme': theme,
            'document_id': False,
            'attachment_id': False,
            'signed_date': False,
            'document_type': False,
            'source_model': False,
            'source_record_id': False,
            'source_file_field': False,
            'source_filename_field': False,
            'is_step_display_row': is_display,
            'navigator_display_id': self.id if is_display else False,
        }
        return vals

    def _get_latest_workflow_record(self, model_name):
        self.ensure_one()
        Model = self.env[model_name].sudo()
        if model_name == 'bhu.sia.team':
            base_domain = [('project_id', '=', self.project_id.id)]
            rec = Model.search(
                base_domain + [
                    '|',
                    ('village_id', '=', self.village_id.id),
                    ('village_ids', 'in', self.village_id.id),
                ],
                order='create_date desc, id desc',
                limit=1,
            )
            if not rec:
                # SIA teams are usually project-scoped even when village is unset on the record.
                rec = Model.search(base_domain, order='create_date desc, id desc', limit=1)
            return rec
        if model_name in self._PROJECT_LEVEL_MODELS:
            return Model.search([
                ('project_id', '=', self.project_id.id),
            ], order='create_date desc, id desc', limit=1)
        return Model.search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
        ], order='create_date desc, id desc', limit=1)

    def _workflow_line_vals(self, step, section_label, variant_label, model_name, file_field, filename_field, seen_steps):
        rec = self._get_latest_workflow_record(model_name)
        has_file = bool(rec and rec.exists() and rec[file_field])
        vals = self._variant_line_vals(step, section_label, variant_label)
        vals.update({
            'document_count': 1 if has_file else 0,
            'is_available': has_file,
            'source_model': model_name if rec else False,
            'source_record_id': rec.id if rec else False,
            'source_file_field': file_field if rec else False,
            'source_filename_field': filename_field if rec else False,
        })
        return vals

    def _attachment_line_vals(self, step, section_label, variant_label, attachment, seen_steps, doc_type=False):
        vals = self._variant_line_vals(step, section_label, variant_label)
        vals.update({
            'document_type': doc_type or False,
            'attachment_id': attachment.id if attachment else False,
            'document_count': 1 if attachment else 0,
            'is_available': bool(attachment),
        })
        return vals

    def _append_form10_step(self, commands, step, seen_steps):
        self._append_step_display_row(commands, step, seen_steps, _('Form 10'))
        surveys = self._form10_surveys()
        survey_count = len(surveys)
        vals = self._variant_line_vals(step, _('Form 10'), _('Bulk PDF'))
        vals.update({
            'document_count': survey_count,
            'is_available': bool(survey_count),
            'source_model': self._FORM10_SOURCE_MODEL if survey_count else False,
            'source_record_id': self.project_id.id if survey_count else False,
            'source_file_field': 'bulk_pdf',
            'source_filename_field': False,
        })
        commands.append((0, 0, vals))

    def _append_signed_workflow_step(self, commands, step, seen_steps, section_label, model_name, collector=True):
        self._append_step_display_row(commands, step, seen_steps, section_label)
        commands.append((0, 0, self._workflow_line_vals(
            step, section_label, _('SDM PDF'), model_name,
            'sdm_signed_file', 'sdm_signed_filename', seen_steps,
        )))
        if collector:
            commands.append((0, 0, self._workflow_line_vals(
                step, section_label, _('Collector PDF'), model_name,
                'collector_signed_file', 'collector_signed_filename', seen_steps,
            )))

    def _append_binary_workflow_step(self, commands, step, seen_steps, section_label, model_name, file_field, filename_field):
        self._append_step_display_row(commands, step, seen_steps, section_label)
        rec = self._get_latest_workflow_record(model_name)
        has_file = bool(rec and rec.exists() and rec[file_field])
        vals = self._variant_line_vals(step, section_label, False)
        vals.update({
            'document_count': 1 if has_file else 0,
            'is_available': has_file,
            'source_model': model_name if rec else False,
            'source_record_id': rec.id if rec else False,
            'source_file_field': file_field if rec else False,
            'source_filename_field': filename_field if rec else False,
        })
        commands.append((0, 0, vals))

    def _append_section23_award_step(self, commands, step, seen_steps):
        section_label = _('Section 23 Award')
        self._append_step_display_row(commands, step, seen_steps, section_label)
        s23_defs = [
            ('section23_land_award', _('Land Award'), 'land', 'standard'),
            ('section23_tree_award', _('Tree Award'), 'tree', 'standard'),
            ('section23_asset_award', _('Asset Award'), 'asset', 'standard'),
            ('section23_consolidated_award', _('Consolidated Award'), 'all', 'consolidated'),
            ('section23_rr_award', _('R&R Award'), 'all', 'rr'),
        ]
        for doc_type, variant_label, scope, variant in s23_defs:
            attachment = self._get_latest_award_cache_attachment(scope=scope, variant=variant)
            commands.append((0, 0, self._attachment_line_vals(
                step, section_label, variant_label, attachment, seen_steps, doc_type=doc_type,
            )))

    def _append_payment_file_step(self, commands, step, seen_steps):
        self._append_step_display_row(commands, step, seen_steps, _('Payment File'))
        payments = self.env['bhu.payment.file'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
        ], order='generation_date desc, create_date desc, id desc')
        if payments:
            for payment in payments:
                attachment = self._payment_attachments_for_record(payment)
                label = payment.display_name or _('Payment File %s') % payment.id
                commands.append((0, 0, self._attachment_line_vals(
                    step, _('Payment File'), label, attachment, seen_steps,
                )))
        else:
            commands.append((0, 0, self._attachment_line_vals(
                step, _('Payment File'), _('Payment PDF'), False, seen_steps,
            )))

    def _section_vault_builders(self):
        return {
            'Surveys': lambda nav, cmds, step, seen: nav._append_form10_step(cmds, step, seen),
            'Payment Voucher': None,
            'Payment Reconciliation': None,
            '(Sec 4) Create SIA Team': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('SIA Team'), 'bhu.sia.team'),
            '(Sec 4) Section 4 Notifications': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Section 4'), 'bhu.section4.notification'),
            '(Sec 4) CBA Notification': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Section 4 (Coal)'), 'bhu.section4.notification'),
            'Expert Group': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Expert Group'), 'bhu.expert.committee.report'),
            'Section 8': lambda nav, cmds, step, seen: nav._append_binary_workflow_step(
                cmds, step, seen, _('Section 8'), 'bhu.section8', 'attachment_file', 'attachment_filename'),
            '(Sec 8) Objection Decision': lambda nav, cmds, step, seen: nav._append_binary_workflow_step(
                cmds, step, seen, _('Section 8 (Coal)'), 'bhu.section8', 'attachment_file', 'attachment_filename'),
            '(Sec 9) Declaration': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Section 9'), 'bhu.section9.notification'),
            'Section 11 Notifications': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Section 11'), 'bhu.section11.preliminary.report'),
            '(Sec 15) Objections': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Section 15 Objections'), 'bhu.section15.objection'),
            'Section 18 R and R Scheme': lambda nav, cmds, step, seen: nav._append_binary_workflow_step(
                cmds, step, seen, _('Section 18 R&R Scheme'), 'bhu.section18.rr.scheme', 'scheme_file', 'scheme_filename'),
            '(Sec 19) Section 19 Notifications': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Section 19'), 'bhu.section19.notification'),
            'Sec 21 notice': lambda nav, cmds, step, seen: nav._append_signed_workflow_step(
                cmds, step, seen, _('Section 21'), 'bhu.section21.notification'),
            'Section 23 Award': lambda nav, cmds, step, seen: nav._append_section23_award_step(cmds, step, seen),
            'Award (Coal Act)': lambda nav, cmds, step, seen: nav._append_section23_award_step(cmds, step, seen),
            'Payment File': lambda nav, cmds, step, seen: nav._append_payment_file_step(cmds, step, seen),
        }

    def _payment_attachments_for_record(self, payment):
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'bhu.payment.file'),
            ('res_id', '=', payment.id),
            ('type', '=', 'binary'),
        ], order='create_date desc, id desc')
        pdf = attachments.filtered(lambda a: (a.mimetype or '').lower().find('pdf') >= 0)[:1]
        return pdf or attachments[:1]

    def _refresh_section_lines(self):
        self.ensure_one()
        self._sanitize_stale_selection()
        self._clear_active_variant_line_id()
        self.section_line_ids = [(5, 0, 0)]
        if not (self.project_id and self.village_id):
            return

        builders = self._section_vault_builders()
        commands = []
        seen_steps = set()

        # Step 1 is always Form 10 (Surveys), regardless of law-master ordering.
        self._append_form10_step(commands, 1, seen_steps)

        step = 2
        for section_name in self._get_dashboard_section_order():
            if section_name == 'Surveys':
                continue
            builder = builders.get(section_name)
            if builder:
                builder(self, commands, step, seen_steps)
            step += 1

        self.section_line_ids = commands
        self._sync_display_line_links()
        self._sync_display_row_stats()
        line_list = list(self.section_line_ids)
        available_ids = [line.document_id.id for line in line_list if line.document_id]
        if self.selected_document_id and self.selected_document_id.id not in available_ids:
            self.selected_document_id = False
        available_attachment_ids = [line.attachment_id.id for line in line_list if line.attachment_id]
        if self.selected_attachment_id and self.selected_attachment_id.id not in available_attachment_ids:
            self.selected_attachment_id = False
        available_sources = [
            line for line in line_list
            if line.is_available and (
                line.source_model == self._FORM10_SOURCE_MODEL
                or (line.source_model and line.source_record_id and line.source_file_field)
            )
        ]
        if self.selected_source_model == self._FORM10_SOURCE_MODEL:
            if not any(line.source_model == self._FORM10_SOURCE_MODEL for line in available_sources):
                self.selected_source_model = False
                self.selected_source_record_id = False
                self.selected_source_file_field = False
                self.selected_source_filename_field = False
        elif self.selected_source_model and self.selected_source_record_id and self.selected_source_file_field:
            match = [
                line for line in available_sources
                if line.source_model == self.selected_source_model
                and line.source_record_id == self.selected_source_record_id
                and line.source_file_field == self.selected_source_file_field
            ]
            if not match:
                self.selected_source_model = False
                self.selected_source_record_id = False
                self.selected_source_file_field = False
                self.selected_source_filename_field = False
        self._finalize_section_line_selection(line_list)


class DocumentVaultNavigatorLine(models.Model):
    _name = 'bhu.document.vault.navigator.line'
    _description = 'Document Vault Navigator Line'
    _order = 'step_no, section_label, variant_label'

    navigator_id = fields.Many2one('bhu.document.vault.navigator', required=True, ondelete='cascade')
    navigator_display_id = fields.Many2one(
        'bhu.document.vault.navigator',
        string='Navigator Display',
        ondelete='cascade',
        index=True,
    )
    step_no = fields.Integer(string='Step')
    step_label = fields.Char(string='Step Label')
    variant_label = fields.Char(string='Variant')
    section_icon = fields.Char(string='Section Icon', readonly=True)
    section_theme = fields.Char(string='Section Theme', readonly=True)
    is_step_display_row = fields.Boolean(string='Step Display Row', default=False)
    available_doc_count = fields.Integer(string='Available Docs', compute='_compute_step_doc_counts')
    total_doc_count = fields.Integer(string='Total Docs', compute='_compute_step_doc_counts')
    doc_count_label = fields.Char(string='Doc Count', compute='_compute_step_doc_counts')
    is_active_variant = fields.Boolean(string='Active Variant', compute='_compute_is_active_variant')
    document_type = fields.Selection(selection=lambda self: self.env['bhu.document.vault']._fields['document_type'].selection)
    section_label = fields.Char(string='Section')
    document_id = fields.Many2one('bhu.document.vault', string='Document')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment')
    source_model = fields.Char(string='Source Model')
    source_record_id = fields.Integer(string='Source Record ID')
    source_file_field = fields.Char(string='Source File Field')
    source_filename_field = fields.Char(string='Source Filename Field')
    signed_date = fields.Date(string='Signed Date')
    document_count = fields.Integer(string='Count')
    is_available = fields.Boolean(string='Available')
    status_display = fields.Char(string='Status', compute='_compute_status_display')
    availability_icon = fields.Char(string='Doc', compute='_compute_availability_icon', store=True)
    is_selected = fields.Boolean(string='Selected', compute='_compute_is_selected')
    is_focused_step = fields.Boolean(string='Focused Step', compute='_compute_is_focused_step')

    @api.model
    def _section_style_for_label(cls, section_label):
        """Return FontAwesome icon class + theme slug for dashboard-style section rows."""
        label = (section_label or '').strip().lower()
        styles = (
            ('form 10', 'fa-clipboard', 'theme-survey'),
            ('sia team', 'fa-users', 'theme-sia'),
            ('section 4', 'fa-bullhorn', 'theme-sec4'),
            ('expert group', 'fa-gavel', 'theme-expert'),
            ('section 8', 'fa-balance-scale', 'theme-sec8'),
            ('section 11', 'fa-file-text-o', 'theme-sec11'),
            ('section 15', 'fa-comments-o', 'theme-sec15'),
            ('section 18', 'fa-home', 'theme-sec18'),
            ('section 19', 'fa-newspaper-o', 'theme-sec19'),
            ('section 21', 'fa-envelope-o', 'theme-sec21'),
            ('section 23', 'fa-trophy', 'theme-award'),
            ('award', 'fa-trophy', 'theme-award'),
            ('payment file', 'fa-credit-card', 'theme-payment'),
            ('surveys', 'fa-clipboard', 'theme-survey'),
        )
        for needle, icon, theme in styles:
            if needle in label:
                return icon, theme
        return 'fa-file-pdf-o', 'theme-default'

    def name_get(self):
        result = []
        for line in self:
            label = line.variant_label or line.section_label or _('Document')
            if not line.is_available:
                label = _('%s (missing)') % label
            result.append((line.id, label))
        return result

    @api.depends(
        'navigator_id.section_line_ids',
        'navigator_id.section_line_ids.is_available',
        'navigator_id.section_line_ids.is_step_display_row',
        'step_no',
        'is_step_display_row',
    )
    def _compute_step_doc_counts(self):
        for line in self:
            if not line.is_step_display_row or not line.navigator_id:
                line.available_doc_count = 0
                line.total_doc_count = 0
                line.doc_count_label = ''
                continue
            variants = line.navigator_id.section_line_ids.filtered(
                lambda l: l.step_no == line.step_no and not l.is_step_display_row
            )
            available = sum(1 for variant in variants if variant._line_is_available())
            total = len(variants)
            line.available_doc_count = available
            line.total_doc_count = total
            if line.step_no == 1 and variants:
                survey_count = variants[0].document_count or 0
                if survey_count:
                    line.doc_count_label = _('%s khasras') % survey_count
                elif available:
                    line.doc_count_label = _('1 doc')
                else:
                    line.doc_count_label = _('0 docs')
            elif total <= 1:
                line.doc_count_label = _('1 doc') if available else _('0 docs')
            else:
                line.doc_count_label = _('%s / %s docs') % (available, total)

    @api.depends('navigator_id.active_variant_line_id')
    def _compute_is_active_variant(self):
        for line in self:
            active_id = line.navigator_id.active_variant_line_id or 0
            line.is_active_variant = bool(active_id and active_id == line.id)

    @api.depends('document_id', 'attachment_id', 'source_model', 'source_record_id', 'source_file_field', 'is_available')
    def _compute_status_display(self):
        for line in self:
            if line.source_model == 'bhu.docvault.form10':
                line.status_display = _('Available') if line.is_available else _('Missing')
                continue
            line.status_display = _('Available') if (
                line.document_id or line.attachment_id or (
                    line.source_model and line.source_record_id and line.source_file_field
                )
            ) else _('Missing')

    @api.depends('is_available')
    def _compute_availability_icon(self):
        for line in self:
            line.availability_icon = '✅' if line.is_available else '⚪'

    @api.depends('navigator_id.focused_step_no', 'step_no')
    def _compute_is_focused_step(self):
        for line in self:
            line.is_focused_step = bool(
                line.navigator_id and line.navigator_id.focused_step_no == line.step_no
            )

    @api.depends(
        'navigator_id.active_variant_line_id',
        'navigator_id.focused_step_no',
        'step_no',
    )
    def _compute_is_selected(self):
        for line in self:
            nav = line.navigator_id
            line.is_selected = bool(
                nav and nav.focused_step_no == line.step_no
            )

    def _line_is_available(self):
        self.ensure_one()
        if self.source_model == 'bhu.docvault.form10':
            return bool(self.navigator_id._form10_surveys())
        if self.attachment_id:
            return bool(self.attachment_id.exists())
        if self.document_id:
            return bool(self.document_id.exists())
        if self.source_model and self.source_record_id and self.source_file_field:
            source_rec = self.env[self.source_model].sudo().browse(self.source_record_id)
            return bool(source_rec.exists() and source_rec[self.source_file_field])
        return False

    def action_select_step(self):
        """Legacy button handler — delegates to navigator by step number."""
        self.ensure_one()
        if not self.navigator_id or not self.step_no:
            return False
        return self.navigator_id.action_select_step_by_step_no(self.step_no)

    def action_select_document(self):
        """Legacy variant button — delegates by step + variant label."""
        self.ensure_one()
        if not self.navigator_id or not self.step_no:
            return False
        if self.is_step_display_row:
            return self.navigator_id.action_select_step_by_step_no(self.step_no)
        if not self._line_is_available():
            return self._notify_missing_document()
        return self.navigator_id.action_select_variant_label(
            self.step_no, self.variant_label or ''
        )

    def _notify_missing_document(self):
        return self.navigator_id._notify_missing_document_nav() if self.navigator_id else False

    def get_formview_action(self, access_uid=None):
        """Prevent x2many row click popup; route selection to PDF preview."""
        self.ensure_one()
        if self.navigator_id and self.step_no:
            if self.is_step_display_row:
                self.navigator_id.action_select_step_by_step_no(self.step_no)
            elif self.variant_label:
                self.navigator_id.action_select_variant_label(
                    self.step_no, self.variant_label or ''
                )
            else:
                self.navigator_id.action_select_step_by_step_no(self.step_no)
        return False
