# -*- coding: utf-8 -*-
# Copyright 2026 Outsource Argentina
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Lista de precios",
        compute="_compute_pricelist_id",
        store=True,
        readonly=False,
        precompute=True,
        check_company=True,
        index="btree_not_null",
        help="Lista de precios usada para calcular el precio de esta línea. "
        "Por defecto toma la lista del pedido. Si su moneda difiere de la del pedido, "
        "el precio se convierte según la cotización de la fecha del pedido.",
    )
    pricelist_follows_order = fields.Boolean(
        string="Lista sigue al pedido",
        default=True,
        copy=True,
        help="Campo técnico: si está activo, la lista de la línea sigue los cambios de cabecera.",
    )

    # ------------------------------------------------------------------
    # Asignación de lista de precios en la línea
    # ------------------------------------------------------------------

    @api.depends("order_id.pricelist_id", "pricelist_follows_order")
    def _compute_pricelist_id(self):
        for line in self:
            if line.pricelist_follows_order or not line.pricelist_id:
                line.pricelist_id = line.order_id.pricelist_id

    @api.onchange("pricelist_id")
    def _onchange_pricelist_id_line(self):
        """Al cambiar la lista en la línea desde la interfaz: deja de seguir al pedido
        y recalcula el precio unitario (incluso si había sido editado manualmente).
        Si el usuario limpia el campo, vuelve a heredar la lista del pedido.
        """
        for line in self:
            if not line.pricelist_id:
                line.pricelist_id = line.order_id.pricelist_id
                line.pricelist_follows_order = True
            else:
                line.pricelist_follows_order = line.pricelist_id == line.order_id.pricelist_id
            if line.product_id and not line.display_type:
                line._compute_pricelist_item_id()
                line.with_context(force_price_recomputation=True)._compute_price_unit()
                line.discount = 0.0
                line._compute_discount()

    @api.model_create_multi
    def create(self, vals_list):
        SaleOrder = self.env["sale.order"]
        for vals in vals_list:
            if (
                vals.get("pricelist_id")
                and vals.get("order_id")
                and "pricelist_follows_order" not in vals
            ):
                order = SaleOrder.browse(vals["order_id"])
                vals["pricelist_follows_order"] = order.pricelist_id.id == vals["pricelist_id"]
        return super().create(vals_list)

    def write(self, vals):
        if "pricelist_id" not in vals:
            return super().write(vals)

        target_pl_id = vals.get("pricelist_id") or False
        changed = self.filtered(lambda l: l.pricelist_id.id != target_pl_id)

        if "pricelist_follows_order" in vals:
            res = super().write(vals)
        else:
            same = self.filtered(lambda line: line.order_id.pricelist_id.id == target_pl_id)
            other = self - same
            res = True
            if same:
                res = super(SaleOrderLine, same).write(dict(vals, pricelist_follows_order=True))
            if other:
                res = super(SaleOrderLine, other).write(dict(vals, pricelist_follows_order=False)) and res

        if changed and "price_unit" not in vals:
            reprice = changed.filtered(lambda l: l.product_id and not l.display_type)
            if reprice:
                reprice._compute_pricelist_item_id()
                reprice.with_context(force_price_recomputation=True)._compute_price_unit()
                reprice.discount = 0.0
                reprice._compute_discount()
        return res

    # ------------------------------------------------------------------
    # Motor de cálculo de precios y multimoneda (Odoo 19.0)
    # ------------------------------------------------------------------

    def _has_own_pricelist(self):
        self.ensure_one()
        return bool(self.pricelist_id) and self.pricelist_id != self.order_id.pricelist_id

    def _get_line_pricelist_currency(self):
        """Moneda en la que debe evaluarse la regla de la lista de la línea,
        o False cuando coincide con la moneda del pedido (comportamiento estándar).
        """
        self.ensure_one()
        currency = self.pricelist_id.currency_id
        if self._has_own_pricelist() and currency and currency != self.currency_id:
            return currency
        return False

    @api.depends("pricelist_id")
    def _compute_pricelist_item_id(self):
        own = self.filtered(lambda line: line._has_own_pricelist())
        super(SaleOrderLine, self - own)._compute_pricelist_item_id()
        for line in own:
            if not line.product_id or line.display_type:
                line.pricelist_item_id = False
            else:
                line.pricelist_item_id = line.pricelist_id._get_product_rule(
                    product=line.product_id,
                    **line._get_pricelist_kwargs(),
                )

    @api.depends("pricelist_id")
    def _compute_price_unit(self):
        return super()._compute_price_unit()

    @api.depends("pricelist_id")
    def _compute_discount(self):
        return super()._compute_discount()

    def _get_pricelist_kwargs(self):
        kwargs = super()._get_pricelist_kwargs()
        if len(self) == 1:
            currency = self._get_line_pricelist_currency()
            if currency:
                # Las reglas de precio fijo / recargo se expresan en la moneda de la lista:
                # evaluamos la regla en esa moneda y luego convertimos a la moneda del pedido.
                kwargs["currency"] = currency
        return kwargs

    def _get_pricelist_price(self):
        price = super()._get_pricelist_price()
        currency = self._get_line_pricelist_currency()
        return self._convert_to_sol_currency(price, currency) if currency else price

    def _get_pricelist_price_before_discount(self):
        price = super()._get_pricelist_price_before_discount()
        currency = self._get_line_pricelist_currency()
        return self._convert_to_sol_currency(price, currency) if currency else price

    def _get_pricelist_price_context(self):
        res = super()._get_pricelist_price_context()
        if self.pricelist_id:
            res["pricelist"] = self.pricelist_id.id
        return res
