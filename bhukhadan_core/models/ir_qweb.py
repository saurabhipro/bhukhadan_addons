# -*- coding: utf-8 -*-

from odoo import models
from odoo.http import request


class IrQweb(models.AbstractModel):
    _inherit = "ir.qweb"

    def _prepare_environment(self, values):
        ir_qweb = super()._prepare_environment(values)
        # Some controller stacks can render frontend templates without website=True.
        # Ensure the "website" key exists to avoid hard QWeb crashes in that case.
        if request and "website" not in values:
            try:
                if "website" in ir_qweb.env:
                    values["website"] = request.env["website"].get_current_website()
            except Exception:
                # Keep rendering behavior unchanged if website is unavailable.
                pass
        return ir_qweb
