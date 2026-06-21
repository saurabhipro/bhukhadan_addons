# -*- coding: utf-8 -*-
from odoo import fields, models


class GoogleFontFamily(models.Model):
    """Compatibility model for optional backend theme fields."""
    _name = 'google.font.family'
    _description = 'Google Font Family (Compatibility)'

    name = fields.Char(required=True)
    css_name = fields.Char()
    font_url = fields.Char()
    url = fields.Char(string='URL')
    is_selected = fields.Boolean(string='Selected', default=False)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    active = fields.Boolean(default=True)


class KpiProviderCompatibility(models.AbstractModel):
    """Placeholder to avoid stale model-registry warnings."""
    _name = 'kpi.provider'
    _description = 'KPI Provider (Compatibility)'


class IrQwebFieldOne2ManyCompatibility(models.AbstractModel):
    """Placeholder to avoid stale model-registry warnings."""
    _name = 'ir.qweb.field.one2many'
    _description = 'QWeb one2many Field (Compatibility)'
