# -*- coding: utf-8 -*-
"""Helpers for BhuKhadan survey REST API."""

import base64
import logging
from datetime import datetime, timezone

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

LANDOWNER_WRITABLE = (
    'name', 'father_name', 'mother_name', 'spouse_name', 'caste', 'phone',
    'village_id', 'rakba', 'aadhar_number', 'bank_name', 'bank_branch',
    'account_number', 'ifsc_code', 'account_holder_name',
)

HOUSE_OWNER_WRITABLE = (
    'name', 'aadhar_number', 'phone', 'caste', 'dob', 'village_id',
    'house_number', 'mohalla',
    'doc_electricity_bill', 'doc_voter_card_owner', 'doc_aadhar_owner',
    'doc_aadhar_witness_1', 'doc_aadhar_witness_2', 'doc_ration_owner',
    'doc_education_owner', 'doc_aadhar_landowner', 'doc_affidavit_noc',
    'doc_passport_photos', 'doc_pan_owner', 'doc_pan_landowner',
    'doc_bank_passbook', 'doc_bank_neft_form', 'doc_bank_ifsc',
    'doc_other', 'doc_other_text',
)

SURVEY_WRITABLE = {
    'project_id', 'department_id', 'village_id', 'tehsil_id', 'area_id', 'survey_date',
    'survey_type', 'khasra_number', 'khata_no', 'land_acquire_year', 'total_area', 'acquired_area',
    'has_traded_land', 'traded_land_area', 'distance_from_main_road',
    'crop_type_id', 'irrigation_type',
    'has_house', 'house_type', 'house_area', 'has_shed', 'shed_area',
    'has_well', 'well_type', 'well_count', 'has_tubewell', 'tubewell_count',
    'has_pond', 'latitude', 'longitude', 'location_accuracy',
    'location_timestamp', 'remarks', 'state',
}


def api_json_error(message, error_code='VALIDATION_ERROR', fields=None, status=400):
    payload = {'success': False, 'error': error_code, 'message': message}
    if fields:
        payload['fields'] = fields
    return payload, status


def api_resolve_tehsil_id(env, village_id, tehsil_id=None):
    if tehsil_id:
        try:
            tid = int(tehsil_id)
        except (TypeError, ValueError):
            tid = False
        if tid and env['bhu.tehsil'].sudo().browse(tid).exists():
            return tid
    if not village_id:
        return False
    village = env['bhu.village'].sudo().browse(int(village_id))
    return village.tehsil_id.id if village.exists() and village.tehsil_id else False


def api_patwari_survey_domain(user):
    return ['|', ('user_id', '=', user.id), ('village_id.user_id', '=', user.id)]


def api_user_can_access_survey(user, survey):
    if not survey or not survey.exists():
        return False
    if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
        return True
    if user.bhuarjan_role not in user.env['res.users'].BHUKHADAN_PATWARI_ROLES:
        return True
    return (
        survey.user_id.id == user.id
        or (survey.village_id and survey.village_id.user_id.id == user.id)
    )


def api_resolve_survey(env, survey_id=None, survey_uuid=None):
    Survey = env['bhu.survey'].sudo()
    survey = Survey.browse()
    if survey_id:
        try:
            survey = Survey.browse(int(survey_id))
        except (TypeError, ValueError):
            survey = Survey.search([('survey_uuid', '=', str(survey_id))], limit=1)
    if not survey.exists() and survey_uuid:
        survey = Survey.search([('survey_uuid', '=', str(survey_uuid))], limit=1)
    return survey


def _api_int_query_arg(args, name):
    raw = args.get(name)
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f'Invalid {name}: must be an integer')


def api_build_survey_list_domain(env, args):
    """Build list domain with optional department → project → village filters."""
    domain = []
    department_id = _api_int_query_arg(args, 'department_id')
    project_id = _api_int_query_arg(args, 'project_id')
    village_id = _api_int_query_arg(args, 'village_id')
    project = env['bhu.project'].sudo().browse()

    if department_id:
        if not env['bhu.department'].sudo().browse(department_id).exists():
            raise ValidationError(f'department_id {department_id} does not exist')
        domain.append(('department_id', '=', department_id))

    if project_id:
        project = env['bhu.project'].sudo().browse(project_id)
        if not project.exists():
            raise ValidationError(f'project_id {project_id} does not exist')
        if department_id and project.department_id.id != department_id:
            raise ValidationError('project_id does not belong to the specified department_id')
        domain.append(('project_id', '=', project_id))

    if village_id:
        village = env['bhu.village'].sudo().browse(village_id)
        if not village.exists():
            raise ValidationError(f'village_id {village_id} does not exist')
        if project_id and village_id not in project.village_ids.ids:
            raise ValidationError('village_id does not belong to the specified project_id')
        domain.append(('village_id', '=', village_id))

    state = args.get('state')
    if state:
        if state.lower() == 'pending':
            domain.append(('state', '!=', 'approved'))
        else:
            domain.append(('state', '=', state))

    if args.get('q'):
        domain.append(('khasra_number', 'ilike', args.get('q')))

    return domain


def _vals_from_dict(data, fields, default_village_id=None):
    vals = {}
    for field in fields:
        if field in data and data[field] is not None and data[field] != '':
            vals[field] = data[field]
    if default_village_id and 'village_id' not in vals:
        vals['village_id'] = default_village_id
    return vals


def api_landowner_o2m_commands(env, data, default_village_id=None, replace_existing=False):
    Landowner = env['bhu.landowner'].sudo()
    commands = []
    if 'landowners' in data and isinstance(data['landowners'], list):
        if replace_existing:
            commands.append((5, 0, 0))
        for index, item in enumerate(data['landowners']):
            if not isinstance(item, dict):
                raise ValidationError(f'landowners[{index}] must be an object')
            vals = _vals_from_dict(item, LANDOWNER_WRITABLE, default_village_id)
            if not vals.get('name'):
                raise ValidationError(f'landowners[{index}].name is required')
            record_id = item.get('id')
            if record_id:
                if not Landowner.browse(int(record_id)).exists():
                    raise ValidationError(f'Landowner ID {record_id} does not exist')
                commands.append((1, int(record_id), vals))
            else:
                commands.append((0, 0, vals))
        return commands

    ids = data.get('landowner_ids')
    if isinstance(ids, list) and ids:
        valid = []
        for lid in ids:
            lo = Landowner.browse(int(lid))
            if not lo.exists():
                raise ValidationError(f'Landowner ID {lid} does not exist')
            if lo.survey_id:
                raise ValidationError(f'Landowner ID {lid} is already linked to a survey')
            valid.append(lo.id)
        return [(6, 0, valid)]
    return []


def api_house_owner_o2m_commands(env, data, default_village_id=None, replace_existing=False):
    HouseOwner = env['bhu.house.owner'].sudo()
    commands = []
    if 'house_owners' in data and isinstance(data['house_owners'], list):
        if replace_existing:
            commands.append((5, 0, 0))
        for index, item in enumerate(data['house_owners']):
            if not isinstance(item, dict):
                raise ValidationError(f'house_owners[{index}] must be an object')
            vals = _vals_from_dict(item, HOUSE_OWNER_WRITABLE, default_village_id)
            if not vals.get('name'):
                raise ValidationError(f'house_owners[{index}].name is required')
            record_id = item.get('id')
            if record_id:
                if not HouseOwner.browse(int(record_id)).exists():
                    raise ValidationError(f'House owner ID {record_id} does not exist')
                commands.append((1, int(record_id), vals))
            else:
                commands.append((0, 0, vals))
        return commands

    ids = data.get('house_owner_ids')
    if isinstance(ids, list) and ids:
        valid = []
        for hid in ids:
            ho = HouseOwner.browse(int(hid))
            if not ho.exists():
                raise ValidationError(f'House owner ID {hid} does not exist')
            if ho.survey_id:
                raise ValidationError(f'House owner ID {hid} is already linked to a survey')
            valid.append(ho.id)
        return [(6, 0, valid)]
    return []


def api_tree_line_commands(env, tree_lines):
    if not tree_lines:
        return []
    TreeMaster = env['bhu.tree.master'].sudo()
    commands = []
    for index, line in enumerate(tree_lines):
        if not isinstance(line, dict):
            continue
        tree_master_id = line.get('tree_master_id')
        if not tree_master_id:
            raise ValidationError(f'tree_lines[{index}].tree_master_id is required')
        master = TreeMaster.browse(int(tree_master_id))
        if not master.exists():
            raise ValidationError(f'Tree master ID {tree_master_id} does not exist')
        development_stage = line.get('development_stage')
        if development_stage not in ('undeveloped', 'semi_developed', 'fully_developed'):
            raise ValidationError(f'tree_lines[{index}].development_stage is invalid')
        vals = {
            'tree_master_id': master.id,
            'development_stage': development_stage,
            'quantity': int(line.get('quantity') or 1),
        }
        girth = line.get('girth_cm')
        if girth not in (None, ''):
            vals['girth_cm'] = float(girth)
        if line.get('id'):
            commands.append((1, int(line['id']), vals))
        else:
            commands.append((0, 0, vals))
    return commands


def api_resolve_crop_type_id(env, data):
    if 'crop_type_id' in data and data['crop_type_id']:
        return int(data['crop_type_id'])
    crop_type = data.get('crop_type')
    if isinstance(crop_type, int):
        return crop_type
    if isinstance(crop_type, str):
        code_map = {
            'single': 'SINGLE_CROP', 'single1': 'SINGLE_CROP',
            'double': 'DOUBLE_CROP', 'double1': 'DOUBLE_CROP',
        }
        code = code_map.get(crop_type.lower())
        if code:
            rec = env['bhu.land.type'].sudo().search([('code', '=', code)], limit=1)
            return rec.id if rec else False
    return False


def api_normalize_optional_selection(value, allowed=None):
    if value in (None, '', 'false', False):
        return False
    if allowed and value not in allowed:
        return None
    return value


def api_build_survey_vals(env, data, user_id=None):
    required = {
        'project_id': 'Project',
        'village_id': 'Village',
        'department_id': 'Department',
        'khasra_number': 'Khasra Number',
        'total_area': 'Total Area',
        'acquired_area': 'Acquired Area',
    }
    missing = [f for f in required if not data.get(f) and data.get(f) != 0]
    if missing:
        labels = [required[f] for f in missing]
        raise ValidationError(f'Missing required fields: {", ".join(labels)}')

    for ref_field, model in (
        ('project_id', 'bhu.project'),
        ('village_id', 'bhu.village'),
        ('department_id', 'bhu.department'),
    ):
        if not env[model].sudo().browse(int(data[ref_field])).exists():
            raise ValidationError(f'{ref_field} {data[ref_field]} does not exist')

    total_area = float(data['total_area'])
    acquired_area = float(data['acquired_area'])
    if total_area <= 0 or acquired_area <= 0:
        raise ValidationError('total_area and acquired_area must be greater than 0')
    if acquired_area > total_area:
        raise ValidationError('acquired_area cannot exceed total_area')

    default_village_id = data.get('village_id')
    landowner_commands = api_landowner_o2m_commands(env, data, default_village_id)
    if not landowner_commands:
        raise ValidationError('At least one landowner is required (landowners[] or landowner_ids[])')

    vals = {
        'user_id': user_id or env.user.id,
        'project_id': int(data['project_id']),
        'village_id': int(data['village_id']),
        'department_id': int(data['department_id']),
        'tehsil_id': api_resolve_tehsil_id(env, data['village_id'], data.get('tehsil_id')) or False,
        'khasra_number': data['khasra_number'],
        'total_area': total_area,
        'acquired_area': acquired_area,
        'survey_type': data.get('survey_type') or 'rural',
        'has_traded_land': data.get('has_traded_land') or 'no',
        'traded_land_area': float(data.get('traded_land_area') or 0.0),
        'distance_from_main_road': float(data.get('distance_from_main_road') or 0.0),
        'irrigation_type': data.get('irrigation_type') or 'irrigated',
        'has_house': data.get('has_house') or 'no',
        'house_area': float(data.get('house_area') or 0.0),
        'has_shed': data.get('has_shed') or 'no',
        'shed_area': float(data.get('shed_area') or 0.0),
        'has_well': data.get('has_well') or 'no',
        'well_count': int(data.get('well_count') or 0),
        'has_tubewell': data.get('has_tubewell') or 'no',
        'tubewell_count': int(data.get('tubewell_count') or 0),
        'has_pond': data.get('has_pond') or 'no',
        'latitude': data.get('latitude'),
        'longitude': data.get('longitude'),
        'location_accuracy': data.get('location_accuracy'),
        'location_timestamp': data.get('location_timestamp'),
        'remarks': data.get('remarks') or '',
        'state': data.get('state') or 'draft',
        'landowner_ids': landowner_commands,
    }

    if data.get('khata_no'):
        vals['khata_no'] = str(data['khata_no']).strip()
    if data.get('land_acquire_year'):
        vals['land_acquire_year'] = str(data['land_acquire_year']).strip()
    if data.get('area_id'):
        vals['area_id'] = int(data['area_id'])

    crop_type_id = api_resolve_crop_type_id(env, data)
    if crop_type_id:
        vals['crop_type_id'] = crop_type_id

    house_type = api_normalize_optional_selection(data.get('house_type'), ('kaccha', 'pakka'))
    if house_type is not None:
        vals['house_type'] = house_type
    well_type = api_normalize_optional_selection(data.get('well_type'), ('kaccha', 'pakka'))
    if well_type is not None:
        vals['well_type'] = well_type

    if data.get('survey_date'):
        vals['survey_date'] = data['survey_date']

    house_owner_commands = api_house_owner_o2m_commands(env, data, default_village_id)
    if house_owner_commands:
        vals['house_owner_ids'] = house_owner_commands

    tree_commands = api_tree_line_commands(env, data.get('tree_lines'))
    if tree_commands:
        vals['tree_line_ids'] = tree_commands

    return vals


def api_build_survey_update_vals(env, survey, data):
    vals = {}
    default_village_id = data.get('village_id', survey.village_id.id)

    for field in SURVEY_WRITABLE:
        if field not in data:
            continue
        value = data[field]
        if field in ('house_type', 'well_type'):
            normalized = api_normalize_optional_selection(value, ('kaccha', 'pakka'))
            if normalized is not None:
                vals[field] = normalized
            continue
        vals[field] = value

    if 'crop_type' in data or 'crop_type_id' in data:
        crop_type_id = api_resolve_crop_type_id(env, data)
        if crop_type_id:
            vals['crop_type_id'] = crop_type_id

    village_id = vals.get('village_id', survey.village_id.id)
    if village_id and 'tehsil_id' not in vals:
        resolved = api_resolve_tehsil_id(env, village_id, data.get('tehsil_id'))
        if resolved:
            vals['tehsil_id'] = resolved

    if 'landowners' in data or 'landowner_ids' in data:
        vals['landowner_ids'] = api_landowner_o2m_commands(
            env, data, default_village_id, replace_existing='landowners' in data,
        )
    if 'house_owners' in data or 'house_owner_ids' in data:
        house_cmds = api_house_owner_o2m_commands(
            env, data, default_village_id, replace_existing='house_owners' in data,
        )
        if house_cmds:
            vals['house_owner_ids'] = house_cmds

    if 'tree_lines' in data and isinstance(data['tree_lines'], list):
        vals['tree_line_ids'] = [(5, 0, 0)] + api_tree_line_commands(env, data['tree_lines'])

    if vals.get('state') == 'submitted' and not survey.submitted_date:
        vals['submitted_date'] = datetime.now(timezone.utc).replace(tzinfo=None)

    return vals


def api_assert_survey_editable(survey):
    if survey.state not in ('draft', 'submitted'):
        raise ValidationError(
            f'Survey cannot be edited in state "{survey.state}". '
            'Only draft or submitted surveys can be edited.'
        )


def api_add_survey_landowners(env, survey, data):
    """Create new or link existing landowners to a survey."""
    Landowner = env['bhu.landowner'].sudo()
    default_village_id = survey.village_id.id
    linked = Landowner.browse()
    has_payload = False

    owners = data.get('landowners')
    if owners is not None:
        if not isinstance(owners, list):
            raise ValidationError('landowners must be an array')
        if owners:
            has_payload = True
            for index, item in enumerate(owners):
                if not isinstance(item, dict):
                    raise ValidationError(f'landowners[{index}] must be an object')
                vals = _vals_from_dict(item, LANDOWNER_WRITABLE, default_village_id)
                if not vals.get('name'):
                    raise ValidationError(f'landowners[{index}].name is required')
                vals['survey_id'] = survey.id
                linked |= Landowner.create(vals)

    ids = data.get('landowner_ids')
    if ids is not None:
        if not isinstance(ids, list):
            raise ValidationError('landowner_ids must be an array')
        if ids:
            has_payload = True
            for lid in ids:
                landowner = Landowner.browse(int(lid))
                if not landowner.exists():
                    raise ValidationError(f'Landowner ID {lid} does not exist')
                if landowner.survey_id and landowner.survey_id.id != survey.id:
                    raise ValidationError(f'Landowner ID {lid} is already linked to another survey')
                if not landowner.survey_id:
                    landowner.write({'survey_id': survey.id})
                linked |= landowner

    if not has_payload:
        raise ValidationError('Provide landowners[] and/or landowner_ids[]')
    if not linked:
        raise ValidationError('No landowners were added')
    return linked


def api_add_survey_house_owners(env, survey, data):
    """Create new or link existing house owners to a survey."""
    HouseOwner = env['bhu.house.owner'].sudo()
    default_village_id = survey.village_id.id
    linked = HouseOwner.browse()
    has_payload = False

    owners = data.get('house_owners')
    if owners is not None:
        if not isinstance(owners, list):
            raise ValidationError('house_owners must be an array')
        if owners:
            has_payload = True
            for index, item in enumerate(owners):
                if not isinstance(item, dict):
                    raise ValidationError(f'house_owners[{index}] must be an object')
                vals = _vals_from_dict(item, HOUSE_OWNER_WRITABLE, default_village_id)
                if not vals.get('name'):
                    raise ValidationError(f'house_owners[{index}].name is required')
                vals['survey_id'] = survey.id
                linked |= HouseOwner.create(vals)

    ids = data.get('house_owner_ids')
    if ids is not None:
        if not isinstance(ids, list):
            raise ValidationError('house_owner_ids must be an array')
        if ids:
            has_payload = True
            for hid in ids:
                house_owner = HouseOwner.browse(int(hid))
                if not house_owner.exists():
                    raise ValidationError(f'House owner ID {hid} does not exist')
                if house_owner.survey_id and house_owner.survey_id.id != survey.id:
                    raise ValidationError(f'House owner ID {hid} is already linked to another survey')
                if not house_owner.survey_id:
                    house_owner.write({'survey_id': survey.id})
                linked |= house_owner

    if not has_payload:
        raise ValidationError('Provide house_owners[] and/or house_owner_ids[]')
    if not linked:
        raise ValidationError('No house owners were added')
    return linked


def api_add_survey_tree_lines(env, survey, data):
    """Append tree lines to a survey."""
    tree_lines = data.get('tree_lines')
    if not isinstance(tree_lines, list) or not tree_lines:
        raise ValidationError('tree_lines must be a non-empty array')

    TreeLine = env['bhu.survey.tree.line'].sudo()
    TreeMaster = env['bhu.tree.master'].sudo()
    created = TreeLine.browse()

    for index, line in enumerate(tree_lines):
        if not isinstance(line, dict):
            raise ValidationError(f'tree_lines[{index}] must be an object')
        tree_master_id = line.get('tree_master_id')
        if not tree_master_id:
            raise ValidationError(f'tree_lines[{index}].tree_master_id is required')
        master = TreeMaster.browse(int(tree_master_id))
        if not master.exists():
            raise ValidationError(f'Tree master ID {tree_master_id} does not exist')
        development_stage = line.get('development_stage')
        if development_stage not in ('undeveloped', 'semi_developed', 'fully_developed'):
            raise ValidationError(f'tree_lines[{index}].development_stage is invalid')
        vals = {
            'survey_id': survey.id,
            'tree_master_id': master.id,
            'development_stage': development_stage,
            'quantity': int(line.get('quantity') or 1),
        }
        girth = line.get('girth_cm')
        if girth not in (None, ''):
            vals['girth_cm'] = float(girth)
        record_id = line.get('id')
        if record_id:
            existing = TreeLine.browse(int(record_id))
            if not existing.exists() or existing.survey_id.id != survey.id:
                raise ValidationError(f'Tree line ID {record_id} does not belong to this survey')
            existing.write({key: val for key, val in vals.items() if key != 'survey_id'})
            created |= existing
        else:
            created |= TreeLine.create(vals)

    return created


def api_serialize_tree_line(line):
    return {
        'id': line.id,
        'tree_type': line.tree_type,
        'tree_master_id': line.tree_master_id.id if line.tree_master_id else None,
        'tree_name': line.tree_master_id.name if line.tree_master_id else '',
        'development_stage': line.development_stage,
        'girth_cm': line.girth_cm,
        'quantity': line.quantity,
    }


def api_serialize_landowner(record):
    return {
        'id': record.id,
        'name': record.name or '',
        'father_name': record.father_name or '',
        'mother_name': record.mother_name or '',
        'spouse_name': record.spouse_name or '',
        'caste': record.caste or '',
        'aadhar_number': record.aadhar_number or '',
        'rakba': record.rakba or '',
        'phone': record.phone or '',
        'village_id': record.village_id.id if record.village_id else None,
        'village_name': record.village_id.name if record.village_id else '',
        'bank_name': record.bank_name or '',
        'bank_branch': record.bank_branch or '',
        'account_number': record.account_number or '',
        'ifsc_code': record.ifsc_code or '',
        'account_holder_name': record.account_holder_name or '',
    }


def api_serialize_house_owner(record):
    data = {
        'id': record.id,
        'name': record.name or '',
        'aadhar_number': record.aadhar_number or '',
        'phone': record.phone or '',
        'caste': record.caste or '',
        'dob': record.dob.strftime('%Y-%m-%d') if record.dob else None,
        'village_id': record.village_id.id if record.village_id else None,
        'village_name': record.village_id.name if record.village_id else '',
        'house_number': record.house_number or '',
        'mohalla': record.mohalla or '',
    }
    for field in HOUSE_OWNER_WRITABLE:
        if field.startswith('doc_') and field not in data:
            if field == 'doc_other_text':
                data[field] = record.doc_other_text or ''
            else:
                data[field] = bool(getattr(record, field, False))
    return data


def api_serialize_tree_lines(survey):
    return [api_serialize_tree_line(line) for line in survey.tree_line_ids]


def api_serialize_survey(survey, include_image=False, summary=False):
    if summary:
        return {
            'id': survey.id,
            'name': survey.name or '',
            'survey_uuid': survey.survey_uuid or '',
            'khasra_number': survey.khasra_number or '',
            'project_id': survey.project_id.id if survey.project_id else None,
            'project_name': survey.project_id.name if survey.project_id else '',
            'village_id': survey.village_id.id if survey.village_id else None,
            'village_name': survey.village_id.name if survey.village_id else '',
            'tehsil_id': survey.tehsil_id.id if survey.tehsil_id else None,
            'tehsil_name': survey.tehsil_id.name if survey.tehsil_id else '',
            'survey_type': survey.survey_type or 'rural',
            'survey_date': survey.survey_date.strftime('%Y-%m-%d') if survey.survey_date else None,
            'total_area': survey.total_area,
            'acquired_area': survey.acquired_area,
            'state': survey.state or '',
            'user_id': survey.user_id.id if survey.user_id else None,
            'user_name': survey.user_id.name if survey.user_id else '',
            'landowners_count': len(survey.landowner_ids),
            'house_owners_count': len(survey.house_owner_ids),
            'photos_count': len(survey.photo_ids),
            'landowners': [api_serialize_landowner(lo) for lo in survey.landowner_ids],
            'landowner_ids': survey.landowner_ids.ids,
            'house_owners': [api_serialize_house_owner(ho) for ho in survey.house_owner_ids],
            'house_owner_ids': survey.house_owner_ids.ids,
            'tree_lines': api_serialize_tree_lines(survey),
        }

    survey_image = None
    if include_image and survey.survey_image:
        survey_image = base64.b64encode(survey.survey_image).decode('utf-8')

    return {
        'id': survey.id,
        'name': survey.name or '',
        'survey_uuid': survey.survey_uuid or '',
        'user_id': survey.user_id.id if survey.user_id else None,
        'user_name': survey.user_id.name if survey.user_id else '',
        'project_id': survey.project_id.id if survey.project_id else None,
        'project_name': survey.project_id.name if survey.project_id else '',
        'village_id': survey.village_id.id if survey.village_id else None,
        'village_name': survey.village_id.name if survey.village_id else '',
        'department_id': survey.department_id.id if survey.department_id else None,
        'department_name': survey.department_id.name if survey.department_id else '',
        'tehsil_id': survey.tehsil_id.id if survey.tehsil_id else None,
        'tehsil_name': survey.tehsil_id.name if survey.tehsil_id else '',
        'district_name': survey.district_name or '',
        'survey_type': survey.survey_type or 'rural',
        'khasra_number': survey.khasra_number or '',
        'khata_no': survey.khata_no or '',
        'land_acquire_year': survey.land_acquire_year or '',
        'total_area': survey.total_area,
        'acquired_area': survey.acquired_area,
        'has_traded_land': survey.has_traded_land or 'no',
        'traded_land_area': survey.traded_land_area or 0.0,
        'distance_from_main_road': survey.distance_from_main_road or 0.0,
        'is_within_distance_for_award': bool(survey.is_within_distance_for_award),
        'survey_date': survey.survey_date.strftime('%Y-%m-%d') if survey.survey_date else None,
        'submitted_date': survey.submitted_date.strftime('%Y-%m-%d %H:%M:%S') if survey.submitted_date else None,
        'crop_type_id': survey.crop_type_id.id if survey.crop_type_id else None,
        'crop_type_name': survey.crop_type_id.name if survey.crop_type_id else '',
        'irrigation_type': survey.irrigation_type,
        'tree_lines': api_serialize_tree_lines(survey),
        'photos': [{
            'id': photo.id,
            'photo_type_id': photo.photo_type_id.id if photo.photo_type_id else None,
            'photo_type_name': photo.photo_type_id.name if photo.photo_type_id else '',
            's3_url': photo.s3_url or '',
            'filename': photo.filename or '',
            'file_size': photo.file_size or 0,
            'latitude': photo.latitude,
            'longitude': photo.longitude,
        } for photo in survey.photo_ids],
        'has_house': survey.has_house,
        'house_type': survey.house_type,
        'house_area': survey.house_area,
        'has_shed': survey.has_shed,
        'shed_area': survey.shed_area,
        'has_well': survey.has_well,
        'well_type': survey.well_type,
        'well_count': survey.well_count or 0,
        'has_tubewell': survey.has_tubewell,
        'tubewell_count': survey.tubewell_count or 0,
        'has_pond': survey.has_pond,
        'latitude': survey.latitude,
        'longitude': survey.longitude,
        'location_accuracy': survey.location_accuracy,
        'location_timestamp': survey.location_timestamp.strftime('%Y-%m-%d %H:%M:%S') if survey.location_timestamp else None,
        'remarks': survey.remarks or '',
        'state': survey.state,
        'survey_image': survey_image,
        'landowners': [api_serialize_landowner(lo) for lo in survey.landowner_ids],
        'landowner_ids': survey.landowner_ids.ids,
        'house_owners': [api_serialize_house_owner(ho) for ho in survey.house_owner_ids],
        'house_owner_ids': survey.house_owner_ids.ids,
    }
