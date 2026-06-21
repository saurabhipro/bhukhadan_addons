# -*- coding: utf-8 -*-
"""Time-savings calculations for BhuKhadan vs manual RFCTLARR workflow (no Odoo imports)."""

from dataclasses import dataclass


@dataclass
class Scale:
    projects: int = 1
    villages: int = 4
    surveys: int = 250
    beneficiaries_per_khasra: float = 1.3
    objection_rate_pct: float = 10.0


@dataclass
class SectionResult:
    section: str
    phase: str
    qty_label: str
    qty: int
    manual_min_per_unit: float
    bhuarjan_min_per_unit: float
    manual_note: str
    bhuarjan_note: str
    manual_min: float
    bhuarjan_min: float
    saved_min: float



HOURS_PER_DAY = 8


def safe_count(value):
    """Round to a non-negative int for in-memory calculations."""
    return max(0, int(round(float(value or 0))))


def hours_to_days(hours: float) -> float:
    return hours / HOURS_PER_DAY


def fmt_days(hours: float) -> str:
    """Format desk hours as workdays (8 h = 1 day)."""
    days = hours_to_days(hours)
    if days >= 100:
        return f'{round(days):,} days'
    if days >= 1:
        return f'{days:.1f} days'
    return f'{days:.2f} days'


def fmt_days_num(days: float) -> str:
    """Format a workday count for tables and KPIs."""
    if days >= 100:
        return f'{round(days):,}'
    if days >= 1:
        return f'{days:.1f}'
    return f'{days:.2f}'


def fmt_hours(minutes: float) -> str:
    hrs = minutes / 60.0
    if hrs >= 100:
        return f'{round(hrs):,} h'
    if hrs >= 10:
        return f'{hrs:.1f} h'
    return f'{hrs:.2f} h'


def fmt_pct(saved: float, manual: float) -> str:
    if manual <= 0:
        return '—'
    return f'{round((saved / manual) * 100)}%'


def build_sections(scale: Scale):
    objections = safe_count((scale.surveys * scale.objection_rate_pct) / 100.0)
    payment_lines = safe_count(scale.surveys * scale.beneficiaries_per_khasra)

    raw = [
        ('Master data & project setup', 'Setup', 'projects', scale.projects, 480, 120,
         'Registers, rate charts, village mapping in Excel',
         'Odoo masters + project-village mapping once'),
        ('Form 10 survey capture', 'Survey', 'surveys (khasras)', scale.surveys, 45, 20,
         'Paper register + re-typing + photo filing',
         'Mobile app + validation + digital photos'),
        ('Survey consolidation & QC', 'Survey', 'villages', scale.villages, 180, 15,
         'Manual cross-check across patwari books',
         'Dashboard completion % + approve/reject workflow'),
        ('Form 10 PDF / Excel export', 'Survey', 'villages', scale.villages, 45, 3,
         'Copy-paste into Word/Excel templates',
         'Bulk Form 10 download per village'),
        ('SIA team formation (Sec 4)', 'Sec 4', 'projects', scale.projects, 240, 45,
         'Draft order + khasra/area tally by hand',
         'Auto khasra count & area from approved surveys'),
        ('Section 4 notification', 'Sec 4', 'villages', scale.villages, 240, 30,
         'Notice drafting + stats re-entry per village',
         'PDF generation + auto area from Form 10'),
        ('Expert Committee report (Sec 7)', 'Sec 7', 'projects', scale.projects, 480, 90,
         'Proposal/order from scratch + annexures',
         'Auto stats + PDF proposal/order'),
        ('Section 8 satisfaction order', 'Sec 8', 'projects', scale.projects, 180, 35,
         'Collector order drafting + filing',
         'Workflow + PDF order generation'),
        ('Section 11 preliminary report', 'Sec 11', 'villages', scale.villages, 300, 45,
         'Land parcel lists typed from Sec 4 + surveys',
         'Auto-populate parcels + PDF report'),
        ('Section 15 objections', 'Sec 15', 'objections', objections, 90, 20,
         'Register + hearing notes + resolution letter',
         'Digital objection record + resolution PDF'),
        ('R&R scheme upload (Sec 18)', 'Sec 18', 'projects', scale.projects, 120, 20,
         'Physical file + scanning + indexing',
         'Single scheme PDF per project in system'),
        ('Section 19 notification', 'Sec 19', 'villages', scale.villages, 240, 35,
         'Declaration + R&R summary typed manually',
         'Wizard + PDF from Sec 11 khasras'),
        ('Section 21 / draft award notice', 'Sec 21', 'villages', scale.villages, 180, 30,
         'Public/personal notices per interested person',
         'Auto notice PDFs + sign workflow'),
        ('Section 23 award calculation', 'Award', 'villages', scale.villages, 720, 60,
         'Land/tree/asset/R&R sheets in Excel by hand',
         'Rate master + survey data → PDF/Excel/HTML'),
        ('R&R payment voucher (bank setup)', 'Payment', 'khasra payout rows', scale.surveys, 25, 5,
         'Per-khasra bank details in spreadsheet',
         'Voucher from award + validation + split payout'),
        ('Payment file / bank Excel', 'Payment', 'beneficiary lines', payment_lines, 18, 2,
         'NEFT row typing per beneficiary',
         'Generate Payment File wizard + bulk Excel'),
        ('Bank reconciliation', 'Payment', 'beneficiary lines', payment_lines, 15, 3,
         'Match UTR to register line-by-line',
         'Upload bank file + UUID/account matching'),
        ('Payment status tracking', 'Payment', 'beneficiary lines', payment_lines, 8, 0.5,
         'Separate pending/success/failed registers',
         'Payment Lines menu + auto status'),
    ]

    results = []
    for row in raw:
        section, phase, qty_label, qty, manual_u, bhu_u, manual_note, bhu_note = row
        qty = safe_count(qty)
        manual_min = qty * manual_u
        bhuarjan_min = qty * bhu_u
        results.append(SectionResult(
            section=section,
            phase=phase,
            qty_label=qty_label,
            qty=qty,
            manual_min_per_unit=manual_u,
            bhuarjan_min_per_unit=bhu_u,
            manual_note=manual_note,
            bhuarjan_note=bhu_note,
            manual_min=manual_min,
            bhuarjan_min=bhuarjan_min,
            saved_min=manual_min - bhuarjan_min,
        ))
    return results


def compute_summary(scale=None):
    scale = scale or Scale()
    rows = build_sections(scale)
    total_manual = sum(r.manual_min for r in rows)
    total_bhuarjan = sum(r.bhuarjan_min for r in rows)
    total_saved = total_manual - total_bhuarjan
    saved_pct = min(100, max(0, round((total_saved / total_manual) * 100))) if total_manual else 0
    phases = []
    for phase in ('Setup', 'Survey', 'Sec 4', 'Sec 7', 'Sec 8', 'Sec 11', 'Sec 15',
                  'Sec 18', 'Sec 19', 'Sec 21', 'Award', 'Payment'):
        phase_rows = [r for r in rows if r.phase == phase]
        if not phase_rows:
            continue
        manual = sum(r.manual_min for r in phase_rows)
        bhuarjan = sum(r.bhuarjan_min for r in phase_rows)
        phases.append({
            'phase': phase,
            'manual_h': round(manual / 60, 1),
            'bhuarjan_h': round(bhuarjan / 60, 1),
            'saved_h': round((manual - bhuarjan) / 60, 1),
            'manual_d': round(manual / 60 / HOURS_PER_DAY, 1),
            'bhuarjan_d': round(bhuarjan / 60 / HOURS_PER_DAY, 1),
            'saved_d': round((manual - bhuarjan) / 60 / HOURS_PER_DAY, 1),
        })
    return {
        'scale': scale,
        'rows': rows,
        'total_manual': total_manual,
        'total_bhuarjan': total_bhuarjan,
        'total_saved': total_saved,
        'saved_pct': saved_pct,
        'workdays_saved': total_saved / (HOURS_PER_DAY * 60),
        'staff_months_saved': total_saved / (22 * HOURS_PER_DAY * 60),
        'total_manual_days': round(total_manual / 60 / HOURS_PER_DAY, 1),
        'total_bhuarjan_days': round(total_bhuarjan / 60 / HOURS_PER_DAY, 1),
        'total_saved_days': round(total_saved / 60 / HOURS_PER_DAY, 1),
        'phases': phases,
        'payment_lines': safe_count(scale.surveys * scale.beneficiaries_per_khasra),
        'objections': safe_count((scale.surveys * scale.objection_rate_pct) / 100.0),
    }
