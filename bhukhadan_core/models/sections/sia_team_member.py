# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SiaTeamMember(models.Model):
    _name = 'bhu.sia.team.member'
    _description = 'SIA Team Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Name / नाम', required=True, tracking=True)
    post = fields.Char(string='Post / पद', tracking=True)
    address = fields.Text(string='Address / पता', tracking=True)
    department_id = fields.Many2one('bhu.department', string='Department / विभाग', tracking=True)
    user_id = fields.Many2one('res.users', string='User / उपयोगकर्ता', tracking=True,
                              help='Link to res.users if this member corresponds to a system user')


class SiaTeamMemberLine(models.Model):
    """SIA Team Member Line - Stores individual member details"""
    _name = 'bhu.sia.team.member.line'
    _description = 'SIA Team Member Line'
    _order = 'sequence, id'
    
    sequence = fields.Integer(string='Sequence', default=10)
    sia_team_id = fields.Many2one('bhu.sia.team', string='SIA Team', required=True, ondelete='cascade')
    
    member_type = fields.Selection([
        ('non_govt_social_scientist', 'Non-Government Social Scientist / गैर शासकीय सामाजिक वैज्ञानिक'),
        ('local_bodies_representative', 'Representatives of Local Bodies / स्थानीय निकायों के प्रतिनिधि'),
        ('resettlement_expert', 'Resettlement Expert / पुनर्व्यवस्थापन विशेषज्ञ'),
        ('technical_expert', 'Technical Expert / तकनीकि विशेषज्ञ'),
    ], string='Member Type', required=True)
    
    name = fields.Char(string='Name / नाम', required=True)
    address = fields.Text(string='Address / पता')
    post = fields.Char(string='Post / पद')


class ExpertCommitteeMemberLine(models.Model):
    """Expert Committee Member Line - Stores individual member details"""
    _name = 'bhu.expert.committee.member.line'
    _description = 'Expert Committee Member Line'
    _order = 'sequence, id'
    
    sequence = fields.Integer(string='Sequence', default=10)
    expert_committee_id = fields.Many2one('bhu.expert.committee.report', string='Expert Committee', required=True, ondelete='cascade')
    
    member_type = fields.Selection([
        ('non_govt_social_scientist', 'Non-Government Social Scientist / गैर शासकीय सामाजिक वैज्ञानिक'),
        ('local_bodies_representative', 'Representatives of Local Bodies / स्थानीय निकायों के प्रतिनिधि'),
        ('resettlement_expert', 'Resettlement Expert / पुनर्व्यवस्थापन विशेषज्ञ'),
        ('technical_expert', 'Technical Expert / तकनीकि विशेषज्ञ'),
    ], string='Member Type', required=True)
    
    name = fields.Char(string='Name / नाम', required=True)
    address = fields.Text(string='Address / पता')
    post = fields.Char(string='Post / पद')

