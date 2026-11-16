# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 07: AJUSTE DEL CIRCUITO DE RETENCIONES Y PRUEBA DE PAGO
================================================================================
Propósito:
    1. Ajustar la Posición Fiscal "Responsable inscripto":
       - Corregir el impuesto por defecto de IIBB a 'IIBB WTH BA 0%' (ID 461).
    2. Asegurar que los contactos con CUIT tengan asignado el País (Argentina)
       y Responsabilidad AFIP (IVA Responsable Inscripto) para que la posición
       fiscal se auto-detecte siempre al seleccionarlos en pagos.
    3. Simular la orden de pago para verificar que Odoo auto-detecte la posición
       fiscal y cargue automáticamente la retención 'IIBB WTH BA 2.5%'.

Configuración:
    DRY_RUN = True  -> Simulación (rollback).
    DRY_RUN = False -> Aplica cambios definitivamente (commit).
================================================================================
"""

from odoo import fields
from datetime import date

# ==============================================================================
# CONTROL DE TRANSACCIÓN (DRY-RUN)
# ==============================================================================
DRY_RUN = False  # Modo real: aplica y confirma cambios en la base de datos

company = env.company
ba_state = env.ref('base.state_ar_b')
ar_country = env.ref('base.ar')
ri_afip = env.ref('l10n_ar.res_IVARI', raise_if_not_found=False)

print("\n" + "="*80)
print(f" AJUSTE DE CIRCUITO Y PRUEBA DE RETENCIÓN [DRY_RUN = {DRY_RUN}] ".center(80, "="))
print("="*80 + "\n")

# ------------------------------------------------------------------------------
# 1. Ajustar Posición Fiscal "Responsable inscripto"
# ------------------------------------------------------------------------------
base_tax_0 = env['account.tax'].search([
    ('company_id', '=', company.id),
    ('l10n_ar_withholding_payment_type', '=', 'supplier'),
    ('l10n_ar_state_id', '=', ba_state.id),
    ('amount', '=', 0.0)
], limit=1)

if not base_tax_0:
    base_tax_0 = env['account.tax'].browse(461)

print(f"[*] Impuesto plantilla base 0%: [{base_tax_0.id}] {base_tax_0.name}")

fpos = env['account.fiscal.position'].search([
    ('company_id', '=', company.id),
    ('name', 'ilike', 'responsable inscripto')
], limit=1)

if fpos:
    print(f"[*] Posición Fiscal encontrada: [{fpos.id}] {fpos.name}")
    for line in fpos.l10n_ar_tax_ids:
        dt = line.default_tax_id
        if line.tax_type == 'withholding' and dt.l10n_ar_state_id.id == ba_state.id:
            if dt.id != base_tax_0.id:
                print(f"    - [CORRECCIÓN] Cambiando impuesto default de IIBB en Pos. Fiscal de [{dt.id}] {dt.name} a [{base_tax_0.id}] {base_tax_0.name}")
                line.write({'default_tax_id': base_tax_0.id})
            else:
                print(f"    - [OK] La línea de IIBB ya tiene como default: [{dt.id}] {dt.name}")
else:
    print("[!] No se encontró la Posición Fiscal 'Responsable inscripto'.")

# ------------------------------------------------------------------------------
# 2. Corregir País en proveedores con CUIT
# ------------------------------------------------------------------------------
partners_no_country = env['res.partner'].search([
    ('vat', '!=', False),
    ('country_id', '=', False),
    ('is_company', '=', True)
])

print(f"\n[*] Proveedores con CUIT sin País asignado: {len(partners_no_country)}")
if partners_no_country:
    print(f"    - Asignando País 'Argentina' a {len(partners_no_country)} empresas...")
    partners_no_country.write({'country_id': ar_country.id})

# Verificar proveedor de prueba específico
partner = env['res.partner'].search([
    ('vat', '=', '30575019524'),
    ('is_company', '=', True)
], limit=1)

if not partner:
    partner = env['res.partner'].browse(2543)

print(f"\n[*] Proveedor de prueba: [{partner.id}] {partner.name} (CUIT: {partner.vat})")
if partner.country_id.id != ar_country.id:
    partner.write({'country_id': ar_country.id})
if ri_afip and partner.l10n_ar_afip_responsibility_type_id.id != ri_afip.id:
    partner.write({'l10n_ar_afip_responsibility_type_id': ri_afip.id})

print(f"    - País: {partner.country_id.name}")
print(f"    - Responsabilidad AFIP: {partner.l10n_ar_afip_responsibility_type_id.name}")

# Test de auto-detección de Posición Fiscal
detected_fpos = env['account.fiscal.position'].with_context(
    l10n_ar_withholding=True, active_test=True
)._get_fiscal_position(partner)
print(f"    - [CHECK AUTO-DETECCIÓN] Posición fiscal detectada: {detected_fpos.name if detected_fpos else 'NINGUNA'}")

# ------------------------------------------------------------------------------
# 3. Simulación de Orden de Pago
# ------------------------------------------------------------------------------
print("\n" + "-"*80)
print(" SIMULACIÓN DE ORDEN DE PAGO Y CÁLCULO DE RETENCIÓN ".center(80, "-"))
print("-" * 80)

bank_journal = env['account.journal'].search([
    ('company_id', '=', company.id),
    ('type', 'in', ['bank', 'cash'])
], limit=1)

payment_method_line = bank_journal.outbound_payment_method_line_ids[:1]

payment = env['account.payment'].new({
    'company_id': company.id,
    'payment_type': 'outbound',
    'partner_type': 'supplier',
    'partner_id': partner.id,
    'journal_id': bank_journal.id,
    'payment_method_line_id': payment_method_line.id if payment_method_line else False,
    'date': fields.Date.today(),
})

payment._compute_fiscal_position_id()
payment._compute_l10n_ar_withholding_line_ids()

print(f"[*] Posición Fiscal en el pago: {payment.l10n_ar_fiscal_position_id.name or 'NINGUNA'}")
print(f"[*] Líneas de retención detectadas en el pago ({len(payment.l10n_ar_withholding_line_ids)}):")

for wline in payment.l10n_ar_withholding_line_ids:
    tax = wline.tax_id
    base_val = getattr(wline, 'base_amount', 0.0)
    amt_val = getattr(wline, 'amount', 0.0)
    print(f"    -> Retención: [{tax.id}] {tax.name:<25} | Alícuota: {tax.amount:>5.2f}% | Base: ${base_val:,.2f} | Retención: ${amt_val:,.2f}")

print("\n" + "="*80)
if DRY_RUN:
    env.cr.rollback()
    print(" [DRY_RUN = True] Simulación completada sin persistir en BD. ".center(80, "="))
    print(" Cambia DRY_RUN = False para aplicar la corrección de país y posición fiscal.".center(80))
else:
    env.cr.commit()
    print(" [DRY_RUN = False] Configuración aplicada y confirmada en BD. ".center(80, "="))
print("="*80 + "\n")
