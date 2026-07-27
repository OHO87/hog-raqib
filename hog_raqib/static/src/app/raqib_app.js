/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { startWebClient } from "@web/start";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { useService } from "@web/core/utils/hooks";

// أزرار النتيجة — نقرة واحدة لكل بند
const RESULT_BTNS = [
    { key: "conform", label: "مطابق", icon: "fa-check", cls: "ok" },
    { key: "class3", label: "تصنيف 3", icon: "fa-exclamation-triangle", cls: "warn" },
    { key: "class4", label: "تصنيف 4", icon: "fa-lightbulb-o", cls: "warn" },
    { key: "nc_minor", label: "صغرى", icon: "fa-times-circle-o", cls: "bad" },
    { key: "nc_major", label: "كبرى", icon: "fa-times-circle", cls: "bad" },
    { key: "na", label: "لا ينطبق", icon: "fa-ban", cls: "muted" },
];

// أقسام قاعدة المعرفة
const KB_KINDS = [
    { key: "evidence", label: "أدلة مطابقة", icon: "fa-check", cls: "ok" },
    { key: "ofi", label: "فرص تحسين", icon: "fa-lightbulb-o", cls: "warn" },
    { key: "nc", label: "مخالفات سابقة", icon: "fa-flag-o", cls: "bad" },
];

export class RaqibAppRoot extends Component {
    static template = "hog_raqib.RaqibAppRoot";
    static components = { MainComponentsContainer };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.resultBtns = RESULT_BTNS;
        this.kbKinds = KB_KINDS;
        this.state = useState({
            loading: true,
            view: "home", // home | new | audit
            user_name: "",
            is_manager: false,
            kpis: null,
            audits: [],
            clients: [],
            standards: [],
            // شاشة التدقيق
            audit: null,   // header
            lines: [],
            findings: [],
            resultLabels: {},
            filter: "all", // all | pending | done | findings
            openLine: false,
            kb: { evidence: [], ofi: [], nc: [] },
            kbFor: 0,
            kbTab: "evidence",
            kbLoading: false,
            kbEdit: null, // {exId, lineId, textEn, fields: [{label, value}]}
            tab: "lines",  // lines | findings | summary
            // إنشاء سريع
            form: { name: "", client_id: 0, client_name: "", standard_id: 0,
                    audit_type: "stage1" },
            saving: false,
        });
        onWillStart(() => this.loadHome());
    }

    _err(e) {
        this.notification.add(e?.data?.message || e?.message || "حدث خطأ.",
            { type: "danger" });
    }

    // ------------------------------------------------------------- الرئيسية
    async loadHome() {
        this.state.loading = true;
        try {
            const res = await this.orm.call("raqib.audit", "raqib_app_home", []);
            Object.assign(this.state, {
                user_name: res.user_name,
                is_manager: res.is_manager,
                kpis: res.kpis,
                audits: res.audits,
                clients: res.clients,
                standards: res.standards,
            });
        } catch (e) {
            this._err(e);
        } finally {
            this.state.loading = false;
        }
    }

    goHome() {
        this.state.view = "home";
        this.state.audit = null;
        this.loadHome();
    }

    // --------------------------------------------------------- إنشاء سريع
    openNew() {
        this.state.form = { name: "", client_id: 0, client_name: "",
                            standard_id: this.state.standards[0]?.id || 0,
                            audit_type: "stage1" };
        this.state.view = "new";
    }

    async createAudit() {
        const f = this.state.form;
        if (!f.name || (!f.client_id && !f.client_name) || !f.standard_id) {
            this.notification.add("أكمل: رقم الزيارة، العميل، والمواصفة.",
                { type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            const id = await this.orm.call(
                "raqib.audit", "raqib_app_quick_create", [{
                    name: f.name,
                    client_id: f.client_id || false,
                    client_name: f.client_name,
                    standard_id: f.standard_id,
                    audit_type: f.audit_type,
                }]);
            await this.openAudit(id);
        } catch (e) {
            this._err(e);
        } finally {
            this.state.saving = false;
        }
    }

    // ----------------------------------------------------------- التدقيق
    async openAudit(id) {
        this.state.loading = true;
        try {
            const res = await this.orm.call("raqib.audit", "raqib_app_audit",
                [[id]]);
            this.state.audit = res.header;
            this.state.lines = res.lines;
            this.state.findings = res.findings;
            this.state.resultLabels = res.result_labels;
            this.state.filter = "all";
            this.state.tab = "lines";
            this.state.openLine = false;
            this.state.view = "audit";
        } catch (e) {
            this._err(e);
        } finally {
            this.state.loading = false;
        }
    }

    get filteredLines() {
        const f = this.state.filter;
        if (f === "pending") {
            return this.state.lines.filter((l) => l.result === "pending");
        }
        if (f === "done") {
            return this.state.lines.filter((l) => l.result !== "pending");
        }
        if (f === "findings") {
            return this.state.lines.filter((l) => l.finding_number);
        }
        return this.state.lines;
    }

    toggleLine(id) {
        this.state.openLine = this.state.openLine === id ? false : id;
        if (this.state.openLine) {
            this.loadKb(id);
        }
    }

    // ------------------------------------------------- قاعدة المعرفة
    async loadKb(lineId) {
        this.state.kbFor = lineId;
        this.state.kbTab = "evidence";
        this.state.kb = { evidence: [], ofi: [], nc: [] };
        this.state.kbEdit = null;
        this.state.kbLoading = true;
        try {
            this.state.kb = await this.orm.call(
                "raqib.audit", "raqib_app_kb", [lineId]);
        } catch (e) {
            this._err(e);
        } finally {
            this.state.kbLoading = false;
        }
    }

    kbCount(kind) {
        return (this.state.kb[kind] || []).length;
    }

    // أقواس [..] القابلة للتصحيح (نستثني وسم الشدة صغرى/كبرى)
    _placeholders(text) {
        const out = [];
        const re = /\[([^\]]*)\]/g;
        let m;
        while ((m = re.exec(text || ""))) {
            if (m[1] === "صغرى" || m[1] === "كبرى") { continue; }
            out.push(m[1]);
        }
        return out;
    }

    // هل محتوى القوس قائمة أمثلة؟ (مثل: / e.g.)
    _listPrefix(s) {
        const m = /^\s*(e\.g\.:?|مثل:?|مثال:?)\s*/i.exec(s || "");
        return m ? m[0] : null;
    }

    _splitItems(s) {
        return (s || "").split(/[،,]/).map((x) => x.trim()).filter(Boolean);
    }

    useExample(line, ex) {
        const enParts = this._placeholders(ex.text_en);
        if (!enParts.length) {
            this._appendNote(line, ex.text_en);
            return;
        }
        const arParts = this._placeholders(ex.text_ar);
        this.state.kbEdit = {
            exId: ex.id,
            lineId: line.id,
            textEn: ex.text_en,
            fields: enParts.map((p, i) => {
                const ar = arParts[i] || p;
                const enPrefix = this._listPrefix(p);
                if (enPrefix) {
                    const enItems = this._splitItems(p.slice(enPrefix.length));
                    const arContent = this._listPrefix(ar)
                        ? ar.slice(this._listPrefix(ar).length) : ar;
                    const arItems = this._splitItems(arContent);
                    return {
                        type: "list",
                        original: p,
                        items: enItems.map((en, j) => ({
                            en, ar: arItems[j] || en, checked: false,
                        })),
                        customInput: "",
                    };
                }
                return { type: "text", label: ar, value: p };
            }),
        };
    }

    addKbCustomItem(f) {
        const v = (f.customInput || "").trim();
        if (!v) { return; }
        f.items.push({ en: v, ar: v, checked: true, custom: true });
        f.customInput = "";
    }

    cancelKbEdit() {
        this.state.kbEdit = null;
    }

    confirmKbEdit(line) {
        const edit = this.state.kbEdit;
        if (!edit) { return; }
        let i = 0;
        const finalText = edit.textEn.replace(/\[([^\]]*)\]/g, (full, inner) => {
            if (inner === "صغرى" || inner === "كبرى") { return full; }
            const f = edit.fields[i++];
            if (f.type === "list") {
                const picked = f.items.filter((it) => it.checked)
                    .map((it) => it.en);
                return picked.length ? picked.join(", ") : f.original;
            }
            return f.value;
        });
        this.state.kbEdit = null;
        this._appendNote(line, finalText);
    }

    async _appendNote(line, text) {
        try {
            const note = await this.orm.call(
                "raqib.audit", "raqib_app_append_note", [line.id, text]);
            line.note = note;
            this.notification.add("أُدرجت النقطة في ملاحظة المدقق.",
                { type: "success" });
        } catch (e) {
            this._err(e);
        }
    }

    async setResult(line, result) {
        await this._saveLine(line, { result });
    }

    async saveLineField(line, field, value) {
        await this._saveLine(line, { [field]: value });
    }

    async _saveLine(line, vals) {
        try {
            const res = await this.orm.call("raqib.audit",
                "raqib_app_set_line", [line.id, vals]);
            if ("result" in vals) {
                line.result = res.result;
            }
            Object.assign(line, {
                finding_number: res.finding_number,
            }, vals.result ? {} : vals);
            this.state.findings = res.findings;
            this.state.audit.progress = res.progress;
            this.state.audit.findings = res.findings_count;
            this.state.audit.client_action_label = res.client_action_label;
        } catch (e) {
            this._err(e);
        }
    }

    resultLabel(key) {
        return this.state.resultLabels[key] || key;
    }

    resultCls(r) {
        if (r === "conform") { return "ok"; }
        if (r === "class3" || r === "class4") { return "warn"; }
        if (r === "nc_minor" || r === "nc_major") { return "bad"; }
        if (r === "na") { return "muted"; }
        return "pending";
    }

    // ------------------------------------------------------------ الخلاصة
    async saveAuditField(field, value) {
        try {
            await this.orm.call("raqib.audit", "raqib_app_set_audit",
                [[this.state.audit.id], { [field]: value }]);
        } catch (e) {
            this._err(e);
        }
    }

    async pickReport(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const b64 = await new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(r.result.split(",")[1]);
            r.onerror = reject;
            r.readAsDataURL(file);
        });
        try {
            this.state.saving = true;
            const url = await this.orm.call("raqib.audit",
                "raqib_app_fill_report",
                [[this.state.audit.id], file.name, b64]);
            this.notification.add("تم توليد التقرير.", { type: "success" });
            if (url) { window.open(url, "_blank"); }
        } catch (e) {
            this._err(e);
        } finally {
            this.state.saving = false;
            ev.target.value = "";
        }
    }
}

startWebClient(RaqibAppRoot);
