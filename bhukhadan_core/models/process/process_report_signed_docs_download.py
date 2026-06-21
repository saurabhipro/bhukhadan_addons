# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import io
import base64
import logging
import zipfile
from datetime import datetime

_logger = logging.getLogger(__name__)


class ProcessReportSignedDocsDownload(models.AbstractModel):
    """Mixin for signed documents download functionality in Process Report Wizard"""
    _name = 'bhu.process.report.signed.docs.download.mixin'
    _description = 'Process Report Signed Documents Download Mixin'

    def action_download_signed_docs(self):
        """Download all signed documents as a zip file"""
        self.ensure_one()
        
        if not self.project_id:
            raise ValidationError(_('Please select a project to download signed documents.'))
        
        records = self._get_filtered_records()
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        zip_file = zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED)
        
        doc_count = 0
        
        try:
            # Collect Section 4 signed documents
            for record in records['section4']:
                project_name = (record.project_id.name or 'Unknown').replace('/', '_').replace('\\', '_')
                village_name = (record.village_id.name or 'Unknown').replace('/', '_').replace('\\', '_')
                
                # SDM signed file
                if record.sdm_signed_file:
                    try:
                        doc_data = base64.b64decode(record.sdm_signed_file)
                        filename = record.sdm_signed_filename or f'Section4_SDM_Signed_{project_name}_{village_name}_{record.name or record.id}.pdf'
                        # Ensure unique filename
                        existing_filenames = [info.filename for info in zip_file.infolist()]
                        if filename in existing_filenames:
                            filename = f'Section4_SDM_Signed_{project_name}_{village_name}_{record.name or record.id}_{record.id}.pdf'
                        zip_file.writestr(filename, doc_data)
                        doc_count += 1
                    except Exception as e:
                        _logger.error(f"Error adding SDM signed file for Section 4 record {record.id}: {str(e)}", exc_info=True)
                
                # Collector signed file
                if record.collector_signed_file:
                    try:
                        doc_data = base64.b64decode(record.collector_signed_file)
                        filename = record.collector_signed_filename or f'Section4_Collector_Signed_{project_name}_{village_name}_{record.name or record.id}.pdf'
                        # Ensure unique filename
                        existing_filenames = [info.filename for info in zip_file.infolist()]
                        if filename in existing_filenames:
                            filename = f'Section4_Collector_Signed_{project_name}_{village_name}_{record.name or record.id}_{record.id}.pdf'
                        zip_file.writestr(filename, doc_data)
                        doc_count += 1
                    except Exception as e:
                        _logger.error(f"Error adding Collector signed file for Section 4 record {record.id}: {str(e)}", exc_info=True)
            
            # Collect Section 11 signed documents
            for record in records['section11']:
                project_name = (record.project_id.name or 'Unknown').replace('/', '_').replace('\\', '_') if record.project_id else 'Unknown'
                village_name = (record.village_id.name or 'Unknown').replace('/', '_').replace('\\', '_') if record.village_id else 'Unknown'
                
                # SDM signed file
                if record.sdm_signed_file:
                    try:
                        doc_data = base64.b64decode(record.sdm_signed_file)
                        filename = record.sdm_signed_filename or f'Section11_SDM_Signed_{project_name}_{village_name}_{record.name or record.id}.pdf'
                        # Ensure unique filename
                        existing_filenames = [info.filename for info in zip_file.infolist()]
                        if filename in existing_filenames:
                            filename = f'Section11_SDM_Signed_{project_name}_{village_name}_{record.name or record.id}_{record.id}.pdf'
                        zip_file.writestr(filename, doc_data)
                        doc_count += 1
                    except Exception as e:
                        _logger.error(f"Error adding SDM signed file for Section 11 record {record.id}: {str(e)}", exc_info=True)
                
                # Collector signed file
                if record.collector_signed_file:
                    try:
                        doc_data = base64.b64decode(record.collector_signed_file)
                        filename = record.collector_signed_filename or f'Section11_Collector_Signed_{project_name}_{village_name}_{record.name or record.id}.pdf'
                        # Ensure unique filename
                        existing_filenames = [info.filename for info in zip_file.infolist()]
                        if filename in existing_filenames:
                            filename = f'Section11_Collector_Signed_{project_name}_{village_name}_{record.name or record.id}_{record.id}.pdf'
                        zip_file.writestr(filename, doc_data)
                        doc_count += 1
                    except Exception as e:
                        _logger.error(f"Error adding Collector signed file for Section 11 record {record.id}: {str(e)}", exc_info=True)
            
            # Collect Section 19 signed documents
            for record in records['section19']:
                project_name = (record.project_id.name or 'Unknown').replace('/', '_').replace('\\', '_') if record.project_id else 'Unknown'
                village_name = (record.village_id.name or 'Unknown').replace('/', '_').replace('\\', '_') if record.village_id else 'Unknown'
                
                # SDM signed file
                if record.sdm_signed_file:
                    try:
                        doc_data = base64.b64decode(record.sdm_signed_file)
                        filename = record.sdm_signed_filename or f'Section19_SDM_Signed_{project_name}_{village_name}_{record.name or record.id}.pdf'
                        # Ensure unique filename
                        existing_filenames = [info.filename for info in zip_file.infolist()]
                        if filename in existing_filenames:
                            filename = f'Section19_SDM_Signed_{project_name}_{village_name}_{record.name or record.id}_{record.id}.pdf'
                        zip_file.writestr(filename, doc_data)
                        doc_count += 1
                    except Exception as e:
                        _logger.error(f"Error adding SDM signed file for Section 19 record {record.id}: {str(e)}", exc_info=True)
                
                # Collector signed file
                if record.collector_signed_file:
                    try:
                        doc_data = base64.b64decode(record.collector_signed_file)
                        filename = record.collector_signed_filename or f'Section19_Collector_Signed_{project_name}_{village_name}_{record.name or record.id}.pdf'
                        # Ensure unique filename
                        existing_filenames = [info.filename for info in zip_file.infolist()]
                        if filename in existing_filenames:
                            filename = f'Section19_Collector_Signed_{project_name}_{village_name}_{record.name or record.id}_{record.id}.pdf'
                        zip_file.writestr(filename, doc_data)
                        doc_count += 1
                    except Exception as e:
                        _logger.error(f"Error adding Collector signed file for Section 19 record {record.id}: {str(e)}", exc_info=True)
            
            zip_file.close()
            
            if doc_count == 0:
                raise ValidationError(_('No signed documents found for the selected project and filters.'))
            
            # Create attachment
            zip_buffer.seek(0)
            zip_data = base64.b64encode(zip_buffer.read())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = (self.project_id.name or 'All').replace('/', '_').replace('\\', '_')
            filename = f'Signed_Documents_{project_name}_{timestamp}.zip'
            
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': zip_data,
                'mimetype': 'application/zip',
                'res_model': 'bhu.process.report.wizard',
                'res_id': self.id,
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
            
        except Exception as e:
            zip_file.close()
            _logger.error(f"Error creating signed documents zip file: {str(e)}", exc_info=True)
            raise ValidationError(_('Error generating signed documents zip file: %s') % str(e))

