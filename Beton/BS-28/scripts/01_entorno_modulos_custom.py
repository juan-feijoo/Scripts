# -*- coding: utf-8 -*-
# 01 - Entorno, versión de Odoo, módulos instalados y personalizaciones (MRP / Planning)
from odoo import release

h('01 - ENTORNO, MÓDULOS Y PERSONALIZACIONES (SOLO LECTURA)')
print('DB: %s' % env.cr.dbname)
print('Odoo release: %s | version_info: %s' % (release.version, release.version_info))
print('Usuario shell: %s (id=%s)' % (env.user.name, env.user.id))

sub('Compañías')
for c in env['res.company'].search([], order='id'):
    print('  [%s] %s | país=%s | moneda=%s' % (
        c.id, c.name, c.country_id.code if c.country_id else '-', c.currency_id.name if c.currency_id else '-'
    ))

sub('Estado de módulos clave (Manufactura, Planeación, Recursos, Flota)')
target_mods = [
    'mrp', 'mrp_workorder', 'mrp_workorder_hr', 'mrp_mps', 'mrp_account', 'mrp_account_enterprise',
    'sale_mrp', 'mrp_maintenance', 'quality_mrp', 'quality_mrp_workorder',
    'planning', 'sale_planning', 'project_planning', 'hr_planning', 'planning_holidays',
    'resource', 'fleet', 'maintenance', 'stock', 'sale_management', 'web_studio',
]
IrModule = env['ir.module.module']
mods = {m.name: m for m in IrModule.search([('name', 'in', target_mods)])}
for name in target_mods:
    m = mods.get(name)
    state = m.state if m else 'no encontrado'
    ver = m.installed_version if m else '-'
    print('  %-26s %-15s %s' % (name, state, ver))

sub('Módulos custom / terceros instalados (author != Odoo S.A.)')
custom_mods = IrModule.search([('state', '=', 'installed')], order='name')
found_custom = False
for m in custom_mods:
    author = m.author or ''
    if 'Odoo S.A.' not in author and 'Odoo SA' not in author:
        found_custom = True
        print('  %-35s v=%-16s author=%r | summary=%s' % (
            m.name, m.installed_version or '-', author, (m.shortdesc or '')[:80]
        ))
if not found_custom:
    print('  (ninguno)')

sub('Campos custom / Studio (x_*) en modelos de Manufactura / Planeación / Venta')
target_models = [
    'mrp.workcenter', 'mrp.workcenter.capacity', 'mrp.routing.workcenter',
    'mrp.bom', 'mrp.bom.line', 'mrp.production', 'mrp.workorder',
    'planning.slot', 'planning.role', 'planning.slot.template',
    'resource.resource', 'resource.calendar',
    'product.template', 'product.product', 'sale.order', 'sale.order.line',
]
existing_models = [m for m in target_models if has_model(m)]
x_fields = env['ir.model.fields'].search([
    ('model', 'in', existing_models),
    ('name', '=like', 'x_%'),
], order='model, name')
for f in x_fields:
    print('  %-28s %-32s %-14s (%s)' % (f.model, f.name, f.ttype, f.field_description))
if not x_fields:
    print('  (ninguno en los modelos relevados)')

sub('Automatizaciones (base.automation) - todas (activas e inactivas)')
if has_model('base.automation'):
    autos = env['base.automation'].with_context(active_test=False).search([], order='id')
    for a in autos:
        mname = a.model_id.model if a.model_id else '-'
        print('  [id=%s active=%s] %-40s model=%-24s trigger=%s' % (
            a.id, a.active, a.name, mname, val(a, 'trigger')
        ))
        if mname in existing_models or any(k in (a.name or '').lower() for k in ('hormig', 'planta', 'mrp', 'plan', 'tiempo', 'ciclo', 'prorrate')):
            actions = val(a, 'action_server_ids') or env['ir.actions.server']
            for act in actions:
                print('      -> server_action [id=%s] %s (state=%s)' % (act.id, act.name, act.state))
                if val(act, 'code'):
                    print('         CODE:\n' + '\n'.join('           ' + ln for ln in act.code.splitlines()[:60]))
            if val(a, 'code'):
                print('      CODE:\n' + '\n'.join('        ' + ln for ln in a.code.splitlines()[:60]))
else:
    print('  (base.automation no instalado)')

sub('Acciones de servidor (ir.actions.server) en modelos MRP / Planning / Resource')
srv_actions = env['ir.actions.server'].search([
    ('model_id.model', 'in', existing_models),
    ('state', '=', 'code'),
], order='model_id, id')
for act in srv_actions:
    print('  [id=%s] %-40s model=%s' % (act.id, act.name, act.model_id.model))
    if val(act, 'code'):
        print('    ' + '\n    '.join(act.code.splitlines()[:60]))
if not srv_actions:
    print('  (ninguna con state=code en esos modelos)')

sub('Crons relacionados (ir.cron)')
crons = env['ir.cron'].with_context(active_test=False).search([
    '|', '|', '|',
    ('model_id.model', 'in', existing_models),
    ('name', 'ilike', 'plan'),
    ('name', 'ilike', 'mrp'),
    ('name', 'ilike', 'hormig'),
], order='id')
for cr in crons:
    print('  [id=%s active=%s] %-45s model=%s' % (
        cr.id, cr.active, cr.name, cr.model_id.model if cr.model_id else '-'
    ))
