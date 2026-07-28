# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RaqibStandard(models.Model):
    _name = "raqib.standard"
    _description = "مواصفة (رقيب)"
    _order = "sequence, id"

    name = fields.Char("المواصفة", required=True)
    code = fields.Char("الرمز", help="مثل: 9001")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_meta = fields.Boolean(
        "قائمة وصفية (لا تُختار)", default=False,
        help="مواصفة وصفية لا يختارها المدقق — بنودها تُضاف تلقائياً حسب "
             "نوع الزيارة (مثل قائمة أهداف المرحلة الأولى من "
             "ISO/IEC 17021-1 §9.3.1.2.2). تُستبعد من اختيار المواصفات "
             "ومن تصفية التقارير، وتظهر في تقرير كل مواصفة.")
    clause_ids = fields.One2many("raqib.clause", "standard_id", string="البنود")
    clause_count = fields.Integer(compute="_compute_clause_count")

    @api.depends("clause_ids")
    def _compute_clause_count(self):
        for rec in self:
            rec.clause_count = len(rec.clause_ids)


# بنود تحمل نفس الرقم عبر المواصفات لكن متطلبها مختلف جوهرياً — يُمنع دمجها.
# المفتاح: (رمز المواصفة، رقم البند) → يُفرد البند بمفتاح خاص فلا يندمج مع غيره.
NO_MERGE_CLAUSES = {
    # 9001 8.2 «متطلبات المنتجات والخدمات» ≠ 14001/45001 8.2 «الاستعداد والاستجابة للطوارئ»
    ("9001", "8.2"),
    # 14001 6.1.2 «الجوانب البيئية» ≠ 45001 6.1.2 «تحديد الأخطار وتقييم المخاطر»
    ("14001", "6.1.2"),
    ("45001", "6.1.2"),
}


class RaqibClause(models.Model):
    _name = "raqib.clause"
    _description = "بند مواصفة (رقيب)"
    _order = "standard_id, sequence, number"
    _rec_name = "display_label"

    standard_id = fields.Many2one(
        "raqib.standard", string="المواصفة", required=True, ondelete="cascade")
    number = fields.Char("رقم البند", required=True)
    name = fields.Char("عنوان البند", required=True)
    requirement = fields.Text("نص المتطلب")
    parent_id = fields.Many2one("raqib.clause", string="البند الأب",
                                domain="[('standard_id','=',standard_id)]")
    child_ids = fields.One2many("raqib.clause", "parent_id", string="البنود الفرعية")
    sequence = fields.Integer(default=10)
    is_leaf = fields.Boolean("بند قابل للتدقيق", default=True,
                             help="البنود الأب (مثل 4) لا تولّد سطر تدقيق")
    # --- نطاق البند حسب نوع الزيارة (م2) -------------------------------
    # المصدر: models/raqib_clause_scope.py — يُطبَّق في الترحيل و post_init_hook.
    # الافتراضات هنا تخص أي بند يُنشأ يدوياً لاحقاً: المرحلة الثانية وما بعدها،
    # والمرحلة الأولى تُفعَّل صراحةً فقط (وثائقية/جاهزية بنص §9.3.1.2.2).
    applies_stage1 = fields.Boolean(
        "المرحلة الأولى", default=False,
        help="ينطبق في تدقيق المرحلة الأولى — مراجعة وثائقية وجاهزية وفهم "
             "ونطاق (ISO/IEC 17021-1 §9.3.1.2.2).")
    applies_stage2 = fields.Boolean(
        "المرحلة الثانية", default=True,
        help="ينطبق في تدقيق المرحلة الثانية — أدلة المطابقة والأداء والضبط "
             "التشغيلي في الموقع (§9.3.1.3).")
    applies_surveillance = fields.Boolean(
        "المراقبة", default=True, help="ينطبق في زيارة المراقبة (§9.6.2.2).")
    applies_recert = fields.Boolean(
        "إعادة الاعتماد", default=True,
        help="ينطبق في تدقيق إعادة الاعتماد (§9.6.3.2.1).")
    is_surveillance_core = fields.Boolean(
        "نواة المراقبة", default=False,
        help="من البنود الثمانية الإلزامية في زيارة المراقبة "
             "(§9.6.2.2 a–h) — لا يجوز تخطيها.")
    stage1_focus = fields.Text(
        "ماذا يُفحص في المرحلة الأولى",
        help="حدود الفحص في المرحلة الأولى لهذا البند: مراجعة وثيقة؟ سؤال "
             "فهم؟ تثبيت نطاق؟ — يظهر للمدقق في تدقيقات المرحلة الأولى فقط.")

    evidence_expected = fields.Text(
        "الدليل المتوقع",
        help="ما الذي يبحث عنه المدقق لإثبات المطابقة (مثال 4.1: تحليل سوات/PESTEL محدث)")
    evidence_hint = fields.Text(
        "أمثلة إرشادية",
        help="أمثلة جاهزة (نقاط قوة/ضعف، سجلات نموذجية...) تُعرض للمدقق أثناء الفحص")
    auditor_input_hint = fields.Char(
        "إدخال المدقق المطلوب",
        help="أقل إدخال مطلوب من المدقق لهذا البند، مثل: تاريخ آخر مراجعة للتحليل")

    display_label = fields.Char(compute="_compute_display_label", store=True)
    hls_key = fields.Char(
        "مفتاح الدمج (HLS)", compute="_compute_hls_key", store=True, index=True,
        help="البنود التي تتشارك نفس المفتاح تُدمج في سطر تدقيق واحد عند اختيار "
             "أكثر من مواصفة. الافتراضي هو رقم البند، ما لم يكن البند ضمن "
             "استثناءات عدم الدمج.")

    @api.depends("number", "standard_id.code")
    def _compute_hls_key(self):
        for rec in self:
            code = rec.standard_id.code or ""
            number = rec.number or ""
            rec.hls_key = ("%s-%s" % (code, number)
                           if (code, number) in NO_MERGE_CLAUSES else number)

    _sql_constraints = [
        ("clause_unique", "unique(standard_id, number)",
         "رقم البند مكرر في هذه المواصفة"),
    ]

    @api.depends("number", "name")
    def _compute_display_label(self):
        for rec in self:
            rec.display_label = "%s %s" % (rec.number or "", rec.name or "")
