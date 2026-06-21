from odoo import http
from odoo.http import request
import logging
import base64

_logger = logging.getLogger(__name__)


class Form10PDFController(http.Controller):
    """Controller for direct PDF download from QR code scan"""

    @http.route('/bhuarjan/form10/<path:project_uuid>/<path:village_uuid>/download', type='http', auth='public', methods=['GET'], csrf=False, website=False)
    def download_pdf(self, project_uuid, village_uuid, **kwargs):
        """Download Form 10 PDF directly using project and village UUIDs - gets all surveys for that project in that village"""
        _logger.debug("Form10 PDF route: project_uuid=%s, village_uuid=%s", project_uuid, village_uuid)
        try:
            project = request.env['bhu.project'].sudo().with_context({}).search([('project_uuid', '=', project_uuid)], limit=1)
            if not project:
                _logger.error("Project not found with UUID: %s", project_uuid)
                return request.not_found("Project not found")

            all_villages_with_uuid = request.env['bhu.village'].sudo().with_context({}).search([('village_uuid', '=', village_uuid)])

            if len(all_villages_with_uuid) > 1:
                _logger.error(
                    "Duplicate village UUID %s assigned to %d villages: %s – deduplicating",
                    village_uuid, len(all_villages_with_uuid),
                    [(v.id, v.name) for v in all_villages_with_uuid],
                )
                for dup_village in all_villages_with_uuid[1:]:
                    import uuid as _uuid_mod
                    new_uuid = str(_uuid_mod.uuid4())
                    _logger.warning("Re-assigning UUID for village %s (%s): %s -> %s", dup_village.id, dup_village.name, village_uuid, new_uuid)
                    dup_village.write({'village_uuid': new_uuid})
                village = all_villages_with_uuid[0]
            elif len(all_villages_with_uuid) == 1:
                village = all_villages_with_uuid[0]
            else:
                village = False

            if not village:
                _logger.error("Village not found with UUID: %s", village_uuid)
                return request.not_found("Village not found")

            if project.project_uuid != project_uuid:
                _logger.error("Project UUID mismatch! Expected %s, got %s", project_uuid, project.project_uuid)
            if village.village_uuid != village_uuid:
                _logger.error("Village UUID mismatch! Expected %s, got %s", village_uuid, village.village_uuid)
            
            # Generate PDF report using Odoo's standard rendering
            try:
                report_action = request.env.ref('bhukhadan_core.action_report_form10_bulk_table').sudo()
            except ValueError:
                return request.not_found("Report not found")
            
            if not report_action.exists():
                return request.not_found("Report not found")
            
            # Get all surveys for the specific project AND village
            # Use explicit AND operator to ensure strict filtering
            domain = [
                '&',  # Explicit AND operator
                ('project_id', '=', project.id),
                ('village_id', '=', village.id)
            ]
            
            _logger.debug("Searching surveys with domain: %s", domain)
            _logger.debug(
                "Expected: Project ID=%s (UUID=%s, Name=%s), Village ID=%s (UUID=%s, Name=%s)",
                project.id, project.project_uuid, project.name,
                village.id, village.village_uuid, village.name,
            )
            
            # Clear any existing context/cache and search fresh
            # Also disable project.filter mixin by clearing bhuarjan_current_project_id
            all_surveys = request.env['bhu.survey'].sudo().with_context(
                active_test=False,
                bhuarjan_current_project_id=False
            ).search(domain, order='id')
            
            _logger.debug("Found %d surveys. Details:", len(all_surveys))
            debug_enabled = _logger.isEnabledFor(logging.DEBUG)
            for survey in all_surveys:
                if debug_enabled:
                    _logger.debug(
                        "  Survey ID=%s: Project ID=%s (Name=%s), Village ID=%s (Name=%s, UUID=%s)",
                        survey.id, survey.project_id.id, survey.project_id.name,
                        survey.village_id.id, survey.village_id.name, survey.village_id.village_uuid,
                    )
                if survey.project_id.id != project.id:
                    _logger.error("Survey %s has wrong project! Expected Project ID=%s, got %s", survey.id, project.id, survey.project_id.id)
                if survey.village_id.id != village.id:
                    _logger.error(
                        "Survey %s has wrong village! Expected Village ID=%s (UUID=%s, Name=%s), got Village ID=%s (UUID=%s, Name=%s)",
                        survey.id, village.id, village.village_uuid, village.name,
                        survey.village_id.id, survey.village_id.village_uuid, survey.village_id.name,
                    )
                if survey.village_id.village_uuid != village_uuid:
                    _logger.error("Survey %s belongs to village with different UUID! Expected %s, got %s", survey.id, village_uuid, survey.village_id.village_uuid)
            
            if not all_surveys:
                # Check if there are ANY surveys for this project (to help debug)
                project_surveys = request.env['bhu.survey'].sudo().search([('project_id', '=', project.id)])
                _logger.warning(f"No surveys found for project {project.id} and village {village.id}. Total surveys for this project: {len(project_surveys)}")
                if project_surveys:
                    _logger.warning(f"Villages with surveys in this project: {set(project_surveys.mapped('village_id.id'))}")
                return request.not_found("No surveys found for this project and village")

            # Landowner text-size diagnostics for row chunking logic.
            # Helps determine whether count (owners) or text length is the first pressure point.
            count_threshold = 5
            length_threshold = 180
            max_count = 0
            max_chars = 0
            max_count_survey = None
            max_chars_survey = None
            first_count_survey = None
            first_length_survey = None
            metric_rows = []
            for survey in all_surveys:
                owners = survey.landowner_ids.sudo()
                lo_count = len(owners)
                total_chars = 0
                for lo in owners:
                    person = lo.name or ''
                    if lo.father_name:
                        person += ' पिता ' + lo.father_name
                    elif lo.spouse_name:
                        person += ' पति ' + lo.spouse_name
                    total_chars += len(person)
                metric_rows.append((survey.id, survey.khasra_number or '', lo_count, total_chars))
                if lo_count > max_count:
                    max_count = lo_count
                    max_count_survey = survey
                if total_chars > max_chars:
                    max_chars = total_chars
                    max_chars_survey = survey
                if first_count_survey is None and lo_count > count_threshold:
                    first_count_survey = survey
                if first_length_survey is None and total_chars > length_threshold:
                    first_length_survey = survey

            first_trigger = 'none'
            if first_count_survey and first_length_survey:
                first_trigger = 'count' if first_count_survey.id <= first_length_survey.id else 'length'
            elif first_count_survey:
                first_trigger = 'count'
            elif first_length_survey:
                first_trigger = 'length'

            _logger.info(
                "Form10 LO metrics: max_count=%s (survey=%s, khasra=%s), "
                "max_total_chars=%s (survey=%s, khasra=%s), first_trigger=%s "
                "[thresholds: count>%s, chars>%s]",
                max_count,
                max_count_survey.id if max_count_survey else None,
                max_count_survey.khasra_number if max_count_survey else None,
                max_chars,
                max_chars_survey.id if max_chars_survey else None,
                max_chars_survey.khasra_number if max_chars_survey else None,
                first_trigger,
                count_threshold,
                length_threshold,
            )
            if _logger.isEnabledFor(logging.DEBUG):
                for survey_id, khasra_no, lo_count, total_chars in sorted(metric_rows, key=lambda x: (x[2], x[3]), reverse=True)[:10]:
                    _logger.debug(
                        "Form10 LO metric detail: survey=%s khasra=%s count=%s total_chars=%s",
                        survey_id, khasra_no, lo_count, total_chars,
                    )
            
            _logger.info(
                "Generating PDF for %d surveys (project=%s[%s], village=%s[%s])",
                len(all_surveys), project.name, project.id, village.name, village.id,
            )
            _logger.debug("Survey IDs: %s", all_surveys.ids)
            
            # Convert recordset to list of IDs for PDF rendering
            # Ensure we have the correct IDs
            res_ids = [int(sid) for sid in all_surveys.ids]
            
            if not res_ids:
                return request.not_found("No survey IDs found")
            
            # Double-check: Browse the records again and FILTER OUT any that don't match
            # This ensures we're passing ONLY the correct IDs to the PDF renderer
            verify_surveys = request.env['bhu.survey'].sudo().browse(res_ids)
            correct_survey_ids = []
            for survey in verify_surveys:
                if survey.project_id.id != project.id:
                    _logger.error(f"FILTERING OUT Survey {survey.id}: Wrong project! Expected Project ID={project.id}, got {survey.project_id.id}")
                    continue
                if survey.village_id.id != village.id:
                    _logger.error(f"FILTERING OUT Survey {survey.id}: Wrong village! Expected Village ID={village.id} (UUID={village.village_uuid}, Name={village.name}), got Village ID={survey.village_id.id} (UUID={survey.village_id.village_uuid}, Name={survey.village_id.name})")
                    continue
                if survey.village_id.village_uuid != village_uuid:
                    _logger.error(f"FILTERING OUT Survey {survey.id}: Village UUID mismatch! Expected {village_uuid}, got {survey.village_id.village_uuid}")
                    continue
                # Survey is correct, include it
                correct_survey_ids.append(survey.id)
            
            # Use only the correct survey IDs
            if len(correct_survey_ids) != len(res_ids):
                _logger.warning(f"Filtered out {len(res_ids) - len(correct_survey_ids)} incorrect surveys. Using {len(correct_survey_ids)} correct surveys.")
            
            if not correct_survey_ids:
                _logger.error("No correct surveys found after filtering!")
                return request.not_found("No valid surveys found for this project and village")
            
            # Update res_ids to only include correct surveys
            res_ids = correct_survey_ids
            
            _logger.debug("Rendering PDF with %d res_ids", len(res_ids))
            
            # Invalidate report cache to ensure fresh generation
            # This prevents any caching issues that might cause the wrong data to appear
            report_action.invalidate_recordset(['report_name', 'report_file'])
            
            # Render PDF directly - Odoo will populate 'docs' in template with these records
            # _render_qweb_pdf signature: (reportname, docids, data=None)
            # Odoo automatically populates 'docs' from res_ids, so we don't need to pass it explicitly
            report_name = report_action.report_name
            
            # Verify surveys exist before rendering
            verify_surveys = request.env['bhu.survey'].sudo().browse(res_ids)
            _logger.debug("Verifying %d surveys before PDF render", len(verify_surveys))
            if not verify_surveys:
                _logger.error("No surveys found to render PDF!")
                return request.not_found("No surveys found for PDF generation")
            
            data = {
                'report_type': 'qweb-pdf',
                'context': {
                    'project_id': project.id,
                    'village_id': village.id,
                }
            }
            try:
                pdf_result = report_action.sudo()._render_qweb_pdf(report_name, res_ids, data=data)
            except Exception as render_error:
                # Fallback: try with minimal data
                _logger.warning(f"PDF render with data failed: {str(render_error)}, trying fallback")
                try:
                    pdf_result = report_action.sudo()._render_qweb_pdf(report_name, res_ids, data={})
                except Exception as render_error2:
                    _logger.error(f"PDF rendering failed: {str(render_error2)}", exc_info=True)
                    # Final fallback: redirect to Odoo's standard URL (use first survey ID)
                    if all_surveys:
                        report_url = f'/report/pdf/{report_action.report_name}/{all_surveys[0].id}'
                        return request.redirect(report_url)
                    return request.not_found("No surveys available for PDF generation")
            
            # Extract PDF bytes from result
            if not pdf_result:
                return request.not_found("Error: PDF rendering returned empty result")
            
            # Handle tuple/list result (pdf_bytes, format)
            if isinstance(pdf_result, (tuple, list)) and len(pdf_result) > 0:
                pdf_data = pdf_result[0]
            else:
                pdf_data = pdf_result
            
            # Ensure pdf_data is bytes
            if not isinstance(pdf_data, bytes):
                if isinstance(pdf_data, str):
                    pdf_data = pdf_data.encode('utf-8')
                else:
                    _logger.error(f"Unexpected PDF data type: {type(pdf_data)}")
                    return request.not_found(f"Error: Invalid PDF data type: {type(pdf_data)}")
            
            # Return PDF with Form10_<project>_<village>.pdf (unicode in filename* — header is Latin-1 safe)
            export_utils = request.env['form10.export.utils']
            filename = export_utils.generate_form10_filename(
                verify_surveys,
                'pdf',
                project_name=project.name,
                village_name=village.name,
            )
            content_disp = export_utils.content_disposition_attachment(
                filename, ascii_fallback='Form10_Export.pdf'
            )
            return request.make_response(
                pdf_data,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', content_disp),
                    ('Content-Length', str(len(pdf_data)))
                ]
            )
            
        except Exception as e:
            _logger.error(f"Error generating PDF for project {project_uuid} and village {village_uuid}: {str(e)}", exc_info=True)
            return request.not_found(f"Error generating PDF: {str(e)}")
    
class Section4DownloadController(http.Controller):

    @http.route(
        '/bhuarjan/section4/<path:notification_uuid>/download',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        website=False
    )
    def download_section4_pdf(self, notification_uuid, **kwargs):
        _logger.info(
            "Section 4 PDF download route called: notification_uuid=%s",
            notification_uuid
        )

        try:
            # ---------------------------------------------------------
            # 1️⃣ Find notification using UUID
            # ---------------------------------------------------------
            notification = (
                request.env['bhu.section4.notification']
                .sudo()
                .search([('notification_uuid', '=', notification_uuid)], limit=1)
            )

            if not notification:
                return request.not_found("Notification not found")

            # ---------------------------------------------------------
            # 2️⃣ Serve signed document if exists
            # ---------------------------------------------------------
            if notification.signed_document_file:
                pdf_data = base64.b64decode(notification.signed_document_file)
                filename = (
                    notification.signed_document_filename
                    or f"Section4_Notification_{notification.name}_Signed.pdf"
                )
                cd = request.env['form10.export.utils'].content_disposition_attachment(
                    filename, ascii_fallback='Section4_Notification.pdf'
                )
                return request.make_response(
                    pdf_data,
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Disposition', cd),
                        ('Content-Length', str(len(pdf_data))),
                    ],
                )

            # ---------------------------------------------------------
            # 3️⃣ Generate unsigned PDF
            # ---------------------------------------------------------
            report_action = request.env.ref(
                'bhukhadan_core.action_report_section4_notification'
            ).sudo()

            # ---------------------------------------------------------
            # 4️⃣ Odoo 18 compatible PDF render (use notification record, not wizard)
            # ---------------------------------------------------------
            pdf_data, _ = report_action._render_qweb_pdf(
                report_action.report_name,
                res_ids=[notification.id],
                data={}
            )

            filename = f"Section4_Notification_{notification.name}.pdf"
            cd = request.env['form10.export.utils'].content_disposition_attachment(
                filename, ascii_fallback='Section4_Notification.pdf'
            )
            return request.make_response(
                pdf_data,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', cd),
                    ('Content-Length', str(len(pdf_data))),
                ],
            )

        except Exception as e:
            _logger.exception("Error in download_section4_pdf")
            return request.not_found(str(e))
    
    @http.route('/bhuarjan/sia/<path:sia_team_uuid>/download', type='http', auth='public', methods=['GET'], csrf=False, website=False)
    def download_sia_pdf(self, sia_team_uuid, **kwargs):
        """Download SIA Team PDF using SIA team UUID"""
        _logger.info(f"SIA PDF download route called: sia_team_uuid={sia_team_uuid}")
        try:
            # Find SIA team by UUID
            sia_team = request.env['bhu.sia.team'].sudo().with_context({}).search([('sia_team_uuid', '=', sia_team_uuid)], limit=1)
            
            if not sia_team:
                _logger.error(f"SIA team not found with UUID: {sia_team_uuid}")
                return request.not_found("SIA team not found")
            
            _logger.info(f"SIA team found: id={sia_team.id}, name={sia_team.name}")
            
            # Generate PDF
            _logger.info("Generating SIA PDF")
            try:
                report_action = request.env.ref('bhukhadan_core.action_report_sia_order').sudo()
            except ValueError:
                _logger.error("SIA download: Report action not found")
                return request.not_found("Report not found")
            
            if not report_action.exists():
                _logger.error("SIA download: Report action does not exist")
                return request.not_found("Report not found")
            
            # Generate PDF directly from SIA team record
            pdf_data, _ = report_action._render_qweb_pdf(
                report_action.report_name,
                res_ids=[sia_team.id],
                data={}
            )
            
            if not pdf_data:
                return request.not_found("Error: PDF rendering returned empty result")
            
            filename = f"SIA_{sia_team.name or sia_team.id}.pdf"
            cd = request.env['form10.export.utils'].content_disposition_attachment(
                filename, ascii_fallback='SIA_Export.pdf'
            )
            return request.make_response(
                pdf_data,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', cd),
                    ('Content-Length', str(len(pdf_data))),
                ]
            )
        
        except Exception as e:
            _logger.error(f"Error in download_sia_pdf: {str(e)}", exc_info=True)
            return request.not_found(f"Error: {str(e)}")
    
    @http.route('/bhuarjan/expert/<path:expert_committee_uuid>/download', type='http', auth='public', methods=['GET'], csrf=False, website=False)
    def download_expert_committee_pdf(self, expert_committee_uuid, **kwargs):
        """Download Expert Committee Report PDF using Expert Committee UUID"""
        _logger.info(f"Expert Committee PDF download route called: expert_committee_uuid={expert_committee_uuid}")
        try:
            # Find Expert Committee Report by UUID
            expert_report = request.env['bhu.expert.committee.report'].sudo().with_context({}).search([('expert_committee_uuid', '=', expert_committee_uuid)], limit=1)
            
            if not expert_report:
                _logger.error(f"Expert Committee Report not found with UUID: {expert_committee_uuid}")
                return request.not_found("Expert Committee Report not found")
            
            _logger.info(f"Expert Committee Report found: id={expert_report.id}, name={expert_report.name}")
            
            # Generate PDF
            _logger.info("Generating Expert Committee PDF")
            try:
                report_action = request.env.ref('bhukhadan_core.action_report_expert_committee_proposal').sudo()
            except ValueError:
                _logger.error("Expert Committee download: Report action not found")
                return request.not_found("Report not found")
            
            if not report_action.exists():
                _logger.error("Expert Committee download: Report action does not exist")
                return request.not_found("Report not found")
            
            # Generate PDF directly from Expert Committee Report record
            pdf_data, _ = report_action._render_qweb_pdf(
                report_action.report_name,
                res_ids=[expert_report.id],
                data={}
            )
            
            if not pdf_data:
                return request.not_found("Error: PDF rendering returned empty result")
            
            filename = f"Expert_Committee_{expert_report.name or expert_report.id}.pdf"
            cd = request.env['form10.export.utils'].content_disposition_attachment(
                filename, ascii_fallback='Expert_Committee.pdf'
            )
            return request.make_response(
                pdf_data,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', cd),
                    ('Content-Length', str(len(pdf_data))),
                ]
            )
        
        except Exception as e:
            _logger.error(f"Error in download_expert_committee_pdf: {str(e)}", exc_info=True)
            return request.not_found(f"Error: {str(e)}")
    
    @http.route('/bhuarjan/section11/<path:report_uuid>/download', type='http', auth='public', methods=['GET'], csrf=False, website=False)
    def download_section11_pdf(self, report_uuid, **kwargs):
        """Download Section 11 Preliminary Report PDF using report UUID - serves signed document if exists, else unsigned PDF"""
        _logger.info(f"Section 11 PDF download route called: report_uuid={report_uuid}")
        try:
            # Find report by UUID
            report = request.env['bhu.section11.preliminary.report'].sudo().with_context({}).search([('report_uuid', '=', report_uuid)], limit=1)
            
            if not report:
                _logger.error(f"Report not found with UUID: {report_uuid}")
                return request.not_found("Report not found")
            
            _logger.info(f"Report found: id={report.id}, name={report.name}, has_signed={bool(report.signed_document_file)}")
            
            # If signed document exists, serve it
            if report.signed_document_file:
                _logger.info("Serving signed document")
                pdf_data = base64.b64decode(report.signed_document_file)
                filename = report.signed_document_filename or f"Section11_Preliminary_Report_{report.name}_Signed.pdf"
                cd = request.env['form10.export.utils'].content_disposition_attachment(
                    filename, ascii_fallback='Section11_Report.pdf'
                )
                response = request.make_response(
                    pdf_data,
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Disposition', cd),
                        ('Content-Length', str(len(pdf_data))),
                    ]
                )
                return response
            
            # Otherwise, generate unsigned PDF
            _logger.info("Generating unsigned PDF")
            try:
                report_action = request.env.ref('bhukhadan_core.action_report_section11_preliminary').sudo()
            except ValueError:
                return request.not_found("Report not found")
            
            # Generate PDF directly from report record
            pdf_data, _ = report_action._render_qweb_pdf(
                report_action.report_name,
                res_ids=[report.id],
                data={}
            )
            
            if not pdf_data:
                return request.not_found("Error: PDF rendering returned empty result")
            
            filename = f"Section11_Preliminary_Report_{report.name}.pdf"
            cd = request.env['form10.export.utils'].content_disposition_attachment(
                filename, ascii_fallback='Section11_Report.pdf'
            )
            return request.make_response(
                pdf_data,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', cd),
                    ('Content-Length', str(len(pdf_data))),
                ]
            )
        
        except Exception as e:
            _logger.error(f"Error in download_section11_pdf: {str(e)}", exc_info=True)
            return request.not_found(f"Error: {str(e)}")
    
    @http.route('/bhuarjan/section19/<path:notification_uuid>/download', type='http', auth='public', methods=['GET'], csrf=False, website=False)
    def download_section19_pdf(self, notification_uuid, **kwargs):
        """Download Section 19 Notification PDF using notification UUID - serves signed document if exists, else unsigned PDF"""
        _logger.info(f"Section 19 PDF download route called: notification_uuid={notification_uuid}")
        try:
            # Find notification by UUID
            notification = request.env['bhu.section19.notification'].sudo().with_context({}).search([('notification_uuid', '=', notification_uuid)], limit=1)
            
            if not notification:
                _logger.error(f"Notification not found with UUID: {notification_uuid}")
                return request.not_found("Notification not found")
            
            _logger.info(f"Notification found: id={notification.id}, name={notification.name}, has_signed={bool(notification.signed_document_file)}")
            
            # If signed document exists, serve it
            if notification.signed_document_file:
                _logger.info("Serving signed document")
                pdf_data = base64.b64decode(notification.signed_document_file)
                filename = notification.signed_document_filename or f"Section19_Notification_{notification.name}_Signed.pdf"
                cd = request.env['form10.export.utils'].content_disposition_attachment(
                    filename, ascii_fallback='Section19_Notification.pdf'
                )
                response = request.make_response(
                    pdf_data,
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Disposition', cd),
                        ('Content-Length', str(len(pdf_data))),
                    ]
                )
                return response
            
            # Otherwise, generate unsigned PDF
            _logger.info("Generating unsigned PDF")
            try:
                report_action = request.env.ref('bhukhadan_core.action_report_section19_notification').sudo()
            except ValueError:
                return request.not_found("Report not found")
            
            # Generate PDF directly from notification record
            pdf_data, _ = report_action._render_qweb_pdf(
                report_action.report_name,
                res_ids=[notification.id],
                data={}
            )
            
            if not pdf_data:
                return request.not_found("Error: PDF rendering returned empty result")
            
            filename = f"Section19_Notification_{notification.name}.pdf"
            cd = request.env['form10.export.utils'].content_disposition_attachment(
                filename, ascii_fallback='Section19_Notification.pdf'
            )
            return request.make_response(
                pdf_data,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', cd),
                    ('Content-Length', str(len(pdf_data))),
                ]
            )
        
        except Exception as e:
            _logger.error(f"Error in download_section19_pdf: {str(e)}", exc_info=True)
            return request.not_found(f"Error: {str(e)}")
    
    @http.route('/bhuarjan/section21/<path:notification_uuid>/download', type='http', auth='public', methods=['GET'], csrf=False, website=False)
    def download_section21_pdf(self, notification_uuid, **kwargs):
        """Download Section 21 Notification PDF using notification UUID - serves signed document if exists, else unsigned PDF"""
        _logger.info(f"Section 21 PDF download route called: notification_uuid={notification_uuid}")
        try:
            # Find notification by UUID
            notification = request.env['bhu.section21.notification'].sudo().with_context({}).search([('notification_uuid', '=', notification_uuid)], limit=1)
            
            if not notification:
                _logger.error(f"Notification not found with UUID: {notification_uuid}")
                return request.not_found("Notification not found")
            
            _logger.info(f"Notification found: id={notification.id}, name={notification.name}, has_signed={bool(notification.signed_document_file)}")
            
            # If signed document exists, serve it
            if notification.signed_document_file:
                _logger.info("Serving signed document")
                pdf_data = base64.b64decode(notification.signed_document_file)
                filename = notification.signed_document_filename or f"Section21_Notification_{notification.name}_Signed.pdf"
                cd = request.env['form10.export.utils'].content_disposition_attachment(
                    filename, ascii_fallback='Section21_Notification.pdf'
                )
                response = request.make_response(
                    pdf_data,
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Disposition', cd),
                        ('Content-Length', str(len(pdf_data))),
                    ]
                )
                return response
            
            # Otherwise, generate unsigned PDF
            _logger.info("Generating unsigned PDF")
            try:
                report_action = request.env.ref('bhukhadan_core.action_report_section21_notification').sudo()
            except ValueError:
                return request.not_found("Report not found")
            
            # Generate PDF directly from notification record
            pdf_data, _ = report_action._render_qweb_pdf(
                report_action.report_name,
                res_ids=[notification.id],
                data={}
            )
            
            if not pdf_data:
                return request.not_found("Error: PDF rendering returned empty result")
            
            filename = f"Section21_Notification_{notification.name}.pdf"
            cd = request.env['form10.export.utils'].content_disposition_attachment(
                filename, ascii_fallback='Section21_Notification.pdf'
            )
            return request.make_response(
                pdf_data,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', cd),
                    ('Content-Length', str(len(pdf_data))),
                ]
            )
        
        except Exception as e:
            _logger.error(f"Error in download_section21_pdf: {str(e)}", exc_info=True)
            return request.not_found(f"Error: {str(e)}")