# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class S23TreeEditWizard(models.TransientModel):
    _name = 'bhu.s23.tree.edit.wizard'
    _description = 'Section 23 - Edit tree inputs'

    survey_line_id = fields.Many2one(
        'bhu.section23.award.survey.line',
        string='Survey line',
        required=True,
        ondelete='cascade',
    )
    survey_id = fields.Many2one(
        'bhu.survey',
        string='Survey',
        related='survey_line_id.survey_id',
        readonly=True,
    )
    khasra_display = fields.Char(string='Khasra / खसरा', readonly=True)
    tree_line_ids = fields.One2many(
        'bhu.s23.tree.edit.wizard.line',
        'wizard_id',
        string='Tree rows',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get('default_survey_line_id')
        if not line_id:
            return res
        line = self.env['bhu.section23.award.survey.line'].browse(line_id)
        if not (line.exists() and line.survey_id):
            return res
        commands = []
        for tline in line.survey_id.tree_line_ids:
            commands.append((0, 0, {
                'tree_master_id': tline.tree_master_id.id,
                'development_stage': tline.development_stage,
                'girth_cm': tline.girth_cm,
                'quantity': tline.quantity,
                'is_other_tree': bool(tline.is_other_tree),
                'tree_description': tline.tree_description,
            }))
        res.update({
            'survey_line_id': line.id,
            'khasra_display': line.survey_id.khasra_number or '',
            'tree_line_ids': commands,
        })
        return res

    def action_apply(self):
        self.ensure_one()
        survey = self.survey_id
        if not survey:
            raise UserError(_('No survey linked on this line.'))
        if any((line.quantity or 0) <= 0 for line in self.tree_line_ids):
            raise UserError(_('Tree quantity must be greater than zero for all rows.'))

        commands = [(5, 0, 0)]
        fallback_other_tree = self.env['bhu.tree.master'].search([
            ('name', 'ilike', 'other')
        ], order='id asc', limit=1)
        for line in self.tree_line_ids:
            tree_master = line.tree_master_id
            if line.is_other_tree and not tree_master:
                if not fallback_other_tree:
                    raise UserError(_('Please configure an "Other" tree in Tree Rate Master first.'))
                tree_master = fallback_other_tree
            commands.append((0, 0, {
                'tree_master_id': tree_master.id,
                'development_stage': line.development_stage,
                'girth_cm': line.girth_cm or 0.0,
                'quantity': int(line.quantity or 0),
                'is_other_tree': bool(line.is_other_tree),
                'tree_description': line.tree_description,
            }))
        survey.write({'tree_line_ids': commands})

        if self.survey_line_id and self.survey_line_id.award_id:
            self.survey_line_id.award_id.message_post(
                body=_(
                    'Tree details updated from Section 23 popup by <b>%(user)s</b> '
                    'for khasra <b>%(khasra)s</b>.'
                ) % {
                    'user': self.env.user.name,
                    'khasra': survey.khasra_number or '-',
                }
            )
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class S23TreeEditWizardLine(models.TransientModel):
    _name = 'bhu.s23.tree.edit.wizard.line'
    _description = 'Section 23 - Edit tree row'

    wizard_id = fields.Many2one(
        'bhu.s23.tree.edit.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    tree_master_id = fields.Many2one(
        'bhu.tree.master',
        string='Tree / वृक्ष',
        required=False,
    )
    is_other_tree = fields.Boolean(string='Other / अन्य', default=False)
    tree_description = fields.Char(string='Description / विवरण')
    tree_type = fields.Selection(
        related='tree_master_id.tree_type',
        string='Tree Type',
        readonly=True,
    )
    development_stage = fields.Selection([
        ('undeveloped', 'Undeveloped / अविकसित'),
        ('semi_developed', 'Semi-developed / अर्ध-विकसित'),
        ('fully_developed', 'Fully Developed / पूर्ण विकसित'),
    ], string='Development Stage / विकास स्तर', default='undeveloped')
    girth_cm = fields.Float(string='Girth (cm) / छाती (से.मी.)', digits=(10, 2))
    quantity = fields.Integer(string='Quantity / मात्रा', required=True, default=1)

    @api.onchange('is_other_tree')
    def _onchange_is_other_tree(self):
        for line in self:
            if line.is_other_tree:
                line.tree_master_id = False
            else:
                line.tree_description = False

    @api.constrains('is_other_tree', 'tree_master_id', 'tree_description')
    def _check_tree_other_requirements(self):
        for line in self:
            if line.is_other_tree and not (line.tree_description or '').strip():
                raise ValidationError(_('Please enter description when Other is selected.'))
            if not line.is_other_tree and not line.tree_master_id:
                raise ValidationError(_('Please select Tree when Other is not selected.'))
