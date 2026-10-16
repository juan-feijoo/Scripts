# -*- coding: utf-8 -*-
"""
Script de Regularización: Conciliación de Cheques de Terceros y Cambio de Estado a 'paid'
Ticket: AG-3
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo.sh)
Configuración: DRY_RUN = True por defecto para pruebas seguras
"""

# IMPORTANTE: Cambiar a False únicamente tras verificar la simulación en DRY_RUN
DRY_RUN = True

def regularizar_pagos_cheques(env, target_payment_ids=None):
    print("=" * 90)
    print("REGULARIZACIÓN DE PAGOS CON CHEQUES DE TERCEROS")
    print(f"MODO: {'*** DRY-RUN (SIMULACIÓN - SIN CAMBIOS REALES) ***' if DRY_RUN else '*** MODO ESCRITURA EN BASE DE DATOS ***'}")
    print("=" * 90)
    
    Payment = env['account.payment']
    
    # Si no se pasan IDs específicos, buscar todos los que estén en in_process con cheques de terceros
    if target_payment_ids:
        payments = Payment.browse(target_payment_ids)
    else:
        payments = Payment.search([
            ('payment_method_code', '=', 'out_third_party_checks'),
            ('state', '=', 'in_process')
        ])
        
    print(f"Pagos a procesar: {len(payments)}")
    
    for pay in payments:
        print(f"\n--- Procesando Pago ID: {pay.id} [{pay.name}] ---")
        print(f"Estado actual: {pay.state} | is_reconciled: {pay.is_reconciled} | is_matched: {pay.is_matched}")
        
        # Buscar la línea de salida del cheque en el asiento del pago
        check_account = pay.outstanding_account_id
        if not check_account:
            print(f"  [!] El pago {pay.id} no tiene outstanding_account_id configurada.")
            continue
            
        out_lines = pay.move_id.line_ids.filtered(
            lambda l: l.account_id == check_account and not l.reconciled
        )
        
        if not out_lines:
            print(f"  [i] No hay líneas pendientes de conciliar en la cuenta {check_account.code} para el pago {pay.id}.")
            if pay.is_reconciled and not pay.is_matched:
                print(f"  [!] Forzando re-cálculo de is_matched y state...")
                if not DRY_RUN:
                    pay._compute_is_matched()
                    pay._compute_state()
            continue
            
        print(f"  Línea de salida encontrada: ID {out_lines.ids} (Haber: {sum(out_lines.mapped('credit'))})")
        
        # Buscar la línea de ingreso del cheque original
        checks = pay.l10n_latam_move_check_ids
        reconciled_any = False
        
        for ch in checks:
            print(f"  Analizando Cheque [{ch.id}] N° {ch.name} (Monto: {ch.amount})...")
            
            # Buscar el pago o asiento origen del cheque
            origin_payment = getattr(ch, 'payment_id', None) or getattr(ch, 'issue_payment_id', None)
            origin_line = None
            
            if origin_payment and origin_payment.move_id:
                # Buscar la línea en el debe de la cuenta de cheques
                in_lines = origin_payment.move_id.line_ids.filtered(
                    lambda l: l.account_id == check_account and not l.reconciled and l.debit > 0
                )
                if in_lines:
                    origin_line = in_lines[0]
                    
            # Si no se encontró por payment_id, buscar líneas abiertas en la misma cuenta con el mismo monto
            if not origin_line:
                candidate_lines = env['account.move.line'].search([
                    ('account_id', '=', check_account.id),
                    ('reconciled', '=', False),
                    ('debit', '=', ch.amount),
                    ('company_id', '=', pay.company_id.id)
                ], limit=5)
                if candidate_lines:
                    print(f"    Líneas candidatas encontradas en {check_account.code} con monto {ch.amount}: {candidate_lines.ids}")
                    # Priorizar líneas donde la referencia o el nombre coincida con el cheque
                    for cand in candidate_lines:
                        if ch.name and ch.name in (cand.name or cand.ref or ''):
                            origin_line = cand
                            break
                    if not origin_line:
                        origin_line = candidate_lines[0]

            if origin_line:
                print(f"    [+] Línea origen de ingreso encontrada: ID {origin_line.id} (Debe: {origin_line.debit}) en Asiento {origin_line.move_id.name}")
                lines_to_reconcile = out_lines + origin_line
                
                print(f"    [>] Se conciliarán las líneas: {lines_to_reconcile.ids}")
                if not DRY_RUN:
                    lines_to_reconcile.reconcile()
                    pay._compute_is_matched()
                    pay._compute_state()
                    print(f"    [OK] Conciliación ejecutada. Nuevo estado del pago: {pay.state} (is_matched: {pay.is_matched})")
                    reconciled_any = True
                else:
                    print(f"    [SIMULACIÓN] En ejecución real se ejecutaría lines_to_reconcile.reconcile()")
            else:
                print(f"    [!] No se encontró línea abierta en el Debe para el cheque {ch.id}. Puede ser un cheque migrado o de saldo inicial.")
                
        # Si no hubo líneas para conciliar pero el cheque ya fue entregado y no debe esperar extracto bancario
        if not reconciled_any and DRY_RUN:
            print("    [SIMULACIÓN] Fin de evaluación para este pago.")

    if DRY_RUN:
        print("\n" + "=" * 90)
        print("SIMULACIÓN COMPLETADA CON ÉXITO (DRY_RUN = True). NO se modificó la base de datos.")
        print("Para aplicar los cambios reales, configure DRY_RUN = False y vuelva a ejecutar.")
        print("=" * 90)
    else:
        print("\n" + "=" * 90)
        print("REGULARIZACIÓN COMPLETADA. Transacción confirmada.")
        print("=" * 90)

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        # Ejecución para el pago 4661 de prueba
        regularizar_pagos_cheques(env, target_payment_ids=[4661])
    else:
        print("Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell / python3 odoo-bin shell).")
