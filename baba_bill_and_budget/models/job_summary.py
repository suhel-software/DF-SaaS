from odoo import api, fields, models, exceptions, SUPERUSER_ID
from odoo.exceptions import Warning
from odoo import models, fields, api, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)


class JobSummary(models.Model):
    _name = 'job.summary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Budget Summary'

    cost_center_id = fields.Many2one('job.center', string='Cost Center')

    job_create_id = fields.Many2one('job.create', string='Budget Name',
                                    domain="[('job_center_id', '=', cost_center_id)]")

    name = fields.Char('Job Name', related='job_create_id.name', readonly=True, store=True)

    user_id = fields.Many2one(comodel_name="res.users", string='Assign To', related='job_create_id.user_id',
                              readonly=True, store=True)

    super_visor = fields.Many2one(comodel_name="res.users", string='Supervisor', related='job_create_id.super_visor',
                                  readonly=True, store=True)

    date = fields.Date('Start Date')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),  # New rejected state
    ], string='State', default='draft', readonly=True, copy=False, track_visibility='onchange')

    items = fields.One2many('job.summary.items', 'summary_id', string='Items')
    approver_ids = fields.One2many('job.summary.approver', 'approver_id', string='Approver')
    subtotal = fields.Float('Subtotal', compute='_compute_subtotal', store=True)
    sub_total = fields.Float('Subtotal', compute='_compute_sub_total', store=True)
    app_total = fields.Float('Approved Amount', compute='_compute_approve_total', store=True)
    apptotal = fields.Float('Approved Amount', compute='_compute_re_approve_total', store=True)

    amount_approver = fields.Many2one('amount.approval')
    attachment = fields.Binary('Attachment', attachment=True)
    attachment_filename = fields.Char('Attachment Filename')
    ref_no = fields.Char('Reference No:')
    note = fields.Text('Note')

    additional_item_ids = fields.One2many(
        'job.summary.additional.item', 'job_summary_id', string='Additional Items'
    )

    additional_approver_ids = fields.One2many(
        'job.summary.additional.approver', 'job_summary_id', string='Additional Approvers'
    )

    show_additional_pages = fields.Boolean(string="Show Additional Pages", default=False)

    def toggle_additional_pages(self):
        self.show_additional_pages = not self.show_additional_pages

    @api.onchange('approve_budget')
    def _onchange_approve_budget(self):
        for record in self:
            # Update the app_total in related bill.adjustment records
            bill_adjustments = self.env['bill.adjustment'].search([('job_id', '=', record.job_create_id.id)])
            for bill_adjustment in bill_adjustments:
                bill_adjustment.app_total = record.approve_budget

    @api.depends('items.total')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = sum(record.items.mapped('total'))

    @api.depends('additional_item_ids.total')
    def _compute_sub_total(self):
        for record in self:
            record.sub_total = sum(record.additional_item_ids.mapped('total'))

    @api.depends('items.approved_amount')
    def _compute_approve_total(self):
        for record in self:
            record.app_total = sum(record.items.mapped('approved_amount'))

    @api.depends('additional_item_ids.approved_amount')
    def _compute_re_approve_total(self):
        for record in self:
            record.apptotal = sum(record.additional_item_ids.mapped('approved_amount'))

    def create_and_approve(self):
        # Variable to check if there's any approved flow
        is_approved = False
        current_user_id = self.env.user.id  # Get the current logged-in user's ID

        # Iterate over the approver lines
        for line in self.approver_ids:
            approve_user = line.user_id.id

            # Check if the flow is approved
            if line.option == 'approve':
                # Ensure only the approver who set 'approve' can approve
                if line.user_id.id != current_user_id:
                    raise exceptions.ValidationError(
                        f"Only {line.user_id.name} can approve this flow as they set the option to 'approve'.")

                is_approved = True  # Mark as approved

        if not approve_user:
            raise exceptions.ValidationError('User ID is not defined')

        # Use system user to search for approver_ids, avoiding access rights issues
        approver_ids = self.env['amount.approval'].with_user(SUPERUSER_ID).search([('user_id', '=', current_user_id)])

        if not approver_ids:
            raise exceptions.ValidationError('User does not have access to approve amounts')

        if approver_ids.amount < self.app_total:
            raise exceptions.ValidationError('User amount limit is not sufficient to approve budget')

        # Check if any approver line has the 'approve' option selected
        if not is_approved:
            raise exceptions.ValidationError('The flow has not been approved. State cannot be changed to approved.')

        # If all conditions are satisfied, update the state to 'approved'
        self.state = 'approved'
        self.write({'state': 'approved'})

        # Send email notification to Assign To and Supervisor
        self._send_approval_notification()

        return True

    def _send_approval_notification(self):
        assign_to_email = self.user_id.login
        supervisor_email = self.super_visor.login

        subject = f"Job Summary {self.name} Approved"
        body = f"Dear {self.user_id.name} and {self.super_visor.name},\n\nThe Job Summary {self.name} has been approved.\n\nBest Wishes to You"

        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_from': self.env.user.email,
            'email_to': f"{assign_to_email},{supervisor_email}",
            'auto_delete': True,
        }

        self.env['mail.mail'].create(mail_values).send()

    def action_reject(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'rejected'
            else:
                raise exceptions.ValidationError("You can only reject  in draft state.")

    def send_recommendation_email(self):
        # Get the last approver (the most recent one)
        last_approver = self.approver_ids[-1] if self.approver_ids else None

        if last_approver:
            # Get the email addresses of the user who recommended and the recommended user
            recommending_user_email = last_approver.user_id.login
            recommended_user_email = last_approver.recommended_user_id.login

            # Construct the email content with a button and dynamic URL
            subject = f"Recommendation for Job Summary {self.name}"
            body = f"Dear {last_approver.recommended_user_id.name},\n\n{last_approver.user_id.name} has recommended you for the approval of Job Summary {self.name}. Click the button below to view the details:\n\n"

            # URL for the button (dynamic URL)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/web?#id={self.id}&model=job.summary&view_type=form&menu_id={self.env.ref('baba_bill_and_budget.menu_job_summary').id}"

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
                    body=f"Email sent successfully to {last_approver.recommended_user_id.name} for recommendation.")
            else:
                # Log a message or raise an alert if the email was not sent
                self.message_post(
                    body=f"Failed to send email to {last_approver.recommended_user_id.name}. Please check the email addresses and try again.")

    # def send_recommendation_email(self):
    #     for approver_ids in self.approver_ids:
    #         # Get the email addresses of the user who recommended and the recommended user
    #         recommending_user_email = approver_ids.user_id.login
    #         recommended_user_email = approver_ids.recommended_user_id.login
    #
    #         # Construct the email content with a button and dynamic URL
    #         subject = f"Recommendation for Job Summary {self.name}"
    #         body = f"Dear {approver_ids.recommended_user_id.name},\n\n{approver_ids.user_id.name} has recommended you for the approval of Job Summary {self.name}. Click the button below to view the details:\n\n"
    #
    #         # URL for the button (dynamic URL)
    #         base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #         url = f"{base_url}/web?#id={self.id}&model=job.summary&view_type=form&menu_id={self.env.ref('baba_bill_and_budget.menu_job_summary').id}"
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
    #                 body=f"Email sent successfully to {approver_ids.recommended_user_id.name} for recommendation.")
    #         else:
    #             # Log a message or raise an alert if the email was not sent
    #             self.message_post(
    #                 body=f"Failed to send email to {approver_ids.recommended_user_id.name}. Please check the email addresses and try again.")

    def action_re_budget(self):
        """Create a new empty item record linked to the current job summary."""
        self.ensure_one()
        self.items.create({'summary_id': self.id})


class JobSummaryApprover(models.Model):
    _name = 'job.summary.approver'
    _description = 'Job Summary Approver'

    user_id = fields.Many2one(comodel_name="res.users", string='Request By',
                              store=True, required=True, default=lambda self: self._default_user())
    option = fields.Selection([
        ('recommendation', 'Recommendation To'),
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], string='Flow')
    recommended_user_id = fields.Many2one(comodel_name="res.users", string='Recommended To', store=True)
    approver_id = fields.Many2one('job.summary', string='Job Summary')
    b_note = fields.Char("Note")
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
            elif record.option == 'recommendation':
                record.status_display = 'Recommended'
            elif record.option == 'approve':
                record.status_display = 'Approved'


class JobSummaryItems(models.Model):
    _name = 'job.summary.items'
    _description = 'Job Summary Items'

    summary_id = fields.Many2one('job.summary', string='Job Summary')
    name = fields.Char('Name')
    item_name = fields.Char('Item Name')
    unit = fields.Selection(
        [
            ("bag", "BAG"),
            ("sft", "SFT"),
            ("box", "BOX"),
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
    quantity = fields.Float('Quantity')
    unit_price = fields.Float('Unit Price')
    total = fields.Float('Total', compute='_compute_total', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_total(self):
        for record in self:
            record.total = record.quantity * record.unit_price

    approved_amount = fields.Float('Approve', compute='_compute_approved_amount', inverse='_set_approved_amount',
                                   store=True)

    @api.depends('total')
    def _compute_approved_amount(self):
        for record in self:
            record.approved_amount = record.total

    def _set_approved_amount(self):
        for record in self:
            record.total = record.approved_amount

    # approved_amount = fields.Float('Approve')
