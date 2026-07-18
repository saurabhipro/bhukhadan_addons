from odoo import http
from odoo.http import request
import json

class OrgChartController(http.Controller):
    @http.route('/bhuarjan/org_chart_data', type='json', auth='user')
    def get_users_tree(self):
        users = request.env['res.users'].sudo().search([])
        Village = request.env['bhu.village'].sudo()
        Tehsil = request.env['bhu.tehsil'].sudo()
        SubDiv = request.env['bhu.sub.division'].sudo()
        data = []
        for u in users:
            villages_rec = Village.search([('user_id', '=', u.id)])
            tehsils_rec = Tehsil.search([('user_id', '=', u.id)])
            subdivisions_rec = SubDiv.search([('user_id', '=', u.id)])
            data.append({
                'id': u.id,
                'parent': u.parent_id.id or None,
                'name': u.name,
                'title': u.login,
                'role': u.bhuarjan_role or 'No Role',
                'state': u.state_id.name if u.state_id else 'No State',
                'district': u.district_id.name if u.district_id else 'No District',
                'mobile': u.mobile or 'No Mobile',
                'active': u.active,
                'avatar': u.avatar_128.decode('utf-8') if u.avatar_128 else None,
                'subordinates_count': len(u.child_ids),
                'villages': [v.name for v in villages_rec],
                'tehsils': [t.name for t in tehsils_rec],
                'sub_divisions': [s.name for s in subdivisions_rec],
            })
        return data

    @http.route('/bhuarjan/detailed_hierarchy', type='json', auth='user')
    def get_detailed_hierarchy(self):
        """
        Returns a complete tree starting from Raigarh district.
        Structure: District -> Tehsils -> Villages -> Users (by role)
        """
        # 1. Find the parent District (Raigarh)
        district = request.env['bhu.district'].sudo().search([('name', 'ilike', 'Raigarh')], limit=1)
        if not district:
            # Fallback to the first district if Raigarh not found
            district = request.env['bhu.district'].sudo().search([], limit=1)
        
        if not district:
            return {'error': 'No district found'}

        # 2. Get all Tehsils under this district
        tehsils = request.env['bhu.tehsil'].sudo().search([('district_id', '=', district.id)])
        
        # 3. Get all Users for this district
        users = request.env['res.users'].sudo().search([('district_id', '=', district.id), ('active', '=', True)])

        linked_user_ids = set()
        for sd_rec in request.env['bhu.sub.division'].sudo().search([('district_id', '=', district.id)]):
            if sd_rec.user_id:
                linked_user_ids.add(sd_rec.user_id.id)
        for tehsil_row in tehsils:
            if tehsil_row.user_id:
                linked_user_ids.add(tehsil_row.user_id.id)
        for village_row in request.env['bhu.village'].sudo().search([('district_id', '=', district.id)]):
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

        # Sub-hierarchy for Users directly under District (e.g. Collector, Admin)
        district_users = users.filtered(
            lambda u: u.id not in linked_user_ids and u.bhuarjan_role in list(
                request.env['res.users'].BHUKHADAN_DISTRICT_LEADERSHIP_ROLES
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
            villages = request.env['bhu.village'].sudo().search([('tehsil_id', '=', tehsil.id)])
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
            
        return tree
