# -*- coding: utf-8 -*-
# Copyright 2026 Outsource Argentina
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
{
    "name": "Lista de Precios por Línea en Ventas",
    "summary": "Permite elegir una lista de precios independiente (y multimoneda) en cada línea de Orden de Venta",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "author": "Juan Martín Feijoó - Outsource Argentina",
    "license": "LGPL-3",
    "depends": [
        "sale",
    ],
    "data": [
        "views/sale_order_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
