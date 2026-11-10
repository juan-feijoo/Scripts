# -*- coding: utf-8 -*-
# 03 - Diarios, cuentas contables de cheques y saldos en el mayor
company = get_company()
h('03 - DIARIOS, CUENTAS CONTABLES Y SALDOS DE CHEQUES (%s)' % company.name)

sub('Diarios contables de cheques')
journals = env['account.journal'].with_company(company).search([
    '|', '|',
    ('type', 'in', ['bank', 'cash']),
    ('name', 'ilike', 'cheque'),
    ('code', 'ilike', 'ch')
])
for j in journals:
    def_acc = j.default_account_id.display_name if hasattr(j, 'default_account_id') and j.default_account_id else 'N/A'
    pmls = []
    if hasattr(j, 'inbound_payment_method_line_ids'):
        pmls = [line.name for line in j.inbound_payment_method_line_ids]
    print('  Diario: %-30s (code=%-6s, tipo=%-6s) Cuenta def: %s' % (j.name, j.code, j.type, def_acc))
    if pmls:
        print('    Métodos entrantes: %s' % ', '.join(pmls))

sub('Cuentas contables relacionadas a cheques (Valores a depositar / Rechazados)')
accounts = env['account.account'].with_company(company).search([
    '|', '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'valor'),
    ('name', 'ilike', 'depositar'),
    ('name', 'ilike', 'rechaz')
])
for acc in accounts:
    # Saldo contable general en account.move.line
    lines = env['account.move.line'].with_company(company).search([
        ('account_id', '=', acc.id),
        ('parent_state', '=', 'posted')
    ])
    debit = sum(lines.mapped('debit'))
    credit = sum(lines.mapped('credit'))
    balance = debit - credit
    reconciled = acc.reconcile if hasattr(acc, 'reconcile') else 'N/A'
    acc_type = acc.account_type if hasattr(acc, 'account_type') else (acc.user_type_id.name if hasattr(acc, 'user_type_id') else '')
    print('  Cuenta: [%s] %-35s Tipo=%-20s Conciliable=%s' % (acc.code, acc.name, acc_type, reconciled))
    print('    Movimientos posted: %d | Debe: %.2f | Haber: %.2f | Saldo (Mayor): %.2f' % (
        len(lines), debit, credit, balance
    ))

sub('Overrides en métodos de pago / cheques (MRO)')
if 'account.payment' in env:
    methods_to_check = ['action_post', 'action_cancel', '_seek_for_lines', '_get_valid_liquidity_accounts']
    if has_field('account.payment', 'action_reject'):
        methods_to_check.append('action_reject')
    method_sources('account.payment', methods_to_check)

if 'account.check' in env:
    methods_to_check = ['action_reject', 'action_holding', 'action_deposited']
    methods_to_check = [m for m in methods_to_check if hasattr(env['account.check'], m)]
    if methods_to_check:
        method_sources('account.check', methods_to_check)
