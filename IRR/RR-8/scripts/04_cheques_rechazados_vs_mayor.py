# -*- coding: utf-8 -*-
# 04 - Inspección de cheques rechazados, apuntes contables y comparación con el mayor
company = get_company()
h('04 - CHEQUES RECHAZADOS VS APUNTES CONTABLES Y MAYOR (%s)' % company.name)

# 1. Caso modelo account.check (Adhoc / OCA)
if 'account.check' in env:
    sub('Inspección en modelo account.check')
    checks = env['account.check'].with_company(company).search([], order='id desc', limit=20)
    print('Últimos %d cheques en account.check:' % len(checks))
    for chk in checks:
        print('  ID=%-6s Número=%-15s Estado=%-12s Importe=%-10.2f Fecha=%s Partner=%s' % (
            chk.id, getattr(chk, 'number', chk.name), getattr(chk, 'state', ''),
            chk.amount, getattr(chk, 'payment_date', getattr(chk, 'issue_date', '')),
            chk.partner_id.display_name if chk.partner_id else ''
        ))
    
    sub('Cheques rechazados en account.check')
    rej_checks = env['account.check'].with_company(company).search([
        ('state', '=', 'rejected')
    ], order='id desc', limit=10)
    if not rej_checks:
        print('  No se encontraron cheques con state = "rejected"')
    for chk in rej_checks:
        print('\n  >> CHEQUE RECHAZADO ID=%s Núm=%s Importe=%.2f' % (chk.id, getattr(chk, 'number', chk.name), chk.amount))
        dump(chk, names=['state', 'issue_date', 'payment_date', 'partner_id', 'journal_id', 'company_id'])
        if hasattr(chk, 'operation_ids'):
            print('    Operaciones:')
            for op in chk.operation_ids:
                print('      - Op ID=%s tipo=%s fecha=%s asiento=%s' % (
                    op.id, getattr(op, 'operation', getattr(op, 'type', '')),
                    getattr(op, 'date', ''),
                    op.origin_move_id.name if hasattr(op, 'origin_move_id') and op.origin_move_id else ''
                ))

# 2. Caso modelo account.payment (Estándar Odoo Enterprise l10n_latam_check)
if 'account.payment' in env:
    sub('Inspección en account.payment (Cheques de terceros)')
    # Buscar líneas de métodos de pago de cheques de terceros
    domain_pay = [
        ('company_id', '=', company.id),
        '|', '|', '|',
        ('payment_method_line_id.code', 'ilike', 'check'),
        ('payment_method_line_id.code', 'ilike', 'third_party'),
        ('check_number', '!=', False) if has_field('account.payment', 'check_number') else ('id', '>', 0),
        ('l10n_latam_check_number', '!=', False) if has_field('account.payment', 'l10n_latam_check_number') else ('id', '>', 0)
    ]
    # Filtrar solo pagos de clientes o entrantes
    payments = env['account.payment'].search(domain_pay, order='date desc, id desc', limit=20)
    print('Últimos %d pagos de cheques encontrados:' % len(payments))
    for p in payments:
        chk_num = getattr(p, 'check_number', getattr(p, 'l10n_latam_check_number', 'S/N'))
        chk_state = getattr(p, 'check_state', getattr(p, 'l10n_latam_check_state', getattr(p, 'state', '')))
        is_matched = getattr(p, 'is_matched', 'N/A')
        print('  ID=%-6s Pago=%-16s Cheque=%-12s Estado=%-12s Matched=%-5s Imp=%-10.2f Fecha=%s Partner=%s' % (
            p.id, p.name, chk_num, chk_state, str(is_matched), p.amount, p.date,
            p.partner_id.display_name if p.partner_id else ''
        ))

    sub('Detalle de los primeros 5 pagos/cheques y sus apuntes contables (Mayor)')
    for p in payments[:5]:
        chk_num = getattr(p, 'check_number', getattr(p, 'l10n_latam_check_number', 'S/N'))
        chk_state = getattr(p, 'check_state', getattr(p, 'l10n_latam_check_state', getattr(p, 'state', '')))
        print('\n  -- Pago ID=%s | Ref=%s | Cheque=%s | Estado=%s | Fecha=%s' % (
            p.id, p.name, chk_num, chk_state, p.date
        ))
        dump(p, prefixes=['check', 'l10n_latam_check', 'is_'], names=['state', 'journal_id', 'destination_account_id'])
        
        move = p.move_id
        if move:
            print('    Asiento contable: %s (id=%s, state=%s, date=%s)' % (move.name, move.id, move.state, move.date))
            for line in move.line_ids:
                matching = getattr(line, 'matching_number', '') or (line.reconciled and 'Conciliado') or 'No'
                print('      Línea ID=%-6s Cuenta=[%s] %-25s Debe=%-9.2f Haber=%-9.2f Match=%s' % (
                    line.id, line.account_id.code, line.account_id.name[:25],
                    line.debit, line.credit, matching
                ))
                # Ver si esta línea fue conciliada con un asiento de rechazo o depósito
                if line.matched_debit_ids or line.matched_credit_ids:
                    for pr in line.matched_debit_ids:
                        contra = pr.debit_move_id
                        print('        -> Conciliada con débito: Asiento=%s Cuenta=%s Imp=%.2f Fecha=%s' % (
                            contra.move_id.name, contra.account_id.code, pr.amount, contra.date
                        ))
                    for pr in line.matched_credit_ids:
                        contra = pr.credit_move_id
                        print('        -> Conciliada con crédito: Asiento=%s Cuenta=%s Imp=%.2f Fecha=%s' % (
                            contra.move_id.name, contra.account_id.code, pr.amount, contra.date
                        ))
