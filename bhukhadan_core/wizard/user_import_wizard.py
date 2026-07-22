# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.bhukhadan_core.utils.user_import import import_user_roster_xlsx


class BhuUserImportWizard(models.TransientModel):
    _name = 'bhu.user.import.wizard'
    _description = 'User Roster Import Wizard'

    data_file = fields.Binary(string='Excel File (.xlsx)', required=True)
    data_file_filename = fields.Char(string='File Name')
    district_id = fields.Many2one(
        'bhu.district',
        string='District / जिला',
        default=lambda self: self.env.user.district_id,
        help='Used for master lookups. Required when auto-creating missing '
             'Project / Tehsil / Sub Division / Village. District Administrators '
             'are limited to their district.',
    )
    update_existing = fields.Boolean(
        string='Update Existing Users',
        default=True,
        help='Update name, mobile, and role when a matching user already exists.',
    )
    create_missing_masters = fields.Boolean(
        string='Create Missing Masters',
        default=True,
        help='If Project / Department / Tehsil / Sub Division / Village is not found, create it '
             'under the selected District, then map the user.',
    )
    force_relink = fields.Boolean(
        string='Overwrite Existing Officer Links',
        default=False,
        help='If a Tehsil / Sub Division / Village is already linked to another user, '
             'replace that link with the imported user.',
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
    created_count = fields.Integer(string='Users Created', readonly=True)
    updated_count = fields.Integer(string='Users Updated', readonly=True)
    masters_created_count = fields.Integer(string='Masters Created', readonly=True)
    tehsils_linked_count = fields.Integer(string='Tehsils Linked', readonly=True)
    subdivisions_linked_count = fields.Integer(string='Sub Divisions Linked', readonly=True)
    villages_linked_count = fields.Integer(string='Villages Linked', readonly=True)
    projects_linked_count = fields.Integer(string='Project↔Village Maps', readonly=True)
    departments_linked_count = fields.Integer(string='Departments Linked', readonly=True)
    rows_count = fields.Integer(string='Rows Processed', readonly=True)
    error_count = fields.Integer(string='Errors', readonly=True)

    @api.model
    def _default_district_id(self):
        user = self.env.user
        is_full_admin = (
            user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('base.group_system')
        )
        if is_full_admin:
            return user.district_id.id if user.district_id else False
        if user.has_group('bhukhadan_core.group_bhuarjan_district_administrator'):
            return user.district_id.id if user.district_id else False
        return False

    def _resolve_district_id(self):
        self.ensure_one()
        user = self.env.user
        is_full_admin = (
            user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('base.group_system')
        )
        if not is_full_admin and user.has_group('bhukhadan_core.group_bhuarjan_district_administrator'):
            if not user.district_id:
                raise ValidationError(_('Your user account has no district assigned.'))
            return user.district_id.id
        return self.district_id.id if self.district_id else False

    def action_import(self):
        self.ensure_one()
        if not self.data_file:
            raise ValidationError(_('Please upload an Excel file.'))

        district_id = self._resolve_district_id()
        if self.create_missing_masters and not district_id:
            raise ValidationError(_(
                'Select a District when “Create Missing Masters” is enabled, '
                'so new Department / Tehsil / Village / Project records can be placed correctly.'
            ))

        stats, log_text = import_user_roster_xlsx(
            self.env,
            self.data_file,
            self.data_file_filename or 'user_roster_import.xlsx',
            district_id=district_id,
            update_existing=self.update_existing,
            dry_run=self.dry_run,
            create_missing_masters=self.create_missing_masters,
            force_relink=self.force_relink,
        )

        self.write({
            'state': 'done',
            'log_text': log_text,
            'created_count': stats['created'],
            'updated_count': stats['updated'],
            'masters_created_count': stats.get('masters_created', 0),
            'tehsils_linked_count': stats['tehsils_linked'],
            'subdivisions_linked_count': stats['subdivisions_linked'],
            'villages_linked_count': stats['villages_linked'],
            'projects_linked_count': stats.get('projects_linked', 0),
            'departments_linked_count': stats.get('departments_linked', 0),
            'rows_count': stats['rows'],
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
                    'message': log_text.split('\n', 2)[1] if log_text else title,
                    'type': notif_type,
                },
            },
        }
