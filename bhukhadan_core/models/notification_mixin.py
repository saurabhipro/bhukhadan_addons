# -*- coding: utf-8 -*-
"""
Mixin model for notification models
Provides common utility methods for all notification models
"""
from odoo import models
from . import utils


class NotificationMixin(models.AbstractModel):
    """Mixin model providing common utilities for notification models"""
    _name = 'bhu.notification.mixin'
    _description = 'Notification Mixin'
    
    def get_plain_text_from_html(self, html_content):
        """
        Convert HTML content to plain text by stripping HTML tags
        This method can be used in QWeb templates
        
        Args:
            html_content (str): HTML content to convert
            
        Returns:
            str: Plain text without HTML tags
        """
        return utils.strip_html_tags(html_content)

