# -*- coding: utf-8 -*-

from odoo import models, fields


class SurveyMessageWizard(models.TransientModel):
    _name = 'bhu.survey.message.wizard'
    _description = 'Survey Message Wizard'

    message = fields.Text(string='Message', readonly=True)


