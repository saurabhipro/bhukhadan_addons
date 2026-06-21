# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime


class ProcessWorkflowMixin(models.AbstractModel):
    """Common workflow mixin for all process forms (SIA, Expert Committee, Section 4, 11, 19)"""
    _name = 'bhu.process.workflow.mixin'
    _description = 'Process Workflow Mixin'

    # Common workflow state
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('send_back', 'Sent Back'),
    ], string='Status', default='draft', tracking=True)
    
    # Date tracking
    submitted_date = fields.Datetime(string='Submitted Date / प्रस्तुत दिनांक', 
                                     readonly=True, tracking=True,
                                     help='Date when record was submitted to Collector')
    approved_date = fields.Datetime(string='Approved Date / अनुमोदित दिनांक', 
                                   readonly=True, tracking=True,
                                   help='Date when record was approved by Collector')
    
    # Days pending approval
    days_pending_approval = fields.Integer(string='Days Pending / लंबित दिन',
                                          compute='_compute_days_pending', store=False,
                                          help='Number of days record has been pending approval')
    
    # Pending with field - shows who the document is currently pending with (name + department + days)
    pending_with = fields.Char(string='Pending With / लंबित', compute='_compute_pending_with', store=False,
                                help='Shows who the document is currently pending with (name, department, and days pending)')

    # SDM signed file
    sdm_signed_file = fields.Binary(string='SDM Signed Document / SDM हस्ताक्षरित दस्तावेज़', 
                                    help='Upload the signed document from SDM')
    sdm_signed_filename = fields.Char(string='SDM Signed Filename')

    # Collector signed file
    collector_signed_file = fields.Binary(string='Collector Signed Document / कलेक्टर हस्ताक्षरित दस्तावेज़',
                                         help='Upload the signed document from Collector')
    collector_signed_filename = fields.Char(string='Collector Signed Filename')
    
    # Location fields - common across all process forms
    project_id = fields.Many2one(
        'bhu.project', 
        string='Project / परियोजना', 
        required=True,
        tracking=True, 
        ondelete='cascade',
        help='Project for which this process form is created'
    )
    
    village_id = fields.Many2one(
        'bhu.village', 
        string='Village / ग्राम', 
        required=True,
        tracking=True,
        help='Village where the land acquisition is taking place'
    )
    
    district_id = fields.Many2one(
        'bhu.district', 
        string='District / जिला', 
        compute='_compute_location', 
        store=True,
        help='District derived from selected village'
    )
    
    tehsil_id = fields.Many2one(
        'bhu.tehsil', 
        string='Tehsil / तहसील', 
        compute='_compute_location', 
        store=True,
        help='Tehsil derived from selected village'
    )
    
    # Computed fields for edit permissions
    is_sdm = fields.Boolean(string='Is SDM', compute='_compute_user_roles', store=False)
    is_collector = fields.Boolean(string='Is Collector', compute='_compute_user_roles', store=False)
    is_admin = fields.Boolean(string='Is Admin', compute='_compute_user_roles', store=False,
                              help='True if user is administrator or system user')
    is_approved_readonly = fields.Boolean(string='Is Approved Readonly', compute='_compute_approved_readonly', store=False,
                                          help='True when record is approved and should be readonly (except for admin)')
    can_sdm_edit = fields.Boolean(string='Can SDM Edit', compute='_compute_edit_permissions', store=False,
                                   help='SDM can edit when state is draft or send_back, readonly when approved')
    can_collector_edit = fields.Boolean(string='Can Collector Edit', compute='_compute_edit_permissions', store=False,
                                        help='Collector can edit when state is submitted, readonly when approved')
    
    @api.onchange('collector_signed_file')
    def _onchange_collector_signed_file(self):
        """Show popup message when Collector uploads their file"""
        if self.collector_signed_file and self.is_collector:
            return {
                'warning': {
                    'title': _('File Uploaded Successfully / फ़ाइल सफलतापूर्वक अपलोड की गई'),
                    'message': _('Please approve or reject this document using the Action buttons at the top. / कृपया शीर्ष पर एक्शन बटन का उपयोग करके इस दस्तावेज़ को स्वीकृत या अस्वीकृत करें।'),
                }
            }
    
    @api.depends('village_id', 'village_id.district_id', 'village_id.tehsil_id')
    def _compute_location(self):
        """Compute district and tehsil from village"""
        for record in self:
            if record.village_id:
                record.district_id = record.village_id.district_id
                record.tehsil_id = record.village_id.tehsil_id
            else:
                record.district_id = False
                record.tehsil_id = False
    
    @api.depends()
    def _compute_user_roles(self):
        """Compute if current user is SDM, Collector, or Admin"""
        current_user = self.env.user
        is_sdm_user = current_user.has_group('bhukhadan_core.group_bhuarjan_sdm')
        is_collector_user = current_user.has_group('bhukhadan_core.group_bhuarjan_collector')
        is_admin_user = current_user.has_group('bhukhadan_core.group_bhuarjan_admin') or current_user.has_group('base.group_system')
        
        for record in self:
            record.is_sdm = is_sdm_user
            record.is_collector = is_collector_user
            record.is_admin = is_admin_user
    
    @api.depends('state', 'is_admin')
    def _compute_approved_readonly(self):
        """Compute if record should be readonly when approved (except for admin)"""
        current_user = self.env.user
        is_admin_user = current_user.has_group('bhukhadan_core.group_bhuarjan_admin') or current_user.has_group('base.group_system')
        for record in self:
            # Record is readonly when approved, unless user is admin
            record.is_approved_readonly = record.state == 'approved' and not is_admin_user
    
    @api.depends('state', 'is_sdm', 'is_collector')
    def _compute_edit_permissions(self):
        """Compute edit permissions based on state and user role"""
        current_user = self.env.user
        is_sdm_user = current_user.has_group('bhukhadan_core.group_bhuarjan_sdm')
        is_collector_user = current_user.has_group('bhukhadan_core.group_bhuarjan_collector')
        is_admin_user = current_user.has_group('bhukhadan_core.group_bhuarjan_admin') or current_user.has_group('base.group_system')
        # Any user who is not exclusively a Collector can fill in draft/send_back records
        is_non_collector = not is_collector_user or is_admin_user
        
        for record in self:
            # For new records (no id), allow editing for anyone who is not purely a collector
            if not record.id:
                record.can_sdm_edit = is_non_collector
                record.can_collector_edit = False  # Collectors can't create new records
            else:
                # can_sdm_edit: True for SDM, Admin, or any non-collector user in draft/send_back
                record.can_sdm_edit = is_non_collector and record.state in ('draft', 'send_back')
                
                # Collector can edit when state is 'submitted', readonly when 'approved'
                record.can_collector_edit = (is_collector_user or is_admin_user) and record.state == 'submitted'

    def write(self, vals):
        """Override write to intercept state changes and validate them"""
        # Check if state is being changed
        if 'state' in vals:
            for record in self:
                old_state = record.state
                new_state = vals['state']
                
                # If state is changing, validate the transition
                if old_state != new_state:
                    # Build method name: _validate_state_to_<new_state>
                    method_name = f'_validate_state_to_{new_state}'
                    
                    # Check if validation method exists and call it
                    if hasattr(record, method_name):
                        method = getattr(record, method_name)
                        method()  # This will raise ValidationError if invalid
                    else:
                        # Fallback: validate basic transition rules
                        record._validate_state_transition(old_state, new_state)
                    
                    # Track dates when state changes
                    if new_state == 'submitted' and not record.submitted_date:
                        vals['submitted_date'] = fields.Datetime.now()
                    elif new_state == 'approved' and not record.approved_date:
                        vals['approved_date'] = fields.Datetime.now()
                    
                    # If validation passes, post message
                    record._post_state_change_message(old_state, new_state)
                    
                    # Create activities based on state transition
                    if new_state == 'submitted' and old_state == 'draft':
                        # SDM submitted to Collector
                        record._create_submission_activity()
                    elif new_state == 'send_back' and old_state == 'submitted':
                        # Collector sent back to SDM
                        record._create_send_back_activity()
                    elif new_state == 'approved':
                        # Mark related activities as done
                        record._mark_activities_done()
        
        return super().write(vals)
    
    def _validate_state_transition(self, old_state, new_state):
        """Validate state transitions"""
        valid_transitions = {
            'draft': ['submitted'],
            'submitted': ['approved', 'send_back'],
            'approved': [],
            'send_back': ['draft'],
        }
        
        if new_state not in valid_transitions.get(old_state, []):
            raise ValidationError(
                _('Invalid state transition from %s to %s') % (
                    dict(self._fields['state'].selection)[old_state],
                    dict(self._fields['state'].selection)[new_state]
                )
            )
    
    def _post_state_change_message(self, old_state, new_state):
        """Post a message when state changes"""
        state_labels = dict(self._fields['state'].selection)
        self.message_post(
            body=_('Status changed from %s to %s by %s') % (
                state_labels[old_state],
                state_labels[new_state],
                self.env.user.name
            ),
            subtype_xmlid='mail.mt_note'  # Internal note - no email notification
        )
    
    # Common workflow methods
    def action_submit(self):
        """Submit for approval by Collector (SDM action)"""
        self.ensure_one()
        
        # Check if user is SDM
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM can submit for approval.'))
        
        # Validate that SDM signed file is uploaded
        if not self.sdm_signed_file:
            raise ValidationError(_('Please upload the SDM signed document before submitting.'))
        
        self.state = 'submitted'
        self.submitted_date = fields.Datetime.now()
        self.message_post(body=_('Submitted for Collector approval by %s') % self.env.user.name, subtype_xmlid='mail.mt_note')
        
        # Create activity for Collector users
        self._create_submission_activity()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success / सफलता'),
                'message': _('Document Submitted Successfully to Collector / दस्तावेज कलेक्टर को सफलतापूर्वक प्रस्तुत किया गया'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_approve(self):
        """Approve (Collector action)"""
        self.ensure_one()
        
        # Check if user is Collector
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only Collector can approve.'))
        
        # Validate that Collector signed file is uploaded
        if not self.collector_signed_file:
            raise ValidationError(_('Please upload the Collector signed document before approving.'))
        
        # Validate state is submitted
        if self.state != 'submitted':
            raise ValidationError(_('Only submitted records can be approved.'))
        
        self.state = 'approved'
        self.approved_date = fields.Datetime.now()
        self.message_post(body=_('Approved by %s') % self.env.user.name, subtype_xmlid='mail.mt_note')
        
        # Create activity notification for SDM users
        self._create_approval_activity()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success / सफलता'),
                'message': _('Document Approved Successfully'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_send_back(self):
        """Open wizard to send back (Collector action)"""
        self.ensure_one()
        
        # Check if user is Collector
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only Collector can send back.'))
        
        # Validate state is submitted
        if self.state != 'submitted':
            raise ValidationError(_('Only submitted records can be sent back.'))
        
        # Open wizard - use model name to determine wizard model
        wizard_model = 'process.send.back.wizard'
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Back'),
            'res_model': wizard_model,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            }
        }
    
    def action_draft(self):
        """Reset to draft (only allowed when sent back) - allows SDM to resubmit"""
        self.ensure_one()
        
        # Only allow reset to draft if sent back
        if self.state != 'send_back':
            raise ValidationError(_('Only sent back records can be reset to draft for resubmission.'))
        
        self.state = 'draft'
        self.message_post(body=_('Reset to draft by %s for resubmission') % self.env.user.name, subtype_xmlid='mail.mt_note')
    
    # Validation methods for statusbar click handling (called from write)
    def _validate_state_to_draft(self):
        """Validate transition to draft state"""
        self.ensure_one()
        # Allow going back to draft only from send_back state
        if self.state != 'send_back':
            raise ValidationError(_('Cannot change status to Draft from current state. Only sent back records can be reset to draft.'))
    
    def _validate_state_to_submitted(self):
        """Validate transition to submitted state"""
        self.ensure_one()
        # Allow going to submitted from draft state
        if self.state != 'draft':
            raise ValidationError(_('Cannot change status to Submitted from current state. Only draft records can be submitted.'))
        # Check if user is SDM
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM can submit for approval.'))
        # Validate that SDM signed file is uploaded
        if not self.sdm_signed_file:
            raise ValidationError(_('Please upload the SDM signed document before submitting.'))
    
    def _validate_state_to_approved(self):
        """Validate transition to approved state"""
        self.ensure_one()
        # Allow going to approved from submitted state
        if self.state != 'submitted':
            raise ValidationError(_('Cannot change status to Approved from current state. Only submitted records can be approved.'))
        # Check if user is Collector
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only Collector can approve.'))
        # Validate that Collector signed file is uploaded
        if not self.collector_signed_file:
            raise ValidationError(_('Please upload the Collector signed document before approving.'))
    
    def _validate_state_to_send_back(self):
        """Validate transition to send_back state"""
        self.ensure_one()
        # Allow going to send_back from submitted state
        if self.state != 'submitted':
            raise ValidationError(_('Cannot change status to Sent Back from current state. Only submitted records can be sent back.'))
        # Check if user is Collector
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only Collector can send back.'))
        # Note: For send_back, we might want to open a wizard, but for statusbar clicks, we'll just validate
    
    # Methods for statusbar click handling (kept for backward compatibility)
    def set_state_draft(self):
        """Set state to draft when clicking on draft status button"""
        self.ensure_one()
        # Allow going back to draft only from send_back state
        if self.state == 'send_back':
            self.state = 'draft'
            self.message_post(body=_('Status changed to Draft by %s') % self.env.user.name, subtype_xmlid='mail.mt_note')
        else:
            raise ValidationError(_('Cannot change status to Draft from current state.'))
    
    def set_state_submitted(self):
        """Set state to submitted when clicking on submitted status button"""
        self.ensure_one()
        # Allow going to submitted from draft state
        if self.state == 'draft':
            # Check if user is SDM
            if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                    self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
                raise ValidationError(_('Only SDM can submit for approval.'))
            # Validate that SDM signed file is uploaded
            if not self.sdm_signed_file:
                raise ValidationError(_('Please upload the SDM signed document before submitting.'))
            self.state = 'submitted'
            self.submitted_date = fields.Datetime.now()
            self.message_post(body=_('Status changed to Submitted by %s') % self.env.user.name, subtype_xmlid='mail.mt_note')
            # Create activity for Collector users
            self._create_submission_activity()
        elif self.state == 'submitted':
            # Already in submitted state
            pass
        else:
            raise ValidationError(_('Cannot change status to Submitted from current state.'))
    
    def set_state_approved(self):
        """Set state to approved when clicking on approved status button"""
        self.ensure_one()
        # Allow going to approved from submitted state
        if self.state == 'submitted':
            # Check if user is Collector
            if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or 
                    self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
                raise ValidationError(_('Only Collector can approve.'))
            # Validate that Collector signed file is uploaded
            if not self.collector_signed_file:
                raise ValidationError(_('Please upload the Collector signed document before approving.'))
            self.state = 'approved'
            self.approved_date = fields.Datetime.now()
            self.message_post(body=_('Status changed to Approved by %s') % self.env.user.name, subtype_xmlid='mail.mt_note')
            # Mark activities as done
            self._mark_activities_done()
        elif self.state == 'approved':
            # Already in approved state
            pass
        else:
            raise ValidationError(_('Cannot change status to Approved from current state.'))
    
    def set_state_send_back(self):
        """Set state to send_back when clicking on send_back status button"""
        self.ensure_one()
        # Allow going to send_back from submitted state
        if self.state == 'submitted':
            # Check if user is Collector
            if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or 
                    self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
                raise ValidationError(_('Only Collector can send back.'))
            # Open wizard for send back
            return self.action_send_back()
        elif self.state == 'send_back':
            # Already in send_back state
            pass
        else:
            raise ValidationError(_('Cannot change status to Sent Back from current state.'))
    
    def action_download_unsigned_file(self):
        """Download unsigned document - to be overridden by each model"""
        self.ensure_one()
        raise ValidationError(_('This method must be overridden in the model.'))
    
    def action_download_sdm_signed_file(self):
        """Download SDM signed document"""
        self.ensure_one()
        if not self.sdm_signed_file:
            raise ValidationError(_('SDM signed document is not available.'))
        filename = self.sdm_signed_filename or 'sdm_signed_document.pdf'
        # Use model name with dots (Odoo's standard format for /web/content/)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/sdm_signed_file/{filename}?download=true',
            'target': 'self',
        }
    
    def action_download_collector_signed_file(self):
        """Download Collector signed document"""
        self.ensure_one()
        if not self.collector_signed_file:
            raise ValidationError(_('Collector signed document is not available.'))
        filename = self.collector_signed_filename or 'collector_signed_document.pdf'
        # Use model name with dots (Odoo's standard format for /web/content/)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/collector_signed_file/{filename}?download=true',
            'target': 'self',
        }
    
    def action_download_latest_pdf(self):
        """Download the latest available PDF (Collector's if available, otherwise SDM's, otherwise unsigned)"""
        self.ensure_one()
        # Priority: Collector signed > SDM signed > Unsigned
        if self.collector_signed_file:
            return self.action_download_collector_signed_file()
        elif self.sdm_signed_file:
            return self.action_download_sdm_signed_file()
        else:
            return self.action_download_unsigned_file()
    
    def action_delete_sdm_signed_file(self):
        """Delete SDM signed file"""
        self.ensure_one()
        if not self.sdm_signed_file:
            raise ValidationError(_('No SDM signed file to delete.'))
        
        if self.state not in ('draft', 'send_back'):
            raise ValidationError(_('Cannot delete SDM signed file in current state. Only allowed in Draft or Sent Back state.'))
        
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only SDM can delete SDM signed file.'))
        
        self.write({
            'sdm_signed_file': False,
            'sdm_signed_filename': False,
        })
        self.message_post(body=_('SDM signed file deleted by %s') % self.env.user.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('SDM signed file has been deleted. You can now upload a new file.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_delete_collector_signed_file(self):
        """Delete Collector signed file"""
        self.ensure_one()
        if not self.collector_signed_file:
            raise ValidationError(_('No Collector signed file to delete.'))
        
        if self.state != 'submitted':
            raise ValidationError(_('Cannot delete Collector signed file in current state. Only allowed in Submitted state.'))
        
        if not (self.env.user.has_group('bhukhadan_core.group_bhuarjan_collector') or 
                self.env.user.has_group('bhukhadan_core.group_bhuarjan_admin')):
            raise ValidationError(_('Only Collector can delete Collector signed file.'))
        
        self.write({
            'collector_signed_file': False,
            'collector_signed_filename': False,
        })
        self.message_post(body=_('Collector signed file deleted by %s') % self.env.user.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Collector signed file has been deleted. You can now upload a new file.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.depends('state', 'submitted_date')
    def _compute_days_pending(self):
        """Compute number of days pending approval"""
        for record in self:
            if record.state == 'submitted' and record.submitted_date:
                now = fields.Datetime.now()
                delta = now - record.submitted_date
                record.days_pending_approval = delta.days
            else:
                record.days_pending_approval = 0
    
    @api.depends('state', 'project_id', 'submitted_date', 'days_pending_approval')
    def _compute_pending_with(self):
        """Compute who the document is currently pending with (name + department + days)"""
        for record in self:
            if record.state == 'approved':
                # Hide when approved
                record.pending_with = ''
            elif record.state == 'submitted':
                # Pending with Collector - get collector name and department
                collector_users = self.env['res.users'].search([
                    ('groups_id', 'in', self.env.ref('bhukhadan_core.group_bhuarjan_collector').id)
                ], limit=1)
                if collector_users:
                    collector = collector_users[0]
                    collector_name = collector.name or 'Collector'
                    # Get department from user's company or project
                    department_name = ''
                    if hasattr(record, 'project_id') and record.project_id and record.project_id.department_id:
                        department_name = record.project_id.department_id.name or ''
                    elif collector.company_id:
                        # Try to get department from company
                        department_name = collector.company_id.name or ''
                    
                    days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                    if department_name:
                        record.pending_with = _('Collector: %s (%s)%s') % (collector_name, department_name, days_text)
                    else:
                        record.pending_with = _('Collector: %s%s') % (collector_name, days_text)
                else:
                    days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                    record.pending_with = _('Collector / कलेक्टर%s') % days_text
            elif record.state in ('draft', 'send_back'):
                # Pending with SDM - get SDM name and department from project
                if hasattr(record, 'project_id') and record.project_id and record.project_id.sdm_ids:
                    sdm_users = record.project_id.sdm_ids
                    sdm_names = []
                    department_name = ''
                    if record.project_id.department_id:
                        department_name = record.project_id.department_id.name or ''
                    
                    for sdm in sdm_users:
                        sdm_names.append(sdm.name or 'SDM')
                    
                    if sdm_names:
                        names_str = ', '.join(sdm_names)
                        days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                        if department_name:
                            record.pending_with = _('SDM: %s (%s)%s') % (names_str, department_name, days_text)
                        else:
                            record.pending_with = _('SDM: %s%s') % (names_str, days_text)
                    else:
                        days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                        record.pending_with = _('SDM / उप-विभागीय मजिस्ट्रेट%s') % days_text
                else:
                    days_text = f" ({record.days_pending_approval} day{'s' if record.days_pending_approval != 1 else ''})" if record.days_pending_approval > 0 else ""
                    record.pending_with = _('SDM / उप-विभागीय मजिस्ट्रेट%s') % days_text
            else:
                record.pending_with = ''
    
    def _create_submission_activity(self):
        """Create activity for Collector users when SDM submits"""
        self.ensure_one()
        
        # Get all Collector users
        collector_group = self.env.ref('bhukhadan_core.group_bhuarjan_collector', raise_if_not_found=False)
        if not collector_group:
            return
        
        collector_users = self.env['res.users'].search([
            ('groups_id', 'in', collector_group.id)
        ])
        
        if not collector_users:
            return
        
        # Get model display name
        model_name = self._name
        try:
            model_record = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            model_display_name = model_record.name if model_record else model_name
        except:
            model_display_name = model_name
        
        # Get record name for activity summary
        record_name = getattr(self, 'name', False) or getattr(self, 'notification_seq_number', False) or f"{model_display_name} #{self.id}"
        
        # Get project name
        project_name = getattr(self, 'project_id', False) and self.project_id.name or ''
        
        # Create activity for each Collector user
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            # Fallback: search for 'To Do' activity type
            activity_type = self.env['mail.activity.type'].search([('name', '=', 'To Do')], limit=1)
        
        if not activity_type:
            return
        
        # Get form view action to link activity
        form_view = self.env['ir.ui.view'].search([
            ('model', '=', model_name),
            ('type', '=', 'form')
        ], limit=1, order='priority desc, id desc')
        
        # Include project name in summary
        if project_name:
            activity_summary = _('%s - %s submitted for approval') % (project_name, record_name)
        else:
            activity_summary = _('%s submitted for approval') % record_name
        activity_note = _('Please review and approve: %s\n\nProject: %s') % (
            record_name,
            getattr(self, 'project_id', False) and self.project_id.name or 'N/A'
        )
        
        # Add village info if available
        if hasattr(self, 'village_id') and self.village_id:
            activity_note += _('\nVillage: %s') % self.village_id.name
        
        for collector_user in collector_users:
            # Check if activity already exists for this user and record
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', model_name),
                ('res_id', '=', self.id),
                ('user_id', '=', collector_user.id),
                ('activity_type_id', '=', activity_type.id),
                ('summary', '=', activity_summary),
            ], limit=1)
            
            if not existing_activity:
                # Create activity without sending email notification
                self.with_context(mail_activity_quick_update=True).activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=activity_summary,
                    note=activity_note,
                    user_id=collector_user.id,
                )
    
    def _create_send_back_activity(self):
        """Create activity for SDM users when Collector sends back"""
        self.ensure_one()
        
        # Get SDM users - try to get from project first
        sdm_users = self.env['res.users']
        
        if hasattr(self, 'project_id') and self.project_id and self.project_id.sdm_ids:
            sdm_users = self.project_id.sdm_ids
        else:
            # Fallback: get all SDM users
            sdm_group = self.env.ref('bhukhadan_core.group_bhuarjan_sdm', raise_if_not_found=False)
            if sdm_group:
                sdm_users = self.env['res.users'].search([
                    ('groups_id', 'in', sdm_group.id)
                ])
        
        if not sdm_users:
            return
        
        # Get model display name
        model_name = self._name
        try:
            model_record = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            model_display_name = model_record.name if model_record else model_name
        except:
            model_display_name = model_name
        
        # Get record name for activity summary
        record_name = getattr(self, 'name', False) or getattr(self, 'notification_seq_number', False) or f"{model_display_name} #{self.id}"
        
        # Get project name
        project_name = getattr(self, 'project_id', False) and self.project_id.name or ''
        
        # Create activity for each SDM user
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            # Fallback: search for 'To Do' activity type
            activity_type = self.env['mail.activity.type'].search([('name', '=', 'To Do')], limit=1)
        
        if not activity_type:
            return
        
        # Include project name in summary
        if project_name:
            activity_summary = _('%s - %s sent back for revision') % (project_name, record_name)
        else:
            activity_summary = _('%s sent back for revision') % record_name
        activity_note = _('Please review and resubmit: %s\n\nProject: %s') % (
            record_name,
            getattr(self, 'project_id', False) and self.project_id.name or 'N/A'
        )
        
        # Add village info if available
        if hasattr(self, 'village_id') and self.village_id:
            activity_note += _('\nVillage: %s') % self.village_id.name
        
        for sdm_user in sdm_users:
            # Check if activity already exists for this user and record
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', model_name),
                ('res_id', '=', self.id),
                ('user_id', '=', sdm_user.id),
                ('activity_type_id', '=', activity_type.id),
                ('summary', '=', activity_summary),
            ], limit=1)
            
            if not existing_activity:
                # Create activity without sending email notification
                self.with_context(mail_activity_quick_update=True).activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=activity_summary,
                    note=activity_note,
                    user_id=sdm_user.id,
                )
    
    def _create_approval_activity(self):
        """Create activity for SDM users when Collector approves"""
        self.ensure_one()
        
        # Get SDM users - try to get from project first
        sdm_users = self.env['res.users']
        
        if hasattr(self, 'project_id') and self.project_id and self.project_id.sdm_ids:
            sdm_users = self.project_id.sdm_ids
        else:
            # Fallback: get all SDM users
            sdm_group = self.env.ref('bhukhadan_core.group_bhuarjan_sdm', raise_if_not_found=False)
            if sdm_group:
                sdm_users = self.env['res.users'].search([
                    ('groups_id', 'in', sdm_group.id)
                ])
        
        if not sdm_users:
            return
        
        # Get model display name
        model_name = self._name
        try:
            model_record = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            model_display_name = model_record.name if model_record else model_name
        except:
            model_display_name = model_name
        
        # Get record name for activity summary
        record_name = getattr(self, 'name', False) or getattr(self, 'notification_seq_number', False) or f"{model_display_name} #{self.id}"
        
        # Get project name
        project_name = getattr(self, 'project_id', False) and self.project_id.name or ''
        
        # Create activity for each SDM user
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            # Fallback: search for 'To Do' activity type
            activity_type = self.env['mail.activity.type'].search([('name', '=', 'To Do')], limit=1)
        
        if not activity_type:
            return
        
        # Include project name in summary
        if project_name:
            activity_summary = _('%s - %s approved by Collector') % (project_name, record_name)
        else:
            activity_summary = _('%s approved by Collector') % record_name
        activity_note = _('The following has been approved: %s\n\nProject: %s\n\nApproved by: %s') % (
            record_name,
            getattr(self, 'project_id', False) and self.project_id.name or 'N/A',
            self.env.user.name
        )
        
        # Add village info if available
        if hasattr(self, 'village_id') and self.village_id:
            activity_note += _('\nVillage: %s') % self.village_id.name
        
        for sdm_user in sdm_users:
            # Check if activity already exists for this user and record
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', model_name),
                ('res_id', '=', self.id),
                ('user_id', '=', sdm_user.id),
                ('activity_type_id', '=', activity_type.id),
                ('summary', '=', activity_summary),
            ], limit=1)
            
            if not existing_activity:
                # Create activity without sending email notification
                self.with_context(mail_activity_quick_update=True).activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=activity_summary,
                    note=activity_note,
                    user_id=sdm_user.id,
                )
    
    def _mark_activities_done(self):
        """Mark all pending activities as done when record is approved"""
        self.ensure_one()
        
        # Get all pending activities for this record (activities without date_done are pending)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('date_done', '=', False),
        ])
        
        if activities:
            activities.action_done()

