# -*- coding: utf-8 -*-
"""
Form 10 Excel Export API Controller
Handles Excel export endpoints for Form 10 (Bulk Table Report)
"""
from odoo import http
from odoo.http import request, Response

import json
import logging

_logger = logging.getLogger(__name__)


class Form10ExcelAPIController(http.Controller):
    """Controller for Form 10 Excel export APIs"""

    @http.route('/api/bhuarjan/form10/excel/download', type='http', auth='public', methods=['GET'], csrf=False)

    # @check_permission
    def download_form10_excel(self, **kwargs):
        """
        Download Form 10 (Bulk Table Report) Excel based on village_id
        Query params: village_id (required), project_id (optional)
        Returns: Excel file (without logo and QR code)
        """
        try:
            _logger.info("Form 10 Excel download API called")
            
            # Get query parameters
            village_id = request.httprequest.args.get('village_id', type=int)
            project_id = request.httprequest.args.get('project_id', type=int)
            # Always export complete dataset for Form 10 downloads.
            # Ignore any incoming `limit` query param to avoid partial files.
            limit = None

            if not village_id:
                _logger.warning("Form 10 Excel download: village_id is missing")
                return Response(
                    json.dumps({'error': 'village_id is required'}),
                    status=400,
                    content_type='application/json'
                )

            _logger.info(f"Form 10 Excel download: village_id={village_id}, project_id={project_id}, limit=ALL")

            # Verify village exists
            village = request.env['bhu.village'].sudo().browse(village_id)
            if not village.exists():
                _logger.warning(f"Form 10 Excel download: Village {village_id} not found")
                return Response(
                    json.dumps({'error': 'Village not found'}),
                    status=404,
                    content_type='application/json'
                )

            # Get project name if provided
            project_name = None
            if project_id:
                project = request.env['bhu.project'].sudo().browse(project_id)
                if not project.exists():
                    _logger.warning(f"Form 10 Excel download: Project {project_id} not found")
                    return Response(
                        json.dumps({'error': 'Project not found'}),
                        status=404,
                        content_type='application/json'
                    )
                project_name = project.name

            # Use utility function to get surveys
            export_utils = request.env['form10.export.utils']
            surveys = export_utils.get_surveys_for_export(
                village_id=village_id,
                project_id=project_id,
                limit=limit
            )

            _logger.info(f"Form 10 Excel download: Found {len(surveys)} surveys")

            if not surveys:
                _logger.warning(f"Form 10 Excel download: No surveys found for village_id={village_id}")
                return Response(
                    json.dumps({'error': f'No surveys found for village_id={village_id}' + (f' and project_id={project_id}' if project_id else '')}),
                    status=404,
                    content_type='application/json'
                )

            # Use utility function to generate Excel
            try:
                excel_data = export_utils.generate_form10_excel(surveys)
                _logger.info("Form 10 Excel download: Excel file generated")
            except Exception as excel_error:
                _logger.error(f"Form 10 Excel download: Excel generation failed: {str(excel_error)}", exc_info=True)
                return Response(
                    json.dumps({'error': str(excel_error)}),
                    status=500,
                    content_type='application/json'
                )

            # Generate filename using utility function
            filename = export_utils.generate_form10_filename(
                surveys,
                file_extension='xlsx',
                project_name=project_name,
                village_name=village.name if village.name else None
            )

            _logger.info(f"Form 10 Excel download: Returning Excel response with filename: {filename}")

            content_disp = export_utils.content_disposition_attachment(
                filename, ascii_fallback='Form10_Export.xlsx'
            )
            response = request.make_response(
                excel_data,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', content_disp),
                    ('Content-Length', str(len(excel_data)))
                ]
            )
            _logger.info("Form 10 Excel download: Excel response created successfully")
            return response

        except Exception as e:
            _logger.error(f"Error in download_form10_excel: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/bhuarjan/form10/excel/survey/download', type='http', auth='public', methods=['GET'], csrf=False)

    # @check_permission
    def download_form10_excel_by_survey(self, **kwargs):
        """
        Download Form 10 (Bulk Table Report) Excel for a specific survey
        Query params: survey_id (required)
        Returns: Excel file (without logo and QR code)
        """
        try:
            _logger.info("Form 10 Excel download by survey API called")
            
            # Get query parameters
            survey_id = request.httprequest.args.get('survey_id', type=int)

            if not survey_id:
                _logger.warning("Form 10 Excel download by survey: survey_id is missing")
                return Response(
                    json.dumps({'error': 'survey_id is required'}),
                    status=400,
                    content_type='application/json'
                )

            _logger.info(f"Form 10 Excel download by survey: survey_id={survey_id}")

            # Use utility function to get survey
            export_utils = request.env['form10.export.utils']
            surveys = export_utils.get_surveys_for_export(survey_id=survey_id)

            if not surveys:
                _logger.warning(f"Form 10 Excel download by survey: Survey {survey_id} not found")
                return Response(
                    json.dumps({'error': 'Survey not found'}),
                    status=404,
                    content_type='application/json'
                )

            # Use utility function to generate Excel
            try:
                excel_data = export_utils.generate_form10_excel(surveys)
                _logger.info("Form 10 Excel download by survey: Excel file generated")
            except Exception as excel_error:
                _logger.error(f"Form 10 Excel download by survey: Excel generation failed: {str(excel_error)}", exc_info=True)
                return Response(
                    json.dumps({'error': str(excel_error)}),
                    status=500,
                    content_type='application/json'
                )

            # Generate filename using utility function
            filename = export_utils.generate_form10_filename(surveys, file_extension='xlsx')

            _logger.info(f"Form 10 Excel download by survey: Returning Excel response with filename: {filename}")

            content_disp = export_utils.content_disposition_attachment(
                filename, ascii_fallback='Form10_Export.xlsx'
            )
            response = request.make_response(
                excel_data,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', content_disp),
                    ('Content-Length', str(len(excel_data)))
                ]
            )
            _logger.info("Form 10 Excel download by survey: Excel response created successfully")
            return response

        except Exception as e:
            _logger.error(f"Error in download_form10_excel_by_survey: {str(e)}", exc_info=True)
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

