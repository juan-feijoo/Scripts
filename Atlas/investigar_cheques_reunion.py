# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE AUDITORÍA Y BÚSQUEDA DE CHEQUES DE LA REUNIÓN
================================================================================
Objetivo:
1. Localizar los 5 cheques indicados en la reunión con los montos exactos:
   - $ 1.415.214,29
   - $   685.504,16
   - $   414.072,03
   - $    43.939,27
   - $   422.272,46
2. Analizar en qué compañía están (Bulgheroni Group ID 1, 1066 S.A., etc.)
   y cuál es su estado actual (current_journal_id, operaciones, etc.).
3. Analizar los 11 cheques que actualmente figuran 'A la mano' en Bulgheroni Group
   y determinar si tienen movimientos de egreso, depósito o transferencias en contabilidad.
4. Mejorar la visualización del Número de Operación en los pagos creados
   (asignar move.name como payment.name para que no figure vacío ni como 'Borrador de pago').
================================================================================
"""

print("\n" + "=" * 135)
print("AUDITORÍA DE CHEQUES SEGÚN DEFINICIÓN DE LA REUNIÓN")
print("=" * 135)

CheckModel = env['l10n_latam.check']
PaymentModel = env['account.payment']
MoveModel = env['account.move']
LineModel = env['account.move.line']
CompanyModel = env['res.company']

target_montos = [
    1415214.29,
    685504.16,
    414072.03,
    43939.27,
    422272.46
]

# ------------------------------------------------------------------------------
# 1. BÚSQUEDA DE LOS 5 CHEQUES DE LA REUNIÓN EN TODAS LAS COMPAÑÍAS
# ------------------------------------------------------------------------------
print("\n[1] BÚSQUEDA DE LOS 5 CHEQUES DE LA REUNIÓN (EN TODAS LAS COMPAÑÍAS):")
print("-" * 135)

found_target_checks = CheckModel
for monto in target_montos:
    # Buscar por monto aproximado (+- 0.05) sin filtro de compañía
    chks = CheckModel.sudo().search([
        ('amount', '>=', monto - 0.05),
        ('amount', '<=', monto + 0.05),
    ])
    if chks:
        found_target_checks |= chks
        for c in chks:
            estado = "EN CARTERA (A la mano)" if c.current_journal_id else "EGRESADO / DEPOSITADO"
            print(f" -> ✅ Encontrado: ${c.amount:>12,.2f} | Nro: {c.name:<10} | Fecha: {c.payment_date} | Compañía: {c.company_id.name} (ID {c.company_id.id}) | Estado: {estado} | Diario: {c.current_journal_id.name if c.current_journal_id else 'Ninguno'}")
    else:
        # Si no lo encuentra por monto exacto, buscar en apuntes contables si existe ese importe
        lines = LineModel.sudo().search([
            ('credit', '>=', monto - 0.05),
            ('credit', '<=', monto + 0.05),
        ], limit=3)
        if lines:
            print(f" -> ⚠️ Cheque de ${monto:>12,.2f} no hallado en l10n_latam.check, pero SÍ hay apunte contable: {lines.mapped(lambda l: f'{l.move_id.name} ({l.company_id.name})')}")
        else:
            print(f" -> ❌ Cheque de ${monto:>12,.2f} NO encontrado en l10n_latam.check ni en apuntes contables.")

# ------------------------------------------------------------------------------
# 2. ANÁLISIS DE LOS 11 CHEQUES QUE ACTUALMENTE FIGURAN 'A LA MANO' EN COMPAÑÍA 1
# ------------------------------------------------------------------------------
print("\n[2] CENSO DE LOS 11 CHEQUES ACTUALMENTE 'A LA MANO' EN BULGHERONI GROUP S.A.:")
print("-" * 135)

current_on_hand_1 = CheckModel.search([
    ('company_id', '=', 1),
    ('current_journal_id', '!=', False)
], order="payment_date asc, id asc")

print(f"{'ID':<5} | {'NRO':<10} | {'FECHA':<10} | {'MONTO ($)':>14} | {'CLIENTE':<30} | {'¿TIENE EGRESO EN CONTABILIDAD?'}")
print("-" * 135)

for c in current_on_hand_1:
    p_name = c.payment_id.partner_id.name[:30] if c.payment_id and c.payment_id.partner_id else 'S/P'
    # Buscar si existe algún crédito en cuentas de valores por ese monto exacto
    cr_lines = LineModel.search([
        ('company_id', '=', 1),
        ('credit', '>=', c.amount - 0.01),
        ('credit', '<=', c.amount + 0.01),
        ('account_id.code', 'ilike', '1.1.1%')
    ])
    if cr_lines:
        egreso_str = f"SÍ: {cr_lines[0].move_id.name} (Conciliado: {cr_lines[0].reconciled})"
    else:
        # Buscar en cualquier cuenta
        cr_any = LineModel.search([
            ('company_id', '=', 1),
            ('credit', '>=', c.amount - 0.01),
            ('credit', '<=', c.amount + 0.01)
        ], limit=1)
        egreso_str = f"En otra cta: {cr_any.move_id.name}" if cr_any else "NO localizado en contabilidad"
    print(f"{c.id:<5} | {c.name:<10} | {str(c.payment_date)[:10]:<10} | {c.amount:>14,.2f} | {p_name:<30} | {egreso_str}")

# ------------------------------------------------------------------------------
# 3. CORRECCIÓN ESTÉTICA DE 'NÚMERO' EN OPERACIONES DE CHEQUES (QUITAR BORRADOR)
# ------------------------------------------------------------------------------
print("\n[3] REVISIÓN DE NÚMERO / DISPLAY_NAME EN PAGOS DE OPERACIÓN:")
print("-" * 135)

blank_name_pays = PaymentModel.search([
    ('company_id', '=', 1),
    ('name', '=', False),
    ('move_id', '!=', False)
])
print(f" -> Pagos asociados a asientos con campo 'name' vacío: {len(blank_name_pays)}")

for p in blank_name_pays:
    new_name = p.move_id.name or f"PAGO-{p.id}"
    env.cr.execute("UPDATE account_payment SET name = %s WHERE id = %s;", (new_name, p.id))
    print(f"    * Pago #{p.id} actualizado con nombre: '{new_name}' (Asiento: {p.move_id.name})")

env.cr.commit()
print("\n✅ Consulta y actualización de nombres finalizada.")
print("=" * 135 + "\n")
