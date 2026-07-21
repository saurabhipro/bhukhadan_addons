# -*- coding: utf-8 -*-
"""Import Tehsildar, SDM, and Patwari users from the government roster XLSX layout."""

import base64
import io
import re

from odoo.exceptions import ValidationError

# 0-based column indexes when headers match the Patwari export / Google Sheet layout.
_DEFAULT_COL_MAP = {
    'tehsil': 1,
    'tehsildar': 2,
    'sub_division': 3,
    'sdm': 4,
    'village': 7,
    'patwari': 8,
    'mobile': 9,
    'email': 10,
}

_ROLE_LABELS = {
    'tehsildar': 'Tehsildar',
    'nodal_officer_lr': 'SDM',
    'halka_patwari': 'Patwari',
}


def _cell_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).strip()


def _normalize_mobile(val):
    digits = ''.join(c for c in str(val or '') if c.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def _normalize_name_key(name):
    return re.sub(r'\s+', ' ', (name or '').strip()).casefold()


def _strip_bilingual_label(text):
    raw = _cell_text(text)
    if not raw:
        return ''
    if '/' in raw:
        parts = [p.strip() for p in raw.split('/') if p.strip()]
        if parts:
            return parts[0]
    return raw


def _extract_bracket_code(cell_text):
    if not cell_text:
        return ''
    match = re.match(r'^\s*\[([^\]]+)\]', cell_text.strip())
    return match.group(1).strip() if match else ''


def _plain_village_label(cell_text):
    if not cell_text:
        return ''
    return re.sub(r'^\[[^\]]+\]\s*', '', cell_text.strip()).strip()


def _detect_column_map(headers):
    col_map = dict(_DEFAULT_COL_MAP)
    for idx, raw in enumerate(headers):
        cell = raw or ''
        low = cell.strip().lower()
        if 'तहसील' in cell and 'तहसीलदार' not in cell:
            col_map['tehsil'] = idx
        elif 'तहसीलदार' in cell or low == 'tehsildar':
            col_map['tehsildar'] = idx
        elif 'sub division' in low or 'उपभाग' in cell:
            col_map['sub_division'] = idx
        elif low == 'sdm' or cell.strip() == 'SDM':
            col_map['sdm'] = idx
        elif 'ग्राम' in cell or 'village' in low or 'प्रभावित' in cell:
            col_map['village'] = idx
        elif 'पटवारी' in cell and 'मोबाइल' not in cell:
            col_map['patwari'] = idx
        elif 'mobile' in low or 'मोबाइल' in cell:
            col_map['mobile'] = idx
        elif 'email' in low or 'e-mail' in low:
            col_map['email'] = idx
    return col_map


def _load_xlsx_rows(file_content, filename):
    try:
        from openpyxl import load_workbook
    except ImportError as err:
        raise ValidationError(
            "Python library 'openpyxl' is required to import .xlsx files."
        ) from err

    raw = base64.b64decode(file_content)
    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    sheet = wb.active
    rows = []
    for row in sheet.iter_rows(values_only=True):
        rows.append([_cell_text(c) for c in row])
    wb.close()
    if not rows:
        raise ValidationError('The Excel file is empty.')
    return rows


def _find_master_by_name(env, model, label, district_id=None):
    plain = _strip_bilingual_label(label)
    if not plain:
        return env[model].browse()

    domain = [('name', 'ilike', plain)]
    if district_id:
        domain.append(('district_id', '=', district_id))
    record = env[model].sudo().search(domain, limit=1)
    if record:
        return record

    # Fallback: match without district filter (single-district deployments).
    return env[model].sudo().search([('name', 'ilike', plain)], limit=1)


def _find_village(env, cell_text, district_id=None):
    plain = _plain_village_label(cell_text)
    code = _extract_bracket_code(cell_text)
    if not plain and not code:
        return env['bhu.village'].browse()

    Village = env['bhu.village'].sudo()
    if code:
        domain = [('village_code', '=ilike', code)]
        if district_id:
            domain.append(('district_id', '=', district_id))
        village = Village.search(domain, limit=1)
        if village:
            return village

    if plain:
        domain = ['|', ('name', '=ilike', plain), ('name', 'ilike', plain)]
        if district_id:
            domain = ['&', ('district_id', '=', district_id)] + domain
        village = Village.search(domain, limit=1)
        if village:
            return village
    return env['bhu.village'].browse()


def _assign_bhuarjan_groups(env, user, role):
    Users = env['res.users']
    role_groups = Users._bhuarjan_role_group_xml_ids()
    all_custom = Users._bhuarjan_all_group_xml_ids()
    all_group_ids = []
    for xid in all_custom:
        group = env.ref(xid, raise_if_not_found=False)
        if group:
            all_group_ids.append(group.id)

    current_ids = user.groups_id.ids
    kept = [gid for gid in current_ids if gid not in all_group_ids]
    group_ref = role_groups.get(role)
    if group_ref:
        group = env.ref(group_ref, raise_if_not_found=False)
        if group and group.id not in kept:
            kept.append(group.id)
    base_user = env.ref('base.group_user', raise_if_not_found=False)
    if base_user and base_user.id not in kept:
        kept.append(base_user.id)
    user.sudo().write({'groups_id': [(6, 0, kept)]})


def _make_login(env, role, name, email=None, mobile=None, district_id=None):
    if email:
        login = email.strip().lower()
        if login:
            return login

    slug = re.sub(r'[^a-z0-9]+', '.', _normalize_name_key(name)).strip('.') or 'user'
    prefix = {
        'halka_patwari': 'patwari',
        'tehsildar': 'tehsildar',
        'nodal_officer_lr': 'sdm',
    }.get(role, 'user')
    if mobile:
        base = f'{prefix}.{mobile}'
    else:
        base = f'{prefix}.{slug}'
    if district_id:
        base = f'{base}.d{district_id}'
    candidate = f'{base}@import.bhuarjan'
    suffix = 1
    Users = env['res.users'].sudo()
    while Users.search_count([('login', '=', candidate)]):
        suffix += 1
        candidate = f'{base}{suffix}@import.bhuarjan'
    return candidate


def _find_existing_user(env, role, name, login=None, mobile=None, district_id=None):
    Users = env['res.users'].sudo()
    if mobile:
        user = Users.search([('mobile', '=', mobile)], limit=1)
        if user:
            return user
    if login:
        user = Users.search([('login', '=', login)], limit=1)
        if user:
            return user
    name_key = _normalize_name_key(name)
    if not name_key:
        return Users.browse()
    domain = [('bhuarjan_role', '=', role), ('name', 'ilike', name.strip())]
    if district_id:
        domain.append(('district_id', '=', district_id))
    candidates = Users.search(domain)
    for user in candidates:
        if _normalize_name_key(user.name) == name_key:
            return user
    return Users.browse()


def _ensure_user(env, cache, role, name, email=None, mobile=None, district_id=None,
                 state_id=None, update_existing=False, dry_run=False, log_lines=None):
    name = (name or '').strip()
    if not name:
        return None, 'skipped', None

    mobile = _normalize_mobile(mobile) or False
    login = (email or '').strip().lower() or None
    cache_key = (role, mobile or login or _normalize_name_key(name))

    if cache_key in cache:
        cached = cache[cache_key]
        return cached, 'cached', cached.name if cached else name

    existing = _find_existing_user(env, role, name, login=login, mobile=mobile, district_id=district_id)
    vals = {'name': name, 'bhuarjan_role': role}
    if mobile:
        vals['mobile'] = mobile
    if district_id:
        vals['district_id'] = district_id
    if state_id:
        vals['state_id'] = state_id

    if existing:
        if update_existing:
            if not dry_run:
                existing.sudo().write(vals)
                _assign_bhuarjan_groups(env, existing, role)
            cache[cache_key] = existing
            if log_lines is not None:
                log_lines.append(f'  Updated {_ROLE_LABELS[role]}: {name}')
            return existing, 'updated', name
        cache[cache_key] = existing
        return existing, 'existing', name

    login = _make_login(env, role, name, email=login, mobile=mobile, district_id=district_id)
    vals['login'] = login
    vals['active'] = True
    company = env.user.company_id or env.company
    if company:
        vals['company_id'] = company.id
        vals['company_ids'] = [(6, 0, [company.id])]

    if dry_run:
        cache[cache_key] = existing or env['res.users'].browse()
        if log_lines is not None:
            log_lines.append(f'  Would create {_ROLE_LABELS[role]}: {name} ({login})')
        return cache[cache_key], 'created', name

    user = env['res.users'].sudo().create(vals)
    _assign_bhuarjan_groups(env, user, role)
    cache[cache_key] = user
    if log_lines is not None:
        log_lines.append(f'  Created {_ROLE_LABELS[role]}: {name} ({login})')
    return user, 'created', name


def _link_master(master, user, field_name, dry_run, log_lines, label, user_display_name=None):
    if not master:
        return False
    display_name = user_display_name or (user.name if user else '')
    if not display_name:
        return False
    current = master[field_name]
    if current and user and current.id != user.id:
        if log_lines is not None:
            log_lines.append(
                f'  Warning: {label} "{master.display_name}" already linked to '
                f'"{current.display_name}" — skipped relink to "{display_name}".'
            )
        return False
    if current and user and current.id == user.id:
        return False
    if not dry_run and user and user.id:
        master.sudo().write({field_name: user.id})
    if log_lines is not None:
        action = 'Would link' if dry_run else 'Linked'
        log_lines.append(f'  {action} {label} "{master.display_name}" → {display_name}')
    return True


def import_user_roster_xlsx(env, file_content, filename, district_id=None,
                            update_existing=False, dry_run=False):
    """Parse roster XLSX and create/link Tehsildar, SDM, and Patwari users."""
    stats = {
        'created': 0,
        'updated': 0,
        'tehsils_linked': 0,
        'subdivisions_linked': 0,
        'villages_linked': 0,
        'rows': 0,
        'errors': 0,
        'skipped': 0,
    }
    log_lines = []
    prefix = '[DRY RUN] ' if dry_run else ''
    log_lines.append(f'{prefix}User roster import started for file: {filename or "upload.xlsx"}')

    rows = _load_xlsx_rows(file_content, filename)
    headers = rows[0]
    col_map = _detect_column_map(headers)
    log_lines.append(
        f'Columns: tehsil={col_map["tehsil"]}, tehsildar={col_map["tehsildar"]}, '
        f'sub_div={col_map["sub_division"]}, sdm={col_map["sdm"]}, '
        f'village={col_map["village"]}, patwari={col_map["patwari"]}, '
        f'mobile={col_map["mobile"]}, email={col_map["email"]}'
    )

    district = env['bhu.district'].browse(district_id) if district_id else env['bhu.district'].browse()
    state_id = district.state_id.id if district else False

    user_cache = {}

    def cell(row, key):
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return ''
        return row[idx]

    for row_num, row in enumerate(rows[1:], start=2):
        if not row or not any(c for c in row):
            continue

        tehsil_name = cell(row, 'tehsil')
        tehsildar_name = cell(row, 'tehsildar')
        subdiv_name = cell(row, 'sub_division')
        sdm_name = cell(row, 'sdm')
        village_cell = cell(row, 'village')
        patwari_name = cell(row, 'patwari')
        mobile = cell(row, 'mobile')
        email = cell(row, 'email')

        if not any([tehsildar_name, sdm_name, patwari_name]):
            continue

        stats['rows'] += 1
        log_lines.append(f'Row {row_num}:')

        try:
            tehsil = _find_master_by_name(env, 'bhu.tehsil', tehsil_name, district_id) if tehsil_name else env['bhu.tehsil'].browse()
            subdiv = _find_master_by_name(env, 'bhu.sub.division', subdiv_name, district_id) if subdiv_name else env['bhu.sub.division'].browse()
            village = _find_village(env, village_cell, district_id) if village_cell else env['bhu.village'].browse()

            row_district_id = district_id
            row_state_id = state_id
            if village and village.district_id:
                row_district_id = village.district_id.id
                row_state_id = village.state_id.id or row_state_id
            elif tehsil and tehsil.district_id:
                row_district_id = tehsil.district_id.id
                row_state_id = tehsil.state_id.id or row_state_id
            elif subdiv and subdiv.district_id:
                row_district_id = subdiv.district_id.id
                row_state_id = subdiv.state_id.id or row_state_id

            if tehsildar_name:
                if tehsil_name and not tehsil:
                    log_lines.append(f'  Warning: Tehsil not found: {tehsil_name}')
                user, status, display_name = _ensure_user(
                    env, user_cache, 'tehsildar', tehsildar_name,
                    district_id=row_district_id, state_id=row_state_id,
                    update_existing=update_existing, dry_run=dry_run, log_lines=log_lines,
                )
                if status == 'created':
                    stats['created'] += 1
                elif status == 'updated':
                    stats['updated'] += 1
                if tehsil and display_name and _link_master(
                    tehsil, user, 'user_id', dry_run, log_lines, 'Tehsil', display_name,
                ):
                    stats['tehsils_linked'] += 1

            if sdm_name:
                if subdiv_name and not subdiv:
                    log_lines.append(f'  Warning: Sub Division not found: {subdiv_name}')
                user, status, display_name = _ensure_user(
                    env, user_cache, 'nodal_officer_lr', sdm_name,
                    district_id=row_district_id, state_id=row_state_id,
                    update_existing=update_existing, dry_run=dry_run, log_lines=log_lines,
                )
                if status == 'created':
                    stats['created'] += 1
                elif status == 'updated':
                    stats['updated'] += 1
                if subdiv and display_name and _link_master(
                    subdiv, user, 'user_id', dry_run, log_lines, 'Sub Division', display_name,
                ):
                    stats['subdivisions_linked'] += 1

            if patwari_name:
                if village_cell and not village:
                    log_lines.append(f'  Warning: Village not found: {village_cell}')
                user, status, display_name = _ensure_user(
                    env, user_cache, 'halka_patwari', patwari_name,
                    email=email, mobile=mobile,
                    district_id=row_district_id, state_id=row_state_id,
                    update_existing=update_existing, dry_run=dry_run, log_lines=log_lines,
                )
                if status == 'created':
                    stats['created'] += 1
                elif status == 'updated':
                    stats['updated'] += 1
                if village and display_name and _link_master(
                    village, user, 'user_id', dry_run, log_lines, 'Village', display_name,
                ):
                    stats['villages_linked'] += 1

        except Exception as err:
            stats['errors'] += 1
            log_lines.append(f'  ERROR: {err}')

    summary = (
        f'{prefix}Done — rows: {stats["rows"]}, users created: {stats["created"]}, '
        f'updated: {stats["updated"]}, tehsils linked: {stats["tehsils_linked"]}, '
        f'sub divisions linked: {stats["subdivisions_linked"]}, '
        f'villages linked: {stats["villages_linked"]}, errors: {stats["errors"]}.'
    )
    log_lines.insert(1, summary)
    return stats, '\n'.join(log_lines)
