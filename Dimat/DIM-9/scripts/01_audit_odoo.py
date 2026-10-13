# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 01: AUDITORÍA DE ENTORNO ODOO (READ-ONLY)
================================================================================
Ejecución en Odoo Shell:
    python3 odoo-bin shell -d <nombre_bd> < scripts/01_audit_odoo.py
    o pegar directamente dentro de la shell interactiva.
================================================================================
"""

print("\n" + "="*80)
print(" AUDITORÍA TÉCNICA ODOO: MONEDAS, COMPAÑÍAS Y TARIFAS ".center(80, "="))
print("="*80 + "\n")

# 1. Auditoría de Compañía
company = env.company
print(f"[*] Compañía actual en contexto: [{company.id}] {company.name}")
print(f"    Moneda de la compañía: {company.currency_id.name} (ID: {company.currency_id.id})")

# 2. Auditoría de Monedas (ARS y USD)
print("\n[*] Verificando divisas ARS y USD:")
currencies = env['res.currency'].search([('name', 'in', ['ARS', 'USD'])])
for curr in currencies:
    print(f"    - [{curr.id}] {curr.name} (Símbolo: {curr.symbol}) | Activa: {curr.active} | Tasa: {curr.rate}")

# 3. Auditoría de Tarifas existentes
pricelists = env['product.pricelist'].search([])
print(f"\n[*] Listas de Precios existentes ({len(pricelists)} encontradas):")
for pl in pricelists:
    item_count = len(pl.item_ids)
    comp_name = pl.company_id.name if pl.company_id else "Global (Todas)"
    print(f"    - ID {pl.id:3d} | {pl.name:<35} | Moneda: {pl.currency_id.name:<4} | Compañía: {comp_name:<25} | Items: {item_count}")

# 4. Auditoría de Productos
total_variants = env['product.product'].search_count([('default_code', '!=', False)])
total_templates = env['product.template'].search_count([('default_code', '!=', False)])
print(f"\n[*] Productos con Referencia Interna ('default_code'):")
print(f"    - Variantes (product.product):  {total_variants}")
print(f"    - Plantillas (product.template): {total_templates}")

print("\n" + "="*80)
print(" FIN DE AUDITORÍA ".center(80, "="))
print("="*80 + "\n")
