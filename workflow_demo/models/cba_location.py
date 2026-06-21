# -*- coding: utf-8 -*-

from odoo import api, models, fields


class CbaDistrict(models.Model):
    _name = 'cba.district'
    _description = 'CBA District'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(string='District Code')
    active = fields.Boolean(default=True)


class CbaTehsil(models.Model):
    _name = 'cba.tehsil'
    _description = 'CBA Tehsil'
    _order = 'name'

    name = fields.Char(required=True)
    district_id = fields.Many2one('cba.district', required=True, ondelete='restrict')
    active = fields.Boolean(default=True)


class CbaVillage(models.Model):
    _name = 'cba.village'
    _description = 'CBA Village'
    _order = 'name'

    name = fields.Char(required=True)
    tehsil_id = fields.Many2one('cba.tehsil', required=True, ondelete='restrict')
    district_id = fields.Many2one(
        'cba.district',
        related='tehsil_id.district_id',
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    @api.model
    def _search_by_project_district(self, args):
        """Filter villages by project district passed from cba.case form context."""
        district_id = self.env.context.get('cba_project_district_id')
        if district_id:
            args = (args or []) + [('district_id', '=', district_id)]
        return args

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = self._search_by_project_district(args)
        return super().name_search(name, args, operator, limit)

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        domain = self._search_by_project_district(list(domain or []))
        return super().search_fetch(domain, field_names, offset, limit, order)
