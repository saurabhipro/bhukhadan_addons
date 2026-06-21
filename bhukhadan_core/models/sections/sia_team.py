# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import uuid

class SiaTeam(models.Model):
    _name = 'bhu.sia.team'
    _description = 'SIA Team'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bhu.process.workflow.mixin', 'bhu.qr.code.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'
    
    # _sql_constraints = [
    #     ('unique_project', 'UNIQUE(project_id)', 
    #      'Only one SIA Team can be created per project! / प्रति परियोजना केवल एक SIA टीम बनाई जा सकती है!')
    # ]

    name = fields.Char(string='Team Name / टीम का नाम', compute='_compute_name', store=True, readonly=True)
    
    # New fields
    sub_division_id = fields.Many2one('bhu.sub.division', string='Sub Division / उपभाग', required=False, tracking=True)
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    requiring_body_id = fields.Many2one('bhu.department', string='Requiring Body / अपेक्षक निकाय', required=True, tracking=True,
                                       help='Select the requiring body/department', related="project_id.department_id")
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=False, tracking=True)
    village_ids = fields.Many2many('bhu.village', string='Affected Villages / प्रभावित ग्राम', tracking=True,
                                   help='Affected villages for this SIA Team (auto-populated from project)')
    tehsil_ids = fields.Many2many('bhu.tehsil', string='Affected Tehsils / प्रभावित तहसीलें', compute='_compute_tehsil_ids', store=False, readonly=True,
                                  help='Tehsils from the selected villages')
    
    # SIA Exemption Selection (Yes/No)
    is_sia_exempt = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes')
    ], string='कि क्या इस परियोजना को सामाजिक समाघत अध्ययन से छूट प्राप्त है ?', 
      default='no', tracking=True,
      help='If Yes, this project is exempt from Social Impact Assessment. This will disable Section 4 and Expert Group for this project.')
    
    # SIA Team Members - One2many fields for each section
    # (क) Non-Government Social Scientist
    non_govt_social_scientist_line_ids = fields.One2many(
        'bhu.sia.team.member.line', 'sia_team_id',
        string='Non-Government Social Scientist / गैर शासकीय सामाजिक वैज्ञानिक',
        domain=[('member_type', '=', 'non_govt_social_scientist')],
        tracking=True)
    
    # (ख) Representatives of Local Bodies
    local_bodies_representative_line_ids = fields.One2many(
        'bhu.sia.team.member.line', 'sia_team_id',
        string='Representatives of Local Bodies / स्थानीय निकायों के प्रतिनिधि',
        domain=[('member_type', '=', 'local_bodies_representative')],
        tracking=True)
    
    # (ग) Resettlement Expert
    resettlement_expert_line_ids = fields.One2many(
        'bhu.sia.team.member.line', 'sia_team_id',
        string='Resettlement Expert / पुनर्व्यवस्थापन विशेषज्ञ',
        domain=[('member_type', '=', 'resettlement_expert')],
        tracking=True)
    
    # (घ) Technical Expert on Project Related Subject
    technical_expert_line_ids = fields.One2many(
        'bhu.sia.team.member.line', 'sia_team_id',
        string='Technical Expert / परियोजना से संबंधित विषय का तकनीकि विशेषज्ञ',
        domain=[('member_type', '=', 'technical_expert')],
        tracking=True)
    
    # Keep old Many2many fields for backward compatibility (hidden in view)
    non_govt_social_scientist_ids = fields.Many2many('bhu.sia.team.member', 
                                                     'sia_team_non_govt_social_scientist_rel',
                                                     'sia_team_id', 'member_id',
                                                     string='Non-Government Social Scientist (Old)',
                                                     tracking=True)
    local_bodies_representative_ids = fields.Many2many('bhu.sia.team.member',
                                                       'sia_team_local_bodies_rep_rel',
                                                       'sia_team_id', 'member_id',
                                                       string='Representatives of Local Bodies (Old)',
                                                       tracking=True)
    resettlement_expert_ids = fields.Many2many('bhu.sia.team.member',
                                                'sia_team_resettlement_expert_rel',
                                                'sia_team_id', 'member_id',
                                                string='Resettlement Expert (Old)',
                                                tracking=True)
    technical_expert_ids = fields.Many2many('bhu.sia.team.member',
                                            'sia_team_technical_expert_rel',
                                            'sia_team_id', 'member_id',
                                            string='Technical Expert (Old)',
                                            tracking=True)
    
    # (ड.) Tehsildar of Affected Area (Convener)
    tehsildar_id = fields.Many2one('res.users',
                                   string='Tehsildar (Convener) / प्रभावित क्षेत्र का तहसीलदार',
                                   tracking=True,
                                   help='Tehsildar of the affected area who will be the convener')
    
    # Documents
    sia_file = fields.Binary(string='SIA File / SIA फ़ाइल')
    sia_filename = fields.Char(string='SIA Filename')
    
    # SIA Team Report
    sia_team_report_file = fields.Binary(string='SIA Team Report / SIA टीम रिपोर्ट')
    sia_team_report_filename = fields.Char(string='SIA Team Report Filename')
    
    # UUID for QR code
    sia_team_uuid = fields.Char(string='SIA Team UUID', copy=False, readonly=True, index=True,
                                 help='Unique identifier for QR code download')
    
    # Kramank (Reference Number)
    kramank = fields.Char(string='Kramank / क्रमांक', required=False, tracking=True,
                          help='Reference number to be displayed in the report (optional)')
    
    # Legacy fields (kept for backward compatibility)
    team_member_ids = fields.Many2many('bhu.sia.team.member', string='Team Members / टीम सदस्य', 
                                      compute='_compute_team_members', store=False)
    
    # Computed fields from Form 10 surveys
    total_khasras_count = fields.Integer(string='Total Khasras Count / कुल खसरा संख्या',
                                         compute='_compute_project_statistics', store=False)
    total_area_acquired = fields.Float(string='Total Area Acquired (Hectares) / कुल अर्जित क्षेत्रफल (हेक्टेयर)',
                                       compute='_compute_project_statistics', store=False,
                                       digits=(16, 4))
    
    # Project villages for reference (read-only)
    project_village_ids = fields.Many2many('bhu.village', 
                                           string='Project Villages / परियोजना ग्राम', 
                                           compute='_compute_project_villages', 
                                           store=False,
                                           help='Villages mapped to the selected project (read-only for reference)')
    
    def read(self, fields=None, load='_classic_read'):
        """Override read to convert old Boolean values to Selection values"""
        result = super().read(fields=fields, load=load)
        
        # Convert any old Boolean values to Selection values
        # Check if is_sia_exempt field is requested or if all fields are requested
        requested_fields = fields if fields else []
        if not fields or 'is_sia_exempt' in requested_fields:
            for record_data in result:
                if 'is_sia_exempt' in record_data:
                    value = record_data['is_sia_exempt']
                    # If value is Boolean True/False, convert to 'yes'/'no'
                    if isinstance(value, bool):
                        record_data['is_sia_exempt'] = 'yes' if value else 'no'
                    elif value not in ('yes', 'no', False, None, ''):
                        # Handle other unexpected values (strings, numbers, etc.)
                        if str(value).lower() in ('true', 't', '1', 'yes'):
                            record_data['is_sia_exempt'] = 'yes'
                        else:
                            record_data['is_sia_exempt'] = 'no'
                    elif value is None or value == '':
                        record_data['is_sia_exempt'] = 'no'
        
        return result
    
    def action_bottom_save(self):
        self.ensure_one()
        if self.id:
            return True   # record already stored; form view auto-saves
        else:
            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.create(self.read()[0]).id,
                "view_mode": "form",
            }


    @api.depends('village_ids', 'village_ids.tehsil_id')
    def _compute_tehsil_ids(self):
        """Compute tehsils from selected villages"""
        for record in self:
            if record.village_ids:
                tehsils = record.village_ids.mapped('tehsil_id').filtered(lambda t: t)
                record.tehsil_ids = tehsils
            else:
                record.tehsil_ids = False
    
    @api.depends('project_id', 'project_id.village_ids', 'village_ids')
    def _compute_project_villages(self):
        """Compute villages - show selected villages if any, otherwise show all project villages"""
        for record in self:
            if record.village_ids:
                # Show only selected villages
                record.project_village_ids = record.village_ids
            elif record.project_id and record.project_id.village_ids:
                # If no villages selected, show all project villages
                record.project_village_ids = record.project_id.village_ids
            else:
                record.project_village_ids = False
    
    @api.depends('project_id', 'project_id.village_ids', 'village_ids')
    def _compute_project_statistics(self):
        """Compute total khasras count and total area acquired from Form 10 surveys"""
        for record in self:
            if record.project_id:
                # If specific villages are selected, use those; otherwise use all project villages
                village_ids = record.village_ids.ids if record.village_ids else record.project_id.village_ids.ids
                
                if village_ids:
                    # Get all surveys for selected villages in this project
                    surveys = self.env['bhu.survey'].search([
                        ('project_id', '=', record.project_id.id),
                        ('village_id', 'in', village_ids),
                        ('khasra_number', '!=', False),
                    ])
                    
                    # Count unique khasra numbers
                    unique_khasras = set(surveys.mapped('khasra_number'))
                    record.total_khasras_count = len(unique_khasras)
                    
                    # Sum acquired area
                    record.total_area_acquired = sum(surveys.mapped('acquired_area'))
                else:
                    record.total_khasras_count = 0
                    record.total_area_acquired = 0.0
            else:
                record.total_khasras_count = 0
                record.total_area_acquired = 0.0
    tehsildar_domain = fields.Char()
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Auto-set tehsildar and villages based on project selection"""
        # Reset tehsildar when project changes
        for rec in self:
            if rec.project_id:
                rec.tehsildar_id = rec.project_id.tehsildar_ids[:1].id or False
                rec.tehsildar_domain = json.dumps([('id', 'in', rec.project_id.tehsildar_ids.ids)])
                
            else:
                rec.tehsildar_id = False
                rec.tehsildar_domain = False
        self.tehsildar_id = False

        
        
        # Auto-populate villages with all project villages only on new records or when project changes
        if not self._origin or (self._origin and self._origin.project_id != self.project_id):
            if self.project_id and self.project_id.village_ids:
                self.village_ids = self.project_id.village_ids
            else:
                self.village_ids = False
        
        domain_updates = {}
        
        if self.project_id and self.project_id.tehsildar_ids:
            # Get Tehsildar user IDs from the project
            tehsildar_user_ids = self.project_id.tehsildar_ids.ids
            
            # Find SIA Team Members that are linked to the project's Tehsildars
            sia_team_members = self.env['bhu.sia.team.member'].search([
                ('user_id', 'in', tehsildar_user_ids)
            ])
            
            # Auto-set if matches found
            if len(sia_team_members) == 1:
                self.tehsildar_id = sia_team_members[0]
            elif len(sia_team_members) > 1:
                # If multiple matches, set the first one (user can change if needed)
                self.tehsildar_id = sia_team_members[0]
            
            # Set domain to only show SIA Team Members linked to project's Tehsildars
            domain_updates['tehsildar_id'] = [('user_id', 'in', tehsildar_user_ids)]
        else:
            # If no project or no Tehsildars, restrict to empty (user must select project first)
            domain_updates['tehsildar_id'] = [('id', '=', False)]
        
        # Set domain for villages to only show project villages
        if self.project_id and self.project_id.village_ids:
            village_ids = self.project_id.village_ids.ids
            domain_updates['village_ids'] = [('id', 'in', village_ids)]
        else:
            domain_updates['village_ids'] = [('id', '=', False)]
        
        return {'domain': domain_updates}
    
    @api.model
    def _get_project_domain(self):
        """Get domain for project_id based on user role"""
        user = self.env.user
        # Admin and system users can see all projects
        if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
            return []
        # SDM users can only see projects where they are assigned
        if user.has_group('bhukhadan_core.group_bhuarjan_sdm'):
            return [('sdm_ids', 'in', [user.id])]
        # For other users, return empty domain (they shouldn't be creating SIA teams)
        return []
    
    # SQL constraint removed to allow multiple teams per project
    # _sql_constraints = [
    #     ('unique_project', 'UNIQUE(project_id)', 
    #      'Only one SIA Team can be created per project! / प्रति परियोजना केवल एक SIA टीम बनाई जा सकती है!')
    # ]
    
    @api.constrains('project_id', 'village_ids')
    def _check_project_village_uniqueness(self):
        """Ensure no overlapping villages for the same project"""
        for record in self:
            if not record.project_id or not record.village_ids:
                continue
            
            # This team covers specific villages. Check if any of these villages are already covered.
            domain = [
                ('project_id', '=', record.project_id.id),
                ('id', '!=', record.id)
            ]
            existing_teams = self.search(domain)
            
            for existing in existing_teams:
                # If existing team has no villages, skip it (allow overlap with "full project" teams)
                if not existing.village_ids:
                    continue
                
                # Check for overlap
                overlap = set(record.village_ids.ids) & set(existing.village_ids.ids)
                if overlap:
                    overlapping_villages = self.env['bhu.village'].browse(list(overlap))
                    names = ', '.join(overlapping_villages.mapped('name'))
                    raise ValidationError(_('A SIA Team already exists for the following village(s): %s') % names)
    
    @api.constrains('project_id')
    def _check_sdm_project_assignment(self):
        """Ensure SDM users can only create SIA teams for projects they're assigned to"""
        user = self.env.user
        # Skip validation for admin/system users
        if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
            return
        
        # For SDM users, check if they're assigned to the project
        if user.has_group('bhukhadan_core.group_bhuarjan_sdm'):
            for record in self:
                if record.project_id and record.project_id.sdm_ids:
                    if user.id not in record.project_id.sdm_ids.ids:
                        raise ValidationError(
                            _('You are not assigned as SDM to project "%s". Please select a project where you are assigned as SDM.') %
                            record.project_id.name
                        )
    
    @api.constrains('village_ids', 'project_id')
    def _check_villages_belong_to_project(self):
        """Ensure selected villages belong to the project"""
        for record in self:
            if record.village_ids and record.project_id:
                invalid_villages = record.village_ids.filtered(
                    lambda v: v not in record.project_id.village_ids
                )
                if invalid_villages:
                    raise ValidationError(
                        _('The following villages do not belong to the selected project: %s') %
                        ', '.join(invalid_villages.mapped('name'))
                    )
    
    # Removed validation - Team members are now added via One2many after saving the record
    # @api.constrains('non_govt_social_scientist_ids', 'local_bodies_representative_ids', 
    #                 'resettlement_expert_ids', 'technical_expert_ids', 'tehsildar_id')
    # def _check_all_team_members_filled(self):
    #     """Validate that all team member sections are filled - Skip if SIA is exempt"""
    #     pass
    
    @api.depends('project_id')
    def _compute_name(self):
        """Generate team name from project"""
        for record in self:
            if record.project_id:
                sequence = self.env['ir.sequence'].next_by_code('bhu.sia.team') or 'New'
                record.name = f'SIA-{sequence}'
            else:
                record.name = 'New'
    
    @api.depends('non_govt_social_scientist_ids', 'local_bodies_representative_ids', 
                 'resettlement_expert_ids', 'technical_expert_ids', 'tehsildar_id')
    def _compute_team_members(self):
        """Compute all team members from all sections"""
        for record in self:
            all_members = record.non_govt_social_scientist_ids
            all_members |= record.local_bodies_representative_ids
            all_members |= record.resettlement_expert_ids
            all_members |= record.technical_expert_ids
            if record.tehsildar_id:
                all_members |= record.tehsildar_id
            record.team_member_ids = all_members
    
    @api.onchange('is_sia_exempt')
    def _onchange_is_sia_exempt(self):
        """Show confirmation when SIA exemption is changed from No to Yes"""
        # Get the previous value from the record if it exists, otherwise default to 'no'
        if self.id:
            # Record exists - read the current value from database
            current_record = self.browse(self.id)
            previous_value = current_record.is_sia_exempt or 'no'
        else:
            # New record - check if there's a previous value in context, otherwise default to 'no'
            previous_value = self.env.context.get('previous_is_sia_exempt', 'no')
        
        # Show confirmation only when changing from No to Yes
        if previous_value == 'no' and self.is_sia_exempt == 'yes':
            # Show warning confirmation - user can still change back to No before saving
            return {
                'warning': {
                    'title': _('SIA Exemption Confirmation'),
                    'message': _('This will disable Section 4 and Expert Group for this project. The SIA will be auto-approved when you save. You can change it back to "No" before saving if needed. Do you want to continue?')
                }
            }
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set project exemption status and auto-approve if exempt"""
        now = fields.Datetime.now()
        for vals in vals_list:
            # If is_sia_exempt is 'yes', auto-approve
            if vals.get('is_sia_exempt') == 'yes' and vals.get('state', 'draft') == 'draft':
                vals['state'] = 'approved'
                vals['approved_date'] = now

        records = super().create(vals_list)

        for record in records:
            # Update project exemption status
            if record.is_sia_exempt == 'yes' and record.project_id:
                record.project_id.write({'is_sia_exempt': True})

            # Post message if auto-approved
            if record.is_sia_exempt == 'yes' and record.state == 'approved':
                record.message_post(
                    body=_('SIA Team auto-approved (SIA Exempt) by %s') % self.env.user.name,
                    subtype_xmlid='mail.mt_note'
                )

        return records
    
    def _validate_state_transition(self, old_state, new_state):
        """Override to allow direct transition from draft to approved when SIA is exempt"""
        # Allow direct transition from draft to approved if SIA is exempt
        if old_state == 'draft' and new_state == 'approved' and self.is_sia_exempt == 'yes':
            return  # Skip validation for exempt projects
        # For all other cases, use parent validation
        return super()._validate_state_transition(old_state, new_state)
    
    def _validate_state_to_approved(self):
        """Override to allow direct approval from draft when SIA is exempt"""
        # Allow direct approval from draft if SIA is exempt
        # Check context flag first (set during write when exemption is being set)
        if self.env.context.get('sia_exempt_auto_approve', False) and self.state == 'draft':
            # Skip all validation for exempt projects (no collector check, no file check)
            return
        # Also check if already exempt (for cases where exemption was set earlier)
        if getattr(self, 'is_sia_exempt', 'no') == 'yes' and self.state == 'draft':
            # Skip all validation for exempt projects
            return
        # For all other cases, use parent validation
        return super()._validate_state_to_approved()
    
    def write(self, vals):
        """Override write to update project exemption status and auto-approve if exempt"""
        # Check if is_sia_exempt is being set to 'yes'
        if 'is_sia_exempt' in vals and vals.get('is_sia_exempt') == 'yes' and self.state == 'draft':
            # Auto-approve when exemption is set to 'yes' in draft state
            vals['state'] = 'approved'
            vals['approved_date'] = fields.Datetime.now()
            # Set context flag to bypass validation - DO NOT set field directly to avoid recursion
            self = self.with_context(sia_exempt_auto_approve=True)
        
        result = super().write(vals)
        
        # Update project exemption status
        if 'is_sia_exempt' in vals and self.project_id:
            # Convert 'yes'/'no' to boolean for project
            self.project_id.write({'is_sia_exempt': vals['is_sia_exempt'] == 'yes'})
        
        # Post message if auto-approved
        if 'is_sia_exempt' in vals and vals.get('is_sia_exempt') == 'yes' and 'state' in vals and vals.get('state') == 'approved':
            self.message_post(
                body=_('SIA Team auto-approved (SIA Exempt) by %s') % self.env.user.name,
                subtype_xmlid='mail.mt_note'
            )
        
        return result
    
    # Workflow Actions - Override mixin methods for SIA-specific validations
    def action_submit(self):
        """Submit SIA Team for approval by Collector (SDM action) - Override mixin"""
        self.ensure_one()
        
        # If SIA is exempt, auto-approve at SDM level
        if self.is_sia_exempt == 'yes':
            # Skip team member validation for exempt projects
            # Auto-approve directly
            self.state = 'approved'
            self.approved_date = fields.Datetime.now()
            self.message_post(
                body=_('SIA Team auto-approved (SIA Exempt) by %s') % self.env.user.name,
                subtype_xmlid='mail.mt_note'
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('SIA Team has been auto-approved as the project is exempt from Social Impact Assessment.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        # Call parent mixin method
        return super().action_submit()
    
    # Document Actions
    def action_download_unsigned_file(self):
        """Generate and download SIA Order Report PDF (unsigned) - Override mixin"""
        self.ensure_one()
        # SDM downloads the order report (SDM's proposal to Collector)
        return self.env.ref('bhukhadan_core.action_report_sia_order').report_action(self)
    
    def action_download_sia_file(self):
        """Alias for action_download_unsigned_file - for backward compatibility with views"""
        return self.action_download_unsigned_file()
    
    def action_download_proposal_report(self):
        """Open wizard to select download format for SIA Proposal Report"""
        self.ensure_one()
        # Open wizard to choose download format (PDF or Word)
        return {
            'name': _('Download SIA Proposal / SIA प्रस्ताव डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_sia_proposal',
                'default_filename': f'SIA_Proposal_{self.kramank or self.name}.doc'
            }
        }
    
    def action_download_sia_order(self):
        """Generate and download SIA Order Report PDF (SDM's Proposal) - For Collector"""
        self.ensure_one()
        return {
            'name': _('Download SIA Order / SIA आदेश डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_sia_order',
                'default_filename': f'SIA_Order_{self.kramank or self.name}.doc'
            }
        }
    
    def action_download_latest_pdf(self):
        """Download the latest available PDF - Override mixin to use proposal report for Collector"""
        self.ensure_one()
        user = self.env.user
        # Priority: Collector signed > SDM signed > Unsigned
        # For unsigned, Collector gets proposal report, others get order report
        if self.collector_signed_file:
            return self.action_download_collector_signed_file()
        elif self.sdm_signed_file:
            return self.action_download_sdm_signed_file()
        else:
            # If Collector, download proposal report (Collector's order template)
            # Otherwise, download order report (SDM's proposal)
            if user.has_group('bhukhadan_core.group_bhuarjan_collector'):
                return self.action_download_proposal_report()
            else:
                return self.action_download_unsigned_file()
    
    def action_download_sia_team_report(self):
        """Download SIA Team Report file"""
        self.ensure_one()
        if not self.sia_team_report_file:
            raise ValidationError(_('SIA Team Report file is not available.'))
        filename = self.sia_team_report_filename or 'sia_team_report.pdf'
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/sia_team_report_file/{filename}?download=true',
            'target': 'self',
        }
    
    def action_create_section4_notification(self):
        """Create Section 4 Notifications for all villages in this SIA Team"""
        self.ensure_one()
        
        # Check if project is SIA exempt
        if self.is_sia_exempt == 'yes' or (self.project_id and self.project_id.is_sia_exempt):
            raise ValidationError(_('Section 4 Notifications cannot be created for projects that are exempt from Social Impact Assessment.'))
        
        if not self.project_id:
            raise ValidationError(_('Please select a project first.'))
        
        if not self.project_id.department_id:
            raise ValidationError(_('Project must have a department/requiring body assigned.'))
        
        if not self.village_ids:
            raise ValidationError(_('Please select at least one village first.'))
        
        # Create Section 4 Notifications for each village
        created_notifications = []
        skipped_villages = []
        
        for village in self.village_ids:
            # Check if notification already exists for this village and project
            existing = self.env['bhu.section4.notification'].search([
                ('project_id', '=', self.project_id.id),
                ('village_id', '=', village.id)
            ], limit=1)
            
            if existing:
                skipped_villages.append(village.name)
                continue
            
            # Check if surveys exist for this village
            surveys = self.env['bhu.survey'].search([
                ('project_id', '=', self.project_id.id),
                ('village_id', '=', village.id)
            ])
            
            if not surveys:
                skipped_villages.append(f"{village.name} (no surveys)")
                continue
            
            # Create notification (requiring_body_id will be auto-populated from project)
            notification = self.env['bhu.section4.notification'].create({
                'project_id': self.project_id.id,
                'village_id': village.id,
            })
            created_notifications.append(notification)
        
        if created_notifications:
            # Add message to SIA Team record about created notifications
            if skipped_villages:
                message = _('Created %d Section 4 Notification(s) from this SIA Team. Skipped villages: %s') % (
                    len(created_notifications),
                    ', '.join(skipped_villages)
                )
            else:
                message = _('Created %d Section 4 Notification(s) from this SIA Team.') % len(created_notifications)
            
            self.message_post(body=message, subtype_xmlid='mail.mt_note')
            
            # Open the first created notification in form view
            return {
                'type': 'ir.actions.act_window',
                'name': _('Section 4 Notifications'),
                'res_model': 'bhu.section4.notification',
                'res_id': created_notifications[0].id if len(created_notifications) == 1 else False,
                'view_mode': 'form' if len(created_notifications) == 1 else 'list,form',
                'domain': [('id', 'in', [n.id for n in created_notifications])] if len(created_notifications) > 1 else [],
                'target': 'current',
                'context': {
                    'default_project_id': self.project_id.id,
                    # requiring_body_id will be auto-populated from project
                }
            }
        else:
            # Show error if no notifications were created
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('No notifications were created. All villages either already have notifications or have no surveys.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }
    
    @api.model
    def _generate_missing_uuids(self):
        """Generate UUIDs for existing SIA teams that don't have one"""
        teams_without_uuid = self.search([('sia_team_uuid', '=', False)])
        for team in teams_without_uuid:
            team.write({'sia_team_uuid': str(uuid.uuid4())})
        return len(teams_without_uuid)
    
    # QR code generation is now handled by bhu.qr.code.mixin

