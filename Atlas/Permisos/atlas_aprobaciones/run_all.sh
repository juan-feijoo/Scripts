#!/bin/bash
# Ejecuta todos los scripts scripts/[0-9]*.py con odoo-bin shell y genera un zip con los .txt resultantes.
# Uso:
#   bash ~/tmp/atlas_aprobaciones/run_all.sh            -> MODO DRY-RUN (simula todo y hace ROLLBACK)
#   APPLY=1 bash ~/tmp/atlas_aprobaciones/run_all.sh    -> MODO REAL (hace COMMIT si todo da OK)
#   DB=otra_base APPLY=1 bash ~/tmp/atlas_aprobaciones/run_all.sh
#   CONTACTO_CIRCUITO_COMPRA="Mi Proveedor" APPLY=1 bash ~/tmp/atlas_aprobaciones/run_all.sh
set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
TASK="$(basename "$BASE")"
TS="$(date +%Y%m%d_%H%M%S)"
MODE_TAG="dryrun"
case "${APPLY:-}" in
  1|true|TRUE|yes|YES|si|SI) MODE_TAG="apply" ;;
esac
NAME="resultados_${MODE_TAG}_${TS}"
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
  echo "Modo: ${MODE_TAG} (APPLY=${APPLY:-0})"
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
  echo ">> Ejecutando $n (${MODE_TAG}) ..."
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
  "$BASE/${TASK}_${MODE_TAG}_${TS}" "$BASE" "$NAME"

echo
echo "Listo (${MODE_TAG}). Archivos:"; ls -la "$OUT"
echo "Con errores:"; grep -l "Traceback\|!! ERROR" "$OUT"/*.txt 2>/dev/null || echo "  ninguno"
echo "ZIP: $BASE/${TASK}_${MODE_TAG}_${TS}.zip  (descargar desde pestaña Editor)"
