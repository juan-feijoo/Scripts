# -*- coding: utf-8 -*-
"""
Test Quirúrgico de la Regla de Oro de Odoo 18:
'or not any(liquidity.account_id.mapped('reconcile'))'
Ticket: AG-3
"""

def test_reconcile_false_vs_true(env):
    print("=" * 95)
    print("TEST DE LA CONDICIÓN 'not any(liquidity.account_id.mapped('reconcile'))'")
    print("=" * 95)
    
    p4661 = env['account.payment'].browse(4661)
    l34329 = env['account.move.line'].browse(34329)
    j69 = env['account.journal'].browse(69)
    acc_1471 = env['account.account'].browse(1471)
    acc_1774 = env['account.account'].browse(1774)
    
    print(f"Cuenta 1471: reconcile = {acc_1471.reconcile} (asset_cash)")
    print(f"Cuenta 1774: reconcile = {acc_1774.reconcile} (asset_current)")
    
    savepoint = env.cr.savepoint()
    try:
        # CASO A: Imputar la línea 34329 a la cuenta 1471 (reconcile = False)
        print("\n--- CASO A: Línea 34329 en Cuenta 1471 (reconcile = False) ---")
        j69.write({'default_account_id': 1471})
        l34329.write({'account_id': 1471})
        p4661._compute_reconciliation_status()
        p4661._compute_state()
        print(f"Resultado en 1471: is_matched = {p4661.is_matched} | state = {p4661.state}")
        
        # CASO B: Imputar la línea 34329 a la cuenta 1774 pero con reconcile = False
        print("\n--- CASO B: Cuenta 1774 con reconcile = False ---")
        acc_1774.write({'reconcile': False})
        j69.write({'default_account_id': 1774})
        l34329.write({'account_id': 1774})
        p4661._compute_reconciliation_status()
        p4661._compute_state()
        print(f"Resultado en 1774 (con reconcile=False): is_matched = {p4661.is_matched} | state = {p4661.state}")

    finally:
        savepoint.rollback()
        print("\n[OK] Rollback completado.")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        test_reconcile_false_vs_true(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
