from odoo import models, fields, _
from odoo.exceptions import UserError
import base64
import csv
import io
import logging
import re
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False


DEFAULT_BHU_PATWARI_GOOGLE_SHEET_CSV_URL = (
    'https://docs.google.com/spreadsheets/d/1JqffBfWRDWAtJL-5MyKJQxa71RlylIkwDUjuaBMa9sw/'
    'export?format=csv&gid=1569404633'
)

_ROSTER_COL_VILLAGE = 7
_ROSTER_COL_PATWARI_NAME = 8
_ROSTER_COL_PATWARI_MOBILE = 9


class UserReportWizard(models.TransientModel):
    _name = 'user.report.wizard'
    _description = 'User Report Excel Export Wizard'

    include_patwaris_without_villages = fields.Boolean(
        string='Include Patwaris without village mapping',
        default=False,
        help=(
            'Patwaris whose user record has no villages assigned still appear when this is '
            'enabled: they export as rows with patron contact filled but tahsil/project/village '
            'columns empty (often mistaken for spreadsheet errors). Turn off for a roster of '
            'only mapped Patwaris × village × project lines.'
        ),
    )

    def _patwari_users_domain(self):
        """Patwari only; district admins are limited to their district."""
        domain = [('bhuarjan_role', '=', 'halka_patwari')]
        user = self.env.user
        is_full_admin = user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group(
            'base.group_system'
        )
        if not is_full_admin and user.has_group('bhukhadan_core.group_bhuarjan_district_administrator'):
            if user.district_id:
                domain.append(('district_id', '=', user.district_id.id))
        return domain

    def _user_email_display(self, user):
        return (user.partner_id.email if user.partner_id else '') or (user.email or '') or (user.login or '')

    def _header_format(self, workbook):
        """Coloured header row only (no body fill)."""
        return workbook.add_format({
            'bold': True,
            'bg_color': '#366092',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': 1,
        })

    def _data_row_format(self, workbook, row_index):
        """Zebra striping: alternating light grey / white; thin grid."""
        alt = (row_index % 2) == 0
        return workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': 1,
            'bg_color': '#E8E8E8' if alt else '#FFFFFF',
        })

    @staticmethod
    def _label_with_optional_code(display_name: str, code: str):
        """Match many2one display: ``[CODE] Name`` when both set (same as bhu.project / bhu.village)."""
        label = (display_name or '').strip()
        cod = (code or '').strip()
        if cod and label:
            return f'[{cod}] {label}'
        if label:
            return label
        if cod:
            return f'[{cod}]'
        return ''

    def _iter_export_lines(self, users, include_patwaris_without_villages=False):
        """Yield (user, village_record|False, project_record|False) for each spreadsheet row.

        One row per village that is assigned to the Patwari × each project that includes
        that village. If a village is on no project, one row with project False.
        If ``include_patwaris_without_villages`` is true, Patwaris with no villages get one row
        with village and project False (contact only); otherwise those users are skipped.
        """
        Project = self.env['bhu.project'].sudo()
        for user in users:
            villages = user.bhu_patwari_village_ids
            if not villages:
                if include_patwaris_without_villages:
                    yield user, False, False
                continue
            for village in villages.sorted(
                key=lambda v: (
                    (v.tehsil_id.name or '').lower(),
                    (v.name or '').lower(),
                    v.id,
                )
            ):
                projects = Project.search([('village_ids', 'in', village.ids)])
                if not projects:
                    yield user, village, False
                    continue
                for project in projects.sorted(key=lambda p: (p.name or '').lower()):
                    yield user, village, project

    @staticmethod
    def _row_sort_key_patwari_export(user, village, project, dept_name, project_name, tehsil_name, village_name):
        """Group rows by department (same name adjacent for Excel merge); stable sub-order."""
        d = (dept_name or '').strip()
        dept_bucket = (0, d.casefold()) if d else (1, '')
        vn_id = village.id if village else 0
        pr_id = project.id if project else 0
        return (
            dept_bucket,
            (project_name or '').casefold(),
            (tehsil_name or '').casefold(),
            (village_name or '').casefold(),
            (user.name or '').casefold(),
            vn_id,
            pr_id,
            user.id,
        )

    def _runs_same_adjacent(self, seq):
        """Return list of (start_index, end_index) inclusive for consecutive equal values."""
        if not seq:
            return []
        runs = []
        i = 0
        n = len(seq)
        while i < n:
            j = i + 1
            while j < n and seq[j] == seq[i]:
                j += 1
            runs.append((i, j - 1))
            i = j
        return runs

    def _patwari_sorted_roster_entries(self, include_patwaris_without_villages=False):
        """Sorted roster rows as dicts with cells + underlying records for reconcile."""
        domain = self._patwari_users_domain()
        users = self.env['res.users'].sudo().search(domain, order='district_id,name,id')
        pending = []
        for user, village, project in self._iter_export_lines(
            users, include_patwaris_without_villages
        ):
            if village:
                tehsil_name = village.tehsil_id.name if village.tehsil_id else ''
                tehsildar = ''
                if village.tehsil_id and village.tehsil_id.user_id:
                    tehsildar = village.tehsil_id.user_id.name or ''
                subdiv = village.sub_division_id.name if village.sub_division_id else ''
                sdm = ''
                if village.sub_division_id and village.sub_division_id.user_id:
                    sdm = village.sub_division_id.user_id.name or ''
                village_name = self._label_with_optional_code(village.name, village.village_code)
            else:
                tehsil_name = tehsildar = subdiv = sdm = village_name = ''

            if project:
                dept_name = project.department_id.name if project.department_id else ''
                project_name = self._label_with_optional_code(project.name, project.code)
            else:
                dept_name = project_name = ''

            sk = self._row_sort_key_patwari_export(
                user, village, project, dept_name, project_name,
                tehsil_name, village_name,
            )
            pending.append([
                sk,
                [
                    0,
                    tehsil_name,
                    tehsildar,
                    subdiv,
                    sdm,
                    dept_name,
                    project_name,
                    village_name,
                    user.name or '',
                    user.mobile or '',
                    self._user_email_display(user),
                    _('DONE'),
                ],
                user,
                village,
                project,
            ])

        pending.sort(key=lambda x: x[0])
        entries = []
        for seq, triple in enumerate(pending, start=1):
            _sk, cells, user, village, project = triple
            row = list(cells)
            row[0] = seq
            entries.append({'cells': row, 'user': user, 'village': village, 'project': project})
        return entries

    def _export_users_excel(self):
        """Patwari roster; rows sorted by department then project/geo; header colour +
        zebra rows; merge consecutive identical dept (F) and project (G) cells.
        """
        if not HAS_XLSXWRITER:
            raise UserError(_(
                'xlsxwriter library is not installed. Please install it to export Excel files.'
            ))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_('Patwari Users'))

        header_fmt = self._header_format(workbook)

        # Match government-style column layout (Hindi headers + Email + status)
        headers = [
            _('स. क्र.'),
            _('तहसील का नाम'),
            _('तहसीलदार'),
            _('Sub Division'),
            _('SDM'),
            _('अपेक्षक निकाय/विभाग का नाम'),
            _('प्रस्तावित परियोजना का नाम'),
            _('प्रभावित ग्राम का नाम'),
            _('पटवारी का नाम'),
            _('पटवारी का मोबाइल'),
            _('Email ID'),
            _('Status'),
        ]
        widths = [6, 20, 22, 22, 22, 34, 46, 36, 26, 14, 36, 12]
        for col, w in enumerate(widths):
            worksheet.set_column(col, col, w)

        for col, title in enumerate(headers):
            worksheet.write(0, col, title, header_fmt)

        dept_col = 5
        project_col = 6

        entries = self._patwari_sorted_roster_entries(self.include_patwaris_without_villages)
        table_rows = [e['cells'] for e in entries]

        n = len(table_rows)
        dept_series = [r[dept_col] for r in table_rows]
        project_series = [r[project_col] for r in table_rows]

        for i in range(n):
            rnum = i + 1
            fmt = self._data_row_format(workbook, rnum)
            row = table_rows[i]
            for col in range(12):
                if col in (dept_col, project_col):
                    continue
                worksheet.write(rnum, col, row[col], fmt)

        for start, end in self._runs_same_adjacent(dept_series):
            r1, r2 = start + 1, end + 1
            val = dept_series[start]
            mfmt = self._data_row_format(workbook, r1)
            if r1 == r2:
                worksheet.write(r1, dept_col, val, mfmt)
            else:
                worksheet.merge_range(r1, dept_col, r2, dept_col, val, mfmt)

        for start, end in self._runs_same_adjacent(project_series):
            r1, r2 = start + 1, end + 1
            val = project_series[start]
            mfmt = self._data_row_format(workbook, r1)
            if r1 == r2:
                worksheet.write(r1, project_col, val, mfmt)
            else:
                worksheet.merge_range(r1, project_col, r2, project_col, val, mfmt)

        workbook.close()
        output.seek(0)
        return base64.b64encode(output.read()).decode()

    @staticmethod
    def _normalize_mobile_digits(val):
        digits = ''.join(c for c in str(val or '') if c.isdigit())
        if len(digits) >= 10:
            return digits[-10:]
        return digits

    @staticmethod
    def _extract_bracket_code_prefix(cell_text):
        if not cell_text:
            return ''
        match = re.match(r'^\s*\[([^\]]+)\]', cell_text.strip())
        return match.group(1).strip() if match else ''

    @staticmethod
    def _sheet_village_plain_label(cell_text):
        if not cell_text:
            return ''
        return re.sub(r'^\[[^\]]+\]\s*', '', cell_text.strip()).strip()

    def _village_cells_overlap(self, odoo_disp, odoo_plain_name, odoo_code, sheet_cell_raw):
        """Loose equality between Odoo roster village column and sheet village cell."""
        sc = (sheet_cell_raw or '').strip()
        if not sc:
            return False
        sc_fold = sc.casefold()
        code_s = self._extract_bracket_code_prefix(sc).lower()
        plain_s = self._sheet_village_plain_label(sc).casefold()

        odisp = (odoo_disp or '').strip().casefold()
        oc = (odoo_code or '').strip().lower()
        opn = (odoo_plain_name or '').strip().casefold()

        if oc and code_s and oc == code_s:
            return True
        if odisp and sc_fold and odisp == sc_fold:
            return True
        if opn and plain_s and (opn == plain_s or opn in plain_s or plain_s in opn):
            return True
        if odisp and plain_s and (plain_s in odisp or odisp in plain_s):
            return True
        return False

    def _patwari_sheet_csv_url(self):
        url = self.env['ir.config_parameter'].sudo().get_param(
            'bhukhadan_core.patwari_google_sheet_csv_url',
            DEFAULT_BHU_PATWARI_GOOGLE_SHEET_CSV_URL,
        )
        url = (url or '').strip()
        return url or DEFAULT_BHU_PATWARI_GOOGLE_SHEET_CSV_URL

    def _fetch_patwari_google_sheet_csv_rows(self):
        url = self._patwari_sheet_csv_url()
        request = Request(url, headers={'User-Agent': 'Odoo-BhuKhadan-Patwari-Reconcile/1.0'})
        try:
            with urlopen(request, timeout=120) as response:
                raw = response.read()
        except HTTPError as err:
            raise UserError(_(
                'Google Sheet returned HTTP %(code)s when downloading CSV export. '
                'Share the sheet so anyone with the link can view it, or set system '
                'parameter bhukhadan_core.patwari_google_sheet_csv_url to a reachable CSV URL.'
            ) % {'code': err.code}) from err
        except URLError as err:
            raise UserError(_(
                'Could not download Google Sheet CSV (%(reason)s). '
                'Check network access and parameter bhukhadan_core.patwari_google_sheet_csv_url.'
            ) % {'reason': err.reason or err}) from err
        except Exception as err:
            raise UserError(_('Could not download Google Sheet CSV: %s') % str(err)) from err

        text = raw.decode('utf-8-sig', errors='replace')
        return list(csv.reader(io.StringIO(text)))

    def _detect_patwari_sheet_columns(self, headers):
        village_idx = mobile_idx = patwari_idx = None
        for i, raw in enumerate(headers):
            cell = raw or ''
            low = cell.strip().lower()
            if mobile_idx is None and ('mobile' in low or 'मोबाइल' in cell):
                mobile_idx = i
            if village_idx is None and (
                'ग्राम' in cell or 'village' in low or 'प्रभावित' in cell
            ):
                village_idx = i
            if patwari_idx is None and 'पटवारी' in cell:
                patwari_idx = i

        if len(headers) >= 11:
            village_idx = village_idx if village_idx is not None else _ROSTER_COL_VILLAGE
            mobile_idx = mobile_idx if mobile_idx is not None else _ROSTER_COL_PATWARI_MOBILE
            patwari_idx = patwari_idx if patwari_idx is not None else _ROSTER_COL_PATWARI_NAME

        if village_idx is None or mobile_idx is None:
            raise UserError(_(
                'Could not detect Village / Mobile columns in the Google Sheet CSV header. '
                'Use headers containing ग्राम / Village and मोबाइल / Mobile, or align columns '
                'with the Odoo Patwari export.'
            ))
        return {'village': village_idx, 'mobile': mobile_idx, 'patwari': patwari_idx}

    def _parse_patwari_google_sheet(self, csv_rows):
        if len(csv_rows) < 2:
            raise UserError(_(
                'Google Sheet CSV must contain a header row and at least one data row.'
            ))

        headers = csv_rows[0]
        cmap = self._detect_patwari_sheet_columns(headers)
        vi, mi, pi = cmap['village'], cmap['mobile'], cmap['patwari']

        def cell(row, idx):
            return row[idx] if idx < len(row) else ''

        parsed = []
        for raw in csv_rows[1:]:
            if not raw or not any((c or '').strip() for c in raw):
                continue
            vil_raw = cell(raw, vi)
            mob_raw = cell(raw, mi)
            pname_raw = cell(raw, pi) if pi is not None else ''
            mob_d = self._normalize_mobile_digits(mob_raw)
            pname_f = (pname_raw or '').strip().casefold()
            if not mob_d and not vil_raw.strip() and not pname_f:
                continue
            parsed.append({
                'mob': mob_d,
                'pname': pname_f,
                'vil_raw': vil_raw,
                'raw': raw,
            })
        return headers, parsed

    def _classify_odoo_row_against_sheet(self, entry, sheet_parsed, sheet_used):
        """Return ``('ok', sheet_idx)``, ``('vil_mismatch', None)``, or ``('missing', None)``."""
        user = entry['user']
        village = entry['village']
        mob_o = self._normalize_mobile_digits(user.mobile)
        pname_o = (user.name or '').strip().casefold()
        cells = entry['cells']
        vil_disp = cells[_ROSTER_COL_VILLAGE]
        vil_plain = (village.name or '').strip() if village else ''
        vil_code = (village.village_code or '').strip() if village else ''

        match_idx = None
        mob_only_mismatch_idx = None
        name_conflict_idx = None

        for j, srow in enumerate(sheet_parsed):
            if sheet_used[j]:
                continue
            mob_s = srow['mob']
            vil_ok = self._village_cells_overlap(
                vil_disp, vil_plain, vil_code, srow['vil_raw']
            )

            if mob_o and mob_s:
                if mob_o != mob_s:
                    continue
                if vil_ok:
                    match_idx = j
                    break
                mob_only_mismatch_idx = j
                continue

            if pname_o and srow['pname'] and pname_o == srow['pname']:
                if vil_ok:
                    match_idx = j
                    break
                name_conflict_idx = j

        if match_idx is not None:
            return 'ok', match_idx
        if mob_only_mismatch_idx is not None:
            return 'vil_mismatch', None
        if name_conflict_idx is not None:
            return 'vil_mismatch', None
        return 'missing', None

    def _issue_highlight_format(self, workbook):
        return workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': 1,
            'bg_color': '#FFC7CE',
            'font_color': '#9C0006',
        })

    def _export_patwari_sheet_reconcile_xlsx(self):
        """Single worksheet: rows that are not mapped between Odoo and the sheet + reason column."""
        if not HAS_XLSXWRITER:
            raise UserError(_(
                'xlsxwriter library is not installed. Please install it to export Excel files.'
            ))

        csv_rows = self._fetch_patwari_google_sheet_csv_rows()
        sheet_headers, sheet_parsed = self._parse_patwari_google_sheet(csv_rows)
        cmap = self._detect_patwari_sheet_columns(sheet_headers)
        vi, mi, pi = cmap['village'], cmap['mobile'], cmap['patwari']

        def raw_cell(raw, idx):
            return raw[idx] if idx < len(raw) else ''

        entries = self._patwari_sorted_roster_entries(self.include_patwaris_without_villages)
        sheet_used = [False] * len(sheet_parsed)

        statuses = []
        for entry in entries:
            code, sidx = self._classify_odoo_row_against_sheet(entry, sheet_parsed, sheet_used)
            if code == 'ok' and sidx is not None:
                sheet_used[sidx] = True
            statuses.append(code)

        problem_rows = []
        for i, entry in enumerate(entries):
            sync = statuses[i]
            if sync == 'ok':
                continue
            if sync == 'missing':
                reason = _(
                    'Missing on Google Sheet — no CSV row matches this Patwari, mobile, and village '
                    '(check मोबाइल, ग्राम, and codes).'
                )
            else:
                reason = _(
                    'Village mismatch — sheet has the same mobile or Patwari name but a different '
                    'village / code than Odoo.'
                )
            problem_rows.append((list(entry['cells']), reason))

        for j, used in enumerate(sheet_used):
            if used:
                continue
            raw = sheet_parsed[j]['raw']
            extra = [''] * 12
            extra[_ROSTER_COL_VILLAGE] = raw_cell(raw, vi)
            extra[_ROSTER_COL_PATWARI_MOBILE] = raw_cell(raw, mi)
            if pi is not None:
                extra[_ROSTER_COL_PATWARI_NAME] = raw_cell(raw, pi)
            problem_rows.append((
                extra,
                _('Only on Google Sheet — no matching Odoo Patwari roster line.'),
            ))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Reconcile')
        header_fmt = self._header_format(workbook)
        hi_fmt = self._issue_highlight_format(workbook)

        headers = [
            _('स. क्र.'),
            _('तहसील का नाम'),
            _('तहसीलदार'),
            _('Sub Division'),
            _('SDM'),
            _('अपेक्षक निकाय/विभाग का नाम'),
            _('प्रस्तावित परियोजना का नाम'),
            _('प्रभावित ग्राम का नाम'),
            _('पटवारी का नाम'),
            _('पटवारी का मोबाइल'),
            _('Email ID'),
            _('Status'),
            _('Reason'),
        ]
        widths = [6, 20, 22, 22, 22, 34, 46, 36, 26, 14, 36, 12, 48]
        for col, w in enumerate(widths):
            ws.set_column(col, col, w)

        for col, title in enumerate(headers):
            ws.write(0, col, title, header_fmt)

        reason_col = 12
        if not problem_rows:
            ok_fmt = self._data_row_format(workbook, 1)
            ws.write(1, 0, 1, ok_fmt)
            for col in range(1, 12):
                ws.write(1, col, '', ok_fmt)
            ws.write(
                1, reason_col,
                _('No mapping gaps — Odoo roster lines match the Google Sheet.'),
                ok_fmt,
            )
        else:
            for rnum, (cells, reason) in enumerate(problem_rows, start=1):
                row = list(cells)
                row[0] = rnum
                for col in range(12):
                    ws.write(rnum, col, row[col], hi_fmt)
                ws.write(rnum, reason_col, reason, hi_fmt)

        workbook.close()
        output.seek(0)
        return base64.b64encode(output.read()).decode()

    def action_export_patwari_sheet_reconcile(self):
        """Compare Odoo Patwari roster to Google Sheet CSV and download highlighted Excel."""
        try:
            excel_data = self._export_patwari_sheet_reconcile_xlsx()
            filename = _('Patwari_Sheet_Reconcile_%s.xlsx') % datetime.now().strftime('%Y%m%d_%H%M%S')

            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': excel_data,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'res_model': 'res.users',
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        except UserError:
            raise
        except Exception as e:
            _logger.error('Patwari sheet reconcile failed: %s', str(e), exc_info=True)
            raise UserError(_('Error generating reconcile report: %s') % str(e)) from e

    def action_export_excel(self):
        """Export Patwari users report to Excel."""
        try:
            excel_data = self._export_users_excel()
            filename = _('Patwari_Users_Report_%s.xlsx') % datetime.now().strftime('%Y%m%d_%H%M%S')

            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': excel_data,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'res_model': 'res.users',
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        except Exception as e:
            _logger.error('Error exporting Patwari users report: %s', str(e), exc_info=True)
            raise UserError(_('Error generating Excel report: %s') % str(e)) from e
