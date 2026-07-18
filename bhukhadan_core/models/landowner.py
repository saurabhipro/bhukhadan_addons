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
    caste = fields.Char(string='Caste/Category / जाति/श्रेणी', tracking=True)
    
    # Contact Information
    phone = fields.Char(string='Phone Number / फोन नंबर', tracking=True)
    
    # Company/Organization Information
    company_id = fields.Many2one('res.company', string='Company / कंपनी', required=True, 
                                 default=lambda self: self.env.company, tracking=True)
    
    # Address Information
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', required=False, tracking=True)
    rakba = fields.Char(string='Rakba / रकबा', tracking=True)
    
    # Identity Documents
    aadhar_number = fields.Char(string='Aadhar Number / आधार नंबर', tracking=True)
    
    # Bank Details
    bank_name = fields.Char(string='Bank Name / बैंक का नाम', tracking=True)
    bank_branch = fields.Char(string='Bank Branch / बैंक शाखा', tracking=True)
    account_number = fields.Char(string='Account Number / खाता संख्या', tracking=True)
    ifsc_code = fields.Char(string='IFSC Code / आईएफएससी कोड', tracking=True)
    account_holder_name = fields.Char(string='Account Holder Name / खाताधारक का नाम', tracking=True)
    
    # Documents
    aadhar_card = fields.Binary(string='Aadhar Card / आधार कार्ड')
    pan_card = fields.Binary(string='PAN Card / पैन कार्ड')
    
    survey_id = fields.Many2one(
        'bhu.survey', string='Survey / सर्वे', ondelete='cascade', index=True, tracking=True,
    )
    
    # Payment Status Tracking
    payment_status_ids = fields.One2many('bhu.landowner.payment.status', 'landowner_id', 
                                        string='Payment Status / भुगतान की स्थिति')
    
    # Validation Methods removed - no validations for aadhar, pan, account_number
    
    def action_view_survey(self):
        """Open the survey this landowner belongs to."""
        self.ensure_one()
        if not self.survey_id:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.act_window',
            'name': _('Survey'),
            'res_model': 'bhu.survey',
            'view_mode': 'form',
            'res_id': self.survey_id.id,
        }

    @api.model
    def _migrate_survey_m2m_to_o2m(self):
        """One-time migration from bhu_survey_landowner_rel to survey_id."""
        cr = self._cr
        cr.execute("SELECT to_regclass('public.bhu_survey_landowner_rel')")
        if not cr.fetchone()[0]:
            return
        cr.execute("""
            SELECT rel.landowner_id, rel.survey_id
            FROM bhu_survey_landowner_rel rel
            ORDER BY rel.landowner_id, rel.survey_id
        """)
        primary_survey = {}
        for landowner_id, survey_id in cr.fetchall():
            landowner = self.browse(landowner_id)
            if not landowner.exists():
                continue
            if landowner_id not in primary_survey:
                landowner.survey_id = survey_id
                primary_survey[landowner_id] = survey_id
            elif primary_survey[landowner_id] != survey_id:
                landowner.copy({'survey_id': survey_id})
        cr.execute("DROP TABLE IF EXISTS bhu_survey_landowner_rel")

    def init(self):
        super().init()
        self._migrate_survey_m2m_to_o2m()

    @api.model
    def _search(self, args, offset=0, limit=None, order=None):
        """Override search to apply role-based filtering"""
        user = self.env.user
        
        # Admin sees everything - no filter
        if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
            return super(BhuLandowner, self)._search(args, offset=offset, limit=limit, order=order)

        # SDM / Tehsildar: record rules (district OR surveys on assigned projects) must apply.
        if user.has_group('bhukhadan_core.group_bhuarjan_sdm') or user.has_group('bhukhadan_core.group_bhuarjan_tahsildar'):
            return super(BhuLandowner, self)._search(args, offset=offset, limit=limit, order=order)
            
        # For all other users, restrict to their assigned district if they have one
        if user.district_id:
            args = [('village_id.district_id', '=', user.district_id.id)] + args
            
        # Apply additional Patwari-specific filtering
        if user.bhuarjan_role in self.env['res.users'].BHUKHADAN_PATWARI_ROLES:
            # Patwari can only see landowners from their assigned villages
            # and landowners who are in surveys they created
            patwari_domain = [
                '|',
                ('village_id.user_id', '=', user.id),
                ('survey_id.user_id', '=', user.id),
            ]
            args = patwari_domain + args
        
        return super(BhuLandowner, self)._search(args, offset=offset, limit=limit, order=order)
    
    def unlink(self):
        """Override unlink to handle survey relationships properly
        
        When a landowner is deleted:
        - The survey itself is NOT deleted
        - We warn the user if the parent survey is approved/submitted
        """
        for landowner in self:
            survey = landowner.survey_id
            if survey:
                import logging
                _logger = logging.getLogger(__name__)
                warning_msg = (
                    f"Deleting landowner '{landowner.name}' (ID: {landowner.id}) "
                    f"from survey '{survey.name}' (ID: {survey.id})."
                )
                if survey.state == 'approved':
                    warning_msg += ' WARNING: survey is APPROVED.'
                elif survey.state == 'submitted':
                    warning_msg += ' WARNING: survey is SUBMITTED.'
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
    
