# -*- coding: utf-8 -*-
# Helpers y configuración centralizada para Atlas (Odoo 18.0+e / Odoo.sh)
# Se ejecuta dentro de `odoo-bin shell` (la variable `env` ya existe, superusuario).
import html
import inspect
import os
import re
import sys
import traceback

# ===========================================================================
# PARÁMETROS DE LA TAREA (editables acá o por variables de entorno)
# ===========================================================================
# Por defecto DRY_RUN = True (simula y hace ROLLBACK).
# Para aplicar cambios reales (COMMIT): APPLY=1 bash run_all.sh
APPLY = os.environ.get('APPLY', '').strip().lower() in ('1', 'true', 'yes', 'si')
DRY_RUN = not APPLY

# Base esperada (evidencia del relevamiento en staging)
EXPECTED_DB = os.environ.get('EXPECTED_DB', 'outsource-argentina-atlas-group1-staging-42306331')
ALLOW_PRODUCTION = os.environ.get('ALLOW_PRODUCTION', '').strip().lower() in ('1', 'true', 'yes', 'si')

# Compañías
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'BULGHERONI')
COMPANY_1066_NAME = os.environ.get('COMPANY_1066_NAME', '1066')

# Contacto particular para el circuito de aprobación de Compras (se crea si no existe)
CONTACTO_CIRCUITO_COMPRA = os.environ.get(
    'CONTACTO_CIRCUITO_COMPRA',
    '[ATLAS] Proveedor Tercero Circuito',
)
CONTACTO_STREET = os.environ.get('CONTACTO_STREET', 'Av. Corrientes 2500')
CONTACTO_CITY = os.environ.get('CONTACTO_CITY', 'Buenos Aires')
CONTACTO_CUIT = os.environ.get('CONTACTO_CUIT', '')  # Opcional: dejar vacío si no se quiere validar CUIT

# Proyecto y datos demo para UI (solo en staging, nunca en producción)
PROYECTO_CIRCUITO_NAME = os.environ.get('PROYECTO_CIRCUITO_NAME', '[ATLAS] Proyecto Circuito Terceros')
CLIENTE_DEMO_NAME = os.environ.get('CLIENTE_DEMO_NAME', '[ATLAS DEMO] Cliente Corporativo S.A.')
PROV_NORMAL_DEMO_NAME = os.environ.get('PROV_NORMAL_DEMO_NAME', '[ATLAS DEMO] Proveedor Regular Sin Aprobación')

SET_STAGING_PASSWORDS = os.environ.get('SET_STAGING_PASSWORDS', '1').strip().lower() in ('1', 'true', 'yes', 'si')
TEST_PASSWORD = os.environ.get('TEST_PASSWORD', '12345')

# ===========================================================================
# MATRIZ DE USUARIOS, ROLES Y NOTIFICACIONES ATLAS
# ===========================================================================
USERS_CONFIG = {
    'mandatario@atlasgroup.com.ar': {
        'name': 'Operador',
        'role': 'group_role_operador',
        'apps': [
            'sales_team.group_sale_salesman',
            'purchase.group_purchase_user',
        ],
        'disallowed_apps': [
            'sales_team.group_sale_salesman_all_leads',
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_invoice',
            'account.group_account_user',
            'account.group_account_manager',
            'base.group_system',
            'base.group_erp_manager',
        ],
        'allow_1066': False,  # EXCLUIDO ESTRICTAMENTE DE 1066 S.A.
        'notification_type': 'inbox',
    },
    'hernanpacetti@atlasgroup.com.ar': {
        'name': 'Hernan Pacetti',
        'role': 'group_role_resp_operaciones',
        'apps': [
            'sales_team.group_sale_salesman_all_leads',
            'purchase.group_purchase_user',
        ],
        'disallowed_apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_invoice',
            'account.group_account_user',
            'account.group_account_manager',
            'base.group_system',
            'base.group_erp_manager',
        ],
        'allow_1066': False,  # EXCLUIDO ESTRICTAMENTE DE 1066 S.A.
        'notification_type': 'inbox',
    },
    'administracion@atlasgroup.com.ar': {
        'name': 'Tomás Di Leo',
        'role': 'group_role_administrativo',
        'apps': [
            'sales_team.group_sale_salesman_all_leads',
            'purchase.group_purchase_user',
            'account.group_account_user',
        ],
        'disallowed_apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_manager',
            'base.group_system',
            'base.group_erp_manager',
        ],
        'allow_1066': True,
        'notification_type': 'inbox',
    },
    'eugeniazanotti@atlasgroup.com.ar': {
        'name': 'Eugenia Zanotti',
        'role': 'group_role_resp_administracion',
        'apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_manager',
        ],
        'disallowed_apps': [
            'base.group_system',
        ],
        'allow_1066': True,
        'notification_type': 'inbox',
    },
    'hernanfernandez@atlasgroup.com.ar': {
        'name': 'Hernan Fernandez',
        'role': 'group_role_resp_general',
        'apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_manager',
        ],
        'disallowed_apps': [],
        'allow_1066': True,
        'notification_type': 'inbox',
    },
}

# Usuarios que reciben la ACTIVIDAD (🕒) y la NOTIFICACIÓN EN BANDEJA (💬 @mención):
# - En Ventas: SOLO Hernán F. y Eugenia (Hernán Pacetti mantiene permiso de aprobar por grupo sin notificación).
# - En Compras (contacto tercero): Hernán F. y Eugenia.
NOTIF_VENTA_LOGINS = [
    'hernanfernandez@atlasgroup.com.ar',
    'eugeniazanotti@atlasgroup.com.ar',
]
NOTIF_COMPRA_LOGINS = [
    'hernanfernandez@atlasgroup.com.ar',
    'eugeniazanotti@atlasgroup.com.ar',
]

# Definición de grupos Atlas (coincide con atlas_security_approvals/security/security_groups.xml)
ATLAS_CATEGORY = ('cat_atlas_aprobaciones', 'Atlas / Aprobaciones y Roles')
ATLAS_GROUPS = [
    # (xmlid, nombre, implied_xmlids_locales, implied_xmlids_core)
    ('group_atlas_can_unlink',          'Atlas: Permitir Eliminación de Movimientos',      [], ['base.group_user']),
    ('group_atlas_aprob_venta',         'Atlas: Aprobador de Órdenes de Venta',            [], []),
    ('group_atlas_aprob_compra',        'Atlas: Aprobador de Requerimiento de Compras',    [], []),
    ('group_atlas_can_manage_contacts', 'Atlas: Permitir Carga de Contactos',              [], []),
    ('group_atlas_can_manage_products', 'Atlas: Permitir Carga de Productos',              [], []),
    ('group_role_operador',             'Rol: Operador',                                   [], ['base.group_user']),
    ('group_role_resp_operaciones',     'Rol: Responsable Operaciones',                    ['group_atlas_aprob_venta'], ['base.group_user']),
    ('group_role_administrativo',       'Rol: Administrativo',                             ['group_atlas_can_manage_contacts', 'group_atlas_can_manage_products'], ['base.group_user']),
    ('group_role_resp_administracion',  'Rol: Responsable Administración',                 ['group_role_administrativo', 'group_atlas_aprob_venta', 'group_atlas_aprob_compra', 'group_atlas_can_unlink'], []),
    ('group_role_resp_general',         'Rol: Responsable General',                        ['group_role_resp_administracion'], []),
]

RULE_VENTA_NAME = '[ATLAS] Aprobación de Orden de Venta'
RULE_COMPRA_NAME = '[ATLAS] Aprobación Compra Tercero'
AUTO_NOTIF_NAME = '[ATLAS] Notificar en bandeja al solicitar aprobación Studio'

# Código ejecutado por la base.automation al crearse studio.approval.request
AUTO_NOTIF_SERVER_CODE = """# Publica UNA sola nota interna con @mención para que los aprobadores reciban
# notificación en Bandeja de Conversaciones (💬) al solicitarse aprobación.
by_target = {}
for req in records:
    rule = req.rule_id.sudo()
    if not rule or not (rule.name or '').startswith('[ATLAS]'):
        continue
    # Deduplicación: _create_request crea 1 studio.approval.request por aprobador;
    # solo disparamos el post en el primer request (menor id) para (rule, res_id).
    first_req = env['studio.approval.request'].sudo().search(
        [('rule_id', '=', rule.id), ('res_id', '=', req.res_id)],
        order='id asc',
        limit=1,
    )
    if first_req and req.id != first_req.id:
        continue
    key = (rule.id, req.res_id)
    by_target.setdefault(key, []).append(req)

for (rule_id, res_id), req_list in by_target.items():
    rule = env['studio.approval.rule'].sudo().browse(rule_id)
    if not rule.model_id.is_mail_thread:
        continue
    doc = env[rule.model_name].sudo().browse(res_id)
    if not doc.exists():
        continue
    users = rule.approver_ids.filtered(lambda u: u.active and u.partner_id)
    if not users:
        continue
    partners = users.mapped('partner_id')
    mentions = ' '.join(
        '<a href="#" data-oe-model="res.partner" data-oe-id="%s" class="o_mail_redirect">@%s</a>'
        % (p.id, p.name)
        for p in partners
    )
    requester = env.user.display_name
    doc_label = doc.display_name or ('ID %s' % doc.id)
    body = (
        '<p><strong>[Aprobación requerida]</strong> %s (%s)<br/>'
        'Solicitada por: %s<br/>'
        'Pendiente de aprobación: %s</p>'
    ) % (rule.name, doc_label, requester, mentions)
    doc.with_context(mail_notify_author=False, mail_post_autofollow=False).message_post(
        body=body,
        body_is_html=True,
        partner_ids=partners.ids,
        message_type='comment',
        subtype_xmlid='mail.mt_note',
        author_id=env.user.partner_id.id,
    )
"""


# ===========================================================================
# HELPERS COMUNES
# ===========================================================================
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
    full = full or []
    for fname in sorted(rec._fields):
        if (names and fname in names) or (prefixes and fname.startswith(tuple(prefixes))):
            print('  %-45s %s' % (fname, fmt(rec, fname, None if fname in full else max_len)))


def strip_html(s):
    return html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).strip()


def has_field(model, fname):
    return model in env and fname in env[model]._fields


def safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        print('  !! ERROR:')
        print('  ' + traceback.format_exc().replace('\n', '\n  '))
        return None


def is_production_db():
    name = (env.cr.dbname or '').lower()
    return ('produccion' in name or 'production' in name) and 'staging' not in name


def check_db_safety():
    db = env.cr.dbname
    if is_production_db() and not ALLOW_PRODUCTION:
        raise Exception(
            'GUARDIA DE PRODUCCIÓN: estás en %r y ALLOW_PRODUCTION no está activo. '
            'Para operar en producción, pasá ALLOW_PRODUCTION=1 explícitamente.' % db
        )
    if db != EXPECTED_DB:
        if 'atlas' in db.lower():
            print('  ⚠ Aviso: DB actual (%s) difiere de EXPECTED_DB (%s), pero pertenece a Atlas. Continuando...' % (db, EXPECTED_DB))
        else:
            raise Exception('BASE NO AUTORIZADA: %s (se esperaba %s).' % (db, EXPECTED_DB))


def get_company(name=None):
    name = name if name is not None else COMPANY_NAME
    companies = env['res.company'].search([('name', 'ilike', name)]) if name else env.company
    if not companies:
        print('!! No se encontró compañía ilike %r' % name)
        return env['res.company']
    return companies[0]


def find_user(login):
    return env['res.users'].with_context(active_test=False).search([('login', '=ilike', login.strip())], limit=1)


def resolve_atlas_module():
    """Usa atlas_security_approvals si está instalado; si no, studio_customization (ya instalado)."""
    installed = env['ir.module.module'].search_count([
        ('name', '=', 'atlas_security_approvals'),
        ('state', '=', 'installed'),
    ])
    return 'atlas_security_approvals' if installed else 'studio_customization'


def ensure_xmlid(mod, xmlid, model, vals, fallback_domain=None, silent=False):
    """Busca por XML ID; si no, por dominio; si no, crea. Garantiza ir.model.data."""
    IMD = env['ir.model.data'].sudo()
    rec = env.ref('%s.%s' % (mod, xmlid), raise_if_not_found=False)
    if rec:
        rec.sudo().write(vals)
        if not silent:
            print('  [actualizado]     %s.%s (id=%s)' % (mod, xmlid, rec.id))
        return rec
    if fallback_domain:
        rec = env[model].with_context(active_test=False).sudo().search(fallback_domain, limit=1)
    if rec:
        rec.sudo().write(vals)
        if not silent:
            print('  [vinculado XMLID] %s.%s (id=%s)' % (mod, xmlid, rec.id))
    else:
        rec = env[model].sudo().create(vals)
        if not silent:
            print('  [creado]          %s.%s (id=%s)' % (mod, xmlid, rec.id))
    existing_imd = IMD.search([('module', '=', mod), ('name', '=', xmlid)], limit=1)
    if existing_imd:
        existing_imd.write({'model': model, 'res_id': rec.id, 'noupdate': True})
    else:
        IMD.create({
            'module': mod,
            'name': xmlid,
            'model': model,
            'res_id': rec.id,
            'noupdate': True,
        })
    return rec


def apply_atlas_configuration(verbose=True):
    """Aplica de forma idempotente:
    1) Categoría y grupos Atlas
    2) Usuarios (multi-compañía, permisos, notification_type='inbox')
    3) Contacto particular del circuito de Compras
    4) Reglas Studio (Ventas + Compras solo contacto tercero)
    5) Automatización base.automation para @mención en bandeja 💬 al solicitar aprobación

    NO hace commit ni rollback (eso lo decide el script llamador según DRY_RUN/APPLY).
    """
    mod = resolve_atlas_module()
    company_bg = get_company(COMPANY_NAME)
    company_1066 = get_company(COMPANY_1066_NAME)
    if not company_bg or not company_1066:
        raise Exception('Faltan compañías BG (%s) o 1066 (%s)' % (bool(company_bg), bool(company_1066)))

    if verbose:
        sub('1. Categoría y grupos Atlas (módulo XMLID: %s)' % mod)
    cat = ensure_xmlid(
        mod,
        ATLAS_CATEGORY[0],
        'ir.module.category',
        {'name': ATLAS_CATEGORY[1], 'sequence': 20},
        [('name', '=', ATLAS_CATEGORY[1])],
        silent=not verbose,
    )
    groups_map = {}
    for g_xmlid, g_name, local_implied, core_implied in ATLAS_GROUPS:
        imp_ids = []
        for lref in local_implied:
            imp_ids.append(groups_map[lref].id)
        for cref in core_implied:
            g_core = env.ref(cref, raise_if_not_found=False)
            if g_core:
                imp_ids.append(g_core.id)
        grp = ensure_xmlid(
            mod,
            g_xmlid,
            'res.groups',
            {
                'name': g_name,
                'category_id': cat.id,
                'implied_ids': [(6, 0, imp_ids)],
            },
            [('name', '=', g_name), '|', ('category_id', '=', cat.id), ('category_id', '=', False)],
            silent=not verbose,
        )
        groups_map[g_xmlid] = grp

    if verbose:
        sub('2. Usuarios Atlas (multi-compañía, permisos y notification_type=inbox)')
    Users = env['res.users'].with_context(active_test=False)
    user_map = {}
    role_group_ids_all = [groups_map[r].id for r in (
        'group_role_operador',
        'group_role_resp_operaciones',
        'group_role_administrativo',
        'group_role_resp_administracion',
        'group_role_resp_general',
        'group_atlas_can_unlink',
        'group_atlas_aprob_venta',
        'group_atlas_aprob_compra',
        'group_atlas_can_manage_contacts',
        'group_atlas_can_manage_products',
    )]

    for login, cfg in USERS_CONFIG.items():
        allowed_cos = [company_bg.id] if not cfg['allow_1066'] else [company_bg.id, company_1066.id]
        u = find_user(login)
        if not u:
            u = Users.with_context(no_reset_password=True).sudo().create({
                'name': cfg['name'],
                'login': login,
                'email': login,
                'company_id': company_bg.id,
                'company_ids': [(6, 0, allowed_cos)],
                'notification_type': cfg['notification_type'],
                'groups_id': [(6, 0, [env.ref('base.group_user').id])],
            })
            if verbose:
                print('  [creado]      %-35s (id=%s, notif=%s, cias=%s)' % (
                    login, u.id, u.notification_type, u.company_ids.mapped('name')
                ))
        else:
            write_vals = {
                'active': True,
                'company_id': company_bg.id,
                'company_ids': [(6, 0, allowed_cos)],
                'notification_type': cfg['notification_type'],
            }
            u.sudo().write(write_vals)
            if verbose:
                print('  [actualizado] %-35s (id=%s, notif=%s, cias=%s)' % (
                    login, u.id, u.notification_type, u.company_ids.mapped('name')
                ))

        # Limpiar roles Atlas previos + grupos denegados
        to_remove = [gid for gid in role_group_ids_all if gid in u.groups_id.ids]
        for x in cfg.get('disallowed_apps', []):
            g = env.ref(x, raise_if_not_found=False)
            if g and g.id in u.groups_id.ids:
                to_remove.append(g.id)
        if to_remove:
            u.sudo().write({'groups_id': [(3, gid) for gid in set(to_remove)]})

        # Agregar apps + rol Atlas
        to_add = [groups_map[cfg['role']].id]
        for x in cfg.get('apps', []):
            g = env.ref(x, raise_if_not_found=False)
            if g:
                to_add.append(g.id)
            elif verbose:
                print('    ⚠ Grupo app no encontrado: %s' % x)
        u.sudo().write({'groups_id': [(4, gid) for gid in set(to_add)]})

        # Re-verificar denegados (por si algún grupo implicado reintrodujo algo)
        still_disallowed = []
        for x in cfg.get('disallowed_apps', []):
            g = env.ref(x, raise_if_not_found=False)
            if g and g in u.groups_id:
                still_disallowed.append(g.id)
        if still_disallowed:
            u.sudo().write({'groups_id': [(3, gid) for gid in set(still_disallowed)]})

        if not is_production_db() and SET_STAGING_PASSWORDS:
            u.sudo().write({'password': TEST_PASSWORD})

        user_map[login] = u

    if verbose:
        sub('3. Contacto particular del circuito de Compras')
    ar_country = env.ref('base.ar', raise_if_not_found=False)
    partner_vals = {
        'name': CONTACTO_CIRCUITO_COMPRA,
        'is_company': True,
        'active': True,
        'company_id': company_bg.id,
        'supplier_rank': 1,
        'street': CONTACTO_STREET,
        'city': CONTACTO_CITY,
    }
    if ar_country:
        partner_vals['country_id'] = ar_country.id
    if CONTACTO_CUIT:
        partner_vals['vat'] = CONTACTO_CUIT
        cuit_type = env.ref('l10n_ar.it_cuit', raise_if_not_found=False)
        if cuit_type and has_field('res.partner', 'l10n_latam_identification_type_id'):
            partner_vals['l10n_latam_identification_type_id'] = cuit_type.id

    partner_tercero = ensure_xmlid(
        mod,
        'atlas_partner_tercero_circuito',
        'res.partner',
        partner_vals,
        [('name', '=', CONTACTO_CIRCUITO_COMPRA)],
        silent=not verbose,
    )

    if verbose:
        sub('4. Reglas Studio Approval (Ventas + Compras solo contacto tercero)')
    notif_venta_users = env['res.users'].browse([user_map[l].id for l in NOTIF_VENTA_LOGINS if l in user_map])
    notif_compra_users = env['res.users'].browse([user_map[l].id for l in NOTIF_COMPRA_LOGINS if l in user_map])

    rule_venta_vals = {
        'name': RULE_VENTA_NAME,
        'model_id': env['ir.model']._get_id('sale.order'),
        'method': 'action_confirm',
        'approval_group_id': groups_map['group_atlas_aprob_venta'].id,
        'domain': False,
        'message': 'Aprobación de Orden de Venta requerida (notifica a Hernán F. y Eugenia)',
        'approver_ids': [(6, 0, notif_venta_users.ids)],
        'users_to_notify': [(6, 0, notif_venta_users.ids)],
        'active': True,
    }
    rule_so = ensure_xmlid(
        mod,
        'rule_approval_sale_order_atlas',
        'studio.approval.rule',
        rule_venta_vals,
        [('name', '=', RULE_VENTA_NAME)],
        silent=not verbose,
    )
    rule_so.invalidate_recordset(['approver_ids', 'approver_log_ids'])
    if set(rule_so.approver_ids.ids) != set(notif_venta_users.ids):
        rule_so.sudo().write({'approver_ids': [(6, 0, notif_venta_users.ids)]})

    domain_compra = str([('partner_id', '=', partner_tercero.id)])
    rule_compra_vals = {
        'name': RULE_COMPRA_NAME,
        'model_id': env['ir.model']._get_id('purchase.order'),
        'method': 'button_confirm',
        'approval_group_id': groups_map['group_atlas_aprob_compra'].id,
        'domain': domain_compra,
        'message': 'Aprobación de Compra a Tercero (%s) requerida por Eugenia o Hernán F.' % partner_tercero.name,
        'approver_ids': [(6, 0, notif_compra_users.ids)],
        'users_to_notify': [(6, 0, notif_compra_users.ids)],
        'active': True,
    }
    rule_po = ensure_xmlid(
        mod,
        'rule_approval_purchase_order_atlas',
        'studio.approval.rule',
        rule_compra_vals,
        [('name', '=', RULE_COMPRA_NAME)],
        silent=not verbose,
    )
    rule_po.invalidate_recordset(['approver_ids', 'approver_log_ids'])
    if set(rule_po.approver_ids.ids) != set(notif_compra_users.ids):
        rule_po.sudo().write({'approver_ids': [(6, 0, notif_compra_users.ids)]})

    # Archivar reglas [ATLAS] viejas que ya no correspondan
    stale = env['studio.approval.rule'].sudo().search([
        ('name', '=like', '[ATLAS]%'),
        ('id', 'not in', [rule_so.id, rule_po.id]),
        ('active', '=', True),
    ])
    if stale:
        stale.write({'active': False})
        if verbose:
            print('  [archivadas]      reglas viejas: %s' % stale.mapped('name'))

    if verbose:
        sub('5. Automatización base.automation para @mención en bandeja 💬 al solicitar aprobación')
    req_model_id = env['ir.model']._get_id('studio.approval.request')
    auto_vals = {
        'name': AUTO_NOTIF_NAME,
        'model_id': req_model_id,
        'trigger': 'on_create',
        'active': True,
    }
    auto = ensure_xmlid(
        mod,
        'atlas_auto_notify_approval_request',
        'base.automation',
        auto_vals,
        [('name', '=', AUTO_NOTIF_NAME)],
        silent=not verbose,
    )

    srv_vals = {
        'name': AUTO_NOTIF_NAME,
        'model_id': req_model_id,
        'state': 'code',
        'code': AUTO_NOTIF_SERVER_CODE,
    }
    if has_field('ir.actions.server', 'usage'):
        srv_vals['usage'] = 'base_automation'
    if has_field('ir.actions.server', 'base_automation_id'):
        srv_vals['base_automation_id'] = auto.id

    srv = ensure_xmlid(
        mod,
        'atlas_srv_notify_approval_request',
        'ir.actions.server',
        srv_vals,
        [('name', '=', AUTO_NOTIF_NAME), ('model_id', '=', req_model_id)],
        silent=not verbose,
    )
    # Asegurar vínculo y forzar registro del hook de base.automation en el proceso actual
    auto_write_vals = {'active': True}
    if has_field('base.automation', 'action_server_ids'):
        auto_write_vals['action_server_ids'] = [(6, 0, [srv.id])]
    auto.sudo().write(auto_write_vals)

    env.flush_all()
    (rule_so | rule_po).invalidate_recordset(['approver_ids', 'approver_log_ids', 'users_to_notify', 'can_validate'])

    return {
        'mod': mod,
        'company_bg': company_bg,
        'company_1066': company_1066,
        'groups': groups_map,
        'users': user_map,
        'partner_tercero': partner_tercero,
        'rule_so': rule_so,
        'rule_po': rule_po,
        'auto': auto,
        'srv': srv,
    }
