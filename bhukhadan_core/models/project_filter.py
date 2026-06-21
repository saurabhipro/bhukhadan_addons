# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProjectFilter(models.AbstractModel):
    """Abstract model to add project filtering capabilities"""
    _name = 'bhu.project.filter'
    _description = 'Project Filter Mixin'

    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        """Override search to apply project filtering"""
        # Get current project from session
        current_project_id = self.env.context.get('bhuarjan_current_project_id')
        
        if current_project_id and current_project_id != '0':
            # Add project filter to domain
            project_filter = ('project_id', '=', int(current_project_id))
            args = args + [project_filter]
        
        return super(ProjectFilter, self).search(args, offset=offset, limit=limit, order=order)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to apply project filtering"""
        # Get current project from session
        current_project_id = self.env.context.get('bhuarjan_current_project_id')
        
        if current_project_id and current_project_id != '0':
            # Add project filter to domain
            project_filter = ('project_id', '=', int(current_project_id))
            if domain is None:
                domain = []
            domain = domain + [project_filter]
        
        return super(ProjectFilter, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)


class BhuSurveyProjectFilter(models.Model):
    _name = 'bhu.survey'
    _inherit = ['bhu.survey', 'bhu.project.filter']


class BhuLandownerProjectFilter(models.Model):
    _name = 'bhu.landowner'
    _inherit = ['bhu.landowner', 'bhu.project.filter']


class BhuPostAwardPaymentProjectFilter(models.Model):
    _name = 'bhu.post.award.payment'
    _inherit = ['bhu.post.award.payment', 'bhu.project.filter']


class BhuPaymentReconciliationProjectFilter(models.Model):
    _name = 'bhu.payment.reconciliation'
    _inherit = ['bhu.payment.reconciliation', 'bhu.project.filter']
