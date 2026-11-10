#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/RR-8
mkdir -p ~/tmp/RR-8/scripts && cd ~/tmp/RR-8
cat > ~/tmp/RR-8/run_all.sh <<'__EOF_AUDIT__'
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
cat > ~/tmp/RR-8/scripts/_lib.py <<'__EOF_AUDIT__'
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
DRY_RUN = os.environ.get('DRY_RUN', '1') == '1'
CHECK_SEARCH = os.environ.get('CHECK_SEARCH', '')     # filtro opcional por número de cheque o partner


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
cat > ~/tmp/RR-8/scripts/01_modulos_y_modelos.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 01 - Módulos instalados y modelos de cheques
company = get_company()
h('01 - MÓDULOS INSTALADOS Y MODELOS DE CHEQUES (%s)' % company.name)

sub('Módulos relacionados a cheques y localización argentina')
modules = env['ir.module.module'].search([
    ('state', '=', 'installed'),
    '|', '|', '|',
    ('name', 'ilike', 'check'),
    ('name', 'ilike', 'l10n_latam'),
    ('name', 'ilike', 'l10n_ar'),
    ('author', 'not ilike', 'Odoo S.A.')
])
for m in sorted(modules, key=lambda x: x.name):
    custom_tag = '[CUSTOM/TERCERO]' if 'Odoo S.A.' not in (m.author or '') else '[OFICIAL]'
    print('  %-35s %-12s %-20s %s' % (m.name, m.installed_version or '', custom_tag, (m.author or '')[:30]))

sub('Modelos de cheques detectados en el sistema')
candidates = [
    'account.payment',
    'account.check',
    'account.third.party.checks',
    'l10n_latam.check',
    'account.check.operation',
    'account.payment.register',
    'account.move',
    'account.move.line'
]
for model_name in candidates:
    exists = model_name in env
    status = 'PRESENTE' if exists else 'NO EXISTE'
    print('  %-30s: %s' % (model_name, status))
    if exists:
        model = env[model_name]
        check_fields = [f for f in sorted(model._fields) if any(k in f.lower() for k in ('check', 'rechaz', 'reject', 'estado', 'third_party'))]
        if check_fields:
            print('    Campos relevantes: %s' % ', '.join(check_fields))
        for state_fname in ('state', 'check_state', 'l10n_latam_check_state', 'status'):
            if state_fname in model._fields:
                field = model._fields[state_fname]
                sel = getattr(field, 'selection', None)
                print('    Selección de %s: %s' % (state_fname, sel))
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/02_reportes_y_menus.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 02 - Reportes, menús, acciones de ventana y vistas de cheques
company = get_company()
h('02 - REPORTES, MENÚS Y ACCIONES DE CHEQUES (%s)' % company.name)

sub('Menús relacionados a cheques')
menus = env['ir.ui.menu'].search([
    '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('complete_name', 'ilike', 'cheque')
])
for m in menus:
    print('  ID=%-6s Menú: %-45s Acción: %s' % (m.id, m.complete_name, m.action.display_name if m.action else 'Sin acción'))

sub('Acciones de ventana (ir.actions.act_window) sobre cheques')
actions = env['ir.actions.act_window'].search([
    '|', '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('res_model', '=', 'account.check'),
    ('domain', 'ilike', 'check')
])
for a in actions:
    print('\n  Acción ID=%s: %s (Modelo: %s)' % (a.id, a.name, a.res_model))
    print('    Dominio: %s' % a.domain)
    print('    Contexto: %s' % a.context)
    print('    Modos de vista: %s' % a.view_mode)

if 'account.report' in env:
    sub('Reportes contables dinámicos (account.report)')
    acc_reports = env['account.report'].search([
        '|', '|',
        ('name', 'ilike', 'cheque'),
        ('name', 'ilike', 'check'),
        ('name', 'ilike', 'tercero')
    ])
    for rep in acc_reports:
        print('\n  Reporte ID=%s: %s (Código: %s)' % (rep.id, rep.name, getattr(rep, 'code', '')))
        if has_field('account.report', 'custom_handler_model_id') and rep.custom_handler_model_id:
            print('    Custom handler model: %s' % rep.custom_handler_model_id.model)
        if has_field('account.report', 'filter_unreconciled'):
            print('    Filtro no conciliados: %s' % rep.filter_unreconciled)
        
        lines = env['account.report.line'].search([('report_id', '=', rep.id)])
        print('    Líneas del reporte (%d):' % len(lines))
        for line in lines:
            print('      - Línea ID=%s: %-35s (code=%s)' % (line.id, line.name, line.code or ''))
            exprs = env['account.report.expression'].search([('report_line_id', '=', line.id)])
            for exp in exprs:
                print('          Expr: %-15s engine=%-12s formula=%s' % (exp.label, exp.engine, exp.formula))

sub('Reportes impresos / QWeb (ir.actions.report)')
qweb_reports = env['ir.actions.report'].search([
    '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('model', 'in', ['account.check', 'account.payment'])
])
for r in qweb_reports:
    print('  ID=%-6s Nombre: %-35s Modelo: %-20s Tipo: %s (report_name: %s)' % (
        r.id, r.name, r.model, r.report_type, r.report_name
    ))
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/03_cuentas_y_diarios.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 03 - Diarios, cuentas contables de cheques y saldos en el mayor
company = get_company()
h('03 - DIARIOS, CUENTAS CONTABLES Y SALDOS DE CHEQUES (%s)' % company.name)

sub('Diarios contables de cheques')
journals = env['account.journal'].with_company(company).search([
    '|', '|',
    ('type', 'in', ['bank', 'cash']),
    ('name', 'ilike', 'cheque'),
    ('code', 'ilike', 'ch')
])
for j in journals:
    def_acc = j.default_account_id.display_name if hasattr(j, 'default_account_id') and j.default_account_id else 'N/A'
    pmls = []
    if hasattr(j, 'inbound_payment_method_line_ids'):
        pmls = [line.name for line in j.inbound_payment_method_line_ids]
    print('  Diario: %-30s (code=%-6s, tipo=%-6s) Cuenta def: %s' % (j.name, j.code, j.type, def_acc))
    if pmls:
        print('    Métodos entrantes: %s' % ', '.join(pmls))

sub('Cuentas contables relacionadas a cheques (Valores a depositar / Rechazados)')
accounts = env['account.account'].with_company(company).search([
    '|', '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'valor'),
    ('name', 'ilike', 'depositar'),
    ('name', 'ilike', 'rechaz')
])
for acc in accounts:
    # Saldo contable general en account.move.line
    lines = env['account.move.line'].with_company(company).search([
        ('account_id', '=', acc.id),
        ('parent_state', '=', 'posted')
    ])
    debit = sum(lines.mapped('debit'))
    credit = sum(lines.mapped('credit'))
    balance = debit - credit
    reconciled = acc.reconcile if hasattr(acc, 'reconcile') else 'N/A'
    acc_type = acc.account_type if hasattr(acc, 'account_type') else (acc.user_type_id.name if hasattr(acc, 'user_type_id') else '')
    print('  Cuenta: [%s] %-35s Tipo=%-20s Conciliable=%s' % (acc.code, acc.name, acc_type, reconciled))
    print('    Movimientos posted: %d | Debe: %.2f | Haber: %.2f | Saldo (Mayor): %.2f' % (
        len(lines), debit, credit, balance
    ))

sub('Overrides en métodos de pago / cheques (MRO)')
if 'account.payment' in env:
    methods_to_check = ['action_post', 'action_cancel', '_seek_for_lines', '_get_valid_liquidity_accounts']
    if has_field('account.payment', 'action_reject'):
        methods_to_check.append('action_reject')
    method_sources('account.payment', methods_to_check)

if 'account.check' in env:
    methods_to_check = ['action_reject', 'action_holding', 'action_deposited']
    methods_to_check = [m for m in methods_to_check if hasattr(env['account.check'], m)]
    if methods_to_check:
        method_sources('account.check', methods_to_check)
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/04_cheques_rechazados_vs_mayor.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 04 - Inspección de cheques rechazados, apuntes contables y comparación con el mayor
company = get_company()
h('04 - CHEQUES RECHAZADOS VS APUNTES CONTABLES Y MAYOR (%s)' % company.name)

# 1. Caso modelo account.check (Adhoc / OCA)
if 'account.check' in env:
    sub('Inspección en modelo account.check')
    checks = env['account.check'].with_company(company).search([], order='id desc', limit=20)
    print('Últimos %d cheques en account.check:' % len(checks))
    for chk in checks:
        print('  ID=%-6s Número=%-15s Estado=%-12s Importe=%-10.2f Fecha=%s Partner=%s' % (
            chk.id, getattr(chk, 'number', chk.name), getattr(chk, 'state', ''),
            chk.amount, getattr(chk, 'payment_date', getattr(chk, 'issue_date', '')),
            chk.partner_id.display_name if chk.partner_id else ''
        ))
    
    sub('Cheques rechazados en account.check')
    rej_checks = env['account.check'].with_company(company).search([
        ('state', '=', 'rejected')
    ], order='id desc', limit=10)
    if not rej_checks:
        print('  No se encontraron cheques con state = "rejected"')
    for chk in rej_checks:
        print('\n  >> CHEQUE RECHAZADO ID=%s Núm=%s Importe=%.2f' % (chk.id, getattr(chk, 'number', chk.name), chk.amount))
        dump(chk, names=['state', 'issue_date', 'payment_date', 'partner_id', 'journal_id', 'company_id'])
        if hasattr(chk, 'operation_ids'):
            print('    Operaciones:')
            for op in chk.operation_ids:
                print('      - Op ID=%s tipo=%s fecha=%s asiento=%s' % (
                    op.id, getattr(op, 'operation', getattr(op, 'type', '')),
                    getattr(op, 'date', ''),
                    op.origin_move_id.name if hasattr(op, 'origin_move_id') and op.origin_move_id else ''
                ))

# 2. Caso modelo account.payment (Estándar Odoo Enterprise l10n_latam_check)
if 'account.payment' in env:
    sub('Inspección en account.payment (Cheques de terceros)')
    # Buscar líneas de métodos de pago de cheques de terceros
    domain_pay = [
        ('company_id', '=', company.id),
        '|', '|', '|',
        ('payment_method_line_id.code', 'ilike', 'check'),
        ('payment_method_line_id.code', 'ilike', 'third_party'),
        ('check_number', '!=', False) if has_field('account.payment', 'check_number') else ('id', '>', 0),
        ('l10n_latam_check_number', '!=', False) if has_field('account.payment', 'l10n_latam_check_number') else ('id', '>', 0)
    ]
    # Filtrar solo pagos de clientes o entrantes
    payments = env['account.payment'].search(domain_pay, order='date desc, id desc', limit=20)
    print('Últimos %d pagos de cheques encontrados:' % len(payments))
    for p in payments:
        chk_num = getattr(p, 'check_number', getattr(p, 'l10n_latam_check_number', 'S/N'))
        chk_state = getattr(p, 'check_state', getattr(p, 'l10n_latam_check_state', getattr(p, 'state', '')))
        is_matched = getattr(p, 'is_matched', 'N/A')
        print('  ID=%-6s Pago=%-16s Cheque=%-12s Estado=%-12s Matched=%-5s Imp=%-10.2f Fecha=%s Partner=%s' % (
            p.id, p.name, chk_num, chk_state, str(is_matched), p.amount, p.date,
            p.partner_id.display_name if p.partner_id else ''
        ))

    sub('Detalle de los primeros 5 pagos/cheques y sus apuntes contables (Mayor)')
    for p in payments[:5]:
        chk_num = getattr(p, 'check_number', getattr(p, 'l10n_latam_check_number', 'S/N'))
        chk_state = getattr(p, 'check_state', getattr(p, 'l10n_latam_check_state', getattr(p, 'state', '')))
        print('\n  -- Pago ID=%s | Ref=%s | Cheque=%s | Estado=%s | Fecha=%s' % (
            p.id, p.name, chk_num, chk_state, p.date
        ))
        dump(p, prefixes=['check', 'l10n_latam_check', 'is_'], names=['state', 'journal_id', 'destination_account_id'])
        
        move = p.move_id
        if move:
            print('    Asiento contable: %s (id=%s, state=%s, date=%s)' % (move.name, move.id, move.state, move.date))
            for line in move.line_ids:
                matching = getattr(line, 'matching_number', '') or (line.reconciled and 'Conciliado') or 'No'
                print('      Línea ID=%-6s Cuenta=[%s] %-25s Debe=%-9.2f Haber=%-9.2f Match=%s' % (
                    line.id, line.account_id.code, line.account_id.name[:25],
                    line.debit, line.credit, matching
                ))
                # Ver si esta línea fue conciliada con un asiento de rechazo o depósito
                if line.matched_debit_ids or line.matched_credit_ids:
                    for pr in line.matched_debit_ids:
                        contra = pr.debit_move_id
                        print('        -> Conciliada con débito: Asiento=%s Cuenta=%s Imp=%.2f Fecha=%s' % (
                            contra.move_id.name, contra.account_id.code, pr.amount, contra.date
                        ))
                    for pr in line.matched_credit_ids:
                        contra = pr.credit_move_id
                        print('        -> Conciliada con crédito: Asiento=%s Cuenta=%s Imp=%.2f Fecha=%s' % (
                            contra.move_id.name, contra.account_id.code, pr.amount, contra.date
                        ))
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/05_simulacion_reporte.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 05 - Simulación de dominios de reportes vs cheques rechazados
company = get_company()
h('05 - SIMULACIÓN DE REPORTES VS CHEQUES RECHAZADOS (%s)' % company.name)

sub('1. Evaluación de acciones de ventana de cheques')
actions = env['ir.actions.act_window'].search([
    '|', '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('res_model', '=', 'account.check'),
    ('domain', 'ilike', 'check')
])

for act in actions:
    print('\nAnalizando Acción: %s (ID=%s, Modelo=%s)' % (act.name, act.id, act.res_model))
    print('  Dominio configurado: %s' % act.domain)
    model = env[act.res_model].with_company(company)
    
    # Intentar evaluar el dominio de la acción
    try:
        domain = eval(act.domain or '[]', {'company_id': company.id, 'active_id': False})
        recs = model.search(domain, limit=10)
        print('  Total registros que devuelve el dominio (mostrando primeros %d):' % len(recs))
        for r in recs:
            r_num = getattr(r, 'number', getattr(r, 'check_number', getattr(r, 'name', '')))
            r_state = getattr(r, 'state', getattr(r, 'check_state', ''))
            print('    - ID=%-6s Cheque/Ref=%-15s Estado=%-12s Importe=%-10.2f Partner=%s' % (
                r.id, r_num, r_state, getattr(r, 'amount', 0.0),
                r.partner_id.display_name if hasattr(r, 'partner_id') and r.partner_id else ''
            ))
            # Verificar si está rechazado
            is_rejected = (
                r_state == 'rejected' or
                'rechaz' in str(r_state).lower() or
                getattr(r, 'is_rejected', False)
            )
            if is_rejected:
                print('      !! ATENCIÓN: Este registro figura RECHAZADO pero el dominio de la acción lo incluye.')
    except Exception as e:
        print('  No se pudo evaluar el dominio directamente: %s' % e)

sub('2. Evaluación de reportes dinámicos account.report')
if 'account.report' in env:
    acc_reports = env['account.report'].search([
        '|', '|',
        ('name', 'ilike', 'cheque'),
        ('name', 'ilike', 'check'),
        ('name', 'ilike', 'tercero')
    ])
    for rep in acc_reports:
        print('\nAnalizando account.report: %s (ID=%s, Code=%s)' % (rep.name, rep.id, getattr(rep, 'code', '')))
        try:
            options = rep._get_options({'allowed_company_ids': [company.id]})
            lines = rep._get_lines(options)
            print('  Líneas devueltas por el reporte: %d' % len(lines))
            for l in lines[:15]:
                print('    Línea: %-40s | Columnas: %s' % (
                    l.get('name', ''),
                    [c.get('name') for c in l.get('columns', [])]
                ))
        except Exception as e:
            print('  No se pudo generar líneas vía _get_lines: %s' % e)

sub('3. Comparación de saldo de cheques en cartera vs saldo de la cuenta en el Mayor')
# Buscamos la cuenta de cheques en cartera
check_accounts = env['account.account'].with_company(company).search([
    '|',
    ('name', 'ilike', 'valor'),
    ('name', 'ilike', 'cheque')
])
for acc in check_accounts:
    # Saldo en el mayor
    aml_lines = env['account.move.line'].with_company(company).search([
        ('account_id', '=', acc.id),
        ('parent_state', '=', 'posted')
    ])
    balance_mayor = sum(aml_lines.mapped('debit')) - sum(aml_lines.mapped('credit'))
    
    # Saldo de cheques físicos no rechazados según account.payment o account.check
    if 'account.check' in env:
        holding_checks = env['account.check'].with_company(company).search([
            ('state', '=', 'holding')
        ])
        total_holding = sum(holding_checks.mapped('amount'))
        print('\nCuenta: [%s] %s' % (acc.code, acc.name))
        print('  Saldo en el Mayor (account.move.line):    $ %.2f' % balance_mayor)
        print('  Total cheques en cartera (state=holding): $ %.2f' % total_holding)
        print('  Diferencia (Mayor - Cartera):             $ %.2f' % (balance_mayor - total_holding))
        
    elif 'account.payment' in env:
        unmatched_checks = env['account.payment'].with_company(company).search([
            ('state', '=', 'posted'),
            ('is_matched', '=', False) if has_field('account.payment', 'is_matched') else ('id', '>', 0),
            '|',
            ('payment_method_line_id.code', 'ilike', 'check'),
            ('payment_method_line_id.code', 'ilike', 'third_party')
        ])
        total_unmatched = sum(unmatched_checks.mapped('amount'))
        print('\nCuenta: [%s] %s' % (acc.code, acc.name))
        print('  Saldo en el Mayor (account.move.line):    $ %.2f' % balance_mayor)
        print('  Total cheques según account.payment:      $ %.2f' % total_unmatched)
        print('  Diferencia:                               $ %.2f' % (balance_mayor - total_unmatched))
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/06_diagnostico_cheques_rechazados.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 06 - Diagnóstico específico de los 3 cheques rechazados y reporte Cheques a Fecha
import inspect
from odoo import fields

company = get_company()
h('06 - DIAGNÓSTICO ESPECÍFICO DE LOS 3 CHEQUES RECHAZADOS (%s)' % company.name)

target_numbers = ['64943755', '90000059', '90000058']
sub('1. Búsqueda de los 3 cheques en l10n_latam.check por número: %s' % target_numbers)

checks = env['l10n_latam.check'].with_company(company).search([
    ('name', 'in', target_numbers)
])

if not checks:
    print('!! No se encontraron por name in %s. Buscando de forma flexible...' % target_numbers)
    checks = env['l10n_latam.check'].with_company(company).search([
        '|', '|',
        ('name', 'ilike', '64943755'),
        ('name', 'ilike', '90000059'),
        ('name', 'ilike', '90000058')
    ])

print('Total cheques encontrados: %d' % len(checks))

for chk in checks:
    print('\n' + '=' * 80)
    print('CHEQUE ID: %s | Número: %s | Importe: $ %.2f | Fecha Pago/Vto: %s' % (
        chk.id, chk.name, chk.amount, chk.payment_date
    ))
    print('  Partner: %s (CUIT: %s)' % (
        chk.partner_id.display_name if chk.partner_id else 'N/A',
        chk.partner_id.vat if chk.partner_id else 'N/A'
    ))
    print('  Diario actual (current_journal_id): %s (ID=%s, Código=%s)' % (
        chk.current_journal_id.name if chk.current_journal_id else 'None',
        chk.current_journal_id.id if chk.current_journal_id else 'None',
        chk.current_journal_id.code if chk.current_journal_id else 'None'
    ))
    if chk.current_journal_id and chk.current_journal_id.default_account_id:
        acc = chk.current_journal_id.default_account_id
        print('    Cuenta del diario actual: [%s] %s' % (acc.code, acc.name))
        
    print('  Pago origen (payment_id): %s (ID=%s, State=%s, Fecha=%s, Diario=%s)' % (
        chk.payment_id.name if chk.payment_id else 'N/A',
        chk.payment_id.id if chk.payment_id else 'N/A',
        chk.payment_id.state if chk.payment_id else 'N/A',
        chk.payment_id.date if chk.payment_id else 'N/A',
        chk.payment_id.journal_id.name if chk.payment_id and chk.payment_id.journal_id else 'N/A'
    ))
    
    # Inspeccionar todos los campos relevantes del cheque
    dump(chk, prefixes=['state', 'status', 'check', 'l10n_latam', 'operation'])
    
    # Operaciones asociadas al cheque
    if hasattr(chk, 'operation_ids') and chk.operation_ids:
        print('  Operaciones asociadas (%d):' % len(chk.operation_ids))
        for op in chk.operation_ids:
            meth = op.payment_method_id.name if op.payment_method_id else ''
            print('    - Op ID=%-6s Ref=%-20s Fecha=%s Estado=%-10s Tipo=%-10s Método=%-15s Diario=%s' % (
                op.id, op.name or '', op.date, op.state,
                getattr(op, 'payment_type', ''), meth,
                op.journal_id.name if op.journal_id else ''
            ))
            if op.move_id:
                print('        Asiento: %s (id=%s, state=%s, date=%s)' % (
                    op.move_id.name, op.move_id.id, op.move_id.state, op.move_id.date
                ))
                for line in op.move_id.line_ids:
                    print('          Línea [%s] %-25s Debe=%-11.2f Haber=%-11.2f Match=%s' % (
                        line.account_id.code, line.account_id.name[:25],
                        line.debit, line.credit,
                        line.matching_number or (line.reconciled and 'Reconciled') or 'No'
                    ))

sub('2. Inspección del código fuente del Wizard account.check.to_date.report.wizard')
Wizard = env['account.check.to_date.report.wizard']
print('Campos del Wizard:')
for fname, f in sorted(Wizard._fields.items()):
    print('  %-30s %s' % (fname, f.type))

for meth_name in ['_get_checks_on_hand', 'print_report', '_get_report_data']:
    if hasattr(Wizard, meth_name):
        print('\n--- Fuente del método %s ---' % meth_name)
        try:
            fn = getattr(Wizard, meth_name)
            src = inspect.getsource(fn)
            print(src)
        except Exception as e:
            print('  <No se pudo obtener fuente: %s>' % e)

sub('3. Simulación de ejecución del Wizard al 06/11/2026 con Diario CHEQT')
cheqt = env['account.journal'].with_company(company).search([('code', '=', 'CHEQT')], limit=1)
if not cheqt:
    cheqt = env['account.journal'].with_company(company).search([('name', 'ilike', 'Cheques de Terceros')], limit=1)

target_date = fields.Date.from_string('2026-11-06')
print('Diario seleccionado: [%s] %s (ID=%s)' % (cheqt.code if cheqt else 'N/A', cheqt.name if cheqt else 'N/A', cheqt.id if cheqt else 'N/A'))
print('Fecha corte: %s' % target_date)

try:
    checks_cheqt = Wizard._get_checks_on_hand(cheqt.id if cheqt else False, target_date)
    print('\nTotal cheques devueltos por el Wizard para CHEQT: %d | Total $: %.2f' % (
        len(checks_cheqt), sum(checks_cheqt.mapped('amount'))
    ))
    
    # Ver si están los 3 cheques
    found_in_report = checks_cheqt.filtered(lambda c: c.name in target_numbers)
    print('¿Aparecen los 3 cheques rechazados en el resultado?: %d encontrados' % len(found_in_report))
    for fc in found_in_report:
        print('  -> ID=%s Núm=%s Imp=$ %.2f DiarioActual=[%s] %s' % (
            fc.id, fc.name, fc.amount,
            fc.current_journal_id.code if fc.current_journal_id else 'None',
            fc.current_journal_id.name if fc.current_journal_id else 'None'
        ))
except Exception as e:
    print('Error ejecutando _get_checks_on_hand:')
    traceback.print_exc()
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/07_auditoria_rechazados_y_reporte.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 07 - Auditoría de movimientos de rechazo y simulación completa del reporte
from odoo import fields

company = get_company()
h('07 - AUDITORÍA DE MOVIMIENTOS DE RECHAZO Y REPORTE (%s)' % company.name)

sub('1. Movimientos en la cuenta 1.1.1.02.006 (Cheque de terceros rechazado)')
acc_rej = env['account.account'].with_company(company).search([('code', '=', '1.1.1.02.006')], limit=1)
if not acc_rej:
    acc_rej = env['account.account'].with_company(company).search([('name', 'ilike', 'terceros rechazado')], limit=1)

if acc_rej:
    lines = env['account.move.line'].with_company(company).search([
        ('account_id', '=', acc_rej.id),
        ('parent_state', '=', 'posted')
    ], order='date desc, id desc')
    print('Total movimientos posted en %s: %d' % (acc_rej.display_name, len(lines)))
    for l in lines:
        try:
            pay = l.payment_id or (l.move_id.payment_ids[:1] if hasattr(l.move_id, 'payment_ids') and l.move_id.payment_ids else None)
            chk_names = []
            if pay:
                if hasattr(pay, 'l10n_latam_new_check_ids') and pay.l10n_latam_new_check_ids:
                    chk_names.extend(pay.l10n_latam_new_check_ids.mapped('name'))
                if hasattr(pay, 'l10n_latam_move_check_ids') and pay.l10n_latam_move_check_ids:
                    chk_names.extend(pay.l10n_latam_move_check_ids.mapped('name'))
            print('  ID=%-6s Fecha=%s Asiento=%-20s Debe=%-10.2f Haber=%-10.2f Partner=%-25s Ref=%-15s Cheques=%s' % (
                l.id, l.date, l.move_id.name, l.debit, l.credit,
                (l.partner_id.name or '')[:25], (l.name or '')[:15], ', '.join(chk_names) if chk_names else 'N/A'
            ))
        except Exception as e:
            print('  Error imprimiendo línea ID=%s: %s' % (l.id, e))

sub('2. Pagos en estado rejected o en diarios de rechazo')
try:
    rej_pays = env['account.payment'].with_company(company).search([
        '|', '|',
        ('state', '=', 'rejected'),
        ('journal_id.code', 'in', ['CSH3', 'CHTER']),
        ('journal_id.name', 'ilike', 'rechaz')
    ], order='date desc, id desc', limit=20)
    print('Pagos detectados (%d):' % len(rej_pays))
    for p in rej_pays:
        print('  ID=%-6s Ref=%-20s Fecha=%s Estado=%-10s Diario=%-20s Imp=%-10.2f Partner=%s' % (
            p.id, p.name, p.date, p.state, p.journal_id.name, p.amount,
            p.partner_id.display_name if p.partner_id else ''
        ))
except Exception as e:
    print('Error en sección 2: %s' % e)

sub('3. Simulación de account.check.to_date.report.wizard')
try:
    Wizard = env['account.check.to_date.report.wizard']
    today = fields.Date.today()

    print('\n-- Ejecutando _get_checks_on_hand SIN filtro de diario (to_date=%s) --' % today)
    checks_all = Wizard._get_checks_on_hand(False, today)
    print('Total cheques en mano devueltos: %d | Importe total: $ %.2f' % (
        len(checks_all), sum(checks_all.mapped('amount'))
    ))
    print('Primeros 15 cheques en el reporte:')
    for c in checks_all[:15]:
        jname = c.current_journal_id.name if c.current_journal_id else 'None'
        print('  ID=%-5s Núm=%-12s Vto=%s Imp=%-11.2f DiarioActual=%-20s Partner=%s' % (
            c.id, c.name, c.payment_date, c.amount, jname[:20], (c.partner_id.name or '')[:30]
        ))

    # Buscar diarios de cheques
    cheq_journals = env['account.journal'].with_company(company).search([
        '|', ('code', 'in', ['CHEQT', 'CSH2']),
        ('name', 'ilike', 'cheque')
    ])
    for j in cheq_journals:
        print('\n-- Ejecutando _get_checks_on_hand para Diario [%s] %s --' % (j.code, j.name))
        checks_j = Wizard._get_checks_on_hand(j.id, today)
        print('Total cheques devueltos para este diario: %d | Importe total: $ %.2f' % (
            len(checks_j), sum(checks_j.mapped('amount'))
        ))
        for c in checks_j[:5]:
            print('  ID=%-5s Núm=%-12s Vto=%s Imp=%-11.2f Partner=%s' % (
                c.id, c.name, c.payment_date, c.amount, (c.partner_id.name or '')[:30]
            ))
except Exception as e:
    print('Error en sección 3: %s' % e)
    traceback.print_exc()

sub('4. Verificación de la vista de búsqueda de l10n_latam.check')
try:
    search_views = env['ir.ui.view'].search([('model', '=', 'l10n_latam.check'), ('type', '=', 'search')])
    for f in search_views:
        print('  View ID=%s: %s' % (f.id, f.name))
        if f.arch and 'checks_on_hand' in f.arch:
            for line in f.arch.splitlines():
                if 'checks_on_hand' in line:
                    print('    Definición checks_on_hand: %s' % line.strip())
except Exception as e:
    print('Error en sección 4: %s' % e)
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/08_verificar_solucion.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 08 - Verificación de la solución: Comparación Mayor vs Reporte sin rechazados
from odoo import fields

company = get_company()
target_date = fields.Date.from_string('2026-11-06')
h('08 - VERIFICACIÓN EXACTA: MAYOR VS REPORTE AL %s (%s)' % (target_date, company.name))

# 1. Saldo en el Mayor de la cuenta 1.1.1.02.010 (Cheques de Terceros) al 06/11/2026
acc_cheq = env['account.account'].with_company(company).search([('code', '=', '1.1.1.02.010')], limit=1)
if not acc_cheq:
    acc_cheq = env['account.account'].with_company(company).search([('name', 'ilike', 'Third Party Checks')], limit=1)

print('Cuenta analizada: [%s] %s' % (acc_cheq.code, acc_cheq.name))
lines_to_date = env['account.move.line'].with_company(company).search([
    ('account_id', '=', acc_cheq.id),
    ('parent_state', '=', 'posted'),
    ('date', '<=', target_date)
])
debit = sum(lines_to_date.mapped('debit'))
credit = sum(lines_to_date.mapped('credit'))
saldo_mayor_to_date = debit - credit
print('  Total apuntes en el Mayor al %s: %d' % (target_date, len(lines_to_date)))
print('  Debe acumulado al corte:   $ %15.2f' % debit)
print('  Haber acumulado al corte:  $ %15.2f' % credit)
print('  SALDO EN EL MAYOR (CORTE): $ %15.2f' % saldo_mayor_to_date)

# 2. Cheques devueltos actualmente por el wizard para el diario CHEQT
cheqt = env['account.journal'].with_company(company).search([('code', '=', 'CHEQT')], limit=1)
if not cheqt:
    cheqt = env['account.journal'].with_company(company).search([('name', 'ilike', 'Cheques de Terceros')], limit=1)

Wizard = env['account.check.to_date.report.wizard']
checks_raw = Wizard._get_checks_on_hand(cheqt.id if cheqt else False, target_date)
total_raw = sum(checks_raw.mapped('amount'))
print('\nReporte Cheques a fecha ACTUAL (con bug):')
print('  Total cheques: %d | Total $: %15.2f' % (len(checks_raw), total_raw))
print('  Diferencia con el Mayor:   $ %15.2f' % (total_raw - saldo_mayor_to_date))

# 3. Identificación y exclusión de los cheques rechazados
rejected_journal_ids = env['account.journal'].search([
    '|', ('code', 'in', ['CHTER', 'CSH3']),
    ('name', 'ilike', 'rechaz')
]).ids

target_numbers = ['64943755', '90000059', '90000058']

# Filtro 1: Excluyendo por diario actual en diarios de rechazo
# Filtro 2: Excluyendo por número de cheque específico si no estuvieran en diarios de rechazo
checks_corregidos = checks_raw.filtered(
    lambda c: c.current_journal_id.id not in rejected_journal_ids and c.name not in target_numbers
)
total_corregido = sum(checks_corregidos.mapped('amount'))

print('\nReporte Cheques a fecha CORREGIDO (excluyendo rechazados):')
print('  Total cheques: %d | Total $: %15.2f' % (len(checks_corregidos), total_corregido))
print('  Cheques rechazados excluidos:')
excluded = checks_raw - checks_corregidos
for c in excluded:
    jcode = c.current_journal_id.code if c.current_journal_id else 'None'
    jname = c.current_journal_id.name if c.current_journal_id else 'None'
    print('    - ID=%-5s Núm=%-12s Imp=$ %12.2f DiarioActual=[%s] %s Partner=%s' % (
        c.id, c.name, c.amount, jcode, jname,
        (c.partner_id.name or '')[:30]
    ))
print('  Suma cheques excluidos:    $ %15.2f' % sum(excluded.mapped('amount')))
print('  NUEVA Diferencia con Mayor:$ %15.2f' % (total_corregido - saldo_mayor_to_date))
__EOF_AUDIT__
cat > ~/tmp/RR-8/scripts/09_fix_cheques_rechazados_dry_run.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 09 - Script de corrección controlada (Dry-Run por defecto)
# Permite simular y, con DRY_RUN=0, aplicar el pase de los 3 cheques al diario de rechazo
import os
from odoo import fields

company = get_company()
DRY_RUN = os.environ.get('DRY_RUN', '1') == '1'

h('09 - FIX CONTROLADO DE CHEQUES RECHAZADOS (DRY_RUN=%s, %s)' % (DRY_RUN, company.name))

target_numbers = ['64943755', '90000059', '90000058']
sub('1. Búsqueda de cheques objetivo')
checks = env['l10n_latam.check'].with_company(company).search([('name', 'in', target_numbers)])
print('Cheques encontrados: %d de %d' % (len(checks), len(target_numbers)))

sub('2. Identificación del diario de destino de cheques rechazados')
journal_rejected = env['account.journal'].with_company(company).search([
    ('code', '=', 'CHTER')
], limit=1)

if not journal_rejected:
    journal_rejected = env['account.journal'].with_company(company).search([
        '|', ('code', 'in', ['CHTER', 'CSH3']),
        ('name', 'ilike', 'rechaz')
    ], limit=1)

if not journal_rejected:
    print('!! ERROR: No se encontró diario de cheques rechazados.')
else:
    print('Diario de rechazo encontrado: [%s] %s (ID=%s)' % (
        journal_rejected.code, journal_rejected.name, journal_rejected.id
    ))

cheqt = env['account.journal'].with_company(company).search([('code', '=', 'CHEQT')], limit=1)
Wizard = env['account.check.to_date.report.wizard']
target_date = fields.Date.from_string('2026-11-06')

if cheqt and Wizard:
    before_checks = Wizard._get_checks_on_hand(cheqt.id, target_date)
    print('\n[ANTES] Total en Reporte Cheques a fecha (CHEQT): %d cheques | $ %.2f' % (
        len(before_checks), sum(before_checks.mapped('amount'))
    ))

sub('3. Evaluación y aplicación de cambios')
for chk in checks:
    print('\nCheque ID=%s | Núm=%s | Importe=$ %.2f' % (chk.id, chk.name, chk.amount))
    print('  Diario actual: [%s] %s' % (
        chk.current_journal_id.code if chk.current_journal_id else 'None',
        chk.current_journal_id.name if chk.current_journal_id else 'None'
    ))
    
    if journal_rejected and chk.current_journal_id != journal_rejected:
        if DRY_RUN:
            print('  -> [DRY-RUN] Se actualizaría current_journal_id -> [%s] %s' % (
                journal_rejected.code, journal_rejected.name
            ))
        else:
            print('  -> [APLICANDO] Actualizando current_journal_id -> [%s] %s' % (
                journal_rejected.code, journal_rejected.name
            ))
            chk.write({'current_journal_id': journal_rejected.id})
    else:
        print('  -> El cheque ya se encuentra en el diario de rechazo o no requiere cambio.')

if cheqt and Wizard:
    after_checks = Wizard._get_checks_on_hand(cheqt.id, target_date)
    print('\n[DESPUÉS DE SIMULACIÓN] Total en Reporte Cheques a fecha (CHEQT): %d cheques | $ %.2f' % (
        len(after_checks), sum(after_checks.mapped('amount'))
    ))

if DRY_RUN:
    print('\nModo DRY-RUN activo: no se guardaron cambios en la base de datos (rollback automático).')
    print('Para aplicar definitivamente los cambios correr con: DRY_RUN=0')
    env.cr.rollback()
else:
    print('\nAplicando cambios definitivamente...')
    env.cr.commit()
    print('>> Cambios confirmados con commit exitosamente.')
__EOF_AUDIT__
chmod +x ~/tmp/RR-8/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/RR-8:'; ls -R ~/tmp/RR-8 | head -50
