# -*- coding: utf-8 -*-
"""واجهات JSON لتطبيق رقيب المستقل (/raqib) — حمولات مجمعة لتقليل الرحلات."""
import base64

from odoo import api, fields, models


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
                "active_audits": len(audits),
                "open_findings": open_findings,
                "pending_lines": pending_lines,
            },
            "audits": [self._app_audit_card(a) for a in audits] +
                      [self._app_audit_card(a) for a in done],
            "clients": self.env["raqib.client"].search_read(
                [], ["name"], limit=200),
            "standards": self.env["raqib.standard"].search_read(
                [], ["name", "code"], limit=20),
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
        client_id = vals.get("client_id")
        if not client_id and vals.get("client_name"):
            client_id = self.env["raqib.client"].create(
                {"name": vals["client_name"]}).id
        standard_ids = vals.get("standard_ids") or (
            [vals["standard_id"]] if vals.get("standard_id") else [])
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
        allowed = {k: v for k, v in vals.items() if k in (
            "mandays_planned", "mandays_actual", "mandays_justification",
            "recommendation", "client_action", "next_visit_month",
            "next_visit_activity", "state")}
        self.write(allowed)
        return True

    # ---------------------------------------------------- قاعدة المعرفة
    @staticmethod
    def _ea_family(code):
        """عائلة قطاع EA للترتيب: أولية / تصنيع / مرافق وإنشاء / خدمات."""
        try:
            c = int(code)
        except (TypeError, ValueError):
            return 9
        if c <= 2:
            return 0
        if c <= 24:
            return 1
        if c <= 28:
            return 2
        return 3

    @api.model
    def raqib_app_kb(self, line_id):
        """أمثلة قاعدة المعرفة لبند السطر — مرتبة حسب قطاع عميل التدقيق:
        نفس الرمز أولًا، ثم نفس عائلة القطاع، ثم البقية."""
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
        ea = client.x_ea_code if "x_ea_code" in client._fields else False
        fam = self._ea_family(ea)
        clause_std = {c.id: c.standard_id.code or "" for c in clauses}

        def rank(r):
            if ea and r.x_ea_code == ea:
                return (0, r.id)
            if ea and self._ea_family(r.x_ea_code) == fam:
                return (1, r.id)
            return (2, r.id)

        examples = Ex.search([("x_clause_id", "in", clauses.ids)])
        out = dict(empty)
        for ex in examples.sorted(key=rank):
            out[ex.x_kind].append({
                "id": ex.id,
                "text_en": ex.x_text or "",
                "text_ar": ex.x_text_ar or ex.x_text or "",
                "ea": ex.x_ea_code or "",
                "ea_label": labels.get(ex.x_ea_code, ""),
                "same": bool(ea and ex.x_ea_code == ea),
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
        """إدراج نص مثال في ملاحظة المدقق — يعيد النص المحدّث."""
        line = self.env["raqib.audit.line"].browse(line_id)
        ex = self.env["x_raqib.kb.example"].browse(example_id)
        sep = "\n• " if line.note else "• "
        line.note = (line.note or "") + sep + (ex.x_text or "")
        return line.note

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
