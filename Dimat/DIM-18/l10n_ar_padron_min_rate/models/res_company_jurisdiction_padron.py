import base64
import io
import logging
import os
import re
import shutil
import zipfile
from markupsafe import Markup, escape

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResCompanyJurisdictionPadron(models.Model):
    _name = "res.company.jurisdiction.padron"
    _inherit = ["res.company.jurisdiction.padron", "mail.thread", "mail.activity.mixin"]
    _order = "l10n_ar_padron_from_date desc, id desc"

    l10n_ar_is_arba_padron = fields.Boolean(
        compute="_compute_l10n_ar_is_arba_padron",
        string="Es padrón ARBA",
    )
    l10n_ar_last_sync_date = fields.Datetime(
        string="Última sincronización",
        readonly=True,
        copy=False,
    )
    l10n_ar_detected_rates_summary = fields.Text(
        string="Alícuotas detectadas (Retenciones)",
        readonly=True,
        copy=False,
    )
    l10n_ar_created_taxes_summary = fields.Text(
        string="Impuestos preparados / creados",
        readonly=True,
        copy=False,
    )
    l10n_ar_sync_warnings = fields.Text(
        string="Observaciones y alertas del ZIP",
        readonly=True,
        copy=False,
    )

    @api.depends("state_id")
    def _compute_l10n_ar_is_arba_padron(self):
        for rec in self:
            rec.l10n_ar_is_arba_padron = bool(rec.state_id and rec.state_id.jurisdiction_code == "902")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("skip_padron_sync"):
            records._auto_prepare_arba_on_save()
        return records

    def write(self, vals):
        cache_breaking_fields = {"file_padron", "l10n_ar_padron_from_date", "l10n_ar_padron_to_date", "state_id"}
        if cache_breaking_fields.intersection(vals):
            self._clear_tmp_dir()
        res = super().write(vals)
        if "file_padron" in vals and not self.env.context.get("skip_padron_sync"):
            self._auto_prepare_arba_on_save()
        return res

    def unlink(self):
        self._clear_tmp_dir()
        return super().unlink()

    def _clear_tmp_dir(self):
        """Elimina los archivos extraídos en /tmp para evitar lecturas obsoletas al actualizar el ZIP."""
        for rec in self:
            if not rec.id or not rec.l10n_ar_padron_from_date or not rec.l10n_ar_padron_to_date:
                continue
            tmp_dir = rec._get_parp_tmp_dir()
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def descompress_file(self, file_padron, dest_dir="/tmp"):
        """Descomprime el ZIP en memoria sin dejar archivos temporales huérfanos en /tmp."""
        _logger.info("Decompressing padron zip file into %s", dest_dir)
        os.makedirs(dest_dir, exist_ok=True)
        raw = base64.b64decode(file_padron)
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zip_file:
            zip_file.extractall(path=dest_dir)

    def find_file(self, rootdir, type_code):
        """Busca Per/Ret incluso dentro de subcarpetas y devuelve la ruta relativa a rootdir."""
        if not rootdir or not os.path.exists(rootdir):
            return False

        code_low = (type_code or "").lower()
        date_tokens = []
        if self.l10n_ar_padron_from_date:
            d = self.l10n_ar_padron_from_date
            date_tokens = [f"{d.month:02d}{d.year}", f"{d.month}{d.year}"]

        fallback_rel = False
        for subdir, _dirs, files in os.walk(rootdir):
            for fname in sorted(files):
                fname_low = fname.lower()
                if code_low in fname_low and fname_low.endswith((".txt", ".csv")):
                    relpath = os.path.relpath(os.path.join(subdir, fname), rootdir)
                    if any(tok in fname_low for tok in date_tokens):
                        return relpath
                    if not fallback_rel:
                        fallback_rel = relpath
        return fallback_rel

    def find_aliquot(self, path, cuit):
        """Evita ejecutar grep con path inexistente o CUIT vacío, y normaliza CUIT con guiones."""
        if not cuit or not path or not os.path.exists(path):
            return False, False
        digits = re.sub(r"\D", "", str(cuit))
        normalized = digits if len(digits) == 11 else str(cuit).strip()
        if not normalized:
            return False, False
        return super().find_aliquot(path, normalized)

    def _ensure_arba_extracted(self):
        """Extrae el ZIP ARBA una sola vez por padrón/período en /tmp."""
        self.ensure_one()
        tmp_dir = self._get_parp_tmp_dir()
        has_files = os.path.isdir(tmp_dir) and any(files for _r, _d, files in os.walk(tmp_dir))
        if not has_files and self.file_padron:
            self.descompress_file(self.file_padron, dest_dir=tmp_dir)
        return tmp_dir

    def _get_arba_aliquots_detail(self, partner):
        """Obtiene Per y Ret en forma independiente para no pisar `nro` entre archivos."""
        self.ensure_one()
        detail = {
            "nro_per": False,
            "aliquot_per": False,
            "nro_ret": False,
            "aliquot_ret": False,
        }
        if not self.file_padron or not partner.vat:
            return detail

        tmp_dir = self._ensure_arba_extracted()
        for code, nro_key, aliq_key in (
            ("Per", "nro_per", "aliquot_per"),
            ("Ret", "nro_ret", "aliquot_ret"),
        ):
            rel_path = self.find_file(tmp_dir, code)
            if not rel_path:
                continue
            nro, aliq = self.find_aliquot(os.path.join(tmp_dir, rel_path), partner.vat)
            detail[nro_key] = nro
            detail[aliq_key] = aliq.replace(",", ".") if aliq else False
        return detail

    def _get_aliquot(self, partner):
        """Mantiene firma estándar (nro, aliquot_ret, aliquot_per) corrigiendo subcarpetas ARBA."""
        if self._is_santa_fe_jurisdiction():
            return super()._get_aliquot(partner)
        detail = self._get_arba_aliquots_detail(partner)
        return (
            detail["nro_ret"] or detail["nro_per"],
            detail["aliquot_ret"] or 0.0,
            detail["aliquot_per"] or 0.0,
        )

    def _auto_prepare_arba_on_save(self):
        """Al guardar un ZIP ARBA, pre-crea impuestos faltantes si está habilitado en la compañía."""
        for rec in self:
            if not rec.file_padron or not rec.l10n_ar_is_arba_padron:
                continue
            if not rec.company_id.l10n_ar_padron_auto_prepare_taxes:
                continue
            raw = base64.b64decode(rec.file_padron)
            if not rec._is_zip_content(raw):
                continue
            rec.with_company(rec.company_id).with_context(padron_auto_save=True).action_sync_taxes_from_padron()

    @api.model
    def _scan_arba_ret_rates_from_disk(self, ret_path):
        """Escanea streaming en binario el archivo Ret de ARBA para extraer tasas únicas y grupos."""
        raw_rates = set()
        groups = set()
        total_lines = 0
        malformed_lines = 0

        with open(ret_path, "rb") as handle:
            for raw_line in handle:
                line = raw_line.rstrip(b"\r\n")
                if not line:
                    continue
                total_lines += 1
                parts = line.split(b";")
                if len(parts) < 9:
                    malformed_lines += 1
                    continue
                try:
                    rate_val = round(float(parts[8].strip().replace(b",", b".")), 4)
                except ValueError:
                    malformed_lines += 1
                    continue
                raw_rates.add(rate_val)
                if len(parts) >= 10:
                    grp = parts[9].strip()
                    if grp:
                        groups.add(grp.decode("latin-1", errors="replace"))

        return {
            "raw_rates": sorted(raw_rates),
            "groups": sorted(groups),
            "total_lines": total_lines,
            "malformed_lines": malformed_lines,
        }

    def _abort_sync_with_warning(self, msg, title=False):
        """Registra observación y notifica opcionalmente cuando el padrón no puede procesarse."""
        self.ensure_one()
        self.with_context(skip_padron_sync=True).write(
            {
                "l10n_ar_last_sync_date": fields.Datetime.now(),
                "l10n_ar_sync_warnings": msg,
            }
        )
        if title:
            self.company_id._notify_padron_event(
                title,
                Markup("<p>%s</p>") % escape(msg),
                record=self,
                schedule_activity=True,
            )
        return {
            "created_taxes": self.env["account.tax"],
            "reactivated_taxes": self.env["account.tax"],
            "existing_taxes": self.env["account.tax"],
            "warnings": [msg],
        }

    def _sync_one_arba_padron(self):
        """Sincroniza impuestos de retención desde el ZIP ARBA de un registro."""
        self.ensure_one()
        company = self.company_id

        if not self.l10n_ar_is_arba_padron:
            return self._abort_sync_with_warning(
                _("Sincronización automática implementada únicamente para Buenos Aires / ARBA (902).")
            )
        if not self.file_padron:
            return self._abort_sync_with_warning(_("No hay archivo ZIP cargado en el registro de padrón."))

        setup = company.with_company(company)._ensure_arba_wth_fiscal_position()
        fp_line = setup["line"]
        default_tax = setup["default_tax"]
        if not default_tax or not fp_line:
            return self._abort_sync_with_warning(
                _(
                    "No se encontró plantilla de impuesto 0% de retención proveedor Buenos Aires o Posición Fiscal RI "
                    "para crear alícuotas automáticamente."
                ),
                title=_("Alerta al preparar Padrón ARBA: falta impuesto plantilla"),
            )

        try:
            tmp_dir = self._ensure_arba_extracted()
        except zipfile.BadZipFile:
            return self._abort_sync_with_warning(
                _("El archivo subido no es un ZIP válido."),
                title=_("Alerta en Padrón ARBA: ZIP inválido"),
            )

        ret_rel = self.find_file(tmp_dir, "Ret")
        if not ret_rel:
            return self._abort_sync_with_warning(
                _("No se encontró archivo de Retenciones (*Ret*.TXT) dentro del ZIP."),
                title=_("Alerta en Padrón ARBA: sin archivo de retenciones"),
            )

        warnings = []
        scan = self._scan_arba_ret_rates_from_disk(os.path.join(tmp_dir, ret_rel))
        if scan["malformed_lines"]:
            warnings.append(
                _("Se detectaron %d líneas con formato inesperado en %s.") % (scan["malformed_lines"], ret_rel)
            )
        if not scan["raw_rates"]:
            warnings.append(_("No se encontraron alícuotas válidas en %s.") % ret_rel)

        effective_rates = sorted({company._apply_arba_min_withholding_rate(r)[0] for r in scan["raw_rates"]})
        domain = fp_line._get_tax_domain()
        Tax = self.env["account.tax"].with_context(active_test=False)

        created_taxes = self.env["account.tax"]
        reactivated_taxes = self.env["account.tax"]
        existing_taxes = self.env["account.tax"]

        for rate in effective_rates:
            pre = Tax.search(domain + [("amount", "=", rate)], limit=1)
            was_inactive = bool(pre and not pre.active)
            tax = fp_line.with_context(skip_single_tax_notify=True)._ensure_tax(rate)
            if not pre:
                created_taxes |= tax
            elif was_inactive:
                reactivated_taxes |= tax
            else:
                existing_taxes |= tax

        raw_str = ", ".join("%.2f%%" % r for r in scan["raw_rates"])
        eff_str = ", ".join("%.2f%%" % r for r in effective_rates)
        groups_str = ", ".join(scan["groups"]) if scan["groups"] else "-"
        rates_summary = _(
            "Archivo: %s (%d líneas)\n"
            "Alícuotas en ZIP (%d): %s\n"
            "Alícuotas efectivas (%d)%s: %s\n"
            "Grupos ARBA: %s"
        ) % (
            ret_rel,
            scan["total_lines"],
            len(scan["raw_rates"]),
            raw_str or "-",
            len(effective_rates),
            _(" [Mínimo %.2f%%]") % company.l10n_ar_arba_wth_min_rate if company.l10n_ar_arba_wth_min_enabled else "",
            eff_str or "-",
            groups_str,
        )

        prep_lines = []
        if created_taxes:
            prep_lines.append(_("Nuevos creados (%d): %s") % (len(created_taxes), ", ".join(created_taxes.mapped("name"))))
        if reactivated_taxes:
            prep_lines.append(
                _("Desarchivados (%d): %s") % (len(reactivated_taxes), ", ".join(reactivated_taxes.mapped("name")))
            )
        if existing_taxes:
            prep_lines.append(_("Ya existentes (%d): %s") % (len(existing_taxes), ", ".join(existing_taxes.mapped("name"))))
        if setup["fp_created"] or setup["line_created"]:
            prep_lines.append(_("Posición Fiscal configurada: %s") % setup["fpos"].display_name)

        self.with_context(skip_padron_sync=True).write(
            {
                "l10n_ar_last_sync_date": fields.Datetime.now(),
                "l10n_ar_detected_rates_summary": rates_summary,
                "l10n_ar_created_taxes_summary": "\n".join(prep_lines),
                "l10n_ar_sync_warnings": "\n".join(warnings) if warnings else False,
            }
        )

        # Notificar en chatter / actividad si hubo impuestos nuevos, alertas o corrida manual
        should_notify = bool(created_taxes or warnings) or not self.env.context.get("padron_auto_save")
        if should_notify:
            br = Markup("<br/>")
            rates_html = br.join(escape(line) for line in rates_summary.splitlines())
            prep_html = br.join(
                escape(line) for line in ("\n".join(prep_lines) or _("Sin cambios en impuestos.")).splitlines()
            )
            alerts_html = ""
            if warnings:
                alerts_html = Markup("<p><b>Alertas:</b><br/>%s</p>") % br.join(
                    escape(w) for w in warnings
                )
            body = (
                Markup("<p><b>Sincronización Padrón ARBA completada</b></p><p>%s</p><p>%s</p>%s")
                % (rates_html, prep_html, alerts_html)
            )
            title = (
                _("Padrón ARBA: %d impuesto(s) nuevo(s) creado(s)") % len(created_taxes)
                if created_taxes
                else _("Padrón ARBA sincronizado")
            )
            company._notify_padron_event(
                title,
                body,
                record=self,
                schedule_activity=bool(created_taxes or warnings),
            )

        return {
            "created_taxes": created_taxes,
            "reactivated_taxes": reactivated_taxes,
            "existing_taxes": existing_taxes,
            "warnings": warnings,
        }

    def action_sync_taxes_from_padron(self):
        """Sincroniza e inicializa impuestos desde el ZIP ARBA para los padrones seleccionados."""
        results = {}
        for rec in self:
            results[rec.id] = rec.with_company(rec.company_id)._sync_one_arba_padron()
        return results

    def action_sync_taxes_from_padron_ui(self):
        """Botón de formulario: sincroniza impuestos del ZIP y muestra notificación en pantalla."""
        results = self.action_sync_taxes_from_padron()
        created_count = sum(len(res["created_taxes"]) for res in results.values())
        warnings = [w for res in results.values() for w in res["warnings"]]
        notif_type = "warning" if warnings else "success"
        msg = _("Sincronización finalizada. Impuestos nuevos creados: %d.") % created_count
        if warnings:
            msg = "%s\n%s" % (msg, "\n".join(warnings))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Padrón ARBA"),
                "message": msg,
                "type": notif_type,
                "sticky": bool(warnings),
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    def action_auto_configure_company_arba_wth_ui(self):
        """Botón de formulario: auto-configura la Posición Fiscal RI e impuesto plantilla ARBA."""
        self.ensure_one()
        res = self.company_id.action_auto_configure_arba_wth().get(self.company_id.id, {})
        fpos = res.get("fpos")
        if fpos:
            notif_type = "success"
            msg = _("Posición Fiscal '%s' verificada/configurada con impuesto plantilla '%s' (%s).") % (
                fpos.display_name,
                res["default_tax"].display_name,
                res["line"].webservice,
            )
        else:
            notif_type = "warning"
            msg = _("No se encontró el impuesto plantilla 0% de retención proveedor Buenos Aires en la compañía.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Configuración ARBA"),
                "message": msg,
                "type": notif_type,
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
