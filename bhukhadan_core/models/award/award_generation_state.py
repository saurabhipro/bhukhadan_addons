# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError


class Section23Award(models.Model):
    _inherit = 'bhu.section23.award'

    def action_submit_award(self):
        """Submit the award after document upload"""
        self.ensure_one()
        if not self.award_document:
            raise ValidationError(_('Please upload the signed award document before submitting.\nकृपया जमा करने से पहले हस्ताक्षरित अवार्ड दस्तावेज़ अपलोड करें।'))

        self.write({
            'state': 'submitted'
        })

        # Log activity
        self.message_post(body=_("Award submitted with signed document."))

    def action_approve_award(self):
        """Mark award as Generated/Approved (used for legacy records generated before auto-approve)."""
        self.ensure_one()
        self.write({'state': 'approved', 'is_generated': True})
        self.message_post(body=_("Award marked as Generated / अवार्ड उत्पन्न के रूप में चिह्नित किया गया।"))

    def action_send_back_award(self):
        """Send back the award for correction"""
        self.ensure_one()
        self.write({'state': 'sent_back'})
        self.message_post(body=_("Award sent back for correction."))
