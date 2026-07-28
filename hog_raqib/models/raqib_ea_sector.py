# -*- coding: utf-8 -*-
"""قطاعات EA/IAF — مرجع معرَّف في الكود بدل حقل Studio هشّ.

الرموز 1–39 حسب تصنيف IAF/EA المعتمد لدى جهات المنح.
تُستخدم لترتيب أمثلة قاعدة المعرفة: نفس القطاع أولاً، ثم نفس العائلة.
"""
from odoo import api, fields, models

# عائلات القطاعات للترتيب التقريبي حين لا يتطابق الرمز تماماً
FAMILY_PRIMARY = "primary"        # 1–2   أولية
FAMILY_MANUFACTURING = "manuf"    # 3–24  تصنيع
FAMILY_UTILITIES = "utilities"    # 25–28 مرافق وإنشاء
FAMILY_SERVICES = "services"      # 29–39 خدمات

FAMILY_LABELS = [
    (FAMILY_PRIMARY, "قطاعات أولية"),
    (FAMILY_MANUFACTURING, "التصنيع"),
    (FAMILY_UTILITIES, "المرافق والإنشاء"),
    (FAMILY_SERVICES, "الخدمات"),
]


def family_of(code):
    """عائلة الرمز — تقبل نصاً أو رقماً، وتعيد False عند التعذر.

    مهم: لا تُرجع قيمة افتراضية مشتركة، وإلا اعتُبر عميلان بلا قطاع
    من «نفس العائلة» ورُفعت أمثلتهما بالخطأ.
    """
    try:
        c = int(str(code).strip())
    except (TypeError, ValueError):
        return False
    if c <= 0:
        return False
    if c <= 2:
        return FAMILY_PRIMARY
    if c <= 24:
        return FAMILY_MANUFACTURING
    if c <= 28:
        return FAMILY_UTILITIES
    return FAMILY_SERVICES


class RaqibEaSector(models.Model):
    _name = "raqib.ea.sector"
    _description = "قطاع EA/IAF"
    _order = "code_int, id"
    _rec_name = "display_name"

    code = fields.Char("الرمز", required=True, index=True)
    code_int = fields.Integer(compute="_compute_code_int", store=True)
    name = fields.Char("القطاع", required=True)
    family = fields.Selection(FAMILY_LABELS, compute="_compute_family",
                              store=True, string="العائلة")
    display_name = fields.Char(compute="_compute_display_name", store=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("ea_code_unique", "unique(code)", "رمز القطاع مكرر"),
    ]

    @api.depends("code")
    def _compute_code_int(self):
        for rec in self:
            try:
                rec.code_int = int((rec.code or "").strip())
            except (TypeError, ValueError):
                rec.code_int = 999

    @api.depends("code")
    def _compute_family(self):
        for rec in self:
            rec.family = family_of(rec.code) or False

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s" % (rec.code or "", rec.name or "")
