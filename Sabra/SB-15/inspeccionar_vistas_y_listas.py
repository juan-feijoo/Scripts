# -*- coding: utf-8 -*-
"""
Inspección de las Vistas QWeb 571 y 578 y de las Reglas de Listas de Precios
Ejecución:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < inspeccionar_vistas_y_listas.py
"""

print("\n" + "=" * 80)
print("1. ARQUITECTURA XML DE LAS VISTAS QWEB DE ETIQUETAS 2X7")
print("=" * 80)

view_simple = env['ir.ui.view'].browse(571)
print(f"\n--- VISTA 571 ({view_simple.key}): {view_simple.name} ---")
print(view_simple.arch)

view_tmpl = env['ir.ui.view'].browse(578)
print(f"\n--- VISTA 578 ({view_tmpl.key}): {view_tmpl.name} ---")
print(view_tmpl.arch)

print("\n" + "=" * 80)
print("2. DETALLE DE LAS LISTAS DE PRECIOS")
print("=" * 80)

pricelists_to_check = [5, 7, 8, 9, 10]
sample_product = env['product.product'].search([('sale_ok', '=', True), ('barcode', '!=', False)], limit=1)
if not sample_product:
    sample_product = env['product.product'].search([('sale_ok', '=', True)], limit=1)

print(f"\nProducto de prueba para cálculo: [{sample_product.default_code}] {sample_product.name}")
print(f"  - list_price: {sample_product.list_price}")
print(f"  - Impuestos: {', '.join(sample_product.taxes_id.mapped('name'))}")

for pl_id in pricelists_to_check:
    pl = env['product.pricelist'].browse(pl_id)
    if not pl.exists():
        continue
    price_base = pl._get_product_price(sample_product, 1.0)
    tax_res = sample_product.taxes_id.compute_all(price_base, product=sample_product, partner=False)
    price_with_tax = tax_res['total_included']
    print(f"\n[ID: {pl.id}] {pl.name}")
    print(f"  - Moneda: {pl.currency_id.name}")
    print(f"  - Cantidad de reglas: {len(pl.item_ids)}")
    print(f"  - Precio base calculado en esta lista: {price_base}")
    print(f"  - Precio CON IVA calculado: {price_with_tax}")
    for item in pl.item_ids[:2]:
        print(f"    * Regla ID {item.id}: applies={item.applied_on}, compute={item.compute_price}, fixed={item.fixed_price}, pct={item.percent_price}, base={item.base}")

print("\n" + "=" * 80)
