# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
import json


class CbaCaseStepLine(models.Model):
    """Per-case tracking line for each workflow step."""
    _name = 'cba.case.step.line'
    _description = 'CBA Case Step Line'
    _order = 'sequence, id'

    case_id = fields.Many2one(
        'cba.case',
        string='CBA Case',
        required=True,
        ondelete='cascade',
        index=True,
    )
    step_id = fields.Many2one(
        'cba.workflow.step',
        string='Workflow Step (Legacy)',
        ondelete='restrict',
    )
    node_id = fields.Many2one(
        'cba.workflow.node',
        string='Workflow Node',
        ondelete='restrict',
    )
    bpmn_id = fields.Char(compute='_compute_line_meta', store=True, readonly=True)
    name = fields.Char(compute='_compute_line_meta', store=True, readonly=True)
    sequence = fields.Integer(compute='_compute_line_meta', store=True, readonly=True)
    lane = fields.Selection(
        related='step_id.lane',
        string='Lane',
        store=True,
        readonly=True,
    )
    step_type = fields.Selection([
        ('start', 'Start Event'),
        ('task', 'Task'),
        ('subprocess', 'Sub-Process'),
        ('gateway', 'Gateway'),
        ('end', 'End Event'),
    ], compute='_compute_line_meta', store=True, readonly=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('skipped', 'Skipped'),
    ], string='Status', default='pending', required=True)
    started_on = fields.Datetime(string='Started On', readonly=True)
    completed_on = fields.Datetime(string='Completed On', readonly=True)
    completed_by_id = fields.Many2one('res.users', string='Completed By', readonly=True)
    notes = fields.Text(string='Notes / Remarks')
    photo_ids = fields.One2many(
        'cba.step.photo',
        'step_line_id',
        string='Photos',
    )
    photo_count = fields.Integer(compute='_compute_photo_count')
    requires_photo = fields.Boolean(compute='_compute_line_meta', store=True, readonly=True)

    @api.depends('step_id', 'node_id')
    def _compute_line_meta(self):
        node_type_map = {
            'start': 'start',
            'task': 'task',
            'subprocess': 'subprocess',
            'gateway': 'gateway',
            'end': 'end',
        }
        for line in self:
            if line.node_id:
                line.name = line.node_id.name
                line.bpmn_id = line.node_id.bpmn_id
                line.sequence = line.node_id.sequence
                line.step_type = node_type_map.get(line.node_id.node_type, 'task')
                line.requires_photo = line.node_id.requires_photo
            elif line.step_id:
                line.name = line.step_id.name
                line.bpmn_id = line.step_id.bpmn_id
                line.sequence = line.step_id.sequence
                line.step_type = line.step_id.step_type
                line.requires_photo = line.step_id.requires_photo
            else:
                line.name = False
                line.bpmn_id = False
                line.sequence = 0
                line.step_type = 'task'
                line.requires_photo = False

    @api.constrains('step_id', 'node_id')
    def _check_step_or_node(self):
        for line in self:
            if not line.step_id and not line.node_id:
                raise ValidationError(_('Each step line must link to a workflow step or node.'))

    @api.depends('photo_ids')
    def _compute_photo_count(self):
        for line in self:
            line.photo_count = len(line.photo_ids)


class CbaCase(models.Model):
    """A Coal Bearing Areas Act acquisition case driven by the L&R Master SOP BPMN."""
    _name = 'cba.case'
    _description = 'CBA Acquisition Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    project_id = fields.Many2one(
        'cba.project',
        string='Project',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    project_district_id = fields.Many2one(
        'cba.district',
        string='Project District',
        related='project_id.district_id',
        readonly=True,
    )
    workflow_id = fields.Many2one(
        'cba.workflow',
        string='Workflow',
        tracking=True,
        ondelete='restrict',
        default=lambda self: self._default_workflow_id(),
    )
    village_id = fields.Many2one(
        'cba.village',
        string='Village',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    district_id = fields.Many2one(
        'cba.district',
        string='District',
        compute='_compute_location',
        store=True,
    )
    tehsil_id = fields.Many2one(
        'cba.tehsil',
        string='Tehsil',
        compute='_compute_location',
        store=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    current_step_id = fields.Many2one(
        'cba.workflow.step',
        string='Current Step (Legacy)',
        tracking=True,
        readonly=True,
    )
    current_node_id = fields.Many2one(
        'cba.workflow.node',
        string='Current BPMN Node',
        tracking=True,
        readonly=True,
    )
    current_step_name = fields.Char(
        compute='_compute_current_labels',
        string='Current Step Label',
        readonly=True,
        store=True,
    )
    current_lane = fields.Selection(
        related='current_step_id.lane',
        string='Current Lane',
        readonly=True,
    )
    current_bpmn_id = fields.Char(
        compute='_compute_current_labels',
        string='Current BPMN ID',
        readonly=True,
        store=True,
    )
    step_line_ids = fields.One2many(
        'cba.case.step.line',
        'case_id',
        string='Process Steps',
    )
    payment_consent = fields.Selection([
        ('yes', 'Consent Given'),
        ('no', 'Consent Refused'),
    ], string='Payment Consent', tracking=True,
       help='Recorded at the Payment Consent gateway in the BPMN flow.')
    bpmn_highlight_json = fields.Char(
        string='BPMN Highlight JSON',
        compute='_compute_bpmn_highlight_json',
        store=False,
    )
    progress_percent = fields.Float(
        string='Progress %',
        compute='_compute_progress_percent',
        store=True,
    )
    description = fields.Text(string='Description')
    photo_ids = fields.One2many(
        'cba.step.photo',
        'case_id',
        string='All Photos',
    )

    @api.depends(
        'current_step_id', 'current_step_id.name', 'current_step_id.bpmn_id',
        'current_node_id', 'current_node_id.name', 'current_node_id.bpmn_id',
    )
    def _compute_current_labels(self):
        for case in self:
            if case.current_node_id:
                case.current_step_name = case.current_node_id.name
                case.current_bpmn_id = case.current_node_id.bpmn_id
            elif case.current_step_id:
                case.current_step_name = case.current_step_id.name
                case.current_bpmn_id = case.current_step_id.bpmn_id
            else:
                case.current_step_name = False
                case.current_bpmn_id = False

    @api.model
    def _default_workflow_id(self):
        return self.env['cba.workflow'].search([('is_default', '=', True)], limit=1).id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if (
            self.project_id
            and self.village_id
            and self.project_id.district_id
            and self.village_id.district_id != self.project_id.district_id
        ):
            self.village_id = False

    @api.constrains('project_id', 'village_id')
    def _check_village_in_project_district(self):
        for case in self:
            if (
                case.project_id
                and case.project_id.district_id
                and case.village_id
                and case.village_id.district_id != case.project_id.district_id
            ):
                raise ValidationError(_(
                    'Village "%s" is not in project district "%s".',
                    case.village_id.name,
                    case.project_id.district_id.name,
                ))

    @api.depends('village_id', 'village_id.district_id', 'village_id.tehsil_id')
    def _compute_location(self):
        for record in self:
            if record.village_id:
                record.district_id = record.village_id.district_id
                record.tehsil_id = record.village_id.tehsil_id
            else:
                record.district_id = False
                record.tehsil_id = False

    @api.depends('step_line_ids.status')
    def _compute_progress_percent(self):
        for case in self:
            lines = case.step_line_ids.filtered(
                lambda l: l.step_type not in ('start', 'end', 'gateway')
            )
            if not lines:
                case.progress_percent = 0.0
                continue
            done = len(lines.filtered(lambda l: l.status in ('done', 'skipped')))
            case.progress_percent = round(100.0 * done / len(lines), 1)

    @api.depends('current_node_id', 'current_step_id', 'step_line_ids.status', 'step_line_ids.bpmn_id')
    def _compute_bpmn_highlight_json(self):
        for case in self:
            completed = case.step_line_ids.filtered(
                lambda l: l.status == 'done'
            ).mapped('bpmn_id')
            current = case.current_bpmn_id or False
            payload = {
                'current': current,
                'completed': completed,
                'workflow_id': case.workflow_id.id if case.workflow_id else False,
            }
            case.bpmn_highlight_json = json.dumps(payload)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = seq.next_by_code('cba.case') or _('New')
        records = super().create(vals_list)
        records._init_step_lines()
        return records

    def _init_step_lines(self):
        """Create step lines from workflow nodes or legacy master steps."""
        Step = self.env['cba.workflow.step']
        for case in self:
            if case.step_line_ids:
                continue
            if case.workflow_id and case.workflow_id.node_ids:
                case._init_step_lines_from_workflow()
                continue
            steps = Step.search([
                ('parent_id', '=', False),
                ('active', '=', True),
            ], order='sequence, id')
            lines = []
            for step in steps:
                status = 'pending'
                if step.step_type == 'start':
                    status = 'in_progress'
                lines.append((0, 0, {
                    'step_id': step.id,
                    'status': status,
                }))
            case.write({
                'step_line_ids': lines,
                'current_step_id': steps[:1].id if steps else False,
            })

    def _init_step_lines_from_workflow(self):
        self.ensure_one()
        nodes = self.workflow_id.node_ids.filtered(
            lambda n: n.node_type in ('start', 'task', 'gateway', 'end')
        ).sorted('sequence')
        lines = []
        start_node = nodes.filtered(lambda n: n.node_type == 'start')[:1]
        for node in nodes:
            status = 'pending'
            if node == start_node:
                status = 'in_progress'
            lines.append((0, 0, {
                'node_id': node.id,
                'status': status,
            }))
        self.write({
            'step_line_ids': lines,
            'current_node_id': start_node.id if start_node else False,
            'current_step_id': False,
        })

    def action_start_process(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft cases can be started.'))
        if self.workflow_id and self.current_node_id:
            start_line = self.step_line_ids.filtered(
                lambda l: l.node_id and l.node_id.node_type == 'start'
            )[:1]
            if start_line:
                start_line.write({
                    'status': 'done',
                    'completed_on': fields.Datetime.now(),
                    'completed_by_id': self.env.user.id,
                })
            next_node = self._resolve_next_node(self.current_node_id)
            self._activate_node(next_node)
        else:
            start_line = self.step_line_ids.filtered(
                lambda l: l.step_id and l.step_id.step_type == 'start'
            )[:1]
            if start_line:
                start_line.write({
                    'status': 'done',
                    'completed_on': fields.Datetime.now(),
                    'completed_by_id': self.env.user.id,
                })
            next_step = self._get_next_step_after(self.current_step_id)
            self._activate_step(next_step)
        self.state = 'in_progress'
        self.message_post(body=_('CBA master process started.'))
        return True

    def action_complete_current_step(self):
        """Complete the active BPMN step and advance the case."""
        self.ensure_one()
        if self.state not in ('draft', 'in_progress'):
            raise UserError(_('This case is not active.'))
        if not self.current_step_id and not self.current_node_id:
            raise UserError(_('No active step on this case.'))
        if self.current_node_id:
            return self._complete_current_node()
        current_line = self._get_step_line(self.current_step_id)
        if not current_line:
            raise UserError(_('Step line missing for the current step.'))
        if current_line.requires_photo and not current_line.photo_ids:
            raise ValidationError(_(
                'Please attach at least one site photo before completing "%s".',
                current_line.name,
            ))
        if current_line.step_type == 'gateway':
            if not self.payment_consent:
                raise ValidationError(_(
                    'Select Payment Consent (Yes/No) before completing the gateway step.'
                ))
        current_line.write({
            'status': 'done',
            'completed_on': fields.Datetime.now(),
            'completed_by_id': self.env.user.id,
        })
        old_step = self.current_step_id
        old_step_name = old_step.name
        if old_step.step_type == 'gateway':
            self._apply_gateway_branch_skips(old_step)
        next_step = self._resolve_next_step(old_step)
        if next_step and next_step.step_type == 'end':
            end_line = self._get_step_line(next_step)
            if end_line:
                end_line.write({
                    'status': 'done',
                    'completed_on': fields.Datetime.now(),
                    'completed_by_id': self.env.user.id,
                })
            self.write({
                'current_step_id': next_step.id,
                'state': 'completed',
            })
            self.message_post(body=_('Process closed — all steps completed.'))
        elif next_step:
            self._activate_step(next_step)
            self.message_post(body=_(
                'Step "%s" completed. Now at "%s".',
                old_step_name,
                next_step.name,
            ))
        else:
            self.state = 'completed'
            self.message_post(body=_('Process completed.'))
        return True

    def _complete_current_node(self):
        self.ensure_one()
        current_line = self._get_node_line(self.current_node_id)
        if not current_line:
            raise UserError(_('Step line missing for the current node.'))
        if current_line.requires_photo and not current_line.photo_ids:
            raise ValidationError(_(
                'Please attach at least one site photo before completing "%s".',
                current_line.name,
            ))
        if current_line.step_type == 'gateway':
            outgoing = self._get_matching_transitions(self.current_node_id)
            if not outgoing:
                raise ValidationError(_(
                    'No valid transition from gateway "%s". Check conditions on transfers.',
                    current_line.name,
                ))
        current_line.write({
            'status': 'done',
            'completed_on': fields.Datetime.now(),
            'completed_by_id': self.env.user.id,
        })
        old_node = self.current_node_id
        old_name = old_node.name
        next_node = self._resolve_next_node(old_node)
        if next_node and next_node.node_type == 'end':
            end_line = self._get_node_line(next_node)
            if end_line:
                end_line.write({
                    'status': 'done',
                    'completed_on': fields.Datetime.now(),
                    'completed_by_id': self.env.user.id,
                })
            self.write({'current_node_id': next_node.id, 'state': 'completed'})
            self.message_post(body=_('Process closed — all steps completed.'))
        elif next_node:
            self._activate_node(next_node)
            self.message_post(body=_(
                'Step "%s" completed. Now at "%s".',
                old_name,
                next_node.name,
            ))
        else:
            self.state = 'completed'
            self.message_post(body=_('Process completed.'))
        return True

    def action_send_back_step(self):
        """Move back to the previous completed step."""
        self.ensure_one()
        if not self.current_step_id and not self.current_node_id:
            raise UserError(_('No current step to send back from.'))
        current_seq = (
            self.current_node_id.sequence if self.current_node_id
            else self.current_step_id.sequence
        )
        prev_lines = self.step_line_ids.filtered(
            lambda l: l.sequence < current_seq and l.status == 'done'
        ).sorted('sequence', reverse=True)
        if not prev_lines:
            raise UserError(_('No previous step to return to.'))
        prev_line = prev_lines[0]
        if self.current_node_id:
            current_line = self._get_node_line(self.current_node_id)
            if current_line and current_line.status == 'in_progress':
                current_line.status = 'pending'
            self._activate_node(prev_line.node_id)
        else:
            prev_step = prev_line.step_id
            current_line = self._get_step_line(self.current_step_id)
            if current_line and current_line.status == 'in_progress':
                current_line.status = 'pending'
            self._activate_step(prev_step)
        self.state = 'in_progress'
        self.message_post(body=_('Sent back to step "%s".', prev_line.name))
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True

    def _get_step_line(self, step):
        self.ensure_one()
        return self.step_line_ids.filtered(lambda l: l.step_id == step)[:1]

    def _get_node_line(self, node):
        self.ensure_one()
        return self.step_line_ids.filtered(lambda l: l.node_id == node)[:1]

    def _activate_step(self, step):
        self.ensure_one()
        if not step:
            return
        for line in self.step_line_ids:
            if line.step_id == step:
                line.write({
                    'status': 'in_progress',
                    'started_on': line.started_on or fields.Datetime.now(),
                })
            elif line.status == 'in_progress' and line.step_id != step:
                line.status = 'pending'
        self.current_step_id = step.id
        if self.state == 'draft':
            self.state = 'in_progress'

    def _activate_node(self, node):
        self.ensure_one()
        if not node:
            return
        for line in self.step_line_ids:
            if line.node_id == node:
                line.write({
                    'status': 'in_progress',
                    'started_on': line.started_on or fields.Datetime.now(),
                })
            elif line.status == 'in_progress' and line.node_id != node:
                line.status = 'pending'
        self.write({'current_node_id': node.id, 'current_step_id': False})
        if self.state == 'draft':
            self.state = 'in_progress'

    def _eval_transition_condition(self, transition):
        self.ensure_one()
        expr = (transition.condition or 'True').strip()
        if not expr or expr == 'True':
            return True
        ctx = {
            'self': self,
            'case': self,
            'user': self.env.user,
            'payment_consent': self.payment_consent,
        }
        try:
            return bool(safe_eval(expr, ctx))
        except Exception:
            return False

    def _get_matching_transitions(self, from_node):
        self.ensure_one()
        transitions = self.env['cba.workflow.transition'].search([
            ('workflow_id', '=', self.workflow_id.id),
            ('from_node_id', '=', from_node.id),
        ], order='sequence, id')
        return transitions.filtered(lambda t: self._eval_transition_condition(t))

    def _resolve_next_node(self, node):
        self.ensure_one()
        if not node:
            return False
        matches = self._get_matching_transitions(node)
        return matches[:1].to_node_id if matches else False

    def _resolve_next_step(self, step):
        self.ensure_one()
        if not step:
            return False
        if step.step_type == 'gateway':
            if self.payment_consent == 'yes':
                return step.next_step_yes_id
            if self.payment_consent == 'no':
                return step.next_step_no_id
            return False
        return self._get_next_step_after(step)

    def _get_next_step_after(self, step):
        if not step:
            return False
        if step.next_step_id:
            return step.next_step_id
        Step = self.env['cba.workflow.step']
        return Step.search([
            ('parent_id', '=', False),
            ('active', '=', True),
            ('sequence', '>', step.sequence),
        ], order='sequence, id', limit=1)

    def _apply_gateway_branch_skips(self, gateway_step):
        """Mark steps on the non-taken gateway branch as skipped."""
        self.ensure_one()
        if gateway_step.bpmn_id != 'Gateway_Payment_Consent':
            return
        if self.payment_consent == 'yes':
            skip_ids = [
                'Task_Initiate_PTT_Deposit',
                'Task_HQ_Approval_PTT',
                'Task_Deposit_PTT',
                'Task_PTT_Hold_Funds',
            ]
        elif self.payment_consent == 'no':
            skip_ids = ['Task_Receive_Compensation']
        else:
            return
        lines = self.step_line_ids.filtered(
            lambda l: l.bpmn_id in skip_ids and l.status == 'pending'
        )
        lines.write({'status': 'skipped'})

    @api.model
    def get_bpmn_case_state(self, case_id):
        """RPC for BPMN viewer — highlight data for a case."""
        case = self.browse(case_id)
        if not case.exists():
            return {'current': False, 'completed': [], 'workflow_id': False}
        return json.loads(case.bpmn_highlight_json or '{}')
