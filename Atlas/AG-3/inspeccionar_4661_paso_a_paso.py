# -*- coding: utf-8 -*-
"""
Script de Inspección Quirúrgica: ¿Por qué 4661 dio in_process en _compute_state?
Ticket: AG-3
"""
import inspect

def inspeccionar_porque_4661_in_process(env):
    print("=" * 95)
    print("INSPECCIÓN PASO A PASO: _compute_state Y VARIABLES DE PAGO 4661")
    print("=" * 95)
    
    p = env['account.payment'].browse(4661)
    j69 = env['account.journal'].browse(69)
    
    savepoint = env.cr.savepoint()
    try:
        j69.write({'default_account_id': 1774})
        l34329 = env['account.move.line'].browse(34329)
        l34329.write({'account_id': 1774})
        
        # 1. Recomputar reconciliation status
        p._compute_reconciliation_status()
        print(f"Tras _compute_reconciliation_status:")
        print(f"  is_matched:    {p.is_matched}")
        print(f"  is_reconciled: {p.is_reconciled}")
        
        # 2. Ver líneas de liquidez y contrapartida que busca _seek_for_lines
        liquidity_lines, counterpart_lines, writeoff_lines = p._seek_for_lines()
        print(f"\n_seek_for_lines():")
        print(f"  liquidity_lines:   {[(l.id, l.account_id.code, l.credit, l.reconciled) for l in liquidity_lines]}")
        print(f"  counterpart_lines: {[(l.id, l.account_id.code, l.debit, l.reconciled) for l in counterpart_lines]}")
        print(f"  writeoff_lines:    {writeoff_lines.ids}")
        
        # 3. Ver código base de Odoo _compute_state
        base_compute_state = None
        for cls in p.__class__.__mro__:
            if '_compute_state' in cls.__dict__ and 'addons/account/' in inspect.getfile(cls):
                base_compute_state = cls.__dict__['_compute_state']
                print(f"\n[+] Código base de _compute_state en {cls.__name__} (addons/account):")
                print(inspect.getsource(base_compute_state))
                break

        # 4. Probar ejecutar directamente el método base vs el override
        print(f"\nEvaluación antes de _compute_state: state={p.state}")
        p._compute_state()
        print(f"Evaluación después de _compute_state: state={p.state}")
        
        # Si sigue en in_process, evaluar manualmente la condición del elif
        print(f"\nCondiciones lógicas directas:")
        print(f"  p.move_id.state == 'draft': {p.move_id.state == 'draft'}")
        print(f"  p.is_reconciled:            {p.is_reconciled}")
        print(f"  p.is_matched:               {p.is_matched}")
        print(f"  p.is_reconciled and p.is_matched: {p.is_reconciled and p.is_matched}")
        
        # Ver si hay invoice_ids o reconciled_bills
        print(f"  invoice_ids:                {p.invoice_ids.ids}")
        print(f"  reconciled_bill_ids:        {p.reconciled_bill_ids.ids}")
        print(f"  reconciled_bills_count:     {p.reconciled_bills_count}")

    finally:
        savepoint.rollback()
        print("\n[OK] Rollback completado.")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        inspeccionar_porque_4661_in_process(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
