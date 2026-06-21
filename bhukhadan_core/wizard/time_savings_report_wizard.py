# -*- coding: utf-8 -*-

import base64
import html as html_lib
import io
from datetime import date

from markupsafe import Markup, escape

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .time_savings_calculator import Scale, compute_summary, fmt_days, fmt_hours, fmt_pct, HOURS_PER_DAY, hours_to_days
from .time_savings_report_widgets import build_dashboard_html, build_phase_chart_html


class BhuTimeSavingsReportWizard(models.TransientModel):
    _name = 'bhu.time.savings.report.wizard'
    _description = 'BhuKhadan Time Savings Report Wizard'

    project_id = fields.Many2one(
        'bhu.project',
        string='Project (optional)',
        help='Pick a project to auto-fill village and survey counts from live data.',
    )
    project_count = fields.Integer(string='Projects', default=1, required=True)
    village_count = fields.Integer(string='Villages affected', default=4, required=True)
    survey_count = fields.Float(
        string='Surveys / khasras', default=250, required=True, digits=(16, 0),
    )
    beneficiaries_per_khasra = fields.Float(
        string='Beneficiaries per khasra',
        default=1.3,
        digits=(4, 2),
        required=True,
    )
    objection_rate_pct = fields.Float(
        string='Objection rate (%)',
        default=10.0,
        digits=(5, 2),
        required=True,
    )

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if not self.project_id:
            return
        project = self.project_id
        villages = project.village_ids
        survey_count = self.env['bhu.survey'].search_count([
            ('project_id', '=', project.id),
            ('state', '=', 'approved'),
        ])
        if not survey_count:
            survey_count = self.env['bhu.survey'].search_count([
                ('project_id', '=', project.id),
            ])
        self.project_count = 1
        self.village_count = max(1, len(villages))
        self.survey_count = max(1, survey_count or len(villages) * 10)

    def _get_scale(self):
        self.ensure_one()
        beneficiaries = float(self.beneficiaries_per_khasra or 1.0)
        if beneficiaries > 100:
            raise UserError(_(
                'Beneficiaries per khasra cannot exceed 100. '
                'Enter a realistic average (typically 1–5).'
            ))
        surveys = max(1, int(self.survey_count or 1))
        return Scale(
            projects=max(1, int(self.project_count or 1)),
            villages=max(1, int(self.village_count or 1)),
            surveys=surveys,
            beneficiaries_per_khasra=max(1.0, beneficiaries),
            objection_rate_pct=min(100.0, max(0.0, float(self.objection_rate_pct or 0.0))),
        )

    def action_generate_report(self):
        self.ensure_one()
        scale = self._get_scale()
        summary = compute_summary(scale)
        line_cmds = []
        for idx, row in enumerate(summary['rows'], start=1):
            manual_h = round(row.manual_min / 60.0, 2)
            bhu_h = round(row.bhuarjan_min / 60.0, 2)
            saved_h = round(row.saved_min / 60.0, 2)
            line_cmds.append((0, 0, {
                'serial': idx,
                'section': row.section,
                'phase': row.phase,
                'qty_label': row.qty_label,
                'qty': row.qty,
                'manual_hours': manual_h,
                'bhuarjan_hours': bhu_h,
                'saved_hours': saved_h,
                'manual_days': round(hours_to_days(manual_h), 2),
                'bhuarjan_days': round(hours_to_days(bhu_h), 2),
                'saved_days': round(hours_to_days(saved_h), 2),
                'saved_pct': round((row.saved_min / row.manual_min) * 100, 1) if row.manual_min else 0.0,
                'manual_note': row.manual_note,
                'bhuarjan_note': row.bhuarjan_note,
            }))
        report = self.env['bhu.time.savings.report'].create({
            'name': _('Time Savings — %s') % date.today().strftime('%d %b %Y'),
            'project_id': self.project_id.id if self.project_id else False,
            'project_count': scale.projects,
            'village_count': scale.villages,
            'survey_count': scale.surveys,
            'beneficiaries_per_khasra': scale.beneficiaries_per_khasra,
            'objection_rate_pct': scale.objection_rate_pct,
            'payment_line_count': summary['payment_lines'],
            'objection_count': summary['objections'],
            'total_manual_hours': round(summary['total_manual'] / 60.0, 2),
            'total_bhuarjan_hours': round(summary['total_bhuarjan'] / 60.0, 2),
            'total_saved_hours': round(summary['total_saved'] / 60.0, 2),
            'total_manual_days': summary['total_manual_days'],
            'total_bhuarjan_days': summary['total_bhuarjan_days'],
            'total_saved_days': summary['total_saved_days'],
            'saved_pct': min(100, max(0, int(summary['saved_pct']))),
            'workdays_saved': round(summary['workdays_saved'], 1),
            'staff_months_saved': round(summary['staff_months_saved'], 2),
            'line_ids': line_cmds,
        })
        line_rows = [{
            'section': row.section,
            'phase': row.phase,
            'saved_days': round(row.saved_min / 60.0 / HOURS_PER_DAY, 2),
            'saved_pct': round((row.saved_min / row.manual_min) * 100, 1) if row.manual_min else 0.0,
        } for row in summary['rows']]
        report._build_report_widgets(summary, line_rows)
        return {
            'type': 'ir.actions.act_window',
            'name': _('BhuKhadan Time Savings Report'),
            'res_model': 'bhu.time.savings.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }


class BhuTimeSavingsReport(models.TransientModel):
    _name = 'bhu.time.savings.report'
    _description = 'BhuKhadan Time Savings Report'
    _order = 'id desc'

    name = fields.Char(string='Title', required=True)
    project_id = fields.Many2one('bhu.project', string='Reference project', readonly=True)
    project_count = fields.Integer(string='Projects', readonly=True)
    village_count = fields.Integer(string='Villages', readonly=True)
    survey_count = fields.Float(string='Surveys / khasras', readonly=True, digits=(16, 0))
    beneficiaries_per_khasra = fields.Float(string='Beneficiaries / khasra', readonly=True, digits=(4, 2))
    objection_rate_pct = fields.Float(string='Objection rate %', readonly=True, digits=(5, 2))
    payment_line_count = fields.Float(string='Payment lines', readonly=True, digits=(16, 0))
    objection_count = fields.Float(string='Sec 15 objections', readonly=True, digits=(16, 0))
    total_manual_hours = fields.Float(string='Manual total (hours)', readonly=True, digits=(16, 2))
    total_bhuarjan_hours = fields.Float(string='BhuKhadan total (hours)', readonly=True, digits=(16, 2))
    total_saved_hours = fields.Float(string='Hours saved', readonly=True, digits=(16, 2))
    total_manual_days = fields.Float(string='Manual total (days)', readonly=True, digits=(16, 1))
    total_bhuarjan_days = fields.Float(string='BhuKhadan total (days)', readonly=True, digits=(16, 1))
    total_saved_days = fields.Float(string='Days saved', readonly=True, digits=(16, 1))
    saved_pct = fields.Integer(string='Time reduction %', readonly=True)
    workdays_saved = fields.Float(string='Officer-days saved', readonly=True, digits=(16, 1))
    staff_months_saved = fields.Float(string='Staff-months saved', readonly=True, digits=(16, 2))
    dashboard_html = fields.Html(string='Dashboard', sanitize=False)
    summary_html = fields.Html(string='Summary', compute='_compute_summary_html', sanitize=False)
    chart_html = fields.Html(string='Phase chart', sanitize=False)
    line_ids = fields.One2many(
        'bhu.time.savings.report.line',
        'report_id',
        string='Section breakdown',
        readonly=True,
    )

    @api.depends(
        'total_manual_hours', 'total_bhuarjan_hours', 'total_saved_hours', 'saved_pct',
        'workdays_saved', 'staff_months_saved', 'project_count', 'village_count',
        'survey_count', 'beneficiaries_per_khasra', 'objection_rate_pct',
        'payment_line_count', 'objection_count', 'project_id',
    )
    def _compute_summary_html(self):
        for rec in self:
            project_note = ''
            if rec.project_id:
                project_note = (
                    f'<p class="mb-1"><strong>Reference project:</strong> '
                    f'{escape(rec.project_id.display_name)}</p>'
                )
            rec.summary_html = Markup(
                f'<div class="bhu_ts_summary_box">'
                f'{project_note}'
                f'<p class="mb-1">Scale: <strong>{rec.project_count}</strong> project(s), '
                f'<strong>{rec.village_count}</strong> village(s), '
                f'<strong>{rec.survey_count:,}</strong> khasras, '
                f'<strong>{rec.beneficiaries_per_khasra:g}</strong> beneficiaries/khasra, '
                f'<strong>{rec.objection_rate_pct:g}%</strong> objections '
                f'→ <strong>{rec.payment_line_count:,}</strong> payment lines.</p>'
                f'<p class="mb-0">You save approximately '
                f'<strong class="bhu_ts_saved">{rec.total_saved_days:,.1f} workdays ({rec.saved_pct}%)</strong> '
                f'vs fully manual processing — about '
                f'<strong>{rec.staff_months_saved:.1f} staff-months</strong> per acquisition cycle '
                f'({HOURS_PER_DAY} desk hours = 1 day).</p>'
                f'</div>'
            )

    def _build_report_widgets(self, summary, line_rows):
        self.ensure_one()
        report_vals = {
            'saved_pct': self.saved_pct,
            'total_manual_days': self.total_manual_days,
            'total_bhuarjan_days': self.total_bhuarjan_days,
            'total_saved_days': self.total_saved_days,
            'staff_months_saved': self.staff_months_saved,
            'project_count': self.project_count,
            'village_count': self.village_count,
            'survey_count': self.survey_count,
            'beneficiaries_per_khasra': self.beneficiaries_per_khasra,
            'objection_rate_pct': self.objection_rate_pct,
            'payment_line_count': self.payment_line_count,
            'objection_count': self.objection_count,
            'project_name': self.project_id.display_name if self.project_id else '',
        }
        self.dashboard_html = build_dashboard_html(report_vals, summary['phases'], line_rows)
        self.chart_html = build_phase_chart_html(summary['phases'])

    def _get_phase_rows_from_lines(self):
        self.ensure_one()
        phases = {}
        for line in self.line_ids:
            bucket = phases.setdefault(line.phase, {
                'phase': line.phase,
                'manual_d': 0.0,
                'bhuarjan_d': 0.0,
                'saved_d': 0.0,
            })
            bucket['manual_d'] += float(line.manual_days or 0)
            bucket['bhuarjan_d'] += float(line.bhuarjan_days or 0)
            bucket['saved_d'] += float(line.saved_days or 0)
        order = ['Setup', 'Survey', 'Sec 4', 'Sec 7', 'Sec 8', 'Sec 11', 'Sec 15',
                 'Sec 18', 'Sec 19', 'Sec 21', 'Award', 'Payment']
        rows = []
        for phase in order:
            if phase in phases:
                p = phases[phase]
                rows.append({
                    'phase': p['phase'],
                    'manual_d': round(p['manual_d'], 1),
                    'bhuarjan_d': round(p['bhuarjan_d'], 1),
                    'saved_d': round(p['saved_d'], 1),
                })
        return rows

    def _pdf_kpi_table(self, colors):
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib.units import cm
        green = colors.HexColor('#1F8A65')
        data = [[
            'Manual (days)', 'BhuKhadan (days)', 'Days saved', 'Reduction',
            'Staff-months', f'Basis ({HOURS_PER_DAY}h/day)',
        ], [
            f'{self.total_manual_days:,.1f}',
            f'{self.total_bhuarjan_days:,.1f}',
            f'{self.total_saved_days:,.1f}',
            f'{self.saved_pct}%',
            f'{self.staff_months_saved:.1f}',
            f'{HOURS_PER_DAY} h',
        ]]
        table = Table(data, colWidths=[3.2 * cm] * 6)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B4513')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, 1), 11),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (2, 1), (2, 1), green),
            ('TEXTCOLOR', (3, 1), (3, 1), green),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E8D5C4')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#FAF7F4')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return table

    def _pdf_scale_table(self, colors):
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib.units import cm
        project_label = self.project_id.display_name if self.project_id else '—'
        data = [
            ['Metric', 'Value', 'Metric', 'Value'],
            ['Project', project_label, 'Projects', str(self.project_count)],
            ['Villages', str(self.village_count), 'Khasras', f'{self.survey_count:,}'],
            ['Beneficiaries/khasra', f'{self.beneficiaries_per_khasra:g}',
             'Objection rate', f'{self.objection_rate_pct:g}%'],
            ['Payment lines', f'{self.payment_line_count:,}',
             'Sec 15 objections', f'{self.objection_count:,}'],
        ]
        table = Table(data, colWidths=[4 * cm, 5 * cm, 4 * cm, 5 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5EBE3')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#8B4513')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAF7F4')]),
        ]))
        return table

    def _pdf_pie_chart(self):
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.lib import colors as rl_colors
        drawing = Drawing(220, 160)
        pie = Pie()
        pie.x = 35
        pie.y = 15
        pie.width = 110
        pie.height = 110
        pie.data = [
            float(self.total_saved_days or 0),
            float(self.total_bhuarjan_days or 0),
        ]
        pie.labels = ['Saved', 'Remaining']
        pie.slices.strokeWidth = 0.5
        pie.slices[0].fillColor = rl_colors.HexColor('#1F8A65')
        pie.slices[1].fillColor = rl_colors.HexColor('#9CA3AF')
        pie.slices.fontSize = 8
        drawing.add(pie)
        drawing.add(String(150, 95, f'{self.saved_pct}% saved', fontSize=12, fillColor=rl_colors.HexColor('#8B4513')))
        drawing.add(String(150, 78, f'{self.total_saved_days:,.1f} days freed', fontSize=9))
        return drawing

    def _pdf_phase_bar_chart(self):
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics.charts.barcharts import HorizontalBarChart
        from reportlab.lib import colors as rl_colors
        phases = self._get_phase_rows_from_lines()
        if not phases:
            return None
        drawing = Drawing(480, 28 * len(phases) + 40)
        chart = HorizontalBarChart()
        chart.x = 80
        chart.y = 20
        chart.height = 22 * len(phases)
        chart.width = 360
        chart.data = [
            [p['manual_d'] for p in phases],
            [p['bhuarjan_d'] for p in phases],
            [p['saved_d'] for p in phases],
        ]
        chart.categoryAxis.categoryNames = [p['phase'] for p in phases]
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.labels.fontSize = 7
        chart.bars[0].fillColor = rl_colors.HexColor('#9CA3AF')
        chart.bars[1].fillColor = rl_colors.HexColor('#6B7280')
        chart.bars[2].fillColor = rl_colors.HexColor('#1F8A65')
        chart.barWidth = 6
        chart.groupSpacing = 8
        chart.barSpacing = 2
        drawing.add(chart)
        return drawing

    def _pdf_top_sections_table(self, colors):
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        body = ParagraphStyle('TopBody', fontSize=8, leading=10)
        lines = sorted(self.line_ids, key=lambda l: l.saved_days, reverse=True)[:5]
        data = [['#', 'Section', 'Phase', 'Saved (days)', 'Saved %']]
        for idx, line in enumerate(lines, start=1):
            data.append([
                str(idx),
                Paragraph(html_lib.escape(line.section or ''), body),
                line.phase or '',
                f'{line.saved_days:,.1f}',
                f'{line.saved_pct:.0f}%',
            ])
        table = Table(data, colWidths=[0.8 * cm, 8 * cm, 2.2 * cm, 2 * cm, 1.5 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5EBE3')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#8B4513')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('TEXTCOLOR', (3, 1), (4, -1), colors.HexColor('#1F8A65')),
            ('FONTNAME', (3, 1), (4, -1), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAF7F4')]),
        ]))
        return table

    def action_download_pdf(self):
        self.ensure_one()
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
                PageBreak,
            )
        except ImportError as exc:
            raise UserError(_(
                'PDF export needs the Python reportlab library on the Odoo server. '
                'Ask your administrator to install it, or use Print on this screen.'
            )) from exc

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=1.0 * cm,
            rightMargin=1.0 * cm,
            topMargin=0.8 * cm,
            bottomMargin=0.8 * cm,
            title=self.name or 'Time Savings Report',
        )
        brand = colors.HexColor('#8B4513')
        header_bg = colors.HexColor('#F5EBE3')
        zebra = colors.HexColor('#FAF7F4')
        green = colors.HexColor('#1F8A65')
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TsTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.white,
            spaceAfter=0, alignment=1,
        )
        subtitle_style = ParagraphStyle(
            'TsSub', parent=styles['Normal'], fontSize=10, textColor=colors.white, alignment=1,
        )
        h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=brand, spaceBefore=10, spaceAfter=6)
        body = ParagraphStyle('B', parent=styles['Normal'], fontSize=9, leading=12)
        small = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.grey)

        def para(text, style=body):
            return Paragraph(html_lib.escape(str(text)).replace('\n', '<br/>'), style)

        # Branded header band
        header_table = Table(
            [[Paragraph('BhuKhadan — Time &amp; Efficiency Report', title_style)],
             [Paragraph(
                 f'Management briefing · {date.today().strftime("%d %b %Y")}'
                 + (f' · {self.project_id.display_name}' if self.project_id else '')
                 + f' · Figures in workdays ({HOURS_PER_DAY}h = 1 day)',
                 subtitle_style,
             )]],
            colWidths=[doc.width],
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), brand),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))

        story = [
            header_table,
            Spacer(1, 0.35 * cm),
            self._pdf_kpi_table(colors),
            Spacer(1, 0.3 * cm),
            para(
                f'You save {self.total_saved_days:,.1f} workdays ({self.saved_pct}%) versus fully manual '
                f'desk work — equivalent to {self.staff_months_saved:.1f} staff-months per acquisition cycle '
                f'({HOURS_PER_DAY} desk hours = 1 day).',
                body,
            ),
            Spacer(1, 0.25 * cm),
            para('Project scale', h2),
            self._pdf_scale_table(colors),
            Spacer(1, 0.25 * cm),
        ]

        # Charts row: pie + phase bars side by side
        pie = self._pdf_pie_chart()
        phase_chart = self._pdf_phase_bar_chart()
        if pie or phase_chart:
            story.append(para('Visual analysis', h2))
            chart_cells = [[pie or Spacer(1, 0.1 * cm), phase_chart or Spacer(1, 0.1 * cm)]]
            story.append(Table(chart_cells, colWidths=[doc.width * 0.38, doc.width * 0.62]))
        story.extend([Spacer(1, 0.25 * cm), para('Top 5 sections by days saved', h2), self._pdf_top_sections_table(colors)])

        # Phase summary table
        phase_rows = self._get_phase_rows_from_lines()
        if phase_rows:
            story.extend([Spacer(1, 0.25 * cm), para('Phase summary (workdays)', h2)])
            phase_data = [['Phase', 'Manual (days)', 'BhuKhadan (days)', 'Saved (days)']]
            for p in phase_rows:
                phase_data.append([
                    p['phase'],
                    f"{p['manual_d']:.1f}",
                    f"{p['bhuarjan_d']:.1f}",
                    f"{p['saved_d']:.1f}",
                ])
            phase_table = Table(phase_data, colWidths=[4 * cm, 3 * cm, 3 * cm, 3 * cm])
            phase_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), header_bg),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('TEXTCOLOR', (0, 0), (-1, 0), brand),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ('TEXTCOLOR', (3, 1), (3, -1), green),
                ('FONTNAME', (3, 1), (3, -1), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, zebra]),
            ]))
            story.append(phase_table)

        story.extend([PageBreak(), para('Full section-by-section breakdown', h2)])
        detail_data = [['Section', 'Phase', 'Qty', 'Manual', 'BhuKhadan', 'Saved', 'Saved %']]
        for line in self.line_ids.sorted('serial'):
            detail_data.append([
                Paragraph(html_lib.escape(line.section or ''), small),
                line.phase or '',
                f'{line.qty:,}',
                f'{line.manual_days:.1f} d',
                f'{line.bhuarjan_days:.1f} d',
                f'{line.saved_days:.1f} d',
                f'{line.saved_pct:.0f}%',
            ])
        detail_table = Table(
            detail_data,
            colWidths=[6.5 * cm, 1.8 * cm, 1.5 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.3 * cm],
            repeatRows=1,
        )
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TEXTCOLOR', (5, 1), (6, -1), green),
            ('FONTNAME', (5, 1), (6, -1), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, zebra]),
        ]))
        story.append(detail_table)
        story.extend([
            Spacer(1, 0.35 * cm),
            para(
                f'Methodology: figures are in workdays ({HOURS_PER_DAY} desk hours = 1 day). '
                'Manual time reflects typing, Excel reconciliation, and repeated data entry; '
                'BhuKhadan time includes approvals and signed uploads but excludes offline field work.',
                small,
            ),
            para('Generated by BhuKhadan · RFCTLARR land acquisition platform', small),
        ])

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        filename = 'BhuKhadan_Time_Efficiency_Report.pdf'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_bytes),
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_new_report(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Time Savings Report'),
            'res_model': 'bhu.time.savings.report.wizard',
            'view_mode': 'form',
            'target': 'new',
        }


class BhuTimeSavingsReportLine(models.TransientModel):
    _name = 'bhu.time.savings.report.line'
    _description = 'BhuKhadan Time Savings Report Line'
    _order = 'serial, id'

    report_id = fields.Many2one(
        'bhu.time.savings.report',
        string='Report',
        required=True,
        ondelete='cascade',
    )
    serial = fields.Integer(string='Sr.', default=1)
    section = fields.Char(string='Section', required=True)
    phase = fields.Char(string='Phase', required=True, index=True)
    qty_label = fields.Char(string='Qty unit')
    qty = fields.Float(string='Quantity', digits=(16, 0))
    manual_hours = fields.Float(string='Manual (h)', digits=(16, 2))
    bhuarjan_hours = fields.Float(string='BhuKhadan (h)', digits=(16, 2))
    saved_hours = fields.Float(string='Saved (h)', digits=(16, 2))
    manual_days = fields.Float(string='Manual (days)', digits=(16, 2))
    bhuarjan_days = fields.Float(string='BhuKhadan (days)', digits=(16, 2))
    saved_days = fields.Float(string='Saved (days)', digits=(16, 2))
    saved_pct = fields.Float(string='Saved %', digits=(16, 1))
    manual_note = fields.Char(string='Manual work')
    bhuarjan_note = fields.Char(string='BhuKhadan replaces')
