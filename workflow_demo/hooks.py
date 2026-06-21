# -*- coding: utf-8 -*-

import logging
import os

from odoo.modules.module import get_module_path

_logger = logging.getLogger(__name__)

_LEGACY_MODEL_PREFIX = 'bhu.cba.'


def pre_init_hook(env):
    """Drop leftover tables/metadata from earlier builds that used bhu.cba.* models."""
    _purge_legacy_cba(env.cr)
    _logger.info('cba pre_init: legacy bhu.cba metadata purged')


def _purge_legacy_cba(cr):
    cr.execute("""
        SELECT table_name
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name LIKE 'bhu_cba_%'
    """)
    for (table_name,) in cr.fetchall():
        cr.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
        _logger.info('cba pre_init: dropped legacy table %s', table_name)

    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'bhuarjan_cba_core'
           AND model LIKE %s
    """, (_LEGACY_MODEL_PREFIX + '%',))
    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE model LIKE %s
    """, (_LEGACY_MODEL_PREFIX + '%',))
    cr.execute("""
        DELETE FROM ir_model
         WHERE model LIKE %s
    """, (_LEGACY_MODEL_PREFIX + '%',))
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'bhuarjan_cba_core'
           AND name LIKE 'model_bhu_cba_%'
    """)


def post_init_hook(env):
    """Load bundled BPMN XML into default definition and workflow designer records."""
    module_path = get_module_path('bhuarjan_cba_core')
    if not module_path:
        return
    bpmn_path = os.path.join(
        module_path,
        'static',
        'src',
        'bpmn',
        'lr-department-master-process.bpmn',
    )
    if not os.path.isfile(bpmn_path):
        return
    with open(bpmn_path, encoding='utf-8') as handle:
        xml_content = handle.read()

    Definition = env['cba.bpmn.definition']
    record = Definition.search([('is_default', '=', True)], limit=1)
    if record:
        record.write({'bpmn_xml': xml_content})
    else:
        Definition.create({
            'name': 'SECL L and R Master SOP',
            'process_id': 'LR_Master_Process',
            'is_default': True,
            'bpmn_xml': xml_content,
        })

    Workflow = env['cba.workflow']
    wf = env.ref('bhuarjan_cba_core.cba_workflow_lr_master_sop', raise_if_not_found=False)
    if not wf:
        wf = Workflow.search([('is_default', '=', True)], limit=1)
    if wf:
        wf.write({'bpmn_xml': xml_content, 'state': 'active'})
        try:
            wf._sync_nodes_and_transitions_from_xml(xml_content)
        except Exception as exc:
            _logger.warning('cba post_init: workflow sync skipped: %s', exc)
