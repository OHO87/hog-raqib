# -*- coding: utf-8 -*-
{
    "name": "رقيب — قمرة التدقيق",
    "summary": "قمرة تدقيق شهادات ISO متكاملة مع تقارير URS "
               "(Stage 1 / Stage 2) — أقل نقرات، بنود مرتبة حسب المواصفة، "
               "أدلة متوقعة وأمثلة جاهزة لكل بند.",
    "version": "19.0.1.7.0",
    "author": "HOG",
    "license": "LGPL-3",
    "category": "Services/Audit",
    "depends": ["base", "mail", "contacts"],
    "data": [
        "security/raqib_security.xml",
        "security/ir.model.access.csv",
        "data/raqib_ea_sectors.xml",
        "data/raqib_9001_standard.xml",
        "data/raqib_standards_extra.xml",
        "data/raqib_stage1_checklist.xml",
        "data/raqib_9001_clauses.xml",
        "data/raqib_14001_clauses.xml",
        "data/raqib_45001_clauses.xml",
        "views/raqib_clause_views.xml",
        "views/raqib_client_views.xml",
        "views/raqib_audit_views.xml",
        "views/raqib_finding_views.xml",
        "wizard/raqib_report_fill_views.xml",
        "views/raqib_menus.xml",
        "views/raqib_app_templates.xml",
    ],
    "assets": {
        "hog_raqib.assets": [
            ("include", "web.assets_backend"),
            # المُقلِع OWL المستقل (نفس نمط حكيم — مسار 2)
            "web/static/src/start.js",
            "hog_raqib/static/src/app/**/*.js",
            "hog_raqib/static/src/app/**/*.xml",
            "hog_raqib/static/src/app/**/*.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "application": True,
    "installable": True,
}
