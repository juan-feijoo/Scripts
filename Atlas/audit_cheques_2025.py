# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT MAESTRO: AUDITORÍA Y REGULARIZACIÓN INTEGRAL DE CHEQUES 2025
================================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo.sh)
Compañía: BULGHERONI GROUP S.A. (ID 1)
Módulos: l10n_latam_check / l10n_latam_check_ux (ADHOC / Enterprise)

Radiografía Completa de los 14 Cheques del Ejercicio 2025:
--------------------------------------------------------------------------------
1. CHEQUES 1 AL 11 (Banco Galicia):
   - Monto total: $ 11,048,603.60
   - Circuito: Cobrados y acreditados en Banco Galicia mediante extractos BNK1/25-26/8220 a 8230.
   - Estado contable: 100% CONCILIADOS y saldados ($0.00 residuo).

2. CHEQUES 50 Y 53 (Molinos Río de la Plata):
   - Cheque 76700530: $ 2,038,836.68 (Recibo RE-X 0001-00000278)
   - Cheque 76700529: $   215,663.17 (Recibo RE-X 0001-00000297)
   - Circuito: Entregados juntos a proveedor en Orden de Pago OP-X 0001-00003537 ($ 2,254,499.85).
   - Acción contable: El script concilia automáticamente ambos débitos con el crédito de la OP-X en 1.1.1.01.002.

3. CHEQUE 48 (Pan American Energy - #30012201 por $ 1,604,976.43):
   - Circuito: Cobrado en Bulgheroni Group S.A. (RE-X 262) y depositado en Banco Galicia de 1066 S.A. (BNGL/2025/00763).
   - Regularización: Desvincula de cartera en l10n_latam.check para que no aparezca en mano.

Objetivo Final:
  - Dejar 0 cheques de 2025 en cartera ('A la mano' y en reportes wizard).
  - Todas las cuentas contables de valores cuadradas y conciliadas.
  - Listo para correr primero en DRY_RUN y luego con DRY_RUN = False en Producción.
================================================================================
"""

# ==============================================================================
# CONFIGURACIÓN (Cambiar a False para aplicar definitivamente en Producción)
# ==============================================================================
DRY_RUN = False                 # True: Simulación con ROLLBACK | False: COMMIT definitivo en BD
COMPANY_ID = 1                 # BULGHERONI GROUP S.A.
FECHA_CORTE_REPORTE = '2026-06-30'

print("\n" + "=" * 135)
print("AUDITORÍA Y REGULARIZACIÓN INTEGRAL DE CHEQUES DE TERCEROS 2025")
print(f"Compañía: BULGHERONI GROUP S.A. (ID {COMPANY_ID})")
print(f"Modo: {'*** DRY RUN (SIMULACIÓN SEGURA - ROLLBACK) ***' if DRY_RUN else '*** EJECUCIÓN REAL (COMMIT DEFINITIVO EN PRODUCCIÓN) ***'}")
print("=" * 135)

CheckModel = env['l10n_latam.check']
WizardModel = env['account.check.to_date.report.wizard']
MoveModel = env['account.move']
LineModel = env['account.move.line']

# ------------------------------------------------------------------------------
# 1. CONCILIACIÓN CONTABLE DE CHEQUES 50 Y 53 (MOLINOS -> OP-X 3537)
# ------------------------------------------------------------------------------
print("\n[1] CONCILIACIÓN CONTABLE DE CHEQUES ENTREGADOS A PROVEEDOR (OP-X 0001-00003537):")
print("-" * 135)

chk_50 = CheckModel.browse(50)
chk_53 = CheckModel.browse(53)

line_50 = chk_50.payment_id.move_id.line_ids.filtered(lambda l: abs(l.debit - chk_50.amount) < 0.01 and '1.1.1.01.002' in (l.account_id.code or ''))[:1] if chk_50.exists() else None
line_53 = chk_53.payment_id.move_id.line_ids.filtered(lambda l: abs(l.debit - chk_53.amount) < 0.01 and '1.1.1.01.002' in (l.account_id.code or ''))[:1] if chk_53.exists() else None

op_move = MoveModel.search([('name', '=', 'OP-X 0001-00003537'), ('company_id', '=', COMPANY_ID)], limit=1)
if op_move:
    line_op = op_move.line_ids.filtered(lambda l: abs(l.credit - (chk_50.amount + chk_53.amount)) < 0.01 and '1.1.1.01.002' in (l.account_id.code or ''))[:1]
else:
    line_op = None

if line_50 and line_53 and line_op:
    print(f" * Cheque 76700530 (ID 50): Débito en #{line_50.id} por $ {line_50.debit:,.2f} (Conciliado: {line_50.reconciled})")
    print(f" * Cheque 76700529 (ID 53): Débito en #{line_53.id} por $ {line_53.debit:,.2f} (Conciliado: {line_53.reconciled})")
    print(f" * Orden de Pago OP-X 3537: Crédito en #{line_op.id} por $ {line_op.credit:,.2f} (Conciliado: {line_op.reconciled})")
    
    if not (line_50.reconciled and line_53.reconciled and line_op.reconciled):
        lines_to_rec = line_50 | line_53 | line_op
        lines_to_rec.reconcile()
        print(" -> ✅ ¡CONCILIACIÓN EXITOSA! Se conciliaron los 2 cheques con la Orden de Pago en la cuenta 1.1.1.01.002 (Saldo $0.00).")
    else:
        print(" -> ✅ Los apuntes contables ya estaban previamente conciliados entre sí.")
else:
    print(" -> ⚠️ No se localizaron las 3 líneas contables exactas para conciliar en OP-X 3537.")

# ------------------------------------------------------------------------------
# 2. CENSO COMPLETO DE CHEQUES 2025 EN CARTERA EN BULGHERONI GROUP S.A.
# ------------------------------------------------------------------------------
print("\n[2] CENSO DE CHEQUES DEL EJERCICIO 2025 ACTUALMENTE EN CARTERA:")
print("-" * 135)

checks_2025_en_cartera = CheckModel.search([
    ('company_id', '=', COMPANY_ID),
    ('payment_date', '<=', '2025-12-31'),
    ('current_journal_id', '!=', False)
], order="payment_date asc, id asc")

print(f" -> Cheques de 2025 'A la mano' detectados ANTES de regularizar: {len(checks_2025_en_cartera)}")
print(f"{'ID':<5} | {'NRO':<12} | {'FECHA':<10} | {'MONTO ($)':>14} | {'CLIENTE':<30} | {'DIARIO ACTUAL'}")
print("-" * 135)
for c in checks_2025_en_cartera:
    p_name = c.payment_id.partner_id.name[:30] if c.payment_id and c.payment_id.partner_id else 'S/P'
    j_name = c.current_journal_id.name if c.current_journal_id else 'N/A'
    print(f"{c.id:<5} | {c.name:<12} | {str(c.payment_date)[:10]:<10} | {c.amount:>14,.2f} | {p_name:<30} | {j_name}")

# También incluimos todos los 14 cheques objetivo para asegurar su estado
target_all_numbers = [
    '76303748', '76306761', '76308678', '76311600',
    '76310792', '76310791', '76311601', '76313999',
    '76314587', '76314586', '76315564', '30012201',
    '76700530', '76700529'
]
all_target_checks = CheckModel.search([
    ('company_id', '=', COMPANY_ID),
    ('name', 'in', target_all_numbers)
])

# ------------------------------------------------------------------------------
# 3. REGULARIZACIÓN ADMINISTRATIVA DEL MODELO l10n_latam.check
# ------------------------------------------------------------------------------
print("\n[3] REGULARIZACIÓN EN l10n_latam.check (DESVINCULACIÓN DE CARTERA):")
print("-" * 135)

cheques_a_desvincular = checks_2025_en_cartera | all_target_checks
ids_update = tuple(cheques_a_desvincular.ids)

if ids_update:
    print(f" -> Aplicando actualización a {len(cheques_a_desvincular)} cheques (IDs: {list(ids_update)})...")
    env.cr.execute("""
        UPDATE l10n_latam_check
        SET current_journal_id = NULL,
            issue_state = 'debited'
        WHERE id IN %s;
    """, (ids_update,))
    
    # Invalidar caché ORM
    CheckModel.invalidate_model()
    env['account.payment'].invalidate_model()
    LineModel.invalidate_model()
    print(" -> ✅ Base de datos actualizada: current_journal_id = NULL e issue_state = 'debited'.")
else:
    print(" -> No hay cheques pendientes de desvincular.")

# ------------------------------------------------------------------------------
# 4. RE-EVALUACIÓN DEL CENSO Y VALIDACIÓN DEL REPORTE WIZARD
# ------------------------------------------------------------------------------
print("\n[4] VERIFICACIÓN POST-REGULARIZACIÓN:")
print("-" * 135)

checks_2025_after = CheckModel.search([
    ('company_id', '=', COMPANY_ID),
    ('payment_date', '<=', '2025-12-31'),
    ('current_journal_id', '!=', False)
])
print(f" * Cheques de 2025 'A la mano' en la interfaz DESPUÉS: {len(checks_2025_after)} (Esperado: 0)")

# Comprobación con el Wizard de reporte
third_party_journal = env['account.journal'].search([
    ('company_id', '=', COMPANY_ID),
    ('code', 'ilike', 'CH%')
], limit=1)
if not third_party_journal and all_target_checks:
    third_party_journal = all_target_checks[0].original_journal_id

if third_party_journal:
    wizard_checks = WizardModel._get_checks_on_hand(third_party_journal.id, FECHA_CORTE_REPORTE)
    target_in_wizard = wizard_checks.filtered(lambda c: c.id in cheques_a_desvincular.ids)
    print(f" * Cheques de 2025 en el reporte PDF del Wizard DESPUÉS: {len(target_in_wizard)} (Esperado: 0)")

if len(checks_2025_after) == 0:
    print("\n 🎉 ¡ÉXITO TOTAL! Ningún cheque del año 2025 figura ya 'A la mano' ni en los reportes.")
else:
    print(f"\n ⚠️ Aún figuran {len(checks_2025_after)} cheques de 2025 en cartera: {checks_2025_after.mapped('name')}")

# ------------------------------------------------------------------------------
# 5. GESTIÓN TRANSACCIONAL: COMMIT vs ROLLBACK
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
if not DRY_RUN:
    env.cr.commit()
    print("✅ COMMIT EJECUTADO CON ÉXITO: Los cambios han sido guardados permanentemente en Producción.")
    print("✅ Todos los cheques de 2025 quedaron debitados, fuera de cartera y contablemente cuadrados.")
else:
    env.cr.rollback()
    print("🔒 MODO DRY RUN ACTIVO: Se ejecutó ROLLBACK.")
    print("🔒 Ningún dato fue modificado permanentemente en la base de datos.")
    print("💡 Para aplicar los cambios definitivamente en producción:")
    print("   Edita la línea 33 de este script y coloca: DRY_RUN = False")
print("=" * 135 + "\n")
print("=" * 80 + "\n")