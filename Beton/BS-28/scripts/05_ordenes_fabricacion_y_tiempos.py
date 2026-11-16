# -*- coding: utf-8 -*-
# 05 - Órdenes de fabricación (mrp.production), Órdenes de trabajo (mrp.workorder) y comparativa de tiempos
h('05 - ÓRDENES DE FABRICACIÓN, ÓRDENES DE TRABAJO Y SIMULACIÓN DE TIEMPOS')

if not has_model('mrp.production'):
    print('!! mrp.production no existe en esta base.')
else:
    MO = env['mrp.production']
    WO = env['mrp.workorder']

    sub('Distribución de cantidades en Órdenes de Fabricación')
    total_mos = MO.search_count([])
    print('Total MOs: %s' % total_mos)
    for st in ('draft', 'confirmed', 'progress', 'to_close', 'done', 'cancel'):
        cnt = MO.search_count([('state', '=', st)])
        if cnt:
            print('  estado %-12s: %s' % (st, cnt))

    buckets = [
        ('<= 1 m3 (pedidos pequeños)', [('product_qty', '<=', 1.0)]),
        ('1 < Q <= 3', [('product_qty', '>', 1.0), ('product_qty', '<=', 3.0)]),
        ('3 < Q <= 6', [('product_qty', '>', 3.0), ('product_qty', '<=', 6.0)]),
        ('6 < Q <= 8', [('product_qty', '>', 6.0), ('product_qty', '<=', 8.0)]),
        ('> 8', [('product_qty', '>', 8.0)]),
    ]
    print('\nDistribución por volumen/cantidad:')
    for label, dom in buckets:
        print('  %-28s: %s' % (label, MO.search_count(dom)))

    sub('Muestra de Órdenes de Fabricación recientes y pedidos pequeños (<= 2)')
    small_mos = MO.search([('product_qty', '<=', 2.0), ('state', '!=', 'cancel')], order='id desc', limit=10)
    recent_mos = MO.search([('state', '!=', 'cancel')], order='id desc', limit=15)
    sample_mos = (small_mos | recent_mos).sorted(key=lambda r: r.id, reverse=True)

    for mo in sample_mos:
        print('\n[MO %s | id=%s | state=%s] prod=%s | qty=%.3f %s | bom=%s (bom_qty=%s) | origin=%s' % (
            mo.name, mo.id, mo.state,
            mo.product_id.display_name,
            mo.product_qty,
            mo.product_uom_id.name if mo.product_uom_id else '-',
            mo.bom_id.display_name if mo.bom_id else '-',
            mo.bom_id.product_qty if mo.bom_id else '-',
            val(mo, 'origin'),
        ))
        print('  planificadas: %s -> %s | reales: %s -> %s' % (
            val(mo, 'date_start'), val(mo, 'date_finished'),
            val(mo, 'date_start_wo') if has_field('mrp.production', 'date_start_wo') else '-',
            val(mo, 'date_finished_wo') if has_field('mrp.production', 'date_finished_wo') else '-',
        ))
        for wo in mo.workorder_ids:
            q = wo.qty_production or mo.product_qty or 0.0
            t_prop_add = BASE_PREP_MIN + RATE_MIN_PER_M3 * q
            t_prop_floor = max(BASE_PREP_MIN, RATE_MIN_PER_M3 * q)
            print('  >> WO [id=%s state=%s] wc=%-22s op=%-22s | qty=%.3f | exp=%.2f min | real=%.2f min | prop(5+2.8Q)=%.2f | prop(max)=%.2f' % (
                wo.id, wo.state,
                wo.workcenter_id.name if wo.workcenter_id else '-',
                wo.operation_id.name if wo.operation_id else wo.name,
                q,
                val(wo, 'duration_expected') or 0.0,
                val(wo, 'duration') or 0.0,
                t_prop_add,
                t_prop_floor,
            ))

    sub('Resumen comparativo en órdenes de trabajo (últimas 30 no canceladas)')
    wos = WO.search([('state', '!=', 'cancel')], order='id desc', limit=30)
    print('%-16s %-22s %8s %10s %10s %11s %11s' % (
        'MO', 'Workcenter', 'Qty', 'OdooExp', 'RealMin', '5+2.8*Q', 'max(5,2.8Q)'
    ))
    print('-' * 96)
    for wo in wos:
        q = wo.qty_production or 0.0
        print('%-16s %-22s %8.2f %10.2f %10.2f %11.2f %11.2f' % (
            (wo.production_id.name or '-')[:16],
            (wo.workcenter_id.name or '-')[:22],
            q,
            val(wo, 'duration_expected') or 0.0,
            val(wo, 'duration') or 0.0,
            BASE_PREP_MIN + RATE_MIN_PER_M3 * q,
            max(BASE_PREP_MIN, RATE_MIN_PER_M3 * q),
        ))

    sub('Inspección de cálculo _get_duration_expected() en workorders recientes (solo lectura)')
    for wo in wos[:5]:
        print('\nWO id=%s (%s | wc=%s | op=%s):' % (
            wo.id, wo.production_id.name, wo.workcenter_id.name, wo.name
        ))
        if wo.workcenter_id and hasattr(wo.workcenter_id, '_get_capacity'):
            bom_qty = (wo.production_bom_id.product_qty if has_field('mrp.workorder', 'production_bom_id') and wo.production_bom_id else (wo.production_id.bom_id.product_qty if wo.production_id.bom_id else 1.0)) or 1.0
            res_cap = safe(wo.workcenter_id._get_capacity, wo.product_id, wo.product_uom_id, bom_qty)
            print('  _get_capacity(product, uom, bom_qty=%s) -> %r' % (bom_qty, res_cap))
        if hasattr(wo, '_get_duration_expected'):
            res_dur = safe(wo._get_duration_expected)
            print('  _get_duration_expected() -> %r' % res_dur)

env.cr.rollback()
