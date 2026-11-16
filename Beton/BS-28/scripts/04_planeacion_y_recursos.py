# -*- coding: utf-8 -*-
# 04 - Módulo de Planeación (planning), Roles, Recursos Materiales y Turnos (slots)
h('04 - PLANEACIÓN (planning), ROLES, RECURSOS Y SLOTS')

if has_model('planning.role'):
    sub('Roles de Planeación (planning.role)')
    roles = env['planning.role'].with_context(active_test=False).search([], order='sequence, id')
    print('Total roles: %s' % len(roles))
    for r in roles:
        dump(r, prefixes=[''], max_len=250)
        print('  ---')
else:
    print('  (planning.role no instalado)')

if has_model('resource.resource'):
    sub('Recursos Materiales y Asociados a Centros de Trabajo (resource.resource)')
    resources = env['resource.resource'].with_context(active_test=False).search([], order='resource_type, id')
    print('Total recursos en resource.resource: %s' % len(resources))
    wc_res_ids = set()
    if has_model('mrp.workcenter'):
        wc_res_ids = set(env['mrp.workcenter'].with_context(active_test=False).search([]).mapped('resource_id').ids)
    for res in resources:
        rtype = val(res, 'resource_type')
        is_wc = res.id in wc_res_ids
        if rtype == 'material' or is_wc or any(k in (res.name or '').lower() for k in ('plant', 'hormig', 'mixer', 'camion', 'bomba', 'dosif')):
            print('  [res id=%s active=%s wc=%s] name=%-30s | type=%-10s | eff=%s | cal=%s | roles=%s | default_role=%s' % (
                res.id,
                res.active,
                is_wc,
                res.name,
                rtype,
                val(res, 'time_efficiency'),
                res.calendar_id.name if val(res, 'calendar_id') else '-',
                ', '.join(res.role_ids.mapped('name')) if has_field('resource.resource', 'role_ids') and res.role_ids else '-',
                res.default_role_id.name if has_field('resource.resource', 'default_role_id') and res.default_role_id else '-',
            ))
            # Campos extra en resource.resource si existen (ej. workcenter_id o x_*)
            extra = [f for f in res._fields if f.startswith(('x_', 'mrp_', 'workcenter'))]
            if extra:
                dump(res, names=extra)

if has_model('planning.slot.template'):
    sub('Plantillas de turnos (planning.slot.template)')
    tpls = env['planning.slot.template'].search([], order='id')
    print('Total plantillas: %s' % len(tpls))
    for t in tpls[:30]:
        dump(t, prefixes=[''], max_len=200)
        print('  ---')

if has_model('planning.slot'):
    sub('Turnos de Planeación (planning.slot)')
    total_slots = env['planning.slot'].search_count([])
    print('Total planning.slot en la base: %s' % total_slots)
    # Priorizar slots de recursos materiales o ligados a ventas/hormigón
    mat_slots = env['planning.slot'].search([('resource_type', '=', 'material')], order='id desc', limit=20) if has_field('planning.slot', 'resource_type') else env['planning.slot']
    if mat_slots:
        print('\n  >> Últimos %s slots con resource_type=material:' % len(mat_slots))
        for s in mat_slots:
            dump(s, names=['id', 'name', 'resource_id', 'role_id', 'start_datetime', 'end_datetime', 'allocated_hours', 'allocated_percentage', 'state', 'sale_line_id', 'company_id'], max_len=200)
            x_cols = [f for f in s._fields if f.startswith(('x_', 'mrp_', 'workcenter', 'production'))]
            if x_cols:
                dump(s, names=x_cols)
            print('  ---')

    recent_slots = env['planning.slot'].search([], order='id desc', limit=15)
    print('\n  >> Últimos %s planning.slot generales:' % len(recent_slots))
    for s in recent_slots:
        print('  [id=%s] res=%-22s | role=%-18s | %s -> %s | hrs=%.3f | pct=%s | state=%s | sale_line=%s' % (
            s.id,
            s.resource_id.name if val(s, 'resource_id') else '(open)',
            s.role_id.name if val(s, 'role_id') else '-',
            val(s, 'start_datetime'),
            val(s, 'end_datetime'),
            val(s, 'allocated_hours') or 0.0,
            val(s, 'allocated_percentage'),
            val(s, 'state'),
            s.sale_line_id.display_name if has_field('planning.slot', 'sale_line_id') and s.sale_line_id else '-',
        ))
else:
    print('\n  (planning.slot no instalado - la palabra "Planeación" puede referirse a Manufactura -> Planeación / mrp_workorder)')

if has_field('product.template', 'planning_enabled'):
    sub('Productos con planning_enabled=True')
    p_plan = env['product.template'].with_context(active_test=False).search([('planning_enabled', '=', True)])
    print('Total productos con planning_enabled=True: %s' % len(p_plan))
    for p in p_plan[:30]:
        print('  [tmpl id=%s] %-35s | uom=%s | role=%s | service_tracking=%s' % (
            p.id,
            p.display_name,
            p.uom_id.name if p.uom_id else '-',
            p.planning_role_id.name if has_field('product.template', 'planning_role_id') and p.planning_role_id else '-',
            val(p, 'service_tracking'),
        ))
