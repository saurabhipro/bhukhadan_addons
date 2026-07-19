# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.bhukhadan_core.utils.survey_import import import_survey_xlsx


class BhuSurveyImportWizard(models.TransientModel):
    _name = 'bhu.survey.import.wizard'
    _description = 'Survey XLSX Import Wizard'

    data_file = fields.Binary(string='Excel File (.xlsx)', required=True)
    data_file_filename = fields.Char(string='File Name')
    project_id = fields.Many2one(
        'bhu.project', string='Project / परियोजना', required=True,
    )
    village_id = fields.Many2one(
        'bhu.village', string='Village / ग्राम', required=True,
    )
    department_id = fields.Many2one(
        'bhu.department', string='Department / विभाग', required=True,
    )
    area_id = fields.Many2one(
        'bhukhadan.area.master', string='Area / क्षेत्र',
    )
    allowed_village_ids = fields.Many2many(
        'bhu.village',
        compute='_compute_allowed_village_ids',
        string='Villages available for selection',
    )
    update_existing = fields.Boolean(
        string='Update Existing Surveys',
        default=False,
        help='If a survey already exists for the same village and khasra, update it instead of skipping.',
    )
    dry_run = fields.Boolean(
        string='Validate Only (Dry Run)',
        default=False,
        help='Parse and validate the file without creating or updating records.',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], default='draft')
    log_text = fields.Text(string='Import Log', readonly=True)
    created_count = fields.Integer(string='Created', readonly=True)
    updated_count = fields.Integer(string='Updated', readonly=True)
    skipped_count = fields.Integer(string='Skipped', readonly=True)
    error_count = fields.Integer(string='Errors', readonly=True)

    @api.depends('project_id', 'project_id.village_ids')
    def _compute_allowed_village_ids(self):
        for wizard in self:
            wizard.allowed_village_ids = (
                wizard.project_id.village_ids if wizard.project_id
                else self.env['bhu.village'].browse()
            )

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            if self.project_id.department_id:
                self.department_id = self.project_id.department_id
            if self.village_id and self.village_id not in self.project_id.village_ids:
                self.village_id = False
            return {'domain': {'village_id': [('id', 'in', self.project_id.village_ids.ids)]}}
        return {'domain': {'village_id': []}}

    def action_import(self):
        self.ensure_one()
        if not self.data_file:
            raise ValidationError(_('Please upload an Excel file.'))
        if not self.project_id or not self.village_id or not self.department_id:
            raise ValidationError(_('Project, village, and department are required.'))

        stats, log_text = import_survey_xlsx(
            self.env,
            self.data_file,
            self.data_file_filename or 'survey_import.xlsx',
            self.project_id.id,
            self.village_id.id,
            self.department_id.id,
            area_id=self.area_id.id if self.area_id else False,
            update_existing=self.update_existing,
            dry_run=self.dry_run,
        )

        self.write({
            'state': 'done',
            'log_text': log_text,
            'created_count': stats['created'],
            'updated_count': stats['updated'],
            'skipped_count': stats['skipped'],
            'error_count': stats['errors'],
        })

        title = _('Validation Complete') if self.dry_run else _('Import Complete')
        notif_type = 'success' if stats['errors'] == 0 else 'warning'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_import_notification': {
                    'title': title,
                    'message': log_text.split('\n', 1)[0],
                    'type': notif_type,
                },
            },
        }
