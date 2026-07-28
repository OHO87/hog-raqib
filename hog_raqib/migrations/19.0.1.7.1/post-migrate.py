# -*- coding: utf-8 -*-
"""إعادة وسم قاعدة المعرفة بعد تصحيح مطابقة المؤشرات العربية.

المصنّف في 19.0.1.7.0 كان يطابق السلاسل خاماً، فـ«عينة» تطابق داخل
«معيَّنة» و«تتبع» داخل «تتبعية» — أي إخفاء نقاط مشروعة في المرحلة الأولى.
صار المطابقة بحدود كلمات عربية صريحة. نعيد الوسم **كاملاً** لأن كل
التصنيفات الحالية آلية (لم يمر عليها تصنيف يدوي بعد).

بعد هذه النسخة استخدم ``raqib_kb_autotag_scope(only_untagged=True)`` فقط،
حتى لا يُدهس أي تصنيف يدوي.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

KB_MODEL = "x_raqib.kb.example"
KB_SCOPE_FIELD = "x_stage_scope"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if KB_MODEL not in env or KB_SCOPE_FIELD not in env[KB_MODEL]._fields:
        _logger.info("raqib m2.1: KB scope field absent — nothing to retag.")
        return
    stats = env["raqib.audit"].raqib_kb_autotag_scope(only_untagged=False)
    _logger.info("raqib m2.1: KB scope full retag -> %s", stats)
