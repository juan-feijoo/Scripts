# -*- coding: utf-8 -*-
"""
Script de Diagnóstico Seguro en Profundidad: Pagos con Cheques de Terceros (4661 vs 4688)
Ticket: AG-3
Entorno: Odoo 18.0+e (Odoo.sh)
"""

def diagnosticar_pagos_v2(env, payment_ids=(4661, 4688)):
    print("=" * 95)
    print("DIAGNÓSTICO DETALLADO: PAGOS 4661 vs 4688 Y ASIENTOS CONTABLES")
    print("=" * 95)
    
    Payment = env['account.payment']
    Check = env.get('l10n_latam.check')
    
    # Inspeccionar campos disponibles en l10n_latam.check si existe
    if Check is not None:
        check_fields = sorted(list(Check._fields.keys()))
        print(f"\n[+] Campos disponibles en l10n_latam.check: {check_fields[:15]}... (total {len(check_fields)})")

    for pid in payment_ids:
        pay = Payment.browse(pid)
        if not pay.exists():
            print(f"\n[!] Pago ID {pid} no existe.")
            continue
            
        print(f"\n{'=' * 40} PAGO ID: {pay.id} - {pay.name} {'=' * 40}")
        print(f"Estado (state):                   {pay.state}")
        print(f"Conciliado Deuda (is_reconciled): {pay.is_reconciled}")
        print(f"Conciliado Liquidez (is_matched): {pay.is_matched}")
        print(f"Monto:                            {pay.amount} {pay.currency_id.name}")
        print(f"Diario:                           [{pay.journal_id.id}] {pay.journal_id.name} (Tipo: {pay.journal_id.type})")
        print(f"Método de Pago:                   [{pay.payment_method_line_id.id}] {pay.payment_method_line_id.name} (Código: {pay.payment_method_code})")
        print(f"Cuenta de Pago en Método:         {pay.payment_method_line_id.payment_account_id.display_name if pay.payment_method_line_id.payment_account_id else 'None'}")
        print(f"Cuenta Pendiente (outstanding):   [{pay.outstanding_account_id.id}] {pay.outstanding_account_id.display_name if pay.outstanding_account_id else 'None'}")
        print(f"Cuenta Destino (destination):     [{pay.destination_account_id.id}] {pay.destination_account_id.display_name if pay.destination_account_id else 'None'}")
        print(f"Creado por:                       {pay.create_uid.name} (ID: {pay.create_uid.id}) el {pay.create_date}")
        print(f"Facturas asociadas:               {[b.name for b in pay.reconciled_bill_ids]}")
        
        # 1. Asiento contable
        move = pay.move_id
        print(f"\n  [+] Asiento Contable: [{move.id}] {move.name} | Estado: {move.state}")
        print("  Líneas del asiento (account.move.line):")
        for line in move.line_ids:
            rec_status = "NO CONCILIADO"
            if line.reconciled:
                full_rec = f"Full ID {line.full_reconcile_id.id}" if line.full_reconcile_id else "Parcial"
                rec_status = f"CONCILIADO ({full_rec})"
            elif line.matched_debit_ids or line.matched_credit_ids:
                rec_status = "PARCIALMENTE CONCILIADO"
                
            print(f"    - Línea [{line.id}] Cuenta [{line.account_id.id}] {line.account_id.display_name}")
            print(f"        Debe: {line.debit:12.2f} | Haber: {line.credit:12.2f} | {rec_status}")
            
            # Detalle de conciliaciones si existen
            if line.matched_debit_ids:
                for p_rec in line.matched_debit_ids:
                    print(f"        -> Matched Debit: Monto {p_rec.amount} contra línea [{p_rec.debit_move_id.id}] {p_rec.debit_move_id.move_id.name} ({p_rec.debit_move_id.account_id.display_name})")
            if line.matched_credit_ids:
                for p_rec in line.matched_credit_ids:
                    print(f"        -> Matched Credit: Monto {p_rec.amount} contra línea [{p_rec.credit_move_id.id}] {p_rec.credit_move_id.move_id.name} ({p_rec.credit_move_id.account_id.display_name})")

        # 2. Cheques asociados
        checks = pay.l10n_latam_move_check_ids
        print(f"\n  [+] Cheques Vinculados ({len(checks)}):")
        for ch in checks:
            ch_data = ch.read()[0] if ch else {}
            # Mostrar campos clave del cheque de forma segura
            print(f"    * Cheque [{ch.id}] Número: {ch.name} | Monto: {ch.amount}")
            for k in ['status', 'state', 'payment_id', 'issue_payment_id', 'operation_ids', 'current_journal_id']:
                if k in ch_data:
                    print(f"        {k}: {ch_data[k]}")
                    
            # Buscar el asiento de origen del cheque
            origin_pay = getattr(ch, 'payment_id', None) or getattr(ch, 'issue_payment_id', None)
            if origin_pay and origin_pay.move_id:
                print(f"        Asiento de Ingreso Original: [{origin_pay.move_id.id}] {origin_pay.move_id.name}")
                for o_line in origin_pay.move_id.line_ids:
                    if o_line.debit > 0:
                        print(f"          -> Línea Débito ingreso: [{o_line.id}] Cuenta: {o_line.account_id.display_name} | Debe: {o_line.debit} | Conciliado: {o_line.reconciled}")


if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        diagnosticar_pagos_v2(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
