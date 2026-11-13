# -*- coding: utf-8 -*-
# Copyright 2026 Outsource Argentina
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
import logging

from odoo.tools.sql import column_exists, create_column

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    """Crea e inicializa las columnas por SQL antes de cargar el ORM para evitar
    que al instalar el módulo se recalculen precios en órdenes existentes o confirmadas.
    """
    cr = env.cr
    if not column_exists(cr, "sale_order_line", "pricelist_follows_order"):
        create_column(cr, "sale_order_line", "pricelist_follows_order", "boolean")
        cr.execute("UPDATE sale_order_line SET pricelist_follows_order = TRUE")
    if not column_exists(cr, "sale_order_line", "pricelist_id"):
        create_column(cr, "sale_order_line", "pricelist_id", "int4")
        cr.execute(
            """
            UPDATE sale_order_line sol
               SET pricelist_id = so.pricelist_id
              FROM sale_order so
             WHERE so.id = sol.order_id
               AND so.pricelist_id IS NOT NULL
            """
        )
        _logger.info("sale_line_pricelist: %s líneas inicializadas con la lista de su pedido", cr.rowcount)
