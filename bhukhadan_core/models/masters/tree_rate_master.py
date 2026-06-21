# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TreeMaster(models.Model):
    _name = 'bhu.tree.master'
    _description = 'Tree Rate Master / वृक्ष दर मास्टर'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Tree Name / वृक्ष का नाम', required=True, tracking=True,
                      help='Name of the tree species (e.g., Mango, Neem, Banyan)')
    
    # Tree Type
    tree_type = fields.Selection([
        ('fruit_bearing', 'Fruit-bearing / फलदार'),
        ('non_fruit_bearing', 'Non-fruit-bearing / गैर-फलदार')
    ], string='Tree Type / वृक्ष प्रकार', required=True, default='non_fruit_bearing', tracking=True,
       help='Type of tree. Both types use rate variants based on development stage and girth range.')
    
    district_id = fields.Many2one('bhu.district', string='District / जिला', tracking=True)
    active = fields.Boolean(string='Active / सक्रिय', default=True, tracking=True)
    fruit_rate = fields.Monetary(
        string='Fruit Flat Rate / फलदार एकल दर',
        currency_field='currency_id',
        tracking=True,
        help='Flat per-tree rate for fruit-bearing trees. No girth/development-stage dependency.',
    )
    tree_type_icon = fields.Char(
        string='Type Icon / प्रकार चिन्ह',
        compute='_compute_tree_list_helpers',
    )
    display_rate = fields.Monetary(
        string='Starting Rate / प्रारंभिक दर',
        currency_field='currency_id',
        compute='_compute_tree_list_helpers',
        help='Shows fruit flat rate for फलदार and first-slab rate for गैर-फलदार trees.',
    )
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.INR'))
    
    # One2many for tree rate variants (same structure for both fruit and non-fruit bearing)
    tree_rate_ids = fields.One2many('bhu.tree.rate.master', 'tree_master_id', 
                                    string='Rate Variants / दर वेरिएंट',
                                    help='Rate variants based on development stage and girth range for all tree types')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Tree name must be unique!')
    ]

    @api.depends(
        'tree_type',
        'fruit_rate',
        'tree_rate_ids.rate',
        'tree_rate_ids.girth_range_min',
        'tree_rate_ids.girth_range_max',
        'tree_rate_ids.development_stage',
        'tree_rate_ids.active',
    )
    def _compute_tree_list_helpers(self):
        for rec in self:
            rec.tree_type_icon = '🍎' if rec.tree_type == 'fruit_bearing' else '🌳'
            if rec.tree_type == 'fruit_bearing':
                rec.display_rate = rec.fruit_rate or 0.0
                continue

            non_fruit_lines = rec.tree_rate_ids.filtered(
                lambda l: l.active and l.development_stage == 'fully_developed'
            )
            if not non_fruit_lines:
                non_fruit_lines = rec.tree_rate_ids.filtered(lambda l: l.active)

            if non_fruit_lines:
                sorted_lines = non_fruit_lines.sorted(
                    key=lambda l: (l.girth_range_min or 0.0, l.girth_range_max or 999999.0)
                )
                rec.display_rate = sorted_lines[0].rate or 0.0
            else:
                rec.display_rate = 0.0

    def _get_tree_master_export_records(self):
        """Always export all active trees (user requested full master)."""
        return self.search([('active', '=', True)]).sorted(lambda r: (r.tree_type or '', r.name or ''))

    def action_download_rate_master_excel(self):
        """Export selected tree masters in annexure-style Excel."""
        import io
        import base64
        try:
            import xlsxwriter
        except ImportError:
            raise ValidationError(_("Python library 'xlsxwriter' is not installed."))

        export_records = self._get_tree_master_export_records()
        payload = export_records._get_rate_master_pdf_payload()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        font = 'Noto Sans Devanagari'

        title_fmt = workbook.add_format({
            'bold': True, 'font_name': font, 'font_size': 14,
            'align': 'center', 'valign': 'vcenter',
        })
        subtitle_fmt = workbook.add_format({
            'font_name': font, 'font_size': 10,
            'align': 'left', 'valign': 'vcenter',
        })
        head_fmt = workbook.add_format({
            'bold': True, 'font_name': font, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#E7EEF7',
        })
        cell_left_fmt = workbook.add_format({
            'font_name': font, 'font_size': 10,
            'align': 'left', 'valign': 'vcenter', 'border': 1,
        })
        cell_center_fmt = workbook.add_format({
            'font_name': font, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter', 'border': 1,
        })
        num_fmt = workbook.add_format({
            'font_name': font, 'font_size': 10,
            'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '#,##0',
        })
        sound_head_fmt = workbook.add_format({
            'bold': True, 'font_name': font, 'font_size': 9,
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#D9EAD3',
        })
        semi_head_fmt = workbook.add_format({
            'bold': True, 'font_name': font, 'font_size': 9,
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FFF2CC',
        })
        un_head_fmt = workbook.add_format({
            'bold': True, 'font_name': font, 'font_size': 9,
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#F4CCCC',
        })
        sound_cell_fmt = workbook.add_format({
            'font_name': font, 'font_size': 10,
            'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '#,##0', 'bg_color': '#F3FAF1',
        })
        semi_cell_fmt = workbook.add_format({
            'font_name': font, 'font_size': 10,
            'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '#,##0', 'bg_color': '#FFFBED',
        })
        un_cell_fmt = workbook.add_format({
            'font_name': font, 'font_size': 10,
            'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '#,##0', 'bg_color': '#FFF1F1',
        })

        # Sheet 1: Fruit
        ws_fruit = workbook.add_worksheet('Fruit Rates')
        ws_fruit.merge_range(0, 0, 0, 2, 'परिशिष्ट "ख" - फलदार प्रजाति के वृक्षों का मूल्य', title_fmt)
        ws_fruit.write(1, 0, f'Generated On: {payload.get("generated_on") or ""}', subtitle_fmt)
        ws_fruit.write(3, 0, 'क्रमांक', head_fmt)
        ws_fruit.write(3, 1, 'वृक्ष का नाम', head_fmt)
        ws_fruit.write(3, 2, 'मूल्य रुपये में', head_fmt)
        row = 4
        for item in payload.get('fruit_rows') or []:
            ws_fruit.write_number(row, 0, item.get('serial') or 0, cell_center_fmt)
            ws_fruit.write(row, 1, item.get('name') or '', cell_left_fmt)
            ws_fruit.write_number(row, 2, item.get('rate') or 0.0, num_fmt)
            row += 1
        if row == 4:
            ws_fruit.merge_range(4, 0, 4, 2, 'No fruit-bearing tree rates found.', cell_center_fmt)
        ws_fruit.set_column(0, 0, 10)
        ws_fruit.set_column(1, 1, 45)
        ws_fruit.set_column(2, 2, 18)

        # Sheet 2: Non-fruit matrix
        ws_non = workbook.add_worksheet('Non Fruit Rates')
        ws_non.merge_range(0, 0, 0, 4, 'परिशिष्ट "क" - इमारती एवं मिश्रित प्रजाति के खड़े वृक्षों का मूल्य', title_fmt)
        ws_non.write(1, 0, f'Generated On: {payload.get("generated_on") or ""}', subtitle_fmt)
        ws_non.write(3, 0, 'छाती (से.मी.)', head_fmt)

        col = 1
        for col_item in payload.get('non_teak_columns') or []:
            ws_non.merge_range(3, col, 3, col + 2, col_item.get('name') or '', head_fmt)
            ws_non.write(4, col, 'Sound', sound_head_fmt)
            ws_non.write(4, col + 1, 'Half Sound', semi_head_fmt)
            ws_non.write(4, col + 2, 'Un Sound', un_head_fmt)
            col += 3

        r = 5
        for slab in payload.get('non_teak_rows') or []:
            ws_non.write(r, 0, slab.get('label') or '', cell_center_fmt)
            c = 1
            for cell in slab.get('cells') or []:
                ws_non.write_number(r, c, cell.get('fully_developed') or 0.0, sound_cell_fmt)
                ws_non.write_number(r, c + 1, cell.get('semi_developed') or 0.0, semi_cell_fmt)
                ws_non.write_number(r, c + 2, cell.get('undeveloped') or 0.0, un_cell_fmt)
                c += 3
            r += 1
        if r == 5:
            ws_non.merge_range(5, 0, 5, 3, 'No non-fruit mixed species selected.', cell_center_fmt)

        ws_non.set_column(0, 0, 14)
        total_cols = max(1, len(payload.get('non_teak_columns') or []))
        ws_non.set_column(1, total_cols * 3, 12)

        # Teak block on same sheet (right side)
        teak_rows = payload.get('teak_rows') or []
        if teak_rows:
            base_col = max(6, (len(payload.get('non_teak_columns') or []) * 3) + 3)
            ws_non.merge_range(3, base_col, 3, base_col + 3, payload.get('teak_name') or 'Teak / सागौन', head_fmt)
            ws_non.write(4, base_col, 'छाती (से.मी.)', head_fmt)
            ws_non.write(4, base_col + 1, 'Sound', sound_head_fmt)
            ws_non.write(4, base_col + 2, 'Half Sound', semi_head_fmt)
            ws_non.write(4, base_col + 3, 'Un Sound', un_head_fmt)
            tr = 5
            for slab in teak_rows:
                first_cell = (slab.get('cells') or [{}])[0]
                ws_non.write(tr, base_col, slab.get('label') or '', cell_center_fmt)
                ws_non.write_number(tr, base_col + 1, first_cell.get('fully_developed') or 0.0, sound_cell_fmt)
                ws_non.write_number(tr, base_col + 2, first_cell.get('semi_developed') or 0.0, semi_cell_fmt)
                ws_non.write_number(tr, base_col + 3, first_cell.get('undeveloped') or 0.0, un_cell_fmt)
                tr += 1
            ws_non.set_column(base_col, base_col, 14)
            ws_non.set_column(base_col + 1, base_col + 3, 12)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()
        filename = 'Tree_Rate_Master.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self[:1].id if self else False,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    @api.model
    def action_regenerate_all_non_fruit_slabs(self):
        """Reset all active non-fruit rates from official chart matrix."""
        self.seed_non_fruit_chart_rates()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _get_rate_master_pdf_payload(self):
        """Return report-friendly payload for fruit/non-fruit annexure tables."""
        records = self.sorted(lambda r: (r.tree_type or '', r.name or ''))
        fruit_records = records.filtered(lambda r: r.tree_type == 'fruit_bearing')
        non_fruit_records = records.filtered(lambda r: r.tree_type == 'non_fruit_bearing')

        def _key(gmin, gmax):
            return round(gmin or 0.0, 2), round((gmax if gmax not in (False, None) else -1.0), 2)

        def _rate_lookup(tree):
            lookup = {}
            for line in tree.tree_rate_ids.filtered(lambda l: l.active):
                lookup[(line.development_stage,) + _key(line.girth_range_min, line.girth_range_max)] = line.rate or 0.0
            return lookup

        def _build_matrix_rows(trees, slabs):
            rows = []
            lookups = {tree.id: _rate_lookup(tree) for tree in trees}
            for label, gmin, gmax in slabs:
                cells = []
                for tree in trees:
                    base_key = _key(gmin, gmax)
                    data = lookups.get(tree.id, {})
                    cells.append({
                        'fully_developed': data.get(('fully_developed',) + base_key, 0.0),
                        'semi_developed': data.get(('semi_developed',) + base_key, 0.0),
                        'undeveloped': data.get(('undeveloped',) + base_key, 0.0),
                    })
                rows.append({'label': label, 'cells': cells})
            return rows

        teak_ref = self.env.ref('bhukhadan_core.tree_master_teak', raise_if_not_found=False)
        teak_record = teak_ref if teak_ref and teak_ref in non_fruit_records else self.env['bhu.tree.master']
        non_teak_records = non_fruit_records - teak_record
        # Keep the export column order aligned with official chart order.
        ordered_xmlids = [
            'bhukhadan_core.tree_master_sal',
            'bhukhadan_core.tree_master_bija',
            'bhukhadan_core.tree_master_sheesham',
            'bhukhadan_core.tree_master_tinsa',
            'bhukhadan_core.tree_master_saja',
            'bhukhadan_core.tree_master_dhawra',
            'bhukhadan_core.tree_master_khamhar',
            'bhukhadan_core.tree_master_other_mixed',
        ]
        ordered_records = self.env['bhu.tree.master']
        for xmlid in ordered_xmlids:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec and rec in non_teak_records:
                ordered_records |= rec
        # Append any additional custom non-fruit species at end.
        non_teak_records = ordered_records | (non_teak_records - ordered_records)

        non_teak_slabs = [
            ('46 से नीचे', 0.0, 45.99),
            ('46 - 60', 46.0, 60.0),
            ('61 - 90', 61.0, 90.0),
            ('91 - 120', 91.0, 120.0),
            ('121 - 150', 121.0, 150.0),
            ('151 - 180', 151.0, 180.0),
            ('180 से अधिक', 180.01, False),
        ]
        teak_slabs = [
            ('31 से नीचे', 0.0, 30.99),
            ('31 - 40', 31.0, 40.0),
            ('41 - 50', 41.0, 50.0),
            ('51 - 60', 51.0, 60.0),
            ('61 - 75', 61.0, 75.0),
            ('76 - 90', 76.0, 90.0),
            ('91 - 105', 91.0, 105.0),
            ('106 - 120', 106.0, 120.0),
            ('120 से अधिक', 120.01, False),
        ]

        return {
            'generated_on': fields.Date.context_today(self),
            'fruit_rows': [
                {
                    'serial': idx + 1,
                    'name': rec.name or '',
                    'rate': rec.fruit_rate or 0.0,
                }
                for idx, rec in enumerate(fruit_records)
            ],
            'non_teak_columns': [{'id': rec.id, 'name': rec.name or ''} for rec in non_teak_records],
            'non_teak_rows': _build_matrix_rows(non_teak_records, non_teak_slabs),
            'teak_name': teak_record.name if teak_record else '',
            'teak_rows': _build_matrix_rows(teak_record, teak_slabs) if teak_record else [],
        }

    def unlink(self):
        """Prevent hard-delete because historical simulator/award lines reference trees.

        To avoid FK crashes in UI, convert delete into archive (active=False).
        """
        self.write({'active': False})
        return True

    def _get_non_fruit_slabs(self):
        """Return girth slabs for non-fruit trees."""
        self.ensure_one()
        # Teak (सागौन) has separate girth bands in the board chart.
        if self.env.ref('bhukhadan_core.tree_master_teak', raise_if_not_found=False) == self:
            return [
                (0.0, 30.99), (31.0, 40.0), (41.0, 50.0), (51.0, 60.0), (61.0, 75.0),
                (76.0, 90.0), (91.0, 105.0), (106.0, 120.0), (120.01, False),
            ]
        return [
            (0.0, 45.99), (46.0, 60.0), (61.0, 90.0), (91.0, 120.0),
            (121.0, 150.0), (151.0, 180.0), (180.01, False),
        ]

    def _get_non_fruit_chart_rows(self):
        """Return chart row matrix (Sound, Half Sound, Un Sound) for this tree."""
        self.ensure_one()
        chart_by_xmlid = {
            'bhukhadan_core.tree_master_sal': [
                (264, 169, 104), (726, 556, 254), (3571, 2710, 1178), (9986, 7280, 2539),
                (18702, 9460, 4199), (29876, 15946, 6010), (36680, 20922, 8955),
            ],
            'bhukhadan_core.tree_master_bija': [
                (89, 76, 70), (811, 468, 301), (4383, 2597, 1355), (11812, 6227, 3436),
                (23572, 12412, 6835), (32717, 17088, 9275), (39591, 20607, 11114),
            ],
            'bhukhadan_core.tree_master_sheesham': [
                (119, 97, 84), (265, 188, 158), (1975, 1268, 763), (6131, 3405, 2040),
                (12413, 6868, 4085), (25060, 13325, 7457), (32247, 17009, 9390),
            ],
            'bhukhadan_core.tree_master_tinsa': [
                (93, 89, 83), (314, 270, 248), (1073, 770, 541), (2887, 1780, 1223),
                (5469, 3397, 2349), (9598, 5497, 3592), (13696, 7732, 4751),
            ],
            'bhukhadan_core.tree_master_saja': [
                (131, 101, 89), (474, 301, 213), (1912, 1093, 683), (4682, 2614, 1581),
                (8488, 4750, 2878), (12638, 6063, 4254), (19014, 10440, 6472),
            ],
            'bhukhadan_core.tree_master_dhawra': [
                (112, 85, 78), (298, 216, 172), (910, 596, 362), (2287, 1790, 984),
                (4997, 3001, 2006), (6740, 4582, 3020), (11615, 6548, 4469),
            ],
            'bhukhadan_core.tree_master_khamhar': [
                (134, 101, 85), (469, 340, 262), (2792, 2214, 1198), (10976, 5812, 3277),
                (22818, 13012, 6636), (31400, 16429, 8944), (38003, 31412, 10722),
            ],
            'bhukhadan_core.tree_master_other_mixed': [
                (89, 78, 78), (230, 177, 134), (960, 617, 447), (2310, 1430, 999),
                (4585, 2449, 1715), (6130, 3794, 2626), (9249, 5501, 3827),
            ],
        }
        teak_rows = [
            (156, 101, 74), (177, 127, 100), (1562, 858, 510), (3166, 2087, 1160),
            (5564, 2952, 1674), (9296, 4852, 2634), (16993, 8642, 4717),
            (24221, 13255, 6704), (53274, 27553, 14609),
        ]

        teak_master = self.env.ref('bhukhadan_core.tree_master_teak', raise_if_not_found=False)
        if teak_master and self == teak_master:
            return teak_rows

        for xmlid, rows in chart_by_xmlid.items():
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec and self == rec:
                return rows

        # Safe fallback for custom non-fruit trees: use 'other mixed' pattern
        return chart_by_xmlid['bhukhadan_core.tree_master_other_mixed']

    def _non_fruit_rate_line_commands(self):
        """Build one2many commands for full non-fruit slab matrix."""
        self.ensure_one()
        if self.tree_type != 'non_fruit_bearing':
            return []
        slabs = self._get_non_fruit_slabs()
        chart_rows = self._get_non_fruit_chart_rows()
        cmds = []
        for idx, (gmin, gmax) in enumerate(slabs):
            row = chart_rows[idx] if chart_rows and idx < len(chart_rows) else (0.0, 0.0, 0.0)
            for stage, pos in (('fully_developed', 0), ('semi_developed', 1), ('undeveloped', 2)):
                cmds.append((0, 0, {
                    'development_stage': stage,
                    'girth_range_min': gmin,
                    'girth_range_max': gmax if gmax else False,
                    'rate': float(row[pos] or 0.0),
                    'active': True,
                }))
        return cmds

    @api.onchange('tree_type')
    def _onchange_tree_type_fill_non_fruit_rates(self):
        """When user selects non-fruit, prefill slab grid in form immediately."""
        for rec in self:
            if rec.tree_type == 'non_fruit_bearing' and not rec.tree_rate_ids:
                rec.tree_rate_ids = [(5, 0, 0)] + rec._non_fruit_rate_line_commands()

    def _clear_generic_zero_rows(self):
        """Delete invalid generic rows (0/0 or 0/empty) for non-fruit trees."""
        self.ensure_one()
        if self.tree_type != 'non_fruit_bearing':
            return self.env['bhu.tree.rate.master']
        rate_model = self.env['bhu.tree.rate.master']
        bad = rate_model.search([
            ('tree_master_id', '=', self.id),
            ('girth_range_min', '=', 0.0),
            '|',
            ('girth_range_max', '=', 0.0),
            ('girth_range_max', '=', False),
        ])
        if bad:
            bad.unlink()
        return bad

    def action_apply_non_fruit_girth_ranges(self):
        """Expand non-fruit tree rates into full girth slabs.

        If existing data has only 3 generic 0-range rows, this converts them
        into full slab rows using the same stage-wise rate values.
        """
        rate_model = self.env['bhu.tree.rate.master']
        for rec in self:
            if rec.tree_type != 'non_fruit_bearing':
                continue

            rec._clear_generic_zero_rows()
            slabs = rec._get_non_fruit_slabs()
            chart_rows = rec._get_non_fruit_chart_rows()

            for idx, (gmin, gmax) in enumerate(slabs):
                for stage in ('fully_developed', 'semi_developed', 'undeveloped'):
                    pos = 0 if stage == 'fully_developed' else (1 if stage == 'semi_developed' else 2)
                    default_rate = chart_rows[idx][pos] if chart_rows and idx < len(chart_rows) else 0.0
                    domain = [
                        ('tree_master_id', '=', rec.id),
                        ('development_stage', '=', stage),
                        ('girth_range_min', '=', gmin),
                        ('girth_range_max', '=', gmax if gmax else False),
                    ]
                    row = rate_model.search(domain, limit=1)
                    # Keep explicit per-slab row value if it exists, else use chart default.
                    use_rate = (row.rate or 0.0) if row else default_rate
                    vals = {
                        'tree_master_id': rec.id,
                        'development_stage': stage,
                        'girth_range_min': gmin,
                        'girth_range_max': gmax if gmax else False,
                        'rate': use_rate,
                        'active': True,
                    }
                    if row:
                        row.write(vals)
                    else:
                        rate_model.create(vals)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.tree_type == 'non_fruit_bearing' and not rec.tree_rate_ids:
                rec.action_apply_non_fruit_girth_ranges()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.tree_type == 'non_fruit_bearing' and not rec.tree_rate_ids:
                rec.action_apply_non_fruit_girth_ranges()
        return res

    @api.model
    def seed_non_fruit_chart_rates(self):
        """Seed non-fruit tree rates (girth + sound class) from chart."""
        # Generic non-teak girth slabs from chart
        non_teak_slabs = [
            ('below46', 0.0, 45.99),
            ('46_60', 46.0, 60.0),
            ('61_90', 61.0, 90.0),
            ('91_120', 91.0, 120.0),
            ('121_150', 121.0, 150.0),
            ('151_180', 151.0, 180.0),
            ('above180', 180.01, False),
        ]
        # Teak has separate girth chart
        teak_slabs = [
            ('below31', 0.0, 30.99),
            ('31_40', 31.0, 40.0),
            ('41_50', 41.0, 50.0),
            ('51_60', 51.0, 60.0),
            ('61_75', 61.0, 75.0),
            ('76_90', 76.0, 90.0),
            ('91_105', 91.0, 105.0),
            ('106_120', 106.0, 120.0),
            ('above120', 120.01, False),
        ]

        # Per row: (Sound, Half Sound, Un Sound)
        rate_matrix = {
            'bhukhadan_core.tree_master_sal': [
                # साल (Sal): Sound / Half Sound / Un Sound
                (264, 169, 104), (726, 556, 254), (3571, 2710, 1178), (9986, 7280, 2539),
                (18702, 9460, 4199), (29876, 15946, 6010), (36680, 20922, 8955),
            ],
            'bhukhadan_core.tree_master_bija': [
                (89, 76, 70), (811, 468, 301), (4383, 2597, 1355), (11812, 6227, 3436),
                (23572, 12412, 6835), (32717, 17088, 9275), (39591, 20607, 11114),
            ],
            'bhukhadan_core.tree_master_sheesham': [
                (119, 97, 84), (265, 188, 158), (1975, 1268, 763), (6131, 3405, 2040),
                (12413, 6868, 4085), (25060, 13325, 7457), (32247, 17009, 9390),
            ],
            'bhukhadan_core.tree_master_tinsa': [
                (93, 89, 83), (314, 270, 248), (1073, 770, 541), (2887, 1780, 1223),
                (5469, 3397, 2349), (9598, 5497, 3592), (13696, 7732, 4751),
            ],
            'bhukhadan_core.tree_master_saja': [
                (131, 101, 89), (474, 301, 213), (1912, 1093, 683), (4682, 2614, 1581),
                (8488, 4750, 2878), (12638, 6063, 4254), (19014, 10440, 6472),
            ],
            'bhukhadan_core.tree_master_dhawra': [
                (112, 85, 78), (298, 216, 172), (910, 596, 362), (2287, 1790, 984),
                (4997, 3001, 2006), (6740, 4582, 3020), (11615, 6548, 4469),
            ],
            'bhukhadan_core.tree_master_khamhar': [
                (134, 101, 85), (469, 340, 262), (2792, 2214, 1198), (10976, 5812, 3277),
                (22818, 13012, 6636), (31400, 16429, 8944), (38003, 31412, 10722),
            ],
            'bhukhadan_core.tree_master_other_mixed': [
                (89, 78, 78), (230, 177, 134), (960, 617, 447), (2310, 1430, 999),
                (4585, 2449, 1715), (6130, 3794, 2626), (9249, 5501, 3827),
            ],
        }

        # Teak rates: (Sound, Half Sound, Un Sound)
        teak_rates = [
            (156, 101, 74), (177, 127, 100), (1562, 858, 510), (3166, 2087, 1160),
            (5564, 2952, 1674), (9296, 4852, 2634), (16993, 8642, 4717),
            (24221, 13255, 6704), (53274, 27553, 14609),
        ]

        rate_model = self.env['bhu.tree.rate.master']
        stage_map = (
            ('fully_developed', 0),   # Sound
            ('semi_developed', 1),    # Half Sound
            ('undeveloped', 2),       # Un Sound
        )

        def _upsert_rate(tree_master, stage, gmin, gmax, rate_val):
            domain = [
                ('tree_master_id', '=', tree_master.id),
                ('development_stage', '=', stage),
                ('girth_range_min', '=', gmin),
                ('girth_range_max', '=', gmax if gmax else False),
            ]
            rec = rate_model.search(domain, limit=1)
            vals = {
                'tree_master_id': tree_master.id,
                'development_stage': stage,
                'girth_range_min': gmin,
                'girth_range_max': gmax if gmax else False,
                'rate': float(rate_val),
                'active': True,
            }
            if rec:
                rec.write(vals)
            else:
                rate_model.create(vals)

        # Non-teak species
        for xmlid, rows in rate_matrix.items():
            tree_master = self.env.ref(xmlid, raise_if_not_found=False)
            if not tree_master:
                continue
            tree_master._clear_generic_zero_rows()
            for idx, (_slug, gmin, gmax) in enumerate(non_teak_slabs):
                row = rows[idx]
                for stage, pos in stage_map:
                    _upsert_rate(tree_master, stage, gmin, gmax, row[pos])

        # Teak
        teak_master = self.env.ref('bhukhadan_core.tree_master_teak', raise_if_not_found=False)
        if teak_master:
            teak_master._clear_generic_zero_rows()
            for idx, (_slug, gmin, gmax) in enumerate(teak_slabs):
                row = teak_rates[idx]
                for stage, pos in stage_map:
                    _upsert_rate(teak_master, stage, gmin, gmax, row[pos])

class TreeRateMaster(models.Model):
    _name = 'bhu.tree.rate.master'
    _description = 'Tree Rate Master - Rate Variants'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'tree_master_id, development_stage, girth_range_min'

    tree_master_id = fields.Many2one('bhu.tree.master', string='Tree / वृक्ष', required=True, ondelete='cascade', tracking=True)
    development_stage = fields.Selection([
        ('undeveloped', 'Undeveloped / अविकसित'),
        ('semi_developed', 'Semi-developed / अर्ध-विकसित'),
        ('fully_developed', 'Fully Developed / पूर्ण विकसित')
    ], string='Development Stage / विकास स्तर', required=True, tracking=True)
    stage_icon = fields.Char(
        string='Stage Icon',
        compute='_compute_stage_icon',
        help='Visual indicator for Sound / Semi Sound / Un Sound stages.',
    )
    
    girth_range_min = fields.Float(string='Min Girth (cm) / न्यूनतम छाती (से.मी.)', required=True, tracking=True,
                                   help='Minimum girth in centimeters')
    girth_range_max = fields.Float(string='Max Girth (cm) / अधिकतम छाती (से.मी.)', tracking=True,
                                   help='Maximum girth in centimeters. Leave empty for "Above X cm"')
    
    rate = fields.Monetary(string='Rate / दर', currency_field='currency_id', required=True, tracking=True,
                          help='Compensation rate for this tree variant')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.INR'))
    
    active = fields.Boolean(string='Active / सक्रिय', default=True, tracking=True)
    description = fields.Text(string='Description / विवरण', tracking=True,
                              help='Additional description or notes for this rate variant')

    _sql_constraints = [
        ('unique_tree_rate', 'unique(tree_master_id, development_stage, girth_range_min, girth_range_max)',
         'A rate variant with the same tree, development stage, and girth range already exists!')
    ]

    @api.depends('development_stage')
    def _compute_stage_icon(self):
        icon_map = {
            'fully_developed': '🟢 Sound',
            'semi_developed': '🟡 Semi Sound',
            'undeveloped': '🔴 Un Sound',
        }
        for rec in self:
            rec.stage_icon = icon_map.get(rec.development_stage, '')
