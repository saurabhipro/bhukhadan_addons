# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BhuScreenshotLog(models.Model):
    _name = 'bhu.screenshot.log'
    _description = 'Screenshot Audit Log'
    _order = 'event_time desc, id desc'
    _rec_name = 'display_name'

    event_time = fields.Datetime(
        string='Event Time',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_login = fields.Char(string='Login')
    user_mobile = fields.Char(string='Mobile')
    user_role = fields.Char(string='Role')
    ip_address = fields.Char(string='IP Address', index=True)
    user_agent = fields.Char(string='User Agent')
    platform = fields.Selection(
        selection=[
            ('android', 'Android'),
            ('ios', 'iOS'),
            ('web', 'Web'),
            ('linux', 'Linux'),
            ('windows', 'Windows'),
            ('macos', 'macOS'),
            ('unknown', 'Unknown'),
        ],
        string='Platform',
        default='unknown',
    )
    screen_name = fields.Char(string='Screen / Page', index=True)
    survey_id = fields.Many2one(
        'bhu.survey',
        string='Survey',
        ondelete='set null',
        index=True,
    )
    device_info = fields.Char(string='Device Info')
    notes = fields.Text(string='Notes')
    raw_payload = fields.Text(string='Raw Payload')
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('user_id', 'user_id.name', 'ip_address', 'screen_name', 'event_time')
    def _compute_display_name(self):
        for rec in self:
            user = rec.user_id.name or rec.user_login or 'Unknown'
            ip = rec.ip_address or '-'
            screen = rec.screen_name or 'unknown'
            when = fields.Datetime.to_string(rec.event_time) if rec.event_time else ''
            rec.display_name = f'{user} @ {ip} — {screen} ({when})'
