# -*- coding: utf-8 -*-

from odoo import models
from odoo.http import request
import logging
import os

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'
    
    @classmethod
    def _authenticate(cls, endpoint):
        """Override authenticate to check for server restart and force logout"""
        # Check server restart BEFORE authentication
        # cls._check_server_restart()  # Disabled to prevent logout on restart
        return super(IrHttp, cls)._authenticate(endpoint)
    
    @classmethod
    def _check_server_restart(cls):
        """Check if server has restarted and invalidate sessions"""
        try:
            if not hasattr(request, 'db') or not request.db:
                # Don't spam logs for non-db requests (e.g. service worker, /web assets).
                _logger.debug("BHURAJAN: No request.db on request; skipping PID check.")
                return
            
            # Get current process ID
            current_pid = str(os.getpid())
            
            # Get registry and cursor directly
            try:
                from odoo.modules.registry import Registry
                from odoo import api
                registry = Registry(request.db)
                
                # First, get stored PID and check if restart occurred
                stored_pid = ''
                try:
                    with registry.cursor() as cr:
                        env = api.Environment(cr, 1, {})
                        # Try SQL first
                        try:
                            cr.execute("SELECT value FROM ir_config_parameter WHERE key = 'bhukhadan_core.server_pid'")
                            result = cr.fetchone()
                            if result:
                                stored_pid = result[0] or ''
                        except Exception:
                            # Fallback to ORM
                            try:
                                Param = env.get('ir.config_parameter')
                                if Param:
                                    stored_pid = Param.get_param('bhukhadan_core.server_pid', default='')
                            except:
                                pass
                except Exception as read_err:
                    _logger.warning("Could not read PID: %s", read_err)
                
                # Log PID check at DEBUG level to avoid noisy logs on every request.
                _logger.debug("BHURAJAN PID CHECK: current=%s stored=%s", current_pid, stored_pid)
                
                # If PIDs don't match, server was restarted - handle session deletion in separate transaction
                if stored_pid and stored_pid != current_pid:
                    _logger.warning("=== SERVER RESTART DETECTED! PID changed from %s to %s ===", stored_pid, current_pid)
                    
                    # Invalidate ALL sessions using ORM in a separate transaction
                    try:
                        with registry.cursor() as cr:
                            env = api.Environment(cr, 1, {})
                            Session = env.get('ir.session')
                            if Session:
                                sessions = Session.search([])
                                session_count = len(sessions)
                                if session_count > 0:
                                    sessions.unlink()
                                    cr.commit()
                                    _logger.warning("=== DELETED %d SESSIONS VIA ORM DUE TO SERVER RESTART ===", session_count)
                                else:
                                    _logger.info("=== NO ACTIVE SESSIONS FOUND ===")
                            cr.commit()
                    except Exception as session_err:
                        _logger.error("Failed to delete sessions: %s", session_err, exc_info=True)
                    
                    # Force invalidate current session
                    if hasattr(request, 'session'):
                        try:
                            request.session.clear()
                            _logger.warning("=== CLEARED CURRENT SESSION ===")
                        except Exception as e:
                            _logger.error("Failed to clear session: %s", e)
                
                # Always update PID in a separate transaction
                try:
                    with registry.cursor() as cr:
                        env = api.Environment(cr, 1, {})
                        # Try ORM first (more reliable)
                        try:
                            Param = env.get('ir.config_parameter')
                            if Param:
                                Param.set_param('bhukhadan_core.server_pid', current_pid)
                                cr.commit()
                                _logger.info("PID stored via ORM: %s", current_pid)
                            else:
                                # Fallback to SQL
                                cr.execute("SELECT id FROM ir_config_parameter WHERE key = 'bhukhadan_core.server_pid'")
                                existing = cr.fetchone()
                                if existing:
                                    cr.execute("UPDATE ir_config_parameter SET value = %s WHERE key = 'bhukhadan_core.server_pid'", (current_pid,))
                                else:
                                    cr.execute("""
                                        INSERT INTO ir_config_parameter (key, value) 
                                        VALUES ('bhukhadan_core.server_pid', %s)
                                    """, (current_pid,))
                                cr.commit()
                                _logger.info("PID stored via SQL: %s", current_pid)
                        except Exception as pid_err:
                            _logger.error("Could not store PID: %s", pid_err)
                            cr.rollback()
                except Exception as pid_trans_err:
                    _logger.error("Could not create transaction for PID storage: %s", pid_trans_err)
                        
            except Exception as env_err:
                _logger.error("Could not access database: %s", env_err, exc_info=True)
                
        except Exception as e:
            _logger.error("Error in _check_server_restart: %s", e, exc_info=True)
    
    def get_frontend_session_info(self):
        """Override to safely handle cases where session might be None"""
        try:
            # Call parent method
            result = super().get_frontend_session_info()
            # Ensure we return a dict, not None
            if result is None:
                return {}
            return result
        except Exception as e:
            _logger.error("Error in get_frontend_session_info: %s", e, exc_info=True)
            # Return empty dict as fallback
            return {}

    def session_info(self):
        result = super().session_info()
        impersonator_uid = request.session.get('impersonator_uid')
        if impersonator_uid:
            imp = self.env['res.users'].sudo().browse(impersonator_uid)
            result['bhu_impersonator'] = {
                'uid': impersonator_uid,
                'name': imp.display_name if imp.exists() else '',
                'back_url': '/bhuarjan/login_as/back',
            }
        real_uid = impersonator_uid or request.session.uid
        real_user = self.env['res.users'].sudo().browse(real_uid)
        result['bhu_can_impersonate_sdm'] = bool(
            real_user.exists()
            and (
                real_user.has_group('base.group_system')
                or real_user.has_group('bhukhadan_core.group_bhuarjan_admin')
                or real_user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
            )
        )
        result['bhu_can_impersonate_collector'] = result['bhu_can_impersonate_sdm']
        terms_user = real_user if real_user.exists() else self.env.user
        if request.session.uid and terms_user.exists() and not terms_user._is_public():
            result['bhu_terms_accepted'] = bool(getattr(terms_user, 'bhu_terms_accepted', False))
        else:
            result['bhu_terms_accepted'] = True
        return result

