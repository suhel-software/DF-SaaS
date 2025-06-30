from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)


class ApproveAdvance(models.Model):
    _name = 'approve.advance.summary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Advance Approve Summary'

    name = fields.Char('Name')
    user_id = fields.Many2one(comodel_name="res.users", string='Request By',
                              store=True, required=True)
    vendor_name = fields.Many2one(comodel_name="res.partner", string='Vendor Name',
                                  store=True, )
    name_job_center = fields.Many2one('job.center', string='Cost Center')

    name_job_create = fields.Many2one('job.create', string='Budget Name',
                                      domain="[('job_center_id', '=', name_job_center)]")
    advance_amount = fields.Float('Advance amount Given')
    total_advance_approve = fields.Float('Total Advance Approved', compute='_compute_total_advance_approve', store=True,
                                         readonly=True)

    user_id = fields.Many2one(comodel_name="res.users", string='Assign To', related='name_job_create.user_id',
                              readonly=True, store=True)
    super_visor = fields.Many2one(comodel_name="res.users", string='Supervisor', related='name_job_create.super_visor',
                                  readonly=True, store=True)
    work_order_number = fields.Many2one('work.order', string='Work Order Number',
                                        domain="[('job_create_id', '=', name_job_create)]")

    related_account_moves = fields.One2many(
        comodel_name='account.move',
        inverse_name='advance_id',
        string='Related Account Moves'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('paid', 'Paid')
    ], default='draft', string='Status', track_visibility='onchange')

    def action_mark_paid(self):
        approved = False

        # Check user's approval limit using SUPERUSER_ID to bypass access rights
        approval_record = self.env['amount.approval'].with_user(SUPERUSER_ID).search(
            [('user_id', '=', self.env.user.id)], limit=1)

        if self.advance_amount <= approval_record.amount:
            self.state = 'paid'
        else:
            raise exceptions.UserError("You don't have the approval limit to mark this as paid.")

    @api.onchange('name_job_create')
    def _onchange_name_job_create(self):
        if self.name_job_create:
            return {
                'domain': {
                    'work_order_number': [('job_create_id', '=', self.name_job_create.id)]
                }
            }
        else:
            return {
                'domain': {
                    'work_order_number': []
                }
            }

    @api.depends('work_order_number')
    def _compute_total_advance_approve(self):
        for adjustment in self:
            if adjustment.work_order_number:
                cost_advance_records = self.env['cost.advance'].search(
                    [('work_order_number', '=', adjustment.work_order_number.id)])
                # bill_adjustment_records = self.search([('work_order_number', '=', cost_advance_records.work_order_number)])
                if cost_advance_records:
                    approve_amount = cost_advance_records.advance_approve
                    print(approve_amount)
                    self.total_advance_approve = approve_amount
                else:
                    self.total_advance_approve = 0.0

    note = fields.Text('Note')
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True, copy=False)

    def open_bill_form(self):
        # Check if an invoice already exists for this advance approval
        if not self.invoice_id:
            # If not, create a new invoice
            invoice_data = {
                'payment_reference': self.name_job_create.id,
                'partner_id': self.user_id.id,
                'move_type': 'in_invoice'
            }
            new_invoice = self.env['account.move'].create(invoice_data)
            # Link the created invoice to this advance approval
            self.invoice_id = new_invoice
        else:
            # If an invoice already exists, use the existing one
            new_invoice = self.invoice_id

        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': new_invoice.id,
        }
        return action
