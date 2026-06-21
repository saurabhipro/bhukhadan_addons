from odoo import models, fields, api, _
from odoo.exceptions import UserError
import uuid
import logging

_logger = logging.getLogger(__name__)

class BhuVillage(models.Model):
    _name = 'bhu.village'
    _description = 'Village'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _get_state_domain(self):
        state_ids = self.env['bhu.district'].search([]).mapped('state_id.id')    
        return [('id', 'in', state_ids)]

    village_uuid = fields.Char(string='Village UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))
    
    def action_regenerate_all_uuids(self):
        """Regenerate unique UUIDs for all villages to ensure uniqueness"""
        all_villages = self.search([])
        total = len(all_villages)
        fixed = 0
        duplicates_found = 0
        
        _logger.info(f"Starting UUID regeneration for {total} villages...")
        
        # Track UUIDs we've assigned to ensure uniqueness
        assigned_uuids = set()
        
        for village in all_villages:
            original_uuid = village.village_uuid
            
            # Check if UUID is missing
            if not village.village_uuid:
                new_uuid = str(uuid.uuid4())
                # Ensure the new UUID is unique (very unlikely but check anyway)
                while new_uuid in assigned_uuids:
                    new_uuid = str(uuid.uuid4())
                village.write({'village_uuid': new_uuid})
                assigned_uuids.add(new_uuid)
                fixed += 1
                _logger.info(f"Village {village.id} ({village.name}) - Generated new UUID: {new_uuid}")
                continue
            
            # Check for duplicates
            duplicate_villages = self.search([
                ('village_uuid', '=', village.village_uuid),
                ('id', '!=', village.id)
            ])
            
            if duplicate_villages or village.village_uuid in assigned_uuids:
                duplicates_found += 1
                new_uuid = str(uuid.uuid4())
                # Ensure the new UUID is unique
                while new_uuid in assigned_uuids:
                    new_uuid = str(uuid.uuid4())
                village.write({'village_uuid': new_uuid})
                assigned_uuids.add(new_uuid)
                fixed += 1
                _logger.info(f"Village {village.id} ({village.name}) - Duplicate UUID found! Regenerated: {original_uuid} -> {new_uuid}")
            else:
                assigned_uuids.add(village.village_uuid)
        
        message = f"UUID regeneration completed!\n\nTotal villages: {total}\nUUIDs regenerated: {fixed}\nDuplicates found: {duplicates_found}"
        _logger.info(message)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'UUID Regeneration Complete',
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_regenerate_uuid(self):
        """Regenerate UUID for a single village"""
        if not self:
            return
        new_uuid = str(uuid.uuid4())
        # Ensure the new UUID is unique
        while self.env['bhu.village'].search([('village_uuid', '=', new_uuid)]):
            new_uuid = str(uuid.uuid4())
        
        self.write({'village_uuid': new_uuid})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'UUID Regenerated',
                'message': f'New UUID: {new_uuid}',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def regenerate_all_uuids_cron(self):
        """Cron method to ensure all villages have unique UUIDs"""
        self.action_regenerate_all_uuids()
    
    state_id = fields.Many2one('res.country.state', string='State', tracking=True)
    user_id = fields.Many2one('res.users', string='Patwari', tracking=True)

    district_id = fields.Many2one('bhu.district', string='District / जिला', tracking=True)
    sub_division_id = fields.Many2one('bhu.sub.division', string='Sub Division / उपभाग', tracking=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील', tracking=True)
    name = fields.Char(string='Village Name / ग्राम का नाम', required=True)
    name_english = fields.Char(
        string='Village Name (English)',
        tracking=True,
        index=True,
        help='Romanized or English spelling for searching and displays.',
    )
    village_code = fields.Char(string='Village Code / ग्राम कोड', tracking=True, copy=False, help='Optional unique code for the village')

    @api.depends('name', 'village_code')
    def _compute_display_name(self):
        """Prefix many2one labels with village code when set (e.g. ``[CODE] Name``)."""
        for village in self:
            label = (village.name or '').strip()
            code = (village.village_code or '').strip()
            if code and label:
                village.display_name = f'[{code}] {label}'
            elif label:
                village.display_name = label
            elif code:
                village.display_name = f'[{code}]'
            else:
                village.display_name = f'{village._name},{village.id}'

    pincode = fields.Char(string='Pincode / पिनकोड', tracking=True)
    village_type = fields.Selection([
        ('rural',  'Rural / ग्रामीण'),
        ('urban',  'Urban / नगरीय'),
    ], string='Village Type / ग्राम प्रकार', default='rural', tracking=True,
       help='Rural or Urban classification of this village.')

    urban_body_type = fields.Selection([
        ('nagar_nigam',     'Nagar Nigam / नगर निगम'),
        ('nagar_palika',    'Nagar Palika / नगर पालिका'),
        ('nagar_panchayat', 'Nagar Panchayat / नगर पंचायत'),
    ], string='Urban Body Type / नगरीय निकाय प्रकार', tracking=True,
       help='Applicable only for Urban villages. Controls area-based slab rates in the award.')
    
    project_ids = fields.Many2many(
        'bhu.project',
        'bhu_project_bhu_village_rel',
        'bhu_village_id',
        'bhu_project_id',
        string='Projects / परियोजनाएं',
        help='Projects that include this village (managed from each project’s Villages tab, '
             'or by linking/unlinking here when the village form is editable).',
    )

    # Bulk-clean helper (server action): drop links involving “mega” projects.
    _MASS_PROJECT_VILLAGE_CAP = 250

    def action_strip_mismatched_project_links(self):
        """Remove this village only from projects whose village roster is absurdly large.

        Uses roster size only (no tehsil logic). Typical junk imports attach hundreds of
        villages to many projects; legitimate projects usually stay under the cap.
        """
        cap = self._MASS_PROJECT_VILLAGE_CAP
        for village in self:
            huge = village.project_ids.filtered(lambda p: len(p.village_ids) > cap)
            if huge:
                huge.write({'village_ids': [(3, village.id, 0)]})
        return True

    project_link_count = fields.Integer(
        string='Projects',
        compute='_compute_project_link_count',
        store=True,
    )

    @api.depends('project_ids')
    def _compute_project_link_count(self):
        for rec in self:
            rec.project_link_count = len(rec.project_ids)

    def action_view_linked_projects(self):
        """Open bhu.project records that include this village (inverse of project.village_ids)."""
        self.ensure_one()
        action = {
            'name': _('Projects / परियोजनाएं'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhu.project',
            'view_mode': 'list,form',
            'domain': [('village_ids', 'in', self.id)],
            'flags': {'mode': 'edit'},
            'context': {
                'skip_project_domain_filter': True,
            },
            'target': 'current',
        }
        try:
            project_action = self.env.ref('bhukhadan_core.action_bhu_project')
            if project_action:
                action_ref = project_action.read(['view_mode', 'views', 'search_view_id'])[0]
                if action_ref.get('views'):
                    action['views'] = action_ref['views']
                if action_ref.get('view_mode'):
                    action['view_mode'] = action_ref['view_mode']
                if action_ref.get('search_view_id'):
                    sv = action_ref['search_view_id']
                    action['search_view_id'] = sv[0] if isinstance(sv, (list, tuple)) else sv
        except Exception:
            pass
        return action

    def action_clear_linked_projects(self):
        """Remove this village from every project's Villages tab (fixes legacy mass links)."""
        for village in self:
            if village.project_ids:
                village.project_ids.write({'village_ids': [(3, village.id, 0)]})
        return True

    def _unlink_project_blocked_message(self, village):
        """Plain UserError body: unique project names, one bracketed “pill” per line.

        Real HTML badge widgets are not available in the standard Odoo warning dialog
        (messages are HTML-escaped); 【】 bullets read clearly for long Hindi/English titles.
        """
        projects = village.project_ids
        if not projects:
            return ''

        ordered = projects.sorted(
            lambda r: ((r.name or '').strip()).casefold()
            if (r.name or '').strip()
            else 'id:%s' % r.id
        )

        pill_labels = []
        seen = set()
        for proj in ordered:
            nm = (proj.name or '').strip()
            label = nm or (_('Project #%s') % proj.id)
            key = nm.casefold() if nm else 'id:%s' % proj.id
            if key in seen:
                continue
            seen.add(key)
            pill_labels.append(label)

        pill_lines = '\n'.join('  【 %s 】' % lbl for lbl in pill_labels)

        return _(
            'Cannot delete village "%(village)s"\n\n'
            '%(intro)s\n'
            '────────────────────────────────────\n'
            '%(pills)s\n'
            '────────────────────────────────────\n\n'
            '%(steps)s'
        ) % {
            'village': village.display_name,
            'intro': _(
                'This village is still mapped to project(s). '
                'Each project name appears only once below:'
            ),
            'pills': pill_lines,
            'steps': _(
                'What to do:\n'
                '  • Open each listed project.\n'
                '  • On the Villages tab, remove this village.\n'
                '  • Then delete this village again.'
            ),
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_except_when_mapped_to_projects(self):
        """Villages linked on a project's Villages tab cannot be deleted."""
        for village in self:
            if not village.project_ids:
                continue
            raise UserError(self._unlink_project_blocked_message(village))
    
    # Related records counts
    section4_notification_count = fields.Integer(string='Section 4 Notifications', compute='_compute_notification_counts', store=False)
    
    # Survey statistics (computed per village)
    survey_count = fields.Integer(
        string='Total Surveys / कुल सर्वे',
        compute='_compute_village_survey_statistics',
        store=False,
        help='Total number of survey records linked to this village',
    )
    total_khasras_count = fields.Integer(string='Total Khasras / कुल खसरा', 
                                         compute='_compute_village_survey_statistics', 
                                         store=False,
                                         help='Total unique khasra numbers in surveys for this village')
    total_captured_area = fields.Float(string='Total Captured Area (Hectares) / कुल कैप्चर क्षेत्रफल (हेक्टेयर)',
                                       compute='_compute_village_survey_statistics',
                                       store=False,
                                       digits=(16, 4),
                                       help='Total acquired area from surveys for this village')
    
    def _compute_village_survey_statistics(self):
        """Compute survey count, unique khasras, and captured area from surveys for this village"""
        for village in self:
            surveys = self.env['bhu.survey'].search([('village_id', '=', village.id)])
            village.survey_count = len(surveys)

            surveys_khasra = surveys.filtered(lambda s: s.khasra_number)
            unique_khasras = set(surveys_khasra.mapped('khasra_number'))
            village.total_khasras_count = len(unique_khasras)
            village.total_captured_area = sum(surveys_khasra.mapped('acquired_area'))
    
    def _compute_notification_counts(self):
        """Compute counts of related notifications"""
        for village in self:
            # Count Section 4 Notifications that include this village
            section4_count = self.env['bhu.section4.notification'].search_count([
                ('village_id', '=', village.id)
            ])
            village.section4_notification_count = section4_count
    
    def action_view_section4_notifications(self):
        """Open Section 4 Notifications for this village"""
        self.ensure_one()
        return {
            'name': _('Section 4 Notifications / धारा 4 अधिसूचनाएं'),
            'type': 'ir.actions.act_window',
            'res_model': 'bhu.section4.notification',
            'view_mode': 'list,form',
            'domain': [('village_id', '=', self.id)],
            'context': {'default_village_id': self.id},
        }
    
    _sql_constraints = [
        ('village_code_unique', 'UNIQUE(village_code)', 'Village Code must be unique! / ग्राम कोड अद्वितीय होना चाहिए!')
    ]
