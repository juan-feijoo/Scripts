# -*- coding: utf-8 -*-
# 02 - Centros de trabajo (mrp.workcenter), capacidades por producto, recursos y productividad
h('02 - CENTROS DE TRABAJO, CAPACIDADES Y RECURSOS')

if not has_model('mrp.workcenter'):
    print('!! El modelo mrp.workcenter no existe en esta base (MRP no instalado).')
else:
    domain = [('name', 'ilike', WORKCENTER_KW)] if WORKCENTER_KW else []
    workcenters = env['mrp.workcenter'].with_context(active_test=False).search(domain, order='company_id, sequence, id')
    print('Total centros de trabajo encontrados (filtro=%r): %s' % (WORKCENTER_KW or 'TODOS', len(workcenters)))

    for wc in workcenters:
        sub('Workcenter: %s (id=%s | active=%s)' % (wc.display_name, wc.id, wc.active))
        dump(wc, prefixes=[''], max_len=400)

        if has_field('mrp.workcenter', 'capacity_ids') and wc.capacity_ids:
            print('\n  >> Capacidades específicas por producto (mrp.workcenter.capacity):')
            for cap in wc.capacity_ids:
                print('    - [cap id=%s] product=%s | uom=%s | capacity=%s | time_start=%s | time_stop=%s' % (
                    cap.id,
                    val(cap, 'product_id') and cap.product_id.display_name,
                    val(cap, 'product_uom_id') and cap.product_uom_id.name,
                    val(cap, 'capacity'),
                    val(cap, 'time_start'),
                    val(cap, 'time_stop'),
                ))

        res = val(wc, 'resource_id')
        if res:
            print('\n  >> Resource asociado (resource.resource id=%s):' % res.id)
            dump(res, prefixes=[''], max_len=300)

        cal = val(wc, 'resource_calendar_id') or (res and val(res, 'calendar_id'))
        if cal:
            print('\n  >> Calendario laboral: %s (id=%s | hours_per_day=%s | tz=%s)' % (
                cal.name, cal.id, val(cal, 'hours_per_day'), val(cal, 'tz')
            ))
            for att in val(cal, 'attendance_ids') or []:
                print('    - %s | día=%s | %s a %s | período=%s' % (
                    att.name, val(att, 'dayofweek'), val(att, 'hour_from'), val(att, 'hour_to'), val(att, 'day_period')
                ))

    if has_model('mrp.workcenter.capacity'):
        sub('Resumen completo de mrp.workcenter.capacity')
        caps = env['mrp.workcenter.capacity'].search([], order='workcenter_id, id')
        print('Total registros capacity_ids: %s' % len(caps))
        for cap in caps[:60]:
            dump(cap, prefixes=[''], max_len=200)
            print('  ---')

    if has_model('mrp.workcenter.productivity'):
        sub('Productividad / Tiempos reales registrados (mrp.workcenter.productivity)')
        prod_logs = env['mrp.workcenter.productivity'].search([], order='id desc', limit=20)
        print('Total registros productividad: %s (mostrando últimos %s)' % (
            env['mrp.workcenter.productivity'].search_count([]), len(prod_logs)
        ))
        for pl in prod_logs:
            print('  [id=%s] wc=%-22s wo=%-25s loss=%-20s dur=%.2f min (%s -> %s)' % (
                pl.id,
                pl.workcenter_id.name if pl.workcenter_id else '-',
                pl.workorder_id.display_name if pl.workorder_id else '-',
                pl.loss_id.name if pl.loss_id else '-',
                val(pl, 'duration') or 0.0,
                val(pl, 'date_start'),
                val(pl, 'date_end'),
            ))
