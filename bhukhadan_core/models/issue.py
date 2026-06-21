from odoo import models, fields, api

class BhuKhadanIssue(models.Model):
    _name = 'bhuarjan.issue'
    _description = 'BhuKhadan Support Issue'
    _order = 'create_date desc'

    name = fields.Char(string='Subject', required=True)
    description = fields.Text(string='Description', required=True)
    screenshot = fields.Binary(string='Screenshot')
    screenshot_filename = fields.Char(string='Filename')
    user_id = fields.Many2one('res.users', string='Reported By', default=lambda self: self.env.user, readonly=True)
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], default='new', string='Status')
    section = fields.Selection([
        ('general', 'General'),
        ('section_4', 'Section 4'),
        ('section_11', 'Section 11'),
        ('section_15', 'Section 15'),
        ('section_19', 'Section 19'),
        ('award', 'Award'),
        ('payment', 'Payment'),
        ('other', 'Other'),
    ], string='Related Section', required=True, default='general')

class BhuKhadanIssueWizard(models.TransientModel):
    _name = 'bhuarjan.issue.wizard'
    _description = 'Report an Issue'

    name = fields.Char(string='Subject', required=True)
    description = fields.Text(string='Description', required=True)
    section = fields.Selection([
        ('general', 'General'),
        ('section_4', 'Section 4'),
        ('section_11', 'Section 11'),
        ('section_15', 'Section 15'),
        ('section_19', 'Section 19'),
        ('award', 'Award'),
        ('payment', 'Payment'),
        ('other', 'Other'),
    ], string='Related Section', required=True, default='general')
    screenshot = fields.Binary(string='Screenshot')
    screenshot_filename = fields.Char(string='Filename')

    def action_submit_issue(self):
        issue = self.env['bhuarjan.issue'].create({
            'name': self.name,
            'description': self.description,
            'section': self.section,
            'screenshot': self.screenshot,
            'screenshot_filename': self.screenshot_filename,
        })
        return {
            'type': 'ir.actions.act_window_close',
            'effect': {
                'fadeout': 'slow',
                'message': f'Issue #{issue.id} has been reported successfully.',
                'type': 'rainbow_man',
            }
        }
