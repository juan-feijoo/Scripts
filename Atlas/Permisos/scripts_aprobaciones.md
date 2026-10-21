# Dimat - Aprobaciones (Odoo 18.0+e / Odoo.sh)

## Estado

| Paso | Qué | Estado |
|---|---|---|
| 0 | Verificación de campos `studio.approval.rule` | ✔ Hecho (2026-10-09) |
| 0b | ¿Enforcement server-side? | ⏳ Pendiente correr |
| A | Script grupos (con XML ID) | ✔ Real COMMIT (2026-10-09) · grupos id 77-84, categoría id 147 |
| B | Script usuarios + reglas | ✔ Real COMMIT en `staging-39574417` (2026-10-09) · reglas id 19-27 · ⏳ re-correr: compra >5M (2026-10-13) + usuarios cuando existan |
| C | Checklist de pruebas en UI | ⏳ |

> ⚠ **Odoo.sh staging**: cada rebuild (push / "Rebuild") crea una **base nueva** copiada de producción → se pierden grupos y reglas. Después de cada rebuild, re-correr A y B. Verificar siempre la línea `DB:` al inicio de la salida.
>
> Diagnóstico D1 (2026-10-09): base `outsource-argentina-dimat-staging-39574417` sin reglas → A y B se corrieron en otra base/build. Re-correr A y B ahí.

### Estado PRODUCCIÓN (`outsource-argentina-dimat-produccion-38233760`, 2026-10-14)

- Las corridas "reales" del 2026-10-09 (A grupos 77-84, B reglas 10-18) **fueron en producción**, no en staging (scripts aún no imprimían DB). El "Resultado paso 0" de abajo también es de producción.
- Producción vacía: solo admin, sin documentos, reglas con 0 entradas → sin impacto.
- Script A dry-run en prod: todo `actualizado` + ✔ → **A no necesita corrida real**.
- ✔ Script B real en prod (2026-10-14): 9 reglas activas, `Compra` (16) archivada, `Compra >5M` creada. Verificado en UI.
- ⏳ Re-correr B con logins reales (cargados 2026-10-16): crea 12 usuarios sin invitación + permisos + aprobadores. Correr P7 → P12.
- Usuarios demo para staging: ver `usuarios_demo.md`.

## 🚀 Runbook PRODUCCIÓN

> Todo en la pestaña **Shell del branch de producción** de Odoo.sh. Abrir `odoo-bin shell` y pegar los bloques **python** tal cual (único bash: paso 0b, va en la terminal, fuera del shell de Odoo).

| # | Acción | OK si… |
|---|---|---|
| P1 | Odoo.sh → branch producción → **Backups → "Make a backup"** (manual, antes de tocar nada) | backup listado con fecha de hoy |
| P2 | **Paso 0** (solo lectura) en producción | `DB:` **sin** "staging"; anotar nombre exacto; versión 18.0+e; campos iguales a staging; revisar monedas, `po_double_validation`, usuarios y reglas existentes |
| P3 | ✔ `EXPECTED_DB` = `outsource-argentina-dimat-produccion-38233760` | — |
| P4 | ✔ Logins reales cargados en Script B (mail cliente 2026-10-16). Revisar `ACCESOS` (⚠ sugerido) | — |
| P5-P6 | Script A: ✔ ya aplicado en prod (dry-run 2026-10-14 todo `actualizado`) → saltear | — |
| P7 | **Script B** `DRY_RUN = True` | `TODO OK` + `ROLLBACK`; 12 `creado`; avisos ⚠ solo de grupos de app inexistentes |
| P8 | **Script B** `DRY_RUN = False` | `TODO OK` + `COMMIT` |
| P9 | **Shell nuevo** → **D1** | aparecen las 9 reglas `[DIMAT]` con aprobadores |
| P10 | UI: Ajustes → Usuarios → revisar permisos de app de cada uno (sobre todo los 5 sin rol) | — |
| P11 | UI: seleccionar usuarios → **Enviar invitación** (recién ahí les llega mail) | usuarios "Invitación enviada" |
| P12 | Prueba humo: cotización > $2M con un usuario sin aprobación → Confirmar | "Falta una aprobación" + actividad a matiasf (contacto@) |

**Si algo sale mal:** script **Rollback** (desactiva reglas `[DIMAT]`). Los grupos no molestan aunque queden.
**Si P2 muestra `po_double_validation = two_step`:** desactivar en Ajustes → Compras (si no, OC con doble aprobación).
**Si P2 muestra ventas/pagos en USD:** frenar y revisar tramos antes de P8 (montos se comparan en moneda del documento).

Resultado paso 0 (staging):
- Campos confirmados: `approval_group_id`, `approver_ids`, `domain`, `notification_order`, `exclusive_user`, `users_to_notify`, `message`.
- Base vacía (sin ventas/compras/pagos, solo admin) → usuarios se asignan cuando existan (script B los saltea si no existen).
- `po_double_validation = one_step` → doble validación nativa de compras ya desactivada.

### Cómo correr los scripts A y B

1. Pestaña **Shell** del branch → `odoo-bin shell` → pegar el bloque python completo.
2. Primera corrida con `DRY_RUN = True` → revisar el reporte: todo debe dar `✔`.
3. Cambiar a `DRY_RUN = False` → correr de nuevo → el reporte final debe repetir todo `✔` y decir `COMMIT`.
4. Son idempotentes: re-correrlos no duplica nada.

---

## Paso 0 - Verificación (solo lectura)

```python
import odoo
print("DB:", env.cr.dbname, "| Odoo", odoo.release.version)
R = env['studio.approval.rule']
print("\n=== CAMPOS studio.approval.rule ===")
for n, f in sorted(R._fields.items()):
    if not f.automatic and not n.startswith(('message_', 'website_message', 'activity_')):
        print(f"{n:30} {f.type:12} {f.string}")
print("\n=== REGLAS EXISTENTES ===")
for r in R.with_context(active_test=False).search([]):
    print(r.id, r.active, r.model_id.model, r.method or r.action_id.name, r.approval_group_id.full_name, r.domain or '')
print("\n=== GRUPOS DIMAT EXISTENTES ===")
print(env['res.groups'].search([('category_id.name', '=', 'Dimat / Aprobaciones')]).mapped('name') or '-')
print("\n=== MONEDAS EN VENTAS/COMPRAS/PAGOS ===")
print(env['sale.order'].read_group([], ['currency_id'], ['currency_id']))
print(env['purchase.order'].read_group([], ['currency_id'], ['currency_id']))
print(env['account.payment'].read_group([], ['currency_id'], ['currency_id']))
print("\n=== DOBLE VALIDACION COMPRAS ===")
for c in env['res.company'].search([]):
    print(c.name, c.po_double_validation, c.po_double_validation_amount)
print("\n=== USUARIOS INTERNOS ===")
for u in env['res.users'].search([('share', '=', False)]):
    print(u.id, u.login, '|', u.name)
```

---

## Paso 0b - ¿Enforcement server-side? (solo lectura)

```bash
odoo-bin shell --no-http <<'EOF' 2>/dev/null
import inspect, odoo.addons.web_studio as ws
print("PATH:", ws.__path__[0])
R = type(env['studio.approval.rule'])
print("\n=== check_approval ===")
print(inspect.getsource(R.check_approval))
EOF
WS=$(odoo-bin shell --no-http <<'EOF' 2>/dev/null | tail -1
import odoo.addons.web_studio as ws; print(ws.__path__[0])
EOF
)
echo "=== USOS EN PYTHON ($WS) ==="
grep -rn "check_approval\|_get_approval_spec\|studio_approval" "$WS" --include=*.py | grep -v "/tests/" | head -40
echo "=== OVERRIDES DE BaseModel / ir.* ==="
grep -rln "_inherit = 'base'\|_inherit = \"base\"\|class Base(" "$WS/models" 2>/dev/null
```

---

## Script A - Grupos con XML ID

Jerarquía (`implied_ids`: el superior hereda al inferior → puede aprobar lo de abajo):

```
Vendedor
 └ Analista Comercial Jr
    └ Analista Comercial Sr
       └ Gerente Comercial
          └ Gerencia (General / Operativa)
Jefa Administrativa
 └ Gerente Operaciones
Aprobador Compras
```

XML IDs resultantes: `studio_customization.dimat_g_vendedor`, `studio_customization.dimat_g_analista_jr`, etc.

```python
import sys, traceback

DRY_RUN = True          # <<< True = prueba y rollback | False = guarda
EXPECTED_DB = 'outsource-argentina-dimat-produccion-38233760'   # <<< PRODUCCIÓN (staging: 'outsource-argentina-dimat-staging-39866751')

MOD = 'studio_customization'
CATEGORY = ('dimat_cat_aprobaciones', 'Dimat / Aprobaciones')
GROUPS = [
    # xmlid                   nombre                              implica
    ('dimat_g_vendedor',      'Vendedor',                         []),
    ('dimat_g_analista_jr',   'Analista Comercial Jr',            ['dimat_g_vendedor']),
    ('dimat_g_analista_sr',   'Analista Comercial Sr',            ['dimat_g_analista_jr']),
    ('dimat_g_gerente_com',   'Gerente Comercial',                ['dimat_g_analista_sr']),
    ('dimat_g_gerencia',      'Gerencia (General / Operativa)',   ['dimat_g_gerente_com']),
    ('dimat_g_jefa_adm',      'Jefa Administrativa',              []),
    ('dimat_g_gerente_op',    'Gerente Operaciones',              ['dimat_g_jefa_adm']),
    ('dimat_g_aprob_compras', 'Aprobador Compras',                []),
]

IMD = env['ir.model.data']
ok_all = True

def check(cond, msg):
    global ok_all
    ok_all &= bool(cond)
    print(('  ✔ ' if cond else '  ✘ ') + msg)

def ensure(xmlid, model, vals, fallback_domain):
    """Busca por XML ID; si no, por dominio (registro creado a mano); si no, crea. Garantiza XML ID."""
    rec = env.ref(f'{MOD}.{xmlid}', raise_if_not_found=False)
    if rec:
        rec.write(vals)
        print(f'actualizado      {MOD}.{xmlid}')
        return rec
    rec = env[model].search(fallback_domain, limit=1)
    if rec:
        rec.write(vals)
        print(f'XML ID agregado  {MOD}.{xmlid}  (existía id={rec.id})')
    else:
        rec = env[model].create(vals)
        print(f'creado           {MOD}.{xmlid}  (id={rec.id})')
    IMD.create({'module': MOD, 'name': xmlid, 'model': model,
                'res_id': rec.id, 'noupdate': True})
    return rec

try:
    installed = env['ir.module.module'].search_count(
        [('name', '=', MOD), ('state', '=', 'installed')])
    print(f'Módulo {MOD} instalado: {bool(installed)} (no es requisito, solo informativo)')
    import odoo
    print(f'DB: {env.cr.dbname} | Odoo {odoo.release.version}')
    print(f'Modo: {"DRY-RUN" if DRY_RUN else "REAL"}\n')
    if env.cr.dbname != EXPECTED_DB:
        raise Exception(f'BASE INCORRECTA: estoy en {env.cr.dbname}, se esperaba {EXPECTED_DB}. Abortado.')

    # --- Aplicar ---
    cat = ensure(CATEGORY[0], 'ir.module.category',
                 {'name': CATEGORY[1], 'sequence': 1},
                 [('name', '=', CATEGORY[1])])
    for xmlid, name, implied in GROUPS:
        ensure(xmlid, 'res.groups', {
            'name': name,
            'category_id': cat.id,
            'implied_ids': [(6, 0, [env.ref(f'{MOD}.{i}').id for i in implied])],
        }, [('name', '=', name), '|', ('category_id', '=', cat.id), ('category_id', '=', False)])
    env.flush_all()

    # --- Verificar ---
    print('\n=== VERIFICACIÓN ===')
    c = env.ref(f'{MOD}.{CATEGORY[0]}', raise_if_not_found=False)
    check(c and c.name == CATEGORY[1], f'categoría {MOD}.{CATEGORY[0]}')
    for xmlid, name, implied in GROUPS:
        g = env.ref(f'{MOD}.{xmlid}', raise_if_not_found=False)
        check(g, f'{MOD}.{xmlid} existe')
        if not g:
            continue
        check(g.name == name, f'   nombre = {name}')
        check(g.category_id == c, f'   categoría = {CATEGORY[1]}')
        exp = {env.ref(f'{MOD}.{i}').id for i in implied}
        check(set(g.implied_ids.ids) == exp, f'   implica = {implied or "-"}')
        check(g.get_external_id().get(g.id) == f'{MOD}.{xmlid}', f'   get_external_id OK')
    dup = env['res.groups'].read_group([('category_id', '=', c.id)], ['name'], ['name'])
    check(all(d.get('name_count', d.get('__count')) == 1 for d in dup), 'sin grupos duplicados en la categoría')

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

> Ver los grupos en UI: Ajustes → Usuarios y compañías → Grupos → filtrar "Dimat".

---

## Script B - Usuarios + reglas de aprobación

> Correr **después** de que el Script A esté en modo real (COMMIT).
>
> Pendientes del cliente (ajustar las variables marcadas ⚠):
> - ¿Monto **con o sin IVA**? → `CAMPO_MONTO_VENTA` / `CAMPO_MONTO_NC`.
> - ¿"Jefe de operaciones" (compras) y "Gerente de operaciones" (pagos) = Diego?
> - ¿Quién aprueba descuento > 5%? → regla comentada.
> - ¿Operan en USD? Los montos se comparan en la moneda del documento.

Comportamiento:
- **Usuarios**: los logins que no existen se saltean con aviso (no rompe). Re-correr cuando se carguen.
- **Reglas**: se identifican por nombre `[DIMAT] ...`. Si se renombra/quita una regla de la lista, la vieja se **archiva**.
- **Aprobadores**: `approver_ids` se llena con los usuarios del mapa `APROBADORES` que existan → a ellos se les agenda la **actividad** al pedir aprobación. **Sin aprobadores no se crea actividad** (ver D2/D3).
- Tramos **excluyentes**: cada documento cae en una sola regla → aprueba un solo nivel.

```python
import sys, traceback

DRY_RUN = True          # <<< True = prueba y rollback | False = guarda
EXPECTED_DB = 'outsource-argentina-dimat-produccion-38233760'   # <<< PRODUCCIÓN (staging: 'outsource-argentina-dimat-staging-39866751')

MOD = 'studio_customization'
M = 1_000_000
CAMPO_MONTO_VENTA = 'amount_total'   # ⚠ o 'amount_untaxed'
CAMPO_MONTO_NC    = 'amount_total'   # ⚠ o 'amount_untaxed'
CAMPO_MONTO_COMPRA = 'amount_total'  # ⚠ o 'amount_untaxed'

# Logins reales (mail del cliente, 2026-10-16)
D = '@drogueriadimat.com.ar'
MATIAS, DIEGO, SALVADOR, IVAN = 'matias'+D, 'diego'+D, 'salvadors'+D, 'ivans'+D
MATIASF, NANCY, NICOLAS = 'contacto'+D, 'nancyg'+D, 'nicolasm'+D

# Usuarios internos a CREAR si no existen (login → nombre). Se crean SIN mandar invitación
# (no_reset_password); las invitaciones se mandan después desde la UI.
# ⚠ Cada usuario interno cuenta para la suscripción Enterprise.
CREAR_USUARIOS = True
NUEVOS = {
    'rrhh'+D:        'Alejandra',
    NANCY:           'Nancy',
    'info'+D:        'Lorena',
    NICOLAS:         'Nicolas',
    'facturacion'+D: 'Agustin',
    MATIASF:         'Matias F.',
    IVAN:            'Ivan',
    SALVADOR:        'Salvador',
    DIEGO:           'Diego',
    MATIAS:          'Matias',
    'gustavov'+D:    'Gustavo',
    'deposito'+D:    'Pedro',
}

# Grupos Dimat. Se asigna el grupo más alto; los inferiores vienen por herencia.
USUARIOS = {
    MATIAS:   ['dimat_g_gerencia'],                                                 # Gerente General
    DIEGO:    ['dimat_g_gerencia', 'dimat_g_gerente_op', 'dimat_g_aprob_compras'],  # Gerente Operativo
    SALVADOR: ['dimat_g_gerente_com', 'dimat_g_aprob_compras'],                     # Gerente Comercial (+ reemplazo compras)
    IVAN:     ['dimat_g_analista_sr', 'dimat_g_aprob_compras'],                     # Analista Sr (+ reemplazo compras)
    MATIASF:  ['dimat_g_analista_jr'],                                              # Analista Jr
    NANCY:    ['dimat_g_jefa_adm'],                                                 # Jefa Administrativa
}

# ⚠ SUGERIDO, revisar: permisos de app (sin esto el aprobador no puede abrir el documento).
# Solo AGREGA grupos, nunca quita. XML IDs que no existan → aviso, no rompe.
VENTAS_TODO = 'sales_team.group_sale_salesman_all_leads'
ACCESOS = {
    MATIAS:   ['sales_team.group_sale_manager', 'purchase.group_purchase_manager', 'account.group_account_manager'],
    DIEGO:    ['sales_team.group_sale_manager', 'purchase.group_purchase_manager', 'account.group_account_manager'],
    SALVADOR: ['sales_team.group_sale_manager', 'purchase.group_purchase_user', 'account.group_account_invoice'],
    IVAN:     [VENTAS_TODO, 'purchase.group_purchase_user', 'account.group_account_invoice'],
    MATIASF:  [VENTAS_TODO],
    NANCY:    ['account.group_account_manager'],
    NICOLAS:  ['purchase.group_purchase_user'],
    # ⚠ Rol a confirmar con el cliente:
    # 'facturacion'+D: ['account.group_account_invoice'],   # Agustin
    # 'deposito'+D:    ['stock.group_stock_user'],          # Pedro
    # 'rrhh'+D:        ['hr.group_hr_user'],                # Alejandra
    # 'info'+D:        [],                                  # Lorena
    # 'gustavov'+D:    [],                                  # Gustavo
}

# approver_ids: reciben la ACTIVIDAD de aprobación (y también pueden aprobar).
# No restringe: can_validate = user in approver_ids OR user in approval_group_id → niveles superiores siguen pudiendo.
# users_to_notify se vacía (Odoo lo usa solo para nota interna tras aprobar/rechazar).
APROBADORES = {
    'dimat_g_analista_jr':   [MATIASF],
    'dimat_g_analista_sr':   [IVAN],
    'dimat_g_gerente_com':   [SALVADOR],
    'dimat_g_gerencia':      [MATIAS, DIEGO],
    'dimat_g_jefa_adm':      [NANCY],
    'dimat_g_gerente_op':    [DIEGO],
    'dimat_g_aprob_compras': [DIEGO],
}

v, n, c = CAMPO_MONTO_VENTA, CAMPO_MONTO_NC, CAMPO_MONTO_COMPRA
RULES = [
    # nombre               modelo              método            grupo                   dominio                                                   descripción
    ('Venta 2M-5M',        'sale.order',       'action_confirm', 'dimat_g_analista_jr',  [(v, '>', 2*M),  (v, '<=', 5*M)],                         'Cotización entre $2M y $5M'),
    ('Venta 5M-10M',       'sale.order',       'action_confirm', 'dimat_g_analista_sr',  [(v, '>', 5*M),  (v, '<=', 10*M)],                        'Cotización entre $5M y $10M'),
    ('Venta 10M-25M',      'sale.order',       'action_confirm', 'dimat_g_gerente_com',  [(v, '>', 10*M), (v, '<=', 25*M)],                        'Cotización entre $10M y $25M'),
    ('Venta >25M',         'sale.order',       'action_confirm', 'dimat_g_gerencia',     [(v, '>', 25*M)],                                         'Cotización mayor a $25M'),
    # ('Venta desc >5%',   'sale.order',       'action_confirm', 'dimat_g_analista_jr',  [('order_line.discount', '>', 5)],                        'Descuento mayor al 5%'),
    ('NC hasta 2M',        'account.move',     'action_post',    'dimat_g_analista_sr',  [('move_type', '=', 'out_refund'), (n, '<=', 2*M)],       'Nota de crédito hasta $2M'),
    ('NC >2M',             'account.move',     'action_post',    'dimat_g_gerente_com',  [('move_type', '=', 'out_refund'), (n, '>', 2*M)],        'Nota de crédito mayor a $2M'),
    ('Compra >5M',         'purchase.order',   'button_confirm', 'dimat_g_aprob_compras', [(c, '>', 5*M)],                                         'Orden de compra mayor a $5M'),
    ('Pago hasta 1M',      'account.payment',  'action_post',    'dimat_g_jefa_adm',     [('payment_type', '=', 'outbound'), ('amount', '<=', 1*M)], 'Pago a proveedor hasta $1M'),
    ('Pago >1M',           'account.payment',  'action_post',    'dimat_g_gerente_op',   [('payment_type', '=', 'outbound'), ('amount', '>', 1*M)],  'Pago a proveedor mayor a $1M'),
]

R = env['studio.approval.rule'].with_context(active_test=False)
Users = env['res.users'].with_context(active_test=False)
ok_all = True
warnings = []

def check(cond, msg):
    global ok_all
    ok_all &= bool(cond)
    print(('  ✔ ' if cond else '  ✘ ') + msg)

def grp(x):
    return env.ref(f'{MOD}.{x}')

def users(logins):
    found = Users.search([('login', 'in', logins)])
    missing = set(logins) - set(found.mapped('login'))
    return found, missing

try:
    import odoo
    print(f'DB: {env.cr.dbname} | Odoo {odoo.release.version}')
    print(f'Modo: {"DRY-RUN" if DRY_RUN else "REAL"}\n')
    if env.cr.dbname != EXPECTED_DB:
        raise Exception(f'BASE INCORRECTA: estoy en {env.cr.dbname}, se esperaba {EXPECTED_DB}. Abortado.')

    # --- Pre-chequeo: grupos del Script A ---
    print('=== PRE-CHEQUEO GRUPOS ===')
    all_groups = {r[3] for r in RULES} | {g for gs in USUARIOS.values() for g in gs}
    for x in sorted(all_groups):
        check(env.ref(f'{MOD}.{x}', raise_if_not_found=False), f'{MOD}.{x}')
    if not ok_all:
        raise Exception('Faltan grupos: correr Script A en modo real primero')

    # --- Crear usuarios (sin invitación) ---
    print('\n=== CREAR USUARIOS ===')
    base_user = env.ref('base.group_user')
    for login, nombre in NUEVOS.items():
        u, missing = users([login])
        if not missing:
            if not u.active:
                u.active = True
                print(f'  reactivado  {login}')
            else:
                print(f'  ya existe   {login} (id={u.id})')
            continue
        if not CREAR_USUARIOS:
            print(f'  ⚠ no existe (CREAR_USUARIOS=False): {login}')
            continue
        u = Users.with_context(no_reset_password=True).create({
            'name': nombre, 'login': login, 'email': login,
            'groups_id': [(6, 0, [base_user.id])],
        })
        print(f'  creado      {login} → {nombre} (id={u.id})')

    # --- Permisos de app ---
    print('\n=== PERMISOS DE APP ===')
    for login, xmlids in ACCESOS.items():
        u, missing = users([login])
        if missing:
            warnings.append(f'accesos: usuario no existe {login}')
            continue
        gs = env['res.groups']
        for x in xmlids:
            g = env.ref(x, raise_if_not_found=False)
            if g:
                gs |= g
            else:
                warnings.append(f'accesos: grupo no existe {x} ({login})')
        u.write({'groups_id': [(4, g.id) for g in gs]})
        print(f'  {login:32} → {gs.mapped("full_name")}')

    # --- Grupos Dimat ---
    print('\n=== GRUPOS DIMAT ===')
    for login, xmlids in USUARIOS.items():
        u, missing = users([login])
        if missing:
            warnings.append(f'usuario no existe: {login}')
            print(f'  ⚠ no existe, salteado: {login}')
            continue
        u.write({'groups_id': [(4, grp(x).id) for x in xmlids]})
        print(f'  asignado {login} → {xmlids}')

    # --- Reglas ---
    print('\n=== REGLAS ===')
    wanted = set()
    for name, model, method, gx, domain, msg in RULES:
        full = f'[DIMAT] {name}'
        wanted.add(full)
        notify, missing = users(APROBADORES.get(gx, []))
        for m in missing:
            warnings.append(f'notificar: login no existe {m} ({full})')
        vals = {
            'name': full,
            'model_id': env['ir.model']._get_id(model),
            'method': method,
            'approval_group_id': grp(gx).id,
            'domain': str(domain) if domain else False,
            'message': msg,
            'approver_ids': [(6, 0, notify.ids)],
            'users_to_notify': [(5, 0, 0)],
            'active': True,
        }
        r = R.search([('name', '=', full)], limit=1)
        if r:
            r.write(vals); print(f'  actualizada {full}')
        else:
            R.create(vals); print(f'  creada      {full}')
    stale = R.search([('name', '=like', '[DIMAT]%'), ('name', 'not in', list(wanted)), ('active', '=', True)])
    if stale:
        stale.write({'active': False})
        print(f'  archivadas (ya no están en la lista): {stale.mapped("name")}')
    env.flush_all()

    # --- Verificación ---
    print('\n=== VERIFICACIÓN USUARIOS ===')
    if CREAR_USUARIOS:
        for login in NUEVOS:
            u, missing = users([login])
            check(not missing and u.active and not u.share and u.has_group('base.group_user'),
                  f'{login} existe, activo, interno')
    for login, xmlids in ACCESOS.items():
        u, missing = users([login])
        if missing:
            continue
        for x in xmlids:
            if env.ref(x, raise_if_not_found=False):
                check(u.has_group(x), f'{login} ∈ {x}')
    for login, xmlids in USUARIOS.items():
        u, missing = users([login])
        if missing:
            continue
        for x in xmlids:
            check(u.has_group(f'{MOD}.{x}'), f'{login} ∈ {x}')

    print('\n=== VERIFICACIÓN REGLAS ===')
    for name, model, method, gx, domain, msg in RULES:
        full = f'[DIMAT] {name}'
        r = R.search([('name', '=', full)])
        check(len(r) == 1, f'{full} existe (única)')
        if len(r) != 1:
            continue
        check(r.active, '   activa')
        check(r.model_id.model == model, f'   modelo = {model}')
        check(r.method == method and hasattr(env[model], method), f'   método = {method} (existe en modelo)')
        check(r.approval_group_id == grp(gx), f'   grupo = {gx}')
        check((r.domain or False) == (str(domain) if domain else False), f'   dominio = {domain or "(sin condición)"}')
        try:
            cnt = env[model].search_count(domain)
            check(True, f'   dominio evalúa OK ({cnt} registros hoy)')
        except Exception as e:
            check(False, f'   dominio NO evalúa: {e}')
        r.invalidate_recordset(['approver_ids', 'approver_log_ids'])
        exp_appr, _miss = users(APROBADORES.get(gx, []))
        check(exp_appr and set(r.approver_ids.ids) == set(exp_appr.ids), f'   aprobadores (actividad) = {r.approver_ids.mapped("login") or "-"}')
        for u in exp_appr:
            check(r.with_user(u).can_validate, f'   {u.login} puede aprobar')

    print('\n=== REGLAS [DIMAT] ACTIVAS EN BASE ===')
    for r in R.search([('name', '=like', '[DIMAT]%'), ('active', '=', True)]):
        print(f'  {r.id:>4} {r.model_id.model:16} {r.method:15} {r.approval_group_id.name:32} {r.domain or ""}')

    if warnings:
        print('\n=== AVISOS (no bloquean) ===')
        for w in warnings:
            print('  ⚠', w)

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

> Si el botón no muestra el ícono de aprobación después de crear las reglas: abrir el form en Studio, clic en el botón y guardar (refresca la vista).

---

## Diagnóstico D1 - Reglas no aparecen en Studio (solo lectura)

Síntoma (2026-10-09): Script B hizo COMMIT (reglas id 10-18), pero Studio → botón Confirm de S00001 → "Aprobaciones" vacío.

Antes de correr: **Ctrl+Shift+R** y volver a abrir Studio. Si sigue vacío, correr **en el shell del mismo branch que la UI**:

```python
import inspect
R = env['studio.approval.rule'].with_context(active_test=False)
print("DB:", env.cr.dbname)
print("Ventas en esta base:", env['sale.order'].search_count([]), env['sale.order'].search([], limit=3).mapped('name'))
print("\n=== REGLAS EN ESTA BASE ===")
for r in R.search([]):
    print(r.id, r.active, r.model_name, r.method, r.action_id.id, r.approval_group_id.name, r.domain)
print("\n=== FIRMA Y CODIGO get_approval_spec ===")
cls = type(R)
for m in ('get_approval_spec', '_get_approval_spec'):
    f = getattr(cls, m, None)
    if f:
        print(m, inspect.signature(f))
        print(inspect.getsource(f)[:2500])
```

Devolver: salida + dominio de la URL de la UI (para confirmar branch/base).

---

## Diagnóstico D2 - "Falta una aprobación" pero no se crea actividad (solo lectura)

Síntoma (2026-10-15, staging): S00001 $30.25M → Confirmar (admin) → "Falta una aprobación", sin actividad en chatter ni notificación.

```python
import inspect, odoo
print("DB:", env.cr.dbname, "| Odoo", odoo.release.version)
REF = 'S00001'                      # <<< documento a revisar
so = env['sale.order'].search([('name', '=', REF)], limit=1)
print("Doc:", so.name, so.id, so.state, so.amount_total)
R = env['studio.approval.rule']
rules = R.search([('model_name', '=', 'sale.order'), ('method', '=', 'action_confirm')])
print("\n=== REGLAS QUE MATCHEAN EL DOC ===")
from odoo.tools.safe_eval import safe_eval
for r in rules:
    match = bool(so.filtered_domain(safe_eval(r.domain or '[]')))
    print(f"  {r.id} {r.name:22} match={match} order={r.notification_order} approvers={r.approver_ids.mapped('login')} notify={r.users_to_notify.mapped('login')}")
print("\n=== ENTRADAS (aprobaciones/rechazos) ===")
for e in env['studio.approval.entry'].search([('model', '=', 'sale.order'), ('res_id', '=', so.id)]):
    print(" ", e.id, e.rule_id.name, e.user_id.login, e.approved, e.create_date)
print("\n=== SOLICITUDES (studio.approval.request) ===")
if 'studio.approval.request' in env:
    for q in env['studio.approval.request'].search([('res_id', '=', so.id), ('rule_id', 'in', rules.ids)]):
        print(" ", q.id, q.rule_id.name, 'activity:', q.mail_activity_id.id, q.mail_activity_id.user_id.login, q.create_date)
else:
    print("  (modelo no existe)")
print("\n=== ACTIVIDADES DEL DOC ===")
for a in env['mail.activity'].search([('res_model', '=', 'sale.order'), ('res_id', '=', so.id)]):
    print(" ", a.id, a.activity_type_id.name, a.user_id.login, a.summary, a.date_deadline)
print("\n=== CODIGO: quién crea la actividad ===")
cls = type(R)
for m in ('check_approval', '_create_request', '_get_or_create_activity_type'):
    f = getattr(cls, m, None)
    if f:
        print(f"--- {m}{inspect.signature(f)}")
        print(inspect.getsource(f)[:3000])
```

---

### Resultado D2

`_create_request` agenda actividades a **`approver_ids`**, no a `users_to_notify`. Reglas `[DIMAT]` solo tienen `approval_group_id` → `approver_ids` vacío → **no se crea actividad**. Falta ver si `approver_ids` restringe quién aprueba (D3).

### Resultado D3

- `can_validate = user in approver_ids or user in approval_group_id.users` → `approver_ids` **suma**, no restringe. Herencia de niveles intacta.
- `approver_ids` = a quién se agenda la actividad. `users_to_notify` = nota interna tras aprobar/rechazar.
- **Fix**: Script B y usuarios demo cargan `approver_ids` (mapa `APROBADORES`) y vacían `users_to_notify`.
- ⚠ Producción: hasta cargar logins reales, `approver_ids` vacío → aprobación exigida pero **sin actividad**.

## Diagnóstico D3 - Semántica approver_ids / grupo / users_to_notify (solo lectura)

```python
import inspect, re
R = env['studio.approval.rule']
cls = type(R)
print("=== AYUDA DE CAMPOS ===")
for n in ('approver_ids', 'approval_group_id', 'users_to_notify', 'exclusive_user', 'notification_order', 'can_validate'):
    f = R._fields[n]
    print(f"{n:20} store={f.store} compute={f.compute} inverse={getattr(f, 'inverse', None)}\n    help: {f.help}")
print("\n=== CODIGO ===")
for m in ('_compute_can_validate', '_compute_approver_ids', '_inverse_approver_ids', '_set_approval', 'set_approval'):
    f = getattr(cls, m, None)
    if f:
        print(f"--- {m}")
        print(inspect.getsource(f)[:2500])
print("\n=== USOS DE users_to_notify ===")
src = inspect.getsource(inspect.getmodule(cls))
for i, line in enumerate(src.splitlines(), 1):
    if 'users_to_notify' in line:
        print(f"{i:5}: {line}")
print("\n=== VALOR ACTUAL approver_ids EN REGLAS DIMAT ===")
for r in R.search([('name', '=like', '[DIMAT]%')]):
    print(f"  {r.id} {r.name:22} grupo={r.approval_group_id.name:30} approvers={r.approver_ids.mapped('login')}")
```

---

## Paso C - Checklist de pruebas (UI)

- [ ] Vendedor confirma cotización de $1.5M → confirma directo
- [ ] Vendedor confirma cotización de $3M → queda pendiente; Matías F. recibe actividad
- [ ] Matías F. intenta aprobar una de $7M → no puede
- [ ] Salvador aprueba una de $7M → puede (herencia de grupo)
- [ ] Cotización de $30M → aprueba Matías o Diego
- [ ] NC $1M → Iván; NC $3M → Salvador
- [ ] **NC desde wizard "Nota de crédito" → "Revertir completo"** → ¿saltea aprobación?
- [ ] Nicolás confirma OC de $4M → confirma directo
- [ ] Nicolás confirma OC de $6M → queda pendiente; aprueba Diego/Salvador/Iván
- [ ] Pago $500k → Nancy; pago $2M → Diego
- [ ] **Pago desde "Registrar pago" en factura de proveedor** → ¿saltea aprobación?
- [ ] **Publicar NC/pagos en masa desde la lista** → ¿saltea aprobación?
- [ ] Venta en USD (si existen) → ¿tramo correcto?

Los ítems en negrita son los atajos a revisar. Si saltean la aprobación, se cubren con un módulo chico o con una acción automatizada que bloquee.

---

## Rollback

Desactiva todas las reglas `[DIMAT]`. Los grupos quedan; borrarlos a mano si hace falta.

```python
rules = env['studio.approval.rule'].search([('name', '=like', '[DIMAT]%')])
rules.write({'active': False})
print('reglas desactivadas:', len(rules))
env.cr.commit()
```
