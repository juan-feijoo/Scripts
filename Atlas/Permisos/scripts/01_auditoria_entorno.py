# ==============================================================================
# SCRIPT 01: AUDITORÍA DE ENTORNO (Solo lectura / Safe)
# Odoo 18.0+e en Odoo.sh
# ==============================================================================
# Ejecutar en odoo-bin shell
# No modifica datos en la base.

import odoo

print("=" * 80)
print(f"AUDITORÍA TÉCNICA - DB: {env.cr.dbname} | Odoo {odoo.release.version}")
print("=" * 80)

# 1. COMPAÑÍAS REGISTRADAS
print("\n[1] COMPAÑÍAS REGISTRADAS:")
companies = env['res.company'].search([])
for c in companies:
    cuit = getattr(c, 'vat', 'N/A')
    currency = c.currency_id.name if c.currency_id else 'N/A'
    print(f"  ID: {c.id:<3} | Nombre: {c.name:<35} | Moneda: {currency:<5} | CUIT: {cuit}")

# 2. MÓDULOS CLAVE
print("\n[2] MÓDULOS CLAVE Y ESTADO:")
check_modules = [
    'sale_management', 'purchase', 'purchase_requisition', 
    'account_accountant', 'l10n_ar', 'web_studio', 
    'approvals', 'account_payment', 'atlas_security_approvals'
]
installed_mods = env['ir.module.module'].search([('name', 'in', check_modules)])
installed_dict = {m.name: m.state for m in installed_mods}
for mod_name in check_modules:
    st = installed_dict.get(mod_name, 'no encontrado')
    symbol = "✔" if st == 'installed' else "⏳" if st in ('to install', 'to upgrade') else "✘"
    print(f"  {symbol} {mod_name:<30} Estado: {st}")

# 3. USUARIOS DEL TICKET
print("\n[3] USUARIOS DEL PROYECTO ATLAS:")
target_logins = [
    'mandatario@atlasgroup.com.ar',
    'hernanpacetti@atlasgroup.com.ar',
    'administracion@atlasgroup.com.ar',
    'eugeniazanotti@atlasgroup.com.ar',
    'hernanfernandez@atlasgroup.com.ar'
]
Users = env['res.users'].with_context(active_test=False)
for login in target_logins:
    u = Users.search([('login', '=ilike', login.strip())], limit=1)
    if u:
        cos = u.company_ids.mapped('name')
        roles = [g.name for g in u.groups_id if 'Atlas' in (g.category_id.name or '') or 'Rol:' in g.name]
        print(f"  ✔ Match: {login:<35} | ID: {u.id:<3} | Activo: {u.active} | Cías: {cos} | Roles: {roles or 'Sin rol custom'}")
    else:
        print(f"  ✘ No existe: {login:<35} (Será creado por el Script 02)")

# 4. REGLAS STUDIO APPROVAL
print("\n[4] REGLAS DE APROBACIÓN DE STUDIO:")
Rule = env['studio.approval.rule'].with_context(active_test=False)
rules = Rule.search([])
if rules:
    for r in rules:
        method_name = r.method or (r.action_id.name if r.action_id else 'N/A')
        appr_logins = r.approver_ids.mapped('login')
        print(f"  ID {r.id:>3}: {r.name:<35} | Modelo: {r.model_id.model:<18} | Método: {method_name:<16} | Activa: {r.active} | Aprobadores: {appr_logins or '(Nadie - Sin actividad)'}")
else:
    print("  (Sin reglas studio.approval.rule registradas)")

# 5. GRUPOS ATLAS CREADOS
print("\n[5] GRUPOS ATLAS EN LA BASE:")
atlas_groups = env['res.groups'].search([('category_id.name', 'ilike', 'Atlas')])
if atlas_groups:
    for g in atlas_groups:
        xmlid = g.get_external_id().get(g.id, 'Sin XMLID')
        print(f"  ID {g.id:>3}: {g.name:<45} | XMLID: {xmlid}")
else:
    print("  (Aún no se crearon grupos Atlas. Instalar el módulo atlas_security_approvals)")

print("\n" + "=" * 80)
print("FIN DE AUDITORÍA")
print("=" * 80)
