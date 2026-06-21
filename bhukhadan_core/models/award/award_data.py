# -*- coding: utf-8 -*-

import re

from odoo import models


class Section23AwardData(models.Model):
    _inherit = 'bhu.section23.award'

    def _land_owner_block_from_record(self, landowner):
        return {
            'id': landowner.id,
            'name': (landowner.name or '').strip(),
            'father_name': (landowner.father_name or '').strip(),
            'spouse_name': (landowner.spouse_name or '').strip(),
            'address': (landowner.owner_address or '').strip(),
        }

    def _land_owner_display_from_blocks(self, owner_blocks):
        lines = []
        for idx, block in enumerate(owner_blocks or [], start=1):
            name = (block.get('name') or '').strip()
            if not name:
                continue
            line = f'{idx}. {name}'
            father = (block.get('father_name') or '').strip()
            spouse = (block.get('spouse_name') or '').strip()
            if father:
                line += f' पिता {father}'
            elif spouse:
                line += f' पति {spouse}'
            addr = (block.get('address') or '').strip()
            if addr:
                line += f' निवासी: {addr}'
            lines.append(line)
        return '\n'.join(lines)

    def _land_row_owner_names(self, row):
        """All landowner names on one khasra row (for preview, Excel, grouping)."""
        names = []
        for block in row.get('owner_blocks') or []:
            name = (block.get('name') or '').strip()
            if name and name not in names:
                names.append(name)
        if not names:
            display = (row.get('landowner_display') or '').strip()
            if display:
                for line in display.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    match = re.match(r'^\d+\.\s*(.+)$', line)
                    rest = (match.group(1) if match else line)
                    for sep in (' निवासी:', ' पिता ', ' पति '):
                        if sep in rest:
                            rest = rest.split(sep, 1)[0]
                    name = rest.strip()
                    if name and name not in names:
                        names.append(name)
        if not names:
            raw = (row.get('landowner_name') or '').strip()
            if raw:
                for part in [p.strip() for p in raw.split(',') if p.strip()]:
                    if part not in names:
                        names.append(part)
        return names

    def _land_merge_owner_blocks(self, bucket, landowners):
        blocks = bucket.setdefault('owner_blocks', [])
        seen = {b.get('id') for b in blocks if b.get('id')}
        for landowner in landowners:
            if landowner.id in seen:
                continue
            seen.add(landowner.id)
            blocks.append(self._land_owner_block_from_record(landowner))
        if landowners and not bucket.get('landowner'):
            bucket['landowner'] = landowners[0]

    def get_land_compensation_data(self):
        """Land compensation — one row per khasra; all owners listed together."""
        self.ensure_one()
        acre_per_hectare = 2.471

        # Get approved surveys for this village and project
        surveys = self.env['bhu.survey'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ['draft', 'submitted', 'approved', 'locked']),
            ('khasra_number', '!=', False),
        ])

        if not surveys:
            return []

        # One bucket per khasra; acquired area counted once per survey (not per owner).
        compensation_data = {}

        for survey in surveys:
            khasra = (survey.khasra_number or '').strip()
            if not khasra:
                continue
            acquired_area = survey.acquired_area or 0.0
            total_area = survey.total_area or acquired_area or 0.0

            irrigation_type = survey.irrigation_type or 'unirrigated'
            is_irrigated = irrigation_type == 'irrigated'
            is_unirrigated = irrigation_type in ('unirrigated', 'fallow')
            is_fallow = self._is_fallow_survey(survey)
            is_diverted = survey.has_traded_land == 'yes'

            landowners = survey.landowner_ids if survey.landowner_ids else []

            key = ('khasra', khasra)
            if key not in compensation_data:
                compensation_data[key] = {
                    'landowner': None,
                    'landowner_name': '',
                    'landowner_display': '',
                    'owner_blocks': [],
                    'father_name': '',
                    'spouse_name': '',
                    'address': '',
                    'khasra': khasra,
                    'original_area': 0.0,
                    'acquired_area': 0.0,
                    'lagan': khasra,
                    'fallow': is_fallow,
                    'unirrigated': is_unirrigated,
                    'irrigated': is_irrigated,
                    'is_diverted': is_diverted,
                    'guide_line_rate': 0.0,
                    'market_value': 0.0,
                    'solatium': 0.0,
                    'interest': 0.0,
                    'total_compensation': 0.0,
                    'rehab_policy_per_acre_1': 0.0,
                    'rehab_policy_per_acre_2': 0.0,
                    'rehab_policy_amount': 0.0,
                    'dev_compensation': 0.0,
                    '_seen_survey_ids': set(),
                }
            bucket = compensation_data[key]
            if landowners:
                self._land_merge_owner_blocks(bucket, landowners)
            if survey.id not in bucket['_seen_survey_ids']:
                bucket['_seen_survey_ids'].add(survey.id)
                bucket['original_area'] += total_area
                bucket['acquired_area'] += acquired_area

        # Convert to list and calculate totals
        result = []
        # Convert to list and calculate totals matching the 19 columns
        result = []
        for _key, data in compensation_data.items():
            data.pop('_seen_survey_ids', None)
            blocks = data.get('owner_blocks') or []
            if blocks:
                data['landowner_display'] = self._land_owner_display_from_blocks(blocks)
                owner_names = self._land_row_owner_names(data)
                data['landowner_name'] = ', '.join(owner_names) if owner_names else (blocks[0].get('name') or '')
                data['father_name'] = blocks[0].get('father_name') or ''
                data['spouse_name'] = blocks[0].get('spouse_name') or ''
                data['address'] = blocks[0].get('address') or ''
            else:
                data['landowner_display'] = data.get('landowner_name') or ''

            # Get survey to access proper rates if possible
            survey = self.env['bhu.survey'].search([
                ('project_id', '=', self.project_id.id),
                ('village_id', '=', self.village_id.id),
                ('khasra_number', '=', data['khasra'])
            ], limit=1)

            # Derive main-road status from measured distance.
            # Rule: rural <= 50m is MR, urban <= 20m is MR; 0/blank counts as MR.
            distance_from_main_road = (survey.distance_from_main_road or 0.0) if survey else 0.0
            threshold = self._s23_distance_threshold()
            derived_is_within_distance = distance_from_main_road <= threshold

            # Effective guideline rate:
            # - MR lane: ×1.0
            # - BMR + diverted + irrigated: ×1.25
            # - BMR + diverted + unirrigated: ×1.0
            # - BMR + not-diverted + irrigated: ×1.0
            # - BMR + not-diverted + unirrigated: ×0.8
            award_line = self.award_survey_line_ids.filtered(lambda l: l.survey_id.id == survey.id)
            has_award_line = bool(award_line)
            is_diverted = survey.has_traded_land == 'yes' if survey else False

            al_rec = award_line[:1] if has_award_line else self.env['bhu.section23.award.survey.line']
            base_rate_ha = self._s23_land_base_rate_per_hectare(survey, al_rec, derived_is_within_distance)
            # Same MR/BMR lane as rate master / optional manual override on award survey line.
            within_lane = bool(al_rec.is_within_distance) if has_award_line else bool(derived_is_within_distance)
            is_within_distance = within_lane

            # Irrigation for BMR factor + Excel must come from the survey, not the grouped dict
            # (e.g. surveys without landowners used to leave irrigated/unirrigated both False).
            if survey:
                _itype = survey.irrigation_type or 'unirrigated'
                is_irrigated_rate = _itype == 'irrigated'
                is_unirrigated_disp = _itype in ('unirrigated', 'fallow')
            else:
                is_irrigated_rate = bool(data.get('irrigated'))
                is_unirrigated_disp = bool(data.get('unirrigated'))

            _bmr_mult = self._s23_bmr_rate_multiplier(
                within_lane, is_diverted, is_irrigated_rate,
            )

            if has_award_line:
                guide_master = award_line[0].guide_line_master_rate or base_rate_ha
            else:
                guide_master = base_rate_ha or 0.0
            # Always derive effective rate from master × survey-based factors (matches report columns).
            effective_rate = guide_master * _bmr_mult

            if survey and survey.irrigation_type == 'irrigated':
                irrigation_label = 'Irrigated / सिंचित'
            else:
                irrigation_label = 'Unirrigated / असिंचित'
            village_name = (self.village_id.name or '') if self.village_id else ''
            road_lbl = 'MR' if is_within_distance else 'BMR'
            diverted_lbl = 'Yes' if is_diverted else 'No'

            # Shared meta fields written into every row regardless of rural/urban path
            data.update({
                'original_area': survey.total_area if survey else 0.0,
                'lagan': survey.lagan if (survey and hasattr(survey, 'lagan')) else data['khasra'],
                'is_within_distance': is_within_distance,
                'distance_from_main_road': distance_from_main_road,
                'irrigated': is_irrigated_rate,
                'unirrigated': is_unirrigated_disp,
                'is_diverted': is_diverted,
                'village_name': village_name,
                'base_rate_hectare': base_rate_ha,
                'effective_rate_hectare': effective_rate,
                'road_type_label': road_lbl,
                'irrigation_label': irrigation_label,
                'diverted_label': diverted_lbl,
                'survey_id': survey.id if survey else False,
                'guide_line_rate': effective_rate,
                'guide_line_rate_unit': 'ha',
                'is_urban_slab': False,
                'slab_label': '',
                'slab_pct': 1.0,
            })

            # --- Urban area-based slab path ---
            # Trigger urban slab path from the award's effective village type
            # (award override first, then village master fallback).
            _effective_vtype = (
                self.village_type
                or (self.village_id.village_type if self.village_id else 'rural')
                or 'rural'
            )
            _is_urban_village = str(_effective_vtype).lower() == 'urban'
            _body_type = (
                self.urban_body_type
                or (self.village_id.urban_body_type if self.village_id else False)
            ) if _is_urban_village else False
            if _body_type and _is_urban_village:
                slab_rows = self._generate_urban_slab_rows(
                    data, is_within_distance, guide_master, effective_rate, acre_per_hectare,
                    body_type=_body_type,
                )
                result.extend(slab_rows)
                continue

            # --- Rural (flat rate) path ---
            # Logic matching 19-column image:
            # 12: basic_value = master effective rate × area
            # 13: market_value = basic_value × gunak (rural 2, urban 1)
            # 14: solatium = market_value * 1.0
            # 15: interest = 1% per month on basic value from section 4 hearing to award date

            market_value_basic = data['acquired_area'] * effective_rate
            market_value_factored = market_value_basic * self._s23_market_value_factor()
            solatium = market_value_factored * 1.0  # 100%

            interest, _days = self._calculate_interest_on_basic(market_value_basic)

            total_compensation = market_value_factored + solatium + interest
            acquired_area_acre = data['acquired_area'] * acre_per_hectare
            rehab_rate_per_acre = self._get_min_rehab_rate_per_acre(
                data.get('fallow'),
                data.get('irrigated'),
                data.get('unirrigated'),
            )
            rehab_policy_amount = acquired_area_acre * rehab_rate_per_acre
            # Col 18 is payable amount: compare Col 16 and Col 17, take higher.
            payable_compensation = max(total_compensation, rehab_policy_amount)

            data.update({
                'basic_value': market_value_basic,
                'market_value': market_value_factored,
                'solatium': solatium,
                'interest': interest,
                'total_compensation': total_compensation,
                'rehab_policy_rate_per_acre': rehab_rate_per_acre,
                'rehab_policy_amount': rehab_policy_amount,
                'paid_compensation': payable_compensation,
                'remark': '',
            })

            result.append(data)

        # Sort by landowner name, then khasra
        result.sort(key=lambda x: (x['landowner_name'] or '', x['khasra'] or ''))

        return result

    # ── Urban area-based slab helper ──────────────────────────────────────────

    def _generate_urban_slab_rows(self, base_data, is_within_distance,
                                  guide_line_ha, effective_rate_ha, acre_per_hectare,
                                  body_type=None):
        """Urban: split one khasra into multiple rows by acquired-area slabs (Nagar Nigam/Palika/Panchayat).

        Plot ₹/sqm from the rate master (MR/BMR lane), then BMR factors via
        ``_s23_bmr_rate_multiplier``. Each slab applies its % to that effective ₹/sqm.
        Area above the last slab uses ``effective_rate_ha`` (₹/ha, already BMR-adjusted).
        """
        self.ensure_one()
        body_type = (
            body_type
            or self.urban_body_type
            or (self.village_id.urban_body_type if self.village_id else False)
            or 'nagar_nigam'
        )
        body_labels = {
            'nagar_nigam': 'Nagar Nigam',
            'nagar_palika': 'Nagar Palika',
            'nagar_panchayat': 'Nagar Panchayat',
        }
        _bt = body_labels.get(body_type, body_type or '')

        if body_type == 'nagar_nigam':
            slabs = [
                (0.050, 1.00, 'Slab 1 (≤0.050 ha)', '100%'),
                (0.100, 0.80, 'Slab 2 (0.050–0.100 ha)', '80%'),
                (0.202, 0.50, 'Slab 3 (0.100–0.202 ha)', '50%'),
            ]
            no_slab_threshold = 0.202
        elif body_type == 'nagar_palika':
            slabs = [
                (0.050, 1.00, 'Slab 1 (≤0.050 ha)', '100%'),
                (0.100, 0.80, 'Slab 2 (0.050–0.100 ha)', '80%'),
                (0.150, 0.50, 'Slab 3 (0.100–0.150 ha)', '50%'),
            ]
            no_slab_threshold = 0.150
        else:  # nagar_panchayat
            slabs = [
                (0.050, 1.00, 'Slab 1 (≤0.050 ha)', '100%'),
                (0.100, 0.25, 'Slab 2 (0.050–0.100 ha)', '25%'),
            ]
            no_slab_threshold = 0.100

        rm = self.env['bhu.rate.master'].search([
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ['active', 'draft']),
        ], limit=1, order='state ASC, effective_from DESC')

        if is_within_distance:
            sqm_raw = float(self.rate_master_main_road_sqm or 0.0)
            if sqm_raw <= 0.0:
                sqm_raw = (rm.main_road_rate_sqm or 0.0) if rm else 0.0
        else:
            sqm_raw = float(self.rate_master_other_road_sqm or 0.0)
            if sqm_raw <= 0.0:
                sqm_raw = (rm.other_road_rate_sqm or 0.0) if rm else 0.0

        _urban_mult = self._s23_bmr_rate_multiplier(
            bool(is_within_distance),
            bool(base_data.get('is_diverted')),
            bool(base_data.get('irrigated')),
        )
        sqm_plot = sqm_raw * _urban_mult

        total_area_ha = base_data['acquired_area']
        rows = []

        # Policy rule: when acquired area crosses body threshold, no slab split applies.
        # Entire acquired area is evaluated on hectare rate.
        _mv_factor = self._s23_market_value_factor()
        if total_area_ha > no_slab_threshold:
            basic_value = total_area_ha * effective_rate_ha
            market_value = basic_value * _mv_factor
            solatium = market_value * 1.0
            interest, _ = self._calculate_interest_on_basic(basic_value)
            total_comp = market_value + solatium + interest

            acquired_acre = total_area_ha * acre_per_hectare
            rehab_rate = self._get_min_rehab_rate_per_acre(
                base_data.get('fallow'), base_data.get('irrigated'), base_data.get('unirrigated')
            )
            rehab_amt = acquired_acre * rehab_rate
            paid = max(total_comp, rehab_amt)

            row = dict(base_data)
            row.update({
                'acquired_area': total_area_ha,
                'guide_line_rate': effective_rate_ha,
                'guide_line_rate_unit': 'ha',
                'base_rate_hectare': effective_rate_ha,
                'basic_value': basic_value,
                'market_value': market_value,
                'solatium': solatium,
                'interest': interest,
                'total_compensation': total_comp,
                'rehab_policy_rate_per_acre': rehab_rate,
                'rehab_policy_amount': rehab_amt,
                'paid_compensation': paid,
                'remark': '',
                'slab_label': f'No slab (>{no_slab_threshold} ha; full area at ₹/ha) / {_bt}',
                'slab_pct': 1.0,
                'is_urban_slab': True,
                'effective_rate_hectare': effective_rate_ha,
            })
            rows.append(row)
            return rows

        prev_limit = 0.0

        for slab_limit, pct, label, pct_label in slabs:
            if total_area_ha <= prev_limit:
                break
            portion_ha = min(total_area_ha, slab_limit) - prev_limit
            if portion_ha <= 0:
                prev_limit = slab_limit
                continue

            portion_sqm = portion_ha * 10000.0
            basic_value = portion_sqm * sqm_plot * pct
            market_value = basic_value * _mv_factor
            solatium = market_value * 1.0
            interest, _ = self._calculate_interest_on_basic(basic_value)
            total_comp = market_value + solatium + interest

            acquired_acre = portion_ha * acre_per_hectare
            rehab_rate = self._get_min_rehab_rate_per_acre(
                base_data.get('fallow'), base_data.get('irrigated'), base_data.get('unirrigated')
            )
            rehab_amt = acquired_acre * rehab_rate
            # Col 18 is payable amount: compare Col 16 and Col 17, take higher.
            paid = max(total_comp, rehab_amt)

            effective_sqm_rate = sqm_plot * pct
            row = dict(base_data)
            row.update({
                'acquired_area': portion_ha,
                'guide_line_rate': effective_sqm_rate,
                'guide_line_rate_unit': 'sqm',
                'base_rate_hectare': sqm_plot,
                'basic_value': basic_value,
                'market_value': market_value,
                'solatium': solatium,
                'interest': interest,
                'total_compensation': total_comp,
                'rehab_policy_rate_per_acre': rehab_rate,
                'rehab_policy_amount': rehab_amt,
                'paid_compensation': paid,
                'remark': '',
                'slab_label': f'{label} / {_bt}',
                'slab_pct': pct,
                'is_urban_slab': True,
                'effective_rate_hectare': effective_sqm_rate * 10000.0,
            })
            rows.append(row)

            prev_limit = slab_limit
            if total_area_ha <= slab_limit:
                break

        return rows

    def get_land_compensation_grouped_data(self):
        """Group land rows by khasra — all owners on one sheet block per khasra."""
        self.ensure_one()
        land_data = self.get_land_compensation_data()
        grouped = {}
        ordered_keys = []

        def _khasra_sort_key(line):
            khasra = (line.get('khasra') or '').strip()
            if not khasra:
                return (1, 10**12, 10**12, '')
            parts = khasra.split('/', 1)
            main = int(parts[0]) if parts[0].isdigit() else 10**12
            sub = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10**12
            return (0, main, sub, khasra)

        def _khasra_group_sort_key(item):
            _key, grp = item
            lines = grp.get('lines') or []
            return _khasra_sort_key(lines[0] if lines else {})

        area_totals = ('original_area', 'acquired_area')
        amount_totals = (
            'basic_value', 'market_value', 'solatium', 'interest',
            'total_compensation', 'rehab_policy_amount', 'paid_compensation',
        )
        for row in land_data:
            khasra = (row.get('khasra') or '').strip()
            key = ('khasra', khasra) if khasra else ('row', id(row))
            if key not in grouped:
                grouped[key] = {
                    'landowner': row.get('landowner'),
                    'landowner_name': row.get('landowner_name', ''),
                    'landowner_display': row.get('landowner_display', ''),
                    'owner_blocks': list(row.get('owner_blocks') or []),
                    'father_name': row.get('father_name', ''),
                    'spouse_name': row.get('spouse_name', ''),
                    'address': row.get('address', ''),
                    'lines': [],
                    'khasra_count': 0,
                    '_seen_khasra_for_totals': set(),
                }
                for field_name in area_totals + amount_totals:
                    grouped[key][field_name] = 0.0
                ordered_keys.append(key)
            group = grouped[key]
            if not group.get('landowner') and row.get('landowner'):
                group['landowner'] = row.get('landowner')
            if row.get('owner_blocks'):
                seen = {b.get('id') for b in group.get('owner_blocks') or [] if b.get('id')}
                for block in row.get('owner_blocks') or []:
                    bid = block.get('id')
                    if bid and bid in seen:
                        continue
                    if bid:
                        seen.add(bid)
                    group.setdefault('owner_blocks', []).append(block)
                group['landowner_display'] = self._land_owner_display_from_blocks(
                    group.get('owner_blocks') or []
                )
            group['lines'].append(row)
            khasra = (row.get('khasra') or '').strip()
            area_present = bool((row.get('original_area', 0.0) or 0.0) or (row.get('acquired_area', 0.0) or 0.0))
            if khasra and area_present:
                # For urban slab-split rows, count khasra only once.
                if khasra not in group['_seen_khasra_for_totals']:
                    group['_seen_khasra_for_totals'].add(khasra)
                    group['khasra_count'] += 1
                    group['original_area'] += row.get('original_area', 0.0) or 0.0
                # Acquired area is portion-wise and should sum across slab rows.
                group['acquired_area'] += row.get('acquired_area', 0.0) or 0.0
            for field_name in amount_totals:
                group[field_name] += row.get(field_name, 0.0) or 0.0

        result = []
        for key, group in sorted(
            ((k, grouped[k]) for k in ordered_keys),
            key=_khasra_group_sort_key,
        ):
            lines = sorted(group.get('lines', []), key=_khasra_sort_key)
            if not group.get('landowner_display'):
                group['landowner_display'] = self._land_owner_display_from_blocks(
                    group.get('owner_blocks') or []
                ) or group.get('landowner_name', '')
            owner_names = self._land_row_owner_names(group)
            if owner_names:
                group['landowner_name'] = ', '.join(owner_names)
            # Add merge metadata for urban slab rows so repeating khasra cells
            # render once with rowspan in report columns 3,4,7,8,9,10.
            i = 0
            while i < len(lines):
                row = lines[i]
                row['khasra_merge_show'] = True
                row['khasra_merge_rowspan'] = 1
                khasra = (row.get('khasra') or '').strip()
                if row.get('is_urban_slab') and khasra:
                    j = i + 1
                    while (
                        j < len(lines)
                        and lines[j].get('is_urban_slab')
                        and (lines[j].get('khasra') or '').strip() == khasra
                    ):
                        j += 1
                    span = j - i
                    if span > 1:
                        row['khasra_merge_rowspan'] = span
                        for k in range(i + 1, j):
                            lines[k]['khasra_merge_show'] = False
                            lines[k]['khasra_merge_rowspan'] = span
                    span_rehab = sum(
                        float(lines[k].get('rehab_policy_amount', 0.0) or 0.0)
                        for k in range(i, j)
                    )
                    row['rehab_policy_amount_display'] = span_rehab
                    i = j
                    continue
                row['rehab_policy_amount_display'] = float(
                    row.get('rehab_policy_amount', 0.0) or 0.0
                )
                i += 1
            group['lines'] = lines
            group.pop('_seen_khasra_for_totals', None)
            result.append(group)
        return result

    def _s23_calculate_group_rehab_total(self, lines):
        """Recompute group rehab total from acquired area and rehab rate."""
        self.ensure_one()
        acre_per_hectare = 2.471053814671653
        total = 0.0
        for line in (lines or []):
            acquired_area_ha = float(line.get('acquired_area', 0.0) or 0.0)
            if acquired_area_ha <= 0.0:
                continue
            rehab_rate = float(line.get('rehab_policy_rate_per_acre', 0.0) or 0.0)
            if rehab_rate <= 0.0:
                rehab_rate = self._get_min_rehab_rate_per_acre(
                    bool(line.get('fallow')),
                    bool(line.get('irrigated')),
                    bool(line.get('unirrigated')),
                )
            total += acquired_area_ha * acre_per_hectare * rehab_rate
        return total

    def format_indian_number(self, value, decimals=2):
        """Format number with Indian numbering system (commas for thousands)"""
        if value is None:
            value = 0.0

        # Format the number with commas (Indian numbering system)
        if decimals == 2:
            formatted = f"{value:,.2f}"
        elif decimals == 4:
            formatted = f"{value:,.4f}"
        else:
            formatted = f"{value:,.{decimals}f}"

        return formatted

    def format_land_sheet_col6_acquired_area(self, land_line_dict):
        """Column 6: acquired area — urban slab rows show हे. / व.मी. (sqm = ha × 10000)."""
        ha = float((land_line_dict or {}).get('acquired_area', 0.0) or 0.0)
        if (land_line_dict or {}).get('is_urban_slab'):
            sqm = ha * 10000.0
            return '%s / %s' % (
                self.format_indian_number(ha, 4),
                self.format_indian_number(sqm, 2),
            )
        return self.format_indian_number(ha, 4)

    def format_land_sheet_col6_acquired_area_group(self, group):
        """कुल row col 6: dual units if any urban slab line in the group."""
        ha = float((group or {}).get('acquired_area', 0.0) or 0.0)
        lines = (group or {}).get('lines') or []
        if any(l.get('is_urban_slab') for l in lines):
            sqm = ha * 10000.0
            return '%s / %s' % (
                self.format_indian_number(ha, 4),
                self.format_indian_number(sqm, 2),
            )
        return self.format_indian_number(ha, 4)

    def format_land_sheet_col6_acquired_area_mahayog(self, land_groups, total_ha):
        """Grand total col 6: dual units if any urban slab exists in the sheet."""
        ha = float(total_ha or 0.0)
        for g in land_groups or []:
            if any(l.get('is_urban_slab') for l in (g.get('lines') or [])):
                sqm = ha * 10000.0
                return '%s / %s' % (
                    self.format_indian_number(ha, 4),
                    self.format_indian_number(sqm, 2),
                )
        return self.format_indian_number(ha, 4)

    def get_tree_compensation_data(self):
        """Tree compensation — one row per khasra + tree type; all owners listed together."""
        self.ensure_one()

        # Get approved surveys with trees for this village and project
        surveys = self.env['bhu.survey'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ['draft', 'submitted', 'approved', 'locked']),
            ('khasra_number', '!=', False),
        ])

        if not surveys:
            return []

        # Get all tree lines from surveys
        tree_data = {}

        def _tree_label(tree_line):
            base = tree_line.tree_master_id.name if tree_line.tree_master_id else 'Other / अन्य'
            if getattr(tree_line, 'is_other_tree', False) and (getattr(tree_line, 'tree_description', '') or '').strip():
                return '%s - %s' % (base, tree_line.tree_description.strip())
            return base

        for survey in surveys:
            khasra = (survey.khasra_number or '').strip()
            if not khasra:
                continue
            landowners = survey.landowner_ids if survey.landowner_ids else []
            tree_lines = survey.tree_line_ids if hasattr(survey, 'tree_line_ids') else []
            if not tree_lines:
                continue

            _la = (survey.acquired_area or 0.0) or (survey.total_area or 0.0)
            for tree_line in tree_lines:
                tree_type_name = _tree_label(tree_line)
                key = ('khasra', khasra, tree_type_name)
                if key not in tree_data:
                    tree_data[key] = {
                        'landowner': None,
                        'landowner_name': '',
                        'landowner_display': '',
                        'owner_blocks': [],
                        'father_name': '',
                        'spouse_name': '',
                        'khasra': khasra,
                        'total_khasra': khasra,
                        'total_area': _la,
                        'land_khasra': khasra,
                        'land_area_ha': _la,
                        'tree_khasra': khasra,
                        'mulya': 0.0,
                        'kul_rashi': 0.0,
                        'tree_type': tree_type_name,
                        'tree_type_code': getattr(tree_line, 'tree_type', '') or 'other',
                        'tree_count': 0,
                        'girth_cm': 0.0,
                        'unit_rate': 0.0,
                        'rate': 0.0,
                        'development_stage': '',
                        'condition': '',
                        'value': 0.0,
                        'determined_value': 0.0,
                        'solatium': 0.0,
                        'interest': 0.0,
                        'total': 0.0,
                        'remark': '',
                    }
                bucket = tree_data[key]
                if landowners:
                    self._land_merge_owner_blocks(bucket, landowners)
                rate_per_tree = (
                    tree_line.get_applicable_rate()
                    if hasattr(tree_line, 'get_applicable_rate')
                    else 0.0
                )
                qty = getattr(tree_line, 'quantity', 0) or 0
                bucket['tree_count'] += qty
                bucket['girth_cm'] = getattr(tree_line, 'girth_cm', 0.0) or 0.0
                bucket['rate'] = rate_per_tree
                bucket['unit_rate'] = rate_per_tree
                bucket['development_stage'] = getattr(tree_line, 'development_stage', '') or ''
                bucket['condition'] = getattr(tree_line, 'condition', '') or ''
                bucket['value'] += qty * rate_per_tree

        # Calculate compensation amounts
        result = []
        for _key, data in tree_data.items():
            blocks = data.get('owner_blocks') or []
            if blocks:
                data['landowner_display'] = self._land_owner_display_from_blocks(blocks)
                owner_names = self._land_row_owner_names(data)
                data['landowner_name'] = ', '.join(owner_names) if owner_names else (blocks[0].get('name') or '')
                data['father_name'] = blocks[0].get('father_name') or ''
                data['spouse_name'] = blocks[0].get('spouse_name') or ''
            else:
                data['landowner_display'] = data.get('landowner_name') or ''
            determined_value = data['value']
            data['mulya'] = determined_value
            data['kul_rashi'] = determined_value
            data['land_khasra'] = data.get('land_khasra') or data.get('khasra') or ''
            data['tree_khasra'] = data.get('tree_khasra') or data.get('khasra') or ''
            data['land_area_ha'] = data.get('land_area_ha', 0.0) or 0.0
            solatium = determined_value * 1.0  # 100% solatium
            interest, _days = self._calculate_interest_on_basic(determined_value)
            total = determined_value + solatium + interest

            data['determined_value'] = determined_value
            data['solatium'] = solatium
            data['interest'] = interest
            data['total'] = total
            result.append(data)

        result.sort(key=lambda x: (x['khasra'] or '', x.get('tree_type', '') or ''))

        return result

    def get_structure_compensation_data(self):
        """Get structure compensation data from shared award structure entries."""
        self.ensure_one()
        surveys = self.env['bhu.survey'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ['draft', 'submitted', 'approved', 'locked']),
            ('khasra_number', '!=', False),
        ])
        if not surveys:
            return []

        structure_lines = self.env['bhu.award.structure.details'].search([
            ('survey_id', 'in', surveys.ids),
        ])
        if not structure_lines:
            return []

        structure_data = []
        for line in structure_lines:
            survey = line.survey_id
            total_value = line.line_total or 0.0
            base_row = {
                'total_khasra': survey.khasra_number or '',
                'total_area': survey.total_area or 0.0,
                'asset_khasra': survey.khasra_number or '',
                'asset_land_area': survey.acquired_area or 0.0,
                'asset_type': line.get_structure_type_label(),
                'structure_type': line.structure_type or '',
                'construction_type': line.construction_type or '',
                'asset_code': 4,
                'asset_dimension': (
                    (line.asset_count or 0.0)
                    if line.structure_type == 'well'
                    else ((line.area_sqm or 0.0) * (line.asset_count or 0.0))
                ),
                'rate_per_sqm': line.market_rate_per_sqm or 0.0,
                'remark': line.description or '',
            }
            owners = survey.landowner_ids
            # Use first owner for display (consistent with land/tree)
            first_owner = owners[0] if owners else None
            owner_names = ', '.join([o.name for o in owners if o.name]) if owners else ''
            total_interest, _days = self._calculate_interest_on_basic(total_value)
            structure_data.append({
                **base_row,
                'landowner_name': owner_names,
                'father_name': first_owner.father_name if first_owner else '',
                'spouse_name': first_owner.spouse_name if first_owner else '',
                'address': first_owner.owner_address if first_owner else '',
                'market_value': total_value,
                'solatium': total_value,
                'interest': total_interest,
                'total': total_value + total_value + total_interest,
            })
        return structure_data

    def get_tree_compensation_grouped_data(self):
        """Group tree rows by khasra (all owners + tree types under one block)."""
        self.ensure_one()
        tree_data = self.get_tree_compensation_data()
        grouped = {}
        ordered_keys = []

        def _khasra_sort_key(khasra):
            text = (khasra or '').strip()
            if not text:
                return (1, 10**12, 10**12, '')
            parts = text.split('/', 1)
            main = int(parts[0]) if parts[0].isdigit() else 10**12
            sub = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10**12
            return (0, main, sub, text)

        numeric_totals = (
            'land_area_ha', 'tree_count', 'value', 'mulya', 'kul_rashi',
            'solatium', 'interest', 'total',
        )
        for row in tree_data:
            khasra = (row.get('tree_khasra') or row.get('khasra') or '').strip()
            key = ('khasra', khasra) if khasra else ('row', id(row))
            if key not in grouped:
                grouped[key] = {
                    'landowner': row.get('landowner'),
                    'landowner_name': row.get('landowner_name', ''),
                    'landowner_display': row.get('landowner_display', ''),
                    'owner_blocks': list(row.get('owner_blocks') or []),
                    'father_name': row.get('father_name', ''),
                    'spouse_name': row.get('spouse_name', ''),
                    'address': row.get('address', ''),
                    'lines': [],
                    'khasra_count': 0,
                    'khasra_seen': set(),
                }
                for field_name in numeric_totals:
                    grouped[key][field_name] = 0.0
                ordered_keys.append(key)
            group = grouped[key]
            if not group.get('landowner') and row.get('landowner'):
                group['landowner'] = row.get('landowner')
            if row.get('owner_blocks'):
                seen = {b.get('id') for b in group.get('owner_blocks') or [] if b.get('id')}
                for block in row.get('owner_blocks') or []:
                    bid = block.get('id')
                    if bid and bid in seen:
                        continue
                    if bid:
                        seen.add(bid)
                    group.setdefault('owner_blocks', []).append(block)
                group['landowner_display'] = self._land_owner_display_from_blocks(
                    group.get('owner_blocks') or []
                )
            group['lines'].append(row)
            khasra = row.get('tree_khasra') or row.get('khasra') or ''
            if khasra and khasra not in group['khasra_seen']:
                group['khasra_seen'].add(khasra)
                group['khasra_count'] += 1
            for field_name in numeric_totals:
                group[field_name] += row.get(field_name, 0.0) or 0.0

        result = []
        for key in sorted(ordered_keys, key=lambda k: _khasra_sort_key(k[1] if k[0] == 'khasra' else '')):
            group = grouped[key]
            if not group.get('landowner_display'):
                group['landowner_display'] = self._land_owner_display_from_blocks(
                    group.get('owner_blocks') or []
                ) or group.get('landowner_name', '')
            group.pop('khasra_seen', None)
            result.append(group)
        return result

    def get_structure_compensation_grouped_data(self):
        """Group structure rows by khasra for report rowspans/subtotals."""
        self.ensure_one()
        structure_data = self.get_structure_compensation_data()
        grouped = {}
        ordered_keys = []
        numeric_totals = ('total_area', 'asset_land_area', 'asset_dimension', 'market_value', 'solatium', 'interest', 'total')
        for row in structure_data:
            # Merge all landowners of the same khasra into one group cell.
            key = ('khasra', row.get('asset_khasra') or row.get('total_khasra') or '')
            if key not in grouped:
                grouped[key] = {
                    'landowner_name': '',
                    'father_name': '',
                    'lines': [],
                    'khasra_count': 0,
                    'khasra_seen': set(),
                    'owner_names': [],
                    'owner_seen': set(),
                }
                for field_name in numeric_totals:
                    grouped[key][field_name] = 0.0
                ordered_keys.append(key)
            group = grouped[key]
            owner_name = (row.get('landowner_name') or '').strip()
            if owner_name and owner_name not in group['owner_seen']:
                group['owner_seen'].add(owner_name)
                group['owner_names'].append(owner_name)
            group['lines'].append(row)
            khasra = row.get('asset_khasra') or row.get('total_khasra') or ''
            if khasra and khasra not in group['khasra_seen']:
                group['khasra_seen'].add(khasra)
                group['khasra_count'] += 1
            for field_name in numeric_totals:
                group[field_name] += row.get(field_name, 0.0) or 0.0

        result = []
        for key in ordered_keys:
            group = grouped[key]
            names = group.get('owner_names') or []
            group['landowner_display'] = '\n'.join(
                f'{idx}. {name}' for idx, name in enumerate(names, start=1) if name
            )
            group['landowner_name'] = ', '.join(names)
            group.pop('owner_names', None)
            group.pop('owner_seen', None)
            group.pop('khasra_seen', None)
            result.append(group)
        return result
