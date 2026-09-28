# -*- coding: utf-8 -*-
"""
================================================================================
REGULARIZACIÓN DEFINITIVA DE CHEQUES DE TERCEROS 2025 (l10n_latam.check)
================================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo.sh)
Módulo: l10n_latam_check / l10n_latam_check_ux (ADHOC)
Reporte: account.check.to_date.report.wizard (l10n_latam_check_ux.checks_to_date)

Diagnóstico Final Confirmado:
  1. 11 cheques fueron debitados y conciliados en Banco Galicia (asientos BNK1/25-26/8220 a 8230)
     mediante extracto bancario (Statement Line).
  2. Al conciliar por extracto, Odoo no crea account.payment, dejando 'current_journal_id' en 69.
  3. Comprobado en vivo: vaciar 'current_journal_id = NULL' y asignar 'issue_state = debited'
     elimina de inmediato los cheques del 'Listado de cheques pendientes'.
  4. Cheque 12 (30012201 por $ 1,604,976.43): se audita si tiene asiento bancario asociado.
================================================================================
"""

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = True              # True = Simulación con ROLLBACK | False = COMMIT permanente en BD
INCLUDE_CHECK_12 = True     # True = Regulariza los 12 cheques | False = Solo los 11 conciliados

TARGET_NUMBERS = [
    '76303748', '76306761', '76308678', '76311600',
    '76310792', '76310791', '76311601', '76313999',
    '76314587', '76314586', '76315564', '30012201'
]

print("\n" + "=" * 120)
print("AUDITORIA Y REGULARIZACION DEFINITIVA DE CHEQUES 2025")
print(f"Modo: {'*** DRY RUN (SIMULACIÓN SEGURA - ROLLBACK) ***' if DRY_RUN else '*** EJECUCIÓN REAL (COMMIT DEFINITIVO EN BD) ***'}")
print("=" * 120)

CheckModel = env['l10n_latam.check']
WizardModel = env['account.check.to_date.report.wizard']
cheques = CheckModel.search([('name', 'in', TARGET_NUMBERS)], order="payment_date asc, id asc")

print(f"\n[1] Cheques objetivo encontrados: {len(cheques)} de 12.")

# ------------------------------------------------------------------------------
# 2. AUDITORÍA CONTABLE Y RASTREO DEL CHEQUE 12
# ------------------------------------------------------------------------------
print("\n[2] AUDITORÍA CONTABLE DE LOS 12 CHEQUES:")
print("-" * 120)
print(f"{'ID':<5} | {'NRO':<10} | {'FECHA':<10} | {'MONTO':>13} | {'ASIENTO COBRO':<20} | {'ASIENTO DÉBITO BANCO':<22} | DIAGNOSTICO")
print("-" * 120)

cheques_11_ok = []
cheque_12 = None

for chk in cheques:
    # Buscar apunte del cheque en el cobro
    orig_move = chk.payment_id.move_id
    line_chk = orig_move.line_ids.filtered(lambda l: l.account_id.code == '1.1.1.01.002' and l.debit > 0)[:1]
    
    # Asiento de contraparte
    debit_str = "SIN_CONCILIAR"
    is_ok = False
    if line_chk and line_chk.reconciled:
        counterparts = (line_chk.matched_credit_ids.mapped('credit_move_id.move_id') + line_chk.matched_debit_ids.mapped('debit_move_id.move_id')).filtered(lambda m: m != orig_move)
        if counterparts:
            debit_str = counterparts[0].name
            is_ok = True
    elif line_chk and line_chk.amount_residual < 0.01:
        debit_str = "SALDADO"
        is_ok = True

    if is_ok:
        diag = "CONTAB_OK (Conciliado Banco)"
        cheques_11_ok.append(chk)
    else:
        diag = f"SALDO_PENDIENTE (${chk.amount:,.2f})"
        cheque_12 = chk

    orig_str = orig_move.name if orig_move else 'N/A'
    chk_date = str(chk.payment_date or chk.date or '')[:10]
    print(f"{chk.id:<5} | {chk.name:<10} | {chk_date:<10} | {chk.amount:>13,.2f} | {orig_str:<20} | {debit_str:<22} | {diag}")

print("-" * 120)

# Búsqueda específica para Cheque 12 por si existe el apunte con el importe de $ 1,604,976.43
if cheque_12:
    print(f"\n[+] RASTREO CONTABLE CHEQUE 12 ({cheque_12.name} por $ {cheque_12.amount:,.2f}):")
    other_lines = env['account.move.line'].search([
        ('credit', '=', cheque_12.amount),
        ('move_id.state', '=', 'posted')
    ])
    if other_lines:
        print(f" -> Encontrados apuntes con crédito de $ {cheque_12.amount:,.2f} en otros asientos:")
        for ol in other_lines:
            print(f"    * Line ID {ol.id} | Asiento: {ol.move_id.name} | Cuenta: {ol.account_id.code} - {ol.account_id.name} | Fecha: {ol.date} | Diario: {ol.journal_id.name}")
            # Si está en la cuenta de cheques pero no conciliado, conciliarlo
            if ol.account_id.code == '1.1.1.01.002' and not ol.reconciled:
                orig_l = cheque_12.payment_id.move_id.line_ids.filtered(lambda l: l.account_id.code == '1.1.1.01.002' and l.debit > 0)[:1]
                if orig_l and not orig_l.reconciled:
                    (orig_l + ol).reconcile()
                    print(f"    └─ ✅ ¡Conciliación contable ejecutada con éxito entre Line {orig_l.id} y Line {ol.id}!")
    else:
        print(f" -> No se encontró ningún apunte con crédito exacto de $ {cheque_12.amount:,.2f}. El cheque permanece con saldo contable abierto.")

# ------------------------------------------------------------------------------
# 3. VERIFICACIÓN EN VIVO CON EL REPORTE ANTES DE REGULARIZAR
# ------------------------------------------------------------------------------
print("\n[3] CONSULTANDO EL REPORTE 'Listado de cheques pendientes' (Wizard):")
journal_target = cheques[0].original_journal_id
checks_before = WizardModel._get_checks_on_hand(journal_target.id, '2026-06-30')
target_before = checks_before.filtered(lambda c: c.id in cheques.ids)
print(f" - Cheques de la lista en el reporte ANTES: {len(target_before)} de 12.")

# ------------------------------------------------------------------------------
# 4. REGULARIZACIÓN (DESVINCULACIÓN DE CARTERA + ESTADO DEBITADO)
# ------------------------------------------------------------------------------
cheques_a_modificar = cheques if INCLUDE_CHECK_12 else CheckModel.browse([c.id for c in cheques_11_ok])
ids_a_modificar = tuple(cheques_a_modificar.ids)

print(f"\n[4] APLICANDO REGULARIZACIÓN A {len(cheques_a_modificar)} CHEQUES (IDs: {cheques_a_modificar.ids}):")

# Actualización directa a nivel de base de datos para anular current_journal_id y asignar 'debited'
env.cr.execute("""
    UPDATE l10n_latam_check
    SET current_journal_id = NULL,
        issue_state = 'debited'
    WHERE id IN %s;
""", (ids_a_modificar,))

# También vaciamos el diario actual en el pago origen si correspondiera
pay_ids = tuple(cheques_a_modificar.mapped('payment_id').ids)
if pay_ids:
    env.cr.execute("""
        UPDATE account_payment
        SET l10n_latam_check_current_journal_id = NULL
        WHERE id IN %s;
    """, (pay_ids,))

# Invalidar caché del ORM para que reconozca los valores de PostgreSQL
CheckModel.invalidate_model()
env['account.payment'].invalidate_model()

# ------------------------------------------------------------------------------
# 5. RE-EVALUACIÓN DEL REPORTE DESPUÉS DE LA REGULARIZACIÓN
# ------------------------------------------------------------------------------
print("\n[5] RE-EVALUACIÓN CON EL REPORTE 'Listado de cheques pendientes':")
checks_after = WizardModel._get_checks_on_hand(journal_target.id, '2026-06-30')
target_after = checks_after.filtered(lambda c: c.id in cheques.ids)
print(f" - Cheques de la lista en el reporte DESPUÉS: {len(target_after)} (Esperado: 0)")

if len(target_after) == 0:
    print(" 🎉 ¡PERFECTO! Ninguno de los 12 cheques figura ya en el reporte de cheques pendientes.")
else:
    print(f" ⚠️ Aún figuran {len(target_after)} cheques en el reporte: {target_after.mapped('name')}")

# ------------------------------------------------------------------------------
# 6. COMMIT vs ROLLBACK
# ------------------------------------------------------------------------------
if not DRY_RUN:
    env.cr.commit()
    print("\n" + "=" * 120)
    print("✅ COMMIT EJECUTADO CON ÉXITO: Los cambios han sido guardados permanentemente en la base de datos.")
    print("=" * 120 + "\n")
else:
    env.cr.rollback()
    print("\n" + "=" * 120)
    print("🔒 MODO DRY RUN ACTIVO: Se ejecutó ROLLBACK.")
    print("🔒 Ningún dato fue modificado permanentemente en la base de datos.")
    print("💡 Para aplicar los cambios definitivamente en producción:")
    print("   Edita la línea 20 de este script y coloca: DRY_RUN = False")
    print("=" * 120 + "\n")
print("=" * 80 + "\n")