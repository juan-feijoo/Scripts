# -*- coding: utf-8 -*-
# 08 - Verificación de la solución: Comparación Mayor vs Reporte sin rechazados
from odoo import fields

company = get_company()
target_date = fields.Date.from_string('2026-11-06')
h('08 - VERIFICACIÓN EXACTA: MAYOR VS REPORTE AL %s (%s)' % (target_date, company.name))

# 1. Saldo en el Mayor de la cuenta 1.1.1.02.010 (Cheques de Terceros) al 06/11/2026
acc_cheq = env['account.account'].with_company(company).search([('code', '=', '1.1.1.02.010')], limit=1)
if not acc_cheq:
    acc_cheq = env['account.account'].with_company(company).search([('name', 'ilike', 'Third Party Checks')], limit=1)

print('Cuenta analizada: [%s] %s' % (acc_cheq.code, acc_cheq.name))
lines_to_date = env['account.move.line'].with_company(company).search([
    ('account_id', '=', acc_cheq.id),
    ('parent_state', '=', 'posted'),
    ('date', '<=', target_date)
])
debit = sum(lines_to_date.mapped('debit'))
credit = sum(lines_to_date.mapped('credit'))
saldo_mayor_to_date = debit - credit
print('  Total apuntes en el Mayor al %s: %d' % (target_date, len(lines_to_date)))
print('  Debe acumulado al corte:   $ %15.2f' % debit)
print('  Haber acumulado al corte:  $ %15.2f' % credit)
print('  SALDO EN EL MAYOR (CORTE): $ %15.2f' % saldo_mayor_to_date)

# 2. Cheques devueltos actualmente por el wizard para el diario CHEQT
cheqt = env['account.journal'].with_company(company).search([('code', '=', 'CHEQT')], limit=1)
if not cheqt:
    cheqt = env['account.journal'].with_company(company).search([('name', 'ilike', 'Cheques de Terceros')], limit=1)

Wizard = env['account.check.to_date.report.wizard']
checks_raw = Wizard._get_checks_on_hand(cheqt.id if cheqt else False, target_date)
total_raw = sum(checks_raw.mapped('amount'))
print('\nReporte Cheques a fecha ACTUAL (con bug):')
print('  Total cheques: %d | Total $: %15.2f' % (len(checks_raw), total_raw))
print('  Diferencia con el Mayor:   $ %15.2f' % (total_raw - saldo_mayor_to_date))

# 3. Identificación y exclusión de los cheques rechazados
rejected_journal_ids = env['account.journal'].search([
    '|', ('code', 'in', ['CHTER', 'CSH3']),
    ('name', 'ilike', 'rechaz')
]).ids

target_numbers = ['64943755', '90000059', '90000058']

# Filtro 1: Excluyendo por diario actual en diarios de rechazo
# Filtro 2: Excluyendo por número de cheque específico si no estuvieran en diarios de rechazo
checks_corregidos = checks_raw.filtered(
    lambda c: c.current_journal_id.id not in rejected_journal_ids and c.name not in target_numbers
)
total_corregido = sum(checks_corregidos.mapped('amount'))

print('\nReporte Cheques a fecha CORREGIDO (excluyendo rechazados):')
print('  Total cheques: %d | Total $: %15.2f' % (len(checks_corregidos), total_corregido))
print('  Cheques rechazados excluidos:')
excluded = checks_raw - checks_corregidos
for c in excluded:
    jcode = c.current_journal_id.code if c.current_journal_id else 'None'
    jname = c.current_journal_id.name if c.current_journal_id else 'None'
    print('    - ID=%-5s Núm=%-12s Imp=$ %12.2f DiarioActual=[%s] %s Partner=%s' % (
        c.id, c.name, c.amount, jcode, jname,
        (c.partner_id.name or '')[:30]
    ))
print('  Suma cheques excluidos:    $ %15.2f' % sum(excluded.mapped('amount')))
print('  NUEVA Diferencia con Mayor:$ %15.2f' % (total_corregido - saldo_mayor_to_date))
