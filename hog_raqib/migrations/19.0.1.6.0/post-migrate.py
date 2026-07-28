# -*- coding: utf-8 -*-
"""ترحيل قطاع EA من حقل Studio x_ea_code إلى ea_sector_ids المعرَّف في الكود.

الحقل القديم Selection نصي على raqib.client. الجديد Many2many إلى
raqib.ea.sector يدعم أكثر من رمز. لا نحذف القديم هنا — يُترك للمراجعة
اليدوية ثم يُزال من Studio بعد التأكد.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'raqib_client' AND column_name = 'x_ea_code'
    """)
    if not cr.fetchone():
        _logger.info("raqib: no x_ea_code on raqib_client - nothing to migrate.")
        return

    cr.execute("""
        SELECT id, x_ea_code FROM raqib_client
        WHERE x_ea_code IS NOT NULL AND x_ea_code <> ''
    """)
    rows = cr.fetchall()
    if not rows:
        _logger.info("raqib: no x_ea_code values to migrate.")
        return

    cr.execute("SELECT code, id FROM raqib_ea_sector")
    by_code = dict(cr.fetchall())

    migrated, missing = 0, []
    for client_id, code in rows:
        for raw in str(code).replace("،", ",").split(","):
            key = raw.strip()
            sector_id = by_code.get(key)
            if not sector_id:
                missing.append((client_id, key))
                continue
            cr.execute("""
                INSERT INTO raqib_client_ea_rel (client_id, sector_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (client_id, sector_id))
            migrated += 1

    _logger.info("raqib: migrated %s EA links for %s clients.",
                 migrated, len(rows))
    if missing:
        _logger.warning("raqib: unknown EA codes not migrated: %s", missing)
