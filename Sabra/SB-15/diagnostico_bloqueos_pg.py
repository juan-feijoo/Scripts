# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO DE BLOQUEOS Y CONEXIONES ACTIVAS EN POSTGRESQL (ODOO.SH)
Ejecución:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < diagnostico_bloqueos_pg.py
"""

env.cr.execute("""
    SELECT 
        pid, 
        usename, 
        client_addr, 
        state, 
        now() - query_start AS duration, 
        now() - xact_start AS xact_duration,
        query
    FROM pg_stat_activity
    WHERE pid != pg_backend_pid()
      AND (state != 'idle' OR (state = 'idle in transaction' AND (now() - xact_start) > interval '10 seconds'))
    ORDER BY duration DESC;
""")
active_queries = env.cr.dictfetchall()

print("\n" + "=" * 80)
print("CONEXIONES ACTIVAS O EN TRANSACCIÓN EN POSTGRESQL")
print("=" * 80)
if not active_queries:
    print("No hay consultas bloqueantes ni transacciones colgadas.")
else:
    for q in active_queries:
        print(f"PID: {q['pid']} | Estado: {q['state']} | Duración Tx: {q['xact_duration']}")
        print(f"Query: {q['query'][:200]}\n")
print("=" * 80 + "\n")
