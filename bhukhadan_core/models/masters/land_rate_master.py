# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import ValidationError, UserError


class LandType(models.Model):
    _name = 'bhu.land.type'
    _description = 'Land Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Land Type', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    description = fields.Text(string='Description', tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Land Type code must be unique!')
    ]


class RateMaster(models.Model):
    _name = 'bhu.rate.master'
    _description = 'Land Rate Master - Land Valuation Rates'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='draft', tracking=True)

    # Location Information
    district_id = fields.Many2one(
        'bhu.district', string='District / जिला', required=True, tracking=True, ondelete='restrict',
    )
    tehsil_id = fields.Many2one(
        'bhu.tehsil', string='Tehsil / तहसील', tracking=True, ondelete='set null',
    )
    village_id = fields.Many2one(
        'bhu.village', string='Village / ग्राम', required=True, tracking=True, ondelete='cascade',
    )
    
    # Base Rate Information (one entry per village)
    # Square Meter Rates
    main_road_rate_sqm = fields.Monetary(string='Rate on Main Road (Sq. Meter)', 
                                         currency_field='currency_id', required=True, tracking=True,
                                         help='Rate per square meter for land on main road')
    
    other_road_rate_sqm = fields.Monetary(string='Rate Within Main Road Range (Sq. Meter)', 
                                         currency_field='currency_id', required=True, tracking=True,
                                         help='Rate per square meter for land within main road range')
    
    # Hectare Rates
    main_road_rate_hectare = fields.Monetary(string='Rate on Main Road (Hectare)', 
                                             currency_field='currency_id', required=True, tracking=True,
                                             help='Rate per hectare for land on main road')
    
    other_road_rate_hectare = fields.Monetary(string='Rate Within Main Road Range (Hectare)', 
                                             currency_field='currency_id', required=True, tracking=True,
                                             help='Rate per hectare for land within main road range')
    
    
    # Legacy fields (kept for backward compatibility, will be computed from hectare rates)
    main_road_rate = fields.Monetary(string='Main Road Rate (Within Main Road Range) / मुख्यमार्ग दर (मुख्यमार्ग सीमा के भीतर)', 
                                     currency_field='currency_id', compute='_compute_legacy_rates', store=True,
                                     help='Legacy field - computed from hectare rate')
    
    other_road_rate = fields.Monetary(string='Other Road Rate (Beyond Main Road Range) / अन्य दर (मुख्यमार्ग सीमा से अधिक)', 
                                     currency_field='currency_id', compute='_compute_legacy_rates', store=True,
                                     help='Legacy field - computed from hectare rate')
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.INR'))
    
    @api.depends('main_road_rate_hectare', 'other_road_rate_hectare')
    def _compute_legacy_rates(self):
        """Compute legacy rates from hectare rates for backward compatibility"""
        for record in self:
            record.main_road_rate = record.main_road_rate_hectare
            record.other_road_rate = record.other_road_rate_hectare
    
    # Computed fields to display all calculated rates (Square Meter)
    main_road_sqm_irrigated = fields.Monetary(string='Main Road - Irrigated (Sq. Meter) / मुख्यमार्ग - सिंचित (वर्ग मीटर)', 
                                               currency_field='currency_id', compute='_compute_all_rates', store=False)
    main_road_sqm_non_irrigated = fields.Monetary(string='Main Road - Non-Irrigated (Sq. Meter) / मुख्यमार्ग - असिंचित (वर्ग मीटर)', 
                                                   currency_field='currency_id', compute='_compute_all_rates', store=False)
    other_road_sqm_irrigated = fields.Monetary(string='Other Road - Irrigated (Sq. Meter) / अन्य - सिंचित (वर्ग मीटर)', 
                                                 currency_field='currency_id', compute='_compute_all_rates', store=False)
    other_road_sqm_non_irrigated = fields.Monetary(string='Other Road - Non-Irrigated (Sq. Meter) / अन्य - असिंचित (वर्ग मीटर)', 
                                                     currency_field='currency_id', compute='_compute_all_rates', store=False)
    
    # Computed fields to display all calculated rates (Hectare)
    main_road_hectare_irrigated = fields.Monetary(string='Main Road - Irrigated (Hectare) / मुख्यमार्ग - सिंचित (हेक्टेयर)', 
                                               currency_field='currency_id', compute='_compute_all_rates', store=False)
    main_road_hectare_non_irrigated = fields.Monetary(string='Main Road - Non-Irrigated (Hectare) / मुख्यमार्ग - असिंचित (हेक्टेयर)', 
                                                   currency_field='currency_id', compute='_compute_all_rates', store=False)
    other_road_hectare_irrigated = fields.Monetary(string='Other Road - Irrigated (Hectare) / अन्य - सिंचित (हेक्टेयर)', 
                                                 currency_field='currency_id', compute='_compute_all_rates', store=False)
    other_road_hectare_non_irrigated = fields.Monetary(string='Other Road - Non-Irrigated (Hectare) / अन्य - असिंचित (हेक्टेयर)', 
                                                     currency_field='currency_id', compute='_compute_all_rates', store=False)
    
    @api.depends('main_road_rate_sqm', 'other_road_rate_sqm', 'main_road_rate_hectare', 'other_road_rate_hectare')
    def _compute_all_rates(self):
        """Calculate all rate combinations for both square meter and hectare rates"""
        for record in self:
            # Square Meter Rates - Main Road
            record.main_road_sqm_irrigated = record.main_road_rate_sqm * 1.2 if record.main_road_rate_sqm else 0.0
            record.main_road_sqm_non_irrigated = record.main_road_rate_sqm * 0.8 if record.main_road_rate_sqm else 0.0
            
            # Square Meter Rates - Other Road
            record.other_road_sqm_irrigated = record.other_road_rate_sqm * 1.2 if record.other_road_rate_sqm else 0.0
            record.other_road_sqm_non_irrigated = record.other_road_rate_sqm * 0.8 if record.other_road_rate_sqm else 0.0
            
            # Hectare Rates - Main Road
            record.main_road_hectare_irrigated = record.main_road_rate_hectare * 1.2 if record.main_road_rate_hectare else 0.0
            record.main_road_hectare_non_irrigated = record.main_road_rate_hectare * 0.8 if record.main_road_rate_hectare else 0.0
            
            # Hectare Rates - Other Road
            record.other_road_hectare_irrigated = record.other_road_rate_hectare * 1.2 if record.other_road_rate_hectare else 0.0
            record.other_road_hectare_non_irrigated = record.other_road_rate_hectare * 0.8 if record.other_road_rate_hectare else 0.0
    
    # Effective Dates
    effective_from = fields.Date(string='Effective From', required=True, default=fields.Date.today, tracking=True)
    effective_to = fields.Date(string='Effective To', tracking=True)
    
    # Additional Information
    remarks = fields.Text(string='Remarks', tracking=True)
    
    # Company Information
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    company_name = fields.Char(related='company_id.name', string='Company Name', store=True)
    
    # Computed Fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    @api.onchange('village_id')
    def _onchange_village_id(self):
        """Auto-populate tehsil and district when village is selected"""
        if self.village_id:
            if self.village_id.tehsil_id:
                self.tehsil_id = self.village_id.tehsil_id
            if self.village_id.district_id:
                self.district_id = self.village_id.district_id
    
    @api.onchange('tehsil_id')
    def _onchange_tehsil_id(self):
        """Auto-populate district when tehsil is selected"""
        if self.tehsil_id and self.tehsil_id.district_id:
            self.district_id = self.tehsil_id.district_id
    
    @api.depends('district_id', 'village_id')
    def _compute_display_name(self):
        for record in self:
            if record.district_id and record.village_id:
                record.display_name = f"{record.district_id.name} - {record.village_id.name}"
            else:
                record.display_name = record.name
    
    @api.constrains('village_id', 'state')
    def _check_unique_active_village(self):
        """Ensure only one active rate master per village"""
        for record in self:
            if record.state == 'active' and record.village_id:
                existing = self.search([
                    ('village_id', '=', record.village_id.id),
                    ('state', '=', 'active'),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_('Only one active land rate master entry per village is allowed. Please deactivate the existing active entry for village "%s" first.') % record.village_id.name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bhu.rate.master') or _('New')
        return super(RateMaster, self).create(vals_list)

    def action_activate(self):
        self.write({'state': 'active'})

    def action_deactivate(self):
        self.write({'state': 'inactive'})

    def action_reset(self):
        self.write({'state': 'draft'})

    def unlink(self):
        """Allow delete: drop transient wizard rows that reference this rate master."""
        if self.filtered(lambda r: r.state == 'active'):
            raise UserError(_(
                'Active land rate masters cannot be deleted. Use "Deactivate" first, '
                'then delete the draft/inactive entry if still required.'
            ))
        wizards = self.env['bhu.rate.master.permutation.wizard'].sudo().search([
            ('rate_master_id', 'in', self.ids),
        ])
        if wizards:
            lines = self.env['bhu.rate.master.permutation.line'].sudo().search([
                ('wizard_id', 'in', wizards.ids),
            ])
            lines.unlink()
            wizards.unlink()
        return super().unlink()
    
    def action_view_permutations(self):
        """Open a wizard to view all rate permutations for this village"""
        self.ensure_one()
        permutations = self.get_all_permutations()
        
        # Create a transient model record to display permutations
        wizard = self.env['bhu.rate.master.permutation.wizard'].create({
            'rate_master_id': self.id,
        })
        
        # Create permutation lines
        for perm in permutations:
            self.env['bhu.rate.master.permutation.line'].create({
                'wizard_id': wizard.id,
                'road_proximity': perm['road_proximity'],
                'irrigation_status': perm['irrigation_status'],
                'is_diverted': perm['is_diverted'],
                'calculated_rate': perm['rate'],
            })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rate Permutations / दर क्रमचय'),
            'res_model': 'bhu.rate.master.permutation.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    @api.model
    def get_rate_for_land(self, district_id, village_id, irrigation_status, road_proximity, is_diverted=False):
        """
        Get the calculated rate for specific land parameters
        
        Rules:
        - Main Road (within_20m) uses main_road_rate
        - Other Road (beyond_20m) uses other_road_rate
        - Irrigated: +20% of base rate
        - Diverted: -20% of base rate
        - Non-Irrigated: base rate (no adjustment)
        """
        # Find the rate master for this village
        domain = [
            ('district_id', '=', district_id),
            ('village_id', '=', village_id),
            ('state', '=', 'active'),
            ('effective_from', '<=', fields.Date.today()),
            '|',
            ('effective_to', '=', False),
            ('effective_to', '>=', fields.Date.today())
        ]
        
        rate_record = self.search(domain, limit=1, order='effective_from desc')
        
        if not rate_record:
            return 0.0
        
        # Get base rate based on road proximity (using hectare rates)
        if road_proximity == 'within_20m':
            base_rate = rate_record.main_road_rate_hectare
        elif road_proximity == 'beyond_20m':
            base_rate = rate_record.other_road_rate_hectare
        else:
            base_rate = rate_record.main_road_rate_hectare  # Default to main road rate
        
        # Apply adjustments (both can apply independently)
        final_rate = base_rate
        
        # If diverted, reduce by 20%
        if is_diverted:
            final_rate = final_rate * 0.8
        
        # If irrigated, increase by 20%
        if irrigation_status == 'irrigated':
            final_rate = final_rate * 1.2
        # If non-irrigated, decrease by 20%
        elif irrigation_status == 'non_irrigated':
            final_rate = final_rate * 0.8
        
        return final_rate

    @api.model
    def get_all_rates_for_village(self, village_id):
        """Get all active rates for a specific village (returns single record per village now)"""
        domain = [
            ('village_id', '=', village_id),
            ('state', '=', 'active'),
            ('effective_from', '<=', fields.Date.today()),
            '|',
            ('effective_to', '=', False),
            ('effective_to', '>=', fields.Date.today())
        ]
        
        return self.search(domain, order='effective_from desc', limit=1)
    
    def get_all_permutations(self):
        """Get all rate permutations for this village entry"""
        self.ensure_one()
        permutations = []
        
        # All combinations
        for road_prox in ['within_20m', 'beyond_20m']:
            for irrig_status in ['irrigated', 'non_irrigated']:
                for diverted in [True, False]:
                    # Get base rate based on road proximity (using hectare rates)
                    if road_prox == 'within_20m':
                        base_rate = self.main_road_rate_hectare
                    elif road_prox == 'beyond_20m':
                        base_rate = self.other_road_rate_hectare
                    else:
                        base_rate = self.main_road_rate_hectare  # Default to main road rate
                    
                    # Apply adjustments (both can apply independently)
                    final_rate = base_rate
                    
                    # If diverted, reduce by 20%
                    if diverted:
                        final_rate = final_rate * 0.8
                    
                    # If irrigated, increase by 20%
                    if irrig_status == 'irrigated':
                        final_rate = final_rate * 1.2
                    # If non-irrigated, decrease by 20%
                    elif irrig_status == 'non_irrigated':
                        final_rate = final_rate * 0.8
                    
                    permutations.append({
                        'road_proximity': road_prox,
                        'irrigation_status': irrig_status,
                        'is_diverted': diverted,
                        'rate': final_rate
                    })
        
        return permutations

    @api.model
    def get_rate_summary_by_district(self, district_id):
        """Get rate summary for all villages in a district"""
        domain = [
            ('district_id', '=', district_id),
            ('state', '=', 'active'),
            ('effective_from', '<=', fields.Date.today()),
            '|',
            ('effective_to', '=', False),
            ('effective_to', '>=', fields.Date.today())
        ]
        
        return self.search(domain)


# Transient model for displaying rate permutations
class RateMasterPermutationWizard(models.TransientModel):
    _name = 'bhu.rate.master.permutation.wizard'
    _description = 'Rate Master Permutation Wizard'
    
    rate_master_id = fields.Many2one(
        'bhu.rate.master', string='Land Rate Master', required=True, readonly=True, ondelete='cascade',
    )
    permutation_line_ids = fields.One2many('bhu.rate.master.permutation.line', 'wizard_id', string='Permutations')


class RateMasterPermutationLine(models.TransientModel):
    _name = 'bhu.rate.master.permutation.line'
    _description = 'Rate Master Permutation Line'
    _order = 'road_proximity, irrigation_status, is_diverted'
    
    wizard_id = fields.Many2one('bhu.rate.master.permutation.wizard', string='Wizard', required=False, ondelete='cascade')
    survey_id = fields.Many2one('bhu.survey', string='Survey', required=False, ondelete='cascade')
    award_id = fields.Many2one('bhu.section23.award', string='Award', required=False, ondelete='cascade')
    road_proximity = fields.Selection([
        ('within_20m', 'Within Distance / दूरी के भीतर'),
        ('beyond_20m', 'Beyond Distance / दूरी से अधिक')
    ], string='Road Proximity / सड़क निकटता', required=True, readonly=True)
    irrigation_status = fields.Selection([
        ('irrigated', 'Irrigated / सिंचित'),
        ('non_irrigated', 'Non-Irrigated / असिंचित')
    ], string='Irrigation Status / सिंचाई स्थिति', required=True, readonly=True)
    is_diverted = fields.Boolean(string='Diverted / विचलित', readonly=True)
    calculated_rate = fields.Monetary(string='Calculated Rate / गणना दर', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.INR'))

