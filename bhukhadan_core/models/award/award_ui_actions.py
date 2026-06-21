# -*- coding: utf-8 -*-

import logging

from odoo import models, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def action_clear_khasra_filter(self):
        """Clear the khasra filter and reload."""
        self.ensure_one()
        self.khasra_filter = ''
        if self.project_id and self.village_id and not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_clear_tree_khasra_filter(self):
        """Clear the tree khasra filter and reload."""
        self.ensure_one()
        self.tree_khasra_filter = ''
        if self.project_id and self.village_id and not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_clear_asset_khasra_filter(self):
        """Clear asset khasra filter and reload."""
        self.ensure_one()
        self.asset_khasra_filter = ''
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_asset_lines_popup(self):
        """Open asset lines popup; if khasra typed, open add form for that khasra."""
        self.ensure_one()
        if self.project_id and self.village_id and not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        list_view = False
        form_view = False
        try:
            list_view = self.env.ref('bhukhadan_core.view_bhu_award_structure_details_popup_list').id
        except Exception:
            list_view = False
        try:
            form_view = self.env.ref('bhukhadan_core.view_bhu_award_structure_details_popup_form').id
        except Exception:
            form_view = False
        term = (self.asset_khasra_filter or '').strip()
        if term:
            if not self.award_survey_line_ids:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Add Asset',
                        'message': 'No khasra lines found. Select project and village first.',
                        'type': 'warning',
                        'sticky': False,
                    },
                }
            matches = self.award_survey_line_ids.filtered(
                lambda l, t=term.lower(): t in (l.khasra_number or '').lower()
            )
            if not matches:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Add Asset',
                        'message': f'No khasra matched "{term}".',
                        'type': 'warning',
                        'sticky': False,
                    },
                }
            exact = matches.filtered(
                lambda l, t=term.lower(): (l.khasra_number or '').strip().lower() == t
            )
            if not exact and len(matches) > 1:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Add Asset',
                        'message': f'Multiple khasra matched "{term}". Please type full khasra number.',
                        'type': 'warning',
                        'sticky': False,
                    },
                }
            target_line = (exact[:1] or matches[:1])
            return {
                'type': 'ir.actions.act_window',
                'name': _('Add Asset / परिसंपत्ति जोड़ें'),
                'res_model': 'bhu.award.structure.details',
                'view_mode': 'form',
                'views': [(form_view, 'form')],
                'target': 'new',
                'context': {
                    'default_award_id': self.id,
                    'default_survey_id': target_line.survey_id.id if target_line and target_line.survey_id else False,
                    'default_structure_type': 'makan',
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asset Lines / परिसंपत्ति पंक्तियां'),
            'res_model': 'bhu.award.structure.details',
            'view_mode': 'list,form',
            'views': [(list_view, 'list'), (form_view, 'form')],
            'domain': [('award_id', '=', self.id)],
            'target': 'new',
            'context': {
                'default_award_id': self.id,
                'create': True,
            },
        }

    def action_apply_asset_khasra_search(self):
        """Search by khasra and open existing asset rows (or add form if none)."""
        self.ensure_one()
        if self.project_id and self.village_id and not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        term = (self.asset_khasra_filter or '').strip()
        if not term:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': 'Enter a khasra value before searching asset lines.',
                    'type': 'warning',
                    'sticky': False,
                },
            }
        if not self.award_survey_line_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': 'No khasra lines found. Select project and village first.',
                    'type': 'warning',
                    'sticky': False,
                },
            }
        survey_matches = self.award_survey_line_ids.filtered(
            lambda l, t=term.lower(): t in (l.khasra_number or '').lower()
        )
        if not survey_matches:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': f'No khasra matched "{term}".',
                    'type': 'warning',
                    'sticky': False,
                },
            }
        exact = survey_matches.filtered(
            lambda l, t=term.lower(): (l.khasra_number or '').strip().lower() == t
        )
        if not exact and len(survey_matches) > 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': f'Multiple khasra matched "{term}". Please type full khasra number.',
                    'type': 'warning',
                    'sticky': False,
                },
            }
        target_line = (exact[:1] or survey_matches[:1])
        target_survey = target_line.survey_id if target_line else False
        matches = self.award_structure_line_ids.filtered(
            lambda l, sid=target_survey.id if target_survey else False: l.survey_id.id == sid
        )
        form_view = False
        try:
            form_view = self.env.ref('bhukhadan_core.view_bhu_award_structure_details_popup_form').id
        except Exception:
            form_view = False
        if not matches:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Add Asset / परिसंपत्ति जोड़ें'),
                'res_model': 'bhu.award.structure.details',
                'view_mode': 'form',
                'views': [(form_view, 'form')],
                'target': 'new',
                'context': {
                    'default_award_id': self.id,
                    'default_survey_id': target_survey.id if target_survey else False,
                    'default_structure_type': 'makan',
                },
            }
        if len(matches) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Asset Line / परिसंपत्ति पंक्ति'),
                'res_model': 'bhu.award.structure.details',
                'res_id': matches.id,
                'view_mode': 'form',
                'views': [(form_view, 'form')],
                'target': 'new',
            }
        list_view = False
        form_view = False
        try:
            list_view = self.env.ref('bhukhadan_core.view_bhu_award_structure_details_popup_list').id
        except Exception:
            list_view = False
        try:
            form_view = self.env.ref('bhukhadan_core.view_bhu_award_structure_details_popup_form').id
        except Exception:
            form_view = False
        return {
            'type': 'ir.actions.act_window',
            'name': f'Asset Khasra Search: {term}',
            'res_model': 'bhu.award.structure.details',
            'view_mode': 'list,form',
            'views': [(list_view, 'list'), (form_view, 'form')],
            'domain': [('id', 'in', matches.ids)],
            'target': 'new',
            'context': {
                'create': True,
            },
        }

    def action_open_tree_add_popup(self):
        """Open tree edit wizard directly for typed khasra."""
        self.ensure_one()
        if self.project_id and self.village_id and not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        if not self.award_survey_line_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Add Tree',
                    'message': 'No khasra lines found. Select project and village first.',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        term = (self.tree_khasra_filter or '').strip()
        if not term:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Add Tree',
                    'message': 'Please enter Khasra number first, then click Add Tree.',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        matches = self.award_survey_line_ids.filtered(
            lambda l, t=term.lower(): t in (l.khasra_number or '').lower()
        )
        if not matches:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Add Tree',
                    'message': f'No khasra matched "{term}".',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        exact = matches.filtered(
            lambda l, t=term.lower(): (l.khasra_number or '').strip().lower() == t
        )
        if not exact and len(matches) > 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Add Tree',
                    'message': f'Multiple khasra matched "{term}". Please type full khasra number.',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        target_line = (exact[:1] or matches[:1])
        return target_line.action_open_survey_for_tree_edit()

    def action_refresh_land_lines_debug(self):
        """[DEBUG] Manually refresh land lines from surveys. Logs details to server console."""
        self.ensure_one()
        _logger.info(f"\n{'='*80}")
        _logger.info(f"[MANUAL DEBUG] User clicked 'Refresh Land Lines'")
        _logger.info(f"Award: {self.name} (ID {self.id})")
        _logger.info(f"Project: {self.project_id.name if self.project_id else 'None'} (ID {self.project_id.id if self.project_id else None})")
        _logger.info(f"Village: {self.village_id.name if self.village_id else 'None'} (ID {self.village_id.id if self.village_id else None})")
        _logger.info(f"Current award_survey_line_ids count: {len(self.award_survey_line_ids)}")
        _logger.info(f"{'='*80}\n")
        self._populate_award_survey_lines(reset_if_empty=True)
        _logger.info(f"\n[MANUAL DEBUG] After populate: award_survey_line_ids count = {len(self.award_survey_line_ids)}\n")
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_apply_khasra_search(self):
        """Search khasra and open edit popup(s) for matching land line(s)."""
        self.ensure_one()
        if self.project_id and self.village_id and not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        term = (self.khasra_filter or '').strip()
        if not term:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': 'Enter a khasra value before searching.',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        matches = self.award_survey_line_ids.filtered(
            lambda l, t=term.lower(): t in (l.khasra_number or '').lower()
        )
        if not matches:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': f'No khasra matched "{term}".',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        # If exactly one match, open the same 4-field edit wizard directly.
        if len(matches) == 1:
            return matches.action_open_survey_for_land_edit()

        # If multiple matches, open popup list with Edit button on each row.
        tree_view = False
        try:
            tree_view = self.env.ref('bhukhadan_core.view_section23_award_survey_line_tree').id
        except Exception:
            tree_view = False

        return {
            'type': 'ir.actions.act_window',
            'name': f'Khasra Search: {term}',
            'res_model': 'bhu.section23.award.survey.line',
            'view_mode': 'list',
            'views': [(tree_view, 'list')],
            'domain': [('id', 'in', matches.ids)],
            'target': 'new',
            'context': {
                'default_award_id': self.id,
                'create': False,
                'edit': False,
            },
        }

    def action_apply_tree_khasra_search(self):
        """Search khasra and open popup tree editor for matching survey line(s)."""
        self.ensure_one()
        if self.project_id and self.village_id and not self.award_survey_line_ids:
            self._populate_award_survey_lines(reset_if_empty=False)
        term = (self.tree_khasra_filter or '').strip()
        if not term:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': 'Enter a khasra value before searching tree lines.',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        matches = self.award_survey_line_ids.filtered(
            lambda l, t=term.lower(): t in (l.khasra_number or '').lower()
        )
        if not matches:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Search',
                    'message': f'No khasra matched "{term}".',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        if len(matches) == 1:
            return matches.action_open_survey_for_tree_edit()

        tree_view = False
        try:
            tree_view = self.env.ref('bhukhadan_core.view_section23_award_survey_line_tree').id
        except Exception:
            tree_view = False

        return {
            'type': 'ir.actions.act_window',
            'name': f'Tree Khasra Search: {term}',
            'res_model': 'bhu.section23.award.survey.line',
            'view_mode': 'list',
            'views': [(tree_view, 'list')],
            'domain': [('id', 'in', matches.ids)],
            'target': 'new',
            'context': {
                'default_award_id': self.id,
                'create': False,
                'edit': False,
            },
        }

    def _s23_recompute_award_survey_lines_for_export(self):
        """Recompute and persist land survey line rates before PDF/Excel (current survey + master)."""
        self.ensure_one()
        lines = self.award_survey_line_ids
        if not lines:
            return
        lines._compute_rate_per_hectare()
        lines._compute_line_display_amounts()
        lines.flush_recordset()

    def action_refresh_land_rates(self):
        """Force-recompute rate_per_hectare and display amounts for all land survey lines."""
        self.ensure_one()
        self._s23_recompute_award_survey_lines_for_export()
        lines = self.award_survey_line_ids
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Rates Refreshed',
                'message': _('Recomputed rates for %s land survey line(s) from the active rate master.') % len(lines),
                'type': 'success',
                'sticky': False,
            },
        }
