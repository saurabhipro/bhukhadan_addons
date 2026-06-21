# -*- coding: utf-8 -*-

from odoo import models, fields, api
import uuid
import logging

_logger = logging.getLogger(__name__)


class QRCodeMixin(models.AbstractModel):
    """Mixin for unified QR code generation across all models"""
    _name = 'bhu.qr.code.mixin'
    _description = 'QR Code Generation Mixin'

    # Mapping of model names to their URL paths and UUID field names
    QR_CODE_CONFIG = {
        'bhu.section4.notification': {
            'path': 'section4',
            'uuid_field': 'notification_uuid',
        },
        'bhu.section11.preliminary.report': {
            'path': 'section11',
            'uuid_field': 'report_uuid',
        },
        'bhu.section19.notification': {
            'path': 'section19',
            'uuid_field': 'notification_uuid',
        },
        'bhu.section21.notification': {
            'path': 'section21',
            'uuid_field': 'notification_uuid',
        },
        'bhu.sia.team': {
            'path': 'sia',
            'uuid_field': 'sia_team_uuid',
        },
        'bhu.expert.committee.report': {
            'path': 'expert',
            'uuid_field': 'expert_committee_uuid',
        },
        'bhu.survey': {
            'path': 'form10',
            'uuid_field': None,  # Special case - uses project_uuid and village_uuid
        },
    }

    def get_qr_code_url(self):
        """Generate QR code URL based on model name and UUID"""
        self.ensure_one()
        model_name = self._name
        
        # Special handling for Form 10 (survey) - uses project and village UUIDs
        if model_name == 'bhu.survey':
            if not self.project_id or not self.village_id:
                return None
            
            # Ensure UUIDs exist
            if not self.project_id.project_uuid:
                self.project_id.write({'project_uuid': str(uuid.uuid4())})
            
            if not self.village_id.village_uuid:
                self.village_id.write({'village_uuid': str(uuid.uuid4())})
            
            project_uuid = self.project_id.project_uuid
            village_uuid = self.village_id.village_uuid
            return f"https://bhuarjan.com/bhuarjan/form10/{project_uuid}/{village_uuid}/download"
        
        # Standard handling for other models
        config = self.QR_CODE_CONFIG.get(model_name)
        if not config:
            _logger.warning(f"No QR code config found for model: {model_name}")
            return None
        
        uuid_field = config['uuid_field']
        if not uuid_field:
            return None
        
        # Ensure UUID exists
        if not getattr(self, uuid_field, None):
            self.write({uuid_field: str(uuid.uuid4())})
        
        uuid_value = getattr(self, uuid_field)
        path = config['path']
        
        return f"https://bhuarjan.com/bhuarjan/{path}/{uuid_value}/download"

    def get_qr_code_data(self):
        """Generate QR code data (base64 image) for the record"""
        try:
            import qrcode
            import io
            import base64
        except ImportError:
            _logger.warning("qrcode library not installed")
            return None
        
        try:
            self.ensure_one()
            
            # Get QR code URL
            qr_url = self.get_qr_code_url()
            if not qr_url:
                return None
            
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=2,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # Generate image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return img_str
        except Exception as e:
            _logger.error(f"Error generating QR code for {self._name} record {self.id}: {str(e)}", exc_info=True)
            return None

