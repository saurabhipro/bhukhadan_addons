# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def _mark_generated_scope(self, export_scope='all'):
        self.ensure_one()
        scope = export_scope or 'all'
        vals = {}
        if scope in ('all', 'land'):
            vals['land_generated'] = True
        if scope in ('all', 'asset'):
            vals['asset_generated'] = True
        if scope in ('all', 'tree'):
            vals['tree_generated'] = True
        if vals:
            self.write(vals)
        all_done = bool(self.land_generated and self.asset_generated and self.tree_generated)
        self.write({
            'is_generated': all_done,
            'state': 'approved' if all_done else 'draft',
        })

    def _mark_variant_generated(self, variant='standard'):
        self.ensure_one()
        var = (variant or 'standard').lower()
        if var == 'consolidated':
            self.write({'consolidated_generated': True})
        elif var == 'rr':
            self.write({'rr_generated': True})

    def _s23_set_loader_progress(self, done=None, total=None, label=None, active=None, flush=False):
        self.ensure_one()
        key = 'bhukhadan_core.s23.loader.progress.%s' % self.id
        user_key = 'bhukhadan_core.s23.loader.progress.user.%s' % self.env.uid
        vtype_raw = (self.village_type or (self.village_id.village_type if self.village_id else '') or '').lower()
        village_type_label = 'Urban / नगरीय' if vtype_raw == 'urban' else 'Rural / ग्रामीण'
        urban_body_label = self.get_urban_body_label() or '-'
        current = {}
        raw = self.env['ir.config_parameter'].sudo().get_param(key, default='') or ''
        if raw:
            try:
                current = json.loads(raw) if isinstance(raw, str) else {}
                if not isinstance(current, dict):
                    current = {}
            except Exception:
                current = {}
        done_val = max(0, int(done if done is not None else current.get('done') or 0))
        total_val = max(0, int(total if total is not None else current.get('total') or 0))
        pct_val = (100.0 * done_val / total_val) if total_val > 0 else float(current.get('pct') or 0.0)
        payload = {
            'active': bool(active) if active is not None else bool(current.get('active', True)),
            'done': done_val,
            'total': total_val,
            'pct': pct_val,
            'label': label if label is not None else (current.get('label') or ''),
            'project': self.project_id.name if self.project_id else '',
            'village': self.village_id.name if self.village_id else '',
            'village_type': village_type_label,
            'urban_body': urban_body_label,
        }
        try:
            if flush:
                # Write progress in an isolated transaction to avoid concurrent
                # updates on the same award row.
                from odoo.modules.registry import Registry
                with Registry(self.env.cr.dbname).cursor() as cr2:
                    env2 = api.Environment(cr2, self.env.uid, dict(self.env.context))
                    env2['ir.config_parameter'].sudo().set_param(key, json.dumps(payload))
                    env2['ir.config_parameter'].sudo().set_param(user_key, json.dumps(payload))
                    cr2.commit()
            else:
                self.env['ir.config_parameter'].sudo().set_param(key, json.dumps(payload))
                self.env['ir.config_parameter'].sudo().set_param(user_key, json.dumps(payload))
        except Exception:
            _logger.exception("Failed loader progress write for award %s", self.id)

    @api.model
    def get_loader_progress(self, award_id):
        try:
            aid = int(award_id or 0)
        except (TypeError, ValueError):
            return {}
        rec = self.browse(aid)
        if not rec.exists():
            return {}
        try:
            key = 'bhukhadan_core.s23.loader.progress.%s' % rec.id
            raw = self.env['ir.config_parameter'].sudo().get_param(key, default='') or ''
            if raw:
                try:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        payload.setdefault('project', rec.project_id.name if rec.project_id else '')
                        payload.setdefault('village', rec.village_id.name if rec.village_id else '')
                        vtype_raw = (rec.village_type or (rec.village_id.village_type if rec.village_id else '') or '').lower()
                        payload.setdefault('village_type', 'Urban / नगरीय' if vtype_raw == 'urban' else 'Rural / ग्रामीण')
                        payload.setdefault('urban_body', rec.get_urban_body_label() or '-')
                        return payload
                except Exception:
                    pass
            vtype_raw = (rec.village_type or (rec.village_id.village_type if rec.village_id else '') or '').lower()
            return {
                'active': False,
                'done': 0,
                'total': 0,
                'pct': 0.0,
                'label': '',
                'project': rec.project_id.name if rec.project_id else '',
                'village': rec.village_id.name if rec.village_id else '',
                'village_type': 'Urban / नगरीय' if vtype_raw == 'urban' else 'Rural / ग्रामीण',
                'urban_body': rec.get_urban_body_label() or '-',
            }
        except Exception:
            _logger.exception("get_loader_progress failed for award_id=%r", award_id)
            return {}

    @api.model
    def get_loader_progress_current(self):
        key = 'bhukhadan_core.s23.loader.progress.user.%s' % self.env.uid
        raw = self.env['ir.config_parameter'].sudo().get_param(key, default='') or ''
        if raw:
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        return {
            'active': False,
            'done': 0,
            'total': 0,
            'pct': 0.0,
            'label': '',
            'project': '',
            'village': '',
            'village_type': '',
            'urban_body': '',
        }

    def _s23_increment_loader_progress(self, step=1, label=None, flush=False, active=True):
        self.ensure_one()
        current = self.get_loader_progress_current() or {}
        cur_done = int(current.get('done') or 0)
        cur_total = int(current.get('total') or 0)
        next_done = cur_done + max(0, int(step or 0))
        if cur_total > 0 and next_done > cur_total:
            next_done = cur_total
        self._s23_set_loader_progress(
            done=next_done,
            total=cur_total,
            label=label,
            active=active,
            flush=flush,
        )

    def _ensure_all_components_generated(self):
        self.ensure_one()
        all_generated = bool(
            (self.land_generated and self.asset_generated and self.tree_generated) or self.is_generated
        )
        if not all_generated:
            raise ValidationError(_(
                'All section awards must be generated first (Land + Asset + Tree), '
                'then you can download Standard/Consolidated/R&R full sheets.'
            ))
