# -*- coding: utf-8 -*-
# 02 - Relevamiento de módulos custom (~/src/user), vínculo OC <-> OV, campos, métodos y automatizaciones
import ast
import os

h('02 - MÓDULOS CUSTOM Y VÍNCULO COMPRAS <-> VENTAS')

sub('Módulos instalados NO desarrollados por Odoo S.A.')
Mod = env['ir.module.module']
custom_mods = Mod.search([
    ('state', 'in', ('installed', 'to upgrade', 'to install')),
    ('author', 'not ilike', 'Odoo S.A.'),
], order='name')
for m in custom_mods:
    print('  %-38s | estado=%-10s | ver=%-15s | autor=%-25s | %s' % (
        m.name, m.state, m.installed_version or '-', (m.author or '-')[:25], (m.shortdesc or '')[:60]
    ))

sub('Módulos clave estándar + Atlas')
for mname in [
    'sale_management', 'purchase', 'purchase_requisition', 'account_accountant',
    'l10n_ar', 'web_studio', 'approvals', 'atlas_security_approvals', 'sale_purchase',
    'sale_purchase_stock', 'sale_expense', 'project_purchase',
]:
    m = Mod.search([('name', '=', mname)], limit=1)
    print('  %-32s -> %s' % (mname, m.state if m else 'no encontrado'))

sub('Escaneo de ~/src/user/ en disco (addons del repositorio Odoo.sh)')
user_src = os.path.expanduser('~/src/user')
user_addon_names = set()
relevant_addons = []

if not os.path.isdir(user_src):
    print('  (No existe %s)' % user_src)
else:
    for root, dirs, files in os.walk(user_src):
        dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', 'static', 'i18n'))
        if '__manifest__.py' in files:
            addon_name = os.path.basename(root)
            user_addon_names.add(addon_name)
            mpath = os.path.join(root, '__manifest__.py')
            mrec = Mod.search([('name', '=', addon_name)], limit=1)
            state = mrec.state if mrec else 'no_en_bd'
            manifest = {}
            try:
                with open(mpath, 'r', encoding='utf-8', errors='replace') as fh:
                    manifest = ast.literal_eval(fh.read())
            except Exception as e:
                manifest = {'_error': str(e)}
            rel_path = os.path.relpath(root, user_src)
            print('\n  ADDON: %-35s | estado=%-10s | ruta=%s' % (addon_name, state, rel_path))
            print('    name:    %s' % manifest.get('name'))
            print('    summary: %s' % manifest.get('summary'))
            print('    depends: %s' % manifest.get('depends'))
            print('    data:    %s' % manifest.get('data'))
            # Detectar relevancia con ventas/compras/terceros/atlas/aprobaciones
            blob = (addon_name + ' ' + str(manifest)).lower()
            if any(k in blob for k in ('purchase', 'sale', 'atlas', 'approv', 'aprob', 'tercer', 'gasto', 'partner', 'link', 'vinc')):
                relevant_addons.append((addon_name, root, state))
            # No bajar dentro de subcarpetas de otro addon si ya es un addon
            dirs[:] = []

sub('Campos custom o no-core en purchase.order, purchase.order.line, sale.order, sale.order.line y res.partner')
Models_check = ['purchase.order', 'purchase.order.line', 'sale.order', 'sale.order.line', 'res.partner']
IMD = env['ir.model.data'].sudo()
Fields = env['ir.model.fields'].sudo()

for model_name in Models_check:
    if model_name not in env:
        continue
    print('\n  MODELO: %s' % model_name)
    all_fields = Fields.search([('model', '=', model_name)], order='name')
    # Mapeo field_id -> módulo creador en ir.model.data
    imds = IMD.search([('model', '=', 'ir.model.fields'), ('res_id', 'in', all_fields.ids)])
    mod_by_fid = {d.res_id: d.module for d in imds}

    for f in all_fields:
        origin_mod = mod_by_fid.get(f.id, '-')
        is_x = f.name.startswith('x_') or f.state == 'manual'
        is_user_mod = origin_mod in user_addon_names
        is_cross_link = (
            (model_name.startswith('purchase.') and f.relation in ('sale.order', 'sale.order.line'))
            or (model_name.startswith('sale.') and f.relation in ('purchase.order', 'purchase.order.line'))
        )
        if is_x or is_user_mod or is_cross_link:
            tag = 'USER_MOD' if is_user_mod else ('CROSS_LINK' if is_cross_link else 'MANUAL/X')
            print(
                '    [%-10s] %-34s | tipo=%-10s | rel=%-20s | mod=%-28s | label=%s'
                % (tag, f.name, f.ttype, f.relation or '-', origin_mod, f.field_description)
            )

sub('Código fuente de métodos custom (/src/user/) en modelos clave')
for model_name in Models_check:
    if model_name not in env:
        continue
    cls = type(env[model_name])
    custom_methods = []
    seen = set()
    for k in cls.__mro__:
        for attr_name, val in k.__dict__.items():
            if attr_name in seen or not callable(val):
                continue
            try:
                src_path = (inspect.getsourcefile(val) or '').replace('\\', '/')
            except Exception:
                src_path = ''
            if '/src/user/' in src_path:
                seen.add(attr_name)
                custom_methods.append(attr_name)
    if custom_methods:
        print('\n  Métodos definidos en /src/user/ sobre %s: %s' % (model_name, custom_methods))
        method_sources(model_name, custom_methods, only_custom=True)
    else:
        print('  (%s: sin métodos en /src/user/)' % model_name)

sub('Lectura completa de archivos .py y .xml de addons relevantes en ~/src/user/')
for addon_name, root, state in relevant_addons:
    print('\n' + '#' * 90)
    print('# ADDON RELEVANTE: %s (estado=%s)' % (addon_name, state))
    print('#' * 90)
    for r, ds, fs in os.walk(root):
        ds[:] = sorted(d for d in ds if d not in ('__pycache__', 'static', 'i18n', 'tests'))
        for fn in sorted(fs):
            if fn.endswith(('.py', '.xml')) and fn != '__init__.py':
                fpath = os.path.join(r, fn)
                rel = os.path.relpath(fpath, root)
                print('\n  --- %s/%s ---' % (addon_name, rel))
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                        lines = fh.readlines()
                    max_lines = 250
                    print(''.join(lines[:max_lines]))
                    if len(lines) > max_lines:
                        print('  ... <truncado: %s líneas totales>' % len(lines))
                except Exception as e:
                    print('  <error leyendo archivo: %s>' % e)

sub('Automatizaciones (base.automation) y Acciones de servidor (ir.actions.server code)')
if 'base.automation' in env:
    autos = env['base.automation'].with_context(active_test=False).search([])
    if not autos:
        print('  (Sin base.automation)')
    for a in autos:
        print('\n  AUTO id=%s active=%s name=%s model=%s trigger=%s' % (
            a.id, a.active, a.name, a.model_id.model, a.trigger if has_field('base.automation', 'trigger') else '?'
        ))
        dump(a, names=['filter_domain', 'filter_pre_domain', 'trigger_field_ids', 'action_server_ids'])
        if has_field('base.automation', 'action_server_ids'):
            for srv in a.action_server_ids:
                dump(srv, names=['name', 'state', 'code'], full=['code'])

if 'ir.actions.server' in env:
    srvs = env['ir.actions.server'].search([
        ('state', '=', 'code'),
        ('model_id.model', 'in', Models_check + ['studio.approval.rule', 'studio.approval.entry', 'studio.approval.request']),
    ])
    print('\n  ir.actions.server (state=code) sobre modelos clave: %s' % len(srvs))
    for s in srvs:
        print('  SRV id=%s model=%s name=%s' % (s.id, s.model_id.model, s.name))
        dump(s, names=['code'], full=['code'])

sub('Ejemplos reales en BD de OC vinculadas a OV (si hay campos detectados)')
if 'purchase.order' in env:
    po_model = env['purchase.order']
    sale_link_fields = [
        fn for fn, f in po_model._fields.items()
        if getattr(f, 'comodel_name', None) in ('sale.order', 'sale.order.line')
    ]
    print('  Campos en purchase.order hacia sale.order*: %s' % sale_link_fields)
    for fn in sale_link_fields:
        linked = po_model.search([(fn, '!=', False)], order='id desc', limit=5)
        print('  OC con %s poblado: %s' % (fn, len(linked)))
        for po in linked:
            print('    PO %s (id=%s, state=%s, partner=%s) -> %s=%s' % (
                po.name, po.id, po.state, po.partner_id.name, fn, fmt(po, fn)
            ))

if 'sale.order' in env:
    so_model = env['sale.order']
    po_link_fields = [
        fn for fn, f in so_model._fields.items()
        if getattr(f, 'comodel_name', None) in ('purchase.order', 'purchase.order.line')
    ]
    print('  Campos en sale.order hacia purchase.order*: %s' % po_link_fields)
    for fn in po_link_fields:
        linked = so_model.search([(fn, '!=', False)], order='id desc', limit=5)
        print('  OV con %s poblado: %s' % (fn, len(linked)))
        for so in linked:
            print('    SO %s (id=%s, state=%s, partner=%s) -> %s=%s' % (
                so.name, so.id, so.state, so.partner_id.name, fn, fmt(so, fn)
            ))
