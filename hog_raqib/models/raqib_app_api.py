# -*- coding: utf-8 -*-
"""واجهات JSON لتطبيق رقيب المستقل (/raqib) — حمولات مجمعة لتقليل الرحلات."""
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .raqib_ea_sector import family_of

# حد أعلى لأمثلة قاعدة المعرفة المُحمَّلة لبند واحد — يمنع تحميل مئات
# الأمثلة لبند شائع. الترتيب يضمن أن الأقرب قطاعياً يبقى ضمن الحد.
KB_FETCH_LIMIT = 300
KB_PER_KIND_LIMIT = 40


def _sel_label(rec, field):
    return dict(rec._fields[field]._description_selection(rec.env)).get(
        rec[field] or "", "")


class RaqibAuditApp(models.Model):
    _inherit = "raqib.audit"

    # ------------------------------------------------------------ الرئيسية
    @api.model
    def raqib_app_home(self):
        user = self.env.user
        audits = self.search([("state", "!=", "done")], limit=60)
        done = self.search([("state", "=", "done")], limit=20)
        open_findings = self.env["raqib.finding"].search_count(
            [("state", "=", "open")])
        pending_lines = self.env["raqib.audit.line"].search_count(
            [("result", "=", "pending"), ("audit_id.state", "!=", "done")])
        return {
            "user_name": user.name,
            "is_manager": user.has_group("hog_raqib.group_raqib_manager"),
            "kpis": {
                # ب-21: search_count لا len() على نتيجة محدودة بـlimit
                "active_audits": self.search_count([("state", "!=", "done")]),
                "open_findings": open_findings,
                "pending_lines": pending_lines,
            },
            "audits": [self._app_audit_card(a) for a in audits] +
                      [self._app_audit_card(a) for a in done],
            "clients": self.env["raqib.client"].search_read(
                [], ["name", "ea_codes"], limit=200),
            "standards": self.env["raqib.standard"].search_read(
                [], ["name", "code"], limit=20),
            "ea_sectors": [
                {"id": s.id, "code": s.code, "name": s.name,
                 "label": s.display_name}
                for s in self.env["raqib.ea.sector"].search([])
            ],
        }

    def _app_audit_card(self, a):
        standards = a.standard_ids or a.standard_id
        return {
            "id": a.id, "name": a.name,
            "client": a.client_id.name,
            "standard": " · ".join(
                s.code or s.name for s in standards.sorted("sequence")),
            "is_multi": len(standards) > 1,
            "type_label": _sel_label(a, "audit_type"),
            "state": a.state, "state_label": _sel_label(a, "state"),
            "progress": round(a.progress),
            "findings": a.finding_count,
        }

    # -------------------------------------------------------- إنشاء سريع
    @api.model
    def raqib_app_quick_create(self, vals):
        # ب-18: تحقق خادمي — لا نعتمد على تحقق الواجهة وحده
        if not (vals.get("name") or "").strip():
            raise UserError(_("رقم الزيارة (JI) مطلوب."))
        standard_ids = vals.get("standard_ids") or (
            [vals["standard_id"]] if vals.get("standard_id") else [])
        if not standard_ids:
            raise UserError(_("اختر مواصفة واحدة على الأقل."))

        client_id = vals.get("client_id")
        sector_ids = [s for s in (vals.get("ea_sector_ids") or []) if s]
        if not client_id:
            client_name = (vals.get("client_name") or "").strip()
            if not client_name:
                raise UserError(_("اسم العميل مطلوب لإنشاء عميل جديد."))
            if not sector_ids:
                raise UserError(_(
                    "حدد قطاع EA واحداً على الأقل للعميل الجديد — "
                    "عليه يعتمد ترتيب الأمثلة المقترحة من التدقيقات السابقة."))
            client_id = self.env["raqib.client"].create({
                "name": client_name,
                "ea_sector_ids": [(6, 0, sector_ids)],
            }).id
        elif sector_ids:
            # عميل قائم بلا قطاع — نكمل بياناته من نفس الشاشة
            client = self.env["raqib.client"].browse(client_id)
            if not client.ea_sector_ids:
                client.ea_sector_ids = [(6, 0, sector_ids)]

        audit = self.create({
            "name": vals["name"],
            "client_id": client_id,
            "standard_ids": [(6, 0, standard_ids)],
            "audit_type": vals.get("audit_type", "stage1"),
        })
        audit.action_generate_lines()
        return audit.id

    # ----------------------------------------------------------- التدقيق
    def raqib_app_audit(self):
        self.ensure_one()
        return {
            "header": dict(self._app_audit_card(self), **{
                "scope": self.client_id.scope_text or "",
                "mandays_planned": self.mandays_planned,
                "mandays_actual": self.mandays_actual,
                "client_action": self.client_action or "",
                "client_action_label": _sel_label(self, "client_action"),
                "recommendation": self.recommendation or "",
                "next_visit_month": self.next_visit_month or "",
                "report_name": self.report_docx_name or "",
                "standard_list": [{
                    "id": s.id, "code": s.code or s.name,
                } for s in (self.standard_ids or self.standard_id).sorted(
                    "sequence")],
            }),
            "lines": [self._app_line(l) for l in self.line_ids],
            "findings": self._app_findings(),
            "result_labels": dict(
                self.env["raqib.audit.line"]._fields[
                    "result"]._description_selection(self.env)),
        }

    def _app_line(self, l):
        clauses = l._covered_clauses()
        return {
            "id": l.id,
            "number": l.number,
            "title": l.clause_name,
            "requirement": l.requirement or "",
            "evidence": l.evidence_expected or "",
            "hint": l.evidence_hint or "",
            "input_hint": l.auditor_input_hint or "",
            "doc_reference": l.doc_reference or "",
            "last_review_date": l.last_review_date
                and fields.Date.to_string(l.last_review_date) or "",
            "note": l.note or "",
            "result": l.result,
            "finding_number": l.finding_id.number or 0,
            "is_merged": l.is_merged,
            "standards": l.standard_codes or "",
            "segments": [{
                "clause_id": c.id,
                "std": c.standard_id.code or "",
                "number": c.number,
                "title": c.name,
                "requirement": c.requirement or "",
                "evidence": c.evidence_expected or "",
                "hint": c.evidence_hint or "",
            } for c in clauses] if l.is_merged else [],
        }

    @api.model
    def raqib_app_split_line(self, line_id):
        """فصل سطر مدمج — يعيد قائمة البنود المحدثة كاملة."""
        line = self.env["raqib.audit.line"].browse(line_id)
        audit = line.audit_id
        line.action_split_line()
        return [audit._app_line(l) for l in audit.line_ids]

    def _app_findings(self):
        return [{
            "id": f.id, "number": f.number,
            "description": f.description,
            "classification": f.classification,
            "classification_label": _sel_label(f, "classification"),
            "clause": f.clause_id.display_label or "",
            "standards": " · ".join(
                (f.standard_ids or f.clause_id.standard_id).mapped("code")),
        } for f in self.finding_ids]

    # ------------------------------------------------------- تحديث سطر
    @api.model
    def raqib_app_set_line(self, line_id, vals):
        line = self.env["raqib.audit.line"].browse(line_id)
        allowed = {k: v for k, v in vals.items() if k in (
            "result", "doc_reference", "last_review_date", "note")}
        if allowed.get("last_review_date") == "":
            allowed["last_review_date"] = False
        line.write(allowed)
        audit = line.audit_id
        return {
            "result": line.result,
            "finding_number": line.finding_id.number or 0,
            "progress": round(audit.progress),
            "findings_count": audit.finding_count,
            "findings": audit._app_findings(),
            "client_action": audit.client_action or "",
            "client_action_label": _sel_label(audit, "client_action"),
        }

    # -------------------------------------------------- خلاصة وتقرير
    def raqib_app_set_audit(self, vals):
        self.ensure_one()
        # ب-7: أُزيل "state" من القائمة البيضاء — كان أي مدقق ينقل التدقيق
        # إلى done عبر RPC مباشر متجاوزاً أزرار سير العمل.
        allowed = {k: v for k, v in vals.items() if k in (
            "mandays_planned", "mandays_actual", "mandays_justification",
            "recommendation", "client_action", "next_visit_month",
            "next_visit_activity")}
        self.write(allowed)
        return True

    # ---------------------------------------------------- قاعدة المعرفة
    @staticmethod
    def _ea_family(code):
        """عائلة قطاع EA — تُعيد False عند التعذر (لا قيمة مشتركة).

        ب-16: الإصدار السابق كان يعيد 9 لكل رمز غير صالح، فيُعتبر عميلان
        بلا قطاع «من نفس العائلة» وتُرفع أمثلتهما بالخطأ.
        """
        return family_of(code)

    @staticmethod
    def _client_ea_codes(client):
        """كل رموز EA للعميل كمجموعة نصية، مع توافق خلفي مع حقل Studio."""
        codes = set()
        if "ea_sector_ids" in client._fields:
            codes |= {c for c in client.ea_sector_ids.mapped("code") if c}
        if not codes and "x_ea_code" in client._fields and client.x_ea_code:
            codes.add(client.x_ea_code)
        return codes

    @api.model
    def raqib_app_kb(self, line_id):
        """أمثلة قاعدة المعرفة لبند السطر — مرتبة حسب قطاعات عميل التدقيق:
        نفس الرمز أولًا، ثم نفس عائلة القطاع، ثم البقية.

        يدعم أكثر من رمز للعميل الواحد (عملاء متعددو النشاط)."""
        empty = {"evidence": [], "ofi": [], "nc": []}
        if "x_raqib.kb.example" not in self.env:
            return empty
        line = self.env["raqib.audit.line"].browse(line_id)
        clauses = line._covered_clauses()
        if not clauses:
            return empty
        Ex = self.env["x_raqib.kb.example"]
        labels = dict(Ex._fields["x_ea_code"]._description_selection(self.env))
        client = line.audit_id.client_id
        codes = self._client_ea_codes(client)
        families = {f for f in (family_of(c) for c in codes) if f}
        clause_std = {c.id: c.standard_id.code or "" for c in clauses}

        def rank(r):
            if codes and r.x_ea_code in codes:
                return (0, r.id)
            if families and family_of(r.x_ea_code) in families:
                return (1, r.id)
            return (2, r.id)

        # ب-22: حد على الجلب — بند شائع قد يحمل مئات الأمثلة
        examples = Ex.search([("x_clause_id", "in", clauses.ids)],
                             limit=KB_FETCH_LIMIT)
        out = {"evidence": [], "ofi": [], "nc": []}
        for ex in examples.sorted(key=rank):
            # ب-6: قيمة x_kind غير متوقعة كانت تُحدث KeyError وتُسقط اللوحة
            bucket = out.get(ex.x_kind)
            if bucket is None or len(bucket) >= KB_PER_KIND_LIMIT:
                continue
            bucket.append({
                "id": ex.id,
                "text_en": ex.x_text or "",
                "text_ar": ex.x_text_ar or ex.x_text or "",
                "ea": ex.x_ea_code or "",
                "ea_label": labels.get(ex.x_ea_code, ""),
                "same": bool(codes and ex.x_ea_code in codes),
                "std": clause_std.get(ex.x_clause_id.id, "")
                    if line.is_merged else "",
            })
        return out

    @api.model
    def raqib_app_append_note(self, line_id, text):
        """إلحاق نقطة (بعد تصحيح الأقواس) بملاحظة المدقق — يعيد النص المحدّث."""
        line = self.env["raqib.audit.line"].browse(line_id)
        sep = "\n• " if line.note else "• "
        line.note = (line.note or "") + sep + (text or "")
        return line.note

    @api.model
    def raqib_app_use_example(self, line_id, example_id):
        """إدراج نص مثال في ملاحظة المدقق — يعيد النص المحدّث.

        ب-25: الواجهة تستخدم raqib_app_append_note بعد محرر الأقواس؛
        هذه أُبقيت كواجهة توافق للنداءات الخارجية ولم تعد تكرر المنطق.
        """
        ex = self.env["x_raqib.kb.example"].browse(example_id)
        return self.raqib_app_append_note(line_id, ex.x_text or "")

    def raqib_app_fill_report(self, filename, b64data, standard_id=False):
        self.ensure_one()
        wizard = self.env["raqib.report.fill"].create({
            "audit_id": self.id,
            "standard_id": standard_id or False,
            "template_file": b64data,
            "template_filename": filename,
        })
        action = wizard.action_fill()
        return action.get("url", "")
