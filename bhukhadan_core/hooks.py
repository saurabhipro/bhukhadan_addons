# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def _docvault_cleanup_active_line_fk(cr):
    """Drop legacy Many2one FK; plain Integer field must accept NULL/0."""
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'bhu_document_vault_navigator'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE bhu_document_vault_navigator
           SET active_variant_line_id = NULL
         WHERE active_variant_line_id = 0
            OR (active_variant_line_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                      FROM bhu_document_vault_navigator_line AS l
                     WHERE l.id = bhu_document_vault_navigator.active_variant_line_id
                ))
    """)
    cr.execute("""
        ALTER TABLE bhu_document_vault_navigator
        DROP CONSTRAINT IF EXISTS bhu_document_vault_navigator_active_variant_line_id_fkey
    """)
    _logger.info("docvault: active_variant_line_id FK dropped / stale refs cleared")


def pre_init_hook(env):
    """Clean Spiffy legacy ``backend.config`` schema/metadata before bhuarjan loads.

    We do NOT register ``backend.config`` in bhuarjan (avoids ORM trying to add an
    integer FK on a varchar column). This hook only fixes the leftover table/metadata.
    """
    cr = env.cr
    _docvault_cleanup_active_line_fk(cr)

    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'backend_config'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        ALTER TABLE backend_config
        DROP CONSTRAINT IF EXISTS backend_config_google_font_family_fkey
    """)

    cr.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'backend_config'
          AND column_name = 'google_font_family'
    """)
    row = cr.fetchone()
    if row:
        dtype = row[0]
        if dtype in ('integer', 'bigint', 'smallint'):
            cr.execute("""
                ALTER TABLE backend_config
                ALTER COLUMN google_font_family TYPE varchar
                USING CASE
                    WHEN google_font_family IS NULL THEN NULL
                    ELSE google_font_family::text
                END
            """)
        elif dtype not in ('character varying', 'text'):
            cr.execute("""
                ALTER TABLE backend_config
                ALTER COLUMN google_font_family TYPE varchar
                USING google_font_family::text
            """)

    # Remove stale field metadata (any module) so nothing re-applies Many2one.
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model = 'ir.model.fields'
          AND res_id IN (
              SELECT id FROM ir_model_fields
              WHERE model = 'backend.config'
                AND name = 'google_font_family'
          )
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'backend.config'
          AND name = 'google_font_family'
    """)
    _logger.info(
        "pre_init_hook: backend_config.google_font_family cleaned (varchar, no FK)"
    )


def post_init_hook(env):
    """Lightweight post-init."""
    from odoo import fields
    try:
        Project = env['bhu.project'].sudo()
        if hasattr(Project, '_bhu_repair_stale_sdm_links'):
            cleared = Project._bhu_repair_stale_sdm_links()
            if cleared:
                _logger.info(
                    "post_init_hook: cleared stale SDM links on %s project(s) without sub division",
                    cleared,
                )
        elif hasattr(Project, '_bhu_sync_sdm_from_sub_division'):
            with_sub = Project.search([('sub_division_id', '!=', False)])
            if with_sub:
                with_sub._bhu_sync_sdm_from_sub_division()

        Voucher = env.get('bhu.payment.voucher')
        if Voucher and hasattr(Voucher, '_recompute_payment_files_status_all'):
            Voucher._recompute_payment_files_status_all()

        env.cr.execute("""
            UPDATE bhu_document_vault_navigator
               SET active_variant_line_id = NULL
             WHERE active_variant_line_id = 0
        """)
        _docvault_cleanup_active_line_fk(env.cr)
        env.cr.execute("""
            DELETE FROM bhu_document_vault_navigator_line
             WHERE step_no IS NULL
               AND COALESCE(section_label, '') = ''
               AND COALESCE(variant_label, '') = ''
        """)
        Navigator = env.get('bhu.document.vault.navigator')
        if Navigator:
            for nav in Navigator.sudo().search([
                ('project_id', '!=', False),
                ('village_id', '!=', False),
            ]):
                nav._sanitize_stale_selection()
                nav._refresh_section_lines()

        Photo = env.get('bhu.survey.photo')
        if Photo:
            from datetime import timedelta
            cutoff = fields.Datetime.now() - timedelta(days=120)
            surveys = env['bhu.survey'].sudo().search([
                ('create_date', '>=', cutoff),
            ])
            synced = 0
            for survey in surveys:
                before = len(survey.photo_ids)
                Photo.sync_from_s3_for_survey(survey)
                if len(survey.photo_ids) > before:
                    synced += 1
            if synced:
                _logger.info(
                    'post_init_hook: linked S3 photos for %s recent survey(s)',
                    synced,
                )
    except Exception as e:
        _logger.error("post_init_hook: %s", e, exc_info=True)
