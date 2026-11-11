#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/KP-12
mkdir -p ~/tmp/KP-12/scripts && cd ~/tmp/KP-12
rm -f ~/tmp/KP-12/scripts/[0-9]*.py
cat > ~/tmp/KP-12/run_all.sh <<'__EOF_AUDIT__'
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
cat > ~/tmp/KP-12/scripts/_lib.py <<'__EOF_AUDIT__'
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
# Agregar acá los parámetros propios de la tarea (ids, nombres de documentos, etc.)


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


def has_field(model, fname):
    return fname in env[model]._fields


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
cat > ~/tmp/KP-12/scripts/01_cargar_embalajes_core_19.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
import gzip
import base64
import json
import os

h('01 - CARGA DE EMBALAJES EN CORE ODOO 19 (uom_ids / uom.uom)')

# Configuración de Dry Run
env_dry_run = os.environ.get('DRY_RUN', '1').lower()
DRY_RUN = env_dry_run not in ('0', 'false', 'no')

mode_str = 'DRY-RUN (Simulación sin persistir)' if DRY_RUN else 'PRODUCCIÓN (PERSISTENTE / COMMIT)'
sub('Modo de Ejecución: %s' % mode_str)

# Payload comprimido con el mapeo {default_code: [cantidades_embalaje]} (2.903 productos)
PAYLOAD_B64 = '''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'''

try:
    raw_json = gzip.decompress(base64.b64decode(PAYLOAD_B64)).decode('utf-8')
    data = json.loads(raw_json)
    print('[*] Payload desempacado correctamente: %s productos con embalajes.' % len(data))
except Exception as e:
    print('[!] Error desempacando payload: %s' % e)
    data = {}

if not data:
    print('ERROR: No hay datos para procesar.')
else:
    # 1. Identificar la Unidad Base de Medida
    sub('1. Identificación de Unidad Base de Medida (Reference Unit)')
    base_uom = env.ref('uom.product_uom_unit', raise_if_not_found=False)
    if not base_uom:
        base_uom = env['uom.uom'].search([('name', 'in', ['Units', 'Unidades', 'Unit(s)'])], limit=1)
    if not base_uom:
        base_uom = env['uom.uom'].search([('relative_uom_id', '=', False), ('active', '=', True)], limit=1)

    print('[*] Unidad de referencia base: [%s] %s' % (base_uom.id, base_uom.name))

    # 2. Gestionar las Unidades de Embalaje en uom.uom (Core Odoo 19)
    sub('2. Verificación / Creación de Presentaciones en uom.uom')
    all_target_qtys = set()
    for qtys in data.values():
        all_target_qtys.update(qtys)
    sorted_qtys = sorted(list(all_target_qtys))
    print('[*] Total tamaños distintos de presentación a gestionar: %s' % len(sorted_qtys))

    uom_by_qty = {}
    uom_creadas = 0
    uom_existentes = 0

    for q in sorted_qtys:
        fq = float(q)
        existing_uom = env['uom.uom'].search([
            ('relative_uom_id', '=', base_uom.id),
            ('relative_factor', '=', fq)
        ], limit=1)
        if not existing_uom:
            existing_uom = env['uom.uom'].search([
                ('name', 'in', ['Bulto x %s' % q, 'Caja x %s' % q, 'Pack of %s' % q])
            ], limit=1)
        if existing_uom:
            uom_by_qty[q] = existing_uom
            uom_existentes += 1
        else:
            vals = {
                'name': 'Bulto x %s' % q,
                'relative_uom_id': base_uom.id,
                'relative_factor': fq,
                'rounding': 0.001,
                'active': True,
            }
            new_uom = env['uom.uom'].create(vals)
            uom_by_qty[q] = new_uom
            uom_creadas += 1

    print('[*] Presentaciones uom.uom reutilizadas: %s' % uom_existentes)
    print('[*] Presentaciones uom.uom creadas:      %s' % uom_creadas)

    # 3. Mapear y Actualizar product.template.uom_ids (Campo Embalajes)
    sub('3. Asignación de Embalajes (uom_ids) a Productos')
    codes = list(data.keys())
    tmpls = env['product.template'].search([('default_code', 'in', codes)])
    tmpl_by_code = {t.default_code: t for t in tmpls}

    missing_codes = [c for c in codes if c not in tmpl_by_code]
    if missing_codes:
        prods = env['product.product'].search([('default_code', 'in', missing_codes)])
        for p in prods:
            if p.product_tmpl_id:
                tmpl_by_code[p.default_code] = p.product_tmpl_id

    print('[*] Productos encontrados en Odoo: %s de %s' % (len(tmpl_by_code), len(codes)))

    stats = {
        'total_productos_planilla': len(codes),
        'productos_encontrados': len(tmpl_by_code),
        'productos_no_encontrados': 0,
        'productos_actualizados': 0,
        'productos_ya_con_embalaje': 0,
        'relaciones_uom_agregadas': 0,
        'errores': 0
    }
    no_encontrados = []

    for code, qtys in data.items():
        tmpl = tmpl_by_code.get(code)
        if not tmpl:
            stats['productos_no_encontrados'] += 1
            if len(no_encontrados) < 20:
                no_encontrados.append(code)
            continue
        target_uom_ids = [uom_by_qty[q].id for q in qtys if q in uom_by_qty]
        current_uom_ids = tmpl.uom_ids.ids
        to_add = [uid for uid in target_uom_ids if uid not in current_uom_ids]
        if to_add:
            try:
                tmpl.write({'uom_ids': [(4, uid) for uid in to_add]})
                stats['productos_actualizados'] += 1
                stats['relaciones_uom_agregadas'] += len(to_add)
            except Exception as e:
                stats['errores'] += 1
                print('[!] Error actualizando [%s] %s: %s' % (code, tmpl.name, e))
        else:
            stats['productos_ya_con_embalaje'] += 1

    # 4. Resumen Estadístico
    sub('4. Resumen de Resultados')
    for k, v in stats.items():
        print('  %-32s: %s' % (k.replace('_', ' ').capitalize(), v))

    if no_encontrados:
        print('\nPrimeros códigos no encontrados en Odoo (de los 2.903):\n  %s' % ', '.join(no_encontrados))

    # Cierre transaccional
    if DRY_RUN:
        env.cr.rollback()
        print('\n' + '>' * 12 + ' [DRY-RUN] Se ejecutó ROLLBACK. Base de datos 100%% intacta. ' + '<' * 12)
    else:
        env.cr.commit()
        print('\n' + '>' * 12 + ' [PRODUCCIÓN] Se ejecutó COMMIT. Embalajes guardados en Odoo core con éxito! ' + '<' * 12)
__EOF_AUDIT__
cat > ~/tmp/KP-12/scripts/02_actualizar_uom_proveedor.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
import gzip
import base64
import json
import os

h('02 - ACTUALIZAR UNIDAD DE MEDIDA DE COMPRA EN PROVEEDORES (product.supplierinfo)')

# -------------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------------
env_dry_run = os.environ.get('DRY_RUN', '1').lower()
DRY_RUN = env_dry_run not in ('0', 'false', 'no')

env_up_price = os.environ.get('UPDATE_PRICE', '0').lower()
ACTUALIZAR_PRECIO = env_up_price in ('1', 'true', 'si', 'yes')

mode_str = 'DRY-RUN (Simulación sin persistir)' if DRY_RUN else 'PRODUCCIÓN (PERSISTENTE / COMMIT)'
sub('Modo de Ejecución: %s' % mode_str)
sub('Ajuste de Precio a Bulto Completo: %s' % ('ACTIVADO' if ACTUALIZAR_PRECIO else 'DESACTIVADO (Mantiene precio original)'))

# -------------------------------------------------------------------------
# 0. INSPECCIÓN DE CAMPOS DE product.supplierinfo EN ODOO 19
# -------------------------------------------------------------------------
sub('0. Inspección de Campos en product.supplierinfo')
SupplierInfo = env['product.supplierinfo']
uom_field_name = None

for fname, f in sorted(SupplierInfo._fields.items()):
    comodel = getattr(f, 'comodel_name', '')
    fstring = f.string or ''
    is_uom_cand = comodel == 'uom.uom' or 'uom' in fname.lower() or 'unidad' in fstring.lower() or 'unit' in fstring.lower()
    if is_uom_cand:
        print('  -> Campo candidato: %-25s | Tipo: %-10s | Etiqueta: %r | Comodel: %s' % (fname, f.type, fstring, comodel))
        if comodel == 'uom.uom' and not uom_field_name:
            uom_field_name = fname

# Dump de un registro de prueba (producto 37303)
test_tmpl = env['product.template'].search([('default_code', '=', '37303')], limit=1)
if test_tmpl and test_tmpl.seller_ids:
    test_seller = test_tmpl.seller_ids[0]
    print('\n  Ejemplo producto [37303] - Registro seller actual:')
    for fname in sorted(test_seller._fields):
        val = getattr(test_seller, fname, None)
        f = test_seller._fields[fname]
        if f.type in ('many2one', 'char', 'float', 'integer', 'selection'):
            print('    %-30s = %r (%s)' % (fname, val.display_name if f.type == 'many2one' and val else val, f.type))

if not uom_field_name:
    print('\n[!] AVISO: No se detectó un campo Many2one hacia uom.uom en product.supplierinfo.')
    print('    Campos disponibles en product.supplierinfo: %s' % list(SupplierInfo._fields.keys()))

# Payload con 961 productos donde uni_compra > 1
PAYLOAD_B64 = '''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'''

try:
    raw_json = gzip.decompress(base64.b64decode(PAYLOAD_B64)).decode('utf-8')
    data = json.loads(raw_json)
    print('\n[*] Payload desempacado correctamente: %s productos con uni_compra > 1.' % len(data))
except Exception as e:
    print('[!] Error desempacando payload: %s' % e)
    data = {}

if not data or not uom_field_name:
    print('Deteniendo ejecución hasta confirmar el campo de unidad en product.supplierinfo.')
else:
    print('[*] Campo de Unidad de Medida detectado para product.supplierinfo: %r' % uom_field_name)

    # 1. Identificar la Unidad Base de Medida
    sub('1. Identificación de Unidad Base')
    base_uom = env.ref('uom.product_uom_unit', raise_if_not_found=False)
    if not base_uom:
        base_uom = env['uom.uom'].search([('name', 'in', ['Units', 'Unidades', 'Unit(s)'])], limit=1)
    if not base_uom:
        base_uom = env['uom.uom'].search([('relative_uom_id', '=', False), ('active', '=', True)], limit=1)
    print('[*] Unidad base de referencia: [%s] %s' % (base_uom.id, base_uom.name))

    # 2. Cachear / Buscar las UdMs de compra en uom.uom
    sub('2. Verificación de Unidades de Compra en uom.uom')
    distinct_ucs = sorted(list(set(item['uc'] for item in data.values())))
    uom_by_uc = {}
    for uc in distinct_ucs:
        fuc = float(uc)
        uom_rec = env['uom.uom'].search([
            ('relative_uom_id', '=', base_uom.id),
            ('relative_factor', '=', fuc)
        ], limit=1)
        if not uom_rec:
            uom_rec = env['uom.uom'].search([
                ('name', 'in', ['Bulto x %s' % uc, 'Caja x %s' % uc, 'Pack of %s' % uc])
            ], limit=1)
        if not uom_rec:
            uom_rec = env['uom.uom'].create({
                'name': 'Bulto x %s' % uc,
                'relative_uom_id': base_uom.id,
                'relative_factor': fuc,
                'rounding': 0.001,
                'active': True,
            })
        uom_by_uc[uc] = uom_rec
    print('[*] %s unidades de compra listas en memoria.' % len(uom_by_uc))

    # 3. Buscar productos en Odoo y actualizar su product.supplierinfo
    sub('3. Actualización de %s en Líneas de Proveedor' % uom_field_name)
    codes = list(data.keys())
    tmpls = env['product.template'].search([('default_code', 'in', codes)])
    tmpl_by_code = {t.default_code: t for t in tmpls}

    stats = {
        'total_productos_en_planilla': len(codes),
        'productos_encontrados': len(tmpl_by_code),
        'productos_no_encontrados': 0,
        'productos_sin_proveedor': 0,
        'lineas_proveedor_actualizadas': 0,
        'lineas_proveedor_ya_correctas': 0,
        'precios_actualizados_a_bulto': 0,
        'errores': 0
    }
    sin_proveedor = []
    no_encontrados = []

    for code, info in data.items():
        tmpl = tmpl_by_code.get(code)
        if not tmpl:
            stats['productos_no_encontrados'] += 1
            if len(no_encontrados) < 15:
                no_encontrados.append(code)
            continue

        uc = info['uc']
        costo_unitario = info.get('costo', 0.0)
        target_uom = uom_by_uc.get(uc)
        if not target_uom:
            stats['errores'] += 1
            continue

        sellers = tmpl.seller_ids
        if not sellers:
            stats['productos_sin_proveedor'] += 1
            if len(sin_proveedor) < 15:
                sin_proveedor.append(code)
            continue

        for seller in sellers:
            vals_to_write = {}
            current_uom = getattr(seller, uom_field_name, None)
            if current_uom != target_uom:
                vals_to_write[uom_field_name] = target_uom.id

            if ACTUALIZAR_PRECIO and costo_unitario > 0:
                precio_bulto = round(costo_unitario * uc, 3)
                if abs(seller.price - precio_bulto) > 0.01:
                    vals_to_write['price'] = precio_bulto
                    stats['precios_actualizados_a_bulto'] += 1

            if vals_to_write:
                try:
                    seller.write(vals_to_write)
                    stats['lineas_proveedor_actualizadas'] += 1
                except Exception as e:
                    stats['errores'] += 1
                    print('[!] Error actualizando seller en [%s] %s: %s' % (code, tmpl.name, e))
            else:
                stats['lineas_proveedor_ya_correctas'] += 1

        # Asegurar también que target_uom esté en tmpl.uom_ids (Embalajes del producto)
        if target_uom.id not in tmpl.uom_ids.ids:
            tmpl.write({'uom_ids': [(4, target_uom.id)]})

    # 4. Resumen Estadístico
    sub('4. Resumen de Resultados')
    for k, v in stats.items():
        print('  %-35s: %s' % (k.replace('_', ' ').capitalize(), v))

    if sin_proveedor:
        print('\nPrimeros productos sin línea de proveedor en Odoo:\n  %s' % ', '.join(sin_proveedor))
    if no_encontrados:
        print('\nPrimeros productos no encontrados en Odoo:\n  %s' % ', '.join(no_encontrados))

    # Cierre transaccional
    if DRY_RUN:
        env.cr.rollback()
        print('\n' + '>' * 12 + ' [DRY-RUN] Se ejecutó ROLLBACK. Base de datos 100%% intacta. ' + '<' * 12)
    else:
        env.cr.commit()
        print('\n' + '>' * 12 + ' [PRODUCCIÓN] Se ejecutó COMMIT. Unidades de compra guardadas con éxito! ' + '<' * 12)
__EOF_AUDIT__
chmod +x ~/tmp/KP-12/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/KP-12:'; ls -R ~/tmp/KP-12 | head -50
