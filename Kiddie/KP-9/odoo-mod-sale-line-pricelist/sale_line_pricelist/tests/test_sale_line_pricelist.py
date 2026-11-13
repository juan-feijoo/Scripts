# -*- coding: utf-8 -*-
# Copyright 2026 Outsource Argentina
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestSaleLinePricelist(SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.currency
        cls.ars = cls._setup_other_currency("ARS", rates=[("2026-01-01", 1000.0)])
        cls.prod = cls._create_product(
            name="Marcador Pizarra Test",
            standard_price=100.0,
            list_price=150.0,
        )
        cls.tmpl = cls.prod.product_tmpl_id

        cls.pl_usd = cls.pricelist
        cls.pl_usd_fixed = cls._create_pricelist(
            name="USD Fixed 80",
            currency_id=cls.usd.id,
            item_ids=[Command.create(cls._fixed_item(cls.tmpl, 80.0))],
        )
        cls.pl_ars_base = cls._create_pricelist(
            name="ARS Público +85%",
            currency_id=cls.ars.id,
            item_ids=[
                Command.create(
                    {
                        "applied_on": "1_product",
                        "product_tmpl_id": cls.tmpl.id,
                        "compute_price": "formula",
                        "base": "standard_price",
                        "price_discount": -85.0,
                    }
                )
            ],
        )
        cls.pl_ars_mayorista = cls._create_pricelist(
            name="ARS Mayorista",
            currency_id=cls.ars.id,
            item_ids=[
                Command.create(
                    {
                        "applied_on": "1_product",
                        "product_tmpl_id": cls.tmpl.id,
                        "min_quantity": 1.0,
                        "compute_price": "formula",
                        "base": "standard_price",
                        "price_discount": -40.0,
                    }
                ),
                Command.create(
                    {
                        "applied_on": "1_product",
                        "product_tmpl_id": cls.tmpl.id,
                        "min_quantity": 10.0,
                        "compute_price": "formula",
                        "base": "standard_price",
                        "price_discount": -25.0,
                    }
                ),
            ],
        )
        cls.pl_ars_fixed = cls._create_pricelist(
            name="ARS Fixed 50000",
            currency_id=cls.ars.id,
            item_ids=[Command.create(cls._fixed_item(cls.tmpl, 50000.0))],
        )

    @classmethod
    def _fixed_item(cls, tmpl, price):
        return {
            "applied_on": "1_product",
            "product_tmpl_id": tmpl.id,
            "compute_price": "fixed",
            "fixed_price": price,
        }

    def _order(self, pricelist, **line_vals):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "pricelist_id": pricelist.id,
                "date_order": "2026-01-01 00:00:00",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.prod.id,
                            "product_uom_qty": 1,
                            **line_vals,
                        }
                    )
                ],
            }
        )

    def test_01_default_follows_order(self):
        order = self._order(self.pl_usd)
        line = order.order_line
        self.assertEqual(line.pricelist_id, self.pl_usd)
        self.assertTrue(line.pricelist_follows_order)
        self.assertAlmostEqual(line.price_unit, 150.0)

    def test_02_formula_cost_and_qty_rules_per_line(self):
        """Caso Kiddie: pedido ARS con fórmula s/costo y escala por cantidad en lista propia."""
        order = self._order(self.pl_ars_base)
        line = order.order_line
        # standard_price 100 USD -> 100.000 ARS + 85% = 185.000 ARS
        self.assertAlmostEqual(line.price_unit, 185000.0, places=2)

        line.write({"pricelist_id": self.pl_ars_mayorista.id})
        self.assertFalse(line.pricelist_follows_order)
        self.assertAlmostEqual(line.price_unit, 140000.0, places=2)

        # Al cambiar cantidad a 10, debe usar la escala de pl_ars_mayorista (no cabecera)
        line.write({"product_uom_qty": 10.0})
        self.assertAlmostEqual(line.price_unit, 125000.0, places=2)

    def test_03_ars_order_with_usd_line(self):
        """Caso Kiddie: pedido en ARS con línea usando lista en USD (80 USD -> 80.000 ARS)."""
        order = self._order(self.pl_ars_base, pricelist_id=self.pl_usd_fixed.id)
        self.assertEqual(order.currency_id, self.ars)
        self.assertFalse(order.order_line.pricelist_follows_order)
        self.assertAlmostEqual(order.order_line.price_unit, 80000.0, places=2)

    def test_04_foreign_currency_fixed_price_on_usd_order(self):
        """50.000 ARS fijo en pedido USD -> 50 USD."""
        order = self._order(self.pl_usd, pricelist_id=self.pl_ars_fixed.id)
        self.assertAlmostEqual(order.order_line.price_unit, 50.0, places=2)

    def test_05_order_pricelist_change_keeps_custom_lines(self):
        order = self._order(self.pl_usd)
        order.order_line = [
            Command.create({"product_id": self.prod.id, "pricelist_id": self.pl_usd_fixed.id})
        ]
        following, custom = order.order_line
        order.pricelist_id = self.pl_ars_fixed
        self.assertEqual(following.pricelist_id, self.pl_ars_fixed)
        self.assertEqual(custom.pricelist_id, self.pl_usd_fixed)

    def test_06_onchange_and_write_force_reprice_over_manual_price(self):
        """Editar precio manual protege ante cantidad, pero cambiar lista en línea fuerza recálculo."""
        order = self._order(self.pl_usd)
        with Form(order) as so_form:
            with so_form.order_line.edit(0) as line_form:
                line_form.price_unit = 123.0
            with so_form.order_line.edit(0) as line_form:
                line_form.pricelist_id = self.pl_ars_fixed
                self.assertAlmostEqual(line_form.price_unit, 50.0, places=2)
        self.assertFalse(order.order_line.pricelist_follows_order)

        # También desde write() en backend tras edición manual
        order.order_line.write({"price_unit": 99.0})
        order.order_line.write({"pricelist_id": self.pl_usd_fixed.id})
        self.assertAlmostEqual(order.order_line.price_unit, 80.0, places=2)

    def test_07_update_prices_uses_line_pricelist(self):
        order = self._order(self.pl_usd, pricelist_id=self.pl_ars_fixed.id)
        order.order_line.price_unit = 1.0
        order.action_update_prices()
        self.assertAlmostEqual(order.order_line.price_unit, 50.0, places=2)
