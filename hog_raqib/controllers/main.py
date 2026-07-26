# -*- coding: utf-8 -*-
"""تطبيق رقيب المستقل على /raqib — نفس نمط حكيم (مسار 2)."""
import json
from markupsafe import Markup
from odoo import http
from odoo.http import request


class RaqibApp(http.Controller):

    @http.route("/raqib", type="http", auth="user", website=False)
    def raqib_app(self, **kw):
        session_info = request.env["ir.http"].session_info()
        return request.render("hog_raqib.index", {
            "session_info": Markup(json.dumps(session_info)),
        }, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
