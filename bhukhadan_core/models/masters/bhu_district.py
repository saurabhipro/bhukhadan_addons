from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class BhuDistrict(models.Model):
    _name = 'bhu.district'
    _description = 'District / जिला'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='District Name / जिला का नाम', required=True, tracking=True)
    code = fields.Char(string='District Code / जिला कोड', tracking=True)
    state_id = fields.Many2one('res.country.state', string='State / राज्य', required=True, 
                              domain="[('country_id.name','=','India')]", tracking=True)
    
    # Related Records
    sub_division_ids = fields.One2many('bhu.sub.division', 'district_id', string='Sub Divisions / उपभाग')
    tehsil_ids = fields.One2many('bhu.tehsil', 'district_id', string='Tehsils / तहसील')
    village_ids = fields.One2many('bhu.village', 'district_id', string='Villages / ग्राम')
    
    # Computed Fields
    sub_division_count = fields.Integer(string='Sub Divisions Count', compute='_compute_counts')
    tehsil_count = fields.Integer(string='Tehsils Count', compute='_compute_counts')
    village_count = fields.Integer(string='Villages Count', compute='_compute_counts')
    
    @api.depends('sub_division_ids', 'tehsil_ids', 'village_ids')
    def _compute_counts(self):
        """Compute counts of related records"""
        for record in self:
            record.sub_division_count = len(record.sub_division_ids)
            record.tehsil_count = len(record.tehsil_ids)
            record.village_count = len(record.village_ids)
    
    @api.constrains('name', 'state_id')
    def _check_unique_district_per_state(self):
        """Ensure district name is unique within a state"""
        for district in self:
            if district.name and district.state_id:
                existing = self.search([
                    ('id', '!=', district.id),
                    ('name', '=', district.name),
                    ('state_id', '=', district.state_id.id)
                ])
                if existing:
                    raise ValidationError(_('District "%s" already exists in state "%s".') % 
                                        (district.name, district.state_id.name))
    
    def action_view_sub_divisions(self):
        """View sub divisions of this district"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sub Divisions of %s') % self.name,
            'res_model': 'bhu.sub.division',
            'view_mode': 'list,form',
            'domain': [('district_id', '=', self.id)],
            'context': {'default_district_id': self.id}
        }
    
    def action_view_tehsils(self):
        """View tehsils of this district"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tehsils of %s') % self.name,
            'res_model': 'bhu.tehsil',
            'view_mode': 'list,form',
            'domain': [('district_id', '=', self.id)],
            'context': {'default_district_id': self.id}
        }
    
    def action_view_villages(self):
        """View villages of this district"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Villages of %s') % self.name,
            'res_model': 'bhu.village',
            'view_mode': 'list,form',
            'domain': [('district_id', '=', self.id)],
            'context': {'default_district_id': self.id}
        }
    

    @api.model
    def get_detailed_hierarchy(self, district_id=None):
        """
        Returns a complete tree starting from Raigarh district.
        Structure: District -> Tehsils -> Villages -> Users (by role)
        """
        # 1. Find the parent District
        if district_id:
            district = self.browse(district_id)
        else:
            # Try to match based on the list of currently selected companies
            allowed_companies = self.env.companies
            _logger.info("HIERARCHY: Selected Companies: %s", allowed_companies.mapped('name'))
            
            # 1. Try to find a district that matches ANY of the selected company names
            for comp in allowed_companies:
                c_name = (comp.name or '').strip()
                district = self.search([('name', 'ilike', c_name)], limit=1)
                if district:
                    _logger.info("HIERARCHY: Matched company '%s' to district '%s'", c_name, district.name)
                    # If we found multiple, and one is 'Raigarh', prioritize it? 
                    # For now, we take the first match we find in the selection.
                    break
            
            # 2. Try substring matching across all selected companies
            if not district:
                all_districts = self.search([])
                for comp in allowed_companies:
                    c_name = (comp.name or '').lower()
                    for d in all_districts:
                        d_name = (d.name or '').lower()
                        if d_name in c_name or c_name in d_name:
                            district = d
                            _logger.info("HIERARCHY: Substring match: %s", d.name)
                            break
                    if district: break

            # 3. Fallback to current user's assigned district
            if not district:
                district = self.env.user.district_id
                if district:
                    _logger.info("HIERARCHY: User district fallback: %s", district.name)
            
            # 4. Hard fallback to 'Raigarh'
            if not district:
                district = self.search([('name', 'ilike', 'Raigarh')], limit=1)

            # 5. Ultimate fallback
            if not district:
                district = self.search([], limit=1)
        if not district:
            return {'error': 'No district found'}

        # 2. Get all Tehsils under this district
        tehsils = self.env['bhu.tehsil'].search([('district_id', '=', district.id)])
        
        # 3. Get all Users for this district
        users = self.env['res.users'].search([('district_id', '=', district.id), ('active', '=', True)])

        linked_user_ids = set()
        for sd_rec in self.env['bhu.sub.division'].search([('district_id', '=', district.id)]):
            if sd_rec.user_id:
                linked_user_ids.add(sd_rec.user_id.id)
        for tehsil_row in tehsils:
            if tehsil_row.user_id:
                linked_user_ids.add(tehsil_row.user_id.id)
        for village_row in self.env['bhu.village'].search([('district_id', '=', district.id)]):
            if village_row.user_id:
                linked_user_ids.add(village_row.user_id.id)
        
        # Helper to get avatar
        def get_avatar(u):
            return u.avatar_128.decode('utf-8') if u.avatar_128 else None

        # Build the tree
        tree = {
            'id': f'd_{district.id}',
            'name': district.name,
            'type': 'district',
            'children': []
        }

        # Sub-hierarchy for Users directly under District (not tied as SDM/Tehsildar/Patwari on masters)
        district_users = users.filtered(
            lambda u: u.id not in linked_user_ids and u.bhuarjan_role in list(
                self.env['res.users'].BHUKHADAN_DISTRICT_LEADERSHIP_ROLES
            )
        )
        for u in district_users:
            tree['children'].append({
                'id': f'u_{u.id}',
                'name': u.name,
                'type': 'user',
                'role': u.bhuarjan_role,
                'avatar': get_avatar(u),
                'title': u.login
            })

        for tehsil in tehsils:
            tehsil_node = {
                'id': f't_{tehsil.id}',
                'name': tehsil.name,
                'type': 'tehsil',
                'children': []
            }
            
            tehsil_users = users.filtered(lambda u: tehsil.user_id and u.id == tehsil.user_id.id)
            for u in tehsil_users:
                tehsil_node['children'].append({
                    'id': f'u_{u.id}',
                    'name': u.name,
                    'type': 'user',
                    'role': u.bhuarjan_role,
                    'avatar': get_avatar(u),
                    'title': u.login
                })
            
            # Villages under this Tehsil
            villages = self.env['bhu.village'].search([('tehsil_id', '=', tehsil.id)])
            for village in villages:
                village_node = {
                    'id': f'v_{village.id}',
                    'name': village.name,
                    'type': 'village',
                    'children': []
                }
                
                village_users = users.filtered(lambda u: village.user_id and u.id == village.user_id.id)
                for u in village_users:
                    village_node['children'].append({
                        'id': f'u_{u.id}',
                        'name': u.name,
                        'type': 'user',
                        'role': u.bhuarjan_role,
                        'avatar': get_avatar(u),
                        'title': u.login
                    })
                
                tehsil_node['children'].append(village_node)
            
            tree['children'].append(tehsil_node)
            
        return {
            'tree': tree,
            'available_districts': self.search_read([], ['id', 'name'])
        }
