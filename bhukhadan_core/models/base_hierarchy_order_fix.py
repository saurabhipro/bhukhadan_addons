# -*- coding: utf-8 -*-
"""Strip read_group pseudo order terms (__count) from hierarchy loads.

Grouped list/search state can persist ``order By __count``. The hierarchy RPC
calls ``Model.search(domain, order=…)``, which only accepts actual fields.
"""


from odoo import api, models


def sanitize_hierarchy_order(env, model_name, order):
    """Return SQL order clause safe for ``search()``, or None."""
    if not order:
        return None
    if not isinstance(order, str):
        return order
    Model = env.get(model_name)
    if Model is None:
        return None
    chunks = []
    for raw in order.split(','):
        part = raw.strip()
        if not part:
            continue
        token = part.split(None, 1)[0].strip()
        if token.lower() in ('__count', '__count__'):
            continue
        if token not in Model._fields:
            continue
        chunks.append(part)
    return ', '.join(chunks) if chunks else None


class BaseHierarchyOrderSanitize(models.AbstractModel):
    """Must load after ``web_hierarchy`` (manifest dependency)."""
    _inherit = 'base'

    @api.model
    def hierarchy_read(self, domain, fields, parent_field, child_field=None, order=None):
        order = sanitize_hierarchy_order(self.env, self._name, order)
        return super().hierarchy_read(
            domain, fields, parent_field, child_field=child_field, order=order
        )
