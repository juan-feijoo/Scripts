# -*- coding: utf-8 -*-
"""
Script de Inspección: Líneas de 1770 y sus conciliaciones
Ticket: AG-3
"""

def inspeccionar_lineas_1770(env):
    print("=" * 95)
    print("INSPECCIÓN DE LÍNEAS EN CUENTA 1770 Y SUS CONCILIACIONES")
    print("=" * 95)
    
    env.cr.execute("""
        SELECT DISTINCT p.id 
        FROM account_payment p
        JOIN account_move_line aml ON aml.payment_id = p.id
        WHERE p.state = 'in_process' 
          AND aml.account_id = 1770;
    """)
    p1770_ids = [r[0] for r in env.cr.fetchall()]
    print(f"Total pagos en 1770: {len(p1770_ids)}")
    
    Payment = env['account.payment']
    for pid in p1770_ids:
        p = Payment.browse(pid)
        lines = p.move_id.line_ids.filtered(lambda l: l.account_id.id == 1770)
        for l in lines:
            recs_deb = l.matched_debit_ids
            recs_cred = l.matched_credit_ids
            has_rec = bool(recs_deb or recs_cred)
            print(f"\nPago {p.id} [{p.name}] - Línea [{l.id}] (Haber: {l.credit}):")
            print(f"  reconciled={l.reconciled}, residual={l.amount_residual}")
            print(f"  ¿Tiene conciliaciones?: {has_rec}")
            if recs_deb:
                for r in recs_deb:
                    print(f"    -> Debit Matched: ID {r.id}, monto={r.amount}, contra línea [{r.debit_move_id.id}] {r.debit_move_id.move_id.name} (cuenta: {r.debit_move_id.account_id.display_name})")
            if recs_cred:
                for r in recs_cred:
                    print(f"    -> Credit Matched: ID {r.id}, monto={r.amount}, contra línea [{r.credit_move_id.id}] {r.credit_move_id.move_id.name} (cuenta: {r.credit_move_id.account_id.display_name})")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        inspeccionar_lineas_1770(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
