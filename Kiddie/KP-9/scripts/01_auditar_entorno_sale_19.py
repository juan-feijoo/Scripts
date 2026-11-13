# -*- coding: utf-8 -*-
"""
================================================================================
DIAGNÓSTICO SOLO LECTURA EN ODOO.SH: ENTORNO DE VENTAS Y LISTAS DE PRECIO (KP-9)
Uso en Odoo.sh:
  odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < scripts/01_auditar_entorno_sale_19.py
================================================================================
"""

import inspect
from odoo import release


def h(title):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def auditar_entorno(env):
    h("1. VERSIÓN DE ODOO Y CAMPOS CLAVE EN sale.order.line")
    print(f"Odoo Version: {release.version} ({release.version_info})")

    LineModel = env['sale.order.line']
    campos_interes = [
        'product_uom_id', 'product_uom',
        'tax_ids', 'tax_id',
        'pricelist_item_id', 'technical_price_unit',
        'price_unit', 'discount', 'display_type',
    ]
    for fname in campos_interes:
        existe = fname in LineModel._fields
        ftype = LineModel._fields[fname].type if existe else '-'
        print(f"  - {fname:<24} : {'OK (' + ftype + ')' if existe else 'NO EXISTE'}")

    h("2. MÓDULOS QUE HEREDAN MÉTODOS DE PRECIO (MRO)")
    metodos = [
        ('sale.order.line', ['_compute_pricelist_item_id', '_get_pricelist_price', '_get_display_price', '_compute_price_unit', '_compute_discount']),
        ('sale.order', ['_recompute_prices', 'action_update_prices']),
    ]
    for model_name, mnames in metodos:
        cls = type(env[model_name])
        for m in mnames:
            definers = [k.__module__ for k in cls.__mro__ if m in k.__dict__]
            print(f"  * {model_name}.{m}: {definers}")

    h("3. VERIFICACIÓN XPATH EN sale.view_order_form")
    view = env.ref('sale.view_order_form', raise_if_not_found=False)
    if view:
        arch = view.arch_db or ''
        print(f"  - Vista ID {view.id} | Usa <list>: {'<list' in arch} | Usa <tree>: {'<tree' in arch}")
        print(f"  - Contiene price_unit: {'price_unit' in arch}")
    else:
        print("  !! No se encontró sale.view_order_form")

    h("4. LISTAS DE PRECIOS ACTIVAS EN LA BASE")
    for pl in env['product.pricelist'].search([]):
        print(f"  * [ID:{pl.id}] {pl.name:<35} | Moneda: {pl.currency_id.name} | Reglas: {len(pl.item_ids)}")

    env.cr.rollback()


if 'env' in locals():
    auditar_entorno(env)
else:
    print("[INFO] Ejecutar dentro de odoo-bin shell.")
