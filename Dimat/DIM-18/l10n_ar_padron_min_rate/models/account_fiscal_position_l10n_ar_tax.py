import logging
from markupsafe import Markup, escape

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountFiscalPositionL10nArTax(models.Model):
    _inherit = "account.fiscal.position.l10n_ar_tax"

    def _apply_arba_withholding_rule_if_needed(self, aliquot, ref):
        """Aplica la alícuota mínima de compañía solo en retenciones ARBA (jurisdicción 902)."""
        self.ensure_one()
        state = self.default_tax_id.l10n_ar_state_id
        if self.tax_type != "withholding" or not state or state.jurisdiction_code != "902":
            return aliquot, ref

        company = self.fiscal_position_id.company_id
        adjusted, note = company._apply_arba_min_withholding_rate(aliquot)
        if note:
            suffix = "[RN 42/12: %s]" % note
            ref = "%s %s" % (ref, suffix) if ref else suffix
        return adjusted, ref

    def _ensure_tax(self, rate):
        """Redondea alícuota y notifica en el padrón si se crea automáticamente un account.tax nuevo."""
        self.ensure_one()
        normalized_rate = round(float(rate), 4)
        domain = self._get_tax_domain()
        pre_existing = (
            self.env["account.tax"]
            .with_context(active_test=False)
            .search(domain + [("amount", "=", normalized_rate)], limit=1)
        )
        tax = super()._ensure_tax(normalized_rate)
        if not pre_existing and tax and not self.env.context.get("skip_single_tax_notify"):
            company = self.fiscal_position_id.company_id
            if company.l10n_ar_padron_notify_new_taxes:
                company._notify_padron_event(
                    _("Nuevo impuesto creado automáticamente desde padrón/ARBA"),
                    Markup(
                        _(
                            "<p>Se creó automáticamente el impuesto <b>%s</b> (alícuota <b>%.2f%%</b>) "
                            "a partir de la plantilla <b>%s</b>.</p>"
                        )
                    )
                    % (escape(tax.display_name), tax.amount, escape(self.default_tax_id.display_name)),
                    schedule_activity=bool(company.l10n_ar_padron_notify_user_id),
                )
        return tax

    def _get_padron_data(self, partner, date, to_date):
        """Lee Per y Ret en forma independiente para ARBA (902) y aplica regla de mínimo parametrizable."""
        self.ensure_one()
        state = self.default_tax_id.l10n_ar_state_id
        if not state or state.jurisdiction_code != "902":
            return super()._get_padron_data(partner, date, to_date)

        padron_file = self._search_padron_file(state, date)
        if not padron_file:
            if self.webservice != "padron":
                return None, None
            raise UserError(
                _(
                    "No hay padrón subido para la fecha indicada %s a %s. Debe subirlo en "
                    "'Contabilidad / Configuración / AFIP / Padrón de Alícuotas por compañía' o cargar "
                    "la alícuota manualmente en el contacto para el período en curso."
                )
                % (date, to_date)
            )

        detail = padron_file._get_arba_aliquots_detail(partner)
        if self.tax_type == "withholding":
            found = bool(detail["nro_ret"])
            raw_aliquot = detail["aliquot_ret"]
        else:
            found = bool(detail["nro_per"])
            raw_aliquot = detail["aliquot_per"]

        if found and raw_aliquot is not False:
            aliquot = float(str(raw_aliquot).replace(",", "."))
            ref = "Alícuota padrón ARBA (archivo importado)"
        else:
            aliquot = None
            ref = "Alícuota no inscripto ARBA (archivo importado)"

        return self._apply_arba_withholding_rule_if_needed(aliquot, ref)

    def _get_arba_data(self, partner, date, to_date):
        """Aplica la misma regla mínima ARBA también cuando el origen viene del Webservice SOAP."""
        self.ensure_one()
        state = self.default_tax_id.l10n_ar_state_id
        has_padron = bool(self._search_padron_file(state, date))
        aliquot, ref = super()._get_arba_data(partner, date, to_date)
        if not has_padron:
            aliquot, ref = self._apply_arba_withholding_rule_if_needed(aliquot, ref)
        return aliquot, ref
