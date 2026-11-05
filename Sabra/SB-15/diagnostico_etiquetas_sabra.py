# -*- coding: utf-8 -*-
"""
================================================================================
DIAGNÓSTICO TÉCNICO: ETIQUETAS, PROVEEDORES, IMPUESTOS Y LISTAS DE PRECIOS
================================================================================
Empresa: JORGE FADY SABRA Y HEKMAT SABRA S.H.
Entorno: Odoo 19 Enterprise (Odoo.sh)
Ejecución:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < diagnostico_etiquetas_sabra.py

Objetivo:
  Inspeccionar la base de datos viva para conocer la configuración exacta antes
  de personalizar la vista/asistente de etiquetas y el reporte QWeb:
  1. Estructura y campos del asistente 'product.label.layout'.
  2. Reporte y vistas QWeb involucradas en el formato 2x7 con precio.
  3. Listas de precios existentes (Minorista vs Mayorista).
  4. Impuestos de venta (alícuotas e indicador price_include).
  5. Esquema de proveedores en productos (seller_ids, códigos, nombres).
================================================================================
"""

import sys

print("\n" + "=" * 80)
print("INICIANDO DIAGNÓSTICO DE ETIQUETAS Y PRODUCTOS (SABRA)")
print("=" * 80)

# 0. Información general de entorno
print(f"Compañía activa: {env.company.name} (ID: {env.company.id})")
print(f"Moneda compañía: {env.company.currency_id.name} ({env.company.currency_id.symbol})")

# 1. Inspección del Asistente 'product.label.layout'
print("\n" + "-" * 50)
print("1. ASISTENTE 'product.label.layout'")
print("-" * 50)
if 'product.label.layout' in env:
    layout_model = env['product.label.layout']
    fields = layout_model.fields_get()
    print("Campos disponibles en 'product.label.layout':")
    for fname in sorted(fields.keys()):
        finfo = fields[fname]
        print(f"  - {fname.ljust(25)} : {finfo['type'].ljust(12)} | {finfo.get('string', '')}")
    
    # Valores de print_format
    if 'print_format' in fields:
        print("\nOpciones de print_format:")
        for key, label in fields['print_format']['selection']:
            print(f"    * {key.ljust(20)} -> {label}")
else:
    print("ERROR: 'product.label.layout' no existe en el entorno.")

# 2. Listas de Precios Activas
print("\n" + "-" * 50)
print("2. LISTAS DE PRECIOS (product.pricelist)")
print("-" * 50)
pricelists = env['product.pricelist'].search([])
print(f"Total listas de precios encontradas: {len(pricelists)}")
for pl in pricelists:
    print(f"  [ID: {pl.id}] {pl.name} (Moneda: {pl.currency_id.name}, Activa: {pl.active})")
    # Mostrar algunas reglas/items si existen
    if pl.item_ids:
        print(f"     Reglas ({len(pl.item_ids)} items). Primeros 3:")
        for item in pl.item_ids[:3]:
            applies = item.applied_on
            compute = item.compute_price
            fixed = item.fixed_price if compute == 'fixed' else ''
            pct = item.percent_price if compute == 'percentage' else ''
            print(f"       - Aplica en: {applies} | Cálculo: {compute} {fixed} {pct}")

# 3. Impuestos de Venta Activos
print("\n" + "-" * 50)
print("3. IMPUESTOS DE VENTA (account.tax)")
print("-" * 50)
sale_taxes = env['account.tax'].search([
    ('type_tax_use', '=', 'sale'),
    ('company_id', '=', env.company.id)
])
print(f"Total impuestos de venta encontrados: {len(sale_taxes)}")
for tax in sale_taxes:
    print(f"  [ID: {tax.id}] {tax.name.ljust(35)} | Alícuota: {str(tax.amount).rjust(6)}% | Incluido en precio: {tax.price_include}")

# 4. Muestra de Productos y Proveedores (seller_ids)
print("\n" + "-" * 50)
print("4. MUESTRA DE PRODUCTOS Y PROVEEDORES (seller_ids)")
print("-" * 50)
# Buscamos algunos de los productos que aparecían en el PDF de muestra
sample_codes = ['21819', '21821', '21820', '1809', '6988776231993', '7795587005106']
products = env['product.product'].search([
    '|', ('default_code', 'in', sample_codes),
    ('barcode', 'in', sample_codes)
], limit=6)

if not products:
    # Si no coinciden por código directo, buscar los primeros 5 productos activos
    products = env['product.product'].search([('sale_ok', '=', True)], limit=5)

for p in products:
    taxes_names = ", ".join(p.taxes_id.mapped('name')) or "Sin Impuestos"
    sellers = p.seller_ids
    main_seller = sellers[0] if sellers else False
    
    # Calcular precio con IVA de lista base
    base_price = p.list_price
    tax_res = p.taxes_id.compute_all(base_price, product=p, partner=False)
    price_with_tax = tax_res['total_included']

    print(f"\nProducto: [{p.default_code or 'S/C'}] {p.name} (ID: {p.id})")
    print(f"  - Barcode: {p.barcode or 'N/A'}")
    print(f"  - Precio base (list_price): {base_price}")
    print(f"  - Impuestos: {taxes_names}")
    print(f"  - Precio con IVA incluido: {price_with_tax}")
    if main_seller:
        print(f"  - Proveedor Principal: {main_seller.partner_id.name} (ID: {main_seller.partner_id.id})")
        print(f"  - Cód. Producto Proveedor: {main_seller.product_code or 'N/A'}")
        print(f"  - Nombre Proveedor en Sellerinfo: {main_seller.product_name or 'N/A'}")
    else:
        print("  - Proveedor Principal: NO TIENE seller_ids cargados.")

# 5. Reporte y Vistas QWeb para Etiquetas 2x7
print("\n" + "-" * 50)
print("5. VISTAS Y ACCIONES DE REPORTE PARA ETIQUETAS 2x7")
print("-" * 50)
reports = env['ir.actions.report'].search([
    ('report_name', 'ilike', 'label')
])
for r in reports:
    if any(k in r.report_name.lower() or k in (r.name or '').lower() for k in ['2x7', 'compact', 'product']):
        print(f"  Report Action: [ID: {r.id}] {r.name} ({r.report_name}) -> Model: {r.model}")

# Buscar vistas QWeb asociadas a 2x7
views_2x7 = env['ir.ui.view'].search([
    ('key', 'ilike', '2x7')
])
print("\nVistas QWeb con clave '2x7':")
for v in views_2x7:
    print(f"  [ID: {v.id}] Key: {v.key} | Name: {v.name} | Model: {v.model or 'None'}")

views_labels = env['ir.ui.view'].search([
    ('key', 'in', ['product.report_simple_label2x7', 'product.report_producttemplatelabel2x7'])
])
for v in views_labels:
    print(f"  [ID: {v.id}] Exact View: {v.key} | Inherit ID: {v.inherit_id.name if v.inherit_id else 'None'}")

print("\n" + "=" * 80)
print("FIN DEL DIAGNÓSTICO")
print("=" * 80)
