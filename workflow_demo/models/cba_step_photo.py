# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup, escape


class CbaStepPhoto(models.Model):
    """Site / survey photo attached to a CBA workflow step (similar to survey photos)."""
    _name = 'cba.step.photo'
    _description = 'CBA Step Photo'
    _inherit = ['mail.thread']
    _order = 'sequence, create_date desc'

    name = fields.Char(string='Caption', tracking=True)
    case_id = fields.Many2one(
        'cba.case',
        string='CBA Case',
        required=True,
        ondelete='cascade',
        index=True,
    )
    step_line_id = fields.Many2one(
        'cba.case.step.line',
        string='Process Step',
        ondelete='cascade',
        index=True,
        domain="[('case_id', '=', case_id)]",
    )
    photo_type_id = fields.Many2one(
        'cba.photo.type',
        string='Photo Type',
        help='Optional classification (e.g. site, asset, crop).',
    )
    image = fields.Binary(string='Photo', attachment=True, required=True)
    image_filename = fields.Char(string='Filename')
    latitude = fields.Float(string='Latitude', digits=(10, 8))
    longitude = fields.Float(string='Longitude', digits=(11, 8))
    sequence = fields.Integer(default=10)
    notes = fields.Text(string='Notes')
    image_preview = fields.Html(
        string='Preview',
        compute='_compute_image_preview',
        sanitize=False,
    )

    @api.depends('image')
    def _compute_image_preview(self):
        for record in self:
            if record.image and record.id:
                record.image_preview = Markup(
                    f'<img src="/web/image/cba.step.photo/{record.id}/image" '
                    f'alt="CBA photo" style="max-height:120px;max-width:180px;'
                    f'border-radius:6px;object-fit:cover;" />'
                )
            else:
                record.image_preview = Markup('')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for photo in records:
            if photo.step_line_id and photo.step_line_id.status == 'pending':
                photo.step_line_id.status = 'in_progress'
            if photo.case_id and photo.case_id.state == 'draft':
                photo.case_id.state = 'in_progress'
        return records
