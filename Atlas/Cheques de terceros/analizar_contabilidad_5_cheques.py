# -*- coding: utf-8 -*-
"""
================================================================================
AUDITORÍA CONTABLE PROFUNDA: LAS 5 ÓRDENES DE PAGO DE LOS 5 CHEQUES
================================================================================
Objetivo:
Revisar el estado contable de las 5 Órdenes de Pago donde figuran los 5 cheques:
- OP-X 0001-00002253 (Cheque #30014031 por $ 1,415,214.29)
- OP-X 0001-00002254 (Cheque #76713446 por $   685,504.16)
- OP-X 0001-00002255 (Cheque #30014086 por $   414,072.03)
- OP-X 0001-00002256 (Cheque #30014125 por $    43,939.27)
- OP-X 0001-00002337 (Cheque #76714712 por $   422,272.46)

Verificamos:
1. Proveedor al que se le emitió la OP.
2. Estado contable del asiento (publicado, borrador, etc.).
3. ¿Está conciliado con facturas de proveedor (deuda saldada)?
4. ¿Impactó la cuenta contable de valores (1.1.1.01.002 / 1.1.1.02.003 / etc.)?
5. ¿Existe grupo de pagos (account.payment.group) asociado?
================================================================================
"""

MoveModel = env['account.move']
PaymentModel = env['account.payment']
CheckModel = env['l10n_latam.check']

target_5_nums = ['30014031', '76713446', '30014086', '30014125', '76714712']
chks_5 = CheckModel.search([('name', 'in', target_5_nums), ('company_id', '=', 1)])

print("\n" + "=" * 135)
print("AUDITORÍA CONTABLE DE LAS 5 ÓRDENES DE PAGO (OP-X):")
print("=" * 135)

for c in chks_5:
    print(f"\n" + "-" * 135)
    print(f"📌 CHEQUE #{c.name} | MONTO: $ {c.amount:,.2f} | FECHA: {c.payment_date} | CLIENTE: {c.partner_id.name if c.partner_id else 'S/P'}")
    
    # Pago de entrada (Cobranza)
    in_pay = c.payment_id
    print(f"   📥 COBRO CLIENTE: Pago #{in_pay.id} | Asiento: {in_pay.move_id.name} | Fecha: {in_pay.date}")
    
    # Pagos de salida
    for op in c.operation_ids:
        op_move = op.move_id
        prov = op_move.partner_id.name if op_move.partner_id else (op.partner_id.name if op.partner_id else 'S/P')
        print(f"\n   📤 ORDEN DE PAGO / EGRESO: Pago #{op.id} | Asiento: {op_move.name}")
        print(f"      * Proveedor: {prov}")
        print(f"      * Fecha del Asiento: {op_move.date} | Estado Asiento: {op_move.state} | Estado Pago: {op.state}")
        
        # Revisar si tiene Payment Group
        if 'account.payment.group' in env:
            pg = env['account.payment.group'].search([('name', '=', op_move.name)], limit=1)
            if not pg:
                pg = env['account.payment.group'].search([('payment_ids', 'in', op.id)], limit=1)
            if pg:
                print(f"      * Payment Group: {pg.name} | Estado Group: {pg.state}")
        
        # Apuntes contables del asiento de salida
        print("      * Líneas Contables del Asiento:")
        for l in op_move.line_ids:
            concil_info = f"Conciliado: {l.reconciled}"
            if l.reconciled:
                reconciled_with = (l.matched_debit_ids.debit_move_id.move_id | l.matched_credit_ids.credit_move_id.move_id) - op_move
                if reconciled_with:
                    concil_info += f" con {', '.join(reconciled_with.mapped('name'))}"
            print(f"         - Cta: {l.account_id.code:<15} ({l.account_id.name[:25]:<25}) | Débito: ${l.debit:>12,.2f} | Crédito: ${l.credit:>12,.2f} | {concil_info}")

print("\n" + "=" * 135 + "\n")
