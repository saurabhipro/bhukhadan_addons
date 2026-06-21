# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import re


class BhuLandowner(models.Model):
    _name = 'bhu.landowner'
    _description = 'Landowner'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    # Basic Information
    name = fields.Char(string='Full Name / पूरा नाम', required=True, tracking=True)
    father_name = fields.Char(string="Father's Name / पिता का नाम", tracking=True)
    mother_name = fields.Char(string="Mother's Name / माता का नाम", tracking=True)
    spouse_name = fields.Char(string="Spouse's Name / पति/पत्नी का नाम", tracking=True)
    
    # Contact Information
    phone = fields.Char(string='Phone Number / फोन नंबर', tracking=True)
    
    # Company/Organization Information
    company_id = fields.Many2one('res.company', string='Company / कंपनी', required=True, 
                                 default=lambda self: self.env.company, tracking=True)
    
    # Address Information
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=False, tracking=True)
    tehsil_id = fields.Many2one('bhu.tehsil', string='Tehsil / तहसील', tracking=True)
    district_id = fields.Many2one('bhu.district', string='District / जिला', tracking=True)
    state = fields.Char(string='State / राज्य', default='Chhattisgarh', readonly=True)
    owner_address = fields.Text(string='Owner Address / मालिक का पता', tracking=True,
                                help='Complete address of the landowner')
    
    # Identity Documents
    aadhar_number = fields.Char(string='Aadhar Number / आधार नंबर', tracking=True)
    pan_number = fields.Char(string='PAN Number / पैन नंबर', tracking=True)
    
    # Bank Details
    bank_name = fields.Char(string='Bank Name / बैंक का नाम', tracking=True)
    bank_branch = fields.Char(string='Bank Branch / बैंक शाखा', tracking=True)
    account_number = fields.Char(string='Account Number / खाता संख्या', tracking=True)
    ifsc_code = fields.Char(string='IFSC Code / आईएफएससी कोड', tracking=True)
    account_holder_name = fields.Char(string='Account Holder Name / खाताधारक का नाम', tracking=True)
    
    # Documents
    aadhar_card = fields.Binary(string='Aadhar Card / आधार कार्ड')
    pan_card = fields.Binary(string='PAN Card / पैन कार्ड')
    
    survey_ids = fields.Many2many('bhu.survey', 'bhu_survey_landowner_rel', 
                                 'landowner_id', 'survey_id', string='Related Surveys / संबंधित सर्वे')
    
    # Payment Status Tracking
    payment_status_ids = fields.One2many('bhu.landowner.payment.status', 'landowner_id', 
                                        string='Payment Status / भुगतान की स्थिति')
    
    # Validation Methods removed - no validations for aadhar, pan, account_number
    
    # Auto-fill methods
    @api.onchange('village_id')
    def _onchange_village_id(self):
        if self.village_id:
            self.tehsil_id = self.village_id.tehsil_id
            self.district_id = self.village_id.district_id
    
    @api.onchange('tehsil_id')
    def _onchange_tehsil_id(self):
        if self.tehsil_id:
            self.district_id = self.tehsil_id.district_id
    
    def action_view_surveys(self):
        """Action to view related surveys"""
        action = self.env.ref('bhukhadan_core.action_bhu_survey').read()[0]
        action['domain'] = [('landowner_ids', 'in', self.ids)]
        action['context'] = {'default_landowner_ids': [(6, 0, self.ids)]}
        return action

    @api.model
    def _search(self, args, offset=0, limit=None, order=None):
        """Override search to apply role-based filtering"""
        user = self.env.user
        
        # Admin sees everything - no filter
        if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
            return super(BhuLandowner, self)._search(args, offset=offset, limit=limit, order=order)

        # SDM / Tehsildar: record rules (district OR surveys on assigned projects) must apply; a blanket
        # district_id filter here would block landowners tied to their projects when district_id is
        # unset or out of sync with res.users.district_id.
        if user.has_group('bhukhadan_core.group_bhuarjan_sdm') or user.has_group('bhukhadan_core.group_bhuarjan_tahsildar'):
            return super(BhuLandowner, self)._search(args, offset=offset, limit=limit, order=order)
            
        # For all other users, restrict to their assigned district if they have one
        if user.district_id:
            args = [('district_id', '=', user.district_id.id)] + args
            
        # Apply additional Patwari-specific filtering
        if user.bhuarjan_role == 'patwari':
            # Patwari can only see landowners from their assigned villages
            # and landowners who are in surveys they created
            patwari_domain = [
                '|',
                ('village_id.user_id', '=', user.id),
                ('survey_ids.user_id', '=', user.id),
            ]
            args = patwari_domain + args
        
        return super(BhuLandowner, self)._search(args, offset=offset, limit=limit, order=order)
    
    def unlink(self):
        """Override unlink to handle survey relationships properly
        
        When a landowner is deleted:
        - The Many2many links to surveys are automatically removed by Odoo
        - Surveys themselves are NOT deleted (only the relationship is removed)
        - We warn the user if there are approved/submitted surveys
        """
        for landowner in self:
            # Check if landowner has linked surveys
            if landowner.survey_ids:
                survey_count = len(landowner.survey_ids)
                # Get survey states for warning
                approved_surveys = landowner.survey_ids.filtered(lambda s: s.state == 'approved')
                submitted_surveys = landowner.survey_ids.filtered(lambda s: s.state == 'submitted')
                
                # Log warning (surveys will not be deleted, links will be removed automatically by Odoo)
                import logging
                _logger = logging.getLogger(__name__)
                warning_msg = f"Deleting landowner '{landowner.name}' (ID: {landowner.id}) with {survey_count} linked survey(s). "
                warning_msg += "Surveys will NOT be deleted - only the relationship links will be removed."
                
                if approved_surveys:
                    warning_msg += f" WARNING: {len(approved_surveys)} survey(s) are APPROVED."
                
                if submitted_surveys:
                    warning_msg += f" WARNING: {len(submitted_surveys)} survey(s) are SUBMITTED."
                
                _logger.warning(warning_msg)
                
        return super(BhuLandowner, self).unlink()


class BhuLandownerPaymentStatus(models.Model):
    _name = 'bhu.landowner.payment.status'
    _description = 'Landowner Payment Status / भूस्वामी भुगतान स्थिति'
    _order = 'transaction_date desc'

    landowner_id = fields.Many2one('bhu.landowner', string='Landowner / भूस्वामी', required=True, ondelete='cascade')
    project_id = fields.Many2one('bhu.project', string='Project / परियोजना', required=True)
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=True)
    survey_id = fields.Many2one('bhu.survey', string='Khasra (Survey) / खसरा (सर्वे)', required=True)
    
    # Transaction Details
    payment_file_id = fields.Many2one('bhu.payment.file', string='Payment File / भुगतान फ़ाइल')
    utr_number = fields.Char(string='UTR Number / यूटीआर संख्या')
    transaction_date = fields.Date(string='Transaction Date / लेनदेन दिनांक')
    amount = fields.Float(string='Amount / राशि', digits=(16, 2))
    
    status = fields.Selection([
        ('pending', 'Pending / लंबित'),
        ('paid', 'Paid / भुगतान किया गया'),
        ('failed', 'Failed / असफल'),
    ], string='Status / स्थिति', default='pending')
    
    remarks = fields.Text(string='Remarks / रिमार्क')
    
    _sql_constraints = [
        ('unique_landowner_survey_project', 'unique(landowner_id, survey_id, project_id)', 
         'Payment status record already exists for this landowner, survey and project!')
    ]
    
