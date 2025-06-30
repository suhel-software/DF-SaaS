from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)


class BillAdjustment(models.Model):
    _name = 'bill.adjustment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bill And Adjustment'

    name = fields.Char('Bill Name', required=True)
    note = fields.Text('Note')
    ref_no = fields.Char('Reference Number')
    # job_id = fields.Many2one('job.create', string='Job Name')
    products = fields.One2many('bill.adjustment.items', 'bill_id', string='Products')
    app_amount = fields.Float('Approved Budget Amount', compute='_compute_app_amount', store=True)
    appamount = fields.Float('Approved Re-Budget Amount', compute='_compute_appamount', store=True)
    job_center_id = fields.Many2one('job.center', string='Job Center')
    job_id = fields.Many2one('job.create', string='Budget Name',
                             domain="[('job_center_id', '=', job_center_id)]")

    vendor_name = fields.Many2one(comodel_name="res.partner", string='Vendor Name',
                                  store=True, )

    approver = fields.One2many('bill.adjustment.approver', 'approver_id', string='Approver')
    attachment = fields.Binary('Attachment', attachment=True)
    attachment_filename = fields.Char('Attachment Filename')
    user_id = fields.Many2one(comodel_name="res.users", string='Request By',
                              store=True, )
    subtotal = fields.Float('Subtotal', compute='_compute_subtotal', store=True)
    payable_amount = fields.Float('Payable Amount', compute='_compute_payable', store=True)

    @api.depends('subtotal', 'total_advance_taken')
    def _compute_payable(self):
        for record in self:
            record.payable_amount = record.subtotal - record.total_advance_taken

    work_order_number = fields.Many2one('work.order', string='Work Order Number',
                                        domain="[('job_create_id', '=', job_id)]")
    total_advance_approve = fields.Float('Total Advance Approved', compute='_compute_total_advance_approve', store=True,
                                         readonly=True)

    total_advance_taken = fields.Float('Total Advance Paid', compute='_compute_total_advance_taken', store=True,
                                       readonly=True)

    @api.depends('work_order_number')
    def _compute_total_advance_taken(self):
        for adjustment in self:
            if adjustment.work_order_number:
                cost_advance_records = self.env['approve.advance.summary'].search(
                    [('work_order_number', '=', adjustment.work_order_number.id)])
                bill_adjustment_records = self.search([('work_order_number', '=', adjustment.work_order_number.id)])

                total_advance_taken = sum(cost_advance_records.mapped('advance_amount'))
                total_advance_taken += sum(bill_adjustment_records.mapped('total_advance_taken'))

                adjustment.total_advance_taken = total_advance_taken
            else:
                adjustment.total_advance_taken = 0.0

    @api.depends('work_order_number')
    def _compute_total_advance_approve(self):
        for adjustment in self:
            if adjustment.work_order_number:
                cost_advance_records = self.env['cost.advance'].search(
                    [('work_order_number', '=', adjustment.work_order_number.id)])
                bill_adjustment_records = self.search([('work_order_number', '=', adjustment.work_order_number.id)])

                total_advance_approve = sum(cost_advance_records.mapped('advance_approve'))
                total_advance_approve += sum(bill_adjustment_records.mapped('total_advance_approve'))

                adjustment.total_advance_approve = total_advance_approve
            else:
                adjustment.total_advance_approve = 0.0

    @api.depends('products.total')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = sum(record.products.mapped('total'))

    @api.depends('job_id')
    def _compute_app_amount(self):
        # Compute app_amount based on the selected job_id
        for record in self:
            if record.job_id:
                job_summary = self.env['job.summary'].search([('job_create_id', '=', record.job_id.id)], limit=1)
                if job_summary:
                    record.app_amount = job_summary.app_total
                else:
                    # Handle the case where no job summary is found
                    record.app_amount = 0.0
            else:
                record.app_amount = 0.0

    @api.depends('job_id')
    def _compute_appamount(self):
        # Compute app_amount based on the selected job_id
        for record in self:
            if record.job_id:
                job_summary = self.env['job.summary'].search([('job_create_id', '=', record.job_id.id)], limit=1)
                if job_summary:
                    record.appamount = job_summary.apptotal
                else:
                    # Handle the case where no job summary is found
                    record.appamount = 0.0
            else:
                record.appamount = 0.0

    invoice_id = fields.Many2one('account.move', string='Invoice')
    label_amount_ids = fields.One2many('bill.adjustment.items', 'bill_id', string='Label and Amount Lines')
    customer_id = fields.Many2one('res.partner', string='Customer')  # Add this field or use your existing one
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),  # New state added
    ], string='State', default='draft', readonly=True, copy=False, track_visibility='onchange')

    # def bill_approve(self):
    #     self.ensure_one()
    #
    #     approved = False  # Track if there's at least one approval
    #
    #     for line in self.approver:
    #         approve_user = line.user_id.id
    #
    #         # Check if the approver's flow is set to 'approve'
    #         if line.option == 'approve':
    #             approved = True  # Mark that an approver has approved
    #
    #             # Search for the approver in the 'amount.approval' model using SUPERUSER_ID
    #             approver = self.env['amount.approval'].with_user(SUPERUSER_ID).search([('user_id', '=', approve_user)])
    #
    #             # Validate if the approver exists and their amount is sufficient
    #             if not approver:
    #                 raise exceptions.ValidationError('Approver not found or has no approval rights.')
    #
    #             if approver.amount < self.subtotal:
    #                 raise exceptions.ValidationError(f'User {approver.user_id.name} has insufficient approval limit.')
    #
    #     # New condition: Check if subtotal is greater than app_amount only if app_amount has a value
    #     if self.app_amount:
    #         if self.subtotal > self.app_amount:
    #             # Additional check for appamount
    #             if self.appamount < self.subtotal:
    #                 raise exceptions.ValidationError('Bill cannot exceed the approved budget amount.')
    #
    #     # Ensure that at least one approver has approved
    #     if approved:
    #         self.state = 'approved'
    #         self.write({'state': 'approved'})
    #
    #         # Call the email notification function
    #         self._send_approval_notification()
    #
    #     else:
    #         # If no approver has set the flow to 'approve', raise an error
    #         raise exceptions.ValidationError(
    #             'The flow has not been approved by any approver. State cannot be changed to approved.')
    #
    #     return True

    def bill_approve(self):
        self.ensure_one()

        approved = False  # Track if there's at least one approval
        current_user_id = self.env.user.id  # Get the current logged-in user's ID

        for line in self.approver:
            # Check if the approver's flow is set to 'approve'
            if line.option == 'approve':
                # Ensure only the approver who set 'approve' can approve
                if line.user_id.id != current_user_id:
                    raise exceptions.ValidationError(
                        f"Only {line.user_id.name} can approve this bill as they set the option to 'approve'.")

                approved = True  # Mark that an approver has approved

                # Search for the approver in the 'amount.approval' model using SUPERUSER_ID
                approver = self.env['amount.approval'].with_user(SUPERUSER_ID).search(
                    [('user_id', '=', current_user_id)])

                # Validate if the approver exists and their amount is sufficient
                if not approver:
                    raise exceptions.ValidationError('Approver not found or has no approval rights.')

                if approver.amount < self.subtotal:
                    raise exceptions.ValidationError(f'User {approver.user_id.name} has insufficient approval limit.')

        # New condition: Check if subtotal is greater than app_amount only if app_amount has a value
        if self.app_amount:
            if self.subtotal > self.app_amount:
                raise exceptions.ValidationError('Bill cannot exceed the approved budget amount.')

        # Ensure that at least one approver has approved
        if approved:
            self.state = 'approved'
            self.write({'state': 'approved'})

            # Call the email notification function
            self._send_approval_notification()
        else:
            # If no approver has set the flow to 'approve', raise an error
            raise exceptions.ValidationError(
                'The flow has not been approved by any approver. State cannot be changed to approved.')

        return True

    def action_reject(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'rejected'
            else:
                raise exceptions.ValidationError("You can only reject a cost advance in draft state.")

    def _send_approval_notification(self):
        # Get the creator's email (assuming it's the user who created the view or the bill)
        creator_email = self.create_uid.login  # Use create_uid to get the user who created this record

        # Get the name and job ID field values
        job_name = self.job_id.name  # Assuming 'job_id' is a Many2one field linked to a job
        name_field_value = self.name  # 'name' field value

        # Create the email subject and body
        subject = f"Bill Adjustment  for {job_name} Approved"
        body = f"Dear {self.create_uid.name},\n\nThe bill '{name_field_value}' for the job '{job_name}' has been approved.\n\nBest regards,\n{self.env.user.name}"

        # Create and send the email
        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_from': self.env.user.email,  # Sender is the current user
            'email_to': creator_email,  # Send the email to the user who created the record
            'auto_delete': True,  # Automatically delete the email after sending
        }

        # Use Odoo's mail functionality to send the email
        self.env['mail.mail'].create(mail_values).send()

        return True

    def mark_as_paid(self):
        self.ensure_one()
        if self.state == 'approved':
            self.state = 'paid'
            self.write({'state': 'paid'})

    def open_invoice_form(self):
        # Check if an invoice already exists for this bill adjustment
        if not self.invoice_id:
            # If not, create a new invoice
            invoice_data = {
                'payment_reference': self.id,
                'partner_id': self.user_id.id,
                'move_type': 'in_invoice'
            }
            new_invoice = self.env['account.move'].create(invoice_data)
            # Link the created invoice to this bill adjustment
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

    # def send_bill_and_adjustment_email(self):
    #     for approver in self.approver:
    #         # Get the email addresses of the user who recommended and the recommended user
    #         recommending_user_email = approver.user_id.login
    #         recommended_user_email = approver.recommended_user_id.login
    #
    #         # Construct the email content with a button and dynamic URL
    #         subject = f"Recommendation for Job Summary {self.name}"
    #         body = f"Dear {approver.recommended_user_id.name},\n\n{approver.user_id.name} has recommended you for the Bill And Adjustment approval of {self.name} of {self.job_id.name}. Click the button below to view the details:\n\n"
    #
    #         # URL for the button (dynamic URL)
    #         base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #         url = f"{base_url}/web?#id={self.id}&model=bill.adjustment&view_type=form&menu_id={self.env.ref('baba_bill_and_budget.menu_bil_generate').id}"
    #
    #         # HTML for the button
    #         button_html = f'<a href="{url}" style="background-color: #4CAF50; color: white; padding: 10px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px;">View Details</a>'
    #
    #         body += button_html
    #
    #         # Create the email
    #         mail = self.env['mail.mail'].create({
    #             'subject': subject,
    #             'body_html': body,
    #             'email_from': recommending_user_email,
    #             'email_to': recommended_user_email,
    #             'auto_delete': True,
    #         })
    #
    #         # Send the email and check if it was sent successfully
    #         if mail:
    #             mail.send()
    #             # Confirm that the email was sent
    #             self.message_post(
    #                 body=f"Email sent successfully to {approver.recommended_user_id.name} for the bill and adjustment recommendation.")
    #         else:
    #             # Log a message or raise an alert if the email was not sent
    #             self.message_post(
    #                 body=f"Failed to send email to {approver.recommended_user_id.name}. Please check the email addresses and try again.")

    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=[('res_model', '=', 'bill.adjustment')],
                                     string='Attachments')

    # last recommended person mail
    def send_bill_and_adjustment_email(self):
        # Get the last approver (the most recent one)
        last_approver = self.approver[-1] if self.approver else None

        if last_approver:
            # Get the email addresses of the user who recommended and the recommended user
            recommending_user_email = last_approver.user_id.login
            recommended_user_email = last_approver.recommended_user_id.login

            # Construct the email content with a button and dynamic URL
            subject = f"Recommendation for Job Summary {self.name}"
            body = f"Dear {last_approver.recommended_user_id.name},\n\n{last_approver.user_id.name} has recommended you for the Bill And Adjustment approval of {self.name} of {self.job_id.name}. Click the button below to view the details:\n\n"

            # URL for the button (dynamic URL)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/web?#id={self.id}&model=bill.adjustment&view_type=form&menu_id={self.env.ref('baba_bill_and_budget.menu_bil_generate').id}"

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
                    body=f"Email sent successfully to {last_approver.recommended_user_id.name} for the bill and adjustment recommendation.")
            else:
                # Log a message or raise an alert if the email was not sent
                self.message_post(
                    body=f"Failed to send email to {last_approver.recommended_user_id.name}. Please check the email addresses and try again.")

    def action_attach_files(self):
        """Open the wizard to upload attachments."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Attach Files',
            'res_model': 'bill.adjustment.attachment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bill_id': self.id,
            }
        }


class BillAdjustmentItems(models.Model):
    _name = 'bill.adjustment.items'
    _description = 'Job Summary Items'

    bill_id = fields.Many2one('bill.adjustment', string='Bill Summary')
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

    bill_id = fields.Many2one('bill.adjustment', string='Bill Adjustment')
    approved_amount = fields.Float('Approve', compute='_compute_approved_amount', inverse='_set_approved_amount',
                                   store=True)

    @api.depends('total')
    def _compute_approved_amount(self):
        for record in self:
            record.approved_amount = record.total

    def _set_approved_amount(self):
        for record in self:
            record.total = record.approved_amount


class BillAdjustmentApprover(models.Model):
    _name = 'bill.adjustment.approver'
    _description = 'Cost Summary Approver'

    user_id = fields.Many2one(comodel_name="res.users", string='Request By',
                              store=True, required=True, default=lambda self: self._default_user())

    option = fields.Selection([
        ('recommendation', 'Recommendation To'),
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], string='Flow')

    recommended_user_id = fields.Many2one(comodel_name="res.users", string='Recommended To', store=True)

    approver_id = fields.Many2one('bill.adjustment', string='Job Summary')

    time_of_approval = fields.Datetime(string='Time of Approval/Recommendation',
                                       default=lambda self: self._default_time_of_approval())

    ba_note = fields.Char('Note')

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
            elif record.option == 'recommendation':
                record.status_display = 'Recommended'
            elif record.option == 'approve':
                record.status_display = 'Approved'
