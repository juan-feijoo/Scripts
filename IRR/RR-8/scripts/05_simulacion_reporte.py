# -*- coding: utf-8 -*-
# 05 - Simulación de dominios de reportes vs cheques rechazados
company = get_company()
h('05 - SIMULACIÓN DE REPORTES VS CHEQUES RECHAZADOS (%s)' % company.name)

sub('1. Evaluación de acciones de ventana de cheques')
actions = env['ir.actions.act_window'].search([
    '|', '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('res_model', '=', 'account.check'),
    ('domain', 'ilike', 'check')
])

for act in actions:
    print('\nAnalizando Acción: %s (ID=%s, Modelo=%s)' % (act.name, act.id, act.res_model))
    print('  Dominio configurado: %s' % act.domain)
    model = env[act.res_model].with_company(company)
    
    # Intentar evaluar el dominio de la acción
    try:
        domain = eval(act.domain or '[]', {'company_id': company.id, 'active_id': False})
        recs = model.search(domain, limit=10)
        print('  Total registros que devuelve el dominio (mostrando primeros %d):' % len(recs))
        for r in recs:
            r_num = getattr(r, 'number', getattr(r, 'check_number', getattr(r, 'name', '')))
            r_state = getattr(r, 'state', getattr(r, 'check_state', ''))
            print('    - ID=%-6s Cheque/Ref=%-15s Estado=%-12s Importe=%-10.2f Partner=%s' % (
                r.id, r_num, r_state, getattr(r, 'amount', 0.0),
                r.partner_id.display_name if hasattr(r, 'partner_id') and r.partner_id else ''
            ))
            # Verificar si está rechazado
            is_rejected = (
                r_state == 'rejected' or
                'rechaz' in str(r_state).lower() or
                getattr(r, 'is_rejected', False)
            )
            if is_rejected:
                print('      !! ATENCIÓN: Este registro figura RECHAZADO pero el dominio de la acción lo incluye.')
    except Exception as e:
        print('  No se pudo evaluar el dominio directamente: %s' % e)

sub('2. Evaluación de reportes dinámicos account.report')
if 'account.report' in env:
    acc_reports = env['account.report'].search([
        '|', '|',
        ('name', 'ilike', 'cheque'),
        ('name', 'ilike', 'check'),
        ('name', 'ilike', 'tercero')
    ])
    for rep in acc_reports:
        print('\nAnalizando account.report: %s (ID=%s, Code=%s)' % (rep.name, rep.id, getattr(rep, 'code', '')))
        try:
            options = rep._get_options({'allowed_company_ids': [company.id]})
            lines = rep._get_lines(options)
            print('  Líneas devueltas por el reporte: %d' % len(lines))
            for l in lines[:15]:
                print('    Línea: %-40s | Columnas: %s' % (
                    l.get('name', ''),
                    [c.get('name') for c in l.get('columns', [])]
                ))
        except Exception as e:
            print('  No se pudo generar líneas vía _get_lines: %s' % e)

sub('3. Comparación de saldo de cheques en cartera vs saldo de la cuenta en el Mayor')
# Buscamos la cuenta de cheques en cartera
check_accounts = env['account.account'].with_company(company).search([
    '|',
    ('name', 'ilike', 'valor'),
    ('name', 'ilike', 'cheque')
])
for acc in check_accounts:
    # Saldo en el mayor
    aml_lines = env['account.move.line'].with_company(company).search([
        ('account_id', '=', acc.id),
        ('parent_state', '=', 'posted')
    ])
    balance_mayor = sum(aml_lines.mapped('debit')) - sum(aml_lines.mapped('credit'))
    
    # Saldo de cheques físicos no rechazados según account.payment o account.check
    if 'account.check' in env:
        holding_checks = env['account.check'].with_company(company).search([
            ('state', '=', 'holding')
        ])
        total_holding = sum(holding_checks.mapped('amount'))
        print('\nCuenta: [%s] %s' % (acc.code, acc.name))
        print('  Saldo en el Mayor (account.move.line):    $ %.2f' % balance_mayor)
        print('  Total cheques en cartera (state=holding): $ %.2f' % total_holding)
        print('  Diferencia (Mayor - Cartera):             $ %.2f' % (balance_mayor - total_holding))
        
    elif 'account.payment' in env:
        unmatched_checks = env['account.payment'].with_company(company).search([
            ('state', '=', 'posted'),
            ('is_matched', '=', False) if has_field('account.payment', 'is_matched') else ('id', '>', 0),
            '|',
            ('payment_method_line_id.code', 'ilike', 'check'),
            ('payment_method_line_id.code', 'ilike', 'third_party')
        ])
        total_unmatched = sum(unmatched_checks.mapped('amount'))
        print('\nCuenta: [%s] %s' % (acc.code, acc.name))
        print('  Saldo en el Mayor (account.move.line):    $ %.2f' % balance_mayor)
        print('  Total cheques según account.payment:      $ %.2f' % total_unmatched)
        print('  Diferencia:                               $ %.2f' % (balance_mayor - total_unmatched))
