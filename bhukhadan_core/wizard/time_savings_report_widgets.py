# -*- coding: utf-8 -*-
"""HTML widget builders for BhuKhadan time savings report (inline SVG — no CSS dependency)."""

import math

from markupsafe import Markup, escape

HOURS_PER_DAY = 8


def fmt_days_num(days: float) -> str:
    if days >= 100:
        return f'{round(days):,}'
    if days >= 1:
        return f'{days:.1f}'
    return f'{days:.2f}'


def _phase_days(p, key_h, key_d):
    if key_d in p:
        return float(p[key_d])
    return float(p[key_h]) / HOURS_PER_DAY


def _svg_donut(saved_pct, saved_d, bhu_d, size=200):
    """Inline SVG donut — renders inside Odoo html fields without external CSS."""
    r = 68
    cx = cy = size // 2
    circ = 2 * math.pi * r
    saved_len = max(0.0, circ * float(saved_pct) / 100.0)
    remain_len = max(0.01, circ - saved_len)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" role="img" aria-label="Time saved {saved_pct} percent">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#d1d5db" stroke-width="24"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1f8a65" stroke-width="24" '
        f'stroke-dasharray="{saved_len:.2f} {remain_len:.2f}" '
        f'transform="rotate(-90 {cx} {cy})"/>'
        f'<circle cx="{cx}" cy="{cy}" r="46" fill="#ffffff"/>'
        f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" font-size="24" font-weight="700" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#1f8a65">{int(saved_pct)}%</text>'
        f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" font-size="10" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#888">TIME SAVED</text>'
        f'</svg>'
        f'<div style="font-size:12px;color:#555;margin-top:6px;line-height:1.5;">'
        f'<div><span style="display:inline-block;width:10px;height:10px;background:#1f8a65;'
        f'border-radius:50%;margin-right:6px;"></span>Saved: <b>{fmt_days_num(saved_d)} days</b></div>'
        f'<div><span style="display:inline-block;width:10px;height:10px;background:#9ca3af;'
        f'border-radius:50%;margin-right:6px;"></span>Remaining: <b>{fmt_days_num(bhu_d)} days</b></div>'
        f'</div>'
    )


def _fmt_bar_label(days: float) -> str:
    if days >= 100:
        return f'{round(days)}d'
    if days >= 10:
        return f'{days:.0f}d'
    if days >= 1:
        return f'{days:.1f}d'
    return f'{days:.2f}d'


def _svg_bar_with_label(parts, x, y, w, h, fill, value_label):
    """Draw rounded bar; place value label inside or just after the bar."""
    w = max(w, 3.0)
    parts.append(
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" fill="{fill}" rx="{h / 2:.1f}" ry="{h / 2:.1f}"/>'
    )
    label_x = x + w + 6
    label_fill = '#555'
    label_weight = '500'
    if w >= 42:
        label_x = x + w - 6
        label_fill = '#fff'
        label_weight = '700'
        parts.append(
            f'<text x="{label_x:.1f}" y="{y + h - 3.5}" text-anchor="end" font-size="10" font-weight="{label_weight}" '
            f'font-family="Segoe UI,Arial,sans-serif" fill="{label_fill}">{value_label}</text>'
        )
    else:
        parts.append(
            f'<text x="{label_x:.1f}" y="{y + h - 3.5}" text-anchor="start" font-size="10" font-weight="600" '
            f'font-family="Segoe UI,Arial,sans-serif" fill="#666">{value_label}</text>'
        )


def _svg_phase_bar_chart(phases):
    """Polished grouped horizontal bar chart — manual vs BhuKhadan in workdays."""
    if not phases:
        return ''

    label_w = 68
    chart_x = label_w + 12
    chart_w = 500
    saved_w = 78
    pad_r = 14
    row_h = 42
    bar_h = 12
    bar_gap = 5
    header_h = 48
    axis_h = 26
    width = chart_x + chart_w + saved_w + pad_r
    height = header_h + len(phases) * row_h + axis_h + 8

    max_d = max(
        max(_phase_days(p, 'manual_h', 'manual_d'), _phase_days(p, 'bhuarjan_h', 'bhuarjan_d'))
        for p in phases
    ) or 1.0
    max_label = _fmt_bar_label(max_d)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height}" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet" '
        f'role="img" aria-label="Workdays by phase comparison">',
        '<defs>',
        '<linearGradient id="bhuTsGradManual" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#c4a882"/><stop offset="100%" stop-color="#9ca3af"/>'
        '</linearGradient>',
        '<linearGradient id="bhuTsGradBhu" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#3cb371"/><stop offset="100%" stop-color="#1f8a65"/>'
        '</linearGradient>',
        '<linearGradient id="bhuTsGradSaved" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#e8f5ef"/><stop offset="100%" stop-color="#d4ede0"/>'
        '</linearGradient>',
        '<filter id="bhuTsBarShadow" x="-2%" y="-20%" width="104%" height="140%">'
        '<feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="#000" flood-opacity="0.08"/>'
        '</filter>',
        '</defs>',
        # Chart panel background
        f'<rect x="{label_w - 4}" y="{header_h - 6}" width="{chart_w + saved_w + 20}" '
        f'height="{len(phases) * row_h + axis_h + 4}" fill="#fafafa" rx="8" stroke="#ececec"/>',
        # Legend
        f'<rect x="{chart_x}" y="10" width="12" height="12" fill="url(#bhuTsGradManual)" rx="3"/>',
        f'<text x="{chart_x + 18}" y="20" font-size="11" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#666">Manual process</text>',
        f'<rect x="{chart_x + 118}" y="10" width="12" height="12" fill="url(#bhuTsGradBhu)" rx="3"/>',
        f'<text x="{chart_x + 136}" y="20" font-size="11" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#666">With BhuKhadan</text>',
        f'<rect x="{chart_x + 248}" y="10" width="12" height="12" fill="#1f8a65" rx="3"/>',
        f'<text x="{chart_x + 266}" y="20" font-size="11" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#666">Days saved</text>',
        f'<text x="{chart_x + chart_w - 2}" y="20" text-anchor="end" font-size="10" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#999">Scale: 0 – {max_label}</text>',
    ]

    # Vertical grid + axis labels
    chart_bottom = header_h + len(phases) * row_h
    for tick in range(5):
        tx = chart_x + chart_w * tick / 4.0
        tick_val = max_d * tick / 4.0
        parts.append(
            f'<line x1="{tx:.1f}" y1="{header_h - 2}" x2="{tx:.1f}" y2="{chart_bottom}" '
            f'stroke="#e8e8e8" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{chart_bottom + 16}" text-anchor="middle" font-size="9" '
            f'font-family="Segoe UI,Arial,sans-serif" fill="#aaa">{_fmt_bar_label(tick_val)}</text>'
        )
    parts.append(
        f'<text x="{chart_x + chart_w / 2:.1f}" y="{height - 2}" text-anchor="middle" font-size="10" '
        f'font-weight="600" font-family="Segoe UI,Arial,sans-serif" fill="#8b7355">Workdays</text>'
    )

    y = header_h + 4
    for idx, p in enumerate(phases):
        manual_d = _phase_days(p, 'manual_h', 'manual_d')
        bhu_d = _phase_days(p, 'bhuarjan_h', 'bhuarjan_d')
        saved_d = _phase_days(p, 'saved_h', 'saved_d')
        mw = max(3.0, chart_w * manual_d / max_d)
        bw = max(3.0, chart_w * bhu_d / max_d)

        # Zebra row highlight
        if idx % 2 == 0:
            parts.append(
                f'<rect x="{label_w - 4}" y="{y - 4}" width="{chart_w + saved_w + 20}" '
                f'height="{row_h - 2}" fill="#ffffff" rx="4" opacity="0.7"/>'
            )

        # Phase label
        parts.append(
            f'<text x="{label_w}" y="{y + bar_h + 2}" text-anchor="end" font-size="11" font-weight="700" '
            f'font-family="Segoe UI,Arial,sans-serif" fill="#5c3d2e">{escape(p["phase"])}</text>'
        )

        # Bar tracks
        track_y1 = y
        track_y2 = y + bar_h + bar_gap
        parts.extend([
            f'<rect x="{chart_x}" y="{track_y1}" width="{chart_w}" height="{bar_h}" fill="#efefef" rx="{bar_h / 2:.1f}"/>',
            f'<rect x="{chart_x}" y="{track_y2}" width="{chart_w}" height="{bar_h}" fill="#efefef" rx="{bar_h / 2:.1f}"/>',
        ])

        # Bars with shadows
        parts.append(f'<g filter="url(#bhuTsBarShadow)">')
        _svg_bar_with_label(parts, chart_x, track_y1, mw, bar_h, 'url(#bhuTsGradManual)', _fmt_bar_label(manual_d))
        _svg_bar_with_label(parts, chart_x, track_y2, bw, bar_h, 'url(#bhuTsGradBhu)', _fmt_bar_label(bhu_d))
        parts.append('</g>')

        # Saved badge
        badge_x = chart_x + chart_w + 8
        badge_y = y + 2
        parts.extend([
            f'<rect x="{badge_x}" y="{badge_y}" width="{saved_w - 12}" height="24" '
            f'fill="url(#bhuTsGradSaved)" stroke="#b8dfc8" rx="12"/>',
            f'<text x="{badge_x + (saved_w - 12) / 2:.1f}" y="{badge_y + 16}" text-anchor="middle" '
            f'font-size="11" font-weight="800" font-family="Segoe UI,Arial,sans-serif" fill="#1f8a65">'
            f'−{_fmt_bar_label(saved_d)}</text>',
        ])

        y += row_h

    parts.append('</svg>')
    return ''.join(parts)


def _executive_summary(report_vals):
    manual_d = float(report_vals.get('total_manual_days') or 0)
    bhu_d = float(report_vals.get('total_bhuarjan_days') or 0)
    saved_d = float(report_vals.get('total_saved_days') or 0)
    saved_pct = int(report_vals.get('saved_pct') or 0)
    staff_mo = float(report_vals.get('staff_months_saved') or 0)
    return (
        '<div style="background:linear-gradient(180deg,#f5ebe3 0%,#faf7f4 100%);'
        'border:1px solid #e8d5c4;border-radius:8px;padding:14px 16px;margin-bottom:14px;">'
        '<div style="font-size:11px;font-weight:700;color:#8b4513;text-transform:uppercase;'
        'letter-spacing:0.05em;margin-bottom:6px;">Executive summary</div>'
        f'<div style="font-size:13px;line-height:1.55;color:#333;">'
        f'For the RFCTLARR land acquisition pipeline, desk-work drops from '
        f'<strong style="color:#8b4513;">{fmt_days_num(manual_d)} workdays</strong> (manual) to '
        f'<strong style="color:#5c3d2e;">{fmt_days_num(bhu_d)} workdays</strong> with BhuKhadan — '
        f'a saving of <strong style="color:#1f8a65;">{fmt_days_num(saved_d)} workdays ({saved_pct}%)</strong>, '
        f'equivalent to <strong>{staff_mo:.1f} staff-months</strong> of officer time '
        f'(<em>{HOURS_PER_DAY} desk hours = 1 workday</em>).</div></div>'
    )


def _top_sections_html(rows, limit=5):
    top = sorted(rows, key=lambda r: r.get('saved_days', 0), reverse=True)[:limit]
    if not top:
        return ''
    items = []
    max_saved = top[0].get('saved_days', 0) or 1
    for idx, row in enumerate(top, start=1):
        saved_d = float(row.get('saved_days', 0))
        pct_w = max(8, int(100 * saved_d / max_saved))
        items.append(
            f'<div style="display:flex;gap:10px;margin-bottom:10px;align-items:flex-start;">'
            f'<span style="width:22px;height:22px;border-radius:50%;background:#8b4513;color:#fff;'
            f'font-size:11px;font-weight:700;display:inline-flex;align-items:center;'
            f'justify-content:center;flex-shrink:0;">{idx}</span>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-size:12px;font-weight:700;color:#333;">{escape(row.get("section") or "")}</div>'
            f'<div style="font-size:11px;color:#777;margin:2px 0 4px;">{escape(row.get("phase") or "")} · '
            f'saved {fmt_days_num(saved_d)} days ({float(row.get("saved_pct", 0)):.0f}%)</div>'
            f'<div style="height:6px;background:#eee;border-radius:3px;overflow:hidden;">'
            f'<div style="height:100%;width:{pct_w}%;background:linear-gradient(90deg,#1f8a65,#3cb371);"></div>'
            f'</div></div></div>'
        )
    return (
        '<div style="border:1px solid #e8d5c4;border-radius:8px;background:#fff;padding:12px 14px;">'
        '<div style="font-size:12px;font-weight:700;color:#8b4513;margin-bottom:10px;text-transform:uppercase;">'
        'Top savings by section</div>'
        + ''.join(items)
        + '</div>'
    )


def _pipeline_html(phases):
    if not phases:
        return ''
    chips = []
    for p in phases:
        manual_d = _phase_days(p, 'manual_h', 'manual_d')
        bhu_d = _phase_days(p, 'bhuarjan_h', 'bhuarjan_d')
        saved_d = _phase_days(p, 'saved_h', 'saved_d')
        chips.append(
            f'<div style="flex:1 1 110px;min-width:100px;background:#faf7f4;border:1px solid #e8d5c4;'
            f'border-radius:6px;padding:8px 10px;text-align:center;">'
            f'<div style="font-size:11px;font-weight:700;color:#8b4513;">{escape(p["phase"])}</div>'
            f'<div style="font-size:14px;font-weight:800;color:#1f8a65;margin:2px 0;">{saved_d:g} days</div>'
            f'<div style="font-size:10px;color:#888;">{manual_d:g} → {bhu_d:g} days</div>'
            f'</div>'
        )
    return (
        '<div style="border:1px solid #e8d5c4;border-radius:8px;background:#fff;padding:12px 14px;margin-top:12px;">'
        '<div style="font-size:12px;font-weight:700;color:#8b4513;margin-bottom:10px;text-transform:uppercase;">'
        'Pipeline savings</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{"".join(chips)}</div>'
        '</div>'
    )


def build_dashboard_html(report_vals, phases, line_rows):
    """Executive dashboard with inline SVG pie + bar charts (workdays)."""
    saved_pct = int(report_vals.get('saved_pct') or 0)
    manual_d = float(report_vals.get('total_manual_days') or 0)
    bhu_d = float(report_vals.get('total_bhuarjan_days') or 0)
    saved_d = float(report_vals.get('total_saved_days') or 0)
    staff_mo = float(report_vals.get('staff_months_saved') or 0)
    project_name = escape(report_vals.get('project_name') or '')

    project_line = ''
    if project_name:
        project_line = f'<div style="margin-top:6px;font-size:13px;">Project: {project_name}</div>'

    kpi_cards = (
        '<div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin-bottom:14px;">'
        f'<div style="border:1px solid #e8d5c4;border-radius:8px;padding:12px;text-align:center;background:#faf7f4;">'
        f'<div style="font-size:22px;font-weight:800;color:#5c3d2e;">{fmt_days_num(manual_d)}</div>'
        f'<div style="font-size:10px;font-weight:600;color:#8b7355;margin-top:4px;">MANUAL (DAYS)</div></div>'
        f'<div style="border:1px solid #e8d5c4;border-radius:8px;padding:12px;text-align:center;background:#faf7f4;">'
        f'<div style="font-size:22px;font-weight:800;color:#5c3d2e;">{fmt_days_num(bhu_d)}</div>'
        f'<div style="font-size:10px;font-weight:600;color:#8b7355;margin-top:4px;">WITH BHUKHADAN</div></div>'
        f'<div style="border:1px solid #b8dfc8;border-radius:8px;padding:12px;text-align:center;background:#e8f5ef;">'
        f'<div style="font-size:22px;font-weight:800;color:#1f8a65;">{fmt_days_num(saved_d)}</div>'
        f'<div style="font-size:10px;font-weight:600;color:#1f8a65;margin-top:4px;">DAYS SAVED</div></div>'
        f'<div style="border:1px solid #b8dfc8;border-radius:8px;padding:12px;text-align:center;background:#e8f5ef;">'
        f'<div style="font-size:22px;font-weight:800;color:#1f8a65;">{saved_pct}%</div>'
        f'<div style="font-size:10px;font-weight:600;color:#1f8a65;margin-top:4px;">REDUCTION</div></div>'
        f'<div style="border:1px solid #e8d5c4;border-radius:8px;padding:12px;text-align:center;background:#faf7f4;">'
        f'<div style="font-size:22px;font-weight:800;color:#5c3d2e;">{staff_mo:.1f}</div>'
        f'<div style="font-size:10px;font-weight:600;color:#8b7355;margin-top:4px;">STAFF-MONTHS</div></div>'
        f'<div style="border:1px solid #e8d5c4;border-radius:8px;padding:12px;text-align:center;background:#faf7f4;">'
        f'<div style="font-size:22px;font-weight:800;color:#5c3d2e;">{HOURS_PER_DAY}h</div>'
        f'<div style="font-size:10px;font-weight:600;color:#8b7355;margin-top:4px;">PER WORKDAY</div></div>'
        '</div>'
    )

    charts_row = (
        '<div style="display:grid;grid-template-columns:220px 1fr;gap:16px;margin-bottom:14px;align-items:start;">'
        f'<div style="border:1px solid #e8d5c4;border-radius:8px;background:#fff;padding:14px;text-align:center;">'
        f'<div style="font-size:12px;font-weight:700;color:#8b4513;margin-bottom:8px;text-transform:uppercase;">'
        f'Efficiency split</div>{_svg_donut(saved_pct, saved_d, bhu_d)}</div>'
        f'<div style="border:1px solid #e8d5c4;border-radius:10px;background:linear-gradient(180deg,#fff 0%,#faf7f4 100%);'
        f'padding:16px 18px;overflow-x:auto;box-shadow:0 1px 4px rgba(139,69,19,0.06);">'
        f'<div style="font-size:12px;font-weight:700;color:#8b4513;margin-bottom:12px;text-transform:uppercase;'
        f'letter-spacing:0.04em;">Workdays by phase — manual vs BhuKhadan</div>{_svg_phase_bar_chart(phases)}</div>'
        '</div>'
    )

    scale = (
        '<div style="border:1px solid #e8d5c4;border-radius:8px;background:#fff;padding:12px 14px;">'
        '<div style="font-size:12px;font-weight:700;color:#8b4513;margin-bottom:8px;text-transform:uppercase;">'
        'Project scale</div>'
        '<table style="width:100%;font-size:12px;border-collapse:collapse;">'
        f'<tr><td style="padding:4px 0;color:#8b7355;font-weight:600;">Villages</td><td>{int(report_vals.get("village_count") or 0)}</td></tr>'
        f'<tr><td style="padding:4px 0;color:#8b7355;font-weight:600;">Surveys / khasras</td><td>{int(report_vals.get("survey_count") or 0):,}</td></tr>'
        f'<tr><td style="padding:4px 0;color:#8b7355;font-weight:600;">Payment lines</td><td>{int(report_vals.get("payment_line_count") or 0):,}</td></tr>'
        f'<tr><td style="padding:4px 0;color:#8b7355;font-weight:600;">Objection rate</td><td>{float(report_vals.get("objection_rate_pct") or 0):g}%</td></tr>'
        '</table></div>'
    )

    return Markup(
        '<div class="bhu_ts_dashboard">'
        '<div style="background:linear-gradient(135deg,#8b4513 0%,#a0522d 55%,#6b3410 100%);'
        'color:#fff;border-radius:8px;padding:16px 18px;margin-bottom:14px;">'
        '<div style="font-size:18px;font-weight:700;">BhuKhadan Time &amp; Cost Efficiency Report</div>'
        f'{project_line}'
        f'<div style="font-size:12px;opacity:0.9;margin-top:4px;">'
        f'Prepared for management review · all figures in workdays ({HOURS_PER_DAY} desk hours = 1 day)</div>'
        '</div>'
        + _executive_summary(report_vals)
        + kpi_cards
        + charts_row
        + '<div style="display:grid;grid-template-columns:1fr 1.2fr;gap:12px;">'
        + scale
        + _top_sections_html(line_rows)
        + '</div>'
        + _pipeline_html(phases)
        + '</div>'
    )


def build_phase_chart_html(phases):
    """Phase detail table in workdays with inline mini-bars."""
    if not phases:
        return Markup('<p>No phase data.</p>')
    max_d = max(
        max(_phase_days(p, 'manual_h', 'manual_d'), _phase_days(p, 'bhuarjan_h', 'bhuarjan_d'))
        for p in phases
    ) or 1
    rows = []
    for p in phases:
        manual_d = _phase_days(p, 'manual_h', 'manual_d')
        bhu_d = _phase_days(p, 'bhuarjan_h', 'bhuarjan_d')
        saved_d = _phase_days(p, 'saved_h', 'saved_d')
        manual_w = max(4, int(100 * manual_d / max_d))
        bhu_w = max(4, int(100 * bhu_d / max_d))
        rows.append(
            f'<tr>'
            f'<td style="font-weight:600;white-space:nowrap;padding:6px 8px;border:1px solid #eee;">'
            f'{escape(p["phase"])}</td>'
            f'<td style="padding:6px 8px;border:1px solid #eee;">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="flex:1;height:14px;background:#f0f0f0;border-radius:3px;overflow:hidden;min-width:80px;">'
            f'<div style="width:{manual_w}%;height:14px;background:#9ca3af;border-radius:3px;"></div></div>'
            f'<span style="font-size:11px;color:#666;white-space:nowrap;">{manual_d:g} days</span></div></td>'
            f'<td style="padding:6px 8px;border:1px solid #eee;">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="flex:1;height:14px;background:#f0f0f0;border-radius:3px;overflow:hidden;min-width:80px;">'
            f'<div style="width:{bhu_w}%;height:14px;background:#6b7280;border-radius:3px;"></div></div>'
            f'<span style="font-size:11px;color:#666;white-space:nowrap;">{bhu_d:g} days</span></div></td>'
            f'<td style="padding:6px 8px;border:1px solid #eee;font-weight:700;color:#1f8a65;text-align:right;">'
            f'{saved_d:g} days</td>'
            f'</tr>'
        )
    return Markup(
        '<div style="border:1px solid #e8d5c4;border-radius:10px;background:linear-gradient(180deg,#fff 0%,#faf7f4 100%);'
        'padding:16px 18px;margin-bottom:8px;overflow-x:auto;box-shadow:0 1px 4px rgba(139,69,19,0.06);">'
        f'<div style="font-size:12px;font-weight:700;color:#8b4513;margin-bottom:12px;text-transform:uppercase;'
        f'letter-spacing:0.04em;">Phase comparison chart</div>{_svg_phase_bar_chart(phases)}</div>'
        '<table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:12px;">'
        '<thead><tr style="background:#f5ebe3;color:#5c3d2e;">'
        '<th style="padding:8px;border:1px solid #e8d5c4;text-align:left;">Phase</th>'
        '<th style="padding:8px;border:1px solid #e8d5c4;text-align:left;">Manual (days)</th>'
        '<th style="padding:8px;border:1px solid #e8d5c4;text-align:left;">BhuKhadan (days)</th>'
        '<th style="padding:8px;border:1px solid #e8d5c4;text-align:right;">Saved (days)</th>'
        '</tr></thead><tbody>'
        + ''.join(rows)
        + '</tbody></table>'
    )
