# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AwardStructureDetails(models.Model):
    _name = 'bhu.award.structure.details'
    _description = 'Award Structure Line'
    _order = 'id desc'

    survey_id = fields.Many2one(
        'bhu.survey',
        string='Khasra / खसरा',
        index=True,
        ondelete='cascade',
        # Not required in DB: new O2M rows on an unsaved parent must be creatable; pick default in
        # default_get; generation/submit on award re-validates.
    )
    award_id = fields.Many2one(
        'bhu.section23.award',
        string='Section 23 Award',
        index=True,
        ondelete='set null'
    )

    project_id = fields.Many2one(
        'bhu.project',
        string='Project',
        related='survey_id.project_id',
        store=True,
        readonly=True
    )
    village_id = fields.Many2one(
        'bhu.village',
        string='Village',
        related='survey_id.village_id',
        store=True,
        readonly=True
    )
    khasra_number = fields.Char(
        string='Khasra Number / खसरा नंबर',
        related='survey_id.khasra_number',
        store=True,
        readonly=True
    )

    structure_type = fields.Selection([
        ('makan', 'Makan / मकान'),
        ('well', 'Well / कुआं'),
        ('maveshi_kotha', 'Maveshi Kotha / मवेशी कोठा'),
        ('poultry_farm_shed', 'Poultry Farm Shed / पोल्ट्री फार्म शेड'),
        ('other', 'Others / अन्य'),
    ], string='Structure Type / परिसम्पत्ति विवरण', required=True, default='makan')
    construction_type = fields.Selection([
        ('kaccha', 'Kaccha / कच्चा'),
        ('pukka', 'Pukka / पक्का'),
        ('other', 'Other / अन्य'),
    ], string='Construction Type / निर्माण प्रकार')
    description = fields.Char(string='Description / विवरण')

    asset_count = fields.Integer(string='Asset Count', default=1)
    area_sqm = fields.Float(string='Area (Sq. Meter) / क्षेत्रफल (वर्ग मीटर)', digits=(10, 2))
    market_rate_per_sqm = fields.Float(string='Market Rate per Sq. Meter (₹) / बाजार मूल्य दर (प्रति वर्ग मीटर)', digits=(16, 2))

    asset_value = fields.Float(
        string='Asset Value (₹) / परिसम्पत्ति की कीमत',
        digits=(16, 2),
        compute='_compute_line_total',
        store=True
    )
    line_total = fields.Float(
        string='Line Total (₹) / पंक्ति कुल',
        digits=(16, 2),
        compute='_compute_line_total',
        store=True
    )

    @api.model
    def _auto_init(self):
        res = super()._auto_init()
        self._cr.execute(
            """
            CREATE INDEX IF NOT EXISTS bhu_award_structure_details_award_survey_idx
            ON bhu_award_structure_details (award_id, survey_id)
            """
        )
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not fields_list:
            return res
        if 'structure_type' in fields_list and not res.get('structure_type'):
            res['structure_type'] = 'makan'
        if 'survey_id' in fields_list and not res.get('survey_id'):
            project_id, village_id = self._s23_default_project_village_for_line()
            if project_id and village_id:
                survey = self.env['bhu.survey'].search([
                    ('project_id', '=', project_id),
                    ('village_id', '=', village_id),
                    ('khasra_number', '!=', False),
                    ('state', 'in', ['draft', 'submitted', 'approved', 'locked']),
                ], order='khasra_number', limit=1)
                if survey:
                    res['survey_id'] = survey.id
        return res

    @api.model
    def _s23_default_project_village_for_line(self):
        """Resolve project/village for default khasra from O2M parent (works with NewId in form)."""
        award_id = self.env.context.get('default_award_id')
        if award_id:
            award = self.env['bhu.section23.award'].browse(award_id)
            if award:
                p, v = award.project_id, award.village_id
                if p and v:
                    return p.id, v.id
        return False, False

    @api.depends('area_sqm', 'asset_count', 'market_rate_per_sqm')
    def _compute_line_total(self):
        for line in self:
            qty = line.asset_count or 0
            rate = line.market_rate_per_sqm or 0.0
            if line.structure_type == 'well':
                # Well valuation is per unit well count.
                computed_value = qty * rate
            else:
                # Other structures follow area-based valuation.
                computed_value = (line.area_sqm or 0.0) * rate * qty
            line.asset_value = computed_value
            line.line_total = computed_value

    @api.onchange('area_sqm', 'asset_count', 'market_rate_per_sqm')
    def _onchange_line_total_fast(self):
        """Immediate UI feedback in editable tree rows."""
        for line in self:
            qty = line.asset_count or 0
            rate = line.market_rate_per_sqm or 0.0
            if line.structure_type == 'well':
                computed_value = qty * rate
            else:
                computed_value = (line.area_sqm or 0.0) * rate * qty
            line.asset_value = computed_value
            line.line_total = computed_value

    @api.onchange('structure_type')
    def _onchange_structure_type_default_rate(self):
        """Set standard base rate for well entries."""
        for line in self:
            if line.structure_type == 'well' and not line.market_rate_per_sqm:
                line.market_rate_per_sqm = 90000.0
            if line.structure_type != 'other' and line.construction_type != 'other':
                line.description = False

    @api.constrains('structure_type', 'construction_type', 'description')
    def _check_other_requires_description(self):
        for line in self:
            needs_desc = line.structure_type == 'other' or line.construction_type == 'other'
            if needs_desc and not (line.description or '').strip():
                raise ValidationError(_(
                    "Please enter Description when Structure Type or Construction Type is 'Other / अन्य'."
                ))

    def get_structure_type_label(self):
        self.ensure_one()
        base = dict(self._fields['structure_type'].selection).get(self.structure_type, self.structure_type or 'Other')
        if self.structure_type == 'other' and (self.description or '').strip():
            base = f"{base} - {self.description.strip()}"
        if self.construction_type:
            ctype = dict(self._fields['construction_type'].selection).get(self.construction_type, self.construction_type)
            return f"{base} ({ctype})"
        return base
