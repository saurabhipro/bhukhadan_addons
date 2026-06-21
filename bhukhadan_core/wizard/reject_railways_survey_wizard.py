# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class RejectRailwaysSurveyWizard(models.TransientModel):
    _name = 'bhu.reject.railways.survey.wizard'
    _description = 'Reject Railways Survey Wizard'
    
    section20d_id = fields.Many2one('bhu.section20d.railways', string='Section 20D Record', readonly=True)
    survey_id = fields.Many2one('bhu.survey', string='Survey (Khasra)', required=True, readonly=True)
    reason = fields.Text(string='Rejection Reason / अस्वीकृति का कारण', required=True)
    
    def action_reject(self):
        """Reject the survey and log message"""
        self.ensure_one()
        
        # Update survey status to rejected
        self.survey_id.write({'state': 'rejected'})
        
        # Log message in survey
        self.survey_id.message_post(
            body=_('Survey rejected from Section 20D (Railways): %s. Reason: %s') % (self.section20d_id.name, self.reason),
            message_type='comment'
        )
        
        # Log message in section 20d record
        self.section20d_id.message_post(
            body=_('Survey %s rejected. Reason: %s') % (self.survey_id.name, self.reason)
        )
        
        return {'type': 'ir.actions.act_window_close'}
