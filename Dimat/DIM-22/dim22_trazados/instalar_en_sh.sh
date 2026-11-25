#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/dim22_trazados
mkdir -p ~/tmp/dim22_trazados/scripts && cd ~/tmp/dim22_trazados
cat > ~/tmp/dim22_trazados/run_all.sh <<'__EOF_AUDIT__'
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
cat > ~/tmp/dim22_trazados/scripts/_lib.py <<'__EOF_AUDIT__'
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
TRACED_PREFIX = os.environ.get('TRACED_PREFIX', '/')  # prefijo actual en nombre de producto


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
    if model not in env:
        return
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
cat > ~/tmp/dim22_trazados/scripts/01_entorno_modulos_custom.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 01 - Entorno, módulos instalados/custom, automatizaciones, acciones de servidor y overrides (solo lectura)
import odoo

h('01 - ENTORNO, MÓDULOS, AUTOMATIZACIONES Y OVERRIDES')

print('Base de datos : %s' % env.cr.dbname)
print('Versión Odoo  : %s' % odoo.release.version)

sub('Compañías (res.company)')
for c in env['res.company'].with_context(active_test=False).search([]):
    print('  id=%s | active=%s | name=%r | vat=%r | country=%s | currency=%s | parent=%s' % (
        c.id, c.active, c.name, c.vat, c.country_id.code if c.country_id else False,
        c.currency_id.name if c.currency_id else False, c.parent_id.name if c.parent_id else False,
    ))

sub('Estado de módulos clave estándar/localización')
key_mods = [
    'sale', 'sale_management', 'purchase', 'stock', 'sale_stock', 'purchase_stock',
    'account', 'account_accountant', 'l10n_ar', 'l10n_ar_afipws_fe', 'l10n_ar_edi',
    'web_studio', 'documents', 'website_sale', 'portal', 'product_expiry',
    'quality_control', 'mrp', 'base_automation', 'stock_barcode',
]
mods_map = {m.name: m for m in env['ir.module.module'].search([('name', 'in', key_mods)])}
for mname in key_mods:
    m = mods_map.get(mname)
    print('  %-25s %s' % (mname, '%s (ver=%s)' % (m.state, m.installed_version) if m else '<no encontrado>'))

sub('Módulos instalados NO Odoo S.A. (custom / terceros / OCA)')
custom_mods = env['ir.module.module'].search([
    ('state', '=', 'installed'),
    ('author', 'not ilike', 'Odoo S.A.'),
], order='name')
print('Total módulos no Odoo S.A. instalados: %s' % len(custom_mods))
for m in custom_mods:
    print('  %-40s | ver=%-14s | author=%r | %s' % (
        m.name, m.installed_version or '', m.author or '', m.shortdesc or '',
    ))

TARGET_MODELS = {
    'product.template', 'product.product', 'res.partner',
    'sale.order', 'sale.order.line',
    'purchase.order', 'purchase.order.line',
    'stock.picking', 'stock.move', 'stock.move.line',
    'account.move', 'account.move.line',
}
KEYWORDS = ('traz', 'hab', 'sedro', 'renpre', 'precur', 'studio', 'warn', 'block', 'barra', 'cert', 'anmat')

if 'base.automation' in env:
    sub('Automatizaciones (base.automation) - todas (activas e inactivas)')
    autos = env['base.automation'].with_context(active_test=False).search([], order='model_id, id')
    print('Total base.automation: %s' % len(autos))
    for a in autos:
        mname = a.model_id.model if a.model_id else ''
        relevant = (mname in TARGET_MODELS) or any(k in (a.name or '').lower() for k in KEYWORDS)
        print('  id=%s | active=%s | model=%s | trigger=%s | name=%r%s' % (
            a.id, a.active, mname, a.trigger, a.name, ' [RELEVANTE]' if relevant else '',
        ))
        if relevant:
            dump(a, names=[
                'filter_domain', 'filter_pre_domain', 'on_change_field_ids',
                'trigger_field_ids', 'action_server_ids',
            ])
            if has_field('base.automation', 'action_server_ids'):
                for srv in a.action_server_ids:
                    print('    -> Server Action id=%s state=%s name=%r' % (srv.id, srv.state, srv.name))
                    if srv.state == 'code' and srv.code:
                        print('       CODE:\n' + '\n'.join('       ' + ln for ln in srv.code.splitlines()))
else:
    sub('Automatizaciones (base.automation)')
    print('  Modelo base.automation no instalado.')

sub('Acciones de servidor Python (ir.actions.server state=code) en modelos relevantes o por keyword')
srv_actions = env['ir.actions.server'].with_context(active_test=False).search([('state', '=', 'code')], order='model_id, id')
print('Total ir.actions.server state=code: %s' % len(srv_actions))
for srv in srv_actions:
    mname = srv.model_id.model if srv.model_id else ''
    blob = ('%s %s %s' % (mname, srv.name or '', srv.code or '')).lower()
    if mname in TARGET_MODELS or any(k in blob for k in KEYWORDS):
        print('  id=%s | model=%s | name=%r | usage=%s' % (
            srv.id, mname, srv.name, fmt(srv, 'usage') if has_field('ir.actions.server', 'usage') else '-',
        ))
        if srv.code:
            print('    CODE:\n' + '\n'.join('    ' + ln for ln in srv.code.splitlines()))

sub('Crons (ir.cron) en modelos relevantes o por keyword')
crons = env['ir.cron'].with_context(active_test=False).search([], order='id')
for cr in crons:
    mname = cr.model_id.model if cr.model_id else ''
    blob = ('%s %s %s' % (mname, cr.name or '', cr.code or '')).lower()
    if mname in TARGET_MODELS or any(k in blob for k in KEYWORDS):
        print('  id=%s | active=%s | model=%s | name=%r' % (cr.id, cr.active, mname, cr.name))

sub('Overrides de código en /src/user/ (MRO)')
method_sources('sale.order', ['action_confirm', '_action_confirm', '_prepare_confirmation_values'], only_custom=True)
method_sources('sale.order.line', ['_onchange_product_id_warning', '_compute_name'], only_custom=True)
method_sources('purchase.order', ['button_confirm'], only_custom=True)
method_sources('purchase.order.line', ['_onchange_product_id_warning'], only_custom=True)
method_sources('stock.picking', ['button_validate'], only_custom=True)
method_sources('account.move', ['action_post', '_post'], only_custom=True)
method_sources('product.template', ['create', 'write'], only_custom=True)
method_sources('res.partner', ['create', 'write'], only_custom=True)
__EOF_AUDIT__
cat > ~/tmp/dim22_trazados/scripts/02_productos_barra_y_catalogos.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
cat > ~/tmp/dim22_trazados/scripts/03_clientes_habilitaciones_y_campos.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 03 - Clientes, campos de res.partner, etiquetas, advertencias, notas, adjuntos y Documents (solo lectura)
import re

h('03 - CLIENTES: CAMPOS, ETIQUETAS, ADVERTENCIAS, NOTAS Y DOCUMENTOS')

KEYWORDS = ('hab', 'traz', 'renpre', 'sedro', 'precur', 'cert', 'lic', 'perm', 'vto', 'venc', 'expir', 'anmat', 'disp', 'inscrip', 'reg')
KW_RE = re.compile(r'hab|traz|renpre|sedro|precur|cert|lic|perm|vto|venc|expir|anmat|disp|inscrip', re.I)

sub('Campos custom o relevantes en res.partner (ir.model.fields)')
partner_fields = env['ir.model.fields'].search([('model', '=', 'res.partner')], order='name')
for f in partner_fields:
    blob = ('%s %s %s' % (f.name, f.field_description or '', f.modules or '')).lower()
    is_custom = f.name.startswith('x_') or f.state == 'manual'
    is_non_core = bool(f.modules) and any(m.strip().startswith(('l10n_', 'custom', 'dimat', 'studio')) for m in f.modules.split(','))
    has_kw = any(k in blob for k in KEYWORDS)
    if is_custom or is_non_core or has_kw or f.name in ('category_id', 'industry_id', 'comment', 'ref', 'sale_warn', 'sale_warn_msg', 'purchase_warn', 'purchase_warn_msg'):
        print('  %-38s | %-12s | state=%-7s | mods=%-25s | label=%r' % (
            f.name, f.ttype, f.state, (f.modules or '')[:25], f.field_description,
        ))

RP = env['res.partner'].with_context(active_test=False)
print('\nTotal res.partner (activos e inactivos): %s (activos=%s)' % (
    RP.search_count([]), env['res.partner'].search_count([]),
))

sub('Etiquetas de contacto (res.partner.category)')
cats = env['res.partner.category'].with_context(active_test=False).search([], order='name')
print('Total res.partner.category: %s' % len(cats))
for cat in cats:
    cnt = RP.search_count([('category_id', 'in', [cat.id])])
    print('  id=%-4s | active=%-5s | partners=%-5s | parent=%r | name=%r' % (
        cat.id, cat.active, cnt, cat.parent_id.name if cat.parent_id else '', cat.name,
    ))

sub('Industrias / Rubros (res.partner.industry)')
if 'res.partner.industry' in env:
    inds = env['res.partner.industry'].with_context(active_test=False).search([], order='name')
    print('Total res.partner.industry: %s' % len(inds))
    for ind in inds:
        cnt = RP.search_count([('industry_id', '=', ind.id)])
        print('  id=%-4s | active=%-5s | partners=%-5s | name=%r (%r)' % (
            ind.id, ind.active, cnt, ind.name, ind.full_name,
        ))

sub('Partners con advertencia nativa (sale_warn / purchase_warn != no-message)')
for wf in ('sale_warn', 'purchase_warn'):
    if has_field('res.partner', wf):
        wrecs = RP.search([(wf, '!=', 'no-message'), (wf, '!=', False)])
        print('  %s configurados: %s' % (wf, len(wrecs)))
        for p in wrecs[:40]:
            msg_f = wf + '_msg'
            print('    id=%-6s | vat=%-13r | %-35r | %s=%s | msg=%r' % (
                p.id, p.vat or '', p.name, wf, p[wf], p[msg_f] if has_field('res.partner', msg_f) else '',
            ))

sub('Partners con texto en Notas internas (comment) o ref que coincida con keywords')
comment_matches = []
# Búsqueda acotada por SQL ilike para no traer toda la tabla si es grande
kw_domain = ['|'] * (len(KEYWORDS) - 1)
for k in KEYWORDS:
    kw_domain.append(('comment', 'ilike', k))
for p in RP.search([('comment', '!=', False)] + kw_domain, limit=100):
    txt = strip_html(p.comment)
    if KW_RE.search(txt):
        comment_matches.append((p, txt))
print('Partners con match en comment (hasta 100 revisados): %s' % len(comment_matches))
for p, txt in comment_matches[:40]:
    print('  id=%-6s | vat=%-13r | %-35r | comment=%r' % (p.id, p.vat or '', p.name, txt[:180]))

sub('Partners con campos x_* cargados (no vacíos)')
x_partner_fields = [f.name for f in partner_fields if f.name.startswith('x_') and f.ttype not in ('one2many',)]
if x_partner_fields:
    for fname in x_partner_fields:
        ftype = env['res.partner']._fields[fname].type
        dom = [(fname, '!=', False)]
        if ftype in ('char', 'text', 'html'):
            dom.append((fname, '!=', ''))
        cnt = RP.search_count(dom)
        print('  Campo %-35s (%s): %s partners con valor' % (fname, ftype, cnt))
        if cnt:
            for p in RP.search(dom, limit=15):
                print('    id=%-6s | %-35r | val=%s' % (p.id, p.name, fmt(p, fname, max_len=100)))
else:
    print('  No hay campos x_* en res.partner.')

sub('Adjuntos (ir.attachment) vinculados a res.partner')
Att = env['ir.attachment'].with_context(active_test=False)
total_att = Att.search_count([('res_model', '=', 'res.partner')])
print('Total adjuntos en res.partner: %s' % total_att)
att_kw_dom = ['|'] * (len(KEYWORDS) - 1) + [('name', 'ilike', k) for k in KEYWORDS]
kw_atts = Att.search([('res_model', '=', 'res.partner')] + att_kw_dom, order='id desc', limit=50)
print('Adjuntos en res.partner con nombre por keyword (hasta 50): %s' % len(kw_atts))
for a in kw_atts:
    p = RP.browse(a.res_id).exists()
    print('  att_id=%-6s | partner_id=%-6s (%r) | %s | name=%r' % (
        a.id, a.res_id, p.display_name if p else '?', a.create_date, a.name,
    ))

print('Muestra de los últimos 20 adjuntos generales en res.partner:')
for a in Att.search([('res_model', '=', 'res.partner')], order='id desc', limit=20):
    p = RP.browse(a.res_id).exists()
    print('  att_id=%-6s | partner_id=%-6s (%r) | %s | name=%r' % (
        a.id, a.res_id, p.display_name if p else '?', a.create_date, a.name,
    ))

if 'documents.document' in env:
    sub('Módulo Documents (documents.document)')
    Doc = env['documents.document'].with_context(active_test=False)
    print('Total documents.document: %s' % Doc.search_count([]))
    if has_field('documents.document', 'type'):
        folders = Doc.search([('type', '=', 'folder')], order='name')
        print('Carpetas (type=folder): %s' % len(folders))
        for fl in folders[:50]:
            print('  id=%-5s | parent=%r | name=%r' % (
                fl.id, fl.folder_id.name if has_field('documents.document', 'folder_id') and fl.folder_id else '', fl.name,
            ))
    if 'documents.tag' in env:
        dtags = env['documents.tag'].search([], order='name')
        print('Etiquetas Documents (documents.tag): %s' % len(dtags))
        for dt in dtags[:50]:
            print('  id=%-5s | name=%r' % (dt.id, dt.display_name))
    doc_kw_dom = ['|'] * (len(KEYWORDS) - 1) + [('name', 'ilike', k) for k in KEYWORDS]
    kw_docs = Doc.search(doc_kw_dom, order='id desc', limit=40)
    print('Documentos por keyword (hasta 40): %s' % len(kw_docs))
    for d in kw_docs:
        print('  id=%-6s | partner=%s | folder=%s | name=%r' % (
            d.id,
            fmt(d, 'partner_id') if has_field('documents.document', 'partner_id') else '-',
            fmt(d, 'folder_id') if has_field('documents.document', 'folder_id') else '-',
            d.name,
        ))
__EOF_AUDIT__
cat > ~/tmp/dim22_trazados/scripts/04_ventas_compras_y_uso_actual.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 04 - Análisis histórico de Ventas, Compras, Inventario y Facturas con productos "/" (solo lectura)
from collections import Counter

h('04 - HISTÓRICO DE VENTAS, COMPRAS, STOCK Y FACTURAS CON PRODUCTOS %r' % TRACED_PREFIX)

PT = env['product.template'].with_context(active_test=False)
traced_tmpls = PT.search([('name', '=like', TRACED_PREFIX + '%')])
leading_ws = PT.search([('name', 'ilike', TRACED_PREFIX)]).filtered(
    lambda p: (p.name or '').lstrip().startswith(TRACED_PREFIX) and p.id not in traced_tmpls.ids
)
traced_tmpls = traced_tmpls | leading_ws
traced_prods = env['product.product'].with_context(active_test=False).search([
    ('product_tmpl_id', 'in', traced_tmpls.ids),
])
print('Templates detectados: %s | Variantes product.product: %s' % (len(traced_tmpls), len(traced_prods)))

if not traced_prods:
    print('No se encontraron productos con prefijo %r. Fin del análisis.' % TRACED_PREFIX)
else:
    # ------------------------------------------------------------------ VENTAS
    if 'sale.order.line' in env:
        sub('Ventas (sale.order.line) con productos trazados')
        sols = env['sale.order.line'].search([('product_id', 'in', traced_prods.ids)])
        print('Total líneas sale.order.line: %s | Pedidos distintos: %s' % (len(sols), len(sols.mapped('order_id'))))
        state_cnt = Counter(sols.mapped('order_id.state'))
        print('Líneas por estado de pedido: %s' % dict(state_cnt))
        if sols:
            dates = [d for d in sols.mapped('order_id.date_order') if d]
            if dates:
                print('Rango date_order: %s .. %s' % (min(dates), max(dates)))

        # Analizar clientes compradores reales (confirmados o todos) para descubrir cómo marcan habilitación
        buyer_counts = Counter()
        confirmed_buyer_counts = Counter()
        for line in sols:
            cp = line.order_id.partner_id.commercial_partner_id
            if cp:
                buyer_counts[cp.id] += 1
                if line.order_id.state in ('sale', 'done'):
                    confirmed_buyer_counts[cp.id] += 1

        print('Clientes comerciales distintos (todos los presupuestos/pedidos): %s' % len(buyer_counts))
        print('Clientes comerciales distintos (pedidos confirmados): %s' % len(confirmed_buyer_counts))

        # Inspeccionar los top 50 clientes confirmados (o todos si <= 50)
        top_ids = [pid for pid, _ in (confirmed_buyer_counts or buyer_counts).most_common(50)]
        Att = env['ir.attachment'].with_context(active_test=False)
        Doc = env['documents.document'].with_context(active_test=False) if 'documents.document' in env else None

        sub('Perfil de los clientes que compraron productos "/" (top %s)' % len(top_ids))
        partners = env['res.partner'].with_context(active_test=False).browse(top_ids)
        x_fnames = [fname for fname in sorted(env['res.partner']._fields) if fname.startswith('x_')]
        for p in partners:
            family_ids = (p | p.child_ids).ids
            att_cnt = Att.search_count([('res_model', '=', 'res.partner'), ('res_id', 'in', family_ids)])
            att_names = Att.search([('res_model', '=', 'res.partner'), ('res_id', 'in', family_ids)], limit=5).mapped('name')
            doc_cnt = 0
            if Doc is not None and has_field('documents.document', 'partner_id'):
                doc_cnt = Doc.search_count([('partner_id', 'in', family_ids)])
            extras = []
            if p.category_id:
                extras.append('tags=%s' % p.category_id.mapped('name'))
            if has_field('res.partner', 'industry_id') and p.industry_id:
                extras.append('ind=%r' % p.industry_id.name)
            if has_field('res.partner', 'sale_warn') and p.sale_warn != 'no-message':
                extras.append('warn=%s:%r' % (p.sale_warn, p.sale_warn_msg))
            if p.ref:
                extras.append('ref=%r' % p.ref)
            if p.comment:
                extras.append('comment=%r' % strip_html(p.comment)[:100])
            if att_cnt:
                extras.append('atts=%s %s' % (att_cnt, att_names))
            if doc_cnt:
                extras.append('docs=%s' % doc_cnt)
            x_non_empty = {fn: fmt(p, fn, max_len=60) for fn in x_fnames if fmt(p, fn, max_len=60) not in (False, None, '', 0, 0.0, '[]')}
            if x_non_empty:
                extras.append('x_=%s' % x_non_empty)

            print('  id=%-6s | conf=%-3s | tot=%-3s | vat=%-13r | %-35r%s' % (
                p.id, confirmed_buyer_counts.get(p.id, 0), buyer_counts.get(p.id, 0),
                p.vat or '', p.name, (' | ' + ' | '.join(extras)) if extras else '',
            ))

    # ------------------------------------------------------------------ COMPRAS
    if 'purchase.order.line' in env:
        sub('Compras (purchase.order.line) con productos trazados')
        pols = env['purchase.order.line'].search([('product_id', 'in', traced_prods.ids)])
        print('Total líneas purchase.order.line: %s | Órdenes: %s' % (len(pols), len(pols.mapped('order_id'))))
        print('Líneas por estado: %s' % dict(Counter(pols.mapped('order_id.state'))))
        sup_cnt = Counter(
            l.order_id.partner_id.commercial_partner_id.id
            for l in pols if l.order_id.partner_id
        )
        print('Proveedores comerciales distintos: %s' % len(sup_cnt))
        for sid, cnt in sup_cnt.most_common(25):
            sp = env['res.partner'].with_context(active_test=False).browse(sid)
            print('  id=%-6s | lineas=%-4s | vat=%-13r | %-35r | tags=%s' % (
                sp.id, cnt, sp.vat or '', sp.name, sp.category_id.mapped('name'),
            ))

    # ------------------------------------------------------------------ INVENTARIO / LOTES
    if 'stock.move' in env:
        sub('Movimientos de stock (stock.move / stock.move.line) con productos trazados')
        moves = env['stock.move'].search([('product_id', 'in', traced_prods.ids)])
        print('Total stock.move: %s' % len(moves))
        print('Por estado: %s' % dict(Counter(moves.mapped('state'))))
        print('Por tipo de operación: %s' % dict(Counter(m.picking_type_id.code or '?' for m in moves)))
        smls = env['stock.move.line'].search([('product_id', 'in', traced_prods.ids)])
        has_lot_name = has_field('stock.move.line', 'lot_name')
        with_lot = smls.filtered(lambda l: l.lot_id or (has_lot_name and l.lot_name))
        print('stock.move.line totales: %s | con lote/serie asignado: %s' % (len(smls), len(with_lot)))

    # ------------------------------------------------------------------ FACTURACIÓN
    if 'account.move.line' in env:
        sub('Facturas/NC (account.move.line) con productos trazados')
        amls = env['account.move.line'].search([
            ('product_id', 'in', traced_prods.ids),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
        ])
        print('Total account.move.line: %s | Comprobantes distintos: %s' % (len(amls), len(amls.mapped('move_id'))))
        print('Por (move_type, state): %s' % dict(Counter((l.move_id.move_type, l.move_id.state) for l in amls)))
        if has_field('account.move', 'l10n_latam_document_type_id'):
            posted_amls = amls.filtered(lambda l: l.move_id.state == 'posted')
            print('Tipos de comprobante ARCA (posted): %s' % dict(Counter(
                l.move_id.l10n_latam_document_type_id.name or 'Sin tipo' for l in posted_amls
            )))
__EOF_AUDIT__
cat > ~/tmp/dim22_trazados/scripts/05_vistas_reportes_estudio_y_pdf.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 05 - Vistas Studio/custom, reportes QWeb PDF existentes y verificación de Website/eCommerce (solo lectura)

h('05 - VISTAS CUSTOM/STUDIO, REPORTES QWEB Y WEBSITE')

TARGET_MODELS = [
    'product.template', 'product.product', 'res.partner',
    'sale.order', 'sale.order.line',
    'purchase.order', 'purchase.order.line',
    'stock.picking', 'stock.move',
    'account.move', 'account.move.line',
]

# Mapa view_id -> xml_id (module.name)
imd_recs = env['ir.model.data'].search([('model', '=', 'ir.ui.view')])
view_xmlids = {r.res_id: '%s.%s' % (r.module, r.name) for r in imd_recs}
installed_core_mods = set(env['ir.module.module'].search([
    ('state', '=', 'installed'),
    ('author', 'ilike', 'Odoo S.A.'),
]).mapped('name'))

sub('Vistas heredadas/custom/Studio en modelos objetivo (ir.ui.view)')
views = env['ir.ui.view'].with_context(active_test=False).search([
    '|', ('model', 'in', TARGET_MODELS), ('type', '=', 'qweb'),
], order='model, priority, id')

for v in views:
    xmlid = view_xmlids.get(v.id, '')
    mod = xmlid.split('.')[0] if '.' in xmlid else ''
    is_studio = 'studio' in (v.name or '').lower() or 'studio' in xmlid.lower()
    is_custom = (not mod) or (mod not in installed_core_mods)
    if v.type == 'qweb':
        # Para qweb filtramos las relevantes a ventas/compras/remitos/facturas o custom/studio
        qblob = ('%s %s' % (v.name or '', xmlid)).lower()
        qrelevant = any(k in qblob for k in ('saleorder', 'purchaseorder', 'deliveryslip', 'invoice', 'l10n_ar', 'picking', 'studio'))
        if not (qrelevant and (is_studio or is_custom)):
            continue
    elif not (is_studio or is_custom):
        continue

    print('  id=%-5s | act=%-5s | type=%-5s | model=%-20s | prio=%-3s | xmlid=%-40s | inherit=%s | name=%r' % (
        v.id, v.active, v.type, v.model or '-', v.priority, xmlid or '<sin xml_id>',
        v.inherit_id.name if v.inherit_id else '-', v.name,
    ))
    if v.arch_db:
        print('    ARCH:\n' + '\n'.join('    ' + ln for ln in v.arch_db.splitlines()[:80]))

sub('Reportes QWeb registrados (ir.actions.report) para Venta, Compra, Remito y Factura')
reports = env['ir.actions.report'].search([
    ('model', 'in', ['sale.order', 'purchase.order', 'stock.picking', 'account.move']),
], order='model, id')
rep_imd = {r.res_id: '%s.%s' % (r.module, r.name) for r in env['ir.model.data'].search([('model', '=', 'ir.actions.report')])}
for r in reports:
    print('  id=%-4s | model=%-15s | type=%-10s | xmlid=%-42s | report_name=%-40s | name=%r' % (
        r.id, r.model, r.report_type, rep_imd.get(r.id, '<sin xml_id>'), r.report_name, r.name,
    ))

sub('Estado de Website / eCommerce respecto a productos "/"')
pub_field = (
    'website_published' if has_field('product.template', 'website_published')
    else ('is_published' if has_field('product.template', 'is_published') else None)
)
if 'website' in env and pub_field:
    PT = env['product.template'].with_context(active_test=False)
    traced = PT.search([('name', '=like', TRACED_PREFIX + '%')])
    pub_traced = traced.filtered(lambda p: p[pub_field])
    print('website_sale instalado. Productos "/" totales: %s | publicados en web (%s): %s' % (
        len(traced), pub_field, len(pub_traced),
    ))
    for p in pub_traced[:30]:
        print('  [WEB PUB] id=%s | name=%r | website_id=%s' % (
            p.id, p.name, fmt(p, 'website_id') if has_field('product.template', 'website_id') else '-',
        ))
else:
    print('website_sale no está instalado (o product.template sin website_published/is_published).')
__EOF_AUDIT__
chmod +x ~/tmp/dim22_trazados/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/dim22_trazados:'; ls -R ~/tmp/dim22_trazados | head -50
