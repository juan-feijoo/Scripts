# -*- coding: utf-8 -*-
# 06 - Inspección de product_brand_sale_purchase, campo is_trazado, x_studio_marca y volumen general (solo lectura)
import os
from odoo.modules.module import get_module_path

h('06 - INSPECCIÓN DE product_brand_sale_purchase, is_trazado Y x_studio_marca')

# 1. Código fuente instalado de product_brand_sale_purchase
mod_path = get_module_path('product_brand_sale_purchase')
print('Ruta product_brand_sale_purchase: %s' % mod_path)
if mod_path and os.path.isdir(mod_path):
    for root, dirs, files in os.walk(mod_path):
        dirs[:] = sorted(d for d in dirs if not d.startswith('__pycache__') and d != '.git')
        for fn in sorted(files):
            fpath = os.path.join(root, fn)
            rel = os.path.relpath(fpath, mod_path).replace('\\', '/')
            sub('FILE product_brand_sale_purchase/%s' % rel)
            if fn.endswith(('.py', '.xml', '.csv', '.md', '.txt', '.js')):
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                        txt = fh.read()
                    print(txt[:30000])
                    if len(txt) > 30000:
                        print('... <truncado, %s chars>' % len(txt))
                except Exception as e:
                    print('  <error leyendo: %s>' % e)

# 2. Campos / modelos / XML IDs registrados por product_brand_sale_purchase
sub('ir.model.data de product_brand_sale_purchase')
imds = env['ir.model.data'].search([('module', '=', 'product_brand_sale_purchase')], order='model, name')
for r in imds:
    print('  %-28s | id=%-6s | %s.%s' % (r.model, r.res_id, r.module, r.name))

# 3. Cruce real de is_trazado, prefijo "/" y x_studio_marca en product.template
sub('Cruce en product.template: prefijo "/", is_trazado y x_studio_marca')
PT = env['product.template'].with_context(active_test=False)
has_traz = has_field('product.template', 'is_trazado')
has_marca = has_field('product.template', 'x_studio_marca')
print('has_field is_trazado=%s | has_field x_studio_marca=%s' % (has_traz, has_marca))

slash_prods = PT.search([('name', '=like', TRACED_PREFIX + '%')], order='name')
traz_prods = PT.search([('is_trazado', '=', True)], order='name') if has_traz else PT.browse()
inf_prods = PT.search([
    '|', ('x_studio_marca', 'ilike', 'inf'), ('x_studio_marca', 'ilike', '/'),
], order='name') if has_marca else PT.browse()

print('Productos con prefijo "/": %s' % len(slash_prods))
print('Productos con is_trazado=True: %s' % len(traz_prods))
print('Productos con x_studio_marca con "/" o "inf": %s' % len(inf_prods))
if has_traz:
    print('  "/" con is_trazado=True : %s' % len(slash_prods.filtered('is_trazado')))
    print('  "/" con is_trazado=False: %s' % len(slash_prods.filtered(lambda p: not p.is_trazado)))
    only_traz = traz_prods - slash_prods
    print('  is_trazado=True SIN "/": %s' % len(only_traz))
    for p in only_traz[:30]:
        print('    [solo is_trazado] id=%s | ref=%r | marca=%r | name=%r' % (
            p.id, p.default_code, p.x_studio_marca if has_marca else '-', p.name,
        ))

if has_marca:
    only_inf = inf_prods - slash_prods - traz_prods
    print('  x_studio_marca con "/" o "inf" SIN "/" ni is_trazado: %s' % len(only_inf))
    for p in only_inf[:40]:
        print('    [solo marca] id=%s | ref=%r | marca=%r | name=%r' % (
            p.id, p.default_code, p.x_studio_marca, p.name,
        ))
    # Valores distintos de x_studio_marca que tengan '/' o 'inf'
    distinct_marcas = sorted({p.x_studio_marca for p in inf_prods if p.x_studio_marca})
    print('Valores distintos de x_studio_marca con "/" o "inf": %s' % distinct_marcas)

# 4. Volumen general de documentos en la base (para entender el estado de la BD)
sub('Volumen general de registros en esta base')
for mdl in ('res.partner', 'product.template', 'sale.order', 'purchase.order', 'stock.picking', 'account.move'):
    if mdl in env:
        cnt = env[mdl].with_context(active_test=False).search_count([])
        print('  %-20s %s' % (mdl, cnt))
