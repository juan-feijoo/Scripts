#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/bs28
mkdir -p ~/tmp/bs28/scripts && cd ~/tmp/bs28
cat > ~/tmp/bs28/run_all.sh <<'__EOF_AUDIT__'
#!/bin/bash
# Ejecuta todos los scripts scripts/[0-9]*.py con odoo-bin shell y genera un zip con los .txt resultantes.
# Uso:  bash ~/tmp/<tarea>/run_all.sh                 (usa $PGDATABASE o el odoo.conf del build)
#       DB=nombre_base bash ~/tmp/<tarea>/run_all.sh
#       LOG_PATTERN='afip|wsfe' bash ~/tmp/<tarea>/run_all.sh   (filtra ~/logs/odoo.log* con ese regex)
set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
TASK="$(basename "$BASE")"
TS="$(date +%Y%m%d_%H%M%S)"
NAME="resultados_${TS}"
OUT="$BASE/$NAME"
mkdir -p "$OUT"

DB="${DB:-${PGDATABASE:-}}"
DB_ARG=""
if [ -n "$DB" ]; then DB_ARG="-d $DB"; fi

# 00 - Entorno
{
  echo "Fecha: $(date)"
  echo "Host: $(hostname)"
  echo "DB: ${DB:-<odoo.conf>}"
  echo; echo "### odoo-bin --version"; odoo-bin --version 2>&1
  for repo in "$HOME/src/odoo" "$HOME/src/enterprise" "$HOME/src/user"; do
    [ -d "$repo/.git" ] && { echo; echo "### git $repo"; git -C "$repo" log -5 --oneline 2>&1; }
  done
  echo; echo "### src/user"; ls -la "$HOME/src/user" 2>&1
} > "$OUT/00_entorno.txt" 2>&1

# NN - Scripts Python dentro de odoo-bin shell
for f in "$BASE"/scripts/[0-9]*.py; do
  [ -f "$f" ] || continue
  n="$(basename "$f" .py)"
  echo ">> Ejecutando $n ..."
  echo "exec(open('$BASE/scripts/_lib.py').read()); exec(open('$f').read())" \
    | odoo-bin shell $DB_ARG --no-http --log-level=warn > "$OUT/$n.txt" 2>&1
done

# 99 - Logs filtrados (opcional)
if [ -n "${LOG_PATTERN:-}" ]; then
  echo ">> Filtrando logs con /$LOG_PATTERN/ ..."
  {
    echo "### ls $HOME/logs"; ls -la "$HOME/logs" 2>&1
    for lf in "$HOME"/logs/odoo.log*; do
      [ -f "$lf" ] || continue
      echo; echo "########## $lf"
      case "$lf" in
        *.gz) zgrep -iE "$LOG_PATTERN" "$lf" | tail -n 3000 ;;
        *)    grep  -iE "$LOG_PATTERN" "$lf" | tail -n 3000 ;;
      esac
    done
  } > "$OUT/99_logs_odoo.txt" 2>&1
fi

# Zip con python (no depende del binario zip)
python3 -c "import shutil,sys; print(shutil.make_archive(sys.argv[1], 'zip', sys.argv[2], sys.argv[3]))" \
  "$BASE/${TASK}_${TS}" "$BASE" "$NAME"

echo
echo "Listo. Archivos:"; ls -la "$OUT"
echo "Con errores:"; grep -l "Traceback\|!! ERROR" "$OUT"/*.txt 2>/dev/null || echo "  ninguno"
echo "ZIP: $BASE/${TASK}_${TS}.zip  (descargar desde pestaña Editor)"
__EOF_AUDIT__
cat > ~/tmp/bs28/scripts/_lib.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# Helpers comunes. Se ejecuta dentro de `odoo-bin shell` (la variable `env` ya existe, superusuario).
import base64
import html
import inspect
import os
import re
import traceback

# ---------------------------------------------------------------------------
# PARÁMETROS DE LA TAREA (editar)
# ---------------------------------------------------------------------------
COMPANY_NAME = os.environ.get('COMPANY_NAME', '')   # ilike sobre res.company.name
WORKCENTER_KW = os.environ.get('WORKCENTER_KW', '') # opcional: filtro por nombre de centro de trabajo
LIMIT_RECS = int(os.environ.get('LIMIT_RECS', '25'))
# Parámetros teóricos del ticket BS-28 (solo referencia para comparativa en memoria)
BASE_PREP_MIN = float(os.environ.get('BASE_PREP_MIN', '5.0'))
RATE_MIN_PER_M3 = float(os.environ.get('RATE_MIN_PER_M3', '2.8'))


def h(title):
    print('\n' + '=' * 100)
    print(title)
    print('=' * 100)


def sub(title):
    print('\n--- %s %s' % (title, '-' * max(0, 94 - len(title))))


def fmt(rec, fname, max_len=None):
    field = rec._fields[fname]
    try:
        val = rec[fname]
    except Exception as e:
        return '<error leyendo: %s>' % e
    if field.type == 'binary':
        return '<binario vacío>' if not val else '<binario %s bytes>' % len(val)
    if field.type == 'many2one':
        return '%s (id=%s)' % (val.display_name, val.id) if val else False
    if field.type in ('one2many', 'many2many'):
        if not val:
            return '[]'
        items = ', '.join('%s(id=%s)' % (r.display_name, r.id) for r in val[:20])
        return '%s registros: %s%s' % (len(val), items, ' ...' if len(val) > 20 else '')
    if max_len and isinstance(val, str) and len(val) > max_len:
        return val[:max_len] + '... <truncado, %s chars>' % len(val)
    return val


def dump(rec, prefixes=None, names=None, max_len=300, full=None):
    """Imprime campos de `rec` cuyo nombre está en `names` o empieza con algún `prefixes`
    (prefixes=[''] = todos). Campos en `full` sin truncar. Ignora nombres inexistentes."""
    full = full or []
    for fname in sorted(rec._fields):
        if (names and fname in names) or (prefixes and fname.startswith(tuple(prefixes))):
            print('  %-45s %s' % (fname, fmt(rec, fname, None if fname in full else max_len)))


def strip_html(s):
    return html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).strip()


def get_company(name=None):
    name = name or COMPANY_NAME
    companies = env['res.company'].search([('name', 'ilike', name)]) if name else env.company
    if not companies:
        print('!! No se encontró compañía ilike %r' % name)
        return env['res.company']
    if len(companies) > 1:
        print('!! Varias compañías coinciden, uso la primera: %s' % companies.mapped('name'))
    return companies[0]


def safe(fn, *args, **kwargs):
    """Ejecuta fn y, si falla, imprime el traceback y devuelve None (el script sigue)."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        print('  !! ERROR:')
        print('  ' + traceback.format_exc().replace('\n', '\n  '))
        return None


def has_model(model):
    return model in env


def has_field(model, fname):
    return model in env and fname in env[model]._fields


def val(rec, fname, default=None):
    return rec[fname] if fname in rec._fields else default


def chatter(record):
    """Mensajes + tracking de un registro (quién cambió qué y cuándo)."""
    msgs = env['mail.message'].search([('model', '=', record._name), ('res_id', '=', record.id)], order='date, id')
    for msg in msgs:
        print('  [%s] id=%s tipo=%s autor=%s subtype=%s' % (msg.date, msg.id, msg.message_type,
                                                            msg.author_id.display_name, msg.subtype_id.name))
        body = strip_html(msg.body)
        if body:
            print('      cuerpo: %s' % body[:2000])
        for t in msg.tracking_value_ids:
            fname = t.field_id.name if 'field_id' in t._fields else '?'
            old = t.old_value_char or t.old_value_integer or t.old_value_float or t.old_value_datetime
            new = t.new_value_char or t.new_value_integer or t.new_value_float or t.new_value_datetime
            print('      tracking: %s: %r -> %r' % (fname, old, new))


def method_sources(model, methods, only_custom=True):
    """Para cada método, lista qué módulos lo definen (MRO) e imprime la fuente de los no core."""
    cls = type(env[model])
    for meth in methods:
        definers = [k for k in cls.__mro__ if meth in k.__dict__]
        if not definers:
            continue
        sub('%s.%s' % (model, meth))
        for k in definers:
            fn = k.__dict__[meth]
            try:
                path = (inspect.getsourcefile(fn) or '?').replace('\\', '/')
            except Exception:
                path = '?'
            print('  definido en: %s  (%s)' % (k.__module__, path))
            custom = '/src/user/' in path
            if not only_custom or custom:
                try:
                    print('    ' + inspect.getsource(fn).replace('\n', '\n    '))
                except Exception as e:
                    print('    <sin fuente: %s>' % e)
__EOF_AUDIT__
cat > ~/tmp/bs28/scripts/01_entorno_modulos_custom.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
cat > ~/tmp/bs28/scripts/02_centros_de_trabajo.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
cat > ~/tmp/bs28/scripts/03_productos_boms_operaciones.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
cat > ~/tmp/bs28/scripts/04_planeacion_y_recursos.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
cat > ~/tmp/bs28/scripts/05_ordenes_fabricacion_y_tiempos.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
cat > ~/tmp/bs28/scripts/06_codigo_odoo_formulas.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
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
