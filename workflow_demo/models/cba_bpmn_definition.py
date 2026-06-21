# -*- coding: utf-8 -*-

import os

from odoo import models, fields, api, _
from odoo.modules.module import get_module_path


class CbaBpmnDefinition(models.Model):
    """Stores the BPMN diagram XML for the CBA master process."""
    _name = 'cba.bpmn.definition'
    _description = 'CBA BPMN Definition'
    _rec_name = 'name'

    name = fields.Char(string='Diagram Name', required=True, default='SECL L and R Master SOP')
    process_id = fields.Char(
        string='BPMN Process ID',
        default='LR_Master_Process',
        help='Root process id inside the BPMN file.',
    )
    bpmn_xml = fields.Text(string='BPMN XML', required=True)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(string='Default Diagram', default=False)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'BPMN definition name must be unique.'),
    ]

    @api.model
    def get_default_bpmn_xml(self):
        """Return XML from the bundled BPMN file or the default stored record."""
        record = self.search([('is_default', '=', True), ('active', '=', True)], limit=1)
        if record and record.bpmn_xml:
            return record.bpmn_xml
        module_path = get_module_path('bhuarjan_cba_core')
        if not module_path:
            return ''
        bpmn_path = os.path.join(
            module_path,
            'static',
            'src',
            'bpmn',
            'lr-department-master-process.bpmn',
        )
        if os.path.isfile(bpmn_path):
            with open(bpmn_path, encoding='utf-8') as handle:
                return handle.read()
        return record.bpmn_xml if record else ''

    @api.model
    def get_bpmn_viewer_payload(self):
        """RPC payload for the BPMN viewer widget."""
        return {
            'bpmn_xml': self.get_default_bpmn_xml(),
            'process_id': 'LR_Master_Process',
        }
