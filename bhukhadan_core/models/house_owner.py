# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BhuHouseOwner(models.Model):
    _name = 'bhu.house.owner'
    _description = 'House Owner'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Full Name / पूरा नाम', required=True, tracking=True)
    aadhar_number = fields.Char(string='Aadhar Number / आधार नंबर', tracking=True)
    phone = fields.Char(string='Mobile Number / मोबाइल नंबर', tracking=True)
    caste = fields.Char(string='Caste/Category / जाति/श्रेणी', tracking=True)
    dob = fields.Date(string='Date of Birth / जन्म तिथि', tracking=True)

    company_id = fields.Many2one(
        'res.company', string='Company / कंपनी', required=True,
        default=lambda self: self.env.company, tracking=True,
    )
    village_id = fields.Many2one('bhu.village', string='Village / ग्राम', tracking=True)
    house_number = fields.Char(string='House Number / मकान नंबर', tracking=True)
    mohalla = fields.Char(string='Mohalla / मोहल्ला', tracking=True)

    survey_id = fields.Many2one(
        'bhu.survey', string='Survey / सर्वे', ondelete='cascade', index=True, tracking=True,
    )

    # Document checklist
    doc_electricity_bill = fields.Boolean(string='Electricity Bill - House owner')
    doc_voter_card_owner = fields.Boolean(string='Voter Card - House owner')
    doc_aadhar_owner = fields.Boolean(string='Aadhar Card - House owner')
    doc_aadhar_witness_1 = fields.Boolean(string='Aadhar Card - Witness 01')
    doc_aadhar_witness_2 = fields.Boolean(string='Aadhar Card - Witness 02')
    doc_ration_owner = fields.Boolean(string='Ration Card - House owner')
    doc_education_owner = fields.Boolean(string='Educational Certificate - House owner')
    doc_aadhar_landowner = fields.Boolean(string='Aadhar Card - Land owner')
    doc_affidavit_noc = fields.Boolean(string='Affidavit/NOC from landowner')
    doc_passport_photos = fields.Boolean(string='House owner passport photos')
    doc_pan_owner = fields.Boolean(string='PAN Card - House owner')
    doc_pan_landowner = fields.Boolean(string='PAN Card - Land owner')
    doc_bank_passbook = fields.Boolean(string='Bank Account Passbook')
    doc_bank_neft_form = fields.Boolean(string='Bank NEFT mandate form')
    doc_bank_ifsc = fields.Boolean(string='Bank IFSC Details')
    doc_other = fields.Boolean(string='Other Documents')
    doc_other_text = fields.Char(string='Other Documents Detail')

    @api.model
    def _migrate_survey_m2m_to_o2m(self):
        """One-time migration from bhu_survey_house_owner_rel to survey_id."""
        cr = self._cr
        cr.execute("SELECT to_regclass('public.bhu_survey_house_owner_rel')")
        if not cr.fetchone()[0]:
            return
        cr.execute("""
            SELECT rel.house_owner_id, rel.survey_id
            FROM bhu_survey_house_owner_rel rel
            ORDER BY rel.house_owner_id, rel.survey_id
        """)
        primary_survey = {}
        for house_owner_id, survey_id in cr.fetchall():
            house_owner = self.browse(house_owner_id)
            if not house_owner.exists():
                continue
            if house_owner_id not in primary_survey:
                house_owner.survey_id = survey_id
                primary_survey[house_owner_id] = survey_id
            elif primary_survey[house_owner_id] != survey_id:
                house_owner.copy({'survey_id': survey_id})
        cr.execute("DROP TABLE IF EXISTS bhu_survey_house_owner_rel")

    def init(self):
        super().init()
        self._migrate_survey_m2m_to_o2m()

    @api.model
    def _search(self, args, offset=0, limit=None, order=None):
        user = self.env.user

        if user.has_group('bhukhadan_core.group_bhuarjan_admin') or user.has_group('base.group_system'):
            return super()._search(args, offset=offset, limit=limit, order=order)

        if user.has_group('bhukhadan_core.group_bhuarjan_sdm') or user.has_group('bhukhadan_core.group_bhuarjan_tahsildar'):
            return super()._search(args, offset=offset, limit=limit, order=order)

        if user.district_id:
            args = [('village_id.district_id', '=', user.district_id.id)] + args

        if user.bhuarjan_role in self.env['res.users'].BHUKHADAN_PATWARI_ROLES:
            patwari_domain = [
                '|',
                ('village_id.user_id', '=', user.id),
                ('survey_id.user_id', '=', user.id),
            ]
            args = patwari_domain + args

        return super()._search(args, offset=offset, limit=limit, order=order)
