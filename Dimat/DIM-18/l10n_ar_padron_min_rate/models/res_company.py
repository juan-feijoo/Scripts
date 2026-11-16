from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_arba_wth_min_enabled = fields.Boolean(
        string="Aplicar alícuota mínima retención ARBA",
        default=False,
        help="Aplica la regla de piso mínimo de retención IIBB ARBA (por ejemplo RN 42/12 droguerías).",
    )
    l10n_ar_arba_wth_min_rate = fields.Float(
        string="Alícuota mínima retención ARBA (%)",
        digits=(6, 2),
        default=2.50,
        help="Porcentaje mínimo a aplicar cuando la retención ARBA obtenida sea inferior (p. ej. 2,50%).",
    )
    l10n_ar_arba_wth_exclude_zero = fields.Boolean(
        string="Mantener alícuota 0% sin mínimo",
        default=True,
        help="Si el contribuyente tiene 0,00% en ARBA, no se aplica el mínimo (solo aplica a alícuotas > 0%).",
    )
    l10n_ar_arba_wth_apply_if_absent = fields.Boolean(
        string="Aplicar mínimo si no figura en padrón",
        default=False,
        help="Si está activo, aplica la alícuota mínima también cuando el CUIT no figura en el padrón ARBA.",
    )
    l10n_ar_arba_wth_source = fields.Selection(
        [
            ("padron", "Archivo de padrón (ZIP)"),
            ("arba", "Webservice ARBA (con contingencia padrón)"),
        ],
        string="Fuente de alícuotas ARBA (Retenciones)",
        default="padron",
        required=True,
        help="Define el método asignado automáticamente en la Posición Fiscal para retenciones IIBB Buenos Aires.",
    )
    l10n_ar_arba_wth_default_tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto plantilla Retención ARBA (0%)",
        domain="[('company_id', '=', id), ('l10n_ar_withholding_payment_type', '=', 'supplier'), ('amount_type', 'in', ('percent', 'division'))]",
        help="Impuesto base de proveedor utilizado para calcular no inscriptos y clonar nuevas alícuotas.",
    )
    l10n_ar_padron_auto_prepare_taxes = fields.Boolean(
        string="Preparar impuestos automáticamente al cargar ZIP ARBA",
        default=True,
        help="Escanea las alícuotas del archivo Ret al subir un padrón de Buenos Aires y crea los account.tax faltantes.",
    )
    l10n_ar_padron_notify_new_taxes = fields.Boolean(
        string="Notificar nuevas alícuotas o alertas del ZIP",
        default=True,
        help="Registra aviso en el chatter y programa notificación/actividad si se crean nuevos impuestos o hay alertas.",
    )
    l10n_ar_padron_notify_user_id = fields.Many2one(
        "res.users",
        string="Responsable a notificar (Padrón ARBA)",
        help="Usuario que recibirá la notificación/actividad cuando aparezcan alícuotas nuevas o alertas en el padrón.",
    )

    @api.constrains("l10n_ar_arba_wth_min_rate")
    def _check_arba_wth_min_rate(self):
        for company in self:
            if company.l10n_ar_arba_wth_min_rate < 0.0 or company.l10n_ar_arba_wth_min_rate > 100.0:
                raise ValidationError(_("La alícuota mínima de retención ARBA debe estar entre 0% y 100%."))

    def _get_arba_wth_default_tax(self):
        """Localiza (y desarchiva si hace falta) el impuesto plantilla 0% de retención ARBA."""
        self.ensure_one()
        ba_state = self.env.ref("base.state_ar_b", raise_if_not_found=False)
        if not ba_state:
            return self.env["account.tax"]

        tax = self.l10n_ar_arba_wth_default_tax_id
        if tax and tax.company_id == self and tax.l10n_ar_withholding_payment_type == "supplier":
            if not tax.active:
                tax.active = True
            return tax

        Tax = self.env["account.tax"].with_context(active_test=False)
        domain = [
            ("company_id", "=", self.id),
            ("l10n_ar_withholding_payment_type", "=", "supplier"),
            ("l10n_ar_state_id", "=", ba_state.id),
            ("amount_type", "in", ("percent", "division")),
        ]
        tax = Tax.search(domain + [("amount", "=", 0.0)], limit=1)
        if not tax:
            tax = Tax.search(domain, order="amount asc, id asc", limit=1)
        if tax:
            if not tax.active:
                tax.active = True
            if not self.l10n_ar_arba_wth_default_tax_id:
                self.l10n_ar_arba_wth_default_tax_id = tax
        return tax

    def _apply_arba_min_withholding_rate(self, rate):
        """Aplica la regla parametrizable de mínimo ARBA; devuelve (tasa_ajustada, nota_auditoria)."""
        self.ensure_one()
        if not self.l10n_ar_arba_wth_min_enabled or self.l10n_ar_arba_wth_min_rate <= 0.0:
            return rate, False

        min_rate = round(float(self.l10n_ar_arba_wth_min_rate), 4)
        if rate is None:
            if self.l10n_ar_arba_wth_apply_if_absent:
                return min_rate, _("ausente -> %.2f%%") % min_rate
            return None, False

        numeric_rate = round(float(rate), 4)
        if numeric_rate == 0.0 and self.l10n_ar_arba_wth_exclude_zero:
            return 0.0, False
        if numeric_rate < min_rate:
            return min_rate, _("%.2f%% -> %.2f%%") % (numeric_rate, min_rate)
        return numeric_rate, False

    def _ensure_arba_wth_fiscal_position(self):
        """Asegura Posición Fiscal RI auto-aplicable con regla de retención ARBA."""
        self.ensure_one()
        default_tax = self._get_arba_wth_default_tax()
        ar_country = self.env.ref("base.ar", raise_if_not_found=False)
        ri_resp = self.env.ref("l10n_ar.res_IVARI", raise_if_not_found=False)
        if not default_tax or not ar_country or not ri_resp:
            return {
                "fpos": self.env["account.fiscal.position"],
                "line": self.env["account.fiscal.position.l10n_ar_tax"],
                "default_tax": default_tax,
                "fp_created": False,
                "line_created": False,
            }

        FiscalPos = self.env["account.fiscal.position"].with_company(self)
        candidate_fps = FiscalPos.search(
            [
                ("company_id", "=", self.id),
                ("auto_apply", "=", True),
                ("l10n_ar_afip_responsibility_type_ids", "in", ri_resp.ids),
                "|",
                ("country_id", "=", ar_country.id),
                ("country_id", "=", False),
            ],
            order="sequence asc, id asc",
        )

        # Priorizar FP existente que ya tenga una línea de retención ARBA del mismo grupo/jurisdicción
        existing_line = self.env["account.fiscal.position.l10n_ar_tax"]
        target_fp = self.env["account.fiscal.position"]
        for fp in candidate_fps:
            matching = fp.l10n_ar_tax_ids.filtered(
                lambda x: x.tax_type == "withholding"
                and x.default_tax_id.tax_group_id == default_tax.tax_group_id
                and x.default_tax_id.l10n_ar_state_id == default_tax.l10n_ar_state_id
            )
            if matching:
                target_fp = fp
                existing_line = matching[:1]
                break

        fp_created = False
        line_created = False
        if not target_fp:
            target_fp = candidate_fps[:1]
        if not target_fp:
            target_fp = FiscalPos.create(
                {
                    "name": _("Retenciones ARBA - Resp. Inscripto"),
                    "company_id": self.id,
                    "auto_apply": True,
                    "sequence": 10,
                    "country_id": ar_country.id,
                    "l10n_ar_afip_responsibility_type_ids": [(6, 0, [ri_resp.id])],
                }
            )
            fp_created = True

        source = self.l10n_ar_arba_wth_source or "padron"
        if not existing_line:
            existing_line = self.env["account.fiscal.position.l10n_ar_tax"].create(
                {
                    "fiscal_position_id": target_fp.id,
                    "tax_type": "withholding",
                    "default_tax_id": default_tax.id,
                    "webservice": source,
                }
            )
            line_created = True
        else:
            updates = {}
            if existing_line.default_tax_id != default_tax:
                updates["default_tax_id"] = default_tax.id
            if existing_line.webservice != source:
                updates["webservice"] = source
            if updates:
                existing_line.write(updates)

        return {
            "fpos": target_fp,
            "line": existing_line,
            "default_tax": default_tax,
            "fp_created": fp_created,
            "line_created": line_created,
        }

    def action_auto_configure_arba_wth(self):
        """Configura Posición Fiscal RI e impuesto plantilla ARBA de retenciones para cada compañía."""
        results = {}
        for company in self:
            if company.country_id.code != "AR":
                continue
            results[company.id] = company._ensure_arba_wth_fiscal_position()
        return results

    def _notify_padron_event(self, title, body_html, record=None, schedule_activity=False):
        """Publica aviso en chatter (del padrón vigente o nuevo) y programa actividad si está parametrizado."""
        self.ensure_one()
        if not self.l10n_ar_padron_notify_new_taxes:
            return
        target = record
        if not target:
            ba_state = self.env.ref("base.state_ar_b", raise_if_not_found=False)
            if ba_state:
                today = fields.Date.context_today(self)
                target = self.env["res.company.jurisdiction.padron"].search(
                    [
                        ("company_id", "=", self.id),
                        ("state_id", "=", ba_state.id),
                        "|",
                        ("l10n_ar_padron_from_date", "=", False),
                        ("l10n_ar_padron_from_date", "<=", today),
                        "|",
                        ("l10n_ar_padron_to_date", "=", False),
                        ("l10n_ar_padron_to_date", ">=", today),
                    ],
                    order="id desc",
                    limit=1,
                )
        if not target:
            return

        notify_user = self.l10n_ar_padron_notify_user_id
        partner_ids = notify_user.partner_id.ids if notify_user and notify_user.partner_id else []
        target.message_post(
            body=Markup(body_html),
            subject=title,
            partner_ids=partner_ids,
            subtype_xmlid="mail.mt_note",
        )
        if schedule_activity and notify_user:
            target.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=title,
                note=Markup(body_html),
                user_id=notify_user.id,
            )
