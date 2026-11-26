#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/atlas_relevamiento
mkdir -p ~/tmp/atlas_relevamiento/scripts && cd ~/tmp/atlas_relevamiento
cat > ~/tmp/atlas_relevamiento/run_all.sh <<'__EOF_AUDIT__'
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
cat > ~/tmp/atlas_relevamiento/scripts/_lib.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# Helpers comunes. Se ejecuta dentro de `odoo-bin shell` (la variable `env` ya existe, superusuario).
import base64
import html
import inspect
import os
import re
import traceback

# ---------------------------------------------------------------------------
# PARÁMETROS DE LA TAREA (Atlas - Relevamiento permisos, notificaciones y OC<->OV)
# ---------------------------------------------------------------------------
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'BULGHERONI')
COMPANY_1066_NAME = os.environ.get('COMPANY_1066_NAME', '1066')
MOD_ATLAS = os.environ.get('MOD_ATLAS', 'atlas_security_approvals')

TARGET_LOGINS = [
    'mandatario@atlasgroup.com.ar',
    'hernanpacetti@atlasgroup.com.ar',
    'administracion@atlasgroup.com.ar',
    'eugeniazanotti@atlasgroup.com.ar',
    'hernanfernandez@atlasgroup.com.ar',
]

# Usuarios que deben recibir la notificación/actividad de aprobación de Ventas
NOTIF_VENTA_LOGINS = [
    'hernanfernandez@atlasgroup.com.ar',
    'eugeniazanotti@atlasgroup.com.ar',
]

# Usuarios que aprueban y reciben notificación en circuito de Compras
NOTIF_COMPRA_LOGINS = [
    'hernanfernandez@atlasgroup.com.ar',
    'eugeniazanotti@atlasgroup.com.ar',
]

# Contacto particular configurable para el circuito de aprobación de Compras
CONTACTO_CIRCUITO_COMPRA = os.environ.get(
    'CONTACTO_CIRCUITO_COMPRA',
    '[ATLAS] Proveedor Tercero Circuito',
)


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
    name = name if name is not None else COMPANY_NAME
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
    return model in env and fname in env[model]._fields


def chatter(record):
    """Mensajes + tracking de un registro (quién cambió qué y cuándo)."""
    msgs = env['mail.message'].search(
        [('model', '=', record._name), ('res_id', '=', record.id)],
        order='date, id',
    )
    for msg in msgs:
        partners = msg.partner_ids.mapped('name') if has_field('mail.message', 'partner_ids') else []
        print(
            '  [%s] id=%s tipo=%s autor=%s subtype=%s partner_ids=%s'
            % (
                msg.date,
                msg.id,
                msg.message_type,
                msg.author_id.display_name,
                msg.subtype_id.name,
                partners,
            )
        )
        body = strip_html(msg.body)
        if body:
            print('      cuerpo: %s' % body[:2000])
        for t in msg.tracking_value_ids:
            fname = t.field_id.name if 'field_id' in t._fields else '?'
            old = t.old_value_char or t.old_value_integer or t.old_value_float or t.old_value_datetime
            new = t.new_value_char or t.new_value_integer or t.new_value_float or t.new_value_datetime
            print('      tracking: %s: %r -> %r' % (fname, old, new))
        if 'mail.notification' in env:
            notifs = env['mail.notification'].search([('mail_message_id', '=', msg.id)])
            for nf in notifs:
                print(
                    '      notif id=%s para=%s tipo=%s estado=%s is_read=%s failure=%s'
                    % (
                        nf.id,
                        nf.res_partner_id.display_name,
                        nf.notification_type if has_field('mail.notification', 'notification_type') else '?',
                        nf.notification_status if has_field('mail.notification', 'notification_status') else '?',
                        nf.is_read if has_field('mail.notification', 'is_read') else '?',
                        nf.failure_type if has_field('mail.notification', 'failure_type') else '?',
                    )
                )


def method_sources(model, methods, only_custom=True):
    """Para cada método, lista qué módulos lo definen (MRO) e imprime la fuente de los no core."""
    if model not in env:
        print('  (modelo %s no existe)' % model)
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


def find_user(login):
    return env['res.users'].with_context(active_test=False).search([('login', '=ilike', login.strip())], limit=1)
__EOF_AUDIT__
cat > ~/tmp/atlas_relevamiento/scripts/01_entorno_usuarios_notificaciones.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 01 - Entorno, compañías, usuarios Atlas, notification_type y estado de correo/notificaciones (solo lectura)
import odoo

h('01 - ENTORNO, USUARIOS Y CONFIGURACIÓN DE NOTIFICACIONES')
print('DB:      %s' % env.cr.dbname)
print('Odoo:    %s' % odoo.release.version)

sub('Parámetros de sistema clave (neutralización / correo / base)')
ICP = env['ir.config_parameter'].sudo()
for key in [
    'database.is_neutralized',
    'web.base.url',
    'mail.catchall.domain',
    'mail.default.from',
    'mail.bounce.alias',
]:
    print('  %-35s %r' % (key, ICP.get_param(key)))

sub('Servidores de correo saliente (ir.mail_server)')
for srv in env['ir.mail_server'].with_context(active_test=False).search([]):
    dump(srv, names=['name', 'active', 'smtp_host', 'smtp_port', 'smtp_encryption', 'smtp_user', 'sequence'])

sub('Compañías registradas')
for c in env['res.company'].search([]):
    print(
        '  id=%-3s | %-35s | moneda=%-5s | vat=%-18s | po_double_val=%s (%s)'
        % (
            c.id,
            c.name,
            c.currency_id.name if c.currency_id else '-',
            c.vat if has_field('res.company', 'vat') else '-',
            c.po_double_validation if has_field('res.company', 'po_double_validation') else '-',
            c.po_double_validation_amount if has_field('res.company', 'po_double_validation_amount') else '-',
        )
    )

sub('Usuarios del proyecto Atlas (detalle completo incluyendo notification_type)')
for login in TARGET_LOGINS:
    u = find_user(login)
    if not u:
        print('  [FALTA] %s (no existe en la BD)' % login)
        continue
    print('\n  >> %s (id=%s | partner_id=%s | activo=%s)' % (u.login, u.id, u.partner_id.id, u.active))
    dump(
        u,
        names=[
            'name',
            'login',
            'email',
            'active',
            'share',
            'state',
            'notification_type',
            'odoobot_state',
            'company_id',
            'company_ids',
            'lang',
            'tz',
        ],
    )
    atlas_groups = [
        '%s (%s)' % (g.name, g.get_external_id().get(g.id, '-'))
        for g in u.groups_id
        if 'atlas' in (g.category_id.name or '').lower() or 'atlas' in (g.name or '').lower() or 'rol:' in (g.name or '').lower()
    ]
    key_app_xmlids = [
        'sales_team.group_sale_salesman',
        'sales_team.group_sale_salesman_all_leads',
        'sales_team.group_sale_manager',
        'purchase.group_purchase_user',
        'purchase.group_purchase_manager',
        'account.group_account_invoice',
        'account.group_account_user',
        'account.group_account_manager',
        'base.group_erp_manager',
        'base.group_system',
    ]
    has_apps = [x for x in key_app_xmlids if env.ref(x, raise_if_not_found=False) and u.has_group(x)]
    print('  %-45s %s' % ('grupos_atlas', atlas_groups or '[]'))
    print('  %-45s %s' % ('grupos_app_clave', has_apps))

sub('Otros usuarios internos (share=False)')
other_users = env['res.users'].with_context(active_test=False).search([
    ('share', '=', False),
    ('login', 'not in', TARGET_LOGINS),
])
for u in other_users:
    nt = u.notification_type if has_field('res.users', 'notification_type') else '?'
    print('  id=%-4s activo=%-5s notif=%-6s login=%-38s nombre=%s' % (u.id, u.active, nt, u.login, u.name))

sub('Grupos de categoría Atlas y membresías')
groups = env['res.groups'].search([
    '|',
    ('category_id.name', 'ilike', 'atlas'),
    ('name', 'ilike', 'atlas'),
])
if not groups:
    print('  (Sin grupos Atlas encontrados)')
for g in groups:
    xmlid = g.get_external_id().get(g.id, '-')
    print(
        '  id=%-4s | %-42s | xmlid=%-50s | implica=%s | usuarios=%s'
        % (
            g.id,
            g.name,
            xmlid,
            g.implied_ids.mapped('name'),
            g.users.mapped('login'),
        )
    )

sub('Últimas 15 mail.notification para Hernán F., Euge y Hernán Pacetti')
check_users = [find_user(l) for l in (NOTIF_VENTA_LOGINS + ['hernanpacetti@atlasgroup.com.ar'])]
check_partners = [u.partner_id.id for u in check_users if u and u.partner_id]
if check_partners and 'mail.notification' in env:
    notifs = env['mail.notification'].search(
        [('res_partner_id', 'in', check_partners)],
        order='id desc',
        limit=15,
    )
    if not notifs:
        print('  (Sin registros en mail.notification para estos usuarios)')
    for nf in notifs:
        msg = nf.mail_message_id
        print(
            '  nf=%-6s | para=%-20s | tipo=%-6s | estado=%-10s | read=%-5s | model=%-15s res_id=%-5s | msg=%s'
            % (
                nf.id,
                nf.res_partner_id.name[:20],
                nf.notification_type if has_field('mail.notification', 'notification_type') else '?',
                nf.notification_status if has_field('mail.notification', 'notification_status') else '?',
                nf.is_read if has_field('mail.notification', 'is_read') else '?',
                msg.model or '-',
                msg.res_id or 0,
                strip_html(msg.body)[:90],
            )
        )

sub('Actividades pendientes (mail.activity) para usuarios Atlas')
atlas_uids = [u.id for u in [find_user(l) for l in TARGET_LOGINS] if u]
if atlas_uids and 'mail.activity' in env:
    acts = env['mail.activity'].search([('user_id', 'in', atlas_uids)], order='id desc', limit=30)
    if not acts:
        print('  (Sin actividades pendientes para usuarios Atlas)')
    for a in acts:
        print(
            '  act=%-5s | user=%-32s | tipo=%-22s | model=%-15s res_id=%-5s | deadline=%s | summary=%s'
            % (
                a.id,
                a.user_id.login,
                a.activity_type_id.name,
                a.res_model,
                a.res_id,
                a.date_deadline,
                (a.summary or '')[:60],
            )
        )
__EOF_AUDIT__
cat > ~/tmp/atlas_relevamiento/scripts/02_modulos_custom_vinculo_oc_ov.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 02 - Relevamiento de módulos custom (~/src/user), vínculo OC <-> OV, campos, métodos y automatizaciones
import ast
import os

h('02 - MÓDULOS CUSTOM Y VÍNCULO COMPRAS <-> VENTAS')

sub('Módulos instalados NO desarrollados por Odoo S.A.')
Mod = env['ir.module.module']
custom_mods = Mod.search([
    ('state', 'in', ('installed', 'to upgrade', 'to install')),
    ('author', 'not ilike', 'Odoo S.A.'),
], order='name')
for m in custom_mods:
    print('  %-38s | estado=%-10s | ver=%-15s | autor=%-25s | %s' % (
        m.name, m.state, m.installed_version or '-', (m.author or '-')[:25], (m.shortdesc or '')[:60]
    ))

sub('Módulos clave estándar + Atlas')
for mname in [
    'sale_management', 'purchase', 'purchase_requisition', 'account_accountant',
    'l10n_ar', 'web_studio', 'approvals', 'atlas_security_approvals', 'sale_purchase',
    'sale_purchase_stock', 'sale_expense', 'project_purchase',
]:
    m = Mod.search([('name', '=', mname)], limit=1)
    print('  %-32s -> %s' % (mname, m.state if m else 'no encontrado'))

sub('Escaneo de ~/src/user/ en disco (addons del repositorio Odoo.sh)')
user_src = os.path.expanduser('~/src/user')
user_addon_names = set()
relevant_addons = []

if not os.path.isdir(user_src):
    print('  (No existe %s)' % user_src)
else:
    for root, dirs, files in os.walk(user_src):
        dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', 'static', 'i18n'))
        if '__manifest__.py' in files:
            addon_name = os.path.basename(root)
            user_addon_names.add(addon_name)
            mpath = os.path.join(root, '__manifest__.py')
            mrec = Mod.search([('name', '=', addon_name)], limit=1)
            state = mrec.state if mrec else 'no_en_bd'
            manifest = {}
            try:
                with open(mpath, 'r', encoding='utf-8', errors='replace') as fh:
                    manifest = ast.literal_eval(fh.read())
            except Exception as e:
                manifest = {'_error': str(e)}
            rel_path = os.path.relpath(root, user_src)
            print('\n  ADDON: %-35s | estado=%-10s | ruta=%s' % (addon_name, state, rel_path))
            print('    name:    %s' % manifest.get('name'))
            print('    summary: %s' % manifest.get('summary'))
            print('    depends: %s' % manifest.get('depends'))
            print('    data:    %s' % manifest.get('data'))
            # Detectar relevancia con ventas/compras/terceros/atlas/aprobaciones
            blob = (addon_name + ' ' + str(manifest)).lower()
            if any(k in blob for k in ('purchase', 'sale', 'atlas', 'approv', 'aprob', 'tercer', 'gasto', 'partner', 'link', 'vinc')):
                relevant_addons.append((addon_name, root, state))
            # No bajar dentro de subcarpetas de otro addon si ya es un addon
            dirs[:] = []

sub('Campos custom o no-core en purchase.order, purchase.order.line, sale.order, sale.order.line y res.partner')
Models_check = ['purchase.order', 'purchase.order.line', 'sale.order', 'sale.order.line', 'res.partner']
IMD = env['ir.model.data'].sudo()
Fields = env['ir.model.fields'].sudo()

for model_name in Models_check:
    if model_name not in env:
        continue
    print('\n  MODELO: %s' % model_name)
    all_fields = Fields.search([('model', '=', model_name)], order='name')
    # Mapeo field_id -> módulo creador en ir.model.data
    imds = IMD.search([('model', '=', 'ir.model.fields'), ('res_id', 'in', all_fields.ids)])
    mod_by_fid = {d.res_id: d.module for d in imds}

    for f in all_fields:
        origin_mod = mod_by_fid.get(f.id, '-')
        is_x = f.name.startswith('x_') or f.state == 'manual'
        is_user_mod = origin_mod in user_addon_names
        is_cross_link = (
            (model_name.startswith('purchase.') and f.relation in ('sale.order', 'sale.order.line'))
            or (model_name.startswith('sale.') and f.relation in ('purchase.order', 'purchase.order.line'))
        )
        if is_x or is_user_mod or is_cross_link:
            tag = 'USER_MOD' if is_user_mod else ('CROSS_LINK' if is_cross_link else 'MANUAL/X')
            print(
                '    [%-10s] %-34s | tipo=%-10s | rel=%-20s | mod=%-28s | label=%s'
                % (tag, f.name, f.ttype, f.relation or '-', origin_mod, f.field_description)
            )

sub('Código fuente de métodos custom (/src/user/) en modelos clave')
for model_name in Models_check:
    if model_name not in env:
        continue
    cls = type(env[model_name])
    custom_methods = []
    seen = set()
    for k in cls.__mro__:
        for attr_name, val in k.__dict__.items():
            if attr_name in seen or not callable(val):
                continue
            try:
                src_path = (inspect.getsourcefile(val) or '').replace('\\', '/')
            except Exception:
                src_path = ''
            if '/src/user/' in src_path:
                seen.add(attr_name)
                custom_methods.append(attr_name)
    if custom_methods:
        print('\n  Métodos definidos en /src/user/ sobre %s: %s' % (model_name, custom_methods))
        method_sources(model_name, custom_methods, only_custom=True)
    else:
        print('  (%s: sin métodos en /src/user/)' % model_name)

sub('Lectura completa de archivos .py y .xml de addons relevantes en ~/src/user/')
for addon_name, root, state in relevant_addons:
    print('\n' + '#' * 90)
    print('# ADDON RELEVANTE: %s (estado=%s)' % (addon_name, state))
    print('#' * 90)
    for r, ds, fs in os.walk(root):
        ds[:] = sorted(d for d in ds if d not in ('__pycache__', 'static', 'i18n', 'tests'))
        for fn in sorted(fs):
            if fn.endswith(('.py', '.xml')) and fn != '__init__.py':
                fpath = os.path.join(r, fn)
                rel = os.path.relpath(fpath, root)
                print('\n  --- %s/%s ---' % (addon_name, rel))
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                        lines = fh.readlines()
                    max_lines = 250
                    print(''.join(lines[:max_lines]))
                    if len(lines) > max_lines:
                        print('  ... <truncado: %s líneas totales>' % len(lines))
                except Exception as e:
                    print('  <error leyendo archivo: %s>' % e)

sub('Automatizaciones (base.automation) y Acciones de servidor (ir.actions.server code)')
if 'base.automation' in env:
    autos = env['base.automation'].with_context(active_test=False).search([])
    if not autos:
        print('  (Sin base.automation)')
    for a in autos:
        print('\n  AUTO id=%s active=%s name=%s model=%s trigger=%s' % (
            a.id, a.active, a.name, a.model_id.model, a.trigger if has_field('base.automation', 'trigger') else '?'
        ))
        dump(a, names=['filter_domain', 'filter_pre_domain', 'trigger_field_ids', 'action_server_ids'])
        if has_field('base.automation', 'action_server_ids'):
            for srv in a.action_server_ids:
                dump(srv, names=['name', 'state', 'code'], full=['code'])

if 'ir.actions.server' in env:
    srvs = env['ir.actions.server'].search([
        ('state', '=', 'code'),
        ('model_id.model', 'in', Models_check + ['studio.approval.rule', 'studio.approval.entry', 'studio.approval.request']),
    ])
    print('\n  ir.actions.server (state=code) sobre modelos clave: %s' % len(srvs))
    for s in srvs:
        print('  SRV id=%s model=%s name=%s' % (s.id, s.model_id.model, s.name))
        dump(s, names=['code'], full=['code'])

sub('Ejemplos reales en BD de OC vinculadas a OV (si hay campos detectados)')
if 'purchase.order' in env:
    po_model = env['purchase.order']
    sale_link_fields = [
        fn for fn, f in po_model._fields.items()
        if getattr(f, 'comodel_name', None) in ('sale.order', 'sale.order.line')
    ]
    print('  Campos en purchase.order hacia sale.order*: %s' % sale_link_fields)
    for fn in sale_link_fields:
        linked = po_model.search([(fn, '!=', False)], order='id desc', limit=5)
        print('  OC con %s poblado: %s' % (fn, len(linked)))
        for po in linked:
            print('    PO %s (id=%s, state=%s, partner=%s) -> %s=%s' % (
                po.name, po.id, po.state, po.partner_id.name, fn, fmt(po, fn)
            ))

if 'sale.order' in env:
    so_model = env['sale.order']
    po_link_fields = [
        fn for fn, f in so_model._fields.items()
        if getattr(f, 'comodel_name', None) in ('purchase.order', 'purchase.order.line')
    ]
    print('  Campos en sale.order hacia purchase.order*: %s' % po_link_fields)
    for fn in po_link_fields:
        linked = so_model.search([(fn, '!=', False)], order='id desc', limit=5)
        print('  OV con %s poblado: %s' % (fn, len(linked)))
        for so in linked:
            print('    SO %s (id=%s, state=%s, partner=%s) -> %s=%s' % (
                so.name, so.id, so.state, so.partner_id.name, fn, fmt(so, fn)
            ))
__EOF_AUDIT__
cat > ~/tmp/atlas_relevamiento/scripts/03_studio_approvals_motor_y_reglas.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 03 - Relevamiento del motor Studio Approvals (código real del build) y reglas actuales
import inspect

h('03 - STUDIO APPROVALS: REGLAS, HISTORIAL Y CÓDIGO DEL MOTOR')

if 'studio.approval.rule' not in env:
    print('!! El modelo studio.approval.rule NO existe (¿web_studio instalado?)')
else:
    Rule = env['studio.approval.rule'].with_context(active_test=False)

    sub('Campos de studio.approval.rule')
    for fname, field in sorted(Rule._fields.items()):
        if not field.automatic and not fname.startswith(('message_', 'website_message', 'activity_')):
            print('  %-28s | %-12s | store=%-5s | %s' % (fname, field.type, field.store, field.string))
            if field.help:
                print('      help: %s' % field.help.replace('\n', ' '))

    sub('Todas las reglas studio.approval.rule en la base (activas e inactivas)')
    rules = Rule.search([], order='id')
    if not rules:
        print('  (Sin reglas registradas)')
    for r in rules:
        xmlid = r.get_external_id().get(r.id, '-')
        print('\n  REGLA id=%s | active=%s | xmlid=%s | name=%s' % (r.id, r.active, xmlid, r.name))
        dump(
            r,
            names=[
                'name', 'active', 'model_id', 'model_name', 'method', 'action_id',
                'approval_group_id', 'approver_ids', 'users_to_notify',
                'notification_order', 'exclusive_user', 'domain', 'message',
                'conditional', 'can_validate',
            ],
            full=['domain', 'message'],
        )
        if r.approval_group_id:
            print('  %-45s %s' % ('approval_group_id.users', r.approval_group_id.users.mapped('login')))

    sub('Últimas 20 entradas (studio.approval.entry)')
    if 'studio.approval.entry' in env:
        entries = env['studio.approval.entry'].search([], order='id desc', limit=20)
        if not entries:
            print('  (Sin studio.approval.entry)')
        for e in entries:
            print(
                '  id=%-5s | rule=%-35s | model=%-15s res_id=%-5s | user=%-32s | approved=%-5s | date=%s'
                % (
                    e.id,
                    (e.rule_id.name or '-')[:35],
                    e.model if has_field('studio.approval.entry', 'model') else '-',
                    e.res_id,
                    e.user_id.login if e.user_id else '-',
                    e.approved,
                    e.create_date,
                )
            )

    sub('Últimas 20 solicitudes (studio.approval.request)')
    if 'studio.approval.request' in env:
        reqs = env['studio.approval.request'].search([], order='id desc', limit=20)
        if not reqs:
            print('  (Sin studio.approval.request)')
        for q in reqs:
            act = q.mail_activity_id if has_field('studio.approval.request', 'mail_activity_id') else None
            print(
                '  id=%-5s | rule=%-35s | res_id=%-5s | act_id=%-5s | act_user=%-32s | date=%s'
                % (
                    q.id,
                    (q.rule_id.name or '-')[:35],
                    q.res_id,
                    act.id if act else 0,
                    act.user_id.login if act and act.user_id else '-',
                    q.create_date,
                )
            )

    sub('Código fuente de studio.approval.rule en este build (notificaciones, menciones y actividades)')
    cls = type(Rule)
    methods_to_inspect = [
        '_compute_can_validate',
        'check_approval',
        '_check_approval',
        '_create_request',
        '_get_approval_spec',
        'get_approval_spec',
        'set_approval',
        '_set_approval',
        '_notify_approval',
        '_send_approval_notification',
        'delete_approval',
        '_get_rule_domain',
    ]
    for mname in methods_to_inspect:
        fn = getattr(cls, mname, None)
        if fn:
            print('\n  >>> studio.approval.rule.%s%s' % (mname, safe(inspect.signature, fn) or ''))
            src = safe(inspect.getsource, fn)
            if src:
                print(src[:4500])

    def _srcfile(obj):
        try:
            return (inspect.getsourcefile(obj) or '').replace('\\', '/')
        except Exception:
            return ''

    sub('Líneas de web_studio/models/studio_approval.py relacionadas con notificaciones / menciones / actividades')
    mod_file = None
    for k in cls.__mro__:
        p = _srcfile(k)
        if p and 'web_studio' in p:
            mod_file = p
            break
    print('  Archivo fuente: %s' % mod_file)
    if mod_file and os.path.isfile(mod_file):
        with open(mod_file, 'r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
        keywords = ('users_to_notify', 'approver_ids', 'message_post', 'activity_schedule', 'partner_ids', 'mail.notification', '_notify', 'create_request', 'Grant Approval')
        for idx, line in enumerate(lines, 1):
            if any(k in line for k in keywords):
                print('  L%04d: %s' % (idx, line.rstrip()))

    if 'studio.approval.entry' in env:
        sub('Código fuente de studio.approval.entry (clases en web_studio / custom)')
        ecls = type(env['studio.approval.entry'])
        for k in ecls.__mro__:
            p = _srcfile(k)
            if 'web_studio' in p or '/src/user/' in p:
                print('\n  >>> %s (%s)' % (k.__module__, p))
                src = safe(inspect.getsource, k)
                if src:
                    print(src[:4500])

    if 'studio.approval.request' in env:
        sub('Código fuente de studio.approval.request (clases en web_studio / custom)')
        qcls = type(env['studio.approval.request'])
        for k in qcls.__mro__:
            p = _srcfile(k)
            if 'web_studio' in p or '/src/user/' in p:
                print('\n  >>> %s (%s)' % (k.__module__, p))
                src = safe(inspect.getsource, k)
                if src:
                    print(src[:4500])

    sub('Vistas heredadas de Studio / custom sobre sale.order y purchase.order')
    views = env['ir.ui.view'].with_context(active_test=False).search([
        ('model', 'in', ['sale.order', 'purchase.order']),
        '|',
        ('name', 'ilike', 'studio'),
        ('arch_db', 'ilike', 'studio_approval'),
    ])
    print('  Vistas encontradas: %s' % len(views))
    for v in views:
        print('  VIEW id=%s active=%s model=%s name=%s' % (v.id, v.active, v.model, v.name))
        dump(v, names=['arch_db'], full=['arch_db'])
__EOF_AUDIT__
cat > ~/tmp/atlas_relevamiento/scripts/04_estado_actual_demo_y_contactos.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 04 - Estado actual de documentos demo, contactos existentes y chatter/notificaciones previas (solo lectura)

h('04 - DOCUMENTOS DEMO, CONTACTOS Y EVIDENCIA PREVIA EN CHATTER')

sub('Resumen de sale.order y purchase.order por compañía y estado')
for model_name in ('sale.order', 'purchase.order'):
    if model_name not in env:
        continue
    print('\n  %s (total=%s):' % (model_name, env[model_name].search_count([])))
    groups = safe(env[model_name].read_group, [], ['company_id', 'state'], ['company_id', 'state'], lazy=False) or []
    for g in groups:
        print('    comp=%-35s | state=%-12s | count=%s' % (g.get('company_id'), g.get('state'), g.get('__count')))

sub('Registros DEMO / TEST previos de Atlas (para saber qué limpiar luego)')
demo_sos = env['sale.order'].search([
    '|', '|',
    ('client_order_ref', 'ilike', 'DEMO'),
    ('client_order_ref', 'ilike', 'TEST'),
    ('partner_id.name', 'ilike', 'ATLAS'),
], order='id desc', limit=20)
print('  sale.order demo/test (%s):' % len(demo_sos))
for so in demo_sos:
    print('    id=%-5s name=%-12s state=%-8s ref=%-18s user=%-25s partner=%-35s total=%s' % (
        so.id, so.name, so.state, so.client_order_ref or '-', so.user_id.login or '-', so.partner_id.name[:35], so.amount_total
    ))

demo_pos = env['purchase.order'].search([
    '|', '|',
    ('partner_ref', 'ilike', 'DEMO'),
    ('partner_ref', 'ilike', 'TEST'),
    ('partner_id.name', 'ilike', 'ATLAS'),
], order='id desc', limit=20)
print('\n  purchase.order demo/test (%s):' % len(demo_pos))
for po in demo_pos:
    print('    id=%-5s name=%-12s state=%-10s ref=%-18s user=%-25s partner=%-35s total=%s' % (
        po.id, po.name, po.state, po.partner_ref or '-', po.user_id.login or '-', po.partner_id.name[:35], po.amount_total
    ))

sub('Chatter + actividades + mail.notification de las últimas 3 OV (demo o recientes)')
inspect_sos = demo_sos[:3] if demo_sos else env['sale.order'].search([], order='id desc', limit=3)
for so in inspect_sos:
    print('\n  >>> OV %s (id=%s, state=%s, company=%s, user=%s)' % (
        so.name, so.id, so.state, so.company_id.name, so.user_id.login
    ))
    chatter(so)
    acts = env['mail.activity'].search([('res_model', '=', 'sale.order'), ('res_id', '=', so.id)])
    print('  Actividades en %s: %s' % (so.name, [(a.id, a.activity_type_id.name, a.user_id.login, a.summary) for a in acts]))

sub('Chatter + actividades + mail.notification de las últimas 3 OC (demo o recientes)')
inspect_pos = demo_pos[:3] if demo_pos else env['purchase.order'].search([], order='id desc', limit=3)
for po in inspect_pos:
    print('\n  >>> OC %s (id=%s, state=%s, company=%s, user=%s, partner=%s)' % (
        po.name, po.id, po.state, po.company_id.name, po.user_id.login, po.partner_id.name
    ))
    chatter(po)
    acts = env['mail.activity'].search([('res_model', '=', 'purchase.order'), ('res_id', '=', po.id)])
    print('  Actividades en %s: %s' % (po.name, [(a.id, a.activity_type_id.name, a.user_id.login, a.summary) for a in acts]))

sub('Contactos relacionados con Atlas / Terceros / Proveedores recientes')
Partner = env['res.partner'].with_context(active_test=False)
p_match = Partner.search([
    '|', '|', '|',
    ('name', 'ilike', 'atlas'),
    ('name', 'ilike', 'tercero'),
    ('name', 'ilike', 'gasto'),
    ('name', '=', CONTACTO_CIRCUITO_COMPRA),
], limit=30)
print('  Coincidencias por nombre (%s):' % len(p_match))
for p in p_match:
    print('    id=%-6s active=%-5s comp=%-25s supp_rank=%s cust_rank=%s vat=%-15s name=%s' % (
        p.id, p.active, p.company_id.name or '(todas)', p.supplier_rank, p.customer_rank, p.vat or '-', p.name
    ))

print('\n  Últimos 10 proveedores usados en purchase.order:')
recent_pos = env['purchase.order'].search([], order='id desc', limit=20)
seen_p = set()
for po in recent_pos:
    p = po.partner_id
    if p and p.id not in seen_p:
        seen_p.add(p.id)
        print('    id=%-6s comp=%-25s vat=%-15s name=%s' % (p.id, p.company_id.name or '(todas)', p.vat or '-', p.name))
        if len(seen_p) >= 10:
            break
__EOF_AUDIT__
cat > ~/tmp/atlas_relevamiento/scripts/05_simulacion_notificacion_venta_rollback.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 05 - Simulación 100% segura (savepoint + rollback) de notificaciones de aprobación en Ventas
# Comprueba qué genera Studio HOY vs con notification_type='inbox' + Hernán F. y Euge.

h('05 - SIMULACIÓN DE NOTIFICACIONES EN VENTAS (100% ROLLBACK)')


class _Undo(Exception):
    pass


def _inspect_so_events(so, before_msg_id, before_act_id, before_notif_id):
    acts = env['mail.activity'].search([
        ('res_model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', before_act_id),
    ])
    msgs = env['mail.message'].search([
        ('model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', before_msg_id),
    ], order='id')
    notifs = env['mail.notification'].search([
        ('mail_message_id', 'in', msgs.ids),
        ('id', '>', before_notif_id),
    ], order='id')
    reqs = (
        env['studio.approval.request'].search([('res_id', '=', so.id)])
        if 'studio.approval.request' in env
        else env['res.users']
    )
    entries = (
        env['studio.approval.entry'].search([('model', '=', 'sale.order'), ('res_id', '=', so.id)])
        if 'studio.approval.entry' in env
        else env['res.users']
    )

    print('  studio.approval.request (%s):' % len(reqs))
    for q in reqs:
        act = q.mail_activity_id if has_field('studio.approval.request', 'mail_activity_id') else None
        print('    req=%s rule=%s act=%s user=%s' % (q.id, q.rule_id.name, act.id if act else 0, act.user_id.login if act else '-'))

    print('  studio.approval.entry (%s):' % len(entries))
    for e in entries:
        print('    entry=%s rule=%s user=%s approved=%s' % (e.id, e.rule_id.name, e.user_id.login, e.approved))

    print('  mail.activity nuevas (%s):' % len(acts))
    for a in acts:
        print('    act=%s tipo=%s para=%s summary=%s' % (a.id, a.activity_type_id.name, a.user_id.login, a.summary))

    print('  mail.message nuevos (%s):' % len(msgs))
    for m in msgs:
        print('    msg=%s tipo=%s subtype=%s autor=%s partner_ids=%s | body=%s' % (
            m.id, m.message_type, m.subtype_id.name, m.author_id.name,
            m.partner_ids.mapped('name'), strip_html(m.body)[:180]
        ))

    print('  mail.notification nuevas (%s):' % len(notifs))
    for nf in notifs:
        print('    nf=%s para=%s tipo=%s estado=%s is_read=%s msg_id=%s' % (
            nf.id,
            nf.res_partner_id.name,
            nf.notification_type if has_field('mail.notification', 'notification_type') else '?',
            nf.notification_status if has_field('mail.notification', 'notification_status') else '?',
            nf.is_read if has_field('mail.notification', 'is_read') else '?',
            nf.mail_message_id.id,
        ))


try:
    company_bg = get_company(COMPANY_NAME)
    u_op = find_user('mandatario@atlasgroup.com.ar')
    u_pac = find_user('hernanpacetti@atlasgroup.com.ar')
    u_adm = find_user('administracion@atlasgroup.com.ar')
    u_euge = find_user('eugeniazanotti@atlasgroup.com.ar')
    u_hf = find_user('hernanfernandez@atlasgroup.com.ar')

    Rule = env['studio.approval.rule']
    rule_so = Rule.search([
        ('model_id.model', '=', 'sale.order'),
        ('method', '=', 'action_confirm'),
        ('active', '=', True),
    ], limit=1)

    print('Compañía BG: %s' % (company_bg.name if company_bg else 'NO ENCONTRADA'))
    print('Regla OV activa: %s (id=%s)' % (rule_so.name if rule_so else 'NO ENCONTRADA', rule_so.id if rule_so else 0))
    print('Usuarios encontrados: op=%s pac=%s adm=%s euge=%s hf=%s' % (
        bool(u_op), bool(u_pac), bool(u_adm), bool(u_euge), bool(u_hf)
    ))

    if not (company_bg and rule_so and u_op and u_euge and u_hf):
        print('!! Faltan datos mínimos (compañía, regla OV activa o usuarios) para correr la simulación.')
    else:
        partner = env['res.partner'].sudo().search([('company_id', 'in', (False, company_bg.id))], limit=1)
        product = env['product.product'].sudo().search([('sale_ok', '=', True)], limit=1) or env['product.product'].sudo().search([], limit=1)
        if not (partner and product):
            print('!! Falta al menos 1 partner y 1 producto en la base para simular la OV.')
        else:
            # ------------------------------------------------------------------
            # ESCENARIO A: Estado ACTUAL de la base (sin cambios)
            # ------------------------------------------------------------------
            sub('ESCENARIO A: Estado ACTUAL (operador solicita aprobación en OV)')
            try:
                with env.cr.savepoint():
                    so = env['sale.order'].sudo().create({
                        'partner_id': partner.id,
                        'user_id': u_op.id,
                        'company_id': company_bg.id,
                        'order_line': [(0, 0, {
                            'product_id': product.id,
                            'name': 'Simulación Escenario A',
                            'product_uom_qty': 1,
                            'price_unit': 100000.0,
                        })],
                    })
                    env.flush_all()
                    last_msg = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)

                    print('  notification_type ACTUAL -> Hernán F.: %s | Euge: %s | Pacetti: %s' % (
                        u_hf.notification_type, u_euge.notification_type, u_pac.notification_type if u_pac else '-'
                    ))
                    print('  Regla ACTUAL -> approver_ids=%s | users_to_notify=%s' % (
                        rule_so.approver_ids.mapped('login'), rule_so.users_to_notify.mapped('login')
                    ))

                    res = safe(Rule.with_user(u_op).check_approval, 'sale.order', so.id, 'action_confirm', False)
                    env.flush_all()
                    print('  check_approval (como Operador) -> approved=%s' % (res.get('approved') if isinstance(res, dict) else res))
                    _inspect_so_events(so, last_msg, last_act, last_nf)
                    raise _Undo()
            except _Undo:
                pass
            env.invalidate_all()

            # ------------------------------------------------------------------
            # ESCENARIO B: Propuesta (inbox + approver_ids=[HF, Euge] + users_to_notify=[HF, Euge])
            # ------------------------------------------------------------------
            sub('ESCENARIO B: Simulación PROPUESTA (inbox + solo Hernán F. y Euge notificados)')
            try:
                with env.cr.savepoint():
                    notif_users = u_hf | u_euge
                    notif_users.sudo().write({'notification_type': 'inbox'})
                    rule_so.sudo().write({
                        'approver_ids': [(6, 0, notif_users.ids)],
                        'users_to_notify': [(6, 0, notif_users.ids)],
                    })
                    env.flush_all()
                    rule_so.invalidate_recordset()

                    print('  Verificación can_validate con nueva config:')
                    for label, usr in [
                        ('Operador', u_op),
                        ('Hernán Pacetti (por grupo)', u_pac),
                        ('Administrativo', u_adm),
                        ('Eugenia Zanotti', u_euge),
                        ('Hernán Fernández', u_hf),
                    ]:
                        if usr:
                            print('    %-28s -> can_validate=%s | notif_type=%s' % (
                                label, rule_so.with_user(usr).can_validate, usr.notification_type
                            ))

                    so = env['sale.order'].sudo().create({
                        'partner_id': partner.id,
                        'user_id': u_op.id,
                        'company_id': company_bg.id,
                        'order_line': [(0, 0, {
                            'product_id': product.id,
                            'name': 'Simulación Escenario B',
                            'product_uom_qty': 1,
                            'price_unit': 100000.0,
                        })],
                    })
                    env.flush_all()
                    last_msg = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)

                    print('\n  [Paso B1] Operador dispara check_approval:')
                    res = safe(Rule.with_user(u_op).check_approval, 'sale.order', so.id, 'action_confirm', False)
                    env.flush_all()
                    print('  check_approval -> approved=%s' % (res.get('approved') if isinstance(res, dict) else res))
                    _inspect_so_events(so, last_msg, last_act, last_nf)

                    print('\n  [Paso B2] Prueba directa de @mención en chatter hacia Hernán F. y Euge con inbox:')
                    last_msg2 = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act2 = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf2 = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)
                    from markupsafe import Markup
                    mentions = ' '.join(
                        '<a href="#" data-oe-model="res.partner" data-oe-id="%s">@%s</a>' % (u.partner_id.id, u.name)
                        for u in notif_users
                    )
                    so.with_user(u_op).message_post(
                        body=Markup('Solicitud de aprobación pendiente para %s') % Markup(mentions),
                        partner_ids=notif_users.mapped('partner_id').ids,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                    env.flush_all()
                    _inspect_so_events(so, last_msg2, last_act2, last_nf2)

                    print('\n  [Paso B3] Eugenia aprueba (set_approval) para ver qué dispara users_to_notify:')
                    last_msg3 = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act3 = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf3 = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)
                    safe(rule_so.with_user(u_euge).set_approval, so.id, True)
                    env.flush_all()
                    _inspect_so_events(so, last_msg3, last_act3, last_nf3)

                    raise _Undo()
            except _Undo:
                pass
            env.invalidate_all()

finally:
    env.cr.rollback()
    print('\n>> ROLLBACK FINAL EJECUTADO: Base de datos intacta (0 cambios persistidos).')
__EOF_AUDIT__
chmod +x ~/tmp/atlas_relevamiento/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/atlas_relevamiento:'; ls -R ~/tmp/atlas_relevamiento | head -50
