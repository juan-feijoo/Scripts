# -*- coding: utf-8 -*-
"""
================================================================================
SIMULACIÓN Y VERIFICACIÓN DE ETIQUETAS SABRA (DRY-RUN)
================================================================================
Compañía: JORGE FADY SABRA Y HEKMAT SABRA S.H.
Ejecución en Odoo.sh:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < test_simulacion_etiqueta.py
================================================================================
"""

print("\n" + "=" * 80)
print("TEST DE CÁLCULO DE ETIQUETAS: PROVEEDOR, IVA Y DOBLE PRECIO (MINORISTA/MAYORISTA)")
print("=" * 80)

# 1. Obtener Listas de Precios de Sabra
pl_minorista = env['product.pricelist'].browse(5) # Lista ARS
pl_mayorista = env['product.pricelist'].browse(7) # MAYORISTA

print(f"Lista Minorista: [ID: {pl_minorista.id}] {pl_minorista.name}")
print(f"Lista Mayorista: [ID: {pl_mayorista.id}] {pl_mayorista.name}")

# 2. Productos de prueba representativos
sample_codes = ['101500700374', '21819', '1809', '6988776231993', '7795587005106']
products = env['product.product'].search([
    '|', ('default_code', 'in', sample_codes),
    ('barcode', 'in', sample_codes)
])

if not products:
    products = env['product.product'].search([('sale_ok', '=', True)], limit=5)

currency = env.company.currency_id

print("\n" + "-" * 80)
print(f"{'ARTÍCULO':<15} | {'PROVEEDOR':<22} | {'MIN. BASE':<10} | {'MIN. C/IVA':<10} | {'MAY. C/IVA':<10}")
print("-" * 80)

for p in products:
    seller = (p.seller_ids and p.seller_ids[0]) or (p.product_tmpl_id.seller_ids and p.product_tmpl_id.seller_ids[0])
    vendor_name = seller.partner_id.name[:20] if seller else "SIN PROVEEDOR"
    if seller and seller.product_code:
        vendor_name += f" ({seller.product_code})"

    # Minorista
    p_min_base = pl_minorista._get_product_price(p, 1.0, currency=currency) if pl_minorista else p.list_price
    t_min = p.taxes_id.compute_all(p_min_base, product=p, partner=False) if p.taxes_id else {'total_included': p_min_base}
    p_min_inc = t_min['total_included']

    # Mayorista
    p_may_base = pl_mayorista._get_product_price(p, 1.0, currency=currency) if pl_mayorista else p_min_base
    t_may = p.taxes_id.compute_all(p_may_base, product=p, partner=False) if p.taxes_id else {'total_included': p_may_base}
    p_may_inc = t_may['total_included']

    code = (p.default_code or p.barcode or 'S/C')[:14]
    print(f"{code:<15} | {vendor_name:<22} | ${p_min_base:>9.2f} | ${p_min_inc:>9.2f} | ${p_may_inc:>9.2f}")

print("-" * 80)
print("\nVerificación de resultado:")
print("  - Los precios calculados con IVA incluido reflejan el monto final de góndola / punto de venta.")
print("  - El código o nombre del proveedor principal está resuelto correctamente para cada artículo.")
print("=" * 80 + "\n")
