# -*- coding: utf-8 -*-
"""م2 — تمييز أنواع الزيارات: تطبيق مصفوفة النطاق ووسم قاعدة المعرفة.

1. تطبيق ``CLAUSE_SCOPE`` على البنود القائمة. ملفات البيانات محمّلة بـ
   ``noupdate="1"`` فلا تُحدِّث سجلاً موجوداً — مصدر الحقيقة الوحيد للأعلام
   هو ``models/raqib_clause_scope.py`` ويُطبَّق من هنا.
2. إنشاء الحقل اليدوي ``x_stage_scope`` على نموذج قاعدة المعرفة (نموذج
   Studio) — لا يمكن تعريفه في الكود لأن النموذج يدوي.
3. وسم النقاط غير المصنَّفة آلياً. آمن للتكرار ولا يدهس تصنيفاً يدوياً،
   ويترك أي محتوى يُستورد لاحقاً ظاهراً حتى يُوسم.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.hog_raqib.models.raqib_clause_scope import apply_scope

_logger = logging.getLogger(__name__)

KB_MODEL = "x_raqib.kb.example"
KB_SCOPE_FIELD = "x_stage_scope"


def _ensure_kb_scope_field(env):
    """حقل نطاق الزيارة على نموذج قاعدة المعرفة اليدوي."""
    if KB_MODEL not in env:
        _logger.warning("raqib m2: %s not present — skipping KB tagging.",
                        KB_MODEL)
        return False
    if KB_SCOPE_FIELD in env[KB_MODEL]._fields:
        return True
    model = env["ir.model"].sudo().search([("model", "=", KB_MODEL)], limit=1)
    if not model:
        return False
    env["ir.model.fields"].sudo().create({
        "name": KB_SCOPE_FIELD,
        "model_id": model.id,
        "field_description": "نطاق الزيارة الصالح",
        "help": "فارغ = غير مصنَّفة (تظهر في كل الزيارات) · "
                "stage2_only = دليل مرحلة ثانية يُخفى في المرحلة الأولى · "
                "any = صالحة لكل الزيارات.",
        "ttype": "char",
        "size": 16,
        "state": "manual",
        "index": True,
    })
    # إنشاء حقل يدوي يعيد بناء السجل عادةً؛ نتأكد صراحةً تفادياً لاختلاف
    # التوقيت بين الإصدارات.
    if KB_SCOPE_FIELD not in env[KB_MODEL]._fields:
        env.flush_all()
        env.registry.setup_models(env.cr)
    return KB_SCOPE_FIELD in env[KB_MODEL]._fields


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    updated = apply_scope(env)
    _logger.info("raqib m2: visit-scope matrix applied to %s clauses.", updated)

    if _ensure_kb_scope_field(env):
        env.registry.clear_cache()
        env = api.Environment(cr, SUPERUSER_ID, {})
        stats = env["raqib.audit"].raqib_kb_autotag_scope(only_untagged=True)
        _logger.info("raqib m2: KB scope auto-tagging -> %s", stats)
