from odoo import models, fields, tools

class AllSectionReport(models.Model):
    _name = 'bhu.all.section.report'
    _description = 'All Sections Report'
    _auto = False
    _order = 'create_date desc'

    name = fields.Char(string='Reference/Name', readonly=True)
    section_type = fields.Selection([
        ('sec4', 'Section 4 Notification'),
        ('sec11', 'Section 11 Preliminary Report'),
        ('sec19', 'Section 19 Notification'),
        ('sec21', 'Section 21 Notification'),
        ('sec23', 'Section 23 Award'),
        ('sia', 'SIA Team'),
        ('expert', 'Expert Committee'),
    ], string='Section Type', readonly=True)
    
    project_id = fields.Many2one('bhu.project', string='Project', readonly=True)
    village_id = fields.Many2one('bhu.village', string='Village', readonly=True)
    department_id = fields.Many2one('bhu.department', string='Department', readonly=True)
    status = fields.Char(string='Status', readonly=True)
    create_date = fields.Datetime(string='Created On', readonly=True)
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    (id + 100000000) as id,
                    name,
                    'sec4' as section_type,
                    project_id,
                    village_id,
                    (SELECT department_id FROM bhu_project WHERE id = project_id) as department_id,
                    state as status,
                    create_date
                FROM bhu_section4_notification
                
                UNION ALL
                
                SELECT
                    (id + 200000000) as id,
                    name,
                    'sec11' as section_type,
                    project_id,
                    village_id,
                    (SELECT department_id FROM bhu_project WHERE id = project_id) as department_id,
                    state as status,
                    create_date
                FROM bhu_section11_preliminary_report
                
                UNION ALL
                
                SELECT
                    (id + 300000000) as id,
                    name,
                    'sec19' as section_type,
                    project_id,
                    village_id,
                    (SELECT department_id FROM bhu_project WHERE id = project_id) as department_id,
                    state as status,
                    create_date
                FROM bhu_section19_notification
                
                UNION ALL
                
                SELECT
                    (id + 400000000) as id,
                    name,
                    'sec21' as section_type,
                    project_id,
                    village_id,
                    (SELECT department_id FROM bhu_project WHERE id = project_id) as department_id,
                    state as status,
                    create_date
                FROM bhu_section21_notification
                
                UNION ALL
                
                SELECT
                    (id + 500000000) as id,
                    name,
                    'sec23' as section_type,
                    project_id,
                    village_id,
                    (SELECT department_id FROM bhu_project WHERE id = project_id) as department_id,
                    state as status,
                    create_date
                FROM bhu_section23_award
                
                UNION ALL
                
                SELECT
                    (id + 600000000) as id,
                    name,
                    'sia' as section_type,
                    project_id,
                    village_id,
                    (SELECT department_id FROM bhu_project WHERE id = project_id) as department_id,
                    state as status,
                    create_date
                FROM bhu_sia_team

                UNION ALL
                
                SELECT
                    (id + 700000000) as id,
                    name,
                    'expert' as section_type,
                    project_id,
                    village_id,
                    (SELECT department_id FROM bhu_project WHERE id = project_id) as department_id,
                    state as status,
                    create_date
                FROM bhu_expert_committee_report
            )
        """ % (self._table,))

    def action_open_record(self):
        """Redirect to the actual record form view"""
        self.ensure_one()
        
        model_map = {
            'sec4': 'bhu.section4.notification',
            'sec11': 'bhu.section11.preliminary.report',
            'sec19': 'bhu.section19.notification',
            'sec21': 'bhu.section21.notification',
            'sec23': 'bhu.section23.award',
            'sia': 'bhu.sia.team',
            'expert': 'bhu.expert.committee.report',
        }
        
        res_model = model_map.get(self.section_type)
        if not res_model:
            return False
            
        # Extract the real ID by removing the prefix added in init()
        prefix_map = {
            'sec4': 100000000,
            'sec11': 200000000,
            'sec19': 300000000,
            'sec21': 400000000,
            'sec23': 500000000,
            'sia': 600000000,
            'expert': 700000000,
        }
        
        real_id = self.id - prefix_map.get(self.section_type)
        
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': res_model,
            'res_id': real_id,
            'view_mode': 'form',
            'target': 'current',
        }
