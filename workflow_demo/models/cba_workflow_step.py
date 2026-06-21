# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class CbaWorkflowStep(models.Model):
    """Master definition of a BPMN node in the SECL L&R Master SOP."""
    _name = 'cba.workflow.step'
    _description = 'CBA Workflow Step'
    _order = 'sequence, id'

    name = fields.Char(string='Step Name', required=True, translate=True)
    bpmn_id = fields.Char(
        string='BPMN Element ID',
        required=True,
        index=True,
        help='Technical id from the BPMN diagram (e.g. Task_S4_Notification).',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    lane = fields.Selection([
        ('central', 'Ministry of Coal / Central Govt'),
        ('area', 'Area L and R / Project Office'),
        ('state', 'State Revenue / SDM / Collector'),
        ('committees', 'Committees'),
        ('hq', 'SECL HQ'),
        ('pap', 'PAP / Landowner'),
        ('tribunal', 'Part-Time Tribunal Bilaspur'),
    ], string='Lane / Responsible Party')
    step_type = fields.Selection([
        ('start', 'Start Event'),
        ('task', 'Task'),
        ('subprocess', 'Sub-Process'),
        ('gateway', 'Gateway'),
        ('end', 'End Event'),
    ], string='BPMN Type', default='task', required=True)
    parent_id = fields.Many2one(
        'cba.workflow.step',
        string='Parent Sub-Process',
        ondelete='cascade',
        index=True,
    )
    child_ids = fields.One2many(
        'cba.workflow.step',
        'parent_id',
        string='Sub-Steps',
    )
    requires_photo = fields.Boolean(
        string='Requires Site Photo',
        help='When enabled, at least one photo must be attached before completing this step.',
    )
    next_step_id = fields.Many2one(
        'cba.workflow.step',
        string='Default Next Step',
        ondelete='set null',
    )
    next_step_yes_id = fields.Many2one(
        'cba.workflow.step',
        string='Next Step (Yes / Consent)',
        ondelete='set null',
    )
    next_step_no_id = fields.Many2one(
        'cba.workflow.step',
        string='Next Step (No / Refusal)',
        ondelete='set null',
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Instructions')

    _sql_constraints = [
        ('bpmn_id_unique', 'unique(bpmn_id)', 'BPMN element id must be unique.'),
    ]

    def name_get(self):
        result = []
        for step in self:
            label = step.name or step.bpmn_id
            if step.lane:
                lane_label = dict(self._fields['lane'].selection).get(step.lane, '')
                label = f'[{lane_label}] {label}'
            result.append((step.id, label))
        return result
