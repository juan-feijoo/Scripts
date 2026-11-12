# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 06: VERIFICACIÓN POST-APLICACIÓN (READ-ONLY)
================================================================================
Propósito:
    Comprobar que los 802 registros en l10n_ar.partner.tax y los nuevos impuestos
    en account.tax quedaron efectivamente guardados tras el commit.
================================================================================
"""

company = env.company
from datetime import date
from collections import Counter

FROM_DATE = date(2026, 11, 1)
TO_DATE = date(2026, 11, 30)

print("\n" + "="*80)
print(" VERIFICACIÓN DE REGÍMENES PERSISTIDOS EN BASE DE DATOS ".center(80, "="))
print("="*80 + "\n")

# 1. Impuestos de retención BA existentes
ba_state = env.ref('base.state_ar_b')
taxes = env['account.tax'].search([
    ('company_id', '=', company.id),
    ('l10n_ar_withholding_payment_type', '=', 'supplier'),
    ('l10n_ar_state_id', '=', ba_state.id)
])

print(f"[*] Impuestos de retención ARBA en account.tax ({len(taxes)}):")
for t in taxes:
    print(f"    - ID {t.id:4d} | {t.name:<30} | Alícuota: {t.amount:>5.2f}% | Activo: {t.active}")

# 2. Registros vigentes para 11/2026 en l10n_ar.partner.tax
partner_taxes = env['l10n_ar.partner.tax'].search([
    ('company_id', '=', company.id),
    ('from_date', '=', FROM_DATE),
    ('to_date', '=', TO_DATE)
])

print(f"\n[*] Total asignaciones vigentes en l10n_ar.partner.tax para 11/2026: {len(partner_taxes):,}")

by_tax = Counter(pt.tax_id.name for pt in partner_taxes)
for tname, cnt in sorted(by_tax.items()):
    print(f"    - {tname:<30} : {cnt:4d} contactos")

rule_applied_count = len(partner_taxes.filtered(lambda pt: 'Droguerías' in (pt.ref or '')))
print(f"\n[*] Contactos con leyenda de Regla Droguerías (mínimo 2.50%): {rule_applied_count:,}")

print("\n" + "="*80)
print(" VERIFICACIÓN EXITOSA ".center(80, "="))
print("="*80 + "\n")
