# -*- coding: utf-8 -*-
# 03 - Unidades de medida, Productos, Listas de Materiales (BoMs) y Operaciones de Rutas
h('03 - UOM, PRODUCTOS, BOMS Y OPERACIONES (mrp.routing.workcenter)')

sub('Unidades de Medida (uom.uom) relacionadas con volumen / tiempo / unidades')
uoms = env['uom.uom'].with_context(active_test=False).search([], order='id')
for u in uoms:
    uname = (u.name or '').lower()
    cat_or_rel = val(u, 'category_id') or val(u, 'relative_uom_id')
    cname = cat_or_rel.name.lower() if cat_or_rel else ''
    if any(k in uname or k in cname for k in ('m3', 'm³', 'cub', 'vol', 'hora', 'hour', 'min', 'time', 'tiempo', 'unid', 'unit', 'litro')):
        dump(u, names=['id', 'name', 'category_id', 'relative_uom_id', 'uom_type', 'factor', 'factor_inv', 'relative_factor', 'rounding', 'active'])
        print('  ---')

if not has_model('mrp.bom'):
    print('!! mrp.bom no existe en esta base.')
else:
    boms = env['mrp.bom'].with_context(active_test=False).search([], order='company_id, id')
    sub('Listas de Materiales (mrp.bom): total=%s' % len(boms))
    for bom in boms:
        tmpl = bom.product_tmpl_id
        prod = bom.product_id
        print('\n[BoM id=%s active=%s] prod_tmpl=%s | variant=%s | qty=%s %s | type=%s | company=%s | ops=%s' % (
            bom.id,
            bom.active,
            tmpl.display_name if tmpl else '-',
            prod.display_name if prod else '(todas)',
            bom.product_qty,
            bom.product_uom_id.name if bom.product_uom_id else '-',
            bom.type,
            bom.company_id.name if bom.company_id else '(todas)',
            len(bom.operation_ids),
        ))
        # Configuración de producto relevante para MRP / Venta / Planeación
        if tmpl:
            p_info = []
            for fn in ('type', 'uom_id', 'uom_po_id', 'planning_enabled', 'planning_role_id', 'service_tracking', 'sale_ok', 'purchase_ok'):
                if fn in tmpl._fields:
                    p_info.append('%s=%s' % (fn, fmt(tmpl, fn)))
            if 'route_ids' in tmpl._fields:
                p_info.append('routes=%s' % ', '.join(tmpl.route_ids.mapped('name')))
            print('  Producto tmpl: ' + ' | '.join(p_info))

        for op in bom.operation_ids:
            print('  >> Operación [op id=%s seq=%s] %s' % (op.id, op.sequence, op.name))
            dump(op, prefixes=[''], max_len=250)

    sub('Todas las operaciones mrp.routing.workcenter huérfanas o fuera de BoMs activas')
    all_ops = env['mrp.routing.workcenter'].with_context(active_test=False).search([], order='workcenter_id, id')
    print('Total operaciones en mrp.routing.workcenter: %s' % len(all_ops))
    for op in all_ops:
        bom = op.bom_id
        print('  [op id=%s active=%s] %-28s | wc=%-22s | bom=%s (qty=%s %s) | mode=%s | batch=%s | manual=%.2f | cycle=%.2f' % (
            op.id,
            val(op, 'active'),
            op.name,
            op.workcenter_id.name if op.workcenter_id else '-',
            bom.display_name if bom else '(sin bom)',
            bom.product_qty if bom else '-',
            bom.product_uom_id.name if (bom and bom.product_uom_id) else '-',
            val(op, 'time_mode'),
            val(op, 'time_mode_batch'),
            val(op, 'time_cycle_manual') or 0.0,
            val(op, 'time_cycle') or 0.0,
        ))
