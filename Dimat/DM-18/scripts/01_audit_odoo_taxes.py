# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 01: AUDITORÍA DE ENTORNO ODOO - IMPUESTOS, REGÍMENES Y CONTACTOS
================================================================================
Propósito:
    Inspeccionar en Odoo.sh la configuración actual de localización argentina
    (l10n_ar, l10n_ar_tax, l10n_ar_withholding), los impuestos existentes de
    ARBA (Percepciones de Ventas y Retenciones de Compras/Pagos), y la forma
    en que se asignan actualmente los regímenes a los contactos (res.partner).

Ejecución en Odoo Shell (Odoo.sh):
    python3 odoo-bin shell -d $PGDATABASE < scripts/01_audit_odoo_taxes.py
    o pegar directamente dentro de la consola odoo-bin shell.

Seguridad:
    SOLO LECTURA (READ-ONLY / DRY-RUN). No realiza modificaciones ni commit.
================================================================================
"""

import logging

print("\n" + "="*80)
print(" AUDITORÍA TÉCNICA ODOO: ARBA / REGÍMENES / CONTACTOS ".center(80, "="))
print("="*80 + "\n")

company = env.company
print(f"[*] Compañía en contexto: [{company.id}] {company.name} | CUIT: {company.vat or 'S/D'}")
print(f"    País: {company.country_id.name} ({company.country_id.code}) | Moneda: {company.currency_id.name}")

# ----------------------------------------------------------------------
# 1. Módulos instalados relevantes
# ----------------------------------------------------------------------
print("\n" + "-"*80)
print(" 1. MÓDULOS DE LOCALIZACIÓN INSTALADOS ".center(80, "-"))
print("-" * 80)

modules_to_check = [
    'l10n_ar',
    'l10n_ar_withholding',
    'l10n_ar_tax',
    'l10n_ar_tax_settlement',
    'account_payment_pro',
    'account_tax_settlement',
    'l10n_ar_arba_ws',
]

for mod_name in modules_to_check:
    mod = env['ir.module.module'].search([('name', '=', mod_name)], limit=1)
    status = mod.state if mod else 'no instalado'
    print(f"    - {mod_name:<30} : {status}")

# ----------------------------------------------------------------------
# 2. Modelos disponibles para asignación de regímenes
# ----------------------------------------------------------------------
print("\n" + "-"*80)
print(" 2. MODELOS Y CAMPOS DETECTADOS ".center(80, "-"))
print("-" * 80)

has_partner_tax_model = 'l10n_ar.partner.tax' in env
print(f"    - Modelo 'l10n_ar.partner.tax': {'DISPONIBLE' if has_partner_tax_model else 'NO DISPONIBLE'}")

partner_fields = env['res.partner']._fields
for f_name in ['l10n_ar_partner_tax_ids', 'l10n_ar_partner_perception_ids', 'l10n_ar_gross_income_type', 'l10n_ar_gross_income_number']:
    print(f"    - res.partner.{f_name:<32} : {'PRESENTE' if f_name in partner_fields else 'NO PRESENTE'}")

# Verificar si hay campos Studio relacionados a padrón o alícuota
studio_tax_fields = [f for f in partner_fields if 'studio' in f.lower() and any(w in f.lower() for w in ['arba', 'ret', 'per', 'padron', 'ali'])]
if studio_tax_fields:
    print(f"    - Campos Studio detectados en res.partner: {studio_tax_fields}")

# ----------------------------------------------------------------------
# 3. Impuestos existentes de ARBA / IIBB (account.tax)
# ----------------------------------------------------------------------
print("\n" + "-"*80)
print(" 3. IMPUESTOS CONFIGURADOS EN ACCOUNT.TAX (ARBA / IIBB) ".center(80, "-"))
print("-" * 80)

# Buscar impuestos que mencionen ARBA, IIBB, Buenos Aires o con grupos de percepción/retención
taxes = env['account.tax'].search([
    ('company_id', '=', company.id),
    '|', '|', '|',
    ('name', 'ilike', 'arba'),
    ('name', 'ilike', 'iibb'),
    ('name', 'ilike', 'bs'),
    ('name', 'ilike', 'buenos aires')
])

print(f"[*] Total impuestos relacionados encontrados: {len(taxes)}")
for t in taxes:
    type_use = t.type_tax_use
    tg_name = t.tax_group_id.name if t.tax_group_id else 'Sin Grupo'
    w_type = getattr(t, 'l10n_ar_withholding_payment_type', 'N/A')
    state = t.l10n_ar_state_id.name if hasattr(t, 'l10n_ar_state_id') and t.l10n_ar_state_id else 'N/A'
    print(f"    - ID {t.id:4d} | {t.name:<45} | Uso: {type_use:<8} | Monto: {t.amount:>6.2f}% | Grupo: {tg_name:<18} | Jurisdicción: {state} | Ret.Type: {w_type}")

# ----------------------------------------------------------------------
# 4. Auditoría de Contactos (res.partner)
# ----------------------------------------------------------------------
print("\n" + "-"*80)
print(" 4. AUDITORÍA DE CONTACTOS (RES.PARTNER) ".center(80, "-"))
print("-" * 80)

cuit_type = env.ref('l10n_ar.it_cuit', raise_if_not_found=False)
domain_base = [('commercial_partner_id', '=', True)] if 'commercial_partner_id' in partner_fields else []

total_partners = env['res.partner'].search_count([('is_company', '=', True)])
partners_with_vat = env['res.partner'].search_count([('is_company', '=', True), ('vat', '!=', False)])

domain_customers = [('is_company', '=', True), ('customer_rank', '>', 0), ('vat', '!=', False)]
domain_suppliers = [('is_company', '=', True), ('supplier_rank', '>', 0), ('vat', '!=', False)]
total_customers = env['res.partner'].search_count(domain_customers)
total_suppliers = env['res.partner'].search_count(domain_suppliers)

print(f"[*] Empresas totales (is_company=True):              {total_partners:,}")
print(f"[*] Empresas con CUIT / Identificación fiscal:       {partners_with_vat:,}")
print(f"[*] Clientes activos con CUIT (customer_rank > 0):    {total_customers:,}")
print(f"[*] Proveedores activos con CUIT (supplier_rank > 0): {total_suppliers:,}")

# ----------------------------------------------------------------------
# 5. Estado actual de regímenes e impuestos en los contactos
# ----------------------------------------------------------------------
print("\n" + "-"*80)
print(" 5. REGÍMENES / IMPUESTOS ASIGNADOS A CONTACTOS ".center(80, "-"))
print("-" * 80)

if has_partner_tax_model:
    all_partner_taxes = env['l10n_ar.partner.tax'].search([('company_id', '=', company.id)])
    print(f"[*] Total registros en l10n_ar.partner.tax para la empresa: {len(all_partner_taxes):,}")
    
    # Agrupar por tipo de impuesto y ver vigencias
    taxes_grouped = {}
    for pt in all_partner_taxes:
        tname = pt.tax_id.name if pt.tax_id else 'Sin Impuesto'
        taxes_grouped[tname] = taxes_grouped.get(tname, 0) + 1
    
    for tname, cnt in sorted(taxes_grouped.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    - {tname:<45} : {cnt:,} contactos")

    # Muestra de 5 contactos con impuestos asignados
    sample_pt = all_partner_taxes[:5]
    if sample_pt:
        print("\n[*] Muestra de 5 asignaciones vigentes:")
        for pt in sample_pt:
            p_name = pt.partner_id.name
            cuit = pt.partner_id.vat
            t_name = pt.tax_id.name
            f_desde = pt.from_date or 'Indefinido'
            f_hasta = pt.to_date or 'Indefinido'
            print(f"    - Contacto: {p_name} (CUIT: {cuit}) | Impuesto: {t_name} | Desde: {f_desde} | Hasta: {f_hasta}")
else:
    print("[!] El modelo 'l10n_ar.partner.tax' no está presente.")
    # Verificar si se asignan en posiciones fiscales o campos propios
    fpos = env['account.fiscal.position'].search([('company_id', '=', company.id)])
    print(f"[*] Posiciones Fiscales existentes ({len(fpos)}):")
    for fp in fpos:
        print(f"    - ID {fp.id:3d} | {fp.name}")

print("\n" + "="*80)
print(" FIN DE AUDITORÍA ODOO ".center(80, "="))
print("="*80 + "\n")
