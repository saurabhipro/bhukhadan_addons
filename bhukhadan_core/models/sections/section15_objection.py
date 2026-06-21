# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
import json

class Section15Objection(models.Model):
    _name = 'bhu.section15.objection'
    _description = 'Section 15 Objections'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Objection Reference / आपत्ति संदर्भ', required=True, tracking=True, default='New', readonly=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True, tracking=True)
    
    # Single survey (khasra) selection - multiple objections can be created for the same survey
    survey_id = fields.Many2one('bhu.survey', string='Survey (Khasra) / सर्वे (खसरा)', tracking=True,
                                help='Select a khasra from the selected village. Multiple objections can be created for the same khasra to track different changes (landowner added/removed, area decreased).')
    
    # Available surveys for selection (computed based on village)
    available_survey_ids = fields.Many2many('bhu.survey', string='Available Surveys', compute='_compute_available_survey_ids', store=False)
    
    # Landowners from selected surveys (can be removed or added)
    resolution_landowner_ids = fields.Many2many('bhu.landowner', 
                                                'section15_objection_landowner_rel',
                                                'objection_id', 'landowner_id',
                                                string='Landowners (After Resolution) / भूमिस्वामी (समाधान के बाद)', 
                                                tracking=True,
                                                help='Landowners after resolution. You can add or remove landowners. Changes are tracked in the survey.')
    
    # Original landowners from surveys (readonly, for comparison)
    original_landowner_ids = fields.Many2many('bhu.landowner', 
                                             'section15_objection_original_landowner_rel',
                                             'objection_id', 'landowner_id',
                                             string='Original Landowners / मूल भूमिस्वामी', 
                                             compute='_compute_original_landowner_ids', 
                                             store=True, readonly=True)
    
    # Resolution changes per khasra (One2many to track area decreases per survey)
    resolution_khasra_ids = fields.One2many('bhu.section15.objection.khasra', 'objection_id',
                                            string='Khasra Resolution Changes / खसरा समाधान परिवर्तन',
                                            tracking=True,
                                            help='Track area decreases per khasra')
    
    objection_resolution_comments = fields.Text(string='Objection and Resolution Comments / आपत्ति एवं निराकरण कमेंट बॉक्स', tracking=True)
    
    # Separate fields for objection and resolution
    objection_comments = fields.Text(string='Objection / आपत्ति', tracking=True, help='Enter the objection details here')
    resolution_comments = fields.Text(string='Resolution / निराकरण', tracking=True, help='Enter the resolution details here')
    
    @api.depends('village_id')
    def _compute_available_survey_ids(self):
        """Compute available survey IDs based on village - show all khasras from that village"""
        for record in self:
            if record.village_id:
                # Find all surveys (khasras) for this village
                # Only one active objection can be created for the same survey (Khasra)
                # Order by khasra_number descending
                surveys = self.env['bhu.survey'].search([
                    ('village_id', '=', record.village_id.id),
                    ('state', 'in', ['draft', 'submitted', 'approved'])  # Only show valid surveys
                ], order='khasra_number desc')
                record.available_survey_ids = surveys
            else:
                record.available_survey_ids = False
    
    @api.depends('survey_id')
    def _compute_original_landowner_ids(self):
        """Compute original landowners from selected survey"""
        for record in self:
            if record.survey_id:
                # Get all landowners from selected survey
                record.original_landowner_ids = record.survey_id.landowner_ids
            else:
                record.original_landowner_ids = False
    
    objection_date = fields.Date(string='Objection Date / आपत्ति दिनांक', required=True, tracking=True, default=fields.Date.today)
    
    # Extend workflow state with "rejected" without overriding the base workflow selection
    state = fields.Selection(selection_add=[('rejected', 'Rejected')], tracking=True)
    
    # Age in days since objection date
    age_days = fields.Integer(string='Age (Days) / आयु (दिन)', compute='_compute_age_days', store=False)
    
    @api.depends('objection_date')
    def _compute_age_days(self):
        """Compute age of objection in days"""
        today = date.today()
        for record in self:
            if record.objection_date:
                delta = today - record.objection_date
                record.age_days = delta.days
            else:
                record.age_days = 0
    
    @api.onchange('resolution_landowner_ids')
    def _onchange_resolution_landowner_ids(self):
        """Auto-generate objection number when landowners are changed"""
        if self.survey_id and self.resolution_landowner_ids and self.name == 'New':
            # Check if landowners actually changed
            if set(self.resolution_landowner_ids.ids) != set(self.original_landowner_ids.ids):
                # Auto-generate objection number
                if self.project_id:
                    sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'section15_objection', self.project_id.id, village_id=self.village_id.id if self.village_id else None
                    )
                    if sequence_number:
                        self.name = sequence_number
                    else:
                        sequence = self.env['ir.sequence'].next_by_code('bhu.section15.objection') or str(self._origin.id or 'NEW')
                        self.name = f'OBJ-{sequence}'
                
                # Show warning message
                return {
                    'warning': {
                        'title': _('Objection Created / आपत्ति बनाई गई'),
                        'message': _('Landowner changes detected. Objection %s has been created automatically. Please save to confirm.') % self.name +
                                 '\n\n' + _('भूमिस्वामी परिवर्तन का पता चला। आपत्ति %s स्वचालित रूप से बनाई गई है। पुष्टि करने के लिए कृपया सहेजें।') % self.name
                    }
                }
    
    @api.onchange('resolution_khasra_ids')
    def _onchange_resolution_khasra_ids(self):
        """Auto-generate objection number when area is changed"""
        if self.survey_id and self.resolution_khasra_ids and self.name == 'New':
            # Check if any area was actually changed
            for khasra in self.resolution_khasra_ids:
                if khasra.resolved_acquired_area and khasra.resolved_acquired_area != khasra.original_acquired_area:
                    # Auto-generate objection number
                    if self.project_id:
                        sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                            'section15_objection', self.project_id.id, village_id=self.village_id.id if self.village_id else None
                        )
                        if sequence_number:
                            self.name = sequence_number
                        else:
                            sequence = self.env['ir.sequence'].next_by_code('bhu.section15.objection') or str(self._origin.id or 'NEW')
                            self.name = f'OBJ-{sequence}'
                    
                    # Show warning message
                    return {
                        'warning': {
                            'title': _('Objection Created / आपत्ति बनाई गई'),
                            'message': _('Area changes detected. Objection %s has been created automatically. Please save to confirm.') % self.name +
                                     '\n\n' + _('क्षेत्रफल परिवर्तन का पता चला। आपत्ति %s स्वचालित रूप से बनाई गई है। पुष्टि करने के लिए कृपया सहेजें।') % self.name
                        }
                    }
                    break
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate objection reference if not provided"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                # Try to use sequence settings from settings master
                project_id = vals.get('project_id')
                village_id = vals.get('village_id')
                if project_id:
                    sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'section15_objection', project_id, village_id=village_id
                    )
                    if sequence_number:
                        vals['name'] = sequence_number
                    else:
                        # Fallback to ir.sequence
                        sequence = self.env['ir.sequence'].next_by_code('bhu.section15.objection') or 'New'
                        vals['name'] = f'OBJ-{sequence}'
                else:
                    # No project_id, use fallback
                    sequence = self.env['ir.sequence'].next_by_code('bhu.section15.objection') or 'New'
                    vals['name'] = f'OBJ-{sequence}'
        records = super().create(vals_list)
        
        # Link this objection to the survey and sync landowners
        for record in records:
            if record.survey_id:
                # Link objection to survey (Many2many)
                record.survey_id.section15_objection_ids = [(4, record.id)]
                
                # Sync landowners to survey immediately on creation if provided
                if record.resolution_landowner_ids:
                    record.survey_id.write({
                        'landowner_ids': [(6, 0, record.resolution_landowner_ids.ids)]
                    })
                
                if not record.resolution_khasra_ids:
                    record.resolution_khasra_ids = [(0, 0, {
                        'survey_id': record.survey_id.id,
                        'original_acquired_area': record.survey_id.acquired_area,
                        'resolved_acquired_area': record.survey_id.acquired_area,
                    })]
            
            # Validate that changes were made
            record._validate_objection_changes()
        
        return records
    
    def _validate_objection_changes(self):
        """Validate that actual changes were made before saving objection"""
        for record in self:
            # Skip validation if we don't have a survey selected yet
            if not record.survey_id:
                continue
            
            # Check if landowners changed - compare IDs directly
            # Use record._origin if available to get the truly original state if needed,
            # but for many2many, comparing resolution vs original should work.
            landowners_changed = False
            
            # Get current resolution IDs and original IDs
            # many2many fields always return a recordset, so .ids is safe
            res_ids = set(record.resolution_landowner_ids.ids)
            orig_ids = set(record.original_landowner_ids.ids)
            
            if res_ids != orig_ids:
                landowners_changed = True
            
            # Check if area changed
            area_changed = False
            if record.resolution_khasra_ids:
                for khasra in record.resolution_khasra_ids:
                    # Use a small epsilon for float comparison if necessary, but here we expect exact matches for "no change"
                    if khasra.resolved_acquired_area != khasra.original_acquired_area:
                        area_changed = True
                        break
            
            # Check if comments added
            comments_added = bool(record.objection_resolution_comments) or bool(record.objection_comments) or bool(record.resolution_comments)
            
            # If nothing changed, raise error
            # if not landowners_changed and not area_changed and not comments_added:
            #     res_count = len(record.resolution_landowner_ids)
            #     orig_count = len(record.original_landowner_ids)
            #     raise ValidationError(_(
            #         "No changes detected! Cannot save objection without any changes to landowners, khasra area, or adding comments.\n"
            #         "(Current Landowners: %d, Original Landowners: %d)\n\n"
            #         "कोई परिवर्तन नहीं मिला! भूमिस्वामी, खसरा क्षेत्रफल या कमेंट जोड़े बिना आपत्ति सहेजी नहीं जा सकती।\n"
            #         "(वर्तमान भूमिस्वामी: %d, मूल भूमिस्वामी: %d)"
            #     ) % (res_count, orig_count, res_count, orig_count))
    
    @api.constrains('survey_id')
    def _check_unique_survey_objection(self):
        """Ensure only one objection per Khasra (Survey) is possible in a village"""
        for record in self:
            if record.survey_id:
                # Search for other objections for the same survey_id that are NOT rejected
                duplicate = self.search([
                    ('survey_id', '=', record.survey_id.id),
                    ('id', '!=', record.id),
                    ('state', '!=', 'rejected'),
                ], limit=1)
                
                if duplicate:
                    raise ValidationError(_(
                        "An objection already exists for Khasra No. %s (Objection Ref: %s). "
                        "Only one objection per Khasra is allowed in this village."
                    ) % (record.survey_id.khasra_number, duplicate.name))

    
    def action_open_reject_wizard(self):
        """Open the reject survey wizard from the main form"""
        self.ensure_one()
        if not self.survey_id:
            raise ValidationError(_('Please select a survey (khasra) first.'))
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Survey / सर्वे अस्वीकार करें'),
            'res_model': 'bhu.reject.survey.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_objection_id': self.id,
                'default_survey_id': self.survey_id.id,
            }
        }

    def write(self, vals):
        """Override write to update survey when objection is saved"""
        # Validate changes before write (only for resolution fields)
        if 'resolution_landowner_ids' in vals or 'resolution_khasra_ids' in vals:
            # After write, validate changes
            result = super().write(vals)
            self._validate_objection_changes()
        else:
            result = super().write(vals)
        
        # Centralized sync to survey
        if 'resolution_landowner_ids' in vals or 'resolution_khasra_ids' in vals:
            for record in self:
                record._sync_to_survey()
        
        # If survey_id changed, update resolution_khasra_ids and resolution_survey_detail_ids
        if 'survey_id' in vals:
            for record in self:
                if record.survey_id:
                    # Update khasra resolution
                    if record.resolution_khasra_ids:
                        for khasra in record.resolution_khasra_ids:
                            if not khasra.survey_id:
                                khasra.write({
                                    'survey_id': record.survey_id.id,
                                    'original_acquired_area': record.survey_id.acquired_area,
                                })
                                if khasra.resolved_acquired_area > record.survey_id.acquired_area:
                                    khasra.write({'resolved_acquired_area': record.survey_id.acquired_area})
                    elif record.survey_id:
                        record.resolution_khasra_ids = [(0, 0, {
                            'survey_id': record.survey_id.id,
                            'original_acquired_area': record.survey_id.acquired_area,
                            'resolved_acquired_area': record.survey_id.acquired_area,
                        })]
                    

        

        
        return result

    def _sync_to_survey(self):
        """Centralized method to sync objection changes to the survey"""
        self.ensure_one()
        if not self.survey_id:
            return
            
        # 1. Sync landowners
        if self.resolution_landowner_ids:
            self.survey_id.write({
                'landowner_ids': [(6, 0, self.resolution_landowner_ids.ids)]
            })
            
        # 2. Sync khasra details (area, wells, etc.) from resolution lines
        for khasra in self.resolution_khasra_ids:
            if khasra.survey_id:
                # Map all resolution fields to survey fields
                sync_vals = {
                    'acquired_area': khasra.resolved_acquired_area,
                    'has_well': khasra.has_well,
                    'well_count': khasra.well_count,
                    'has_tubewell': khasra.has_tubewell,
                    'tubewell_count': khasra.tubewell_count,
                    'has_house': khasra.has_house,
                    'house_area': khasra.house_area,
                    'has_shed': khasra.has_shed,
                    'shed_area': khasra.shed_area,
                    'has_pond': khasra.has_pond,
                    'irrigation_type': khasra.irrigation_type,
                }
                khasra.survey_id.write(sync_vals)

    

    village_domain = fields.Char()
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain"""
        for rec in self:
            if rec.project_id and rec.project_id.village_ids:
                rec.village_domain = json.dumps([('id', 'in', rec.project_id.village_ids.ids)])
            else:
                rec.village_domain = json.dumps([])   # empty domain
                rec.village_id = False
    
    @api.onchange('village_id')
    def _onchange_village_id(self):
        """Reset survey when village changes"""
        self.survey_id = False
        self.resolution_landowner_ids = False
        self.resolution_khasra_ids = False
        # Trigger recomputation
        self._compute_available_survey_ids()
    
    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        """Update original landowners and initialize resolution data when survey changes"""
        if not self.survey_id:
            self.resolution_landowner_ids = False
            self.resolution_khasra_ids = [(5, 0, 0)]

            return
        
        # Compute original landowners
        all_landowners = self.survey_id.landowner_ids
        self.original_landowner_ids = all_landowners
        # Initialize resolution_landowner_ids with original
        if all_landowners:
            self.resolution_landowner_ids = [(6, 0, all_landowners.ids)]
        else:
            self.resolution_landowner_ids = False
            return {
                'warning': {
                    'title': _('No Landowners Found'),
                    'message': _('The selected survey (Khasra %s) has no linked landowners. Please check the survey data.') % self.survey_id.khasra_number
                }
            }
        
        # Initialize or update resolution khasra record
        if self.resolution_khasra_ids and len(self.resolution_khasra_ids) > 0:
            # Update existing record
            existing = self.resolution_khasra_ids[0]
            if existing.id:
                existing.write({
                    'survey_id': self.survey_id.id,
                    'original_acquired_area': self.survey_id.acquired_area,
                })
                if existing.resolved_acquired_area > self.survey_id.acquired_area:
                    existing.write({'resolved_acquired_area': self.survey_id.acquired_area})
            else:
                existing.survey_id = self.survey_id.id
                existing.original_acquired_area = self.survey_id.acquired_area
                if existing.resolved_acquired_area > self.survey_id.acquired_area:
                    existing.resolved_acquired_area = self.survey_id.acquired_area
        else:
            # Create new record
            if self.survey_id.id:
                self.resolution_khasra_ids = [(0, 0, {
                    'survey_id': self.survey_id.id,
                    'original_acquired_area': self.survey_id.acquired_area,
                    'resolved_acquired_area': self.survey_id.acquired_area,
                })]
        

    
    @api.constrains('resolution_landowner_ids')
    def _check_resolution_landowners(self):
        """Ensure at least one landowner remains"""
        for record in self:
            # Ensure at least one landowner remains
            if not record.resolution_landowner_ids:
                raise ValidationError(_('At least one landowner must remain. You cannot remove all landowners.'))
    
    @api.constrains('resolution_khasra_ids')
    def _check_resolution_areas(self):
        """Ensure resolved areas are not greater than original areas - SDM can only decrease, not increase"""
        for record in self:
            for khasra in record.resolution_khasra_ids:
                if khasra.original_acquired_area and khasra.resolved_acquired_area:
                    if khasra.resolved_acquired_area > khasra.original_acquired_area:
                        raise ValidationError(_('Resolved acquired area (%.4f hectares) cannot be greater than original area (%.4f hectares) for khasra %s. You can only decrease the area, not increase it.') % 
                                            (khasra.resolved_acquired_area, khasra.original_acquired_area, khasra.survey_id.khasra_number or khasra.khasra_number or ''))
    
    def action_approve(self):
        """Approve objection (SDM action)"""
        self.ensure_one()
        
        # Check if user is SDM
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM can approve.'))
        
        # Resolution details is optional, no validation needed
        
        # Validate state is draft
        if self.state != 'draft':
            raise ValidationError(_('Only draft records can be approved.'))
        
        self.state = 'approved'
        
        # Ensure all changes are synced to survey upon approval
        self._sync_to_survey()
        
        self.message_post(body=_('Approved by %s and changes synced to survey.') % self.env.user.name)
    
    def action_reject(self):
        """Reject objection (SDM action)"""
        self.ensure_one()
        
        # Check if user is SDM
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM can reject.'))
        
        # Validate state is draft
        if self.state != 'draft':
            raise ValidationError(_('Only draft records can be rejected.'))
        
        self.state = 'rejected'
        self.message_post(body=_('Rejected by %s') % self.env.user.name)
    
    def set_state_approved(self):
        """Set state to approved when clicking on approved status button"""
        self.ensure_one()
        # Allow going to approved from draft state
        if self.state == 'draft':
            # Check if user is SDM
            if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                    self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
                raise ValidationError(_('Only SDM can approve.'))
            # Resolution details is optional, no validation needed
            self.state = 'approved'
            self._sync_to_survey()
            self.message_post(body=_('Status changed to Approved by %s and changes synced to survey.') % self.env.user.name)
        elif self.state == 'approved':
            # Already in approved state
            pass
        else:
            raise ValidationError(_('Cannot change status to Approved from current state. Only draft records can be approved.'))
    
    def set_state_rejected(self):
        """Set state to rejected when clicking on rejected status button"""
        self.ensure_one()
        # Allow going to rejected from draft state
        if self.state == 'draft':
            # Check if user is SDM
            if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                    self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
                raise ValidationError(_('Only SDM can reject.'))
            self.state = 'rejected'
            self.message_post(body=_('Status changed to Rejected by %s') % self.env.user.name)
        elif self.state == 'rejected':
            # Already in rejected state
            pass
        else:
            raise ValidationError(_('Cannot change status to Rejected from current state. Only draft records can be rejected.'))
    
    def _validate_state_to_approved(self):
        """Validate transition to approved state"""
        self.ensure_one()
        # Allow going to approved from draft state
        if self.state != 'draft':
            raise ValidationError(_('Cannot change status to Approved from current state. Only draft records can be approved.'))
        # Check if user is SDM
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM can approve.'))
        # Resolution details is optional, no validation needed
    
    def _validate_state_to_rejected(self):
        """Validate transition to rejected state"""
        self.ensure_one()
        # Allow going to rejected from draft state
        if self.state != 'draft':
            raise ValidationError(_('Cannot change status to Rejected from current state. Only draft records can be rejected.'))
        # Check if user is SDM
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM can reject.'))
    
    def get_resolution_changes_summary(self):
        """Get summary of resolution changes for report"""
        self.ensure_one()
        changes = []
        
        # Check for removed landowners
        if self.original_landowner_ids and self.resolution_landowner_ids:
            removed = self.original_landowner_ids - self.resolution_landowner_ids
            if removed:
                removed_names = ', '.join(removed.mapped('name'))
                changes.append({
                    'type': 'landowner_removed',
                    'description': f'Removed landowners: {removed_names}',
                    'hindi_description': f'हटाए गए भूमिस्वामी: {removed_names}'
                })
        
        # Check for area decreases
        for khasra in self.resolution_khasra_ids:
            if khasra.resolved_acquired_area < khasra.original_acquired_area:
                decrease = khasra.original_acquired_area - khasra.resolved_acquired_area
                changes.append({
                    'type': 'area_decreased',
                    'khasra': khasra.survey_id.khasra_number or '',
                    'original_area': khasra.original_acquired_area,
                    'resolved_area': khasra.resolved_acquired_area,
                    'decrease': decrease,
                    'description': f'Khasra {khasra.survey_id.khasra_number}: Area decreased from {khasra.original_acquired_area:.4f} to {khasra.resolved_acquired_area:.4f} hectares',
                    'hindi_description': f'खसरा {khasra.survey_id.khasra_number}: क्षेत्रफल {khasra.original_acquired_area:.4f} से {khasra.resolved_acquired_area:.4f} हेक्टेयर तक कम किया गया'
                })
        
        return changes
    
    def unlink(self):
        """Remove objection from survey when deleted"""
        for record in self:
            if record.state == 'approved' and not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin') or self.env.user.has_group('base.group_system')):
                raise ValidationError(_('You cannot delete an approved objection. / आप स्वीकृत आपत्ति को हटा नहीं सकते।'))
        
        # Store survey_ids and objection_ids before deletion
        survey_objection_map = {}
        for record in self:
            if record.survey_id:
                if record.survey_id.id not in survey_objection_map:
                    survey_objection_map[record.survey_id.id] = []
                survey_objection_map[record.survey_id.id].append(record.id)
        
        result = super().unlink()
        
        # Remove from survey's objection list
        for survey_id, objection_ids in survey_objection_map.items():
            survey = self.env['bhu.survey'].browse(survey_id)
            if survey.exists():
                for objection_id in objection_ids:
                    survey.section15_objection_ids = [(3, objection_id)]
        
        return result


class Section15ObjectionKhasra(models.Model):
    """Model to track resolution changes per khasra (survey)"""
    _name = 'bhu.section15.objection.khasra'
    _description = 'Section 15 Objection Khasra Resolution'
    
    objection_id = fields.Many2one('bhu.section15.objection', string='Objection / आपत्ति', required=True, ondelete='cascade')
    survey_id = fields.Many2one('bhu.survey', string='Survey (Khasra) / सर्वे (खसरा)', required=True, 
                               ondelete='restrict')
    khasra_number = fields.Char(string='Khasra Number / खसरा नंबर', related='survey_id.khasra_number', readonly=True, store=True)
    original_acquired_area = fields.Float(string='Original Acquired Area (Hectares) / मूल अर्जन क्षेत्रफल (हेक्टेयर)', 
                                          digits=(10, 4), required=True, readonly=True)
    resolved_acquired_area = fields.Float(string='Resolved Acquired Area (Hectares) / समाधान अर्जन क्षेत्रफल (हेक्टेयर)', 
                                         digits=(10, 4), required=True,
                                         help='Enter the resolved acquired area. Must be less than or equal to original area.')
    
    # Other Survey Details for Editing
    has_well = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Has Well / कुआं है')
    well_count = fields.Integer(string='Well Count / कुआं संख्या')
    has_tubewell = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Has Tubewell / ट्यूबवेल है')
    tubewell_count = fields.Integer(string='Tubewell Count / ट्यूबवेल संख्या')
    has_house = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Has House / घर है')
    house_area = fields.Float(string='House Area / घर का क्षेत्रफल')
    has_shed = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Has Shed / शेड है')
    shed_area = fields.Float(string='Shed Area / शेड का क्षेत्रफल')
    has_pond = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Has Pond / तालाब है')
    irrigation_type = fields.Selection([
        ('irrigated', 'Irrigated / सिंचित'),
        ('unirrigated', 'Unirrigated / असिंचित'),
    ], string='Irrigation Type / सिंचाई का प्रकार')
    
    def unlink(self):
        """When a khasra line is deleted from the objection, mark the linked survey as rejected"""
        for record in self:
            if record.survey_id:
                # Mark linked survey as rejected
                record.survey_id.write({'state': 'rejected'})
                # Add a message to the survey's chatter
                record.survey_id.message_post(
                    body=_("Survey marked as REJECTED because it was deleted from Section 15 Objection: %s") % record.objection_id.name
                )
        return super().unlink()
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        
        # Set objection_id from context if available
        if 'default_objection_id' in self.env.context:
            objection_id = self.env.context.get('default_objection_id')
            if objection_id and 'objection_id' in fields_list:
                res['objection_id'] = objection_id
        
        # Try to get survey_id from context
        survey_id = self.env.context.get('default_survey_id')
        
        # If not in context, try to get from objection_id
        if not survey_id and 'default_objection_id' in self.env.context:
            objection_id = self.env.context.get('default_objection_id')
            if objection_id:
                objection = self.env['bhu.section15.objection'].browse(objection_id)
                if objection.exists() and objection.survey_id:
                    survey_id = objection.survey_id.id
        
        if survey_id:
            survey = self.env['bhu.survey'].browse(survey_id)
            if survey.exists():
                if 'survey_id' in fields_list:
                    res['survey_id'] = survey_id
                if 'original_acquired_area' in fields_list:
                    res['original_acquired_area'] = survey.acquired_area
                if 'resolved_acquired_area' in fields_list:
                    res['resolved_acquired_area'] = survey.acquired_area
                
                # Sync other details from survey
                res.update({
                    'has_well': survey.has_well,
                    'well_count': survey.well_count,
                    'has_tubewell': survey.has_tubewell,
                    'tubewell_count': survey.tubewell_count,
                    'has_house': survey.has_house,
                    'house_area': survey.house_area,
                    'has_shed': survey.has_shed,
                    'shed_area': survey.shed_area,
                    'has_pond': survey.has_pond,
                    'irrigation_type': survey.irrigation_type,
                })
        
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Ensure survey_id is set from objection if not provided"""
        # Set survey_id in vals_list before creation
        for vals in vals_list:
            if not vals.get('survey_id') and vals.get('objection_id'):
                objection = self.env['bhu.section15.objection'].browse(vals['objection_id'])
                if objection.exists() and objection.survey_id:
                    vals['survey_id'] = objection.survey_id.id
                    # Also set areas if not set
                    if not vals.get('original_acquired_area'):
                        vals['original_acquired_area'] = objection.survey_id.acquired_area
                    if not vals.get('resolved_acquired_area'):
                        vals['resolved_acquired_area'] = objection.survey_id.acquired_area
        
        records = super().create(vals_list)
        
        # After creation, ensure survey_id is set for any records that still don't have it
        for record in records:
            if not record.survey_id and record.objection_id and record.objection_id.survey_id:
                record.write({
                    'survey_id': record.objection_id.survey_id.id,
                    'original_acquired_area': record.objection_id.survey_id.acquired_area,
                    'resolved_acquired_area': record.objection_id.survey_id.acquired_area,
                })
            
            # Update survey's acquired_area when resolved_acquired_area is set
            if record.survey_id:
                survey_vals = {}
                if record.resolved_acquired_area and record.original_acquired_area and record.resolved_acquired_area <= record.original_acquired_area:
                    survey_vals['acquired_area'] = record.resolved_acquired_area
                
                # Update other survey details
                survey_vals.update({
                    'has_well': record.has_well,
                    'well_count': record.well_count,
                    'has_tubewell': record.has_tubewell,
                    'tubewell_count': record.tubewell_count,
                    'has_house': record.has_house,
                    'house_area': record.house_area,
                    'has_shed': record.has_shed,
                    'shed_area': record.shed_area,
                    'has_pond': record.has_pond,
                    'irrigation_type': record.irrigation_type,
                })
                record.survey_id.write(survey_vals)
        
        return records
    
    def write(self, vals):
        """Ensure survey_id is set from objection if not provided, and update survey's acquired_area when resolved_acquired_area changes"""
        # Fields that trigger a survey update
        sync_fields = [
            'resolved_acquired_area', 'has_well', 'well_count', 'has_tubewell', 
            'tubewell_count', 'has_house', 'house_area', 'has_shed', 'shed_area', 
            'has_pond', 'irrigation_type'
        ]
        
        # Track which records need survey update
        records_to_update = self.env[self._name]
        if any(f in vals for f in sync_fields):
            records_to_update = self
        
        result = super().write(vals)
        
        # After write, ensure survey_id is set for any records that don't have it
        for record in self:
            if not record.survey_id and record.objection_id and record.objection_id.survey_id:
                record.write({
                    'survey_id': record.objection_id.survey_id.id,
                    'original_acquired_area': record.objection_id.survey_id.acquired_area,
                })
                if not record.resolved_acquired_area or record.resolved_acquired_area > record.objection_id.survey_id.acquired_area:
                    record.write({'resolved_acquired_area': record.objection_id.survey_id.acquired_area})
        
        # Update linked surveys
        for record in records_to_update:
            if record.survey_id:
                record.survey_id.write({
                    'acquired_area': record.resolved_acquired_area,
                    'has_well': record.has_well,
                    'well_count': record.well_count,
                    'has_tubewell': record.has_tubewell,
                    'tubewell_count': record.tubewell_count,
                    'has_house': record.has_house,
                    'house_area': record.house_area,
                    'has_shed': record.has_shed,
                    'shed_area': record.shed_area,
                    'has_pond': record.has_pond,
                    'irrigation_type': record.irrigation_type,
                })
        
        return result
    
    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        """Update area fields when survey changes - ensure resolved area doesn't exceed original"""
        if self.survey_id:
            self.original_acquired_area = self.survey_id.acquired_area
            # If resolved area is greater than original, set it to original (can only decrease)
            if not self.resolved_acquired_area or self.resolved_acquired_area > self.survey_id.acquired_area:
                self.resolved_acquired_area = self.survey_id.acquired_area
    
    @api.onchange('resolved_acquired_area')
    def _onchange_resolved_acquired_area(self):
        """Ensure resolved area doesn't exceed original area - SDM can only decrease, not increase"""
        if self.original_acquired_area and self.resolved_acquired_area:
            if self.resolved_acquired_area > self.original_acquired_area:
                # Reset to original if user tries to increase
                self.resolved_acquired_area = self.original_acquired_area
                return {
                    'warning': {
                        'title': _('Area Cannot Be Increased'),
                        'message': _('You can only decrease the acquired area, not increase it. The resolved area has been set to the original area (%.4f hectares).') % self.original_acquired_area
                    }
                }
    
    @api.constrains('resolved_acquired_area', 'original_acquired_area')
    def _check_area_decrease(self):
        """Ensure resolved area is not greater than original - SDM can only decrease, not increase"""
        for record in self:
            if record.original_acquired_area and record.resolved_acquired_area:
                if record.resolved_acquired_area > record.original_acquired_area:
                    raise ValidationError(_('Resolved acquired area (%.4f hectares) cannot be greater than original area (%.4f hectares) for khasra %s. You can only decrease the area, not increase it.') % 
                                        (record.resolved_acquired_area, record.original_acquired_area, record.khasra_number or record.survey_id.khasra_number or ''))
    def action_open_reject_wizard(self):
        """Open the reject survey wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Survey / सर्वे अस्वीकार करें'),
            'res_model': 'bhu.reject.survey.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_objection_id': self.objection_id.id,
                'default_survey_id': self.survey_id.id,
            }
        }
