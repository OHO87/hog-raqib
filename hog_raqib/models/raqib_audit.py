# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

FINDING_RESULTS = ("class3", "class4", "nc_minor", "nc_major")

RESULT_TO_CLASSIFICATION = {
    "class3": "class3",
    "class4": "class4",
    "nc_minor": "nc_minor",
    "nc_major": "nc_major",
}


class RaqibAudit(models.Model):
    _name = "raqib.audit"
    _description = "تدقيق (رقيب)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    name = fields.Char("رقم الزيارة (JI)", required=True, tracking=True)
    client_id = fields.Many2one("raqib.client", string="العميل",
                                required=True, tracking=True)
    standard_id = fields.Many2one("raqib.standard", string="المواصفة",
                                  required=True, tracking=True)
    audit_type = fields.Selection([
        ("stage1", "المرحلة الأولى (Stage 1)"),
        ("stage2", "المرحلة الثانية (Stage 2)"),
        ("surveillance", "زيارة مراقبة"),
        ("recert", "إعادة اعتماد"),
    ], string="نوع الزيارة", required=True, default="stage1", tracking=True)
    state = fields.Selection([
        ("draft", "مسودة"),
        ("in_progress", "قيد التدقيق"),
        ("review", "مراجعة"),
        ("done", "مكتمل"),
    ], default="draft", tracking=True, string="الحالة")

    date_start = fields.Date("تاريخ البدء")
    date_end = fields.Date("تاريخ انتهاء التدقيق")
    team_ids = fields.One2many("raqib.audit.team", "audit_id", string="فريق التدقيق")
    mandays_planned = fields.Float("أيام التدقيق المخططة")
    mandays_actual = fields.Float("أيام التدقيق الفعلية")
    mandays_diff = fields.Float("الفرق", compute="_compute_mandays_diff", store=True)
    mandays_justification = fields.Text("تبرير الفرق")
    employees_onsite = fields.Integer("الموظفون في الموقع أثناء التدقيق")
    fte_equiv = fields.Float("مكافئ الدوام الكامل (FTE)")

    line_ids = fields.One2many("raqib.audit.line", "audit_id", string="بنود الفحص")
    finding_ids = fields.One2many("raqib.finding", "audit_id", string="الملاحظات")
    finding_count = fields.Integer(compute="_compute_counters")
    progress = fields.Float("نسبة الإنجاز", compute="_compute_counters")

    client_action = fields.Selection([
        ("none", "لا إجراء مطلوب"),
        ("consider_next", "يؤخذ بالاعتبار في الزيارة القادمة"),
        ("send_capa", "إرسال خطة إجراءات تصحيحية (تصنيف 3 و4)"),
        ("repeat_stage1", "إعادة Stage 1 / تقييم أولي"),
    ], string="الإجراء المطلوب من العميل",
        compute="_compute_client_action", store=True, readonly=False, tracking=True)
    recommendation = fields.Selection([
        ("arrange_stage2", "ترتيب تدقيق المرحلة الثانية"),
        ("client_advise", "العميل يبلغ عند الجاهزية"),
        ("continue_cert", "استمرار الشهادة"),
        ("suspend", "تعليق/إجراء خاص"),
    ], string="التوصية", tracking=True)
    next_visit_month = fields.Char("الزيارة القادمة (شهر/سنة)")
    next_visit_activity = fields.Char("نشاط الزيارة القادمة", default="Stage 2")
    scope_changed = fields.Boolean("تغير النطاق؟")
    revised_scope = fields.Text("النطاق المعدل")
    scope_justification = fields.Text("مبرر التعديل")
    report_docx = fields.Binary("تقرير URS المعبأ", attachment=True, readonly=True)
    report_docx_name = fields.Char("اسم ملف التقرير")

    @api.depends("mandays_planned", "mandays_actual")
    def _compute_mandays_diff(self):
        for rec in self:
            rec.mandays_diff = (rec.mandays_actual or 0.0) - (rec.mandays_planned or 0.0)

    @api.depends("line_ids.result", "finding_ids")
    def _compute_counters(self):
        for rec in self:
            rec.finding_count = len(rec.finding_ids)
            total = len(rec.line_ids)
            done = len(rec.line_ids.filtered(lambda l: l.result != "pending"))
            rec.progress = (done * 100.0 / total) if total else 0.0

    @api.depends("finding_ids.classification")
    def _compute_client_action(self):
        """يقترح الإجراء المطلوب من العميل حسب شدة الملاحظات — يبقى قابلاً للتعديل."""
        for rec in self:
            classes = set(rec.finding_ids.mapped("classification"))
            if "nc_major" in classes:
                rec.client_action = "repeat_stage1" if rec.audit_type == "stage1" else "send_capa"
            elif classes & {"class3", "class4", "nc_minor"}:
                rec.client_action = "send_capa"
            else:
                rec.client_action = "none"

    def action_generate_lines(self):
        """توليد بنود الفحص من مكتبة المواصفة حسب نوع الزيارة — نقرة واحدة."""
        stage_field = {
            "stage1": "applies_stage1",
            "stage2": "applies_stage2",
            "surveillance": "applies_stage2",
            "recert": "applies_stage2",
        }
        for rec in self:
            if rec.line_ids:
                raise UserError("توجد بنود مولدة مسبقاً — احذفها أولاً إن أردت إعادة التوليد.")
            clauses = self.env["raqib.clause"].search([
                ("standard_id", "=", rec.standard_id.id),
                ("is_leaf", "=", True),
                (stage_field[rec.audit_type], "=", True),
            ], order="sequence, number")
            self.env["raqib.audit.line"].create([{
                "audit_id": rec.id,
                "clause_id": c.id,
            } for c in clauses])
            rec.state = "in_progress"
        return True

    def action_open_report_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "تعبئة تقرير URS",
            "res_model": "raqib.report.fill",
            "view_mode": "form",
            "target": "new",
            "context": {"default_audit_id": self.id},
        }

    def action_done(self):
        self.write({"state": "done"})

    def action_review(self):
        self.write({"state": "review"})


class RaqibAuditTeam(models.Model):
    _name = "raqib.audit.team"
    _description = "عضو فريق التدقيق"
    _order = "sequence, id"

    audit_id = fields.Many2one("raqib.audit", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    role = fields.Selection([
        ("lead", "قائد الفريق"),
        ("member", "عضو"),
        ("specialist", "خبير فني"),
        ("translator", "مترجم"),
    ], required=True, default="lead", string="الدور")
    name = fields.Char("الاسم", required=True)
    days = fields.Float("أيام التدقيق")


class RaqibAuditLine(models.Model):
    _name = "raqib.audit.line"
    _description = "بند فحص في تدقيق"
    _order = "sequence, id"

    audit_id = fields.Many2one("raqib.audit", required=True, ondelete="cascade")
    sequence = fields.Integer(related="clause_id.sequence", store=True)
    clause_id = fields.Many2one("raqib.clause", string="البند", required=True)
    number = fields.Char(related="clause_id.number", string="البند رقم", store=True)
    clause_name = fields.Char(related="clause_id.name", string="العنوان")
    requirement = fields.Text(related="clause_id.requirement", string="المتطلب")
    evidence_expected = fields.Text(related="clause_id.evidence_expected",
                                    string="الدليل المتوقع")
    evidence_hint = fields.Text(related="clause_id.evidence_hint",
                                string="أمثلة إرشادية")
    auditor_input_hint = fields.Char(related="clause_id.auditor_input_hint",
                                     string="المطلوب منك")

    doc_reference = fields.Char("مرجع الوثيقة / السجل",
                                help="مثل: SWOT-2026 rev.3 أو QM-01 Issue 5")
    last_review_date = fields.Date("تاريخ آخر مراجعة")
    note = fields.Text("ملاحظة المدقق")
    result = fields.Selection([
        ("pending", "لم يفحص"),
        ("conform", "مطابق"),
        ("class3", "تصنيف 3 — احتمال عدم مطابقة"),
        ("class4", "تصنيف 4 — فرصة تحسين"),
        ("nc_minor", "عدم مطابقة صغرى"),
        ("nc_major", "عدم مطابقة كبرى"),
        ("na", "لا ينطبق"),
    ], default="pending", string="النتيجة", required=True)
    finding_id = fields.Many2one("raqib.finding", string="الملاحظة المرتبطة",
                                 readonly=True)

    def write(self, vals):
        res = super().write(vals)
        if "result" in vals or "note" in vals:
            self._sync_finding()
        return res

    def _sync_finding(self):
        """إنشاء/تحديث ملاحظة تلقائياً عندما تكون النتيجة تصنيفاً — دون أي نقرات إضافية."""
        Finding = self.env["raqib.finding"]
        for line in self:
            if line.result in FINDING_RESULTS:
                desc = line.note or (
                    "بند %s (%s): يتطلب معالجة." % (line.number, line.clause_name))
                vals = {
                    "audit_id": line.audit_id.id,
                    "clause_id": line.clause_id.id,
                    "line_id": line.id,
                    "description": desc,
                    "classification": RESULT_TO_CLASSIFICATION[line.result],
                }
                if line.finding_id:
                    line.finding_id.write(vals)
                else:
                    line.finding_id = Finding.create(vals)
            elif line.finding_id:
                line.finding_id.unlink()

    # أزرار نقرة واحدة من داخل القائمة
    def action_set_conform(self):
        self.write({"result": "conform"})

    def action_set_class3(self):
        self.write({"result": "class3"})

    def action_set_class4(self):
        self.write({"result": "class4"})

    def action_set_na(self):
        self.write({"result": "na"})
