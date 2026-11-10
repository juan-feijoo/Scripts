# -*- coding: utf-8 -*-
# 01 - Módulos instalados y modelos de cheques
company = get_company()
h('01 - MÓDULOS INSTALADOS Y MODELOS DE CHEQUES (%s)' % company.name)

sub('Módulos relacionados a cheques y localización argentina')
modules = env['ir.module.module'].search([
    ('state', '=', 'installed'),
    '|', '|', '|',
    ('name', 'ilike', 'check'),
    ('name', 'ilike', 'l10n_latam'),
    ('name', 'ilike', 'l10n_ar'),
    ('author', 'not ilike', 'Odoo S.A.')
])
for m in sorted(modules, key=lambda x: x.name):
    custom_tag = '[CUSTOM/TERCERO]' if 'Odoo S.A.' not in (m.author or '') else '[OFICIAL]'
    print('  %-35s %-12s %-20s %s' % (m.name, m.installed_version or '', custom_tag, (m.author or '')[:30]))

sub('Modelos de cheques detectados en el sistema')
candidates = [
    'account.payment',
    'account.check',
    'account.third.party.checks',
    'l10n_latam.check',
    'account.check.operation',
    'account.payment.register',
    'account.move',
    'account.move.line'
]
for model_name in candidates:
    exists = model_name in env
    status = 'PRESENTE' if exists else 'NO EXISTE'
    print('  %-30s: %s' % (model_name, status))
    if exists:
        model = env[model_name]
        check_fields = [f for f in sorted(model._fields) if any(k in f.lower() for k in ('check', 'rechaz', 'reject', 'estado', 'third_party'))]
        if check_fields:
            print('    Campos relevantes: %s' % ', '.join(check_fields))
        for state_fname in ('state', 'check_state', 'l10n_latam_check_state', 'status'):
            if state_fname in model._fields:
                field = model._fields[state_fname]
                sel = getattr(field, 'selection', None)
                print('    Selección de %s: %s' % (state_fname, sel))
