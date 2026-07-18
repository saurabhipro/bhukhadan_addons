from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import csv
import uuid
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

class ReportWizard(models.TransientModel):
    _name = 'report.wizard'
    _description = 'Report Wizard'

    report_type = fields.Selection([
        ('form5', 'Form 5'),
        ('form6', 'Form 6'),
        ('dols', 'DOLS'),
    ], string='Report Type', default='form5', required=True)
    export_type = fields.Selection([
        ('pdf', 'PDF'),
    ], string='Export Type', default='pdf', required=True)
    project_id = fields.Many2one('bhu.project', string='Project ID')
    village_id = fields.Many2one('bhu.village', string='Village ID')
    project_name = fields.Char(string='Project / परियोजना', readonly=True)
    village_name = fields.Char(string='Village / ग्राम', readonly=True)
    allowed_village_ids = fields.Many2many(
        'bhu.village',
        string='Allowed Villages',
        compute='_compute_allowed_village_ids',
        store=False,
    )
    
    @api.model
    def default_get(self, fields_list):
        """Override to populate project and village names from context"""
        res = super(ReportWizard, self).default_get(fields_list)
        if self.env.context.get('default_report_type'):
            res['report_type'] = self.env.context.get('default_report_type')
        
        # Get project and village from context; fallback to dashboard selection
        project_id = self.env.context.get('default_project_id')
        village_id = self.env.context.get('default_village_id')
        if not project_id or not village_id:
            saved_selection = self.env['bhuarjan.dashboard'].get_dashboard_selection() or {}
            project_id = project_id or saved_selection.get('project_id')
            village_id = village_id or saved_selection.get('village_id')
        
        # Fetch project name
        if project_id:
            project = self.env['bhu.project'].browse(project_id)
            if project.exists():
                res['project_id'] = project_id
                res['project_name'] = project.name
        
        # Fetch village name
        if village_id:
            village = self.env['bhu.village'].browse(village_id)
            if village.exists():
                res['village_id'] = village_id
                res['village_name'] = village.name
        
        return res
    
    @api.depends('project_id')
    def _compute_allowed_village_ids(self):
        """Compute allowed villages based on project and user role"""
        for wizard in self:
            if wizard.project_id and wizard.project_id.village_ids:
                # Get project villages
                project_village_ids = wizard.project_id.village_ids.ids
                if wizard.env.user.bhuarjan_role == 'patwari':
                    user_village_ids = wizard.env.user._patwari_assigned_villages().ids
                    allowed_ids = list(set(project_village_ids) & set(user_village_ids))
                else:
                    # For other users, show all project villages
                    allowed_ids = project_village_ids
                wizard.allowed_village_ids = [(6, 0, allowed_ids)]
            else:
                # No project selected or project has no villages
                if wizard.env.user.bhuarjan_role == 'patwari':
                    wizard.allowed_village_ids = [(6, 0, wizard.env.user._patwari_assigned_villages().ids)]
                else:
                    # For other users, show no villages until project is selected
                    wizard.allowed_village_ids = [(6, 0, [])]
    
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Reset village when project changes and update domain to filter by project villages"""
        self.project_name = self.project_id.name if self.project_id else False
        self.village_id = False
        self.village_name = False
        if self.project_id and self.project_id.village_ids:
            # Get project villages
            project_village_ids = self.project_id.village_ids.ids
            if self.env.user.bhuarjan_role == 'patwari':
                user_village_ids = self.env.user._patwari_assigned_villages().ids
                allowed_ids = list(set(project_village_ids) & set(user_village_ids))
            else:
                # For other users, show all project villages
                allowed_ids = project_village_ids
            return {'domain': {'village_id': [('id', 'in', allowed_ids)]}}
        else:
            # No project selected or project has no villages
            if self.env.user.bhuarjan_role == 'patwari':
                return {'domain': {'village_id': [('id', 'in', self.env.user._patwari_assigned_villages().ids)]}}
            else:
                # For other users, show no villages until project is selected
                return {'domain': {'village_id': [('id', '=', False)]}}

    @api.onchange('village_id')
    def _onchange_village_id(self):
        self.village_name = self.village_id.name if self.village_id else False

    def action_print_report(self):
        """Generate selected report (Form 5/6/DOLS/Form 10) in selected format."""
        # If Many2one fields are empty but we have names, reconstruct them
        # This can happen when invisible fields don't save properly
        if not self.project_id and self.project_name:
            # Try to find project from saved selection or user's department
            saved_selection = self.env['bhuarjan.dashboard'].get_dashboard_selection()
            if saved_selection.get('project_id'):
                self.project_id = saved_selection['project_id']
        
        if not self.village_id and self.village_name:
            # Try to find village from saved selection
            saved_selection = self.env['bhuarjan.dashboard'].get_dashboard_selection()
            if saved_selection.get('village_id'):
                self.village_id = saved_selection['village_id']
        
        # Validate that project and village are now set
        if not self.project_id:
            raise UserError("Please select a project.")
        
        if not self.village_id:
            raise UserError("Please select a village.")
        
        # Role-based validation for patwari
        patwari_village_ids = self.env.user._patwari_assigned_villages().ids
        if self.env.user.bhuarjan_role == 'patwari' and self.village_id.id not in patwari_village_ids:
            raise UserError("You are not allowed to download for this village.")
        
        # Ensure UUIDs exist and are UNIQUE
        if not self.project_id.project_uuid:
            self.project_id.write({'project_uuid': str(uuid.uuid4())})
        
        # Check for duplicate village UUIDs - regenerate if found
        if not self.village_id.village_uuid:
            self.village_id.write({'village_uuid': str(uuid.uuid4())})
        else:
            # Verify this UUID is unique to this village
            duplicate_villages = self.env['bhu.village'].search([
                ('village_uuid', '=', self.village_id.village_uuid),
                ('id', '!=', self.village_id.id)
            ])
            if duplicate_villages:
                _logger.warning(f"Village {self.village_id.id} ({self.village_id.name}) has duplicate UUID! Regenerating...")
                self.village_id.write({'village_uuid': str(uuid.uuid4())})
        
        selected_village_id = self.village_id.id
        selected_village_name = self.village_id.name
        selected_village_uuid = self.village_id.village_uuid
        selected_project_id = self.project_id.id
        selected_project_name = self.project_id.name

        _logger.debug(
            "Wizard: project=%s[%s], village=%s[%s] uuid=%s",
            selected_project_name, selected_project_id,
            selected_village_name, selected_village_id, selected_village_uuid,
        )

        domain = [
            '&',
            ('project_id', '=', selected_project_id),
            ('village_id', '=', selected_village_id),
        ]

        all_records = self.env['bhu.survey'].sudo().with_context(
            active_test=False,
            bhuarjan_current_project_id=False
        ).search(domain, order='id')

        _logger.debug("Wizard: search returned %d surveys", len(all_records))

        correct_records = self.env['bhu.survey']
        debug_on = _logger.isEnabledFor(logging.DEBUG)
        for survey in all_records:
            survey_village_id = survey.village_id.id
            survey_project_id = survey.project_id.id

            if survey_project_id != selected_project_id:
                _logger.error(
                    "Wizard: SKIP survey %s – wrong project (got %s, expected %s)",
                    survey.id, survey_project_id, selected_project_id,
                )
                continue
            if survey_village_id != selected_village_id:
                _logger.error(
                    "Wizard: SKIP survey %s – wrong village (got %s, expected %s)",
                    survey.id, survey_village_id, selected_village_id,
                )
                continue

            if debug_on:
                _logger.debug("Wizard: survey %s valid", survey.id)
            correct_records |= survey

        if not correct_records:
            _logger.warning(
                "Wizard: no valid surveys for project %s village %s",
                selected_project_id, selected_village_id,
            )
            raise UserError(f"No records found for this project ({selected_project_name}) and village ({selected_village_name}).")

        if len(correct_records) != len(all_records):
            _logger.warning(
                "Wizard: filtered out %d wrong surveys, keeping %d",
                len(all_records) - len(correct_records), len(correct_records),
            )

        _logger.info(
            "Wizard: %d surveys for project=%s[%s] village=%s[%s]",
            len(correct_records), selected_project_name, selected_project_id,
            selected_village_name, selected_village_id,
        )
        _logger.debug("Wizard: survey IDs=%s", correct_records.ids)
        
        all_records = correct_records

        if self.export_type == 'pdf':
            if self.report_type == 'form5':
                return self.env.ref('bhukhadan_core.action_report_form5_bulk').report_action(all_records)
            if self.report_type == 'form6':
                return self.env.ref('bhukhadan_core.action_report_form6_bulk').report_action(all_records)
            if self.report_type == 'dols':
                return self.env.ref('bhukhadan_core.action_report_dols_bulk').report_action(all_records)
            raise UserError(_("Unsupported report type selected."))
        elif self.export_type == 'excel':
            raise UserError(_("Excel export is not available for Coal Act report downloads."))
        elif self.export_type == 'csv':
            raise UserError(_("CSV export is not available for Coal Act report downloads."))

    def _export_to_excel(self, surveys):
        """Export surveys to Excel format matching PDF structure"""
        # Use utility function to generate Excel
        export_utils = self.env['form10.export.utils']
        excel_data = export_utils.generate_form10_excel(surveys)
        
        # Generate filename (explicit project/village from wizard; keeps Hindi names)
        filename = export_utils.generate_form10_filename(
            surveys,
            file_extension='xlsx',
            project_name=self.project_id.name if self.project_id else None,
            village_name=self.village_id.name if self.village_id else None,
        )
        
        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(excel_data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'report.wizard',
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def _export_to_csv(self, surveys):
        """Export surveys to CSV format matching PDF structure"""
        if not surveys:
            raise UserError(_("No surveys found."))
        
        output = io.StringIO()
        writer = csv.writer(output)
        first = surveys[0]
        
        # Process surveys in chunks of 5
        for start_idx in range(0, len(surveys), 5):
            chunk = surveys[start_idx:start_idx + 5]
            
            # Title
            writer.writerow(['भू-अर्जन फार्म-10 (प्रारंभिक सर्वे प्रपत्र)'] + [''] * 17)
            writer.writerow([])  # Empty row
            
            # Header info (project/department/village/tehsil/date)
            project_name = first.project_id.name or ''
            dept_name = first.department_id.name or ''
            village_name = first.village_id.name or ''
            tehsil_name = first.tehsil_id.name or ''
            survey_date_str = first.survey_date.strftime('%d/%m/%Y') if first.survey_date else ''
            
            writer.writerow(['परियोजना का नाम :', project_name] + [''] * 16)
            writer.writerow(['विभाग का नाम', dept_name] + [''] * 16)
            writer.writerow(['ग्राम का नाम', village_name] + [''] * 16)
            writer.writerow(['तहसील का नाम', f"{tehsil_name} जिला-रायगढ़ (छ.ग.)"] + [''] * 16)
            writer.writerow(['सर्वे दिनाँक', survey_date_str] + [''] * 16)
            writer.writerow([])  # Empty row
            
            # Table headers (2 rows - matching PDF structure)
            # First header row
            writer.writerow([
                'क्र.', 'प्रभावित खसरा क्रमांक', 'कुल रकबा (हे.में.)', 
                'अर्जन हेतु प्रस्तावित क्षेत्रफल (हेक्टेयर)', 'भूमिस्वामी का नाम',
                'भूमि का प्रकार', '', '', '',
                'भूमि पर स्थित वृक्ष की संख्या (प्रजातिवार)', '', '',
                'भूमि पर स्थित परिसंपत्तियों का विवरण', '', '', '', '', ''
            ])
            # Second header row
            writer.writerow([
                '', '', '', '', '',
                'एक फसली', 'दो फसली', 'सिंचित', 'असिंचित',
                'अविकसित', 'अर्द्ध विकसित', 'पूर्ण विकसित',
                'मकान (कच्चा/पक्का) क्षेत्रफल वर्गफुट में', 'शेड (क्षेत्रफल वर्गफुट में)',
                'कुँआ (कच्चा/पक्का) (हाँ/नहीं)', 'ट्यूबवेल / सम्बमर्शिबल पम्प फिटिंग सहित (हाँ/नहीं)', 
                'तालाब (हाँ/नहीं)', 'रिमार्क'
            ])
            
            # Data rows (max 5 per chunk)
            for idx, survey in enumerate(chunk):
                serial_num = start_idx + idx + 1
                
                # Get landowner names (see form10_export_utils: sudo for linked rows only)
                owner_names = []
                counter = 1
                for lo in survey.landowner_ids.sudo():
                    name = lo.name
                    if lo.father_name:
                        name += f" पिता {lo.father_name}"
                    elif lo.spouse_name:
                        name += f" पति {lo.spouse_name}"
                    owner_names.append(f"{counter}. {name}")
                    counter += 1
                owner_str = ", ".join(owner_names) if owner_names else "नहीं"
                
                # Well type
                well_str = "नहीं"
                if survey.has_well == 'yes':
                    if survey.well_type == 'kaccha':
                        well_str = "हाँ-कच्चा"
                    elif survey.well_type == 'pakka':
                        well_str = "हाँ-पक्का"
                
                # House type
                house_str = "नहीं"
                if survey.house_type and survey.house_area:
                    house_str = f"{survey.house_type} / {survey.house_area}"
                
                data = [
                    serial_num,
                    survey.khasra_number or "नहीं",
                    survey.total_area or 0,
                    survey.acquired_area or 0,
                    owner_str,
                    "हाँ" if survey.is_single_crop else "नहीं",
                    "हाँ" if survey.is_double_crop else "नहीं",
                    "हाँ" if survey.is_irrigated else "नहीं",
                    "हाँ" if survey.is_unirrigated else "नहीं",
                    survey.undeveloped_tree_count if survey.undeveloped_tree_count > 0 else "नहीं",
                    survey.semi_developed_tree_count if survey.semi_developed_tree_count > 0 else "नहीं",
                    survey.fully_developed_tree_count if survey.fully_developed_tree_count > 0 else "नहीं",
                    house_str,
                    survey.shed_area or "नहीं",
                    well_str,
                    "हाँ" if survey.has_tubewell == 'yes' else "नहीं",
                    "हाँ" if survey.has_pond == 'yes' else "नहीं",
                    survey.remarks or "नहीं"
                ]
                
                writer.writerow(data)
            
            # Signature section after each chunk of 5 rows
            writer.writerow([])  # Empty row
            writer.writerow(['(हस्ताक्षर)', 'अपेक्षक निकाय के अधिकृत प्रतिनिधि', '', '', '',
                            '(हस्ताक्षर)', 'तहसीलदार', '', '', '',
                            '(हस्ताक्षर)', 'नायब तहसीलदार', '', '', '',
                            '(हस्ताक्षर)', 'राजस्व निरीक्षक', '', ''])
            writer.writerow(['नाम -', 'पदनाम', '', '', '',
                            'नाम -', '', '', '', '',
                            'नाम -', '', '', '', '',
                            'नाम-', 'रा.नि.मं.', '', ''])
            writer.writerow([])  # Empty row before next chunk
            writer.writerow([])  # Extra spacing
        
        csv_data = output.getvalue()
        output.close()
        
        # Create attachment — same naming as PDF/Excel: Form10_<project>_<village>.csv
        export_utils = self.env['form10.export.utils']
        filename = export_utils.generate_form10_filename(
            surveys,
            file_extension='csv',
            project_name=self.project_id.name if self.project_id else None,
            village_name=self.village_id.name if self.village_id else None,
        )
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(csv_data.encode('utf-8-sig')),
            'mimetype': 'text/csv',
            'res_model': 'report.wizard',
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
