# -*- coding: utf-8 -*-
"""
Liberar bloqueos y transacciones colgadas en PostgreSQL (Odoo.sh)
Ejecución:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < liberar_bloqueos_pg.py
"""

print("\n" + "=" * 80)
print("VERIFICANDO Y TERMINANDO TRANSACCIONES COLGADAS EN POSTGRESQL")
print("=" * 80)

env.cr.execute("""
    SELECT pid, state, now() - xact_start AS xact_duration, query
    FROM pg_stat_activity
    WHERE pid != pg_backend_pid()
      AND state IN ('idle in transaction', 'active')
      AND (now() - xact_start) > interval '15 seconds';
""")
stuck = env.cr.dictfetchall()

if not stuck:
    print("No hay transacciones colgadas de larga duración.")
else:
    print(f"Se encontraron {len(stuck)} transacciones colgadas. Terminándolas...")
    for s in stuck:
        print(f"  - Terminando PID {s['pid']} (Estado: {s['state']}, Duración: {s['xact_duration']})")
        env.cr.execute("SELECT pg_terminate_backend(%s);", (s['pid'],))

print("=" * 80 + "\n")
