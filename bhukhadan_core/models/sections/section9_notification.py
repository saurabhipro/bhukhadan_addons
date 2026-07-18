# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class Section9Notification(models.Model):
    _name = 'bhu.section9.notification'
    _description = 'Section 9 Notification'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Section 9 Reference / धारा 9 संदर्भ',
        required=True,
        tracking=True,
        default='New',
        readonly=True,
        copy=False,
    )
    declaration_number = fields.Char(
        string='Declaration Number / घोषणा क्रमांक',
        tracking=True,
        help='Official declaration reference used in the Section 9 template.',
    )
    declaration_date = fields.Date(
        string='Declaration Date / घोषणा दिनांक',
        tracking=True,
    )
    gazette_publication_date = fields.Date(
        string='Gazette Publication Date / राजपत्र प्रकाशन दिनांक',
        tracking=True,
    )
    notification_summary = fields.Text(
        string='Notification Summary / अधिसूचना सारांश',
        tracking=True,
    )
    remarks = fields.Text(
        string='Remarks / टिप्पणियां',
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                project_id = vals.get('project_id')
                village_id = vals.get('village_id')
                seq = False
                if project_id:
                    seq = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'section9',
                        project_id,
                        village_id=village_id if village_id else None,
                    )
                vals['name'] = seq or (self.env['ir.sequence'].next_by_code('bhu.section9.notification') or 'SEC9-NEW')
        return super().create(vals_list)

    def action_print_section9(self):
        self.ensure_one()
        return self.env.ref('bhukhadan_core.action_report_section9_notification').report_action(self)
