from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)


class AmountLimit(models.Model):
    _name = 'amount.approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Amount Approval'

    user_id = fields.Many2one(comodel_name="res.users",
                              string='Name', required=True)

    amount = fields.Float('Amount Limit')


class JobCenter(models.Model):
    _name = 'job.center'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Budget Name'

    name = fields.Char('Name')
    location = fields.Char('Location')
    advance_records = fields.One2many('cost.advance', 'name_job_center', string='Cost Advances')
    job_create_ids = fields.One2many('job.summary', 'cost_center_id', string='Cost Summary')
    job_center_ids = fields.One2many('bill.adjustment', 'job_center_id', string='Cost Summary')


class JobCreate(models.Model):
    _name = 'job.create'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Budget Description'

    job_center_id = fields.Many2one('job.center', string='Job Center', required=True, create=False)
    name = fields.Char('Job Name')
    description = fields.Char('Job Description')
    reference_no = fields.Integer('Reference No')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    user_id = fields.Many2one(comodel_name="res.users",
                              string='Assign To', required=True, default=lambda self: self.env.uid)
    super_visor = fields.Many2one(comodel_name="res.users",
                                  string='Supervisor', required=True, default=lambda self: self.env.uid)
    budget_summary_count = fields.Integer(string="Budget Summary Count", compute="_compute_budget_summary")

    def _compute_budget_summary(self):
        for rec in self:
            budget_summary_count = self.env['job.summary'].search_count([('job_create_id', '=', rec.name)])
            rec.budget_summary_count = budget_summary_count

    def action_open_budget_summary(self):
        return {
            "type": 'ir.actions.act_window',
            "name": 'Budget Summary',
            "res_model": 'job.summary',
            "domain": [('job_create_id', '=', self.name)],
            "view_mode": "tree,form",
            "target": "current",
        }

    work_order_count = fields.Integer(string="Work Order Count", compute="_compute_work_order")

    def _compute_work_order(self):
        for rec in self:
            work_order_count = self.env['work.order'].search_count([('job_create_id', '=', rec.name)])
            rec.work_order_count = work_order_count

    def action_open_work_order(self):
        return {
            "type": 'ir.actions.act_window',
            "name": 'Work Order',
            "res_model": 'work.order',
            "domain": [('job_create_id', '=', self.name)],
            "view_mode": "tree,form",
            "target": "current",
        }

    advance_request_count = fields.Integer(string="Advance Request and Approve  Count",
                                           compute="_compute_advance_request")

    def _compute_advance_request(self):
        for rec in self:
            advance_request_count = self.env['cost.advance'].search_count([('name_job_create', '=', rec.name)])
            rec.advance_request_count = advance_request_count

    def action_open_advance_req_approve(self):
        return {
            "type": 'ir.actions.act_window',
            "name": 'Advance Req & App',
            "res_model": 'cost.advance',
            "domain": [('name_job_create', '=', self.name)],
            "view_mode": "tree,form",
            "target": "current",
        }

    advance_approve_count = fields.Integer(string="Advance Approve Count",
                                           compute="_compute_advance_approve")

    def _compute_advance_approve(self):
        for rec in self:
            advance_approve_count = self.env['approve.advance.summary'].search_count(
                [('name_job_create', '=', rec.name)])
            rec.advance_approve_count = advance_approve_count

    def action_open_advance_approve(self):
        return {
            "type": 'ir.actions.act_window',
            "name": 'Advance Approve',
            "res_model": 'approve.advance.summary',
            "domain": [('name_job_create', '=', self.name)],
            "view_mode": "tree,form",
            "target": "current",
        }

    adjustment_count = fields.Integer(string="Bill Adjustment Count",
                                      compute="_compute_adjustment_count")

    def _compute_adjustment_count(self):
        for rec in self:
            adjustment_count = self.env['bill.adjustment'].search_count(
                [('job_id', '=', rec.name)])
            rec.adjustment_count = adjustment_count

    def action_open_bill_adjustment(self):
        return {
            "type": 'ir.actions.act_window',
            "name": 'Bill Adjustment',
            "res_model": 'bill.adjustment',
            "domain": [('job_id', '=', self.name)],
            "view_mode": "tree,form",
            "target": "current",
        }

    def send_assignment_email(self):
        # Get the email addresses of user_id and super_visor
        user_email = self.user_id.login
        supervisor_email = self.super_visor.login

        # Construct the email content
        subject = f"Bill And Budget Approver: {self.job_center_id.name}"
        body = f"Dear {self.user_id.name},\n\nYou have been assigned for the job {self.name} at {self.job_center_id.name} and for this task your \n\nSupervisor: Mr/Mrs {self.super_visor.name}"

        # Create the email
        mail = self.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_from': supervisor_email,  # Set the supervisor's email as the sender
            'email_to': user_email,
            'auto_delete': True,
        })

        # Send the email and check if it was sent successfully
        if mail:
            mail.send()
            # Confirm that the email was sent
            self.message_post(body="Email sent successfully to the user and supervisor.")
        else:
            # Log a message or raise an alert if the email was not sent
            self.message_post(body="Failed to send email. Please check the email addresses and try again.")

