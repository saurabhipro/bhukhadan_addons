# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
import logging

_logger = logging.getLogger(__name__)

# SDM pipeline dot id → menu window action (same sections as unified dashboard).
_PIPELINE_STAGE_ACTION_REFS = {
    'survey': 'bhukhadan_core.action_bhu_survey',
    'section4': 'bhukhadan_core.action_section4_notification',
    'sia_team': 'bhukhadan_core.action_create_sia_team',
    'expert_committee': 'bhukhadan_core.action_expert_committee_report',
    'section11': 'bhukhadan_core.action_section11_preliminary_report',
    'section15': 'bhukhadan_core.action_section15_objections',
    'section19': 'bhukhadan_core.action_section19_notification',
    'section21': 'bhukhadan_core.action_section21_notification',
    'section23': 'bhukhadan_core.action_section23_award',
    'payment_voucher': 'bhukhadan_core.action_bhu_payment_voucher',
    'payment_file': 'bhukhadan_core.action_bhu_payment_voucher_export',
}

_PIPELINE_STAGE_RES_MODELS = {
    'survey': 'bhu.survey',
    'section4': 'bhu.section4.notification',
    'sia_team': 'bhu.sia.team',
    'expert_committee': 'bhu.expert.committee.report',
    'section11': 'bhu.section11.preliminary.report',
    'section15': 'bhu.section15.objection',
    'section19': 'bhu.section19.notification',
    'section21': 'bhu.section21.notification',
    'section23': 'bhu.section23.award',
    'payment_voucher': 'bhu.payment.voucher',
    'payment_file': 'bhu.payment.voucher.export',
}

_PIPELINE_MODELS_WITH_VILLAGE = frozenset({
    'bhu.survey',
    'bhu.section4.notification',
    'bhu.section11.preliminary.report',
    'bhu.section15.objection',
    'bhu.section19.notification',
    'bhu.section21.notification',
    'bhu.section23.award',
    'bhu.payment.voucher',
    'bhu.payment.voucher.export',
})


class DashboardActions(models.AbstractModel):
    """Dashboard action methods for opening various views"""
    _name = 'bhuarjan.dashboard.actions'
    _description = 'Dashboard Action Methods'

    @api.model
    def _ensure_act_window_views(self, action):
        """Odoo 18 web client expects ``views`` on ir.actions.act_window; ORM RPC skips generate_views."""
        if not isinstance(action, dict):
            return action
        if action.get('type') != 'ir.actions.act_window':
            return action
        views = action.get('views')
        if isinstance(views, list) and len(views):
            return action
        view_mode = action.get('view_mode') or 'list,form'
        if isinstance(view_mode, str):
            modes = [m.strip() for m in view_mode.split(',') if m.strip()]
        else:
            try:
                modes = [str(x).strip() for x in view_mode if str(x).strip()]
            except (TypeError, ValueError):
                modes = []
        if not modes:
            modes = ['list', 'form']
        out = dict(action)
        out['views'] = [(False, mode) for mode in modes]
        return out

    @api.model
    def _get_action_dict(self, action_ref):
        """Helper method to get action dictionary with all required fields"""
        try:
            # Use sudo to bypass any access issues when reading the action
            # Read all fields to ensure we get the complete action
            action = action_ref.sudo().read([])[0]
            # Ensure action has required fields for Odoo 18
            if 'type' not in action:
                action['type'] = 'ir.actions.act_window'
            if 'target' not in action:
                action['target'] = 'current'
            # Ensure views is a list (Odoo 18 requirement)
            # views should be a list of tuples: [(view_id, mode), ...]
            if 'views' not in action or not action.get('views') or action.get('views') == False:
                # If views is missing, create it from view_mode
                view_mode = action.get('view_mode', 'list,form')
                if isinstance(view_mode, str):
                    view_mode = view_mode.split(',')
                action['views'] = [(False, mode.strip()) for mode in view_mode]
            elif isinstance(action.get('views'), list):
                # Ensure all views are tuples
                action['views'] = [
                    (v[0], v[1]) if isinstance(v, (list, tuple)) and len(v) >= 2 else (False, v if isinstance(v, str) else 'list')
                    for v in action['views']
                ]
            return self._ensure_act_window_views(action)
        except Exception as e:
            _logger.error(f"Error reading action {action_ref.id}: {e}", exc_info=True)
            # Fallback: create action dynamically from action_ref
            view_mode = action_ref.view_mode or 'list,form'
            if isinstance(view_mode, str):
                view_mode = view_mode.split(',')
            return self._ensure_act_window_views({
                'type': 'ir.actions.act_window',
                'name': action_ref.name or action_ref.xml_id.split('.')[-1].replace('_', ' ').title() if hasattr(action_ref, 'xml_id') else 'Action',
                'res_model': action_ref.res_model,
                'view_mode': ','.join(view_mode),
                'views': [(False, mode) for mode in view_mode],
                'target': 'current',
            })
    @api.model
    def action_open_districts(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_district')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_district: {e}", exc_info=True)
            return self._ensure_act_window_views({
                'type': 'ir.actions.act_window',
                'name': 'Districts',
                'res_model': 'bhu.district',
                'view_mode': 'list,form',
                'target': 'current',
            })
    @api.model
    def action_open_sub_divisions(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_sub_division')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_sub_division: {e}", exc_info=True)
            return self._ensure_act_window_views({
                'type': 'ir.actions.act_window',
                'name': 'Sub Divisions',
                'res_model': 'bhu.sub.division',
                'view_mode': 'list,form',
                'target': 'current',
            })
    @api.model
    def action_open_tehsils(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_tehsil')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_tehsil: {e}", exc_info=True)
            return self._ensure_act_window_views({
                'type': 'ir.actions.act_window',
                'name': 'Tehsils',
                'res_model': 'bhu.tehsil',
                'view_mode': 'list,form',
                'target': 'current',
            })
    @api.model
    def action_open_villages(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_village')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_village: {e}", exc_info=True)
            return self._ensure_act_window_views({
                'type': 'ir.actions.act_window',
                'name': 'Villages',
                'res_model': 'bhu.village',
                'view_mode': 'list,form',
                'target': 'current',
            })
    @api.model
    def action_open_projects(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_project')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_project: {e}", exc_info=True)
            return self._ensure_act_window_views({
                'type': 'ir.actions.act_window',
                'name': 'Projects',
                'res_model': 'bhu.project',
                'view_mode': 'list,form',
                'target': 'current',
            })
    @api.model
    def action_open_departments(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_department')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_department: {e}", exc_info=True)
            return self._ensure_act_window_views({
                'type': 'ir.actions.act_window',
                'name': 'Departments',
                'res_model': 'bhu.department',
                'view_mode': 'list,form',
                'target': 'current',
            })
    @api.model
    def action_open_landowners(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_landowner')
            action = self._get_action_dict(action_ref)
            # Clear any default filters to prevent saved filters from auto-applying
            if 'context' not in action:
                action['context'] = {}
            action['context'].update({
                'search_default_district_id': False,
            })
            return action
        except Exception as e:
            _logger.error(f"Error getting action_bhu_landowner: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Landowners',
                'res_model': 'bhu.landowner',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_rate_masters(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_land_rate_master')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_land_rate_master: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Rate Masters',
                'res_model': 'bhu.rate.master',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_surveys(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_survey')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_bhu_survey: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Surveys',
                'res_model': 'bhu.survey',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_surveys_draft(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_survey')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'draft')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_bhu_survey: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Draft Surveys',
                'res_model': 'bhu.survey',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'draft')],
                'target': 'current',
            }
    @api.model
    def action_open_surveys_rejected(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_survey')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'rejected')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_bhu_survey: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Rejected Surveys',
                'res_model': 'bhu.survey',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'rejected')],
                'target': 'current',
            }
    @api.model
    def action_open_surveys_submitted(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_survey')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'submitted')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_bhu_survey: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Submitted Surveys',
                'res_model': 'bhu.survey',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'submitted')],
                'target': 'current',
            }
    @api.model
    def action_open_surveys_approved(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_survey')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'approved')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_bhu_survey: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Approved Surveys',
                'res_model': 'bhu.survey',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'approved')],
                'target': 'current',
            }
    @api.model
    def action_open_surveys_pending(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_survey')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', 'in', ['submitted', 'rejected'])]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_bhu_survey: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Pending Surveys',
                'res_model': 'bhu.survey',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', 'in', ['submitted', 'rejected'])],
                'target': 'current',
            }
    @api.model
    def action_open_surveys_done(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_survey')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', 'in', ['approved', 'rejected'])]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_bhu_survey: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Completed Surveys',
                'res_model': 'bhu.survey',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', 'in', ['approved', 'rejected'])],
                'target': 'current',
            }
    @api.model
    def action_open_expert_committee(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_expert_committee_report')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_expert_committee_report: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Expert Committee Reports',
                'res_model': 'bhu.expert.committee.report',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_section4(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section4_notification')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_section4_notification: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 4 Notifications',
                'res_model': 'bhu.section4.notification',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_section11(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section11_preliminary_report')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_section11_preliminary_report: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 11 Preliminary Reports',
                'res_model': 'bhu.section11.preliminary.report',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_section15(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section15_objections')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_section15_objections: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 15 Objections',
                'res_model': 'bhu.section15.objection',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_documents(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_document_vault')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_document_vault: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Document Vault',
                'res_model': 'bhu.document.vault',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }

    @api.model
    def action_open_document_vault_navigator(self):
        """Open dashboard-style document navigator."""
        return self.env['bhu.document.vault.navigator'].action_open_navigator()
    @api.model
    def action_open_section19(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section19_notification')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_section19_notification: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 19 Notifications',
                'res_model': 'bhu.section19.notification',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_section19_draft(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section19_notification')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'draft')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_section19_notification: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 19 Notifications (Draft)',
                'res_model': 'bhu.section19.notification',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'draft')],
                'target': 'current',
            }
    @api.model
    def action_open_section19_generated(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section19_notification')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'generated')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_section19_notification: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 19 Notifications (Generated)',
                'res_model': 'bhu.section19.notification',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'generated')],
                'target': 'current',
            }
    @api.model
    def action_open_section19_signed(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section19_notification')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'signed')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_section19_notification: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 19 Notifications (Signed)',
                'res_model': 'bhu.section19.notification',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'signed')],
                'target': 'current',
            }
    @api.model
    def _get_award_for_payment_voucher_dashboard(self, project_id, village_id):
        """Resolve Section 23 award for dashboard payment voucher actions."""
        if not project_id or not village_id:
            raise UserError(_(
                'Please select a project and village on the dashboard before working on a payment voucher.'
            ))
        project_id = int(project_id)
        village_id = int(village_id)
        award = self.env['bhu.section23.award'].search([
            ('project_id', '=', project_id),
            ('village_id', '=', village_id),
        ], limit=1)
        if not award:
            raise UserError(_(
                'Cannot create a Payment Voucher yet.\n\n'
                'Complete Step 11 — Section 23 Award for the selected project and village first.\n'
                'After the award is saved, generate the R&R award on that form, then return here and click Create.\n\n'
                'अभी भुगतान वाउचर नहीं बनाया जा सकता। '
                'कृपया पहले चरण 11 — धारा 23 अवार्ड इस प्रोजेक्ट और गाँव के लिए बनाएं, '
                'फिर उस पर R&R जेनरेट करें।'
            ))
        if not award.rr_generated:
            raise UserError(_(
                'Cannot create a Payment Voucher yet.\n\n'
                'Step 11 — Section 23 Award exists, but R&R has not been generated.\n'
                'Open that award, generate the R&R award, then click Create on Payment Voucher again.\n\n'
                'धारा 23 अवार्ड मौजूद है, पर R&R अभी जेनरेट नहीं हुआ है। '
                'कृपया अवार्ड खोलकर R&R जेनरेट करें, फिर यहाँ Create दबाएं।'
            ))
        return award

    @api.model
    def action_create_payment_voucher_from_dashboard(self, project_id, village_id):
        """Create (or reopen) the single R&R payment voucher for this award."""
        award = self._get_award_for_payment_voucher_dashboard(project_id, village_id)
        return award.action_create_draft_rr_payment_voucher()

    @api.model
    def action_open_payment_voucher_from_dashboard(self, project_id, village_id):
        """Open existing R&R payment voucher from dashboard."""
        award = self._get_award_for_payment_voucher_dashboard(project_id, village_id)

        Voucher = self.env['bhu.payment.voucher']
        voucher = Voucher.search([
            ('award_id', '=', award.id),
        ], order='create_date desc, id desc', limit=1)

        if not voucher:
            raise UserError(_(
                'No payment voucher exists for this award yet.\n\n'
                'Click Create on Payment Voucher (Step 12) after R&R is generated on the Section 23 award.\n\n'
                'इस अवार्ड के लिए अभी कोई भुगतान वाउचर नहीं है। '
                'R&R जेनरेट करने के बाद Payment Voucher पर Create दबाएं।'
            ))

        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_payment_voucher')
            result = self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error('Error loading payment voucher action: %s', e, exc_info=True)
            result = {
                'type': 'ir.actions.act_window',
                'name': _('R&R Payment Voucher'),
                'res_model': 'bhu.payment.voucher',
                'view_mode': 'form',
                'target': 'current',
            }

        form_view = self.env.ref('bhukhadan_core.view_bhu_payment_voucher_form', raise_if_not_found=False)
        form_view_id = form_view.id if form_view else False

        result.update({
            'name': _('R&R Payment Voucher'),
            'res_id': voucher.id,
            'view_mode': 'form',
            'views': [(form_view_id, 'form')],
            'domain': [('id', '=', voucher.id)],
            'context': dict(
                self.env.context,
                default_award_id=award.id,
                default_project_id=project_id,
                default_village_id=village_id,
                create=False,
            ),
        })
        return self._ensure_act_window_views(result)

    @api.model
    def action_open_payment_voucher_list_from_dashboard(self, project_id, village_id):
        """Open payment voucher list for dashboard Payment File → View/Edit."""
        domain = []
        if project_id:
            domain.append(('project_id', '=', int(project_id)))
        if village_id:
            domain.append(('village_id', '=', int(village_id)))

        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_payment_voucher')
            result = self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error('Error loading payment voucher action: %s', e, exc_info=True)
            result = {
                'type': 'ir.actions.act_window',
                'name': _('R&R Payment Vouchers'),
                'res_model': 'bhu.payment.voucher',
                'view_mode': 'list,form',
                'target': 'current',
            }

        result['domain'] = domain
        ctx = dict(self.env.context)
        if project_id:
            ctx['default_project_id'] = int(project_id)
        if village_id:
            ctx['default_village_id'] = int(village_id)
        result['context'] = ctx
        return self._ensure_act_window_views(result)

    @api.model
    def _payment_export_action_defaults(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_payment_voucher_export')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error('Error getting payment export action: %s', e, exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Generated Payment Files'),
                'res_model': 'bhu.payment.voucher.export',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
                'context': {'create': False},
            }

    @api.model
    def action_open_payment_files(self):
        return self._payment_export_action_defaults()

    @api.model
    def action_open_payment_files_draft(self):
        """Vouchers ready to generate the next bank payment file (one voucher per award)."""
        try:
            action_ref = self.env.ref('bhukhadan_core.action_bhu_payment_voucher')
            action = self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error('Error getting payment voucher action: %s', e, exc_info=True)
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Payment Vouchers (ready for file)'),
                'res_model': 'bhu.payment.voucher',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
        action['domain'] = [('state', '=', 'ready')]
        return action

    @api.model
    def action_open_payment_files_generated(self):
        action = self._payment_export_action_defaults()
        action['domain'] = [('generated_file', '!=', False)]
        return action
    @api.model
    def action_open_payment_reconciliations(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_payment_reconciliation_bank')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_payment_reconciliation_bank: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Payment Reconciliations',
                'res_model': 'bhu.payment.reconciliation',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_reconciliations_draft(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_payment_reconciliation_bank')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'draft')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_payment_reconciliation_bank: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Payment Reconciliations (Draft)',
                'res_model': 'bhu.payment.reconciliation',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'draft')],
                'target': 'current',
            }
    @api.model
    def action_open_reconciliations_processed(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_payment_reconciliation_bank')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'processed')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_payment_reconciliation_bank: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Payment Reconciliations (Processed)',
                'res_model': 'bhu.payment.reconciliation',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'processed')],
                'target': 'current',
            }
    @api.model
    def action_open_reconciliations_completed(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_payment_reconciliation_bank')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'completed')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_payment_reconciliation_bank: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Payment Reconciliations (Completed)',
                'res_model': 'bhu.payment.reconciliation',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'completed')],
                'target': 'current',
            }
    @api.model
    def action_open_sia_teams(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_create_sia_team')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_create_sia_team: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'SIA Teams',
                'res_model': 'bhu.sia.team',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_sia_teams_draft(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_create_sia_team')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'draft')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_create_sia_team: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'SIA Teams (Draft)',
                'res_model': 'bhu.sia.team',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'draft')],
                'target': 'current',
            }
    @api.model
    def action_open_sia_teams_submitted(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_create_sia_team')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'submitted')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_create_sia_team: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'SIA Teams (Submitted)',
                'res_model': 'bhu.sia.team',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'submitted')],
                'target': 'current',
            }
    @api.model
    def action_open_sia_teams_approved(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_create_sia_team')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'approved')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_create_sia_team: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'SIA Teams (Approved)',
                'res_model': 'bhu.sia.team',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'approved')],
                'target': 'current',
            }
    @api.model
    def action_open_sia_teams_send_back(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_create_sia_team')
            action = self._get_action_dict(action_ref)
            action['domain'] = [('state', '=', 'send_back')]
            return action
        except Exception as e:
            _logger.error(f"Error getting action_create_sia_team: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'SIA Teams (Sent Back)',
                'res_model': 'bhu.sia.team',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('state', '=', 'send_back')],
                'target': 'current',
            }

    @api.model
    def action_open_section23(self):
        try:
            action_ref = self.env.ref('bhukhadan_core.action_section23_award')
            return self._get_action_dict(action_ref)
        except Exception as e:
            _logger.error(f"Error getting action_section23_award: {e}", exc_info=True)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Section 23 Award',
                'res_model': 'bhu.section23.award',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }
    @api.model
    def action_open_mobile_users(self):
        """Open mobile users list (JWT tokens with mobile channel)"""
        return self._ensure_act_window_views({
            'type': 'ir.actions.act_window',
            'name': 'Active Mobile Users',
            'res_model': 'jwt.token',
            'view_mode': 'list,form',
            'domain': ['|', ('channel_type', '=', 'mobile'), ('channel_type', '=', False)],
            'context': {'search_default_group_by_user': 1},
        })

    @api.model
    def _merge_action_context(self, action, extra_ctx):
        """Merge RPC-safe context dict into an act_window payload."""
        ctx = action.get('context') or {}
        if isinstance(ctx, str):
            try:
                ctx = safe_eval(ctx) or {}
            except Exception:
                ctx = {}
        if not isinstance(ctx, dict):
            ctx = {}
        merged = dict(ctx)
        merged.update(extra_ctx)
        action['context'] = merged
        return action

    @api.model
    def get_pipeline_stage_window_action(self, stage_id, project_id, village_id=False):
        """Return ir.actions.act_window for a pipeline dot (SDM pipeline dashboard)."""
        stage = (stage_id or '').strip()
        pid = int(project_id or 0)
        vid = int(village_id or 0) if village_id else 0
        if not pid:
            raise UserError(_('Project is required to open this section.'))
        xmlid = _PIPELINE_STAGE_ACTION_REFS.get(stage)
        res_model = _PIPELINE_STAGE_RES_MODELS.get(stage)
        if not xmlid or not res_model:
            raise UserError(_('Unknown pipeline stage: %s') % (stage or '—'))

        domain = [('project_id', '=', pid)]
        if vid and res_model in _PIPELINE_MODELS_WITH_VILLAGE:
            domain.append(('village_id', '=', vid))

        ctx = {
            'default_project_id': pid,
            'default_village_id': vid or False,
            'active_project_id': pid,
            'active_village_id': vid or False,
        }
        if res_model == 'bhu.survey':
            ctx['search_default_group_by_state'] = 1
        if res_model == 'bhu.payment.voucher.export':
            ctx['create'] = False

        # One voucher per village: open form when a single record exists.
        if stage == 'payment_voucher' and vid:
            Voucher = self.env['bhu.payment.voucher'].sudo()
            vouchers = Voucher.search(
                [('project_id', '=', pid), ('village_id', '=', vid)],
                order='id desc',
                limit=2,
            )
            if len(vouchers) == 1:
                try:
                    action_ref = self.env.ref(xmlid)
                    action = self._get_action_dict(action_ref)
                except Exception:
                    action = {
                        'type': 'ir.actions.act_window',
                        'name': _('Payment Voucher'),
                        'res_model': res_model,
                        'view_mode': 'form',
                        'views': [(False, 'form')],
                        'target': 'current',
                    }
                action = dict(action)
                action['res_model'] = res_model
                action['res_id'] = vouchers.id
                action['view_mode'] = 'form'
                action['views'] = [(False, 'form')]
                action['domain'] = domain
                action['target'] = 'current'
                return self._merge_action_context(action, ctx)

        try:
            action_ref = self.env.ref(xmlid)
            action = self._get_action_dict(action_ref)
        except Exception as e:
            _logger.warning('Pipeline stage action %s: %s', xmlid, e)
            action = {
                'type': 'ir.actions.act_window',
                'name': stage.replace('_', ' ').title(),
                'res_model': res_model,
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
                'target': 'current',
            }

        action = dict(action)
        action['res_model'] = res_model
        action['domain'] = domain
        action['target'] = 'current'
        if 'res_id' in action and not action.get('res_id'):
            action.pop('res_id', None)
        return self._merge_action_context(self._ensure_act_window_views(action), ctx)
