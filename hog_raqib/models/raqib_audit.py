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

# حقل النطاق على البند لكل نوع زيارة — surveillance و recert مفصولان عن
# stage2 (كانا يشيران إليه، فكانت ثلاثة أنواع زيارة متطابقة تماماً).
STAGE_FIELD = {
    "stage1": "applies_stage1",
    "stage2": "applies_stage2",
    "surveillance": "applies_surveillance",
    "recert": "applies_recert",
}

# نتائج تُصنَّف عدم مطابقة — تستدعي تحذيراً ناعماً في المرحلة الأولى
NC_RESULTS = ("nc_minor", "nc_major")

# ISO/IEC 17021-1 §9.3.1.2.4 يسمّي مخرجات المرحلة الأولى «areas of concern».
# قرار معتمد: تحذير ناعم وإعادة تسمية معروضة — لا منع صلب، لأن الوثيقة
# لا تمنع صراحةً تسجيل عدم مطابقة في المرحلة الأولى.
STAGE1_RESULT_LABELS = {
    "pending": "لم يفحص",
    "conform": "مستوفٍ للجاهزية",
    "class3": "مجال اهتمام — تصنيف 3",
    "class4": "مجال اهتمام — فرصة تحسين",
    "nc_minor": "مجال اهتمام (يقابل عدم مطابقة صغرى)",
    "nc_major": "مجال اهتمام جوهري (يقابل عدم مطابقة كبرى)",
    "na": "لا ينطبق",
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
                                  required=True, tracking=True,
                                  domain="[('is_meta','=',False)]")
    standard_ids = fields.Many2many(
        "raqib.standard", "raqib_audit_standard_rel", "audit_id", "standard_id",
        string="المواصفات", domain="[('is_meta','=',False)]",
        help="اختر مواصفة واحدة أو أكثر — نظام متكامل (IMS) عند اختيار أكثر من واحدة.")
    is_multi_standard = fields.Boolean(compute="_compute_is_multi_standard")

    @api.depends("standard_ids")
    def _compute_is_multi_standard(self):
        for rec in self:
            rec.is_multi_standard = len(rec.standard_ids) > 1

    @property
    def effective_standards(self):
        """المواصفات الفعلية: standard_ids إن حُددت وإلا standard_id (توافق خلفي)."""
        self.ensure_one()
        return self.standard_ids or self.standard_id

    @api.onchange("standard_ids")
    def _onchange_standard_ids(self):
        for rec in self:
            if rec.standard_ids and (
                    not rec.standard_id or rec.standard_id not in rec.standard_ids):
                rec.standard_id = rec.standard_ids.sorted("sequence")[:1]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_standard_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._sync_standard_vals(vals)
        return super().write(vals)

    @api.model
    def _sync_standard_vals(self, vals):
        """standard_id ↔ standard_ids: أيهما أعطي يملأ الآخر."""
        if vals.get("standard_ids") and not vals.get("standard_id"):
            cmd = vals["standard_ids"]
            ids = []
            for c in cmd:
                if c[0] == 6:
                    ids = list(c[2])
                elif c[0] == 4:
                    ids.append(c[1])
            if ids:
                vals["standard_id"] = ids[0]
        elif vals.get("standard_id") and "standard_ids" not in vals:
            vals["standard_ids"] = [(4, vals["standard_id"])]
        return vals
    audit_type = fields.Selection([
        ("stage1", "المرحلة الأولى (Stage 1)"),
        ("stage2", "المرحلة الثانية (Stage 2)"),
        ("surveillance", "زيارة مراقبة"),
        ("recert", "إعادة اعتماد"),
    ], string="نوع الزيارة", required=True, default="stage1", tracking=True)
    is_stage1 = fields.Boolean(compute="_compute_is_stage1", store=True)

    @api.depends("audit_type")
    def _compute_is_stage1(self):
        for rec in self:
            rec.is_stage1 = rec.audit_type == "stage1"

    # §9.3.1.2.2 e — «agree the details of stage 2»: مخرج إلزامي للمرحلة
    # الأولى يُنقل إلى التقرير.
    stage1_agreed_details = fields.Text(
        "تفاصيل المرحلة الثانية المتفق عليها",
        help="التوقيت والمدة والمواقع والعمليات ولغة التدقيق واحتياجات "
             "الخبرة الفنية — يُتفق عليها مع العميل في المرحلة الأولى "
             "(ISO/IEC 17021-1 §9.3.1.2.2e).")
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

    @api.model
    def _meta_standards(self):
        """المواصفات الوصفية (S1) — تُضاف مهما كانت المواصفات المختارة،
        ولا يختارها المدقق. تصفية بنودها تتم بعلم نوع الزيارة نفسه، فلا
        تظهر إلا حيث فُعِّلت — عملياً في المرحلة الأولى وحدها."""
        return self.env["raqib.standard"].search([("is_meta", "=", True)])

    def action_generate_lines(self):
        """توليد بنود الفحص من مكتبة المواصفة حسب نوع الزيارة — نقرة واحدة."""
        for rec in self:
            if rec.line_ids:
                raise UserError("توجد بنود مولدة مسبقاً — احذفها أولاً إن أردت إعادة التوليد.")
            standards = rec.effective_standards
            # البنود الوصفية (S1) تُصفّى بنفس علم نوع الزيارة، فلا تظهر
            # إلا حيث فُعِّلت — عملياً في المرحلة الأولى وحدها.
            search_std_ids = standards.ids + rec._meta_standards().ids
            clauses = self.env["raqib.clause"].search([
                ("standard_id", "in", search_std_ids),
                ("is_leaf", "=", True),
                (STAGE_FIELD[rec.audit_type], "=", True),
            ], order="sequence, number")
            vals_list = []
            if len(standards) <= 1:
                vals_list = [{"audit_id": rec.id, "clause_id": c.id,
                              "clause_ids": [(6, 0, [c.id])]} for c in clauses]
            else:
                # دمج البنود المشتركة (HLS) بمفتاح الدمج عبر المواصفات المختارة.
                # المفتاح = رقم البند، إلا للبنود المستثناة (نفس الرقم/متطلب مختلف).
                std_order = {s.id: i for i, s in enumerate(
                    standards.sorted("sequence"))}
                groups = {}
                order = []
                for c in clauses:
                    key = c.hls_key or c.number
                    if key not in groups:
                        groups[key] = c
                        order.append(key)
                    else:
                        groups[key] |= c
                for number in order:
                    grp = groups[number].sorted(
                        key=lambda c: std_order.get(c.standard_id.id, 99))
                    vals_list.append({
                        "audit_id": rec.id,
                        "clause_id": grp[0].id,
                        "clause_ids": [(6, 0, grp.ids)],
                    })
            self.env["raqib.audit.line"].create(vals_list)
            rec.state = "in_progress"
        return True

    def action_regenerate_lines(self):
        """إعادة توليد البنود بعد تغيير نوع الزيارة أو المواصفات.

        يُرفض إن كان أي سطر يحمل عمل مدقق — نتيجة أو ملاحظة أو مرجع وثيقة —
        لا النتيجة وحدها: سطر «لم يفحص» قد يحمل ملاحظة مكتوبة تُفقد بالحذف.
        (يعالج أيضاً ب-19: فشل التوليد بعد الإنشاء كان يترك تدقيقاً بلا بنود.)"""
        for rec in self:
            done = rec.line_ids.filtered(
                lambda l: l.result != "pending" or l.note
                or l.doc_reference or l.last_review_date)
            if done:
                raise UserError(
                    "لا يمكن إعادة التوليد: %d بنداً يحمل نتيجة أو ملاحظة أو "
                    "مرجع وثيقة. امسح محتواها أولاً إن كنت متأكداً." % len(done))
            rec.line_ids.unlink()
            rec.action_generate_lines()
        return True

    def _result_labels(self):
        """تسميات النتائج المعروضة — في المرحلة الأولى تُسمّى «مجال اهتمام»
        بدل «عدم مطابقة» (§9.3.1.2.4). القيم المخزَّنة لا تتغير، فلا تتأثر
        الملاحظات ولا التقارير ولا الإحصاءات."""
        self.ensure_one()
        base = dict(self.env["raqib.audit.line"]._fields[
            "result"]._description_selection(self.env))
        if self.audit_type == "stage1":
            base.update(STAGE1_RESULT_LABELS)
        return base

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
    clause_ids = fields.Many2many(
        "raqib.clause", "raqib_audit_line_clause_rel", "line_id", "clause_id",
        string="البنود المشمولة",
        help="في التدقيق متعدد المواصفات: البنود المتناظرة المدمجة في هذا السطر.")
    is_merged = fields.Boolean(compute="_compute_merged", store=True)
    standard_codes = fields.Char(compute="_compute_merged", store=True,
                                 string="المواصفات")

    @api.depends("clause_ids", "clause_id")
    def _compute_merged(self):
        for line in self:
            clauses = line.clause_ids or line.clause_id
            line.is_merged = len(clauses) > 1
            line.standard_codes = " · ".join(
                clauses.mapped("standard_id.code")) if clauses else ""

    def _covered_clauses(self):
        self.ensure_one()
        return self.clause_ids or self.clause_id

    def action_split_line(self):
        """فصل السطر المدمج إلى سطر مستقل لكل مواصفة.
        الملاحظة والنتيجة الحالية تبقى على السطر الأول، والبقية فارغة."""
        for line in self:
            clauses = line._covered_clauses()
            if len(clauses) <= 1:
                continue
            first, rest = clauses[0], clauses[1:]
            line.write({"clause_id": first.id,
                        "clause_ids": [(6, 0, [first.id])]})
            self.env["raqib.audit.line"].create([{
                "audit_id": line.audit_id.id,
                "clause_id": c.id,
                "clause_ids": [(6, 0, [c.id])],
            } for c in rest])
            if line.finding_id:
                line._sync_finding()
        return True
    number = fields.Char(related="clause_id.number", string="البند رقم", store=True)
    clause_name = fields.Char(related="clause_id.name", string="العنوان")
    requirement = fields.Text(related="clause_id.requirement", string="المتطلب")
    evidence_expected = fields.Text(related="clause_id.evidence_expected",
                                    string="الدليل المتوقع")
    evidence_hint = fields.Text(related="clause_id.evidence_hint",
                                string="أمثلة إرشادية")
    auditor_input_hint = fields.Char(related="clause_id.auditor_input_hint",
                                     string="المطلوب منك")
    stage1_focus = fields.Text(related="clause_id.stage1_focus",
                               string="حدود فحص المرحلة الأولى")
    is_surveillance_core = fields.Boolean(
        related="clause_id.is_surveillance_core", string="نواة المراقبة",
        store=True)

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
                    "clause_ids": [(6, 0, line._covered_clauses().ids)],
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
