from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ar_arba_wth_min_enabled = fields.Boolean(
        related="company_id.l10n_ar_arba_wth_min_enabled",
        readonly=False,
    )
    l10n_ar_arba_wth_min_rate = fields.Float(
        related="company_id.l10n_ar_arba_wth_min_rate",
        readonly=False,
    )
    l10n_ar_arba_wth_exclude_zero = fields.Boolean(
        related="company_id.l10n_ar_arba_wth_exclude_zero",
        readonly=False,
    )
    l10n_ar_arba_wth_apply_if_absent = fields.Boolean(
        related="company_id.l10n_ar_arba_wth_apply_if_absent",
        readonly=False,
    )
    l10n_ar_arba_wth_source = fields.Selection(
        related="company_id.l10n_ar_arba_wth_source",
        readonly=False,
    )
    l10n_ar_arba_wth_default_tax_id = fields.Many2one(
        related="company_id.l10n_ar_arba_wth_default_tax_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('l10n_ar_withholding_payment_type', '=', 'supplier'), ('amount_type', 'in', ('percent', 'division'))]",
    )
    l10n_ar_padron_auto_prepare_taxes = fields.Boolean(
        related="company_id.l10n_ar_padron_auto_prepare_taxes",
        readonly=False,
    )
    l10n_ar_padron_notify_new_taxes = fields.Boolean(
        related="company_id.l10n_ar_padron_notify_new_taxes",
        readonly=False,
    )
    l10n_ar_padron_notify_user_id = fields.Many2one(
        related="company_id.l10n_ar_padron_notify_user_id",
        readonly=False,
    )

    def action_auto_configure_arba_wth_from_settings(self):
        """Aplica la configuración automática de FP + impuesto plantilla ARBA y sincroniza padrón vigente."""
        self.ensure_one()
        self.execute()
        company = self.company_id
        res = company.action_auto_configure_arba_wth().get(company.id, {})
        created_count = 0
        ba_state = self.env.ref("base.state_ar_b", raise_if_not_found=False)
        if ba_state:
            padrons = self.env["res.company.jurisdiction.padron"].search(
                [
                    ("company_id", "=", company.id),
                    ("state_id", "=", ba_state.id),
                    ("file_padron", "!=", False),
                ]
            )
            if padrons:
                sync_res = padrons.with_company(company).action_sync_taxes_from_padron()
                created_count = sum(len(item["created_taxes"]) for item in sync_res.values())

        fpos = res.get("fpos")
        if fpos:
            notif_type = "success"
            msg = _(
                "Posición Fiscal '%s' configurada (%s) con plantilla '%s'. "
                "Impuestos nuevos creados desde padrón ZIP: %d."
            ) % (
                fpos.display_name,
                res["line"].webservice,
                res["default_tax"].display_name,
                created_count,
            )
        else:
            notif_type = "warning"
            msg = _("No se encontró impuesto plantilla 0% de retención proveedor Buenos Aires para esta compañía.")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Retenciones ARBA"),
                "message": msg,
                "type": notif_type,
                "sticky": False,
            },
        }
