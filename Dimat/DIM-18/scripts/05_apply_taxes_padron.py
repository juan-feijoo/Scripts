# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 05: APLICACIÓN DE REGÍMENES E IMPUESTOS ARBA EN CONTACTOS
================================================================================
Propósito:
    1. Asegurar la existencia de los impuestos de Retención ARBA en account.tax
       para las alícuotas correspondientes (2.5%, 3.0%, 3.5%, 4.0%, 5.0%, 6.0%)
       a partir del impuesto plantilla ID 461 (IIBB WTH BA 0%).
    2. Asignar los regímenes e impuestos en res.partner a través del modelo
       l10n_ar.partner.tax con vigencia 01/11/2026 al 30/11/2026.
    3. Aplicar la regla de Droguerías (RN 42/12): alícuota mínima de retención 2.50%.

Configuración:
    DRY_RUN = True  -> Modo simulación (hace rollback al finalizar, 100% seguro).
    DRY_RUN = False -> Modo real (guarda cambios con commit).

Ejecución en Odoo Shell (Odoo.sh):
    python3 odoo-bin shell -d $PGDATABASE < scripts/05_apply_taxes_padron.py
================================================================================
"""

import re
import json
import gzip
import base64
from datetime import date

# ==============================================================================
# PARÁMETRO DE CONTROL DE TRANSACCIÓN (DRY-RUN)
# ==============================================================================
DRY_RUN = False  # Modo real: aplica y confirma cambios en la base de datos
FROM_DATE = date(2026, 11, 1)
TO_DATE = date(2026, 11, 30)

print("\n" + "="*80)
print(f" APLICACIÓN DE REGÍMENES ARBA 11/2026 [DRY_RUN = {DRY_RUN}] ".center(80, "="))
print("="*80 + "\n")

company = env.company
print(f"[*] Compañía: [{company.id}] {company.name}")
print(f"[*] Período de vigencia: {FROM_DATE} al {TO_DATE}")

# ------------------------------------------------------------------------------
# 1. Cargar datos de los 802 contactos procesados
# ------------------------------------------------------------------------------
EMBEDDED_B64 = """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"""

import os
if os.path.exists('matched_partners_padron.json'):
    print("[*] Cargando datos desde 'matched_partners_padron.json'...")
    with open('matched_partners_padron.json', 'r', encoding='utf-8') as f:
        raw_list = json.load(f)
    partners_data = {}
    for p in raw_list:
        ret = p.get('retencion')
        if ret and ret.get('ali_final', 0) > 0:
            partners_data[str(p['partner_id'])] = {
                'vat': p['vat'],
                'name': p['name'],
                'ali_final': ret['ali_final'],
                'ali_orig': ret['ali_orig'],
                'rule_applied': ret['rule_applied']
            }
else:
    print("[*] Cargando datos embebidos en el script (fallback)...")
    decomp = gzip.decompress(base64.b64decode(EMBEDDED_B64)).decode('utf-8')
    partners_data = json.loads(decomp)

print(f"[*] Total contactos a configurar: {len(partners_data):,}")

# ------------------------------------------------------------------------------
# 2. Localizar impuesto plantilla base (ID 461 o buscar por criterio)
# ------------------------------------------------------------------------------
ba_state = env.ref('base.state_ar_b')
base_tax = env['account.tax'].search([
    ('company_id', '=', company.id),
    ('l10n_ar_withholding_payment_type', '=', 'supplier'),
    ('l10n_ar_state_id', '=', ba_state.id),
    ('amount', '=', 0.0)
], limit=1)

if not base_tax:
    base_tax = env['account.tax'].browse(461)

if not base_tax.exists():
    raise Exception("ERROR: No se encontró el impuesto plantilla base de retención ARBA (IIBB WTH BA 0%).")

print(f"[*] Impuesto plantilla base: [{base_tax.id}] {base_tax.name} ({base_tax.amount}%)")

# ------------------------------------------------------------------------------
# 3. Asegurar existencia de los impuestos para cada alícuota requerida
# ------------------------------------------------------------------------------
distinct_rates = sorted(list(set(item['ali_final'] for item in partners_data.values())))
print(f"[*] Alícuotas requeridas: {distinct_rates}")

tax_by_rate = {}
for rate in distinct_rates:
    # Buscar si ya existe el impuesto con esa alícuota
    domain = [
        ('company_id', '=', company.id),
        ('l10n_ar_withholding_payment_type', '=', 'supplier'),
        ('l10n_ar_state_id', '=', ba_state.id),
        ('amount', '=', rate)
    ]
    tax = env['account.tax'].with_context(active_test=False).search(domain, limit=1)
    if tax:
        if not tax.active:
            print(f"    - Activando impuesto existente: [{tax.id}] {tax.name}")
            tax.active = True
        tax_by_rate[rate] = tax
        print(f"    - [OK] Impuesto encontrado: [{tax.id}] {tax.name} ({tax.amount}%)")
    else:
        # Clonar desde plantilla base
        new_name = f"IIBB WTH BA {rate}%"
        print(f"    - [CREAR] Creando impuesto: '{new_name}' (alícuota: {rate}%) desde plantilla [{base_tax.id}]...")
        tax = base_tax.copy(default={
            'sequence': 10,
            'amount': rate,
            'active': True,
            'name': new_name,
        })
        tax_by_rate[rate] = tax
        print(f"    - [CREADO] Nuevo impuesto ID: [{tax.id}] {tax.name}")

# ------------------------------------------------------------------------------
# 4. Asignar impuestos en contactos (l10n_ar.partner.tax)
# ------------------------------------------------------------------------------
print("\n" + "-"*80)
print(" ASIGNACIÓN DE REGÍMENES A CONTACTOS ".center(80, "-"))
print("-" * 80)

PartnerTax = env['l10n_ar.partner.tax']
created_count = 0
updated_count = 0
overlap_closed_count = 0
rule_boosted_count = 0

partner_ids = [int(pid) for pid in partners_data.keys()]
partners = env['res.partner'].browse(partner_ids)
partner_by_id = {p.id: p for p in partners}

for pid_str, info in partners_data.items():
    pid = int(pid_str)
    partner = partner_by_id.get(pid)
    if not partner or not partner.exists():
        continue

    rate = info['ali_final']
    target_tax = tax_by_rate[rate]
    rule_applied = info['rule_applied']
    if rule_applied:
        rule_boosted_count += 1
        ref_text = f"ARBA RN 42/12 Droguerías (Orig: {info['ali_orig']}%) - 11/2026"
    else:
        ref_text = f"ARBA RN 42/12 - 11/2026"

    # Verificar asignaciones existentes para este partner en el mismo grupo de impuestos y jurisdicción
    existing_records = PartnerTax.search([
        ('partner_id', '=', partner.id),
        ('tax_id.tax_group_id', '=', target_tax.tax_group_id.id),
        ('tax_id.l10n_ar_state_id', '=', ba_state.id),
        ('tax_id.l10n_ar_withholding_payment_type', '=', 'supplier')
    ])

    # Buscar si ya tiene exactamente un registro para este mismo período (11/2026)
    exact_period_record = existing_records.filtered(
        lambda r: r.from_date == FROM_DATE and r.to_date == TO_DATE
    )

    if exact_period_record:
        # Ya existe para este mes: actualizar impuesto si difiere
        rec = exact_period_record[0]
        if rec.tax_id.id != target_tax.id or rec.ref != ref_text:
            rec.write({
                'tax_id': target_tax.id,
                'ref': ref_text
            })
            updated_count += 1
    else:
        # Cerrar registros anteriores abiertos que se solapen con FROM_DATE (2026-11-01)
        overlapping = existing_records.filtered(
            lambda r: (not r.to_date or r.to_date >= FROM_DATE) and (not r.from_date or r.from_date < FROM_DATE)
        )
        for ov in overlapping:
            # Cerrar al día anterior
            ov.write({'to_date': date(2026, 10, 31)})
            overlap_closed_count += 1

        # Crear nuevo registro para el período
        PartnerTax.create({
            'partner_id': partner.id,
            'tax_id': target_tax.id,
            'from_date': FROM_DATE,
            'to_date': TO_DATE,
            'ref': ref_text,
            'company_id': company.id
        })
        created_count += 1

print(f"[*] Resumen de operaciones:")
print(f"    - Registros nuevos creados en l10n_ar.partner.tax: {created_count:,}")
print(f"    - Registros existentes actualizados:             {updated_count:,}")
print(f"    - Vigencias anteriores cerradas (al 31/10/2026): {overlap_closed_count:,}")
print(f"    - Contactos con regla Droguerías (piso 2.50%):   {rule_boosted_count:,}")

# ------------------------------------------------------------------------------
# 5. Muestra de verificación
# ------------------------------------------------------------------------------
sample_check = PartnerTax.search([
    ('company_id', '=', company.id),
    ('from_date', '=', FROM_DATE),
    ('to_date', '=', TO_DATE)
], limit=5)

print("\n[*] Muestra de 5 asignaciones verificadas:")
for sc in sample_check:
    print(f"    - [{sc.partner_id.id}] {sc.partner_id.name[:35]:<35} | CUIT: {sc.partner_id.vat} | Impuesto: {sc.tax_id.name:<20} | Ref: {sc.ref}")

# ------------------------------------------------------------------------------
# 6. Control de Transacción (Commit o Rollback)
# ------------------------------------------------------------------------------
print("\n" + "="*80)
if DRY_RUN:
    env.cr.rollback()
    print(" [SIMULACIÓN / DRY-RUN EXITOSO] ".center(80, "="))
    print(" NO SE MODIFICÓ LA BASE DE DATOS (env.cr.rollback ejecutado).".center(80))
    print(" Para aplicar los cambios definitivamente, edita el script y pon: DRY_RUN = False".center(80))
else:
    env.cr.commit()
    print(" [APLICACIÓN REAL CONFIRMADA] ".center(80, "="))
    print(" TODOS LOS CAMBIOS FUERON GUARDADOS EXITOSAMENTE (env.cr.commit ejecutado).".center(80))
print("="*80 + "\n")
