# -*- coding: utf-8 -*-
# 06 - Código fuente instalado en este build (MRO) y módulos en /src/user
import os

h('06 - CÓDIGO FUENTE INSTALADO (FÓRMULAS REALES DE DURACIÓN Y PLANEACIÓN)')

targets = [
    ('mrp.workcenter', ['_get_capacity', '_get_first_available_slot']),
    ('mrp.routing.workcenter', ['_compute_time_cycle', '_get_duration_expected']),
    ('mrp.workorder', ['_get_duration_expected', '_compute_duration_expected', '_plan_workorder', '_get_dates_planned']),
    ('mrp.production', ['_plan_workorders', 'button_plan']),
    ('planning.slot', ['_compute_allocated_hours', '_compute_end_datetime', '_get_duration']),
    ('sale.order.line', ['_planning_slot_values', '_timesheet_service_generation', '_action_launch_stock_rule']),
]

for model, methods in targets:
    if not has_model(model):
        print('\n[Modelo %s no existe en esta base]' % model)
        continue
    method_sources(model, methods, only_custom=False)

sub('Archivos Python en ~/src/user (custom / terceros)')
user_src = os.path.expanduser('~/src/user')
if os.path.isdir(user_src):
    py_files = []
    for root, dirs, files in os.walk(user_src):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fn in files:
            if fn.endswith('.py') or fn == '__manifest__.py':
                rel = os.path.relpath(os.path.join(root, fn), user_src)
                py_files.append(rel)
    print('Total archivos .py / __manifest__.py en ~/src/user: %s' % len(py_files))
    for p in sorted(py_files)[:120]:
        print('  ' + p)
    if len(py_files) > 120:
        print('  ... (%s más)' % (len(py_files) - 120))
else:
    print('  No existe %s' % user_src)
