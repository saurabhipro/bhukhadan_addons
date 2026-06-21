# -*- coding: utf-8 -*-
"""Payment Dashboard - read-only SQL views for Collector / Admin drill-down.

Two database views are exposed:

- ``bhu.payment.project.summary``  → consolidated per-project KPIs.
- ``bhu.payment.village.summary``  → per-project + per-village KPIs.

Both views aggregate from ``bhu.payment.reconciliation.bank.line`` joined with
``bhu.payment.reconciliation.bank`` so they stay in sync with bank reconciliation
activity, i.e. each settled / failed / pending bank transaction.
"""

from odoo import api, fields, models, tools


class PaymentProjectSummary(models.Model):
    _name = 'bhu.payment.project.summary'
    _description = 'Payment Dashboard - Project Summary'
    _auto = False
    _order = 'failed_count desc, project_name'

    project_id = fields.Many2one('bhu.project', string='Project', readonly=True)
    project_name = fields.Char(string='Project Name', readonly=True)
    total_count = fields.Integer(string='Total Payments', readonly=True)
    success_count = fields.Integer(string='Successful', readonly=True)
    failed_count = fields.Integer(string='Failed', readonly=True)
    pending_count = fields.Integer(string='Pending', readonly=True)
    total_amount = fields.Float(string='Total Amount', readonly=True)
    success_amount = fields.Float(string='Successful Amount', readonly=True)
    failed_amount = fields.Float(string='Failed Amount', readonly=True)
    pending_amount = fields.Float(string='Pending Amount', readonly=True)
    success_rate = fields.Float(string='Success Rate %', readonly=True, digits=(6, 2))

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    recon.project_id AS id,
                    recon.project_id AS project_id,
                    proj.name AS project_name,
                    COUNT(line.id) AS total_count,
                    COUNT(line.id) FILTER (WHERE line.status = 'settled') AS success_count,
                    COUNT(line.id) FILTER (WHERE line.status = 'failed') AS failed_count,
                    COUNT(line.id) FILTER (WHERE line.status = 'pending') AS pending_count,
                    COALESCE(SUM(line.credit_amount), 0) AS total_amount,
                    COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'settled'), 0) AS success_amount,
                    COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'failed'), 0) AS failed_amount,
                    COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'pending'), 0) AS pending_amount,
                    CASE
                        WHEN COUNT(line.id) > 0
                        THEN (COUNT(line.id) FILTER (WHERE line.status = 'settled'))::float
                             / COUNT(line.id) * 100.0
                        ELSE 0
                    END AS success_rate
                FROM bhu_payment_reconciliation_bank_line line
                JOIN bhu_payment_reconciliation_bank recon ON recon.id = line.reconciliation_id
                LEFT JOIN bhu_project proj ON proj.id = recon.project_id
                WHERE recon.project_id IS NOT NULL
                GROUP BY recon.project_id, proj.name
            )
            """ % self._table
        )

    def action_open_villages(self):
        """Drill-down: open village-wise summary for this project."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Village Payment Summary - %s' % (self.project_name or ''),
            'res_model': 'bhu.payment.village.summary',
            'view_mode': 'kanban,list',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'default_project_id': self.project_id.id},
            'target': 'current',
        }


class PaymentVillageSummary(models.Model):
    _name = 'bhu.payment.village.summary'
    _description = 'Payment Dashboard - Village Summary'
    _auto = False
    _order = 'failed_count desc, village_name'

    project_id = fields.Many2one('bhu.project', string='Project', readonly=True)
    project_name = fields.Char(string='Project Name', readonly=True)
    village_id = fields.Many2one('bhu.village', string='Village', readonly=True)
    village_name = fields.Char(string='Village Name', readonly=True)
    total_count = fields.Integer(string='Total Payments', readonly=True)
    success_count = fields.Integer(string='Successful', readonly=True)
    failed_count = fields.Integer(string='Failed', readonly=True)
    pending_count = fields.Integer(string='Pending', readonly=True)
    total_amount = fields.Float(string='Total Amount', readonly=True)
    success_amount = fields.Float(string='Successful Amount', readonly=True)
    failed_amount = fields.Float(string='Failed Amount', readonly=True)
    pending_amount = fields.Float(string='Pending Amount', readonly=True)
    success_rate = fields.Float(string='Success Rate %', readonly=True, digits=(6, 2))

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    (recon.project_id * 1000000 + recon.village_id) AS id,
                    recon.project_id AS project_id,
                    proj.name AS project_name,
                    recon.village_id AS village_id,
                    vill.name AS village_name,
                    COUNT(line.id) AS total_count,
                    COUNT(line.id) FILTER (WHERE line.status = 'settled') AS success_count,
                    COUNT(line.id) FILTER (WHERE line.status = 'failed') AS failed_count,
                    COUNT(line.id) FILTER (WHERE line.status = 'pending') AS pending_count,
                    COALESCE(SUM(line.credit_amount), 0) AS total_amount,
                    COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'settled'), 0) AS success_amount,
                    COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'failed'), 0) AS failed_amount,
                    COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'pending'), 0) AS pending_amount,
                    CASE
                        WHEN COUNT(line.id) > 0
                        THEN (COUNT(line.id) FILTER (WHERE line.status = 'settled'))::float
                             / COUNT(line.id) * 100.0
                        ELSE 0
                    END AS success_rate
                FROM bhu_payment_reconciliation_bank_line line
                JOIN bhu_payment_reconciliation_bank recon ON recon.id = line.reconciliation_id
                LEFT JOIN bhu_project proj ON proj.id = recon.project_id
                LEFT JOIN bhu_village vill ON vill.id = recon.village_id
                WHERE recon.project_id IS NOT NULL AND recon.village_id IS NOT NULL
                GROUP BY recon.project_id, proj.name, recon.village_id, vill.name
            )
            """ % self._table
        )

    def action_open_failed_lines(self):
        """Drill-down: open failed payment lines for this village + project."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Failed Payments - %s / %s' % (self.project_name or '', self.village_name or ''),
            'res_model': 'bhu.payment.reconciliation.bank.line',
            'view_mode': 'list,form',
            'domain': [
                ('status', '=', 'failed'),
                ('reconciliation_id.project_id', '=', self.project_id.id),
                ('reconciliation_id.village_id', '=', self.village_id.id),
            ],
            'target': 'current',
        }


class PaymentDashboard(models.TransientModel):
    """Top banner record used by the Payment Dashboard view.

    Holds org-wide consolidated KPIs so we can render nice header cards
    alongside the per-project kanban.
    """
    _name = 'bhu.payment.dashboard'
    _description = 'Payment Dashboard (Consolidated)'

    total_count = fields.Integer(string='Total Payments', readonly=True)
    success_count = fields.Integer(string='Successful', readonly=True)
    failed_count = fields.Integer(string='Failed', readonly=True)
    pending_count = fields.Integer(string='Pending', readonly=True)
    total_amount = fields.Float(string='Total Amount', readonly=True)
    success_amount = fields.Float(string='Successful Amount', readonly=True)
    failed_amount = fields.Float(string='Failed Amount', readonly=True)
    pending_amount = fields.Float(string='Pending Amount', readonly=True)
    success_rate = fields.Float(string='Success Rate %', readonly=True, digits=(6, 2))
    project_count = fields.Integer(string='Projects Tracked', readonly=True)
    village_count = fields.Integer(string='Villages Tracked', readonly=True)

    @api.model
    def _payment_dashboard_project_ids(self):
        """Return project ids to scope payment dashboard; ``None`` means all projects."""
        user = self.env.user
        if (
            user.has_group('base.group_system')
            or user.has_group('bhukhadan_core.group_bhuarjan_admin')
            or user.has_group('bhukhadan_core.group_bhuarjan_collector')
            or user.has_group('bhukhadan_core.group_bhuarjan_additional_collector')
            or user.has_group('bhukhadan_core.group_bhuarjan_district_administrator')
        ):
            return None
        if user.has_group('bhukhadan_core.group_bhuarjan_sdm') or user.has_group('bhukhadan_core.group_bhuarjan_tahsildar'):
            return self.env['bhuarjan.dashboard.stats']._get_sdm_project_ids(user)
        return []

    @api.model
    def _compute_consolidated(self, project_ids=None):
        project_filter_sql = ''
        params = []
        if project_ids is not None:
            if not project_ids:
                return {
                    'total_count': 0,
                    'success_count': 0,
                    'failed_count': 0,
                    'pending_count': 0,
                    'total_amount': 0.0,
                    'success_amount': 0.0,
                    'failed_amount': 0.0,
                    'pending_amount': 0.0,
                    'project_count': 0,
                    'village_count': 0,
                    'success_rate': 0.0,
                }
            project_filter_sql = ' AND recon.project_id = ANY(%s)'
            params.append(project_ids)

        self.env.cr.execute(
            """
            SELECT
                COUNT(line.id) AS total_count,
                COUNT(line.id) FILTER (WHERE line.status = 'settled') AS success_count,
                COUNT(line.id) FILTER (WHERE line.status = 'failed') AS failed_count,
                COUNT(line.id) FILTER (WHERE line.status = 'pending') AS pending_count,
                COALESCE(SUM(line.credit_amount), 0) AS total_amount,
                COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'settled'), 0) AS success_amount,
                COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'failed'), 0) AS failed_amount,
                COALESCE(SUM(line.credit_amount) FILTER (WHERE line.status = 'pending'), 0) AS pending_amount,
                COUNT(DISTINCT recon.project_id) AS project_count,
                COUNT(DISTINCT recon.village_id) AS village_count
            FROM bhu_payment_reconciliation_bank_line line
            JOIN bhu_payment_reconciliation_bank recon ON recon.id = line.reconciliation_id
            WHERE 1=1
            """ + project_filter_sql,
            params,
        )
        row = self.env.cr.dictfetchone() or {}
        total = row.get('total_count') or 0
        success = row.get('success_count') or 0
        row['success_rate'] = (success / total * 100.0) if total else 0.0
        return row

    @api.model
    def action_open_dashboard(self):
        scoped_ids = self._payment_dashboard_project_ids()
        vals = self._compute_consolidated(scoped_ids)
        record = self.create(vals)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment Dashboard',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': record.id,
            'target': 'current',
        }

    def action_open_all_projects(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project Payment Summary',
            'res_model': 'bhu.payment.project.summary',
            'view_mode': 'kanban,list',
            'target': 'current',
        }

    def action_open_all_failed(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'All Failed Payments',
            'res_model': 'bhu.payment.reconciliation.bank.line',
            'view_mode': 'list,form',
            'domain': [('status', '=', 'failed')],
            'target': 'current',
        }

    def action_refresh(self):
        self.ensure_one()
        scoped_ids = self._payment_dashboard_project_ids()
        vals = self._compute_consolidated(scoped_ids)
        self.write(vals)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    # ------------------------------------------------------------------
    # OWL Dashboard RPC
    # ------------------------------------------------------------------

    @api.model
    def get_payment_dashboard_data(self):
        """One-shot RPC that returns every KPI + table needed by the OWL
        payment dashboard component.

        Returns
        -------
        dict
            {
                'stats': { total/success/failed/pending counts + amounts + rate,
                            project_count, village_count },
                'projects': [ { id, name, total, success, failed, pending,
                                 total_amount, success_amount, failed_amount,
                                 pending_amount, success_rate } ],
                'villages': [ { project_id, project_name, village_id,
                                 village_name, ...counts + amounts } ],
                'recent_failures': [ { id, utr_number, beneficiary_name,
                                        credit_amount, error, project_name,
                                        village_name, reconciliation_id } ],
            }
        """
        scoped_project_ids = self._payment_dashboard_project_ids()
        stats = self._compute_consolidated(scoped_project_ids)
        stats['success_rate'] = round(stats.get('success_rate') or 0.0, 2)

        summary_domain = []
        if scoped_project_ids is not None:
            summary_domain = [('project_id', 'in', scoped_project_ids or [0])]

        payment_projects = self.env['bhu.payment.project.summary'].search_read(
            summary_domain, [
                'project_id', 'project_name',
                'total_count', 'success_count', 'failed_count', 'pending_count',
                'total_amount', 'success_amount', 'failed_amount', 'pending_amount',
                'success_rate',
            ], order='failed_count desc, project_name',
        )
        payment_by_project = {}
        for p in payment_projects:
            p['project_id'] = p['project_id'][0] if p.get('project_id') else False
            p['success_rate'] = round(p.get('success_rate') or 0.0, 2)
            if p['project_id']:
                payment_by_project[p['project_id']] = p

        villages = self.env['bhu.payment.village.summary'].search_read(
            summary_domain, [
                'project_id', 'project_name', 'village_id', 'village_name',
                'total_count', 'success_count', 'failed_count', 'pending_count',
                'total_amount', 'success_amount', 'failed_amount', 'pending_amount',
                'success_rate',
            ], order='project_name, failed_count desc, village_name',
        )
        for v in villages:
            v['project_id'] = v['project_id'][0] if v.get('project_id') else False
            v['village_id'] = v['village_id'][0] if v.get('village_id') else False
            v['success_rate'] = round(v.get('success_rate') or 0.0, 2)

        # ------------------------------------------------------------------
        # Pending fallback from payment files
        # ------------------------------------------------------------------
        # Dashboard base views aggregate only reconciliation lines. When a
        # payment file is created for a village but bank reconciliation has not
        # started yet, show those transactions as "pending".
        recon_village_keys = {
            (v.get('project_id'), v.get('village_id'))
            for v in villages
            if v.get('project_id') and v.get('village_id')
        }
        file_pending_by_village = {}
        file_pending_by_project = {}

        file_domain = [
            ('state', 'in', ['draft', 'generated']),
            ('project_id', '!=', False),
            ('village_id', '!=', False),
        ]
        if scoped_project_ids is not None:
            file_domain.append(('project_id', 'in', scoped_project_ids or [0]))

        payment_files = self.env['bhu.payment.file'].search_read(
            file_domain,
            ['project_id', 'village_id', 'payment_line_ids', 'total_net_payable', 'total_compensation'],
            order='id desc',
        )

        for pf in payment_files:
            project = pf.get('project_id') or []
            village = pf.get('village_id') or []
            project_id = project[0] if project else False
            village_id = village[0] if village else False
            if not project_id or not village_id:
                continue

            key = (project_id, village_id)
            if key in recon_village_keys:
                # Reconciliation already exists for this project-village, so
                # avoid double counting payment file lines.
                continue

            pending_count = len(pf.get('payment_line_ids') or [])
            pending_amount = float(pf.get('total_net_payable') or pf.get('total_compensation') or 0.0)
            if pending_count <= 0 and pending_amount <= 0:
                continue

            if key not in file_pending_by_village:
                file_pending_by_village[key] = {
                    'project_id': project_id,
                    'project_name': project[1] if len(project) > 1 else '',
                    'village_id': village_id,
                    'village_name': village[1] if len(village) > 1 else '',
                    'total_count': 0,
                    'success_count': 0,
                    'failed_count': 0,
                    'pending_count': 0,
                    'total_amount': 0.0,
                    'success_amount': 0.0,
                    'failed_amount': 0.0,
                    'pending_amount': 0.0,
                    'success_rate': 0.0,
                }
            row = file_pending_by_village[key]
            row['total_count'] += pending_count
            row['pending_count'] += pending_count
            row['total_amount'] += pending_amount
            row['pending_amount'] += pending_amount

            project_bucket = file_pending_by_project.setdefault(
                project_id, {'count': 0, 'amount': 0.0}
            )
            project_bucket['count'] += pending_count
            project_bucket['amount'] += pending_amount

        if file_pending_by_village:
            villages.extend(file_pending_by_village.values())
            villages.sort(
                key=lambda row: (
                    (row.get('project_name') or '').lower(),
                    -int(row.get('failed_count') or 0),
                    (row.get('village_name') or '').lower(),
                )
            )

        # Merge payment-file fallback into project aggregates and top KPIs.
        extra_total_count = 0
        extra_pending_count = 0
        extra_total_amount = 0.0
        extra_pending_amount = 0.0
        for project_id, extra in file_pending_by_project.items():
            base = payment_by_project.get(project_id)
            if not base:
                base = {
                    'project_id': project_id,
                    'project_name': '',
                    'total_count': 0,
                    'success_count': 0,
                    'failed_count': 0,
                    'pending_count': 0,
                    'total_amount': 0.0,
                    'success_amount': 0.0,
                    'failed_amount': 0.0,
                    'pending_amount': 0.0,
                    'success_rate': 0.0,
                }
                payment_by_project[project_id] = base

            base['total_count'] = int(base.get('total_count') or 0) + int(extra['count'] or 0)
            base['pending_count'] = int(base.get('pending_count') or 0) + int(extra['count'] or 0)
            base['total_amount'] = float(base.get('total_amount') or 0.0) + float(extra['amount'] or 0.0)
            base['pending_amount'] = float(base.get('pending_amount') or 0.0) + float(extra['amount'] or 0.0)
            success = float(base.get('success_count') or 0.0)
            total = float(base.get('total_count') or 0.0)
            base['success_rate'] = round((success / total * 100.0) if total else 0.0, 2)

            extra_total_count += int(extra['count'] or 0)
            extra_pending_count += int(extra['count'] or 0)
            extra_total_amount += float(extra['amount'] or 0.0)
            extra_pending_amount += float(extra['amount'] or 0.0)

        if extra_total_count or extra_total_amount:
            stats['total_count'] = int(stats.get('total_count') or 0) + extra_total_count
            stats['pending_count'] = int(stats.get('pending_count') or 0) + extra_pending_count
            stats['total_amount'] = float(stats.get('total_amount') or 0.0) + extra_total_amount
            stats['pending_amount'] = float(stats.get('pending_amount') or 0.0) + extra_pending_amount
            success = float(stats.get('success_count') or 0.0)
            total = float(stats.get('total_count') or 0.0)
            stats['success_rate'] = round((success / total * 100.0) if total else 0.0, 2)

        # Include every project in the dashboard, even if it has zero payment
        # reconciliation records so the collector gets one complete view.
        project_domain = []
        if scoped_project_ids is not None:
            project_domain = [('id', 'in', scoped_project_ids or [0])]

        all_projects = self.env['bhu.project'].search_read(
            project_domain,
            ['name', 'code', 'state', 'department_id', 'district_id', 'village_ids', 'total_cost', 'create_date'],
            order='create_date desc, name',
        )
        unique_village_ids = set()
        for project in all_projects:
            unique_village_ids.update(project.get('village_ids') or [])
        stats['project_count'] = len(all_projects)
        stats['village_count'] = len(unique_village_ids)

        projects = []
        for project in all_projects:
            project_id = project['id']
            payment = payment_by_project.get(project_id, {})

            total_count = int(payment.get('total_count') or 0)
            success_count = int(payment.get('success_count') or 0)
            failed_count = int(payment.get('failed_count') or 0)
            pending_count = int(payment.get('pending_count') or 0)
            success_rate = round(payment.get('success_rate') or 0.0, 2)

            if total_count == 0:
                payment_status = 'No Payment'
                payment_status_key = 'none'
            elif failed_count > 0:
                payment_status = 'Needs Attention'
                payment_status_key = 'danger'
            elif pending_count > 0:
                payment_status = 'In Progress'
                payment_status_key = 'warning'
            else:
                payment_status = 'Healthy'
                payment_status_key = 'success'

            projects.append({
                'id': project_id,
                'project_id': project_id,
                'project_name': project.get('name') or '',
                'project_code': project.get('code') or '',
                'project_state': project.get('state') or '',
                'department_name': (
                    project.get('department_id')[1]
                    if project.get('department_id') and len(project.get('department_id')) > 1
                    else ''
                ),
                'district_name': (
                    project.get('district_id')[1]
                    if project.get('district_id') and len(project.get('district_id')) > 1
                    else ''
                ),
                'village_count': len(project.get('village_ids') or []),
                'total_cost': project.get('total_cost') or '',
                'total_count': total_count,
                'success_count': success_count,
                'failed_count': failed_count,
                'pending_count': pending_count,
                'total_amount': float(payment.get('total_amount') or 0.0),
                'success_amount': float(payment.get('success_amount') or 0.0),
                'failed_amount': float(payment.get('failed_amount') or 0.0),
                'pending_amount': float(payment.get('pending_amount') or 0.0),
                'success_rate': success_rate,
                'payment_status': payment_status,
                'payment_status_key': payment_status_key,
            })
        projects.sort(
            key=lambda row: (
                0 if row['payment_status_key'] == 'danger' else
                1 if row['payment_status_key'] == 'warning' else
                2 if row['payment_status_key'] == 'none' else
                3,
                (row.get('project_name') or '').lower(),
            )
        )

        recent_failures = []
        failure_domain = [('status', '=', 'failed')]
        if scoped_project_ids is not None:
            failure_domain.append(('reconciliation_id.project_id', 'in', scoped_project_ids or [0]))
        failures = self.env['bhu.payment.reconciliation.bank.line'].search(
            failure_domain, limit=15, order='id desc',
        )
        for f in failures:
            recon = f.reconciliation_id
            recent_failures.append({
                'id': f.id,
                'reconciliation_id': recon.id,
                'reconciliation_name': recon.name or '',
                'utr_number': f.utr_number or '',
                'beneficiary_name': f.beneficiary_name or '',
                'beneficiary_account': f.beneficiary_account or '',
                'credit_amount': f.credit_amount or 0.0,
                'error': (f.error or f.event_status or '')[:120],
                'project_name': recon.project_id.name or '',
                'village_name': recon.village_id.name or '',
            })

        return {
            'stats': stats,
            'projects': projects,
            'villages': villages,
            'recent_failures': recent_failures,
        }
