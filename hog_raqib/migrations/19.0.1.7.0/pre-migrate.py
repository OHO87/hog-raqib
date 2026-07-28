# -*- coding: utf-8 -*-
"""تبنّي سجلات 14001/45001 القائمة قبل تحميل ملفات البيانات الجديدة.

خلفية: بنود 14001 و45001 (61 بنداً) وسجلا المواصفتين أُنشئت بسكربت مباشر
على ستيجنغ فلم تحمل XML ID ولم تدخل المستودع. في م2-٠ صُدِّرت إلى
``data/raqib_14001_clauses.xml`` و``data/raqib_45001_clauses.xml``.

لولا هذا الترحيل لأنشأ محمِّل البيانات **نسخة ثانية** من كل سجل، وقيد
الفرادة على (standard_id, number) كان سيُسقط الترقية. هنا نكتب
``ir_model_data`` للسجلات القائمة بنفس المعرّفات التي يستخدمها ملف
البيانات، فيتبنّاها المحمّل بدل تكرارها.

المعرّف مشتق آلياً: ``c{code}_{number مع استبدال . بـ _}`` — نفس اشتقاق
مولّد التصدير.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = "hog_raqib"
CODES = ("14001", "45001")


def _ensure_imd(cr, model, res_id, xmlid):
    cr.execute("""
        SELECT id FROM ir_model_data WHERE module = %s AND name = %s
    """, (MODULE, xmlid))
    if cr.fetchone():
        return False
    cr.execute("""
        INSERT INTO ir_model_data
            (module, name, model, res_id, noupdate, create_date, write_date)
        VALUES (%s, %s, %s, %s, true, now(), now())
    """, (MODULE, xmlid, model, res_id))
    return True


def migrate(cr, version):
    if not version:
        return

    adopted_std = 0
    cr.execute("SELECT id, code FROM raqib_standard WHERE code IN %s", (CODES,))
    standards = cr.fetchall()
    for std_id, code in standards:
        if _ensure_imd(cr, "raqib.standard", std_id, "standard_%s" % code):
            adopted_std += 1

    adopted_clause = 0
    if standards:
        cr.execute("""
            SELECT c.id, c.number, s.code
            FROM raqib_clause c
            JOIN raqib_standard s ON s.id = c.standard_id
            WHERE s.code IN %s
        """, (CODES,))
        for clause_id, number, code in cr.fetchall():
            xmlid = "c%s_%s" % (code, (number or "").replace(".", "_"))
            if _ensure_imd(cr, "raqib.clause", clause_id, xmlid):
                adopted_clause += 1

    _logger.info(
        "raqib m2-0: adopted %s standards and %s clauses into ir_model_data.",
        adopted_std, adopted_clause)
