# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import re
from html import unescape


def _selection_label(record, field_name):
    """Readable label for a selection value on ``record``."""
    val = getattr(record, field_name, False)
    if val is False or val is None:
        return ''
    field = record._fields.get(field_name)
    if not field or field.type != 'selection':
        return str(val)
    selection = field.selection
    if callable(selection):
        selection = selection(record)
    return dict(selection).get(val, val)

class Section8(models.Model):
    _name = 'bhu.section8'
    _description = 'Section 8'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Section 8 Reference / धारा 8 संदर्भ', required=True, tracking=True, default='New', readonly=True)
    order_kramank = fields.Char(
        string='आदेश क्रमांक / Order reference',
        tracking=True,
        copy=False,
        help='Official क्रमांक printed on धारा 8 आदेश PDF (e.g. LAND-43/214/2026). '
             'If empty, the system reference below is used on the PDF.',
    )
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', 
                                    related='project_id.department_id', 
                                    store=True, readonly=True, tracking=True,
                                    help='Department automatically derived from selected project')
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True, tracking=True, ondelete='cascade')
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', tracking=True)
    
    # Satisfaction fields
    is_satisfied = fields.Selection([
        ('yes', 'Yes / हाँ'),
        ('no', 'No / नहीं'),
    ], string='Are you satisfied? / क्या आप संतुष्ट हैं?', tracking=True)
    dissatisfaction_reason = fields.Text(string='Reason for Dissatisfaction / असंतुष्टि का कारण', tracking=True)
    
    # File upload (optional)
    attachment_file = fields.Binary(string='Attachment / अनुलग्नक', tracking=True)
    attachment_filename = fields.Char(string='Attachment Filename / अनुलग्नक फ़ाइल नाम', tracking=True)
    
    # State for Approve/Reject
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)
    
    # Approval/Rejection details
    approval_date = fields.Datetime(string='Approval Date / अनुमोदन दिनांक', readonly=True, tracking=True)
    approval_reason = fields.Text(string='Approval Reason / अनुमोदन का कारण', tracking=True)
    rejection_date = fields.Datetime(string='Rejection Date / अस्वीकृति दिनांक', readonly=True, tracking=True)
    rejection_reason = fields.Text(string='Rejection Reason / अस्वीकृति का कारण', tracking=True)
    
    # Notes
    notes = fields.Text(string='Notes / नोट्स', tracking=True)
    
    village_domain = fields.Char()
    project_domain = fields.Char()
    
    # Computed field to check if current user is SDM (for readonly)
    is_sdm_user = fields.Boolean(string='Is SDM User', compute='_compute_is_sdm_user', store=False)
    
    @api.depends()
    def _compute_is_sdm_user(self):
        """Compute if current user is SDM"""
        is_sdm = self.env.user.has_group('bhukhadan_core.group_bhuarjan_sdm')
        for rec in self:
            rec.is_sdm_user = is_sdm

    # --- PDF report helpers (QWeb Section 8 order; values come from stored records) ---

    def _report_format_datetime(self, dt_value):
        """Format datetime in current user's timezone for PDF."""
        if not dt_value:
            return ''
        localized = fields.Datetime.context_timestamp(self, dt_value)
        return localized.strftime('%d/%m/%Y %H:%M')

    def _report_selection_label(self, field_name):
        self.ensure_one()
        return _selection_label(self, field_name)

    def _report_project_subdivision_names(self):
        self.ensure_one()
        if not self.project_id:
            return ''
        return ', '.join(n for n in self.project_id.sub_division_id.mapped('name') if n)

    def _report_project_tehsil_names(self):
        self.ensure_one()
        if not self.project_id:
            return ''
        return ', '.join(n for n in self.project_id.tehsil_ids.mapped('name') if n)

    def _report_project_village_names(self):
        self.ensure_one()
        if not self.project_id:
            return ''
        names = sorted({n for n in self.project_id.village_ids.mapped('name') if n})
        return ', '.join(names)

    def _report_kramank_display(self):
        """क्रमांक shown on PDF — user-entered order number, else internal sequence ref."""
        self.ensure_one()
        return (self.order_kramank or self.name or '').strip()

    def _report_generated_timestamp_label(self):
        """Print timestamp when PDF is rendered (user timezone)."""
        now = fields.Datetime.now()
        localized = fields.Datetime.context_timestamp(self, now)
        return localized.strftime('%d/%m/%Y %H:%M')

    def _report_plain_text(self, html_blob):
        """Strip basic HTML from Text fields for PDF."""
        if not html_blob:
            return ''
        t = re.sub(r'<[^>]+>', ' ', str(html_blob))
        return unescape(' '.join(t.split())).strip()

    def _report_order_date_only(self):
        """Order date on letterhead (approval → write → create)."""
        self.ensure_one()
        dt = self.approval_date or self.write_date or self.create_date
        if not dt:
            return ''
        localized = fields.Datetime.context_timestamp(self, dt)
        return localized.strftime('%d/%m/%Y')

    def _report_district_name(self):
        self.ensure_one()
        if self.project_id and self.project_id.district_id:
            return (self.project_id.district_id.name or '').strip()
        return ''

    def _report_primary_village_name(self):
        self.ensure_one()
        if self.village_id and self.village_id.name:
            return self.village_id.name.strip()
        if self.project_id:
            names = sorted({n for n in self.project_id.village_ids.mapped('name') if n})
            return names[0] if names else ''
        return ''

    def _report_primary_tehsil_name(self):
        self.ensure_one()
        if self.village_id and self.village_id.tehsil_id:
            return (self.village_id.tehsil_id.name or '').strip()
        tehsils = self.project_id.tehsil_ids.mapped('name') if self.project_id else []
        return (tehsils[0] or '').strip() if tehsils else ''

    def _report_project_prose_for_order(self):
        """Project title + plain description for acquisition paragraph."""
        self.ensure_one()
        if not self.project_id:
            return ''
        name = (self.project_id.name or '').strip()
        desc = self._report_plain_text(self.project_id.description or '')
        if desc and desc != name:
            return f'{name}, {desc}' if name else desc
        return name or desc

    def _report_first_subdivision_name(self):
        self.ensure_one()
        if not self.project_id or not self.project_id.sub_division_id:
            return ''
        names = [n for n in self.project_id.sub_division_id.mapped('name') if n]
        return names[0].strip() if names else ''

    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and set domain"""
        for rec in self:
            if rec.project_id and rec.project_id.village_ids:
                rec.village_domain = json.dumps([('id', 'in', rec.project_id.village_ids.ids)])
            else:
                rec.village_domain = json.dumps([('id', 'in', [])])
                rec.village_id = False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate section 8 reference if not provided"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                # Try to use sequence settings from settings master
                project_id = vals.get('project_id')
                village_id = vals.get('village_id')
                if project_id:
                    sequence_number = self.env['bhuarjan.settings.master'].get_sequence_number(
                        'section8', project_id, village_id=village_id if village_id else None
                    )
                    if sequence_number:
                        vals['name'] = sequence_number
                    else:
                        # Fallback to ir.sequence
                        sequence = self.env['ir.sequence'].next_by_code('bhu.section8') or 'New'
                        vals['name'] = f'SEC8-{sequence}'
                else:
                    # No project_id, use fallback
                    sequence = self.env['ir.sequence'].next_by_code('bhu.section8') or 'New'
                    vals['name'] = f'SEC8-{sequence}'
        return super().create(vals_list)
    
    def action_approve(self):
        """Open wizard to approve Section 8"""
        self.ensure_one()
        if self.state == 'approved':
            raise ValidationError(_('Section 8 is already approved.'))
        
        wizard = self.env['bhu.section8.approve.reject.wizard'].create({
            'res_id': self.id,
            'action_type': 'approve',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approve Section 8'),
            'res_model': 'bhu.section8.approve.reject.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }
    
    def action_reject(self):
        """Open wizard to reject Section 8"""
        self.ensure_one()
        if self.state == 'rejected':
            raise ValidationError(_('Section 8 is already rejected.'))
        
        wizard = self.env['bhu.section8.approve.reject.wizard'].create({
            'res_id': self.id,
            'action_type': 'reject',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Section 8'),
            'res_model': 'bhu.section8.approve.reject.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }
    
    def action_download_sia_report(self):
        """Download SIA Report for the project"""
        self.ensure_one()
        if not self.project_id:
            raise ValidationError(_('Please select a project first.'))
        
        # Find SIA team for this project
        sia_team = self.env['bhu.sia.team'].search([
            ('project_id', '=', self.project_id.id)
        ], limit=1, order='create_date desc')
        
        if not sia_team:
            raise ValidationError(_('No SIA Team found for this project.'))
        
        # Download SIA Order (SDM's proposal) via generic wizard
        return {
            'name': _('Download SIA Team Report / SIA रिपोर्ट डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'bhu.sia.team',
                'default_res_id': sia_team.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_sia_order',
                'default_filename': f'SIA_Team_Report_{self.project_id.name}.doc'
            }
        }
    
    def action_download_expert_report(self):
        """Download Expert Committee Report for the project"""
        self.ensure_one()
        if not self.project_id:
            raise ValidationError(_('Please select a project first.'))
        
        # Find Expert Committee report for this project
        expert_report = self.env['bhu.expert.committee.report'].search([
            ('project_id', '=', self.project_id.id)
        ], limit=1, order='create_date desc')
        
        if not expert_report:
            raise ValidationError(_('No Expert Committee Report found for this project.'))
        
        # Download Expert Committee Order via generic wizard
        return {
            'name': _('Download Expert Group Report / विशेषज्ञ समिति रिपोर्ट डाउनलोड करें'),
            'type': 'ir.actions.act_window',
            'res_model': 'sia.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'bhu.expert.committee.report',
                'default_res_id': expert_report.id,
                'default_report_xml_id': 'bhukhadan_core.action_report_expert_committee_order',
                'default_filename': f'Expert_Group_Report_{self.project_id.name}.doc'
            }
        }

