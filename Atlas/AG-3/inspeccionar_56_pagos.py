# -*- coding: utf-8 -*-
"""
Script de Inspección de Código y Cuentas para Ticket AG-3
Entorno: Odoo 18.0+e (Odoo.sh)
"""
import inspect

def inspeccionar_logica_y_56_pagos(env):
    print("=" * 95)
    print("INSPECCIÓN DE CÓDIGO ORM: _compute_is_matched Y _compute_state")
    print("=" * 95)
    
    Payment = env['account.payment']
    
    # 1. Ver código fuente de _compute_is_matched en Odoo 18
    try:
        source_matched = inspect.getsource(Payment._compute_is_matched)
        print("\n[+] Código fuente de Payment._compute_is_matched:")
        print(source_matched)
    except Exception as e:
        print(f"[!] No se pudo obtener código fuente de _compute_is_matched: {e}")
        
    try:
        source_state = inspect.getsource(Payment._compute_state)
        print("\n[+] Código fuente de Payment._compute_state:")
        print(source_state)
    except Exception as e:
        print(f"[!] No se pudo obtener código fuente de _compute_state: {e}")

    # 2. Análisis de las cuentas contables de los 56 pagos en 'in_process'
    print("\n" + "=" * 95)
    print("ANÁLISIS DE CUENTAS EN LOS 56 PAGOS EN 'in_process'")
    print("=" * 95)
    
    env.cr.execute("""
        SELECT 
            aml.account_id,
            a.name->>'es_AR' AS account_name,
            COUNT(DISTINCT p.id) AS total_pagos,
            SUM(aml.credit) AS total_haber
        FROM account_move_line aml
        JOIN account_move m ON m.id = aml.move_id
        JOIN account_payment p ON p.id = aml.payment_id
        JOIN account_payment_method_line pml ON pml.id = p.payment_method_line_id
        JOIN account_payment_method apm ON apm.id = pml.payment_method_id
        JOIN account_account a ON a.id = aml.account_id
        WHERE apm.code = 'out_third_party_checks'
          AND p.state = 'in_process'
          AND aml.account_id != p.destination_account_id
        GROUP BY aml.account_id, a.name
        ORDER BY total_pagos DESC;
    """)
    rows = env.cr.fetchall()
    print(f"{'Account ID':12} | {'Nombre de Cuenta':35} | {'Pagos':8} | {'Total Monto':15}")
    print("-" * 75)
    for r in rows:
        print(f"{r[0]:<12} | {r[1]:<35} | {r[2]:<8} | {r[3]:15.2f}")

    # 3. Comparación detallada 4661 vs 4688
    print("\n" + "=" * 95)
    print("COMPARACIÓN DIRECTA DE LÍNEAS DE LIQUIDEZ: 4661 vs 4688")
    print("=" * 95)
    for pid in [4661, 4688]:
        p = Payment.browse(pid)
        print(f"\nPago {p.id} [{p.name}]: state={p.state}, is_matched={p.is_matched}, is_reconciled={p.is_reconciled}")
        print(f"  outstanding_account_id: [{p.outstanding_account_id.id}] {p.outstanding_account_id.display_name}")
        for l in p.move_id.line_ids:
            if l.account_id != p.destination_account_id:
                print(f"  Línea Liquidez [{l.id}]: Cuenta [{l.account_id.id}] {l.account_id.display_name} | Haber: {l.credit} | Reconciled: {l.reconciled}")
                # Ver si la cuenta de la línea coincide con outstanding_account_id
                coincide = (l.account_id == p.outstanding_account_id)
                print(f"    ¿Coincide con outstanding_account_id?: {coincide}")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        inspeccionar_logica_y_56_pagos(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
