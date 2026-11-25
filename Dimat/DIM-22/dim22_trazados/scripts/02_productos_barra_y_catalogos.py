# -*- coding: utf-8 -*-
# 02 - Productos con prefijo "/", etiquetas, categorías, advertencias y campos custom (solo lectura)
import re

h('02 - PRODUCTOS CON %r, ETIQUETAS, ADVERTENCIAS Y CAMPOS CUSTOM' % TRACED_PREFIX)

PT = env['product.template'].with_context(active_test=False)
all_count = PT.search_count([])
active_count = env['product.template'].search_count([])
print('Total product.template: %s (activos=%s, archivados=%s)' % (all_count, active_count, all_count - active_count))

traced_prefix_recs = PT.search([('name', '=like', TRACED_PREFIX + '%')], order='name, id')
# Por si alguno tiene espacios antes de la barra
leading_ws_recs = PT.search([('name', 'ilike', TRACED_PREFIX)], order='name, id').filtered(
    lambda p: (p.name or '').lstrip().startswith(TRACED_PREFIX) and p.id not in traced_prefix_recs.ids
)
traced_recs = traced_prefix_recs | leading_ws_recs

print('Productos cuyo nombre empieza con %r: %s (con espacio inicial=%s)' % (
    TRACED_PREFIX, len(traced_recs), len(leading_ws_recs),
))

# También revisar otros que tengan "/" en el nombre o referencia sin empezar con "/"
other_slash = PT.search([('name', 'ilike', '/'), ('id', 'not in', traced_recs.ids)], order='name')
print('Otros productos que contienen "/" en otro lugar del nombre: %s' % len(other_slash))
for p in other_slash[:25]:
    print('  [otro "/"] id=%s | active=%s | ref=%r | name=%r' % (p.id, p.active, p.default_code, p.name))

sub('Listado completo de productos que empiezan con %r (%s)' % (TRACED_PREFIX, len(traced_recs)))
for p in traced_recs:
    extras = []
    if has_field('product.template', 'is_storable'):
        extras.append('storable=%s' % p.is_storable)
    if has_field('product.template', 'website_published'):
        extras.append('web_pub=%s' % p.website_published)
    elif has_field('product.template', 'is_published'):
        extras.append('is_pub=%s' % p.is_published)
    if has_field('product.template', 'product_tag_ids') and p.product_tag_ids:
        extras.append('tags=%s' % p.product_tag_ids.mapped('name'))
    if has_field('product.template', 'sale_line_warn') and p.sale_line_warn != 'no-message':
        extras.append('sale_warn=%s:%r' % (p.sale_line_warn, p.sale_line_warn_msg))
    if has_field('product.template', 'purchase_line_warn') and p.purchase_line_warn != 'no-message':
        extras.append('purch_warn=%s:%r' % (p.purchase_line_warn, p.purchase_line_warn_msg))
    if len(p.product_variant_ids) > 1:
        extras.append('variantes=%s' % len(p.product_variant_ids))
    # Valores no vacíos de campos custom x_*
    x_vals = {}
    for fname in sorted(p._fields):
        if fname.startswith('x_'):
            val = fmt(p, fname, max_len=120)
            if val not in (False, None, '', 0, 0.0, '[]'):
                x_vals[fname] = val
    if x_vals:
        extras.append('x_=%s' % x_vals)

    print('  id=%-5s | act=%-5s | ref=%-15r | type=%-7s | track=%-6s | sale=%s | purch=%s | categ=%r | name=%r%s' % (
        p.id, p.active, p.default_code or '', p.type,
        p.tracking if has_field('product.template', 'tracking') else '-',
        p.sale_ok if has_field('product.template', 'sale_ok') else '-',
        p.purchase_ok if has_field('product.template', 'purchase_ok') else '-',
        p.categ_id.complete_name if p.categ_id else '', p.name,
        (' | ' + ' | '.join(extras)) if extras else '',
    ))

sub('Productos con advertencia nativa (sale_line_warn / purchase_line_warn != no-message)')
for wf in ('sale_line_warn', 'purchase_line_warn'):
    if has_field('product.template', wf):
        wrecs = PT.search([(wf, '!=', 'no-message'), (wf, '!=', False)])
        print('  %s activos/totales configurados: %s' % (wf, len(wrecs)))
        for p in wrecs[:30]:
            msg_f = wf + '_msg'
            print('    id=%s | name=%r | %s=%s | msg=%r' % (
                p.id, p.name, wf, p[wf], p[msg_f] if has_field('product.template', msg_f) else '',
            ))

if 'product.tag' in env:
    sub('Etiquetas de producto existentes (product.tag)')
    tags = env['product.tag'].search([], order='name')
    print('Total product.tag: %s' % len(tags))
    for t in tags:
        cnt_all = PT.search_count([('product_tag_ids', 'in', [t.id])])
        cnt_traced = PT.search_count([('id', 'in', traced_recs.ids), ('product_tag_ids', 'in', [t.id])])
        print('  id=%-4s | color=%-3s | total_prods=%-4s | en_barra=%-4s | name=%r' % (
            t.id, t.color if has_field('product.tag', 'color') else '-', cnt_all, cnt_traced, t.name,
        ))

sub('Categorías de producto (product.category) con conteo')
for c in env['product.category'].search([], order='complete_name'):
    cnt_all = PT.search_count([('categ_id', '=', c.id)])
    cnt_traced = PT.search_count([('id', 'in', traced_recs.ids), ('categ_id', '=', c.id)])
    if cnt_all or cnt_traced:
        print('  id=%-4s | total=%-5s | en_barra=%-4s | %s' % (c.id, cnt_all, cnt_traced, c.complete_name))

sub('Campos custom (x_* o state=manual) en modelos de producto, venta, compra, stock y factura')
check_models = [
    'product.template', 'product.product',
    'sale.order', 'sale.order.line',
    'purchase.order', 'purchase.order.line',
    'stock.picking', 'stock.move', 'stock.move.line',
    'account.move', 'account.move.line',
]
custom_fields = env['ir.model.fields'].search([
    ('model', 'in', check_models),
    '|', ('name', '=like', 'x_%'), ('state', '=', 'manual'),
], order='model, name')
print('Total campos custom en esos modelos: %s' % len(custom_fields))
for f in custom_fields:
    print('  %-22s | %-35s | %-12s | state=%-7s | label=%r' % (
        f.model, f.name, f.ttype, f.state, f.field_description,
    ))
