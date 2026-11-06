#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/audit_redondeo_mayorista
mkdir -p ~/tmp/audit_redondeo_mayorista/scripts && cd ~/tmp/audit_redondeo_mayorista
cat > ~/tmp/audit_redondeo_mayorista/run_all.sh <<'__EOF_AUDIT__'
#!/bin/bash
# Ejecuta todos los scripts scripts/[0-9]*.py con odoo-bin shell y genera un zip con los .txt resultantes.
# Uso:  bash ~/tmp/audit_redondeo_mayorista/run_all.sh                 (usa $PGDATABASE o el odoo.conf del build)
#       DB=nombre_base bash ~/tmp/audit_redondeo_mayorista/run_all.sh
#       LOG_PATTERN='pricelist|rounding' bash ~/tmp/audit_redondeo_mayorista/run_all.sh
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
cat > ~/tmp/audit_redondeo_mayorista/scripts/_lib.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# Helpers comunes para auditoría de redondeo y listas de precios.
# Se ejecuta dentro de `odoo-bin shell` (la variable `env` ya existe, superusuario).
import base64
import html
import inspect
import math
import os
import re
import traceback

# ---------------------------------------------------------------------------
# PARÁMETROS DE LA TAREA
# ---------------------------------------------------------------------------
DRY_RUN = True
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'SABRA')
MAYORISTA_PL_ID = int(os.environ.get('MAYORISTA_PL_ID', '7'))
MINORISTA_PL_ID = int(os.environ.get('MINORISTA_PL_ID', '5'))


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
    """Imprime campos de `rec` cuyo nombre está en `names` o empieza con algún `prefixes`."""
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
        print('!! No se encontró compañía ilike %r, usando env.company' % name)
        return env.company
    if len(companies) > 1:
        print('!! Varias compañías coinciden, uso la primera: %s' % companies.mapped('name'))
    return companies[0]


def safe(fn, *args, **kwargs):
    """Ejecuta fn y, si falla, imprime el traceback y devuelve None."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        print('  !! ERROR:')
        print('  ' + traceback.format_exc().replace('\n', '\n  '))
        return None


def has_field(model, fname):
    return fname in env[model]._fields
__EOF_AUDIT__
cat > ~/tmp/audit_redondeo_mayorista/scripts/01_auditoria_listas_precios.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 01 - Auditoría detallada de Listas de Precios y Reglas de Redondeo
company = get_company()
h('01 - LISTAS DE PRECIOS Y REGLAS DE CÁLCULO / REDONDEO (%s)' % company.name)

pricelists = env['product.pricelist'].with_company(company).search([])
print("Total de listas de precios encontradas: %d\n" % len(pricelists))

for pl in pricelists:
    sub("Lista [ID: %s] '%s' (Moneda: %s, Compañía: %s, Activa: %s)" % (
        pl.id, pl.name, pl.currency_id.name, pl.company_id.name or 'Global', pl.active
    ))
    
    # Política de descuentos y campos clave
    dump(pl, names=['discount_policy', 'currency_id', 'company_id', 'active'])
    
    items = pl.item_ids
    print("\n  Cantidad de reglas (item_ids): %d" % len(items))
    for idx, item in enumerate(items, 1):
        target = "Global (Todo el catálogo)"
        if item.applied_on == '2_product_category':
            target = "Categoría: %s" % (item.categ_id.display_name if item.categ_id else 'N/A')
        elif item.applied_on == '1_product':
            target = "Plantilla: %s" % (item.product_tmpl_id.display_name if item.product_tmpl_id else 'N/A')
        elif item.applied_on == '0_product_variant':
            target = "Variante: %s" % (item.product_id.display_name if item.product_id else 'N/A')
            
        print("\n    Regla #%d [ID: %s] | Aplica a: %s (%s)" % (idx, item.id, item.applied_on, target))
        print("      - Método de cálculo (compute_price): %s" % item.compute_price)
        
        if item.compute_price == 'fixed':
            print("      - Precio Fijo: %s" % item.fixed_price)
        elif item.compute_price == 'percentage':
            print("      - Porcentaje de Descuento: %s %%" % item.percent_price)
        elif item.compute_price == 'formula':
            base_desc = item.base
            if item.base == 'pricelist' and item.base_pricelist_id:
                base_desc += " -> Lista '%s' [ID: %s]" % (item.base_pricelist_id.name, item.base_pricelist_id.id)
            print("      - Base de cálculo: %s" % base_desc)
            print("      - Descuento (price_discount): %s %%" % item.price_discount)
            print("      - Margen extra / Recargo (price_surcharge): %s" % item.price_surcharge)
            print("      - MÉTODO DE REDONDEO (price_round): %s" % item.price_round)
            print("      - Margen Mínimo: %s | Margen Máximo: %s" % (item.price_min_margin, item.price_max_margin))
            
        print("      - Cantidad Mínima: %s" % item.min_quantity)
        if item.date_start or item.date_end:
            print("      - Vigencia: desde %s hasta %s" % (item.date_start, item.date_end))
__EOF_AUDIT__
cat > ~/tmp/audit_redondeo_mayorista/scripts/02_monedas_impuestos_precision.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 02 - Monedas, Precisión Decimal e Impuestos de Venta
company = get_company()
h('02 - CONFIGURACIÓN DE MONEDA, PRECISIÓN DECIMAL E IMPUESTOS (%s)' % company.name)

# 1. Monedas
sub('1. Monedas (res.currency)')
currencies = env['res.currency'].search([('name', 'in', ['ARS', 'USD'])])
for cur in currencies:
    print("  Moneda: %s (%s) [ID: %s]" % (cur.name, cur.symbol, cur.id))
    print("    - Redondeo (rounding): %s" % cur.rounding)
    print("    - Lugares decimales (decimal_places): %s" % cur.decimal_places)
    print("    - Posición del símbolo: %s" % cur.position)
    print("    - Activa: %s" % cur.active)
    print("    - Tasa actual: %s\n" % cur.rate)

# 2. Precisión Decimal
sub('2. Precisión Decimal (decimal.precision)')
precisions = env['decimal.precision'].search([])
for dp in precisions:
    print("  - %-30s : %d dígitos" % (dp.name, dp.digits))

# 3. Configuración de la Compañía para Impuestos
sub('3. Configuración de Redondeo en res.company')
print("  - Compañía: %s [ID: %s]" % (company.name, company.id))
print("  - Moneda principal: %s" % company.currency_id.name)
if has_field('res.company', 'tax_calculation_rounding_method'):
    print("  - Método de redondeo de impuestos (tax_calculation_rounding_method): %s" % company.tax_calculation_rounding_method)

# 4. Impuestos de Venta
sub('4. Impuestos de Venta (account.tax)')
sale_taxes = env['account.tax'].search([
    ('type_tax_use', '=', 'sale'),
    ('company_id', 'in', [company.id, False])
])
for tax in sale_taxes:
    print("  [ID: %s] %-35s | Alícuota: %6.2f%% | Tipo: %s | ¿Incluido en precio? (price_include): %s" % (
        tax.id, tax.name, tax.amount, tax.amount_type, tax.price_include
    ))
__EOF_AUDIT__
cat > ~/tmp/audit_redondeo_mayorista/scripts/03_simulacion_calculo_redondeo.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 03 - Simulación de Cálculo de Precios Mayoristas y Estrategias de Redondeo (DRY-RUN)
import math

company = get_company()
h('03 - SIMULACIÓN DE CÁLCULO MAYORISTA Y ESTRATEGIAS DE REDONDEO (%s)' % company.name)

# 1. Obtener Listas de Precios
pl_min = env['product.pricelist'].browse(MINORISTA_PL_ID)
if not pl_min.exists():
    pl_min = env['product.pricelist'].search([('name', 'ilike', 'ars'), ('company_id', 'in', [company.id, False])], limit=1)

pl_may = env['product.pricelist'].browse(MAYORISTA_PL_ID)
if not pl_may.exists():
    pl_may = env['product.pricelist'].search([('name', 'ilike', 'mayorista'), ('company_id', 'in', [company.id, False])], limit=1)

print("Lista Minorista en uso : [ID: %s] %s" % (pl_min.id if pl_min else 'N/A', pl_min.name if pl_min else 'N/A'))
print("Lista Mayorista en uso : [ID: %s] %s" % (pl_may.id if pl_may else 'N/A', pl_may.name if pl_may else 'N/A'))

# 2. Selección de Productos
sample_codes = ['101500700374', '21819', '1809', '6988776231993', '7795587005106']
products = env['product.product'].with_company(company).search([
    '|', ('default_code', 'in', sample_codes), ('barcode', 'in', sample_codes)
])

if len(products) < 5:
    extra = env['product.product'].with_company(company).search([('sale_ok', '=', True)], limit=10)
    products = (products | extra)[:10]

currency = company.currency_id

sub('TABLA COMPARATIVA DE CÁLCULO Y ALTERNATIVAS DE REDONDEO')
print("Explicación de columnas:")
print("  - LIST PRICE    : Precio de lista en la ficha del producto.")
print("  - MIN. C/IVA    : Precio minorista final (con impuestos).")
print("  - MAY. BASE     : Precio devuelto por la regla mayorista (neto sin IVA).")
print("  - MAY. ACTUAL   : Precio mayorista con IVA actual (con sus decimales).")
print("  - REDOND. $1    : Redondeo al entero más cercano (sin centavos).")
print("  - REDOND. $10   : Redondeo a la decena más cercana.")
print("  - CEIL $10      : Redondeo a la decena siempre hacia arriba.")
print("  - REDOND. $50   : Redondeo al múltiplo de $50.")
print("-" * 125)
header = "%-14s | %-20s | %10s | %10s | %10s | %12s | %10s | %10s | %10s | %10s" % (
    "CÓDIGO", "PRODUCTO", "LIST PRICE", "MIN C/IVA", "MAY BASE", "MAY ACTUAL", "RED $1", "RED $10", "CEIL $10", "RED $50"
)
print(header)
print("-" * 125)

for p in products:
    code = (p.default_code or p.barcode or 'S/C')[:14]
    name = (p.name or '')[:20]
    
    # 1. Minorista
    p_min_base = pl_min._get_product_price(p, 1.0, currency=currency) if pl_min else p.list_price
    t_min = p.taxes_id.compute_all(p_min_base, product=p, partner=False) if p.taxes_id else {'total_included': p_min_base}
    p_min_inc = t_min['total_included']
    
    # 2. Mayorista
    p_may_base = pl_may._get_product_price(p, 1.0, currency=currency) if pl_may else p_min_base
    t_may = p.taxes_id.compute_all(p_may_base, product=p, partner=False) if p.taxes_id else {'total_included': p_may_base}
    p_may_inc = t_may['total_included']
    
    # Estrategias de Redondeo sobre el precio mayorista con IVA
    r_1 = round(p_may_inc)
    r_10 = round(p_may_inc / 10.0) * 10
    c_10 = math.ceil(p_may_inc / 10.0) * 10
    r_50 = round(p_may_inc / 50.0) * 50
    
    line = "%-14s | %-20s | %10.2f | %10.2f | %10.2f | %12.4f | %10.2f | %10.2f | %10.2f | %10.2f" % (
        code, name, p.list_price, p_min_inc, p_may_base, p_may_inc, r_1, r_10, c_10, r_50
    )
    print(line)

print("-" * 125)
print("\nObservaciones sobre el cálculo:")
print("1. Si 'MAY BASE' no tiene centavos pero 'MAY ACTUAL' sí, los centavos provienen de la alícuota de IVA (ej. 21%% sobre una base impar).")
print("2. Si 'MAY BASE' ya tiene centavos, la regla de la lista de precios no tiene configurado 'price_round' (método de redondeo) o tiene un porcentaje fraccionario.")
print("3. Si la empresa busca precios comerciales limpios en la etiqueta, la solución más robusta depende de si se quiere redondear antes o después de impuestos.")
__EOF_AUDIT__
chmod +x ~/tmp/audit_redondeo_mayorista/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/audit_redondeo_mayorista:'; ls -R ~/tmp/audit_redondeo_mayorista | head -50
