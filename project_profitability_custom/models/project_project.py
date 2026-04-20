from odoo import api, fields, models, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # ------------------------------------------------------------------
    # Computed profitability fields
    # ------------------------------------------------------------------

    profitability_margin = fields.Float(
        string='Profitability Margin (%)',
        compute='_compute_profitability',
        store=True,
        digits=(16, 2),
        aggregator='avg',
        help=(
            'Formula: (Revenue − Total Costs) / Revenue × 100\n'
            '• Revenue     : sum of amount_untaxed on confirmed Sale Orders linked to this project.\n'
            '• Vendor costs: sum of amount_untaxed on posted Vendor Bills linked via analytic account.\n'
            '• Purchase costs: sum of price_subtotal on confirmed Purchase Order lines linked via analytic account.\n'
            '• Timesheet costs: abs(Σ account.analytic.line.amount) for this project.\n\n'
            'Note: Vendor Bills and Purchase Orders may overlap when a PO has already been invoiced. '
            'Use the Recompute button to refresh after related records change.'
        ),
    )

    profitability_level = fields.Selection(
        selection=[
            ('0', 'Negative'),
            ('1', 'Low'),
            ('2', 'Medium'),
            ('3', 'Good'),
        ],
        string='Profitability Level',
        compute='_compute_profitability',
        store=True,
        help=(
            'Colour category based on the profitability margin:\n'
            '• Negative : < 0 %\n'
            '• Low      : 0 – 20 %\n'
            '• Medium   : 20 – 50 %\n'
            '• Good     : > 50 %'
        ),
    )

    profitability_margin_display = fields.Char(
        string='Margin',
        compute='_compute_profitability',
        store=True,
        help='Human-readable margin percentage (e.g. "42.3 %") used in kanban ribbons.',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends(
        'timesheet_ids',
        'timesheet_ids.unit_amount',
        'timesheet_ids.amount',
    )
    def _compute_profitability(self):
        """
        Compute profitability_margin, profitability_level and
        profitability_margin_display for each project.

        The @api.depends covers timesheet mutations automatically.
        For Sale Order, Vendor Bill and Purchase Order mutations call
        action_recompute_profitability() or run the scheduled action.
        """
        for project in self:
            revenue = project._get_profitability_revenue()
            total_costs = project._get_profitability_costs()

            if revenue:
                margin = (revenue - total_costs) / revenue * 100.0
            else:
                # No revenue: signal a deficit only if real costs exist
                margin = -100.0 if total_costs else 0.0

            project.profitability_margin = margin
            project.profitability_margin_display = f'{margin:.1f} %'

            if margin < 0.0:
                project.profitability_level = '0'
            elif margin < 20.0:
                project.profitability_level = '1'
            elif margin < 50.0:
                project.profitability_level = '2'
            else:
                project.profitability_level = '3'

    # ------------------------------------------------------------------
    # Revenue helper
    # ------------------------------------------------------------------

    def _get_profitability_revenue(self) -> float:
        """
        Return the untaxed revenue from confirmed Sale Orders whose
        project_id points to this project (sale_project module).
        """
        self.ensure_one()
        sale_orders = self.env['sale.order'].search([
            ('project_id', '=', self.id),
            ('state', 'in', ('sale', 'done')),
        ])
        return sum(sale_orders.mapped('amount_untaxed'))

    # ------------------------------------------------------------------
    # Cost helpers
    # ------------------------------------------------------------------

    def _get_profitability_costs(self) -> float:
        """Return the sum of all cost components for this project."""
        self.ensure_one()
        return (
            self._get_vendor_bill_cost()
            + self._get_purchase_order_cost()
            + self._get_timesheet_cost()
        )

    def _get_analytic_account(self):
        """
        Return the analytic account linked to this project.
        Uses the inverse relation on account.analytic.account (project_ids),
        which is the reliable path regardless of whether project.project
        exposes analytic_account_id as a direct field.
        """
        self.ensure_one()
        return self.env['account.analytic.account'].search(
            [('project_ids', 'in', self.id)], limit=1
        )

    def _get_vendor_bill_cost(self) -> float:
        """
        Return the net untaxed cost from posted Vendor Bills whose lines
        carry this project's analytic account in their analytic_distribution.

        Both in_invoice (bills) and in_refund (credit notes) are considered
        so that credit notes correctly reduce the cost.
        """
        self.ensure_one()
        analytic_account = self._get_analytic_account()
        if not analytic_account:
            return 0.0

        bills = self.env['account.move'].search([
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('state', '=', 'posted'),
            ('invoice_line_ids.analytic_distribution', 'in', [str(analytic_account.id)]),
        ])
        # amount_untaxed_signed is negative for in_invoice (payable) and
        # positive for in_refund (receivable from supplier). Negating the
        # sum converts to a positive net cost figure.
        return -sum(bills.mapped('amount_untaxed_signed'))

    def _get_purchase_order_cost(self) -> float:
        """
        Return the untaxed cost from confirmed Purchase Order lines whose
        analytic_distribution references this project's analytic account.

        Only non-section / non-note lines from confirmed or done POs are
        included (display_type=False).
        """
        self.ensure_one()
        analytic_account = self._get_analytic_account()
        if not analytic_account:
            return 0.0

        purchase_lines = self.env['purchase.order.line'].search([
            ('order_id.state', 'in', ('purchase', 'done')),
            ('display_type', '=', False),
            ('analytic_distribution', 'in', [str(analytic_account.id)]),
        ])
        return sum(purchase_lines.mapped('price_subtotal'))

    def _get_timesheet_cost(self) -> float:
        """
        Return the total timesheet cost for this project.

        Uses the `amount` field on account.analytic.line, which Odoo
        computes as unit_amount × employee cost rate and stores with a
        negative sign (debit). abs() converts it to a positive cost figure.
        """
        self.ensure_one()
        timesheet_lines = self.env['account.analytic.line'].search([
            ('project_id', '=', self.id),
        ])
        return abs(sum(timesheet_lines.mapped('amount')))

    # ------------------------------------------------------------------
    # Manual recompute action  (button in list / form views)
    # ------------------------------------------------------------------

    def action_recompute_profitability(self):
        """
        Force profitability recomputation on the selected project(s).

        Useful after Sale Orders, Vendor Bills or Purchase Orders are
        created or modified, since those mutations do not trigger the
        @api.depends automatically.
        """
        self._compute_profitability()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Profitability Updated'),
                'message': _('Profitability recomputed for %d project(s).') % len(self),
                'sticky': False,
                'type': 'success',
            },
        }
