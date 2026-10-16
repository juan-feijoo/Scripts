# -*- coding: utf-8 -*-
"""
Script de Simulación de Solución Completa (DRY_RUN / Rollback)
Prueba:
1. Qué pasa con los 42 pagos en 1774 si el diario 69 tiene default_account_id = 1774
2. Qué pasa con los 14 pagos en 1770 si su línea se corrige a 1774
Ticket: AG-3
"""

def simular_solucion(env):
    print("=" * 95)
    print("SIMULACIÓN DE SOLUCIÓN: UNIFICACIÓN EN CUENTA REAL OPERATIVA [1774]")
    print("=" * 95)
    
    Payment = env['account.payment']
    Journal = env['account.journal']
    j69 = Journal.browse(69)
    acc_1774 = env['account.account'].browse(1774)
    
    print(f"\nEstado Actual:")
    print(f"  Diario 69 default_account_id: [{j69.default_account_id.id}] {j69.default_account_id.display_name}")
    print(f"  Cuenta Operativa Real (109 movs): [{acc_1774.id}] {acc_1774.display_name}")
    
    # 1. Probar un pago de los 42 que están en 1774
    # Buscar uno de los pagos en in_process cuya línea esté en 1774
    env.cr.execute("""
        SELECT p.id 
        FROM account_payment p
        JOIN account_move_line aml ON aml.payment_id = p.id
        WHERE p.state = 'in_process' 
          AND aml.account_id = 1774
        LIMIT 1;
    """)
    res = env.cr.fetchone()
    sample_pay_1774_id = res[0] if res else None
    
    if sample_pay_1774_id:
        p1774 = Payment.browse(sample_pay_1774_id)
        print(f"\n[Test 1] Pago Muestra en 1774: ID {p1774.id} [{p1774.name}]")
        print(f"  Estado actual: {p1774.state} | is_matched: {p1774.is_matched}")
        
        # Simular cambio de default_account_id en j69 temporalmente en memoria
        # (Sin commit a BD, env.cr.rollback() al final)
        savepoint = env.cr.savepoint()
        try:
            j69.write({'default_account_id': 1774})
            p1774._compute_reconciliation_status()
            p1774._compute_state()
            print(f"  -> Con default_account_id = 1774: is_matched = {p1774.is_matched} | state = {p1774.state}")
        finally:
            savepoint.rollback()

    # 2. Probar el pago 4661 (que está en 1770)
    p4661 = Payment.browse(4661)
    print(f"\n[Test 2] Pago 4661 (actualmente en 1770 Pagos Pendientes):")
    print(f"  Estado actual: {p4661.state} | is_matched: {p4661.is_matched}")
    
    savepoint = env.cr.savepoint()
    try:
        j69.write({'default_account_id': 1774})
        # Pasar la línea 34329 de 1770 a 1774
        l34329 = env['account.move.line'].browse(34329)
        l34329.write({'account_id': 1774})
        p4661._compute_reconciliation_status()
        p4661._compute_state()
        print(f"  -> Con línea en 1774 y default_account_id = 1774: is_matched = {p4661.is_matched} | state = {p4661.state}")
    finally:
        savepoint.rollback()
        print("\n[OK] Simulación finalizada. No se alteró ningún dato (rollback ejecutado).")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        simular_solucion(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
