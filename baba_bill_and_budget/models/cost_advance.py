from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)


class CostAdvance(models.Model):
    _name = 'cost.advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Cost Advance'

    user_id = fields.Many2one(comodel_name="res.users", string='Request By',
                              store=True, required=True)

    vendor_name = fields.Many2one(comodel_name="res.partner", string='Vendor Name',
                                  store=True, )

    note = fields.Text('Note')

    ref_no = fields.Char('Reference No')

    work_order_number = fields.Many2one('work.order', string='Work Order Number',
                                        domain="[('job_create_id', '=', name_job_create)]")

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

    date = fields.Date('Date')
    items = fields.One2many('cost.advance.items', 'summary_id', string='Items')
    subtotal = fields.Float('Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('items.total')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = sum(record.items.mapped('total'))

    name_job_center = fields.Many2one('job.center', string='Cost Center')
    # name_job_center = fields.Char('Name from Job Center', related='job_create_id.job_center_id.name',
    #                               store=True)
    name_job_create = fields.Many2one('job.create', string='Budget Name',
                                      domain="[('job_center_id', '=', name_job_center)]")

    user_id = fields.Many2one(comodel_name="res.users", string='Assign To', related='name_job_create.user_id',
                              readonly=True, store=True)
    super_visor = fields.Many2one(comodel_name="res.users", string='Supervisor', related='name_job_create.super_visor',
                                  readonly=True, store=True)
    t_budget_from_job_summary = fields.Float('Budget from Job Summary', readonly=True)
    advance_amount = fields.Float('Advance Request Amount')
    advance_approve = fields.Float('Advance Approve Amount')
    advance_number = fields.Char('Advance Number')
    approver = fields.One2many('cost.advance.approver', 'approver_id', string='Approver')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),  # New rejected state
    ], string='State', default='draft', readonly=True, copy=False, track_visibility='onchange')

    def mark_as_paid(self):
        self.ensure_one()
        if self.state == 'approved':
            self.state = 'paid'
            self.write({'state': 'paid'})

    app_amount = fields.Float('Budget Approved Amount', compute='_compute_app_amount', store=True, readonly=True)

    total_advance_approve = fields.Float('Total Advance Approved', compute='_compute_total_advance_approve', store=True,
                                         readonly=True)

    @api.depends('name_job_create')
    def _compute_app_amount(self):
        for advance in self:
            if advance.name_job_create:
                job_summary = self.env['job.summary'].search([('job_create_id', '=', advance.name_job_create.id)])
                if job_summary and job_summary.state == 'approved':
                    advance.app_amount = job_summary.app_total
                else:
                    advance.app_amount = 0.0
            else:
                advance.app_amount = 0.0


    @api.depends('work_order_number', 'advance_approve')
    def _compute_total_advance_approve(self):
        for advance in self:
            if advance.work_order_number:
                advance_records = self.search([('work_order_number', '=', advance.work_order_number.id)])
                total_advance_approve = sum(advance_records.mapped('advance_approve'))
                advance.total_advance_approve = total_advance_approve
            else:
                advance.total_advance_approve = 0.0

    def action_approve(self):
        approved = False  # Track if there's at least one approval

        for line in self.approver:
            approve_user = line.user_id.id

            # Check if the approval flow is set to 'approve'
            if line.option == 'approve':
                approved = True  # Mark that the approver has approved

                # Search for the approver in the 'amount.approval' model using SUPERUSER_ID
                approver = self.env['amount.approval'].with_user(SUPERUSER_ID).search([('user_id', '=', approve_user)])

                # Validate if the approver exists and their amount limit is sufficient
                if not approver:
                    raise exceptions.ValidationError(
                        f"Approver '{line.user_id.name}' not found or has no approval rights.")

                # Check if approver's limit is less than the amount to approve
                if approver.amount < self.subtotal:
                    raise exceptions.ValidationError(
                        f"User '{approver.user_id.name}' has insufficient approval limit to approve the advance. "
                        f"Limit: {approver.amount}, Required: {self.subtotal}")

        # Ensure that at least one approver has approved
        if approved:
            self.state = 'approved'
            self.write({'state': 'approved'})

            # Call the email function to send notifications
            self._send_approval_notification()

        else:
            # If no approver has set the flow to 'approve', raise an error
            raise exceptions.ValidationError(
                'The flow has not been approved. State cannot be changed to approved')

        return True

    def action_reject(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'rejected'
            else:
                raise exceptions.ValidationError("You can only reject in draft state.")

    def _send_approval_notification(self):
        # Ensure that the Assign To (user_id) and Supervisor (super_visor) emails are present
        assign_to_email = self.user_id.login
        supervisor_email = self.super_visor.login

        # Create the email subject and body content
        subject = f"Advance for {self.name_job_create.name} Approved"
        body = f"Dear {self.user_id.name} and {self.super_visor.name},\n\n" \
               f"The advance for {self.name_job_create.name} has been approved.\n\n" \
               f"Best regards,\n{self.env.user.name}"

        # Create and send the email
        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_from': self.env.user.email,  # Sender is the current user
            'email_to': f"{assign_to_email},{supervisor_email}",  # Send to both Assign To and Supervisor
            'auto_delete': True,  # Automatically delete the email after sending
        }

        # Use Odoo's email functionality to send the mail
        self.env['mail.mail'].create(mail_values).send()

    def open_bill_form(self):
        # Assuming you have necessary information for creating the invoice
        invoice_data = {
            'payment_reference': self.name_job_create.id,
            'partner_id': self.user_id.id,
            'move_type': 'in_invoice'

        }
        new_invoice = self.env['account.move'].create(invoice_data)

        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            # 'view_type': 'form',
            'view_mode': 'tree,form',
            'res_id': new_invoice.id,
        }
        return action

    def send_advance_email(self):
        for approver in self.approver:
            # Get the email addresses of the user who recommended and the recommended user
            recommending_user_email = approver.user_id.login
            recommended_user_email = approver.recommended_user_id.login

            # Construct the email content with a button and dynamic URL
            subject = f"Recommendation for Approve Request {self.name_job_center.name}"
            body = f"Dear {approver.recommended_user_id.name},\n\n{approver.user_id.name} has recommended you for the approval of Advance Request of {self.name_job_center.name}. Click the button below to view the details:\n\n"

            # URL for the button (dynamic URL)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/web?#id={self.id}&model=cost.advance&view_type=form&menu_id={self.env.ref('baba_bill_and_budget.menu_job_advance').id}"

            # HTML for the button
            button_html = f'<a href="{url}" style="background-color: #4CAF50; color: white; padding: 10px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px;">View Details</a>'

            body += button_html

            # Create the email
            mail = self.env['mail.mail'].create({
                'subject': subject,
                'body_html': body,
                'email_from': recommending_user_email,
                'email_to': recommended_user_email,
                'auto_delete': True,
            })

            # Send the email and check if it was sent successfully
            if mail:
                mail.send()
                # Confirm that the email was sent
                self.message_post(
                    body=f"Email sent successfully to {approver.recommended_user_id.name} for the advance request recommendation.")
            else:
                # Log a message or raise an alert if the email was not sent
                self.message_post(
                    body=f"Failed to send email to {approver.recommended_user_id.name}. Please check the email addresses and try again.")


class WorkOrderItems(models.Model):
    _name = 'cost.advance.items'
    _description = 'Cost Advance Items'

    summary_id = fields.Many2one('cost.advance', string='Work Order Summary')
    name = fields.Char('Name')
    item_name = fields.Char('Item Name')
    quantity = fields.Float('Quantity')
    unit_price = fields.Float('Unit Price')
    total = fields.Float('Total', compute='_compute_total', store=True)
    unit = fields.Selection(
        [
            ("bag", "BAG"),
            ("box", "BOX"),
            ("sft", "SFT"),
            ("cft", "CFT"),
            ("dollar", "DOLLAR"),
            ("floor", "FLOOR"),
            ("foot", "FOOT"),
            ("gm", "GM"),
            ("inch", "INCH"),
            ("kg", "KG"),
            ("liter", "LITER"),
            ("mbps", "MBPS"),
            ("ml", "ML"),
            ("node", "NODE"),
            ("package", "PACKAGE"),
            ("pair", "PAIR"),
            ("per month", "PER MONTH"),
            ("person", "PERSON"),
            ("pices", "PICES"),
            ("pkt", "PKT"),
            ("ream", "REAM"),
            ("set", "SET"),
            ("taka", "TAKA"),
            ("ton", "TON"),
            ("yards", "YARDS"),
            ("year", "YEAR"),
        ],
    )

    @api.depends('quantity', 'unit_price')
    def _compute_total(self):
        for record in self:
            record.total = record.quantity * record.unit_price

    advance_approve_related = fields.Float(string='Advance Approve Related', compute='_compute_advance_approve_related',
                                           store=True)

    @api.depends('summary_id.advance_approve')
    def _compute_advance_approve_related(self):
        for item in self:
            item.advance_approve_related = item.summary_id.advance_approve

    # approved_amount = fields.Float('Approve')


class CostAdvanceApprover(models.Model):
    _name = 'cost.advance.approver'
    _description = 'Cost Summary Approver'

    user_id = fields.Many2one(comodel_name="res.users", string='Request By',
                              store=True, required=True, default=lambda self: self._default_user())
    option = fields.Selection([
        ('recommendation', 'Recommendation To'),
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], string='Flow')
    recommended_user_id = fields.Many2one(comodel_name="res.users", string='Recommended To', store=True)
    approver_id = fields.Many2one('cost.advance', string='Job Summary')
    note = fields.Char("Note")
    time_of_approval = fields.Datetime(string='Time of Approval/Recommendation',
                                       default=lambda self: self._default_time_of_approval())

    @api.model
    def _default_time_of_approval(self):
        # Set the default time to Bangladesh Standard Time (BST)
        bst_timezone = pytz.timezone('Asia/Dhaka')
        current_time_utc = datetime.now(pytz.utc)
        current_time_bst = current_time_utc.astimezone(bst_timezone)
        return current_time_bst.strftime('%Y-%m-%d %H:%M:%S')

    @api.model
    def _default_user(self):
        # Assuming self.env.user is available to get the current user
        return self.env.user.id

    status_display = fields.Char(string='Status', compute='_compute_status_display', store=True, readonly=True)

    @api.depends('option')
    def _compute_status_display(self):
        for record in self:
            if record.option == 'reject':
                record.status_display = 'Rejected'
            elif record.option == 'job':
                record.status_display = 'Recommended'
            elif record.option == 'approve':
                record.status_display = 'Approved'
