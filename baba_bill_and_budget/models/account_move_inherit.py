from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
import logging
from num2words import num2words

# __init__.py in the models directory

_logger = logging.getLogger(__name__)


class CombineView(models.Model):
    _name = 'combined.recommendation.view'


class AccountAmount(models.Model):
    _inherit = "account.move"

    type_id = fields.Many2one(
        string="Type", comodel_name="bill.adjustment",
    )
    advance_id = fields.Many2one(
        string="Advance Id", comodel_name="approve.advance.summary",
    )
    approve_amount = fields.Float(string="Approved Budget Amount")
    total_advance_approve = fields.Float('Advance Approve')
    total_advance_taken = fields.Float('Total Advance Paid')
    account_select = fields.Many2one('account.account', string='Account')
    receive_amount = fields.Float('Payable Amount', compute='_compute_receive', store=True)
    narration = fields.Text('Narration')
    cheque = fields.Char('Cheque Number')
    bank = fields.Char('Bank')

    @api.depends('type_id')
    def _compute_receive(self):
        for record in self:
            if record.type_id:
                bill_adjustment = self.env['bill.adjustment'].browse(record.type_id.id)
                record.receive_amount = bill_adjustment.payable_amount if bill_adjustment else 0.0

    @api.onchange('advance_id')
    def onchange_advance_id(self):
        if self.advance_id:
            advance_summary = self.env['approve.advance.summary'].browse(self.advance_id.id)
            self.total_advance_approve = advance_summary.total_advance_approve if advance_summary else 0.0
            self.total_advance_taken = advance_summary.advance_amount if advance_summary else 0.0

    @api.onchange('type_id')
    def onchange_type_id(self):
        if self.type_id:
            bill_adjustment = self.env['bill.adjustment'].browse(self.type_id.id)
            self.approve_amount = bill_adjustment.app_amount if bill_adjustment else 0.0
            self.receive_amount = bill_adjustment.payable_amount if bill_adjustment else 0.0
            self.partner_id = bill_adjustment.vendor_name if bill_adjustment else False

    def create_move_lines(self):
        for record in self:
            if record.type_id:
                bill_adjustment = self.env['bill.adjustment'].browse(record.type_id.id)
                record.approve_amount = bill_adjustment.app_amount if bill_adjustment else 0.0

                new_lines = []
                for item in bill_adjustment.products:
                    new_lines.append((0, 0, {
                        'name': item.item_name,
                        'quantity': item.quantity,
                        'price_unit': item.unit_price,
                        'account_id': record.account_select.id,  # Update with your account selection
                    }))

                # Remove existing lines and add new ones
                record.invoice_line_ids = [(5, 0, 0)] + new_lines

    def your_button_function(self):
        self.update_move_lines()

    def create_advance_lines(self):
        for record in self:
            if record.advance_id:
                bill_adjustment = self.env['approve.advance.summary'].browse(record.advance_id.id)
                new_lines = []
                for item in bill_adjustment.products:
                    new_lines.append((0, 0, {
                        'account_id': record.account_select.id,  # Update with your account selection
                    }))

                # Remove existing lines and add new ones
                record.invoice_line_ids = [(5, 0, 0)] + new_lines

    def your_button_function(self):
        self.update_move_lines()

    @api.model
    def create(self, values):
        if 'amount_total' in values and 'receive_amount' in values:
            if values['amount_total'] > values['receive_amount']:
                raise ValidationError(_("Total amount cannot be greater than the payable amount."))
        return super(AccountAmount, self).create(values)

    def write(self, values):
        if 'amount_total' in values and 'receive_amount' in values:
            if values['amount_total'] > values['receive_amount']:
                raise ValidationError(_("Total amount cannot be greater than the payable amount."))
        return super(AccountAmount, self).write(values)

    @api.model
    def amount_to_text(self, amount):
        from num2words import num2words
        return num2words(amount, lang='en').capitalize() + ' Taka only'

    # def _get_total_debit_amount_words(self):
    #     self.ensure_one()
    #     total_debit = sum(self.line_ids.mapped('debit'))
    #     return self.amount_to_text(total_debit)

    def _get_total_debit_amount_words(self):
        self.ensure_one()
        total_debit = sum(self.line_ids.mapped('debit'))
        amount_words = num2words(total_debit, lang='en_IN').replace(',', '')
        return f"{amount_words} taka only"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"


class ResCompany(models.Model):
    _inherit = 'res.company'

    concern_type = fields.Selection([
        ('specific_concern_1', 'Bill And Budget'),
        ('specific_concern_2', 'Amar Security'),
        ('specific_concern_3', 'BVCL'),
        ('specific_concern_4', 'DCL'),
        ('specific_concern_5', 'DIC'),
        ('specific_concern_6', 'DJIT'),
        ('specific_concern_7', 'DNC'),
        ('specific_concern_8', 'KNOWLEDGE'),
        ('specific_concern_9', 'Eminence'),
        ('specific_concern_10', 'DIPTI'),
    ], string="Concern Type")
