# -*- coding: utf-8 -*-

import logging
import re
import xml.etree.ElementTree as ET

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

BPMN_NS = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL'}
NODE_TAGS = {
    'startEvent': 'start',
    'endEvent': 'end',
    'task': 'task',
    'userTask': 'task',
    'serviceTask': 'task',
    'scriptTask': 'task',
    'exclusiveGateway': 'gateway',
    'parallelGateway': 'gateway',
    'inclusiveGateway': 'gateway',
    'subProcess': 'subprocess',
}


class CbaWorkflow(models.Model):
    """BPMN workflow definition with visual designer, nodes and transitions."""
    _name = 'cba.workflow'
    _description = 'CBA Workflow Definition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string='Code', tracking=True)
    description = fields.Text()
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        ondelete='set null',
        tracking=True,
        help='Optional Odoo model this workflow can be started on.',
    )
    model_name = fields.Char(related='model_id.model', store=True, readonly=True)
    bpmn_xml = fields.Text(string='BPMN Diagram XML')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], default='draft', required=True, tracking=True)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(
        string='Default L&R SOP',
        help='Used automatically for new CBA cases when no workflow is chosen.',
    )
    node_ids = fields.One2many('cba.workflow.node', 'workflow_id', string='Nodes / States')
    transition_ids = fields.One2many('cba.workflow.transition', 'workflow_id', string='Transfers')
    node_count = fields.Integer(compute='_compute_counts')
    transition_count = fields.Integer(compute='_compute_counts')
    case_ids = fields.One2many('cba.case', 'workflow_id', string='Cases')

    @api.depends('node_ids', 'transition_ids')
    def _compute_counts(self):
        for wf in self:
            wf.node_count = len(wf.node_ids)
            wf.transition_count = len(wf.transition_ids)

    def action_set_active(self):
        self.write({'state': 'active'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_sync_from_bpmn(self):
        """Parse BPMN XML and upsert node + transition records."""
        for wf in self:
            if not wf.bpmn_xml or not wf.bpmn_xml.strip():
                raise UserError(_('Save or import a BPMN diagram first.'))
            wf._sync_nodes_and_transitions_from_xml(wf.bpmn_xml)
        return True

    def sync_bpmn_xml(self, bpmn_xml):
        """Save diagram XML from the modeler and sync nodes/transfers in one step."""
        self.ensure_one()
        if not bpmn_xml or not bpmn_xml.strip():
            raise ValidationError(_('BPMN XML cannot be empty.'))
        self.write({'bpmn_xml': bpmn_xml})
        self._sync_nodes_and_transitions_from_xml(bpmn_xml)
        return {
            'node_count': len(self.node_ids),
            'transition_count': len(self.transition_ids),
        }

    def _sync_nodes_and_transitions_from_xml(self, bpmn_xml):
        self.ensure_one()
        nodes_data, flows_data = self._parse_bpmn(bpmn_xml)
        Node = self.env['cba.workflow.node']
        Transition = self.env['cba.workflow.transition']

        existing_nodes = {n.bpmn_id: n for n in self.node_ids}
        seen_node_ids = set()
        seq = 10
        for nd in nodes_data:
            vals = {
                'name': nd['name'],
                'bpmn_id': nd['bpmn_id'],
                'node_type': nd['node_type'],
                'sequence': seq,
            }
            seq += 10
            if nd['bpmn_id'] in existing_nodes:
                existing_nodes[nd['bpmn_id']].write(vals)
            else:
                Node.create(dict(vals, workflow_id=self.id))
            seen_node_ids.add(nd['bpmn_id'])

        orphan_nodes = self.node_ids.filtered(lambda n: n.bpmn_id not in seen_node_ids)

        node_map = {n.bpmn_id: n.id for n in self.node_ids}
        existing_flows = {t.bpmn_flow_id: t for t in self.transition_ids if t.bpmn_flow_id}
        seen_flow_ids = set()
        fseq = 10
        for fl in flows_data:
            from_id = node_map.get(fl['from_bpmn_id'])
            to_id = node_map.get(fl['to_bpmn_id'])
            if not from_id or not to_id:
                continue
            vals = {
                'name': fl['name'],
                'from_node_id': from_id,
                'to_node_id': to_id,
                'bpmn_flow_id': fl['bpmn_flow_id'],
                'sequence': fseq,
            }
            fseq += 10
            if fl['bpmn_flow_id'] in existing_flows:
                existing_flows[fl['bpmn_flow_id']].write(vals)
            else:
                Transition.create(dict(vals, workflow_id=self.id))
            seen_flow_ids.add(fl['bpmn_flow_id'])

        orphan_flows = self.transition_ids.filtered(
            lambda t: t.bpmn_flow_id and t.bpmn_flow_id not in seen_flow_ids
        )
        stale_flows = self.transition_ids.filtered(
            lambda t: t.from_node_id.bpmn_id not in seen_node_ids
            or t.to_node_id.bpmn_id not in seen_node_ids
        )
        (orphan_flows | stale_flows).unlink()

        if orphan_nodes:
            orphan_nodes.unlink()

        self.message_post(body=_(
            'Synced %s node(s) and %s transition(s) from BPMN.',
            len(seen_node_ids), len(seen_flow_ids),
        ))

    @staticmethod
    def _bpmn_local_tag(elem):
        return elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

    @api.model
    def _parse_bpmn(self, bpmn_xml):
        try:
            root = ET.fromstring(bpmn_xml)
        except ET.ParseError as exc:
            raise UserError(_('Invalid BPMN XML: %s') % exc) from exc

        process = root.find('.//bpmn:process', BPMN_NS)
        if process is None:
            process = root.find('.//{http://www.omg.org/spec/BPMN/20100524/MODEL}process')
        if process is None:
            for elem in root.iter():
                if elem.tag.endswith('process'):
                    process = elem
                    break
        if process is None:
            raise UserError(_('No BPMN process element found in the diagram.'))

        nodes_data = []
        seen_bpmn_ids = set()
        for elem in process.iter():
            tag = self._bpmn_local_tag(elem)
            if tag not in NODE_TAGS:
                continue
            bpmn_id = elem.get('id')
            if not bpmn_id or bpmn_id in seen_bpmn_ids:
                continue
            seen_bpmn_ids.add(bpmn_id)
            name = elem.get('name') or bpmn_id
            nodes_data.append({
                'bpmn_id': bpmn_id,
                'name': name,
                'node_type': NODE_TAGS[tag],
            })

        flows_data = []
        seen_flow_ids = set()
        for elem in process.iter():
            if self._bpmn_local_tag(elem) != 'sequenceFlow':
                continue
            flow_id = elem.get('id')
            source = elem.get('sourceRef')
            target = elem.get('targetRef')
            if not flow_id or not source or not target or flow_id in seen_flow_ids:
                continue
            seen_flow_ids.add(flow_id)
            flows_data.append({
                'bpmn_flow_id': flow_id,
                'name': elem.get('name') or flow_id,
                'from_bpmn_id': source,
                'to_bpmn_id': target,
            })

        return nodes_data, flows_data

    @staticmethod
    def _bpmn_element_type_to_node_type(element_type):
        mapping = {
            'bpmn:StartEvent': 'start',
            'bpmn:EndEvent': 'end',
            'bpmn:ExclusiveGateway': 'gateway',
            'bpmn:ParallelGateway': 'gateway',
            'bpmn:InclusiveGateway': 'gateway',
            'bpmn:SubProcess': 'subprocess',
        }
        if element_type in mapping:
            return mapping[element_type]
        if element_type and 'Task' in element_type:
            return 'task'
        return 'task'

    def action_open_node_by_bpmn_element(self, bpmn_element_id, element_type=None, element_name=None):
        """Open node activity popup for a BPMN canvas element (double-click)."""
        self.ensure_one()
        if not bpmn_element_id:
            raise UserError(_('No BPMN element selected.'))
        node = self.node_ids.filtered(lambda n: n.bpmn_id == bpmn_element_id)[:1]
        if not node:
            node = self.env['cba.workflow.node'].create({
                'workflow_id': self.id,
                'bpmn_id': bpmn_element_id,
                'name': element_name or bpmn_element_id,
                'node_type': self._bpmn_element_type_to_node_type(element_type),
            })
        view = self.env.ref('bhuarjan_cba_core.view_cba_workflow_node_popup')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Open: Activity'),
            'res_model': 'cba.workflow.node',
            'res_id': node.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
            'context': {
                'bpmn_element_id': bpmn_element_id,
            },
        }

    def _get_or_create_node_by_bpmn_id(self, bpmn_id, element_name=None, element_type=None):
        self.ensure_one()
        node = self.node_ids.filtered(lambda n: n.bpmn_id == bpmn_id)[:1]
        if node:
            return node
        return self.env['cba.workflow.node'].create({
            'workflow_id': self.id,
            'bpmn_id': bpmn_id,
            'name': element_name or bpmn_id,
            'node_type': self._bpmn_element_type_to_node_type(element_type),
        })

    def action_open_transition_by_bpmn_flow(
        self, bpmn_flow_id, flow_name=None, source_ref=None, target_ref=None,
    ):
        """Open transition popup for a BPMN sequence flow (click on connector line)."""
        self.ensure_one()
        if not bpmn_flow_id:
            raise UserError(_('No transition selected.'))
        transition = self.transition_ids.filtered(
            lambda t: t.bpmn_flow_id == bpmn_flow_id
        )[:1]
        if not transition:
            if not source_ref or not target_ref:
                raise UserError(_(
                    'This connector is not synced yet. Use Sync Nodes & Transfers '
                    'or draw a connection between two nodes first.',
                ))
            from_node = self._get_or_create_node_by_bpmn_id(source_ref)
            to_node = self._get_or_create_node_by_bpmn_id(target_ref)
            transition = self.env['cba.workflow.transition'].create({
                'workflow_id': self.id,
                'bpmn_flow_id': bpmn_flow_id,
                'name': flow_name or bpmn_flow_id,
                'from_node_id': from_node.id,
                'to_node_id': to_node.id,
                'condition': 'True',
            })
        view = self.env.ref('bhuarjan_cba_core.view_cba_workflow_transition_popup')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Open: Transition'),
            'res_model': 'cba.workflow.transition',
            'res_id': transition.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
            'context': {
                'bpmn_flow_id': bpmn_flow_id,
            },
        }

    @api.model
    def get_modeler_payload(self, workflow_id):
        wf = self.browse(workflow_id)
        if not wf.exists():
            return {'bpmn_xml': '', 'workflow_id': workflow_id}
        xml = wf.bpmn_xml or ''
        if not xml.strip():
            xml = self._default_empty_bpmn(wf.name)
        return {'bpmn_xml': xml, 'workflow_id': wf.id, 'name': wf.name}

    def save_bpmn_xml(self, bpmn_xml):
        self.ensure_one()
        if not bpmn_xml or not bpmn_xml.strip():
            raise ValidationError(_('BPMN XML cannot be empty.'))
        self.write({'bpmn_xml': bpmn_xml})
        return True

    @staticmethod
    def _default_empty_bpmn(name='New Workflow'):
        safe = re.sub(r'[^\w]', '_', name or 'Process')[:40]
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
  id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_{safe}" name="{name}" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1" name="Start"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_{safe}">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="180" y="160" width="36" height="36"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""


class CbaWorkflowNode(models.Model):
    """Workflow state / BPMN node."""
    _name = 'cba.workflow.node'
    _description = 'CBA Workflow Node'
    _order = 'sequence, id'

    workflow_id = fields.Many2one('cba.workflow', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True)
    bpmn_id = fields.Char(string='BPMN Element ID', required=True, index=True)
    node_type = fields.Selection([
        ('start', 'Start Event'),
        ('task', 'Task / State'),
        ('gateway', 'Gateway'),
        ('subprocess', 'Sub-Process'),
        ('end', 'End Event'),
    ], required=True, default='task')
    sequence = fields.Integer(default=10)
    join_mode = fields.Selection([
        ('or', 'Or'),
        ('and', 'And'),
    ], string='Join Mode', default='or')
    show_in_workflow = fields.Boolean(string='Show in Workflow Bar', default=True)
    calendar_notify = fields.Boolean(string='Calendar Event & Notify')
    no_decision = fields.Boolean(string='No Decision')
    trans_type = fields.Selection([
        ('auto', 'Auto Process'),
        ('need_note', 'Need Note'),
        ('todo', 'To-Do Task'),
        ('event', 'Event Detection'),
    ], string='Trans Type', default='auto', required=True)
    fill_color = fields.Char(string='Fill Color', default='#FFFFFF')
    stroke_color = fields.Char(string='Stroke Color', default='#000000')
    stroke_width = fields.Integer(string='Width of Stroke', default=1)
    audit_type = fields.Selection([
        ('approval', 'Approval'),
        ('counter_sign', 'Counter Sign'),
        ('notify', 'Notify'),
    ], string='Audit Type', default='approval')
    flow_role = fields.Char(string='Flow Roles')
    module_name = fields.Char(string='Module ID', help='Technical module name, e.g. crm.')
    task_model_id = fields.Many2one('ir.model', string='Model Name', ondelete='set null')
    real_id = fields.Char(string='Real ID', default='self.id')
    view_id = fields.Many2one('ir.ui.view', string='Model View', ondelete='set null')
    menu_id = fields.Many2one('ir.ui.menu', string='Menu', ondelete='set null')
    task_condition = fields.Char(string='Task Condition', default='False')
    action_context = fields.Char(string='Context')
    requires_photo = fields.Boolean(string='Requires Photo')
    python_action = fields.Text(string='Python Action',
                               help='Python code executed when entering this node.')
    action_args = fields.Char(string='Action Args')
    group_ids = fields.Many2many('res.groups', string='Allowed Groups')
    user_ids = fields.Many2many('res.users', string='Allowed Users')
    description = fields.Text()
    outgoing_ids = fields.One2many(
        'cba.workflow.transition', 'from_node_id', string='Outgoing Transfers',
    )
    incoming_ids = fields.One2many(
        'cba.workflow.transition', 'to_node_id', string='Incoming Transfers',
    )
    target_model_id = fields.Many2one(
        'ir.model',
        related='workflow_id.model_id',
        string='Target Model',
        readonly=True,
    )
    field_line_ids = fields.One2many(
        'cba.workflow.node.field', 'node_id', string='Field Rules',
    )

    _sql_constraints = [
        ('bpmn_id_workflow_unique', 'unique(workflow_id, bpmn_id)',
         'BPMN element id must be unique per workflow.'),
    ]

    def _get_field_config_model(self):
        self.ensure_one()
        return self.workflow_id.model_id or self.task_model_id

    def action_load_model_fields(self):
        """Populate field rules from the workflow target model."""
        FieldLine = self.env['cba.workflow.node.field']
        for node in self:
            model = node._get_field_config_model()
            if not model:
                raise UserError(_(
                    'Set a target model on the workflow first (Configuration tab on the workflow).',
                ))
            domain = [
                ('model_id', '=', model.id),
                ('ttype', 'not in', ['one2many', 'many2many', 'binary']),
            ]
            model_fields = self.env['ir.model.fields'].search(domain, order='name')
            existing = {line.field_id.id for line in node.field_line_ids}
            seq = (max(node.field_line_ids.mapped('sequence') or [0]) // 10 + 1) * 10
            to_create = []
            for field in model_fields:
                if field.id in existing:
                    continue
                to_create.append({
                    'node_id': node.id,
                    'field_id': field.id,
                    'sequence': seq,
                })
                seq += 10
            if to_create:
                FieldLine.create(to_create)
        return True

    def action_all_to_readonly(self):
        self.mapped('field_line_ids').write({'readonly': True})
        return True


class CbaWorkflowNodeField(models.Model):
    """Per-node field visibility and edit rules for the target business model."""
    _name = 'cba.workflow.node.field'
    _description = 'CBA Workflow Node Field Rule'
    _order = 'sequence, id'

    node_id = fields.Many2one(
        'cba.workflow.node', required=True, ondelete='cascade', index=True,
    )
    target_model_id = fields.Many2one(
        'ir.model',
        related='node_id.workflow_id.model_id',
        store=True,
        readonly=True,
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', target_model_id)]",
    )
    readonly = fields.Boolean(string='Readonly')
    is_required = fields.Boolean(string='Required')
    invisible = fields.Boolean(string='Invisible')
    group_ids = fields.Many2many(
        'res.groups', 'cba_node_field_group_rel', 'line_id', 'group_id',
        string='Groups',
    )
    user_ids = fields.Many2many(
        'res.users', 'cba_node_field_user_rel', 'line_id', 'user_id',
        string='Users',
    )
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('node_field_unique', 'unique(node_id, field_id)',
         'Each field can only be configured once per activity.'),
    ]


class CbaWorkflowTransition(models.Model):
    """Workflow transfer / BPMN sequence flow."""
    _name = 'cba.workflow.transition'
    _description = 'CBA Workflow Transition'
    _order = 'sequence, id'

    workflow_id = fields.Many2one('cba.workflow', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True, default='Transfer')
    bpmn_flow_id = fields.Char(string='BPMN Flow ID', index=True)
    from_node_id = fields.Many2one(
        'cba.workflow.node', string='From Node', required=True,
        ondelete='cascade', domain="[('workflow_id', '=', workflow_id)]",
    )
    to_node_id = fields.Many2one(
        'cba.workflow.node', string='To Node', required=True,
        ondelete='cascade', domain="[('workflow_id', '=', workflow_id)]",
    )
    condition = fields.Char(
        string='Condition',
        default='True',
        help='Python expression evaluated on the business record. Use True for unconditional.',
    )
    trans_type = fields.Selection([
        ('auto', 'Auto Process'),
        ('need_note', 'Need Note'),
        ('todo', 'To-Do Task'),
        ('event', 'Event Detection'),
    ], string='Transfer Type', default='auto', required=True)
    group_ids = fields.Many2many('res.groups', 'cba_transition_group_rel', 'transition_id', 'group_id')
    user_ids = fields.Many2many('res.users', 'cba_transition_user_rel', 'transition_id', 'user_id')
    stroke_color = fields.Char(string='Stroke Color', default='#546E7A')
    stroke_width = fields.Integer(string='Stroke Width', default=1)
    is_reverse = fields.Boolean(string='Is Reverse')
    sequence = fields.Integer(default=10)

    @api.constrains('from_node_id', 'to_node_id', 'workflow_id')
    def _check_nodes_same_workflow(self):
        for rec in self:
            if rec.from_node_id.workflow_id != rec.workflow_id:
                raise ValidationError(_('From node must belong to the same workflow.'))
            if rec.to_node_id.workflow_id != rec.workflow_id:
                raise ValidationError(_('To node must belong to the same workflow.'))
