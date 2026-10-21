# FIX Pruebas - Aprobadores en reglas (staging, sin rebuild)

> ✔ **Aplicado 2026-10-15** en `staging-39866751`: 9 reglas con aprobadores, todo ✔, simulación S00001 → actividad para matias + diego. COMMIT.
> ⏳ Producción: mismo fix pendiente (Script B con logins reales).

**Problema:** Studio exige la aprobación ("Falta una aprobación") pero **no crea actividad ni notifica**.
**Causa (D2/D3):** Odoo 18 agenda la actividad solo a `approver_ids` de la regla. Las reglas `[DIMAT]` tienen solo grupo → `approver_ids` vacío → nadie recibe nada.
**Fix:** cargar `approver_ids` en las 9 reglas + asegurar grupos de los usuarios demo. No borra nada, no toca producción.

> Pestaña **Shell** del branch **staging** → `odoo-bin shell` → pegar el bloque completo.
> `DRY_RUN = False`: guarda directo, **pero solo si todo da ✔** (si algo falla → ROLLBACK automático).
> Para solo probar sin guardar: `DRY_RUN = True`.

```python
import sys, traceback

DRY_RUN = False         # <<< False = guarda (solo si TODO OK) | True = prueba y rollback
EXPECTED_DB = 'outsource-argentina-dimat-staging-39866751'

MOD = 'studio_customization'

# Grupo aprobador de la regla → logins que reciben la ACTIVIDAD (y pueden aprobar)
APROBADORES = {
    'dimat_g_analista_jr':   ['matiasf'],
    'dimat_g_analista_sr':   ['ivan'],
    'dimat_g_gerente_com':   ['salvador'],
    'dimat_g_gerencia':      ['matias', 'diego'],
    'dimat_g_jefa_adm':      ['nancy'],
    'dimat_g_gerente_op':    ['diego'],
    'dimat_g_aprob_compras': ['diego'],
}

# Login → grupos Dimat que debe tener (se agregan si faltan, no se quita nada)
GRUPOS_USUARIO = {
    'matias':   ['dimat_g_gerencia'],
    'diego':    ['dimat_g_gerencia', 'dimat_g_gerente_op', 'dimat_g_aprob_compras'],
    'salvador': ['dimat_g_gerente_com', 'dimat_g_aprob_compras'],
    'ivan':     ['dimat_g_analista_sr', 'dimat_g_aprob_compras'],
    'matiasf':  ['dimat_g_analista_jr'],
    'nancy':    ['dimat_g_jefa_adm'],
    'vendedor': ['dimat_g_vendedor'],
}

Users = env['res.users'].with_context(active_test=False)
Rules = env['studio.approval.rule']
ok_all = True

def check(cond, msg):
    global ok_all
    ok_all &= bool(cond)
    print(('  ✔ ' if cond else '  ✘ ') + msg)

def grp(x):
    return env.ref(f'{MOD}.{x}', raise_if_not_found=False)

def xmlid_of(group):
    return group.get_external_id().get(group.id, '').split('.')[-1]

try:
    import odoo
    print(f'DB: {env.cr.dbname} | Odoo {odoo.release.version}')
    print(f'Modo: {"DRY-RUN" if DRY_RUN else "REAL"}\n')
    if 'produccion' in env.cr.dbname or env.cr.dbname != EXPECTED_DB:
        raise Exception(f'BASE NO PERMITIDA: {env.cr.dbname} (esperada {EXPECTED_DB}). Abortado.')

    # --- Estado ANTES ---
    rules = Rules.search([('name', '=like', '[DIMAT]%')])
    print(f'=== ANTES ({len(rules)} reglas) ===')
    for r in rules:
        print(f'  {r.id:>3} {r.name:24} grupo={r.approval_group_id.name:32} approvers={r.approver_ids.mapped("login") or "-"}')
    if not rules:
        raise Exception('No hay reglas [DIMAT] en esta base')

    # --- 1. Grupos de usuarios ---
    print('\n=== 1. GRUPOS DE USUARIOS ===')
    for login, xmlids in GRUPOS_USUARIO.items():
        u = Users.search([('login', '=', login)], limit=1)
        if not u:
            check(False, f'usuario {login} NO existe (correr script de usuarios_demo.md)')
            continue
        faltan = [x for x in xmlids if grp(x) and grp(x) not in u.groups_id]
        if faltan:
            u.write({'groups_id': [(4, grp(x).id) for x in faltan]})
            print(f'  {login:10} agregados: {faltan}')
        else:
            print(f'  {login:10} OK (ya tenía todo)')
        if not u.active:
            u.active = True
            print(f'  {login:10} reactivado')

    # --- 2. Aprobadores en reglas ---
    print('\n=== 2. APROBADORES EN REGLAS ===')
    expected = {}
    for r in rules:
        logins = APROBADORES.get(xmlid_of(r.approval_group_id), [])
        appr = Users.search([('login', 'in', logins)])
        expected[r.id] = appr
        r.write({'approver_ids': [(6, 0, appr.ids)], 'users_to_notify': [(5, 0, 0)]})
        print(f'  {r.name:24} → {appr.mapped("login") or "-"}')
    env.flush_all()
    rules.invalidate_recordset(['approver_ids', 'approver_log_ids'])

    # --- 3. Verificación ---
    print('\n=== 3. VERIFICACIÓN ===')
    for r in rules:
        exp = expected[r.id]
        check(exp and set(r.approver_ids.ids) == set(exp.ids),
              f'{r.name:24} aprobadores = {r.approver_ids.mapped("login") or "-"}')
        for u in exp:
            check(r.with_user(u).can_validate, f'   {u.login} puede aprobar')
        # nivel inferior NO debe poder aprobar (ej. matiasf en venta 5M-10M)
        if r.name == '[DIMAT] Venta 5M-10M':
            jr = Users.search([('login', '=', 'matiasf')])
            if jr:
                check(not r.with_user(jr).can_validate, '   matiasf NO puede aprobar (correcto)')
        if r.name == '[DIMAT] Venta 5M-10M':
            sal = Users.search([('login', '=', 'salvador')])
            if sal:
                check(r.with_user(sal).can_validate, '   salvador SÍ puede (nivel superior)')

    # --- 4. Simulación (savepoint: SIEMPRE se descarta) ---
    print('\n=== 4. SIMULACIÓN pedir aprobación (se descarta) ===')
    class _Undo(Exception):
        pass
    so = env['sale.order'].search([('state', 'in', ('draft', 'sent')), ('amount_total', '>', 2_000_000)], limit=1)
    if not so:
        print('  ℹ no hay cotización > $2M en borrador para simular')
    else:
        try:
            with env.cr.savepoint():
                res = Rules.check_approval('sale.order', so.id, 'action_confirm', False)
                acts = env['mail.activity'].search([('res_model', '=', 'sale.order'), ('res_id', '=', so.id)])
                print(f'  {so.name} ${so.amount_total:,.0f} → approved={res.get("approved")}')
                print(f'  {"✔" if acts else "⚠"} actividades para: {acts.mapped("user_id.login") or "-"}')
                raise _Undo()
        except _Undo:
            pass
        env.invalidate_all()

    print('\n=== RESULTADO:', 'TODO OK' if ok_all else 'HAY ERRORES', '===')
    if DRY_RUN or not ok_all:
        env.cr.rollback()
        print('ROLLBACK (nada guardado)')
    else:
        env.cr.commit()
        print('COMMIT (guardado)')
except Exception:
    traceback.print_exc(file=sys.stdout)
    env.cr.rollback()
    print('ERROR → ROLLBACK')
```

## Después del COMMIT - probar en UI

1. Ctrl+Shift+R.
2. Admin → S00001 → **Confirmar** → "Falta una aprobación" → en el chatter aparece actividad **Grant Approval** para Diego y Matías.
3. Login `diego` / `1234` (incógnito) → 🕒 → abre S00001 → **Aprobar** (ícono en botón Confirmar) → Confirmar.
4. Seguir con [guion_demo.md](guion_demo.md).
