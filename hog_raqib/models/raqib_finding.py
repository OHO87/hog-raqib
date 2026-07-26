# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RaqibFinding(models.Model):
    _name = "raqib.finding"
    _description = "ملاحظة تدقيق (Comment Raised)"
    _order = "audit_id, number"

    audit_id = fields.Many2one("raqib.audit", required=True, ondelete="cascade",
                               string="التدقيق")
    number = fields.Integer("الرقم", readonly=True)
    clause_id = fields.Many2one("raqib.clause", string="البند")
    line_id = fields.Many2one("raqib.audit.line", string="سطر الفحص")
    description = fields.Text("الوصف", required=True)
    classification = fields.Selection([
        ("class3", "3 — احتمال عدم مطابقة (Potential NC)"),
        ("class4", "4 — فرصة تحسين (OFI)"),
        ("nc_minor", "عدم مطابقة صغرى (Minor NC)"),
        ("nc_major", "عدم مطابقة كبرى (Major NC)"),
    ], required=True, string="التصنيف")
    state = fields.Selection([
        ("open", "مفتوحة"),
        ("closed", "مغلقة"),
    ], default="open", string="الحالة")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("number") and vals.get("audit_id"):
                last = self.search(
                    [("audit_id", "=", vals["audit_id"])],
                    order="number desc", limit=1)
                vals["number"] = (last.number or 0) + 1
        return super().create(vals_list)

    def urs_type_label(self):
        """التسمية الرقمية لعمود Type of Comment في تقرير URS."""
        self.ensure_one()
        return {
            "class3": "3",
            "class4": "4",
            "nc_minor": "Minor NC",
            "nc_major": "Major NC",
        }[self.classification]
