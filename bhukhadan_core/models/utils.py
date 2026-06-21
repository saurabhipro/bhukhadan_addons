# -*- coding: utf-8 -*-
"""
Utility functions for BhuKhadan module
Shared utilities that can be used across different models
"""
from odoo.tools import html2plaintext
import re


def strip_html_tags(html_content):
    """
    Convert HTML content to plain text by stripping HTML tags
    
    Args:
        html_content (str): HTML content to convert
        
    Returns:
        str: Plain text without HTML tags
        
    Example:
        strip_html_tags('<p><strong>Hello</strong> World</p>') 
        returns 'Hello World'
    """
    if not html_content:
        return ''
    
    # Use html2plaintext to convert HTML to plain text
    try:
        plain_text = html2plaintext(html_content)
        return plain_text.strip()
    except Exception:
        # Fallback: use regex to remove HTML tags
        clean = re.sub('<.*?>', '', html_content)
        clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        clean = clean.replace('&quot;', '"').replace('&#39;', "'")
        return clean.strip()

