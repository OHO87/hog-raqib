# -*- coding: utf-8 -*-
from . import controllers
from . import models
from . import wizard

from .models.raqib_clause_scope import apply_scope


def post_init_hook(env):
    """تطبيق مصفوفة نطاق الزيارات على البنود بعد تركيب نظيف.

    ملفات البيانات محمّلة بـnoupdate="1" ولا تحمل الأعلام؛ مصدر الحقيقة
    الوحيد هو models/raqib_clause_scope.py — يُطبَّق هنا وفي الترحيل.
    """
    apply_scope(env)
