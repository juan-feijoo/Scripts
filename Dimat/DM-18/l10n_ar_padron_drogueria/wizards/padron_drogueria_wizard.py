# -*- coding: utf-8 -*-
import base64
import calendar
import io
import logging
import re
import zipfile
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PadronDrogueriaWizard(models.TransientModel):
    _name = "padron.drogueria.wizard"
    _description = "Asistente de Importación Padrón ARBA (Droguerías RN 42/12)"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    file_padron = fields.Binary(
        string="Archivo Padrón ARBA (.ZIP)",
        required=True,
        help="Suba el archivo ZIP original descargado de la web de ARBA (ej. PadronRGS112026.zip)."
    )
    filename = fields.Char(string="Nombre de Archivo")
    from_date = fields.Date(
        string="Vigencia Desde",
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    to_date = fields.Date(
        string="Vigencia Hasta",
        required=True,
        default=lambda self: fields.Date.today().replace(
            day=calendar.monthrange(fields.Date.today().year, fields.Date.today().month)[1]
        ),
    )
    min_retention_aliquot = fields.Float(
        string="Piso Retención Droguerías (%)",
        required=True,
        default=lambda self: self.env.company.l10n_ar_drogueria_min_retention or 2.50,
        help="Alícuota mínima legal exigida a droguerías según RN 42/12 de ARBA."
    )
    auto_assign_country = fields.Boolean(
        string="Asignar Argentina a contactos sin país",
        default=True,
        help="Asegura que los contactos con CUIT tengan asignado el país Argentina para permitir la autodetección de la Posición Fiscal."
    )

    @api.onchange("filename")
    def _onchange_filename(self):
        """Auto-detectar mes y año desde el nombre de archivo (ej. PadronRGS112026.zip)"""
        if not self.filename:
            return
        match = re.search(r"(\d{2})(\d{4})", self.filename)
        if match:
            month = int(match.group(1))
            year = int(match.group(2))
            if 1 <= month <= 12 and 2000 <= year <= 2100:
                last_day = calendar.monthrange(year, month)[1]
                self.from_date = date(year, month, 1)
                self.to_date = date(year, month, last_day)

    def action_process_padron(self):
        self.ensure_one()
        if not self.file_padron:
            raise UserError(_("Por favor seleccione un archivo ZIP del padrón de ARBA."))

        try:
            zip_bytes = base64.b64decode(self.file_padron)
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        except Exception as e:
            raise UserError(_("El archivo proporcionado no es un archivo ZIP válido: %s") % str(e))

        # 1. Localizar archivo de Retenciones dentro del ZIP
        ret_filename = None
        for name in zf.namelist():
            if "ret" in name.lower() and name.lower().endswith((".txt", ".csv")):
                ret_filename = name
                break

        if not ret_filename:
            raise UserError(_("No se encontró el archivo de Retenciones ('PadronRGSRet...') dentro del ZIP."))

        # 2. Cargar contactos de Odoo con CUIT
        Partner = self.env["res.partner"]
        ar_country = self.env.ref("base.ar")
        partners = Partner.search([
            ("is_company", "=", True),
            ("vat", "!=", False)
        ])

        cuit_map = {}
        for p in partners:
            clean_vat = re.sub(r"\D", "", p.vat or "")
            if len(clean_vat) == 11:
                cuit_map[clean_vat] = p

        if not cuit_map:
            raise UserError(_("No se encontraron contactos comerciales con CUIT de 11 dígitos en el sistema."))

        # Auto-asignar país si está habilitado
        if self.auto_assign_country:
            partners_to_fix = [p for p in cuit_map.values() if not p.country_id]
            if partners_to_fix:
                Partner.browse([p.id for p in partners_to_fix]).write({"country_id": ar_country.id})

        # 3. Leer y procesar padrón en streaming de memoria
        ret_data = {}  # cuit -> (ali_final, ali_orig, rule_applied)
        with zf.open(ret_filename) as f:
            for line_bytes in f:
                line = line_bytes.decode("latin1", errors="replace").rstrip("\r\n")
                if not line:
                    continue
                parts = line.split(";")
                if len(parts) >= 9:
                    cuit = parts[4]
                    if cuit in cuit_map:
                        try:
                            ali_orig = float(parts[8].replace(",", "."))
                        except ValueError:
                            ali_orig = 0.0

                        # Aplicación de Regla Droguerías (RN 42/12)
                        if 0.0 < ali_orig < self.min_retention_aliquot:
                            ali_final = self.min_retention_aliquot
                            rule_applied = True
                        else:
                            ali_final = ali_orig
                            rule_applied = False

                        ret_data[cuit] = (ali_final, ali_orig, rule_applied)

        # Filtrar contactos que requieren retención (> 0%)
        pasibles = {cuit: vals for cuit, vals in ret_data.items() if vals[0] > 0}

        if not pasibles:
            raise UserError(_("No se encontraron contactos pasibles de retención con alícuota mayor a 0%."))

        # 4. Asegurar impuestos en account.tax
        ba_state = self.env.ref("base.state_ar_b")
        base_tax = self.env["account.tax"].search([
            ("company_id", "=", self.company_id.id),
            ("l10n_ar_withholding_payment_type", "=", "supplier"),
            ("l10n_ar_state_id", "=", ba_state.id),
            ("amount", "=", 0.0)
        ], limit=1)

        if not base_tax:
            base_tax = self.env["account.tax"].search([
                ("company_id", "=", self.company_id.id),
                ("l10n_ar_withholding_payment_type", "=", "supplier"),
                ("l10n_ar_state_id", "=", ba_state.id)
            ], limit=1)

        if not base_tax:
            raise UserError(_("No se encontró un impuesto plantilla de retención para Buenos Aires en account.tax."))

        distinct_rates = set(v[0] for v in pasibles.values())
        tax_by_rate = {}
        Tax = self.env["account.tax"].with_context(active_test=False)

        for rate in distinct_rates:
            domain = [
                ("company_id", "=", self.company_id.id),
                ("l10n_ar_withholding_payment_type", "=", "supplier"),
                ("l10n_ar_state_id", "=", ba_state.id),
                ("amount", "=", rate)
            ]
            tax = Tax.search(domain, limit=1)
            if not tax:
                new_name = f"IIBB WTH BA {rate}%"
                tax = base_tax.copy(default={
                    "sequence": 10,
                    "amount": rate,
                    "active": True,
                    "name": new_name,
                })
            elif not tax.active:
                tax.active = True
            tax_by_rate[rate] = tax

        # 5. Asignar en l10n_ar.partner.tax
        PartnerTax = self.env["l10n_ar.partner.tax"]
        created_count = 0
        updated_count = 0
        rule_boosted_count = 0
        prev_closed_count = 0

        one_day_before = fields.Date.subtract(self.from_date, days=1)

        for cuit, (ali_final, ali_orig, rule_applied) in pasibles.items():
            partner = cuit_map[cuit]
            target_tax = tax_by_rate[ali_final]

            if rule_applied:
                rule_boosted_count += 1
                ref_text = f"ARBA RN 42/12 Droguerías (Orig: {ali_orig}%) - {self.from_date.strftime('%m/%Y')}"
            else:
                ref_text = f"ARBA RN 42/12 - {self.from_date.strftime('%m/%Y')}"

            existing_taxes = PartnerTax.search([
                ("partner_id", "=", partner.id),
                ("tax_id.tax_group_id", "=", target_tax.tax_group_id.id),
                ("tax_id.l10n_ar_state_id", "=", ba_state.id),
                ("tax_id.l10n_ar_withholding_payment_type", "=", "supplier")
            ])

            exact_record = existing_taxes.filtered(
                lambda r: r.from_date == self.from_date and r.to_date == self.to_date
            )

            if exact_record:
                exact_record.write({
                    "tax_id": target_tax.id,
                    "ref": ref_text
                })
                updated_count += 1
            else:
                # Cerrar registros abiertos previos que se solapan
                overlapping = existing_taxes.filtered(
                    lambda r: (not r.to_date or r.to_date >= self.from_date) and (not r.from_date or r.from_date < self.from_date)
                )
                if overlapping:
                    overlapping.write({"to_date": one_day_before})
                    prev_closed_count += len(overlapping)

                PartnerTax.create({
                    "partner_id": partner.id,
                    "tax_id": target_tax.id,
                    "from_date": self.from_date,
                    "to_date": self.to_date,
                    "ref": ref_text,
                    "company_id": self.company_id.id
                })
                created_count += 1

        message = _(
            "Padrón procesado exitosamente para el período %(period)s:\n\n"
            "• Total contactos pasibles configurados: %(total)s\n"
            "• Asignaciones nuevas creadas: %(created)s\n"
            "• Asignaciones actualizadas: %(updated)s\n"
            "• Contactos ajustados por Regla Droguerías (piso %(min_ali)s%%): %(boosted)s\n"
            "• Vigencias anteriores cerradas: %(closed)s",
            period=f"{self.from_date} al {self.to_date}",
            total=len(pasibles),
            created=created_count,
            updated=updated_count,
            boosted=rule_boosted_count,
            min_ali=self.min_retention_aliquot,
            closed=prev_closed_count
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Importación ARBA Finalizada"),
                "message": message,
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
