#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/RR-8
mkdir -p ~/tmp/RR-8/scripts && cd ~/tmp/RR-8
cat > ~/tmp/RR-8/scripts/08_verificar_solucion.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 08 - Verificación de la solución: Comparación Mayor vs Reporte sin rechazados
from odoo import fields

company = get_company()
h('08 - VERIFICACIÓN EXACTA: MAYOR VS REPORTE (%s)' % company.name)

# 1. Saldo actual del Mayor en la cuenta 1.1.1.02.010 (Cheques de Terceros)
acc_cheq = env['account.account'].with_company(company).search([('code', '=', '1.1.1.02.010')], limit=1)
if not acc_cheq:
    acc_cheq = env['account.account'].with_company(company).search([('name', 'ilike', 'Third Party Checks')], limit=1)

print('Cuenta analizada: [%s] %s' % (acc_cheq.code, acc_cheq.name))
lines = env['account.move.line'].with_company(company).search([
    ('account_id', '=', acc_cheq.id),
    ('parent_state', '=', 'posted')
])
debit = sum(lines.mapped('debit'))
credit = sum(lines.mapped('credit'))
saldo_mayor = debit - credit
print('  Total apuntes en el Mayor: %d' % len(lines))
print('  Debe acumulado:   $ %15.2f' % debit)
print('  Haber acumulado:  $ %15.2f' % credit)
print('  SALDO EN EL MAYOR:$ %15.2f' % saldo_mayor)

# 2. Cheques devueltos actualmente por el wizard
Wizard = env['account.check.to_date.report.wizard']
today = fields.Date.today()
checks_raw = Wizard._get_checks_on_hand(False, today)
total_raw = sum(checks_raw.mapped('amount'))
print('\nReporte Cheques a fecha ACTUAL (con bug):')
print('  Total cheques: %d | Total $: %15.2f' % (len(checks_raw), total_raw))
print('  Diferencia con el Mayor: $ %15.2f' % (total_raw - saldo_mayor))

# 3. Aplicando el filtro excluyendo diarios de rechazo (CHTER, CSH3)
rejected_journal_ids = env['account.journal'].search([
    '|', ('code', 'in', ['CHTER', 'CSH3']),
    ('name', 'ilike', 'rechaz')
]).ids

checks_corregidos = checks_raw.filtered(lambda c: c.current_journal_id.id not in rejected_journal_ids)
total_corregido = sum(checks_corregidos.mapped('amount'))

print('\nReporte Cheques a fecha CORREGIDO (excluyendo diarios de rechazo):')
print('  Total cheques: %d | Total $: %15.2f' % (len(checks_corregidos), total_corregido))
print('  Cheques rechazados excluidos:')
for c in (checks_raw - checks_corregidos):
    print('    - ID=%s Núm=%-12s Imp=%12.2f Diario=[%s] %s Partner=%s' % (
        c.id, c.name, c.amount, c.current_journal_id.code, c.current_journal_id.name,
        (c.partner_id.name or '')[:30]
    ))
print('  NUEVA Diferencia con el Mayor: $ %15.2f' % (total_corregido - saldo_mayor))
__EOF_AUDIT__
chmod +x ~/tmp/RR-8/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/RR-8:'; ls -R ~/tmp/RR-8 | head -50
