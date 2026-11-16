#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/circuito_padron
mkdir -p ~/tmp/circuito_padron/scripts && cd ~/tmp/circuito_padron
cat > ~/tmp/circuito_padron/run_all.sh <<'__EOF_AUDIT__'
#!/bin/bash
# Ejecuta todos los scripts scripts/[0-9]*.py con odoo-bin shell y genera un zip con los .txt resultantes.
# Uso:  bash ~/tmp/circuito_padron/run_all.sh                 (usa $PGDATABASE o el odoo.conf del build)
#       DB=nombre_base bash ~/tmp/circuito_padron/run_all.sh
#       LOG_PATTERN='arba|padron|withholding' bash ~/tmp/circuito_padron/run_all.sh
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
cat > ~/tmp/circuito_padron/scripts/_lib.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# Helpers comunes. Se ejecuta dentro de `odoo-bin shell` (la variable `env` ya existe, superusuario).
import base64
import html
import inspect
import os
import re
import traceback

# ---------------------------------------------------------------------------
# PARÁMETROS DE LA TAREA (editar o pasar por variable de entorno)
# ---------------------------------------------------------------------------
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'DIMAT')   # ilike sobre res.company.name


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
    if name:
        companies = env['res.company'].search([('name', 'ilike', name)])
        if not companies:
            print('!! No se encontró compañía ilike %r, usando env.company (%s)' % (name, env.company.name))
            return env.company
        if len(companies) > 1:
            print('!! Varias compañías coinciden, uso la primera: %s' % companies.mapped('name'))
        return companies[0]
    return env.company


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
        print('  [!] Modelo %s no existe en env' % model)
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
cat > ~/tmp/circuito_padron/scripts/01_entorno_y_codigo_padron.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 01 - Entorno, módulos instalados, parámetros y código fuente real del circuito de padrón/retenciones
import os

h('01 - ENTORNO, MÓDULOS Y CÓDIGO INSTALADO')

# 1. Compañías
sub('Compañías en la base')
companies = env['res.company'].with_context(active_test=False).search([])
for c in companies:
    print('  [%s] %s | active=%s | CUIT=%s | country=%s | chart=%s' % (
        c.id, c.name, c.active, c.vat, c.country_id.code if c.country_id else False,
        getattr(c, 'chart_template', False),
    ))
    extra = []
    for fname in ('use_payment_pro', 'l10n_ar_arba_wh_mode', 'l10n_ar_afip_ws_environment',
                  'l10n_ar_tax_base_account_id', 'l10n_ar_company_requires_vat', 'reconcile_on_company_currency'):
        if has_field('res.company', fname):
            extra.append('%s=%s' % (fname, fmt(c, fname)))
    if has_field('res.company', 'arba_cit'):
        cit = getattr(c, 'arba_cit', False)
        extra.append('arba_cit=%s' % ('SET (len=%d)' % len(cit) if cit else 'EMPTY'))
    if extra:
        print('      ' + ' | '.join(extra))

company = get_company()
print('\n[*] Compañía seleccionada: [%s] %s' % (company.id, company.name))

# 2. Parámetros del sistema relevantes
sub('ir.config_parameter (arba / padron / l10n_ar / withholding)')
params = env['ir.config_parameter'].sudo().search([
    '|', '|', '|',
    ('key', 'ilike', 'arba'),
    ('key', 'ilike', 'padron'),
    ('key', 'ilike', 'l10n_ar'),
    ('key', 'ilike', 'withholding'),
], order='key')
for p in params:
    val = p.value or ''
    if any(k in p.key.lower() for k in ('pass', 'secret', 'token', 'cit', 'key')):
        val = '<oculto len=%d>' % len(val)
    print('  %-55s = %s' % (p.key, val[:150]))

# 3. Módulos instalados de localización, pagos y terceros/custom
sub('Módulos instalados (no Odoo S.A. o l10n_ar / payment / tax)')
mods = env['ir.module.module'].search([
    ('state', '=', 'installed'),
    '|', '|', '|',
    ('author', 'not ilike', 'Odoo S.A.'),
    ('name', 'ilike', 'l10n_ar'),
    ('name', 'ilike', 'payment_pro'),
    ('name', 'ilike', 'tax_settlement'),
], order='name')
for m in mods:
    print('  %-38s | %-15s | %s' % (m.name, m.latest_version or m.installed_version or '', m.author or ''))

# 4. Crons, automatizaciones y acciones de servidor relacionadas
sub('ir.cron relacionados (activos e inactivos)')
crons = env['ir.cron'].with_context(active_test=False).search([
    '|', '|',
    ('name', 'ilike', 'padron'),
    ('name', 'ilike', 'arba'),
    ('name', 'ilike', 'l10n_ar'),
], order='name')
for cr in crons:
    print('  [%s] %s | active=%s | interval=%s %s | nextcall=%s | model=%s' % (
        cr.id, cr.name, cr.active, cr.interval_number, cr.interval_type,
        cr.nextcall, cr.model_id.model if cr.model_id else False,
    ))

sub('base.automation y ir.actions.server (code) relacionados')
if 'base.automation' in env:
    autos = env['base.automation'].with_context(active_test=False).search([])
    for a in autos:
        print('  AUTO [%s] %s | active=%s | model=%s | trigger=%s' % (
            a.id, a.name, a.active, a.model_id.model if a.model_id else False, a.trigger,
        ))
srv_actions = env['ir.actions.server'].search([
    ('state', '=', 'code'),
    '|', '|',
    ('model_id.model', 'in', ['res.partner', 'account.payment', 'account.move', 'res.company.jurisdiction.padron', 'l10n_ar.partner.tax']),
    ('name', 'ilike', 'padron'),
    ('name', 'ilike', 'arba'),
])
for sa in srv_actions:
    if any(k in (sa.code or '').lower() for k in ('padron', 'arba', 'l10n_ar', 'partner.tax', 'withholding', 'aliquot')):
        print('  ACTION [%s] %s | model=%s' % (sa.id, sa.name, sa.model_id.model))
        print('    ' + (sa.code or '').replace('\n', '\n    '))

# 5. Código fuente real en ejecución (MRO completo)
h('CÓDIGO FUENTE EN EJECUCIÓN (MRO)')
safe(method_sources, 'res.company.jurisdiction.padron', [
    'check_state_id', 'descompress_file', 'find_file', 'find_aliquot', '_get_aliquot', '_get_parp_tmp_dir',
], only_custom=False)
safe(method_sources, 'account.fiscal.position', [
    '_l10n_ar_add_taxes', '_get_fpos_ranking_functions', '_get_fiscal_position',
], only_custom=False)
safe(method_sources, 'account.fiscal.position.l10n_ar_tax', [
    '_get_missing_taxes', '_get_tax_from_ws', '_ensure_tax', '_get_arba_data', '_get_padron_data', '_search_padron_file',
], only_custom=False)
safe(method_sources, 'account.payment', [
    '_compute_fiscal_position_id', '_compute_l10n_ar_withholding_line_ids', 'action_confirm', 'action_post',
], only_custom=False)
safe(method_sources, 'account.move', [
    '_compute_fiscal_position_id', '_l10n_ar_recompute_fiscal_position_taxes',
], only_custom=False)
safe(method_sources, 'account.move.line', [
    '_get_computed_taxes',
], only_custom=False)
safe(method_sources, 'sale.order.line', [
    '_compute_tax_id',
], only_custom=False)
safe(method_sources, 'l10n_ar.partner.tax', [
    '_check_tax_group_overlap',
], only_custom=False)
__EOF_AUDIT__
cat > ~/tmp/circuito_padron/scripts/02_impuestos_y_posiciones_fiscales.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 02 - Auditoría completa de impuestos (account.tax), posiciones fiscales y diarios
from collections import Counter

company = get_company()
h('02 - IMPUESTOS, POSICIONES FISCALES Y DIARIOS (%s)' % company.name)

# 1. Resumen general de account.tax
sub('Resumen de account.tax (active_test=False)')
all_taxes = env['account.tax'].with_context(active_test=False).search([
    ('company_id', '=', company.id),
], order='type_tax_use, id')
print('  Total impuestos en compañía: %d' % len(all_taxes))

by_use_group = Counter((t.type_tax_use, t.active, t.tax_group_id.name if t.tax_group_id else 'Sin Grupo') for t in all_taxes)
for (use, act, grp), cnt in sorted(by_use_group.items()):
    print('    uso=%-8s | active=%-5s | grupo=%-30s : %d' % (use, act, grp, cnt))

# 2. Impuestos relevantes: Retenciones, Percepciones, IIBB, ARBA, Jurisdicción AR
sub('Detalle de impuestos de Retención / Percepción / IIBB / Jurisdicción AR')
rel_taxes = all_taxes.filtered(lambda t: (
    t.type_tax_use == 'none'
    or (has_field('account.tax', 'l10n_ar_withholding_payment_type') and t.l10n_ar_withholding_payment_type)
    or (has_field('account.tax', 'l10n_ar_state_id') and t.l10n_ar_state_id)
    or (t.tax_group_id and getattr(t.tax_group_id, 'l10n_ar_tribute_afip_code', False))
    or any(k in (t.name or '').lower() for k in ('arba', 'iibb', 'perc', 'ret', 'bs', 'buenos aires', 'agip', 'sire', 'sicore'))
))
print('  Impuestos relevantes encontrados: %d' % len(rel_taxes))
for t in rel_taxes:
    tg = t.tax_group_id
    tg_info = '%s (id=%s, afip=%s)' % (
        tg.name, tg.id, getattr(tg, 'l10n_ar_tribute_afip_code', False)
    ) if tg else 'Sin Grupo'
    state = getattr(t, 'l10n_ar_state_id', False)
    state_info = '%s (cod=%s)' % (state.name, getattr(state, 'jurisdiction_code', '?')) if state else 'Sin Prov.'
    seq = getattr(t, 'l10n_ar_withholding_sequence_id', False)
    seq_info = '%s (id=%s)' % (seq.name, seq.id) if seq else 'SIN SECUENCIA'
    wtype = getattr(t, 'l10n_ar_withholding_payment_type', False)
    ttype = getattr(t, 'l10n_ar_tax_type', False)
    print('\n  [%d] %s | active=%s | use=%s | amount_type=%s | amount=%.4f' % (
        t.id, t.name, t.active, t.type_tax_use, t.amount_type, t.amount
    ))
    print('      grupo=%s | prov=%s | wth_pay_type=%s | l10n_ar_tax_type=%s | seq=%s' % (
        tg_info, state_info, wtype, ttype, seq_info
    ))
    if has_field('account.tax', 'l10n_ar_minimum_threshold'):
        print('      umbrales: min_tax=%s | min_base=%s | min_pay=%s | non_taxable=%s' % (
            getattr(t, 'l10n_ar_minimum_threshold', None),
            getattr(t, 'l10n_ar_base_minimum_threshold', None),
            getattr(t, 'l10n_ar_payment_minimum_threshold', None),
            getattr(t, 'l10n_ar_non_taxable_amount', None),
        ))
    for rep in t.invoice_repartition_line_ids:
        acc = rep.account_id
        tags = ', '.join(rep.tag_ids.mapped('name'))
        print('      rep(inv)  %-6s | cuenta=%s | tags=[%s]' % (
            rep.repartition_type, ('%s %s' % (acc.code, acc.name)) if acc else 'False', tags
        ))
    for rep in t.refund_repartition_line_ids:
        acc = rep.account_id
        tags = ', '.join(rep.tag_ids.mapped('name'))
        print('      rep(ref)  %-6s | cuenta=%s | tags=[%s]' % (
            rep.repartition_type, ('%s %s' % (acc.code, acc.name)) if acc else 'False', tags
        ))

# 3. Grupos de impuestos
sub('Grupos de Impuestos (account.tax.group) de la compañía o globales')
groups = env['account.tax.group'].search(['|', ('company_id', '=', company.id), ('company_id', '=', False)])
for g in groups:
    print('  [%3d] %-35s | cia=%s | afip_tribute=%s | vat_code=%s' % (
        g.id, g.name, g.company_id.id if g.company_id else 'Global',
        getattr(g, 'l10n_ar_tribute_afip_code', False),
        getattr(g, 'l10n_ar_vat_afip_code', False),
    ))

# 4. Posiciones Fiscales
sub('Posiciones Fiscales (account.fiscal.position, active_test=False)')
fpos_list = env['account.fiscal.position'].with_context(active_test=False).search([
    ('company_id', '=', company.id),
], order='sequence, id')
print('  Total posiciones fiscales: %d' % len(fpos_list))
for fp in fpos_list:
    resp = ', '.join(fp.l10n_ar_afip_responsibility_type_ids.mapped('name')) if has_field('account.fiscal.position', 'l10n_ar_afip_responsibility_type_ids') else 'N/A'
    states = ', '.join(fp.state_ids.mapped('name')) if fp.state_ids else 'Todas'
    print('\n  [%d] %s | active=%s | seq=%s | auto_apply=%s | vat_req=%s | country=%s' % (
        fp.id, fp.name, fp.active, fp.sequence, fp.auto_apply, fp.vat_required,
        fp.country_id.code if fp.country_id else 'Cualquiera',
    ))
    print('      estados=[%s] | resp_afip=[%s]' % (states, resp))
    if fp.tax_ids:
        print('      mapeo tax_ids (%d):' % len(fp.tax_ids))
        for m in fp.tax_ids[:15]:
            print('        %s -> %s' % (m.tax_src_id.name, m.tax_dest_id.name if m.tax_dest_id else 'QUITAR'))
    if has_field('account.fiscal.position', 'l10n_ar_tax_ids'):
        if fp.l10n_ar_tax_ids:
            print('      líneas l10n_ar_tax_ids (%d):' % len(fp.l10n_ar_tax_ids))
            for lt in fp.l10n_ar_tax_ids:
                dt = lt.default_tax_id
                dt_state = dt.l10n_ar_state_id.name if (dt and has_field('account.tax', 'l10n_ar_state_id') and dt.l10n_ar_state_id) else 'Sin Prov.'
                print('        - [%d] tax_type=%-11s | webservice=%-15s | default_tax=[%d] %s (%.2f%%, active=%s, use=%s, wth=%s, prov=%s, grp=%s)' % (
                    lt.id, lt.tax_type, lt.webservice or 'Manual/Fijo',
                    dt.id if dt else 0, dt.name if dt else 'NONE', dt.amount if dt else 0.0,
                    dt.active if dt else False, dt.type_tax_use if dt else '',
                    getattr(dt, 'l10n_ar_withholding_payment_type', False) if dt else False,
                    dt_state, dt.tax_group_id.name if (dt and dt.tax_group_id) else ''
                ))
        else:
            print('      líneas l10n_ar_tax_ids: (vacío)')

# 5. Diarios de pago y facturación
sub('Diarios de la compañía (bank/cash/sale/purchase)')
journals = env['account.journal'].with_context(active_test=False).search([
    ('company_id', '=', company.id),
    ('type', 'in', ['bank', 'cash', 'sale', 'purchase']),
], order='type, id')
for j in journals:
    extra = ''
    if j.type in ('sale', 'purchase'):
        extra = ' | use_docs=%s | pos_sys=%s | default_taxes=%s' % (
            getattr(j, 'l10n_latam_use_documents', None),
            getattr(j, 'l10n_ar_afip_pos_system', None),
            j.default_account_id.tax_ids.mapped('name') if j.default_account_id else []
        )
    print('  [%3d] %-8s | active=%-5s | %s%s' % (j.id, j.type, j.active, j.name, extra))
__EOF_AUDIT__
cat > ~/tmp/circuito_padron/scripts/03_padrones_y_contactos.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 03 - Inspección de res.company.jurisdiction.padron, l10n_ar.partner.tax y datos fiscales de res.partner
import base64
import io
import re
import zipfile
from collections import Counter

company = get_company()
h('03 - PADRONES CARGADOS, PARTNER TAXES Y PREPARACIÓN DE CONTACTOS (%s)' % company.name)

# 1. Registros en res.company.jurisdiction.padron
sub('Registros en res.company.jurisdiction.padron')
if 'res.company.jurisdiction.padron' in env:
    padrons = env['res.company.jurisdiction.padron'].search([], order='id')
    print('  Total padrones en BD: %d' % len(padrons))
    for p in padrons:
        jcode = getattr(p.state_id, 'jurisdiction_code', '?') if p.state_id else None
        raw = base64.b64decode(p.file_padron) if p.file_padron else b''
        print('\n  Padron ID=%d | cia=[%s] %s | state=[%s] %s (jcode=%s)' % (
            p.id, p.company_id.id, p.company_id.name,
            p.state_id.id if p.state_id else 0, p.state_id.name if p.state_id else False, jcode
        ))
        print('    filename=%r | desde=%s | hasta=%s | bytes=%s' % (
            p.filename, p.l10n_ar_padron_from_date, p.l10n_ar_padron_to_date, f'{len(raw):,}'
        ))
        if raw:
            buf = io.BytesIO(raw)
            if zipfile.is_zipfile(buf):
                buf.seek(0)
                with zipfile.ZipFile(buf, 'r') as zf:
                    print('    Contenido ZIP (%d entradas):' % len(zf.infolist()))
                    for info in zf.infolist():
                        print('      - %-45s | dir=%-5s | size=%s bytes' % (
                            info.filename, info.is_dir(), f'{info.file_size:,}'
                        ))
                        if not info.is_dir() and info.file_size > 0:
                            with zf.open(info.filename) as f:
                                for idx in range(3):
                                    line = f.readline().decode('latin1', errors='replace').rstrip('\r\n')
                                    if not line:
                                        break
                                    print('          muestra[%d]: %s' % (idx + 1, line[:140]))
            else:
                print('    Archivo NO es ZIP. Primeras 3 líneas:')
                text_head = raw[:1024].decode('latin1', errors='replace').splitlines()[:3]
                for idx, line in enumerate(text_head, 1):
                    print('      muestra[%d]: %s' % (idx, line[:140]))
else:
    print('  [!] El modelo res.company.jurisdiction.padron NO está disponible.')

# 2. Registros existentes en l10n_ar.partner.tax
sub('Registros existentes en l10n_ar.partner.tax')
if 'l10n_ar.partner.tax' in env:
    all_pt = env['l10n_ar.partner.tax'].search([('company_id', '=', company.id)])
    print('  Total en compañía [%s]: %d' % (company.id, len(all_pt)))
    all_pt_global = env['l10n_ar.partner.tax'].search([])
    if len(all_pt_global) != len(all_pt):
        print('  Total en TODAS las compañías: %d' % len(all_pt_global))

    by_tax = Counter()
    by_period = Counter()
    for pt in all_pt:
        t = pt.tax_id
        tkey = '[%d] %s (use=%s, wth=%s)' % (
            t.id, t.name, t.type_tax_use, getattr(t, 'l10n_ar_withholding_payment_type', False)
        ) if t else 'Sin impuesto'
        by_tax[tkey] += 1
        by_period[(str(pt.from_date), str(pt.to_date))] += 1

    print('  Desglose por impuesto:')
    for tkey, cnt in by_tax.most_common(25):
        print('    %-70s : %d' % (tkey, cnt))
    print('  Desglose por vigencia (from_date, to_date):')
    for per, cnt in by_period.most_common(15):
        print('    %s : %d' % (per, cnt))
    print('  Muestra de hasta 10 registros:')
    for pt in all_pt[:10]:
        print('    - [%d] partner=[%d] %s (CUIT=%s) | tax=%s | %s..%s | ref=%r' % (
            pt.id, pt.partner_id.id, (pt.partner_id.name or '')[:30], pt.partner_id.vat,
            pt.tax_id.name if pt.tax_id else False, pt.from_date, pt.to_date, pt.ref
        ))
else:
    print('  [!] Modelo l10n_ar.partner.tax NO disponible.')

# 3. Auditoría de contactos comerciales (res.partner)
sub('Preparación de contactos comerciales (res.partner)')
partners = env['res.partner'].search([('is_company', '=', True)])
print('  Total empresas (is_company=True): %d' % len(partners))

# También verificar contactos individuales con parent_id=False que puedan operar como cliente/proveedor
indiv = env['res.partner'].search([('is_company', '=', False), ('parent_id', '=', False), '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)])
print('  Contactos individuales top-level con rank > 0: %d' % len(indiv))

stats = Counter()
combos_sup = Counter()
combos_cus = Counter()
manual_fp_count = 0

for p in partners:
    cuit_digits = re.sub(r'\D', '', p.vat or '')
    has_cuit = len(cuit_digits) == 11
    is_cus = p.customer_rank > 0
    is_sup = p.supplier_rank > 0
    if has_cuit:
        stats['con_cuit_11_dig'] += 1
    else:
        stats['sin_cuit_11_dig'] += 1
    if is_cus:
        stats['customer_rank>0'] += 1
    if is_sup:
        stats['supplier_rank>0'] += 1
    if is_cus and is_sup:
        stats['ambos_cus_y_sup'] += 1
    if p.with_company(company).property_account_position_id:
        manual_fp_count += 1

    key = (
        p.country_id.code if p.country_id else 'SIN_PAIS',
        p.state_id.name if p.state_id else 'SIN_PROV',
        p.l10n_ar_afip_responsibility_type_id.name if has_field('res.partner', 'l10n_ar_afip_responsibility_type_id') and p.l10n_ar_afip_responsibility_type_id else 'SIN_RESP_AFIP',
        'CUIT_OK' if has_cuit else 'SIN_CUIT',
    )
    if is_sup:
        combos_sup[key] += 1
    if is_cus:
        combos_cus[key] += 1

for k, v in sorted(stats.items()):
    print('    %-25s : %d' % (k, v))
print('    %-25s : %d' % ('con_pos_fiscal_manual', manual_fp_count))

print('\n  Top 15 perfiles fiscales de PROVEEDORES (supplier_rank > 0):')
for k, v in combos_sup.most_common(15):
    print('    %4d | %s' % (v, ' | '.join(k)))

print('\n  Top 15 perfiles fiscales de CLIENTES (customer_rank > 0):')
for k, v in combos_cus.most_common(15):
    print('    %4d | %s' % (v, ' | '.join(k)))
__EOF_AUDIT__
cat > ~/tmp/circuito_padron/scripts/04_simular_circuito_completo.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 04 - Simulación controlada (ROLLBACK) del circuito completo de padrón, posición fiscal, pago y factura
import base64
import io
import os
import re
import shutil
import zipfile
from datetime import date
from odoo import fields

company = get_company()
h('04 - SIMULACIÓN DEL CIRCUITO COMPLETO (100%% ROLLBACK / SIN COMMIT) (%s)' % company.name)


class _EndSavepoint(Exception):
    pass


def run_isolated(title, fn):
    """Ejecuta fn dentro de un SAVEPOINT y siempre lo revierte al finalizar."""
    sub(title)
    try:
        with env.cr.savepoint():
            safe(fn)
            raise _EndSavepoint()
    except _EndSavepoint:
        pass


# 1. Ubicar padrón cargado (prioriza Buenos Aires / ARBA)
ba_state = env.ref('base.state_ar_b', raise_if_not_found=False)
padron = env['res.company.jurisdiction.padron'].search([
    ('company_id', '=', company.id),
    ('state_id', '=', ba_state.id if ba_state else False),
], limit=1)
if not padron:
    padron = env['res.company.jurisdiction.padron'].search([('company_id', '=', company.id)], limit=1)

if not padron:
    print('[!] No hay ningún padrón cargado en res.company.jurisdiction.padron para %s.' % company.name)
    test_date = fields.Date.today()
else:
    print('[*] Padrón encontrado: ID=%d | state=%s | %s..%s | file=%r' % (
        padron.id, padron.state_id.name, padron.l10n_ar_padron_from_date,
        padron.l10n_ar_padron_to_date, padron.filename
    ))
    test_date = padron.l10n_ar_padron_from_date or fields.Date.today()

# 2. Cruzar en memoria contra el ZIP del padrón (si existe) para elegir casos testigo reales
partners = env['res.partner'].search([('is_company', '=', True), ('vat', '!=', False)])
cuit_to_partner = {}
for p in partners:
    c = re.sub(r'\D', '', p.vat or '')
    if len(c) == 11 and c not in cuit_to_partner:
        cuit_to_partner[c] = p

ret_rates = {}
per_rates = {}
if padron and padron.file_padron:
    raw = base64.b64decode(padron.file_padron)
    buf = io.BytesIO(raw)
    if zipfile.is_zipfile(buf):
        buf.seek(0)
        with zipfile.ZipFile(buf, 'r') as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size == 0:
                    continue
                low = info.filename.lower()
                target = ret_rates if 'ret' in low else (per_rates if 'per' in low else None)
                if target is None:
                    continue
                with zf.open(info.filename) as f:
                    for line_b in f:
                        parts = line_b.decode('latin1', errors='replace').rstrip('\r\n').split(';')
                        if len(parts) >= 9:
                            cuit_line = parts[4].strip()
                            if cuit_line in cuit_to_partner:
                                try:
                                    target[cuit_line] = float(parts[8].strip().replace(',', '.'))
                                except ValueError:
                                    pass

print('[*] En el ZIP del padrón matchearon con contactos de BD: Ret=%d, Per=%d' % (
    len(ret_rates), len(per_rates)
))

# Resumen rápido de contactos no-proveedores y comprobantes (explica customer_rank=0)
non_sup = partners.filtered(lambda p: p.supplier_rank == 0)
print('[*] Empresas totales=%d | supplier_rank>0=%d | supplier_rank==0=%d' % (
    len(partners), len(partners) - len(non_sup), len(non_sup)
))
if has_field('res.partner', 'l10n_ar_afip_responsibility_type_id'):
    resp_counts = {}
    for p in non_sup:
        rn = p.l10n_ar_afip_responsibility_type_id.name if p.l10n_ar_afip_responsibility_type_id else 'SIN_RESP_AFIP'
        resp_counts[rn] = resp_counts.get(rn, 0) + 1
    print('[*] Desglose resp_afip en supplier_rank==0: %s' % resp_counts)
for mt in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
    cnt = env['account.move'].search_count([('company_id', '=', company.id), ('move_type', '=', mt)])
    print('[*] account.move (%s) en %s: %d' % (mt, company.name, cnt))
if 'sale.order' in env:
    print('[*] sale.order en %s: %d' % (company.name, env['sale.order'].search_count([('company_id', '=', company.id)])))

# Seleccionar casos testigo reales de la BD
samples = []

def pick_partner(label, pred):
    for c, p in cuit_to_partner.items():
        if pred(c, p) and p not in [s[1] for s in samples]:
            samples.append((label, p, ret_rates.get(c), per_rates.get(c)))
            return

pick_partner('PROV_RET_MENOR_2_5', lambda c, p: p.supplier_rank > 0 and 0.0 < ret_rates.get(c, 0.0) < 2.50)
pick_partner('PROV_RET_MAYOR_IGUAL_2_5', lambda c, p: p.supplier_rank > 0 and ret_rates.get(c, 0.0) >= 2.50)
pick_partner('PROV_RESP_INSC_RET', lambda c, p: p.supplier_rank > 0 and has_field('res.partner', 'l10n_ar_afip_responsibility_type_id') and p.l10n_ar_afip_responsibility_type_id and 'Inscripto' in (p.l10n_ar_afip_responsibility_type_id.name or '') and c in ret_rates)
pick_partner('PROV_SOLO_EN_PER_NO_RET', lambda c, p: p.supplier_rank > 0 and c in per_rates and c not in ret_rates)
pick_partner('CLI_CON_PER_GT_0', lambda c, p: p.customer_rank > 0 and per_rates.get(c, 0.0) > 0.0)
if not any(s[0] == 'CLI_CON_PER_GT_0' for s in samples):
    pick_partner('NO_PROV_PER_GT_0', lambda c, p: p.supplier_rank == 0 and per_rates.get(c, 0.0) > 0.0)
pick_partner('NO_EN_PADRON', lambda c, p: (p.supplier_rank > 0 or p.customer_rank > 0) and c not in ret_rates and c not in per_rates)

if not samples and partners:
    for p in partners[:3]:
        c = re.sub(r'\D', '', p.vat or '')
        samples.append(('MUESTRA_GENERAL', p, ret_rates.get(c), per_rates.get(c)))

print('\n[*] Casos testigo seleccionados (%d):' % len(samples))
for lbl, p, rr, pr in samples:
    print('    - %-25s | [%d] %-35s | CUIT=%s | sup=%d | cus=%d | country=%s | state=%s | resp=%s | ZIP(ret=%s, per=%s)' % (
        lbl, p.id, (p.name or '')[:35], p.vat, p.supplier_rank, p.customer_rank,
        p.country_id.code if p.country_id else False,
        p.state_id.name if p.state_id else False,
        p.l10n_ar_afip_responsibility_type_id.name if has_field('res.partner', 'l10n_ar_afip_responsibility_type_id') and p.l10n_ar_afip_responsibility_type_id else False,
        rr, pr
    ))

# 3. Probar lectura directa de res.company.jurisdiction.padron._get_aliquot
if padron:
    tmp_dir_expected = padron._get_parp_tmp_dir()
    existed_before = os.path.exists(tmp_dir_expected)

    def test_padron_direct():
        print('  tmp_dir esperado: %s (existía antes: %s)' % (tmp_dir_expected, existed_before))
        for lbl, p, rr, pr in samples:
            res = safe(padron._get_aliquot, p)
            print('  [%s] partner=[%d] vat=%s -> _get_aliquot()=%r (esperado ZIP: ret=%s, per=%s)' % (
                lbl, p.id, p.vat, res, rr, pr
            ))
        if os.path.exists(tmp_dir_expected):
            print('\n  Árbol extraído en %s:' % tmp_dir_expected)
            for root, dirs, files in os.walk(tmp_dir_expected):
                for fn in files:
                    print('    %s' % os.path.join(root, fn))
        else:
            print('\n  [!] tmp_dir NO existe después de llamar a _get_aliquot.')
        print('  find_file(tmp_dir, "Per") = %r' % safe(padron.find_file, tmp_dir_expected, 'Per'))
        print('  find_file(tmp_dir, "Ret") = %r' % safe(padron.find_file, tmp_dir_expected, 'Ret'))

    run_isolated('A. Prueba directa de padron._get_aliquot() y estructura /tmp', test_padron_direct)

# 4. Probar auto-detección de Posición Fiscal (Pagos vs Ventas)
def test_fpos_detection():
    FP = env['account.fiscal.position'].with_company(company)
    for lbl, p, rr, pr in samples:
        fp_pay = FP.with_context(l10n_ar_withholding=True, active_test=True)._get_fiscal_position(p)
        fp_sale = FP.with_context(active_test=True)._get_fiscal_position(p)
        print('  [%s] [%d] %s:' % (lbl, p.id, (p.name or '')[:35]))
        print('      Pago (l10n_ar_withholding=True) -> %s' % (('[%d] %s' % (fp_pay.id, fp_pay.name)) if fp_pay else 'NINGUNA (False)'))
        print('      Venta/Factura (sin flag wth)    -> %s' % (('[%d] %s' % (fp_sale.id, fp_sale.name)) if fp_sale else 'NINGUNA (False)'))

run_isolated('B. Auto-detección de Posición Fiscal en Pagos vs Ventas', test_fpos_detection)

# 5. Simular pagos (Proveedor vs Cliente) y Factura de Venta
bank_journal = env['account.journal'].search([
    ('company_id', '=', company.id),
    ('type', 'in', ['bank', 'cash']),
], limit=1)
sale_journal = env['account.journal'].search([
    ('company_id', '=', company.id),
    ('type', '=', 'sale'),
], limit=1)
sale_product = env['product.product'].search([('sale_ok', '=', True)], limit=1)

for lbl, p, rr, pr in samples:
    def test_payment_and_invoice(partner=p, label=lbl):
        print('  Partner: [%d] %s (CUIT=%s)' % (partner.id, partner.name, partner.vat))
        if bank_journal:
            pml_out = bank_journal.outbound_payment_method_line_ids[:1]
            pay_sup = env['account.payment'].with_company(company).new({
                'company_id': company.id,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': partner.id,
                'journal_id': bank_journal.id,
                'payment_method_line_id': pml_out.id if pml_out else False,
                'date': test_date,
                'amount': 10000.0,
            })
            safe(pay_sup._compute_fiscal_position_id)
            safe(pay_sup._compute_l10n_ar_withholding_line_ids)
            fp_name = pay_sup.l10n_ar_fiscal_position_id.name if has_field('account.payment', 'l10n_ar_fiscal_position_id') and pay_sup.l10n_ar_fiscal_position_id else 'False'
            print('  -> Pago PROVEEDOR (outbound/supplier): FP=%s | Líneas retención=%d' % (
                fp_name, len(pay_sup.l10n_ar_withholding_line_ids) if has_field('account.payment', 'l10n_ar_withholding_line_ids') else -1
            ))
            if has_field('account.payment', 'l10n_ar_withholding_line_ids'):
                for wl in pay_sup.l10n_ar_withholding_line_ids:
                    print('       * tax=[%s] %s (%.2f%%) | base=%.2f | amount=%.2f | ref=%r' % (
                        wl.tax_id.id, wl.tax_id.name, wl.tax_id.amount, wl.base_amount, wl.amount, wl.ref
                    ))

            pml_in = bank_journal.inbound_payment_method_line_ids[:1]
            pay_cus = env['account.payment'].with_company(company).new({
                'company_id': company.id,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner.id,
                'journal_id': bank_journal.id,
                'payment_method_line_id': pml_in.id if pml_in else False,
                'date': test_date,
                'amount': 10000.0,
            })
            safe(pay_cus._compute_fiscal_position_id)
            safe(pay_cus._compute_l10n_ar_withholding_line_ids)
            fp_cus = pay_cus.l10n_ar_fiscal_position_id.name if has_field('account.payment', 'l10n_ar_fiscal_position_id') and pay_cus.l10n_ar_fiscal_position_id else 'False'
            print('  -> Cobro CLIENTE (inbound/customer):   FP=%s | Líneas retención=%d' % (
                fp_cus, len(pay_cus.l10n_ar_withholding_line_ids) if has_field('account.payment', 'l10n_ar_withholding_line_ids') else -1
            ))

        if sale_journal and sale_product:
            inv = env['account.move'].with_company(company).new({
                'company_id': company.id,
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'journal_id': sale_journal.id,
                'invoice_date': test_date,
                'date': test_date,
                'invoice_line_ids': [(0, 0, {
                    'product_id': sale_product.id,
                    'quantity': 1.0,
                    'price_unit': 10000.0,
                })],
            })
            safe(inv._compute_fiscal_position_id)
            line = inv.invoice_line_ids[:1]
            computed_taxes = safe(line._get_computed_taxes) if line else None
            print('  -> Factura VENTA (out_invoice): FP=%s | _get_computed_taxes=%s' % (
                inv.fiscal_position_id.name if inv.fiscal_position_id else 'False',
                [(t.id, t.name, t.amount) for t in computed_taxes] if computed_taxes else []
            ))

        # Verificar qué habría quedado en l10n_ar.partner.tax dentro de este savepoint antes de revertir
        new_pt = env['l10n_ar.partner.tax'].search([('partner_id', '=', partner.id), ('company_id', '=', company.id)])
        if new_pt:
            print('  -> l10n_ar.partner.tax en savepoint (%d):' % len(new_pt))
            for pt in new_pt:
                print('       * [%s] %s (%s..%s) ref=%r' % (
                    pt.tax_id.id, pt.tax_id.name, pt.from_date, pt.to_date, pt.ref
                ))

    run_isolated('C. Simulación Pago Proveedor / Cobro Cliente / Factura Venta - %s' % lbl, test_payment_and_invoice)

# 6. Simulación controlada CON Posición Fiscal RI + webservice='padron' en SAVEPOINT
def test_with_temp_fp():
    ar_country = env.ref('base.ar', raise_if_not_found=False)
    ri_resp = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '1')], limit=1)
    ba_tax_state = ba_state.id if ba_state else False
    wth_0 = env['account.tax'].with_company(company).with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('l10n_ar_withholding_payment_type', '=', 'supplier'),
        ('l10n_ar_state_id', '=', ba_tax_state),
        ('amount', '=', 0.0),
    ], limit=1)
    per_0 = env['account.tax'].with_company(company).with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('type_tax_use', '=', 'sale'),
        ('l10n_ar_state_id', '=', ba_tax_state),
        ('amount', '=', 0.0),
    ], limit=1)
    print('  Base wth_0=%s | per_0=%s (active=%s) | ri_resp=%s' % (
        wth_0.id if wth_0 else None,
        per_0.id if per_0 else None,
        per_0.active if per_0 else None,
        ri_resp.name if ri_resp else None,
    ))
    if not (ar_country and ri_resp and wth_0 and per_0):
        print('  [!] Faltan registros base para armar la FP temporal.')
        return
    if not per_0.active:
        per_0.active = True
    temp_fp = env['account.fiscal.position'].with_company(company).create({
        'name': 'TEST TEMP RI ARBA PADRON',
        'company_id': company.id,
        'auto_apply': True,
        'country_id': ar_country.id,
        'l10n_ar_afip_responsibility_type_ids': [(6, 0, [ri_resp.id])],
        'l10n_ar_tax_ids': [
            (0, 0, {'tax_type': 'withholding', 'default_tax_id': wth_0.id, 'webservice': 'padron'}),
            (0, 0, {'tax_type': 'perception', 'default_tax_id': per_0.id, 'webservice': 'padron'}),
        ],
    })
    print('  FP temporal creada en savepoint: id=%d' % temp_fp.id)
    if samples:
        lbl, p, rr, pr = samples[0]
        if not p.l10n_ar_afip_responsibility_type_id:
            p.l10n_ar_afip_responsibility_type_id = ri_resp
        FP = env['account.fiscal.position'].with_company(company)
        fp_pay = FP.with_context(l10n_ar_withholding=True, active_test=True)._get_fiscal_position(p)
        fp_sale = FP.with_context(active_test=True)._get_fiscal_position(p)
        print('  Sample=%s (%s) -> _get_fiscal_position(pay)=%s | (sale)=%s' % (
            lbl, p.name, fp_pay.name if fp_pay else False, fp_sale.name if fp_sale else False
        ))
        if bank_journal:
            pml_out = bank_journal.outbound_payment_method_line_ids[:1]
            pay_sup = env['account.payment'].with_company(company).new({
                'company_id': company.id,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': p.id,
                'journal_id': bank_journal.id,
                'payment_method_line_id': pml_out.id if pml_out else False,
                'date': test_date,
                'amount': 10000.0,
            })
            safe(pay_sup._compute_fiscal_position_id)
            safe(pay_sup._compute_l10n_ar_withholding_line_ids)
            print('  Con FP temporal -> Pago PROV wth_lines=%s' % [
                (wl.tax_id.name, wl.tax_id.amount, wl.amount) for wl in pay_sup.l10n_ar_withholding_line_ids
            ])
        if sale_journal and sale_product:
            inv = env['account.move'].with_company(company).new({
                'company_id': company.id,
                'move_type': 'out_invoice',
                'partner_id': p.id,
                'journal_id': sale_journal.id,
                'invoice_date': test_date,
                'date': test_date,
                'invoice_line_ids': [(0, 0, {
                    'product_id': sale_product.id,
                    'quantity': 1.0,
                    'price_unit': 10000.0,
                })],
            })
            safe(inv._compute_fiscal_position_id)
            computed = safe(inv.invoice_line_ids[:1]._get_computed_taxes)
            print('  Con FP temporal -> Factura VENTA computed_taxes=%s' % (
                [(t.id, t.name, t.amount) for t in computed] if computed else []
            ))

run_isolated('D. Simulación en SAVEPOINT CON Fiscal Position RI + webservice="padron"', test_with_temp_fp)

if padron and not existed_before and os.path.exists(tmp_dir_expected):
    shutil.rmtree(tmp_dir_expected, ignore_errors=True)
    print('\n[*] Limpieza de %s completada.' % tmp_dir_expected)

env.cr.rollback()
print('\n[OK] Simulación finalizada con env.cr.rollback() completo. Base de datos intacta.')
__EOF_AUDIT__
chmod +x ~/tmp/circuito_padron/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/circuito_padron:'; ls -R ~/tmp/circuito_padron | head -50
