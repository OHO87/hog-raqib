# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RaqibClient(models.Model):
    _name = "raqib.client"
    _description = "عميل تدقيق (رقيب)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    name = fields.Char("اسم العميل", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="جهة الاتصال")
    client_number = fields.Char("رقم العميل في URS")
    scope_text = fields.Text(
        "نطاق الشهادة", tracking=True,
        help="نص النطاق كما سيظهر على الشهادة — يغذي أمثلة الأدلة المخصصة")
    industry = fields.Char("القطاع / مجال العمل")
    ea_sector_ids = fields.Many2many(
        "raqib.ea.sector", "raqib_client_ea_rel", "client_id", "sector_id",
        string="قطاعات EA",
        help="رمز أو أكثر من تصنيف IAF/EA. يحدد أي أمثلة من قاعدة المعرفة "
             "تُعرض للمدقق أولاً — أمثلة نفس القطاع تتصدر القائمة.")
    ea_sector_primary_id = fields.Many2one(
        "raqib.ea.sector", string="القطاع الأساسي",
        compute="_compute_ea_primary", store=True,
        help="أول قطاع بالترتيب — المستخدم في ترتيب الأمثلة وفي التقارير.")
    ea_codes = fields.Char(compute="_compute_ea_primary", store=True,
                           string="رموز EA")
    address = fields.Text("عنوان الموقع الدائم")
    employee_count = fields.Integer("عدد الموظفين في الموقع")
    fte_equiv = fields.Float("مكافئ الدوام الكامل (FTE)")
    site_count = fields.Integer("عدد المواقع", default=1)
    regulatory_text = fields.Text(
        "الالتزامات التنظيمية والتعاقدية",
        help="أهم التشريعات والعقود المنطبقة على منتج/خدمة العميل — "
             "يعبأ في جدول Regulatory Awareness في تقرير URS")
    regulatory_comment = fields.Text("تعليق المدقق على وعي العميل التنظيمي")
    process_ids = fields.One2many("raqib.client.process", "client_id",
                                  string="العمليات الجوهرية")
    audit_ids = fields.One2many("raqib.audit", "client_id", string="التدقيقات")
    audit_count = fields.Integer(compute="_compute_audit_count")
    notes = fields.Text("ملاحظات")

    @api.depends("ea_sector_ids")
    def _compute_ea_primary(self):
        for rec in self:
            sectors = rec.ea_sector_ids.sorted("code_int")
            rec.ea_sector_primary_id = sectors[:1]
            rec.ea_codes = ",".join(sectors.mapped("code"))

    @api.depends("audit_ids")
    def _compute_audit_count(self):
        for rec in self:
            rec.audit_count = len(rec.audit_ids)

    def action_view_audits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "التدقيقات",
            "res_model": "raqib.audit",
            "view_mode": "list,form",
            "domain": [("client_id", "=", self.id)],
            "context": {"default_client_id": self.id},
        }


class RaqibClientProcess(models.Model):
    _name = "raqib.client.process"
    _description = "عملية جوهرية لدى العميل"
    _order = "sequence, id"

    client_id = fields.Many2one("raqib.client", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    reference = fields.Char("المرجع", help="مثل: PR-01")
    name = fields.Char("اسم العملية أو القسم (بمسمى العميل)", required=True)
