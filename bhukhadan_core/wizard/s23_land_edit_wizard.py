# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class S23LandEditWizard(models.TransientModel):
    _name = 'bhu.s23.land.edit.wizard'
    _description = 'Section 23 – Edit land inputs (distance / irrigation / diverted)'

    survey_line_id = fields.Many2one(
        'bhu.section23.award.survey.line',
        string='Survey line',
        required=True,
        ondelete='cascade',
    )
    khasra_display = fields.Char(string='Khasra / खसरा', readonly=True)
    distance_help = fields.Char(
        string='MR/BMR threshold',
        compute='_compute_distance_help',
    )

    distance_from_main_road = fields.Float(
        string='Distance from main road (m) / मुख्य मार्ग से दूरी (मी.)',
        digits=(10, 2),
    )
    road_type = fields.Selection(
        [
            ('mr',  'MR – main road rate / मुख्य मार्ग दर'),
            ('mbr', 'BMR – beyond main road / मार्ग से परे'),
        ],
        string='Road rate band / मार्ग दर',
        required=True,
    )
    irrigation_type = fields.Selection(
        [
            ('irrigated',   'Irrigated / सिंचित'),
            ('unirrigated', 'Unirrigated / असिंचित'),
        ],
        string='Irrigation / सिंचाई',
    )
    has_traded_land = fields.Selection(
        [
            ('yes', 'Yes – diverted (traded) / हाँ – विचलित'),
            ('no',  'No / नहीं'),
        ],
        string='Diverted land / विचलित भूमि',
    )

    # ------------------------------------------------------------------ helpers
    @api.model
    def _normalize_irrigation_type(self, irrigation_type):
        """Map legacy values to valid wizard options."""
        val = (irrigation_type or '').strip().lower()
        if val == 'irrigated':
            return 'irrigated'
        # Legacy records may still carry "fallow"; treat as unirrigated.
        if val in ('unirrigated', 'fallow'):
            return 'unirrigated'
        return 'unirrigated'

    def _village_type(self):
        self.ensure_one()
        line = self.survey_line_id
        award = line.award_id if line else False
        if award and award.village_id:
            return award.village_id.village_type or 'rural'
        survey = line.survey_id if line else False
        if survey and survey.village_id:
            return survey.village_id.village_type or 'rural'
        return 'rural'

    def _threshold(self):
        st = self._village_type()
        return 50.0 if st == 'rural' else 20.0

    @api.depends('survey_line_id')
    def _compute_distance_help(self):
        for wiz in self:
            st = wiz._village_type() if wiz.survey_line_id else False
            th   = 50.0 if st == 'rural' else 20.0 if st == 'urban' else 50.0
            kind = 'Rural / ग्रामीण' if st == 'rural' else 'Urban / शहरी' if st == 'urban' else 'Rural / ग्रामीण'
            wiz.distance_help = _(
                'MR if ≤ %(th)s m  |  BMR if > %(th)s m  (Village type: %(kind)s)'
            ) % {'th': int(th), 'kind': kind}

    # ------------------------------------------------------------------ onchanges
    @api.onchange('distance_from_main_road')
    def _onchange_distance_auto_road_type(self):
        th = self._threshold()
        d  = self.distance_from_main_road or 0.0
        self.road_type = 'mr' if d <= th else 'mbr'

    @api.onchange('road_type')
    def _onchange_road_type_adjust_distance(self):
        th = self._threshold()
        d  = self.distance_from_main_road or 0.0
        if self.road_type == 'mr' and d > th:
            self.distance_from_main_road = th
        elif self.road_type == 'mbr' and d <= th:
            self.distance_from_main_road = th + 1.0

    # ------------------------------------------------------------------ default_get
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get('default_survey_line_id')
        if not line_id:
            return res
        line = self.env['bhu.section23.award.survey.line'].browse(line_id)
        if not (line.exists() and line.survey_id):
            return res
        s   = line.survey_id
        d   = s.distance_from_main_road or 0.0
        award = line.award_id
        village_type = award.village_id.village_type if (award and award.village_id) else (s.village_id.village_type if s.village_id else 'rural')
        th  = 20.0 if village_type == 'urban' else 50.0
        res.update({
            'survey_line_id':          line.id,
            'khasra_display':          s.khasra_number or '',
            'distance_from_main_road': d,
            'road_type':               'mr' if d <= th else 'mbr',
            'irrigation_type':         self._normalize_irrigation_type(s.irrigation_type),
            'has_traded_land':         s.has_traded_land or 'no',
        })
        return res

    # ------------------------------------------------------------------ apply
    def action_open_linked_survey(self):
        """Open the exact survey record linked to this khasra line."""
        self.ensure_one()
        line = self.survey_line_id
        survey = line.survey_id if line else False
        if not survey:
            raise UserError(_('No survey linked on this line.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Survey / सर्वे'),
            'res_model': 'bhu.survey',
            'res_id': survey.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'flags': {
                'mode': 'readonly',
            },
            'context': {
                'form_view_initial_mode': 'readonly',
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    def action_apply(self):
        self.ensure_one()
        line   = self.survey_line_id
        survey = line.survey_id if line else False
        if not survey:
            raise UserError(_('No survey linked on this line.'))

        before_distance = survey.distance_from_main_road or 0.0
        before_irrigation = survey.irrigation_type or ''
        before_diverted = survey.has_traded_land or ''
        before_within_distance = bool(line.is_within_distance) if line else False

        village_type = line.award_id.village_id.village_type if (line and line.award_id and line.award_id.village_id) else (survey.village_id.village_type if survey.village_id else 'rural')
        th = 20.0 if village_type == 'urban' else 50.0
        d  = self.distance_from_main_road or 0.0
        if self.road_type == 'mr':
            d = min(d, th)
        else:
            if d <= th:
                d = th + 1.0

        survey.write({
            'distance_from_main_road': d,
            'irrigation_type':         self._normalize_irrigation_type(self.irrigation_type),
            'has_traded_land':         self.has_traded_land,
        })
        # Keep award-line MR/BMR lane in sync with popup selection so table badge updates immediately.
        if line:
            line.write({'is_within_distance': self.road_type == 'mr'})
        changed_parts = []
        if float(before_distance or 0.0) != float(d or 0.0):
            changed_parts.append(
                _('Distance: %(old)s m -> %(new)s m') % {
                    'old': round(float(before_distance or 0.0), 2),
                    'new': round(float(d or 0.0), 2),
                }
            )
        if (before_irrigation or '') != (self.irrigation_type or ''):
            changed_parts.append(
                _('Irrigation: %(old)s -> %(new)s') % {
                    'old': before_irrigation or '-',
                    'new': self.irrigation_type or '-',
                }
            )
        if (before_diverted or '') != (self.has_traded_land or ''):
            changed_parts.append(
                _('Diverted land: %(old)s -> %(new)s') % {
                    'old': before_diverted or '-',
                    'new': self.has_traded_land or '-',
                }
            )
        if before_within_distance != (self.road_type == 'mr'):
            changed_parts.append(
                _('Road band: %(old)s -> %(new)s') % {
                    'old': 'MR' if before_within_distance else 'BMR',
                    'new': 'MR' if self.road_type == 'mr' else 'BMR',
                }
            )
        if changed_parts:
            survey.message_post(
                body=_(
                    'Survey updated from Section 23 Award by <b>%(user)s</b> (award: %(award)s, khasra: %(khasra)s).<br/>%(changes)s'
                ) % {
                    'user': self.env.user.name,
                    'award': line.award_id.name if line and line.award_id else '-',
                    'khasra': survey.khasra_number or '-',
                    'changes': '<br/>'.join(changed_parts),
                }
            )
        # Recompute the award line rate so it reflects immediately
        line._compute_rate_per_hectare()
        # Also refresh award totals
        if line.award_id:
            line.award_id._compute_s23_section_previews()
            line.award_id._compute_land_total()
            line.award_id._compute_tree_total()
            line.award_id._compute_structure_total()
            line.award_id._compute_grand_total()

        return {'type': 'ir.actions.act_window_close'}
