# -*- coding: utf-8 -*-
# 09 - Script de corrección controlada (Dry-Run por defecto)
# Permite simular y, con DRY_RUN=0, aplicar el pase de los 3 cheques al diario de rechazo
import os
from odoo import fields

company = get_company()
DRY_RUN = os.environ.get('DRY_RUN', '1') == '1'

h('09 - FIX CONTROLADO DE CHEQUES RECHAZADOS (DRY_RUN=%s, %s)' % (DRY_RUN, company.name))

target_numbers = ['64943755', '90000059', '90000058']
sub('1. Búsqueda de cheques objetivo')
checks = env['l10n_latam.check'].with_company(company).search([('name', 'in', target_numbers)])
print('Cheques encontrados: %d de %d' % (len(checks), len(target_numbers)))

sub('2. Identificación del diario de destino de cheques rechazados')
journal_rejected = env['account.journal'].with_company(company).search([
    ('code', '=', 'CHTER')
], limit=1)

if not journal_rejected:
    journal_rejected = env['account.journal'].with_company(company).search([
        '|', ('code', 'in', ['CHTER', 'CSH3']),
        ('name', 'ilike', 'rechaz')
    ], limit=1)

if not journal_rejected:
    print('!! ERROR: No se encontró diario de cheques rechazados.')
else:
    print('Diario de rechazo encontrado: [%s] %s (ID=%s)' % (
        journal_rejected.code, journal_rejected.name, journal_rejected.id
    ))

cheqt = env['account.journal'].with_company(company).search([('code', '=', 'CHEQT')], limit=1)
Wizard = env['account.check.to_date.report.wizard']
target_date = fields.Date.from_string('2026-11-06')

if cheqt and Wizard:
    before_checks = Wizard._get_checks_on_hand(cheqt.id, target_date)
    print('\n[ANTES] Total en Reporte Cheques a fecha (CHEQT): %d cheques | $ %.2f' % (
        len(before_checks), sum(before_checks.mapped('amount'))
    ))

sub('3. Evaluación y aplicación de cambios')
for chk in checks:
    print('\nCheque ID=%s | Núm=%s | Importe=$ %.2f' % (chk.id, chk.name, chk.amount))
    print('  Diario actual: [%s] %s' % (
        chk.current_journal_id.code if chk.current_journal_id else 'None',
        chk.current_journal_id.name if chk.current_journal_id else 'None'
    ))
    
    if journal_rejected and chk.current_journal_id != journal_rejected:
        if DRY_RUN:
            print('  -> [DRY-RUN] Se actualizaría current_journal_id -> [%s] %s' % (
                journal_rejected.code, journal_rejected.name
            ))
        else:
            print('  -> [APLICANDO] Actualizando current_journal_id -> [%s] %s' % (
                journal_rejected.code, journal_rejected.name
            ))
            chk.write({'current_journal_id': journal_rejected.id})
    else:
        print('  -> El cheque ya se encuentra en el diario de rechazo o no requiere cambio.')

if cheqt and Wizard:
    after_checks = Wizard._get_checks_on_hand(cheqt.id, target_date)
    print('\n[DESPUÉS DE SIMULACIÓN] Total en Reporte Cheques a fecha (CHEQT): %d cheques | $ %.2f' % (
        len(after_checks), sum(after_checks.mapped('amount'))
    ))

if DRY_RUN:
    print('\nModo DRY-RUN activo: no se guardaron cambios en la base de datos (rollback automático).')
    print('Para aplicar definitivamente los cambios correr con: DRY_RUN=0')
    env.cr.rollback()
else:
    print('\nAplicando cambios definitivamente...')
    env.cr.commit()
    print('>> Cambios confirmados con commit exitosamente.')
