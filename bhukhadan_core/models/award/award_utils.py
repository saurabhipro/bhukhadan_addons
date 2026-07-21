# -*- coding: utf-8 -*-

import re

from markupsafe import escape

from odoo import models, api, fields, _

from .award_header_constants import get_award_header_constants


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def _get_active_rate_master_for_village(self):
        self.ensure_one()
        if not self.village_id:
            return False
        return self.env['bhu.rate.master'].search([
            ('village_id', '=', self.village_id.id),
            ('state', 'in', ['active', 'draft']),
        ], limit=1, order='state ASC, effective_from DESC')

    def _s23_distance_threshold(self):
        """MR/BMR threshold in meters from effective village type."""
        self.ensure_one()
        vtype = self.village_type or (self.village_id.village_type if self.village_id else 'rural')
        return 20.0 if vtype == 'urban' else 50.0

    def _html_s23_num(self, value, decimals=2):
        return escape(self.format_indian_number(float(value or 0.0), decimals))

    def _s23_cache_attachment_name(self, export_scope='all', variant='standard', file_format='pdf'):
        self.ensure_one()
        scope = (export_scope or 'all').lower()
        var = (variant or 'standard').lower()
        fmt = 'pdf' if (file_format or 'pdf').lower() == 'pdf' else 'excel'
        return f"s23_cache::{var}::{scope}::{fmt}"

    def _s23_filename_token(self, value, fallback):
        raw = (value or '').strip()
        if not raw:
            return fallback
        token = re.sub(r'\s+', ' ', raw).strip()
        # Keep Hindi/Unicode text readable; only remove filesystem-unsafe chars.
        token = (token
                 .replace('/', '-')
                 .replace('\\', '-')
                 .replace(':', '-')
                 .replace('*', '')
                 .replace('?', '')
                 .replace('"', '')
                 .replace('<', '')
                 .replace('>', '')
                 .replace('|', ''))
        token = token.replace(' ', '_')
        return token or fallback

    def _s23_location_type_suffix(self):
        """Return location type token with readable urban-body name."""
        self.ensure_one()
        village_type = (self.village_type or (self.village_id.village_type if self.village_id else '') or 'rural').lower()
        if village_type != 'urban':
            return 'R_Rural'
        body_type = (self.urban_body_type or (self.village_id.urban_body_type if self.village_id else '') or '').lower()
        body_map = {
            'nagar_nigam': 'Nagar_Nigam',
            'nagar_palika': 'Nagar_Palika',
            'nagar_panchayat': 'Nagar_Panchayat',
        }
        body_code = body_map.get(body_type, 'Urban')
        return f"U_{body_code}"

    def get_urban_body_label(self):
        """Return urban body label only when award location is urban."""
        self.ensure_one()
        village_type = (self.village_type or (self.village_id.village_type if self.village_id else '') or 'rural').lower()
        if village_type != 'urban':
            return ''
        body_type = (self.urban_body_type or (self.village_id.urban_body_type if self.village_id else '') or '').lower()
        if not body_type:
            return ''
        body_map = {
            'nagar_nigam': 'Nagar Nigam / नगर निगम',
            'nagar_palika': 'Nagar Palika / नगर पालिका',
            'nagar_panchayat': 'Nagar Panchayat / नगर पंचायत',
        }
        return body_map.get(body_type, body_type)

    def _requires_section4_for_award_generate(self):
        """LARR-only: Section 4 must be in the project's law.

        Mirrors dashboard ``requiresSection4BeforeAward`` (unified_dashboard.js).
        """
        self.ensure_one()
        law = self.project_id.law_master_id if self.project_id else False
        if not law:
            return False
        names = law.section_ids.mapped('name')
        return '(Sec 4) Section 4 Notifications' in names

    def _get_section4_approval_date(self):
        """Return section 4 approval date for this project/village."""
        self.ensure_one()
        if not self.project_id or not self.village_id:
            return False
        section4_records = self.env['bhu.section4.notification'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
        ], order='approved_date desc, signed_date desc, id desc', limit=10)
        for section4 in section4_records:
            for candidate in (
                section4.approved_date,
                section4.signed_date,
                section4.public_hearing_date,
                section4.public_hearing_datetime,
                section4.create_date,
            ):
                if candidate:
                    if isinstance(candidate, str):
                        return fields.Date.to_date(candidate)
                    if hasattr(candidate, 'date'):
                        return candidate.date()
                    return candidate
        return False

    def _get_section4_public_hearing_date(self):
        """Return section 4 public hearing date for this project/village."""
        self.ensure_one()
        if not self.project_id or not self.village_id:
            return False
        section4_records = self.env['bhu.section4.notification'].search([
            ('project_id', '=', self.project_id.id),
            ('village_id', '=', self.village_id.id),
        ], order='public_hearing_date desc, public_hearing_datetime desc, id desc', limit=10)
        for section4 in section4_records:
            if section4.public_hearing_date:
                return fields.Date.to_date(section4.public_hearing_date)
            if section4.public_hearing_datetime:
                dt = fields.Datetime.to_datetime(section4.public_hearing_datetime)
                return dt.date() if dt else False
        return False

    def _s23_gunak_header_text(self, multiline=False):
        """Column 13 header: rural गुणांक 2, urban गुणांक 1."""
        self.ensure_one()
        gunak = int(self._s23_market_value_factor())
        if multiline:
            return f'13.\nगुणांक {gunak} (रुपए में)'
        return f'13. गुणांक {gunak} (रुपए में)'

    def get_award_header_constants(self):
        """Shared award header labels used by Excel and PDF outputs."""
        self.ensure_one()
        headers = get_award_header_constants()
        gunak_header = self._s23_gunak_header_text()
        gunak_header_multiline = self._s23_gunak_header_text(multiline=True)
        headers['excel']['section23_land_headers'][12] = gunak_header
        headers['excel']['sim_land_headers']['tail_headers'][2] = gunak_header_multiline
        headers['pdf']['land_headers']['col_14'] = gunak_header
        return headers

    def _get_award_calculation_date(self):
        """Return award creation date used for interest end date."""
        self.ensure_one()
        if self.award_date:
            return fields.Date.to_date(self.award_date)
        if self.create_date:
            return fields.Datetime.to_datetime(self.create_date).date()
        return fields.Date.context_today(self)

    def _calculate_interest_on_basic(self, basic_value):
        """Calculate interest at 1% per month (or part thereof)."""
        self.ensure_one()
        start_date = self._get_section4_public_hearing_date()
        end_date = self._get_award_calculation_date()
        if not start_date or not end_date or not basic_value:
            return 0.0, 0
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        days = (end_date - start_date).days
        if days <= 0:
            return 0.0, 0
        # Count partial month as full month:
        # 01/01 to 26/04 => 4 months => 4%
        months = (days + 29) // 30
        interest = basic_value * 0.01 * months
        return interest, days

    @api.model
    def _is_fallow_survey(self, survey):
        """Return True when survey is fallow (पड़ती) land."""
        if not survey or not survey.crop_type_id:
            return False    
        crop_code = (survey.crop_type_id.code or '').upper()
        crop_name = (survey.crop_type_id.name or '')
        return crop_code == 'FALLOW' or 'पड़ती' in crop_name

    @api.model
    def _get_min_rehab_rate_per_acre(self, is_fallow, is_irrigated, is_unirrigated):
        """Minimum rehab policy rate per acre for Col 17 floor.

        Policy mapping used:
        - Fallow (crop type): 6,00,000 per acre
        - Irrigated: 10,00,000 per acre
        - Unirrigated (default): 8,00,000 per acre
        """
        if is_fallow:
            return 600000.0
        if is_irrigated:
            return 1000000.0
        return 800000.0

    def _s23_market_value_factor(self):
        """Column 13 gunak: rural ×2, urban ×1."""
        self.ensure_one()
        vtype = self.village_type or (self.village_id.village_type if self.village_id else 'rural')
        return 1.0 if (vtype or 'rural').lower() == 'urban' else 2.0

    @api.model
    def _s23_bmr_rate_multiplier(self, is_mr_lane, is_diverted, is_irrigated):
        """Guideline land-rate factors apply only on the BMR lane (off main-road master rate).

        MR lane (``is_mr_lane``): multiplier **1.0**.

        BMR lane:
        - **Diverted + irrigated**: **×1.25** on the BMR master rate.
        - **Diverted + unirrigated**: **×1.0** on the BMR master rate.
        - **Not diverted + irrigated**: **×1.0** on the BMR master rate.
        - **Not diverted + unirrigated**: **×0.8** on the BMR master rate.
        """
        if is_mr_lane:
            return 1.0
        if is_diverted:
            return 1.25 if is_irrigated else 1.0
        return 1.0 if is_irrigated else 0.8

    def get_interest_period_note(self):
        """Text note for report header interest period from Section 4 public hearing to award date."""
        self.ensure_one()
        start_date = self._get_section4_public_hearing_date()
        end_date = self._get_award_calculation_date()
        if start_date and end_date:
            if end_date < start_date:
                start_date, end_date = end_date, start_date
            return f"{start_date.strftime('%d/%m/%Y')} से {end_date.strftime('%d/%m/%Y')} तक"
        return "धारा 4 सार्वजनिक सुनवाई दिनांक से अवार्ड दिनांक तक"

    def _s23_land_base_rate_per_hectare(self, survey, award_line, derived_within):
        """MR/BMR rate from award values; fallback to active land rate master."""
        self.ensure_one()
        if not self.village_id or not survey:
            return 0.0
        mr_rate = float(self.rate_master_main_road_ha or 0.0)
        bmr_rate = float(self.rate_master_other_road_ha or 0.0)
        if mr_rate <= 0.0 or bmr_rate <= 0.0:
            rm = self._get_active_rate_master_for_village()
            if rm:
                if mr_rate <= 0.0:
                    mr_rate = float(rm.main_road_rate_hectare or 0.0)
                if bmr_rate <= 0.0:
                    bmr_rate = float(rm.other_road_rate_hectare or 0.0)
        land_type = (award_line.land_type if award_line else (survey.land_type_for_award or 'village'))
        is_within = award_line.is_within_distance if award_line else derived_within
        if land_type not in ('village', 'residential'):
            land_type = 'village'
        if is_within:
            return mr_rate
        return bmr_rate
