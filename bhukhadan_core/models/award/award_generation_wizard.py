# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import ValidationError


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def action_open_land_surveys_for_edit(self):
        """Open village surveys so users can edit distance/irrigation/diverted quickly."""
        self.ensure_one()
        if not (self.project_id and self.village_id):
            raise ValidationError(_('Select project and village first.'))
        return {
            'name': _('Edit land inputs / भूमि इनपुट संपादित करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhu.survey',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [
                ('project_id', '=', self.project_id.id),
                ('village_id', '=', self.village_id.id),
                ('state', 'in', ['draft', 'submitted', 'approved', 'locked', 'rejected']),
                ('khasra_number', '!=', False),
            ],
            'context': {
                'search_default_project_id': self.project_id.id,
                'search_default_village_id': self.village_id.id,
            },
        }

    def action_download_award(self):
        """Download award document - Open wizard for PDF/Word"""
        self.ensure_one()
        return self._open_award_download_wizard(
            generate=False,
            export_scope='all',
            variant='standard',
            title=_('Download Section 23 Award / धारा 23 अवार्ड डाउनलोड करें'),
        )

    def _open_award_download_wizard(
        self,
        generate=False,
        export_scope='all',
        variant='standard',
        default_format='pdf',
        title=None,
        simple_download_dialog=False,
    ):
        self.ensure_one()
        report_action = self._get_section23_report_action()
        scope = export_scope or 'all'
        if scope not in ('all', 'land', 'asset', 'tree'):
            scope = 'all'
        sheet_variant = variant or 'standard'
        if sheet_variant not in ('standard', 'consolidated', 'rr'):
            sheet_variant = 'standard'
        return {
            'name': title or _('Download Award / अवार्ड डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhu.award.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': report_action.get_external_id().get(
                    report_action.id, 'bhukhadan_core.action_report_section23_award'
                ),
                'default_filename': f'Section23_Award_{self.name}.pdf',
                'default_export_scope': scope,
                'default_add_cover_letter': True,
                'default_section23_generate': bool(generate),
                'default_section23_sheet_variant': sheet_variant,
                'default_format': default_format if default_format in ('pdf', 'excel') else 'pdf',
                'default_simple_download_dialog': bool(simple_download_dialog),
            }
        }
