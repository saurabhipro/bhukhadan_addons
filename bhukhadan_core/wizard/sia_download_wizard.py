# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64


class BhuDownloadWizard(models.TransientModel):
    _name = 'sia.download.wizard'  # Keep name for backward compatibility or rename if views updated
    _description = 'Download Format Wizard'

    # Generic fields
    res_model = fields.Char(string='Model Name', required=True)
    res_id = fields.Integer(string='Record ID', required=True)
    report_xml_id = fields.Char(string='Report XML ID', required=True)
    filename = fields.Char(string='Filename', help='Filename for the downloaded file')
    
    # Legacy field (optional/deprecated)
    sia_team_id = fields.Many2one('bhu.sia.team', string='SIA Team')
    
    format = fields.Selection([
        ('pdf', 'PDF Format'),
        ('word', 'Word Format (.doc)'),
        ('excel', 'Excel Format (.xlsx)')
    ], string='Download Format', default='pdf', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Handle context for legacy calls or quick setup
        if self.env.context.get('active_model') and self.env.context.get('active_id'):
            if 'res_model' not in res:
                res['res_model'] = self.env.context.get('active_model')
            if 'res_id' not in res:
                res['res_id'] = self.env.context.get('active_id')
        
        # If legacy sia_team_id is provided in context
        if self.env.context.get('default_sia_team_id'):
            res['res_model'] = 'bhu.sia.team'
            res['res_id'] = self.env.context.get('default_sia_team_id')
            # Default report for SIA Team if not specified
            if 'report_xml_id' not in res:
                res['report_xml_id'] = 'bhukhadan_core.action_report_sia_proposal'
                
        return res

    def action_download(self):
        """Download the report in selected format"""
        self.ensure_one()
        
        record = self.env[self.res_model].browse(self.res_id)
        if self.format == 'pdf':
            # Download as PDF using standard report
            report = self.env.ref(self.report_xml_id)
            return report.report_action(record)
        elif self.format == 'excel':
            # Delegate to record's excel method if it exists
            if hasattr(record, 'action_download_excel'):
                return record.action_download_excel()
            raise UserError(_("Excel export is not supported for this report."))
        elif self.format == 'word':
            # Download as Word (.doc) - HTML format that Word can open
            return self._generate_word_doc(record)
        raise UserError(_("Selected download format is not supported."))
    
    def _generate_word_doc(self, record):
        """Generate Word document from report HTML with embedded images and inline styles"""
        self.ensure_one()
        
        # Get the HTML content from the report
        report = self.env.ref(self.report_xml_id)
        html_content, report_format = report._render_qweb_html(report.report_name, [self.res_id])
        
        # Convert bytes to string if needed
        html_str = html_content.decode('utf-8') if isinstance(html_content, bytes) else html_content
        
        import re
        import base64
        import requests
        
        # Remove all <link> and <script> tags that reference external files
        html_str = re.sub(r'<link[^>]*>', '', html_str)
        html_str = re.sub(r'<script[^>]*>.*?</script>', '', html_str, flags=re.DOTALL)
        
        # Extract inline styles
        style_pattern = r'<style[^>]*>(.*?)</style>'
        styles = re.findall(style_pattern, html_str, re.DOTALL)
        combined_styles = '\n'.join(styles)
        
        # CAREFULLY Remove ONLY the watermark section (not the header!)
        # Pattern 1: Remove watermark HTML comments
        watermark_pattern1 = r'<!--.*?Watermark.*?-->'
        html_str = re.sub(watermark_pattern1, '', html_str, flags=re.DOTALL | re.IGNORECASE)
        
        # Pattern 2: Remove ONLY div with class="watermark" (be specific to avoid removing header)
        # Match: <div class="watermark">...</div> but NOT the header table
        watermark_pattern2 = r'<div\s+class=["\']watermark["\'][^>]*>(?:(?!<table).)*?</div>'
        html_str = re.sub(watermark_pattern2, '', html_str, flags=re.DOTALL | re.IGNORECASE)
        
        # Pattern 3: Remove watermark images by alt text
        html_str = re.sub(r'<img[^>]*alt=["\'][^"\']*[Ww]atermark[^"\']*["\'][^>]*/?>',  '', html_str, flags=re.IGNORECASE)
        
        # Remove the decorative dotted border from container but KEEP its contents
        html_str = re.sub(r'(<div[^>]*class=["\']container[^"\']*["\'][^>]*)style="[^"]*border:\s*2px\s+dotted[^"]*"([^>]*>)', r'\1style="margin:0; padding:0; border:none;"\2', html_str, flags=re.IGNORECASE)
        
        # Convert images to base64 data URIs for embedding in Word
        def convert_image_to_base64(match):
            img_tag = match.group(0)
            src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
            if not src_match:
                return img_tag
            
            img_url = src_match.group(1)
            
            # Check if this is a watermark image by alt text - if so, skip it
            if 'Watermark' in img_tag or 'watermark' in img_tag.lower():
                return ''  # Remove watermark images
            
            # Don't skip any logos - the watermark div is already removed earlier
            # All remaining images are valid (header logo, QR code, etc.)
            
            try:
                # Handle relative URLs
                if img_url.startswith('/'):
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
                    img_url = base_url + img_url
                
                # Fetch the image
                response = requests.get(img_url, timeout=5)
                if response.status_code == 200:
                    img_base64 = base64.b64encode(response.content).decode('utf-8')
                    # Determine mime type from response headers or URL
                    content_type = response.headers.get('content-type', 'image/png')
                    data_uri = f'data:{content_type};base64,{img_base64}'
                    
                    # Build a NEW img tag with forced small size - Word needs width/height attributes, not just CSS
                    alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag)
                    alt_text = alt_match.group(1) if alt_match else 'Image'
                    
                    class_match = re.search(r'class=["\']([^"\']*)["\']', img_tag)
                    class_text = class_match.group(1) if class_match else ''
                    
                    # Create img tag with HTML width/height attributes (Word understands these better than CSS)
                    # Use width and height attributes for Word compatibility
                    new_tag = f'<img src="{data_uri}" alt="{alt_text}" width="80" height="80" style="width:80px; height:80px; display:block; margin:0 auto;"'
                    if class_text:
                        new_tag += f' class="{class_text}"'
                    new_tag += '/>'
                    
                    return new_tag
            except Exception as e:
                pass
            
            return img_tag
        
        # Remove <a> tags around QR codes (links not needed in Word, and they cause sizing issues)
        html_str = re.sub(r'<a[^>]*href="[^"]*qr[^"]*"[^>]*>', '', html_str, flags=re.IGNORECASE)
        html_str = re.sub(r'<a[^>]*href="[^"]*download[^"]*"[^>]*>', '', html_str, flags=re.IGNORECASE)
        html_str = re.sub(r'</a>', '', html_str)
        
        # Remove dots/periods used as placeholders in blank fields (e.g., "........................")
        # Remove sequences of 3 or more dots/periods
        html_str = re.sub(r'\.{3,}', '', html_str)
        # Also remove sequences with spaces between dots
        html_str = re.sub(r'(\.\s*){3,}', '', html_str)
        
        # Convert all images to base64 (logo and QR code will be embedded)
        html_str = re.sub(r'<img[^>]*>', convert_image_to_base64, html_str)
        
        # Force table cells with rowspan="2" (logo and QR columns) to be fixed narrow width
        # Keep styles simple for Word compatibility (no !important)
        html_str = re.sub(r'<td([^>]*)rowspan="2"([^>]*)style="width:\s*12%;[^"]*"([^>]*)>', r'<td\1rowspan="2"\2style="width:85px; padding:2px; text-align:center; vertical-align:middle;"\3>', html_str, flags=re.IGNORECASE)
        html_str = re.sub(r'<td([^>]*)style="width:\s*12%;[^"]*"([^>]*)rowspan="2"([^>]*)>', r'<td\1style="width:85px; padding:2px; text-align:center; vertical-align:middle;"\2rowspan="2"\3>', html_str, flags=re.IGNORECASE)
        
        # Remove inline styles that add spacing - but keep table structure
        # Don't remove border/padding from td/th elements
        html_str = re.sub(r'<(?!td|th|table)([^>]+)style="[^"]*border[^"]*"', r'<\1style=""', html_str, flags=re.IGNORECASE)
        html_str = re.sub(r'<(?!td|th|table)([^>]+)style="[^"]*padding[^"]*"', r'<\1style=""', html_str, flags=re.IGNORECASE)
        html_str = re.sub(r'<(?!td|th|table)([^>]+)style="[^"]*margin[^"]*"', r'<\1style=""', html_str, flags=re.IGNORECASE)
        
        # Remove empty style attributes
        html_str = re.sub(r'\s*style=""\s*', ' ', html_str)
        
        # Clean up styles - remove @page rules that cause issues
        combined_styles = re.sub(r'@page[^{]*\{[^}]*\}', '', combined_styles)
        
        # Word-compatible HTML wrapper - NO XML declaration, pure HTML
        word_html = f"""<html xmlns:o='urn:schemas-microsoft-com:office:office' 
      xmlns:w='urn:schemas-microsoft-com:office:word'
      xmlns='http://www.w3.org/TR/REC-html40'>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <meta name="ProgId" content="Word.Document"/>
    <meta name="Generator" content="Microsoft Word 15"/>
    <meta name="Originator" content="Microsoft Word 15"/>
    <!--[if gte mso 9]>
    <xml>
        <w:WordDocument>
            <w:View>Print</w:View>
            <w:Zoom>100</w:Zoom>
            <w:DoNotOptimizeForBrowser/>
        </w:WordDocument>
    </xml>
    <![endif]-->
    <style type="text/css">
        @page Section1 {{
            size: 11.69in 8.27in;
            mso-page-orientation: landscape;
            margin-top: 0.2in;
            margin-right: 0.2in;
            margin-bottom: 0.2in;
            margin-left: 0.2in;
        }}

        /* Original report styles - inline and self-contained */
        {combined_styles}
        
        /* Word compatibility styles - MINIMAL margins for maximum space */
        /* Note: Avoiding !important as Word doesn't handle it well */
        body {{
            font-family: 'Noto Sans Devanagari', 'Mangal', 'Arial Unicode MS', Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.15;
            margin-top: 0.1in;
            margin-bottom: 0.1in;
            margin-left: 0.15in;
            margin-right: 0.15in;
            padding: 0;
        }}
        
        * {{
            font-size: 10pt;
        }}
        
        div, p, span {{
            margin: 0;
            padding: 0;
        }}
        
        /* Hide watermark (Word-compatible) */
        .watermark {{
            display: none;
            visibility: hidden;
        }}
        
        /* Images - compact with aspect ratio maintained */
        img {{
            max-width: 80px;
            max-height: 80px;
            width: auto;
            height: auto;
            display: block;
            margin: 2px auto;
        }}
        
        /* Image containers */
        .qr_code, .o_company_logo {{
            text-align: center;
            width: 85px;
            max-width: 85px;
        }}
        
        /* Remove decorative borders to save space */
        .container {{
            border: none;
            padding: 0;
            margin: 0;
        }}
        
        /* Tables - Word-compatible styling */
        table {{
            border-collapse: collapse;
            width: 100%;
            mso-table-lspace: 0pt;
            mso-table-rspace: 0pt;
            margin: 2px 0;
        }}
        
        /* Table cells - basic borders */
        td, th {{
            border: 1px solid #000;
            padding: 3px 5px;
            vertical-align: middle;
            text-align: left;
            mso-line-height-rule: exactly;
        }}
        
        /* Table headers */
        th {{
            font-weight: bold;
            background-color: #f0f0f0;
        }}
        
        /* Paragraphs and headings */
        p {{
            margin: 0;
            padding: 0;
            line-height: 1.15;
        }}
        
        h1 {{
            font-size: 14pt;
            margin: 2px 0;
        }}
        
        h2 {{
            font-size: 12pt;
            margin: 2px 0;
        }}
        
        h3 {{
            font-size: 11pt;
            margin: 1px 0;
        }}
        
        h4, h5, h6 {{
            font-size: 10pt;
            margin: 1px 0;
        }}
    </style>
</head>
<body lang="EN-IN" class="Section1">
    {html_str}
</body>
</html>"""
        
        # Generate filename
        if self.filename:
            fn = self.filename
        else:
            name_part = getattr(record, 'name', 'Record')
            # Sanitize name_part for filename
            name_part = re.sub(r'[^\w\s-]', '', name_part).strip().replace(' ', '_')
            
            date_str = getattr(record, 'create_date', fields.Datetime.now()).strftime('%Y%m%d')
            fn = f'{self.res_model.replace(".","_")}_{name_part}_{date_str}'
            
        if not fn.endswith('.doc'):
            fn += '.doc'
            
        # Encode to base64
        word_data = base64.b64encode(word_html.encode('utf-8'))
        
        # Create attachment and download
        attachment = self.env['ir.attachment'].create({
            'name': fn,
            'type': 'binary',
            'datas': word_data,
            'res_model': self.res_model,
            'res_id': self.res_id,
            'mimetype': 'application/msword'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
