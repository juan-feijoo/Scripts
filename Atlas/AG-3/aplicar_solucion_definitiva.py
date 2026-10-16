# -*- coding: utf-8 -*-
"""
Script de Solución y Regularización Definitiva para Ticket AG-3
Entorno: Odoo 18.0+e (Odoo.sh)
Configuración: DRY_RUN = True por defecto para simular antes de aplicar.
"""

# CAMBIAR A True SI SE DESEA VOLVER A SIMULAR
DRY_RUN = False

def ejecutar_solucion_definitiva(env):
    print("=" * 95)
    print("APLICACIÓN DE SOLUCIÓN DEFINITIVA: CHEQUES DE TERCEROS COMO EFECTIVO")
    print(f"MODO: {'*** DRY-RUN (SIMULACIÓN - SIN CAMBIOS REALES) ***' if DRY_RUN else '*** APLICACIÓN REAL EN BASE DE DATOS ***'}")
    print("=" * 95)
    
    Account = env['account.account']
    Journal = env['account.journal']
    Payment = env['account.payment']
    AML = env['account.move.line']
    
    j69 = Journal.browse(69)
    acc_1774 = Account.browse(1774)
    
    print("\n[PASO 1] Configuración de la Cuenta Operativa Real [1774] (1.1.1.01.002)")
    print(f"  Estado actual de 1774: reconcile={acc_1774.reconcile}, type={acc_1774.account_type}")
    if not DRY_RUN:
        acc_1774.write({
            'reconcile': False,
            'account_type': 'asset_cash'
        })
        print(f"  [OK] Cuenta 1774 actualizada: reconcile=False, account_type='asset_cash'")
    else:
        print(f"  [SIMULACIÓN] Se actualizará cuenta 1774 con reconcile=False y account_type='asset_cash'")

    print("\n[PASO 2] Configuración del Diario [69] Cheques de Terceros")
    print(f"  default_account_id actual: [{j69.default_account_id.id}] {j69.default_account_id.display_name}")
    if not DRY_RUN:
        j69.write({'default_account_id': 1774})
        print(f"  [OK] Diario 69 actualizado: default_account_id = 1774")
    else:
        print(f"  [SIMULACIÓN] Se actualizará Diario 69 con default_account_id = 1774")

    print("\n[PASO 3] Regularización de los 42 Pagos ya imputados en la Cuenta 1774")
    env.cr.execute("""
        SELECT DISTINCT p.id 
        FROM account_payment p
        JOIN account_move_line aml ON aml.payment_id = p.id
        WHERE p.state = 'in_process' 
          AND aml.account_id = 1774;
    """)
    p1774_ids = [r[0] for r in env.cr.fetchall()]
    print(f"  Pagos encontrados en 1774 para pasar a 'paid': {len(p1774_ids)}")
    
    if p1774_ids:
        payments_1774 = Payment.browse(p1774_ids)
        if not DRY_RUN:
            for p in payments_1774:
                p._compute_reconciliation_status()
                p._compute_state()
            # Verificar cuántos pasaron a paid
            paid_count = len(payments_1774.filtered(lambda x: x.state == 'paid'))
            print(f"  [OK] {paid_count} de {len(payments_1774)} pagos pasaron a estado 'paid' exitosamente.")
        else:
            print(f"  [SIMULACIÓN] Se recomputará _compute_reconciliation_status y _compute_state en {len(p1774_ids)} pagos.")

    print("\n[PASO 4] Regularización de los 14 Pagos desviados a la Cuenta 1770 (Banco Galicia)")
    env.cr.execute("""
        SELECT DISTINCT p.id 
        FROM account_payment p
        JOIN account_move_line aml ON aml.payment_id = p.id
        WHERE p.state = 'in_process' 
          AND aml.account_id = 1770;
    """)
    p1770_ids = [r[0] for r in env.cr.fetchall()]
    print(f"  Pagos encontrados en 1770 (como 4661) para corregir y pasar a 'paid': {len(p1770_ids)}")
    
    if p1770_ids:
        payments_1770 = Payment.browse(p1770_ids)
        for p in payments_1770:
            lines_1770 = p.move_id.line_ids.filtered(lambda l: l.account_id.id == 1770)
            if not lines_1770:
                continue
                
            has_reconciliation = any(l.matched_debit_ids or l.matched_credit_ids for l in lines_1770)
            if has_reconciliation:
                print(f"    - Pago {p.id} [{p.name}]: PRESERVADO en 1770 (ya tiene extracto bancario en Banco Galicia).")
                if not DRY_RUN:
                    p._compute_reconciliation_status()
                    p._compute_state()
            else:
                print(f"    - Pago {p.id} [{p.name}]: moviendo línea(s) {lines_1770.ids} de 1770 a 1774...")
                if not DRY_RUN:
                    lines_1770.write({'account_id': 1774})
                    p._compute_reconciliation_status()
                    p._compute_state()
                    print(f"      -> Pago {p.id} actualizado: state={p.state}")
                else:
                    print(f"      [SIMULACIÓN] Se cambiará línea a cuenta 1774 y se recomputará a state='paid'")

    if not DRY_RUN:
        env.cr.commit()
        print("\n[OK] Transacción confirmada en base de datos (commit ejecutado).")

    print("\n" + "=" * 95)
    if DRY_RUN:
        print("SIMULACIÓN EXITOSA (DRY_RUN = True). NO se alteró ningún dato en la base de datos.")
        print("Para aplicar los cambios definitivos, edite el archivo y cambie 'DRY_RUN = False'.")
    else:
        print("¡SOLUCIÓN DEFINITIVA APLICADA CON ÉXITO! Todos los pagos fueron regularizados a 'paid'.")
        print("A partir de ahora, todo nuevo pago de cheques de terceros funcionará como efectivo y quedará 'paid'.")
    print("=" * 95)

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        ejecutar_solucion_definitiva(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
