# -*- coding: utf-8 -*-
"""
Snippet para probar en Odoo Shell: Recuperación inteligente de los 81 productos no encontrados
"""
# 1. Traer los no encontrados iniciales
missing_items = [row for row in items_data if row['code'].strip() not in prod_by_code]
print(f"Total a auditar: {len(missing_items)}")

recovered_dot = []
recovered_barcode = []
recovered_name = []
still_missing = []

for m in missing_items:
    code_raw = m['code'].strip()
    name = m['name'].strip()
    prod = False
    
    # Intento 1: Limpieza de puntos finales (ej. '88800000000059.' -> '88800000000059')
    clean_code = code_raw.rstrip('.').strip()
    if clean_code != code_raw:
        prod = env['product.product'].search([('default_code', '=', clean_code)], limit=1)
        if prod:
            recovered_dot.append((code_raw, clean_code, prod.display_name))
            continue
            
    # Intento 2: Buscar en código de barras (barcode)
    prod = env['product.product'].search([('barcode', 'in', [code_raw, clean_code])], limit=1)
    if prod:
        recovered_barcode.append((code_raw, prod.barcode, prod.display_name))
        continue

    # Intento 3: Nombre exacto o muy cercano
    prod = env['product.product'].search([('name', '=ilike', name)], limit=1)
    if prod:
        recovered_name.append((code_raw, prod.default_code, prod.display_name))
        continue
        
    still_missing.append(m)

print(f"\n[+] Recuperados por punto final: {len(recovered_dot)}")
for r in recovered_dot[:5]:
    print(f"    {r[0]} -> {r[1]} ({r[2]})")

print(f"\n[+] Recuperados por Código de Barras: {len(recovered_barcode)}")
for r in recovered_barcode[:5]:
    print(f"    {r[0]} -> {r[1]} ({r[2]})")

print(f"\n[+] Recuperados por Nombre Exacto: {len(recovered_name)}")
for r in recovered_name[:5]:
    print(f"    {r[0]} -> Código en Odoo: {r[1]} ({r[2]})")

print(f"\n[-] Definitivamente No Encontrados: {len(still_missing)}")
