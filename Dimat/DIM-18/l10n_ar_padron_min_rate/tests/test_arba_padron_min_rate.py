import base64
import datetime
import io
import shutil
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import common


class TestArbaPadronMinRate(common.TransactionCase):
    """Pruebas de subcarpeta ZIP ARBA, RN 42/12 parametrizable, auto-setup y WS."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ar_country = cls.env.ref("base.ar")
        cls.ba_state = cls.env.ref("base.state_ar_b")
        cls.ri_resp = cls.env.ref("l10n_ar.res_IVARI")
        cls.cuit_type = cls.env.ref("l10n_ar.it_cuit")

        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Drogueria ARBA SA",
                "country_id": cls.ar_country.id,
                "vat": "30711432031",
            }
        )
        cls.company.partner_id.write(
            {
                "country_id": cls.ar_country.id,
                "l10n_latam_identification_type_id": cls.cuit_type.id,
                "l10n_ar_afip_responsibility_type_id": cls.ri_resp.id,
            }
        )
        cls.tax_group_wth = cls.env["account.tax.group"].create(
            {
                "name": "Test IIBB WTH BA",
                "country_id": cls.ar_country.id,
                "l10n_ar_tribute_afip_code": "01",
            }
        )
        cls.base_wth_tax = cls.env["account.tax"].with_company(cls.company).create(
            {
                "name": "IIBB WTH BA 0%",
                "company_id": cls.company.id,
                "type_tax_use": "none",
                "amount_type": "percent",
                "amount": 0.0,
                "tax_group_id": cls.tax_group_wth.id,
                "l10n_ar_state_id": cls.ba_state.id,
                "l10n_ar_withholding_payment_type": "supplier",
                "l10n_ar_tax_type": "iibb_untaxed",
            }
        )
        cls.company.write(
            {
                "l10n_ar_arba_wth_min_enabled": True,
                "l10n_ar_arba_wth_min_rate": 2.50,
                "l10n_ar_arba_wth_exclude_zero": True,
                "l10n_ar_arba_wth_apply_if_absent": False,
                "l10n_ar_arba_wth_source": "padron",
                "l10n_ar_padron_auto_prepare_taxes": True,
                "l10n_ar_padron_notify_new_taxes": True,
            }
        )
        cls.from_date = datetime.date(2026, 11, 1)
        cls.to_date = datetime.date(2026, 11, 30)

    def _make_partner(self, name, cuit):
        return self.env["res.partner"].create(
            {
                "name": name,
                "is_company": True,
                "country_id": self.ar_country.id,
                "l10n_latam_identification_type_id": self.cuit_type.id,
                "vat": cuit,
                "l10n_ar_afip_responsibility_type_id": self.ri_resp.id,
            }
        )

    def _build_nested_arba_zip(self, per_lines, ret_lines):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("PadronRGS112026/", "")
            if per_lines is not None:
                zf.writestr("PadronRGS112026/PadronRGSPer112026.txt", "\n".join(per_lines) + "\n")
            if ret_lines is not None:
                zf.writestr("PadronRGS112026/PadronRGSRet112026.TXT", "\n".join(ret_lines) + "\n")
        return base64.b64encode(buf.getvalue()).decode()

    def _arba_line(self, tipo, cuit, aliq, group="01"):
        return f"{tipo};29102026;01112026;30112026;{cuit};D;N;S;{aliq};{group};"

    def _create_padron(self, per_lines, ret_lines):
        padron = self.env["res.company.jurisdiction.padron"].with_company(self.company).create(
            {
                "company_id": self.company.id,
                "state_id": self.ba_state.id,
                "l10n_ar_padron_from_date": self.from_date,
                "l10n_ar_padron_to_date": self.to_date,
                "filename": "PadronRGS112026.zip",
                "file_padron": self._build_nested_arba_zip(per_lines, ret_lines),
            }
        )
        self.addCleanup(shutil.rmtree, padron._get_parp_tmp_dir(), ignore_errors=True)
        return padron

    def test_01_nested_zip_subfolders_rn42_and_auto_setup(self):
        """Lee ZIP con subcarpeta, aplica RN 42/12 (2,50%), mantiene 0% y pre-crea impuestos."""
        p_zero = self._make_partner("Prov Cero", "30111111111")
        p_low = self._make_partner("Prov Bajo", "30222222222")
        p_high = self._make_partner("Prov Alto", "30333333333")
        p_only_ret = self._make_partner("Prov Solo Ret", "30444444444")
        p_absent = self._make_partner("Prov Ausente", "30555555555")

        padron = self._create_padron(
            per_lines=[
                self._arba_line("P", p_zero.vat, "0,00"),
                self._arba_line("P", p_low.vat, "1,20"),
                self._arba_line("P", p_high.vat, "5,00"),
            ],
            ret_lines=[
                self._arba_line("R", p_zero.vat, "0,00", "01"),
                self._arba_line("R", p_low.vat, "0,40", "07"),
                self._arba_line("R", p_high.vat, "3,50", "22"),
                self._arba_line("R", p_only_ret.vat, "1,75", "18"),
            ],
        )

        # La carga automática debió configurar FP e impuestos 2.5% y 3.5%
        setup = self.company._ensure_arba_wth_fiscal_position()
        fp_line = setup["line"]
        self.assertTrue(setup["fpos"])
        self.assertTrue(fp_line)

        Tax = self.env["account.tax"].with_company(self.company)
        self.assertTrue(Tax.search([("company_id", "=", self.company.id), ("amount", "=", 2.5)]))
        self.assertTrue(Tax.search([("company_id", "=", self.company.id), ("amount", "=", 3.5)]))
        self.assertFalse(Tax.search([("company_id", "=", self.company.id), ("amount", "=", 0.4)]))
        self.assertTrue(padron.message_ids, "Debe registrar resumen de creación en el chatter.")

        # _get_padron_data con RN 42/12
        self.assertEqual(fp_line._get_padron_data(p_zero, self.from_date, self.to_date)[0], 0.0)
        aliq_low, ref_low = fp_line._get_padron_data(p_low, self.from_date, self.to_date)
        self.assertEqual(aliq_low, 2.5)
        self.assertIn("RN 42/12", ref_low)

        aliq_high, ref_high = fp_line._get_padron_data(p_high, self.from_date, self.to_date)
        self.assertEqual(aliq_high, 3.5)
        self.assertNotIn("RN 42/12", ref_high)

        # CUIT presente en Ret y ausente en Per no debe perder datos ni fallar
        aliq_only, _ref_only = fp_line._get_padron_data(p_only_ret, self.from_date, self.to_date)
        self.assertEqual(aliq_only, 2.5)

        aliq_abs, _ref_abs = fp_line._get_padron_data(p_absent, self.from_date, self.to_date)
        self.assertIsNone(aliq_abs)

        # Re-parametrización en caliente (ej. cambiar mínimo a 3.0% o deshabilitar)
        self.company.l10n_ar_arba_wth_min_rate = 3.00
        self.assertEqual(fp_line._get_padron_data(p_low, self.from_date, self.to_date)[0], 3.0)
        self.company.l10n_ar_arba_wth_min_enabled = False
        self.assertEqual(fp_line._get_padron_data(p_low, self.from_date, self.to_date)[0], 0.4)

    def test_02_reupload_invalidates_tmp_cache(self):
        """Reemplazar el archivo ZIP invalida /tmp para evitar leer alícuotas viejas."""
        partner = self._make_partner("Prov Cache", "30666666666")
        padron = self._create_padron(
            per_lines=[],
            ret_lines=[self._arba_line("R", partner.vat, "1,00")],
        )
        fp_line = self.company._ensure_arba_wth_fiscal_position()["line"]
        self.assertEqual(fp_line._get_padron_data(partner, self.from_date, self.to_date)[0], 2.5)

        padron.file_padron = self._build_nested_arba_zip(
            per_lines=[],
            ret_lines=[self._arba_line("R", partner.vat, "4,00")],
        )
        self.assertEqual(fp_line._get_padron_data(partner, self.from_date, self.to_date)[0], 4.0)

    def test_03_webservice_arba_applies_same_min_rule(self):
        """Cuando no hay ZIP y responde el WS ARBA, también aplica la regla mínima 2,50%."""
        partner = self._make_partner("Prov WS", "30777777777")
        self.company.l10n_ar_arba_wth_source = "arba"
        fp_line = self.company._ensure_arba_wth_fiscal_position()["line"]

        fake_ws = SimpleNamespace(
            Excepcion="",
            Traceback="",
            CodigoError="",
            MensajeError="",
            TipoError="",
            NumeroComprobante="999",
            CodigoHash="HASH",
            GrupoRetencion="07",
            GrupoPercepcion="07",
            AlicuotaRetencion="0,70",
            AlicuotaPercepcion="2,50",
            ConsultarContribuyentes=lambda *args: None,
        )
        with patch.object(type(self.company), "arba_connect", return_value=fake_ws):
            aliq, ref = fp_line._get_arba_data(partner, self.from_date, self.to_date)

        self.assertEqual(aliq, 2.5)
        self.assertIn("RN 42/12", ref)
