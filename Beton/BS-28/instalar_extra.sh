#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/bs28
mkdir -p ~/tmp/bs28/scripts && cd ~/tmp/bs28
cat > ~/tmp/bs28/scripts/07_aplicar_opcion1.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 07 - Aplicar Opción 1 (Estándar Odoo 19): time_start=5.0 min + time_cycle_manual=2.8 min/m³
# Por defecto corre en DRY_RUN=True (simulación completa con rollback al final).
# Para persistir en la base: DRY_RUN=0 odoo-bin shell ...
import os

DRY_RUN = os.environ.get('DRY_RUN', '1') != '0'
RECALC_OPEN_WOS = os.environ.get('RECALC_OPEN_WOS', '1') != '0'
REPLAN_OPEN_MOS = os.environ.get('REPLAN_OPEN_MOS', '1') != '0'
TARGET_TIME_START = float(os.environ.get('BASE_PREP_MIN', str(BASE_PREP_MIN)))
TARGET_TIME_CYCLE = float(os.environ.get('RATE_MIN_PER_M3', str(RATE_MIN_PER_M3)))


def fmt_mmss(minutes):
    total_sec = int(round((minutes or 0.0) * 60))
    return '%02d:%02d' % (total_sec // 60, total_sec % 60)


h('07 - APLICAR OPCIÓN 1 BS-28 | DRY_RUN=%s' % DRY_RUN)
print('Parámetros objetivo:')
print('  - Tiempo base preparación (time_start): %.2f min (%s en UI)' % (TARGET_TIME_START, fmt_mmss(TARGET_TIME_START)))
print('  - Tasa por m³ (time_cycle_manual):      %.2f min (%s en UI)' % (TARGET_TIME_CYCLE, fmt_mmss(TARGET_TIME_CYCLE)))
print('  - Recalcular WOs abiertas:              %s' % RECALC_OPEN_WOS)
print('  - Replanificar MOs abiertas:            %s' % REPLAN_OPEN_MOS)

# 1. Localizar Centro de Trabajo
WC = env['mrp.workcenter']
wc = WC.search([('code', '=', 'PLANTA-01')], limit=1) or WC.search([('name', 'ilike', 'Planta de hormig')], limit=1)
if not wc:
    raise RuntimeError('No se encontró el centro de trabajo Planta de hormigón (PLANTA-01).')

sub('1. Centro de trabajo: %s (id=%s | code=%s)' % (wc.display_name, wc.id, wc.code))
print('  ANTES -> time_start=%.2f (%s) | time_stop=%.2f | time_efficiency=%.2f%% | tz=%s | cal=%s' % (
    wc.time_start, fmt_mmss(wc.time_start), wc.time_stop, wc.time_efficiency, wc.tz,
    wc.resource_calendar_id.name if wc.resource_calendar_id else '-'
))

wc.write({'time_start': TARGET_TIME_START})
print('  DESPUÉS -> time_start=%.2f (%s) | time_stop=%.2f' % (
    wc.time_start, fmt_mmss(wc.time_start), wc.time_stop
))

# 2. Localizar y actualizar operaciones de BoMs en Planta de hormigón
sub('2. Operaciones de BoM vinculadas a %s' % wc.display_name)
all_ops = env['mrp.routing.workcenter'].search([('workcenter_id', '=', wc.id)], order='id')
target_ops = env['mrp.routing.workcenter']
for op in all_ops:
    bom = op.bom_id
    uom_name = bom.product_uom_id.name if (bom and bom.product_uom_id) else ''
    if bom and bom.active and abs((bom.product_qty or 0.0) - 1.0) < 1e-6 and ('m³' in uom_name.lower() or 'm3' in uom_name.lower()):
        target_ops |= op
    else:
        print('  [OMITIDA op id=%s] bom=%s | active=%s | qty=%s %s' % (
            op.id, bom.display_name if bom else '-', bom.active if bom else '-',
            bom.product_qty if bom else '-', uom_name
        ))

print('Operaciones a actualizar: %s' % len(target_ops))
for op in target_ops:
    before_cycle = op.time_cycle_manual
    before_total = val(op, 'time_total') or 0.0
    op.write({
        'time_mode': 'manual',
        'time_cycle_manual': TARGET_TIME_CYCLE,
    })
    after_total = val(op, 'time_total') or 0.0
    print('  [op id=%s] %-42s | manual: %.2f -> %.2f (%s) | time_total(1m³): %.2f -> %.2f (%s)' % (
        op.id,
        op.bom_id.display_name[:42],
        before_cycle,
        op.time_cycle_manual,
        fmt_mmss(op.time_cycle_manual),
        before_total,
        after_total,
        fmt_mmss(after_total),
    ))

# 3. Recalcular duration_expected y replanificar WOs abiertas
if RECALC_OPEN_WOS:
    sub('3. Órdenes de trabajo abiertas en %s (state not in done/cancel)' % wc.display_name)
    open_wos = env['mrp.workorder'].search([
        ('workcenter_id', '=', wc.id),
        ('state', 'not in', ('done', 'cancel')),
    ], order='id')
    print('Total WOs abiertas encontradas: %s' % len(open_wos))
    mos_to_replan = env['mrp.production']
    for wo in open_wos:
        mo = wo.production_id
        before_exp = wo.duration_expected
        before_start = mo.date_start
        before_end = mo.date_finished
        new_exp = wo._get_duration_expected()
        wo.write({'duration_expected': new_exp})
        had_leave = bool(val(wo, 'leave_id'))
        if REPLAN_OPEN_MOS and (had_leave or val(mo, 'is_planned')):
            mos_to_replan |= mo
        print('  [WO id=%s | %s | state=%s] qty=%.2f m³ | exp: %.2f -> %.2f min (%s) | leave=%s' % (
            wo.id, mo.name, wo.state, wo.qty_production, before_exp, wo.duration_expected,
            fmt_mmss(wo.duration_expected), had_leave
        ))

    if REPLAN_OPEN_MOS and mos_to_replan:
        sub('3b. Replanificación de MOs abiertas (%s órdenes)' % len(mos_to_replan))
        for mo in mos_to_replan.sorted('id'):
            b_start, b_end = mo.date_start, mo.date_finished
            def _replan_one(m=mo):
                with env.cr.savepoint():
                    m._plan_workorders(replan=True)
            safe(_replan_one)
            print('  [%s | state=%s] %s -> %s  ==>  %s -> %s' % (
                mo.name, mo.state, b_start, b_end, mo.date_start, mo.date_finished
            ))

# 4. Commit solo si DRY_RUN=False (antes de las MOs de prueba en memoria)
if not DRY_RUN:
    env.cr.commit()
    sub('CAMBIOS CONFIRMADOS EN BASE DE DATOS (env.cr.commit)')
else:
    sub('MODO DRY_RUN: los cambios anteriores NO se confirmaron todavía')

# 5. Prueba de humo con MOs nuevas (1 m³ y 8 m³) -> SIEMPRE rollback al final
sub('4. Simulación con órdenes de fabricación nuevas (1.0 m³ y 8.0 m³) [siempre rollback]')
sample_op = target_ops[:1]
if sample_op:
    bom = sample_op.bom_id
    product = bom.product_id or bom.product_tmpl_id.product_variant_id
    for qty_test in (1.0, 2.5, 5.0, 8.0, 10.0):
        def _sim_mo(q=qty_test):
            with env.cr.savepoint():
                mo_test = env['mrp.production'].with_company(wc.company_id).create({
                    'product_id': product.id,
                    'product_qty': q,
                    'product_uom_id': bom.product_uom_id.id,
                    'bom_id': bom.id,
                })
                mo_test.action_confirm()
                mo_test.button_plan()
                wo_t = mo_test.workorder_ids[:1]
                print('  Simulación %.1f m³ (%s): dur_esperada = %.2f min (%s) | planificada: %s -> %s' % (
                    q, product.display_name, wo_t.duration_expected, fmt_mmss(wo_t.duration_expected),
                    mo_test.date_start, mo_test.date_finished
                ))
        safe(_sim_mo)

env.cr.rollback()
print('\nFin script 07 (%s).' % ('DRY_RUN: rollback total ejecutado' if DRY_RUN else 'Configuración aplicada; MOs de simulación revertidas'))
__EOF_AUDIT__
chmod +x ~/tmp/bs28/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/bs28:'; ls -R ~/tmp/bs28 | head -50
