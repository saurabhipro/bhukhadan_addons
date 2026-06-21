# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def _purge_legacy_cba(cr):
    cr.execute("""
        SELECT table_name
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name LIKE 'bhu_cba_%'
    """)
    for (table_name,) in cr.fetchall():
        cr.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
        _logger.info('Dropped legacy CBA table %s', table_name)

    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'bhuarjan_cba_core'
           AND model LIKE 'bhu.cba.%%'
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE model LIKE 'bhu.cba.%%'
    """)
    cr.execute("""
        DELETE FROM ir_model
         WHERE model LIKE 'bhu.cba.%%'
    """)


def migrate(cr, version):
    _purge_legacy_cba(cr)
