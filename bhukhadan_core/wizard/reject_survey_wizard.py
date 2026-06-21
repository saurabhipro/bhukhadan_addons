# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class RejectSurveyWizard(models.TransientModel):
    _name = 'bhu.reject.survey.wizard'
    _description = 'Reject Survey Wizard'
    
    objection_id = fields.Many2one('bhu.section15.objection', string='Objection', readonly=True)
    survey_id = fields.Many2one('bhu.survey', string='Survey (Khasra)', required=True, readonly=True)
    reason = fields.Text(string='Rejection Reason / अस्वीकृति का कारण', required=True)
    
    def action_reject(self):
        """Reject the survey and create a new objection automatically"""
        self.ensure_one()
        
        # Update survey status to rejected
        self.survey_id.write({'state': 'rejected'})
        
        # Log message in survey
        self.survey_id.message_post(
            body=_('Survey rejected from Section 15 Objection: %s. Reason: %s') % (self.objection_id.name, self.reason),
            message_type='comment'
        )
        
        # Log message in objection
        self.objection_id.message_post(
            body=_('Survey %s rejected. Reason: %s') % (self.survey_id.name, self.reason)
        )
        
        return {'type': 'ir.actions.act_window_close'}
