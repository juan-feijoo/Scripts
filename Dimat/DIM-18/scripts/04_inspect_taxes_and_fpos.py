# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 04: INSPECCIÓN DE IMPUESTOS Y POSICIONES FISCALES ARBA
================================================================================
Propósito:
    Identificar con exactitud cuáles son los impuestos plantilla (default taxes)
    tanto para RETENCIÓN (proveedores) como para PERCEPCIÓN (clientes) de ARBA,
    y cómo están mapeados en las Posiciones Fiscales de ADHOC.
================================================================================
"""

company = env.company
ba_state = env.ref('base.state_ar_b')

print("\n" + "="*80)
print(" CONFIGURACIÓN EXACTA DE IMPUESTOS ARBA (BUENOS AIRES) ".center(80, "="))
print("="*80 + "\n")

# 1. Impuestos de Venta (Percepciones) para Buenos Aires
print("[*] Impuestos de Venta (type_tax_use='sale') con Jurisdicción Buenos Aires o Grupo ARBA:")
sale_taxes = env['account.tax'].search([
    ('company_id', '=', company.id),
    ('type_tax_use', '=', 'sale'),
    '|',
    ('l10n_ar_state_id', '=', ba_state.id),
    ('tax_group_id.name', 'ilike', 'arba')
])
for t in sale_taxes:
    print(f"    - ID {t.id:4d} | {t.name:<40} | Monto: {t.amount:>5.2f}% | Grupo: {t.tax_group_id.name} | Activo: {t.active}")

if not sale_taxes:
    print("    [!] No se encontraron impuestos de venta específicos para ARBA. Buscando todos los de tipo 'sale' con tax_group de percepción...")
    other_perc = env['account.tax'].search([
        ('company_id', '=', company.id),
        ('type_tax_use', '=', 'sale'),
        ('tax_group_id.l10n_ar_tribute_afip_code', 'in', ['02', '03', '04']) # Percepciones
    ])
    for t in other_perc:
        state = t.l10n_ar_state_id.name if t.l10n_ar_state_id else 'Sin Jurisdicción'
        print(f"    - ID {t.id:4d} | {t.name:<40} | Monto: {t.amount:>5.2f}% | Grupo: {t.tax_group_id.name} | Prov: {state}")

# 2. Impuestos de Retención a Proveedores para Buenos Aires
print("\n[*] Impuestos de Retención (withholding supplier) para Buenos Aires:")
wh_taxes = env['account.tax'].search([
    ('company_id', '=', company.id),
    ('l10n_ar_withholding_payment_type', '=', 'supplier'),
    ('l10n_ar_state_id', '=', ba_state.id)
])
for t in wh_taxes:
    print(f"    - ID {t.id:4d} | {t.name:<40} | Monto: {t.amount:>5.2f}% | Grupo: {t.tax_group_id.name} | Activo: {t.active}")

# 3. Posiciones Fiscales y sus líneas de l10n_ar_tax
print("\n[*] Configuración en Posiciones Fiscales (l10n_ar_tax_ids):")
fpos = env['account.fiscal.position'].search([('company_id', '=', company.id)])
for fp in fpos:
    if hasattr(fp, 'l10n_ar_tax_ids') and fp.l10n_ar_tax_ids:
        print(f"\n    Posición Fiscal: [{fp.id}] {fp.name}")
        for line in fp.l10n_ar_tax_ids:
            dt = line.default_tax_id
            print(f"        -> Tipo: {line.tax_type:<12} | WS: {line.webservice or 'Manual':<10} | Impuesto Default: [{dt.id}] {dt.name} ({dt.amount}%)")

# 4. Registros existentes en res.company.jurisdiction.padron
if 'res.company.jurisdiction.padron' in env:
    padrons = env['res.company.jurisdiction.padron'].search([('company_id', '=', company.id)])
    print(f"\n[*] Padrones cargados en el sistema ({len(padrons)}):")
    for p in padrons:
        print(f"    - ID {p.id:3d} | Jurisdicción: {p.state_id.name} | Desde: {p.l10n_ar_padron_from_date} | Hasta: {p.l10n_ar_padron_to_date} | Archivo: {p.filename}")

print("\n" + "="*80)
print(" FIN DE INSPECCIÓN ".center(80, "="))
print("="*80 + "\n")
