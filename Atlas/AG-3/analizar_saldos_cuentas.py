# -*- coding: utf-8 -*-
"""
Script de Análisis de Saldos y Movimientos: 1471 vs 1774 vs 1770
Ticket: AG-3
Entorno: Odoo 18.0+e (Odoo.sh)
"""

def analizar_saldos_cuentas(env):
    print("=" * 95)
    print("ANÁLISIS CONTABLE: CUENTA 1471 vs CUENTA 1774 vs CUENTA 1770")
    print("=" * 95)
    
    Account = env['account.account']
    AML = env['account.move.line']
    
    target_accounts = [1471, 1774, 1770]
    
    for aid in target_accounts:
        acc = Account.browse(aid)
        lines = AML.search([('account_id', '=', acc.id)])
        debit = sum(lines.mapped('debit'))
        credit = sum(lines.mapped('credit'))
        balance = debit - credit
        unreconciled_lines = lines.filtered(lambda l: not l.reconciled)
        
        print(f"\nCuenta [{acc.id}] {acc.code} - {acc.name}:")
        print(f"  Tipo: {acc.account_type} | Reconcile: {acc.reconcile}")
        print(f"  Total líneas contables: {len(lines)}")
        print(f"  Debe total:   {debit:15.2f}")
        print(f"  Haber total:  {credit:15.2f}")
        print(f"  Saldo final:  {balance:15.2f}")
        print(f"  Líneas abiertas (sin conciliar): {len(unreconciled_lines)} (Saldo residual: {sum(unreconciled_lines.mapped('amount_residual')):15.2f})")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        analizar_saldos_cuentas(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
