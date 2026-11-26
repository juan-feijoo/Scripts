#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/atlas_aprobaciones
mkdir -p ~/tmp/atlas_aprobaciones/scripts && cd ~/tmp/atlas_aprobaciones
cat > ~/tmp/atlas_aprobaciones/scripts/_lib.py <<'__EOF_AUDIT__'
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
__EOF_AUDIT__
cat > ~/tmp/atlas_aprobaciones/scripts/02_smoke_test_circuitos_rollback.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 02 - Smoke Test end-to-end de notificaciones (🕒 + 💬), aprobación Ventas, Compras Tercero y vínculo relacion_oc_ov
# SIEMPRE ejecuta ROLLBACK al final (nunca deja basura en la base, incluso con APPLY=1).
import odoo

h('02 - SMOKE TEST END-TO-END: NOTIFICACIONES (🕒 + 💬), VENTAS, COMPRAS TERCERO Y RELACIÓN OC<->OV')
print('DB:   %s | Odoo %s' % (env.cr.dbname, odoo.release.version))
print('MODO: %s (este script SIEMPRE hace ROLLBACK de sus registros de prueba)' % ('DRY-RUN' if DRY_RUN else 'POST-APPLY'))

total = 0
passed = 0


def test(cond, desc):
    global total, passed
    total += 1
    if cond:
        passed += 1
        print('  ✔ [PASÓ]  %s' % desc)
    else:
        print('  ✘ [FALLÓ] %s' % desc)


try:
    check_db_safety()

    # Si estamos en DRY-RUN, 01 hizo rollback; aplicamos la config en memoria dentro de esta transacción
    # que igualmente terminará en ROLLBACK. Si estamos en APPLY=1, leemos lo ya commiteado por 01.
    if DRY_RUN:
        print('  ℹ DRY-RUN: aplicando configuración temporal en memoria para testear el circuito completo...')
        ctx = apply_atlas_configuration(verbose=False)
        company_bg = ctx['company_bg']
        company_1066 = ctx['company_1066']
        partner_tercero = ctx['partner_tercero']
        rule_so = ctx['rule_so']
        rule_po = ctx['rule_po']
        u_op = ctx['users']['mandatario@atlasgroup.com.ar']
        u_pac = ctx['users']['hernanpacetti@atlasgroup.com.ar']
        u_adm = ctx['users']['administracion@atlasgroup.com.ar']
        u_euge = ctx['users']['eugeniazanotti@atlasgroup.com.ar']
        u_hf = ctx['users']['hernanfernandez@atlasgroup.com.ar']
    else:
        company_bg = get_company(COMPANY_NAME)
        company_1066 = get_company(COMPANY_1066_NAME)
        partner_tercero = env['res.partner'].sudo().search([('name', '=', CONTACTO_CIRCUITO_COMPRA)], limit=1)
        rule_so = env['studio.approval.rule'].sudo().search([('name', '=', RULE_VENTA_NAME), ('active', '=', True)], limit=1)
        rule_po = env['studio.approval.rule'].sudo().search([('name', '=', RULE_COMPRA_NAME), ('active', '=', True)], limit=1)
        u_op = find_user('mandatario@atlasgroup.com.ar')
        u_pac = find_user('hernanpacetti@atlasgroup.com.ar')
        u_adm = find_user('administracion@atlasgroup.com.ar')
        u_euge = find_user('eugeniazanotti@atlasgroup.com.ar')
        u_hf = find_user('hernanfernandez@atlasgroup.com.ar')

    test(all([company_bg, company_1066, partner_tercero, rule_so, rule_po, u_op, u_pac, u_adm, u_euge, u_hf]),
         'Precondiciones cargadas (compañías, contacto tercero, reglas Studio y 5 usuarios)')

    # Datos auxiliares temporales (se descartan con rollback)
    partner_cliente = env['res.partner'].sudo().create({
        'name': '[SMOKE] Cliente Test',
        'company_id': company_bg.id,
        'customer_rank': 1,
    })
    partner_otro_prov = env['res.partner'].sudo().create({
        'name': '[SMOKE] Otro Proveedor Sin Regla',
        'company_id': company_bg.id,
        'supplier_rank': 1,
    })
    product = env['product.product'].sudo().search([('sale_ok', '=', True), ('purchase_ok', '=', True)], limit=1) \
        or env['product.product'].sudo().search([], limit=1)
    project = env['project.project'].sudo().create({
        'name': '[SMOKE] Proyecto Circuito OC-OV',
        'company_id': company_bg.id,
        'privacy_visibility': 'employees',
    })
    Rule = env['studio.approval.rule']
    expected_notif_partners = {u_hf.partner_id.id, u_euge.partner_id.id}
    expected_notif_logins = {'hernanfernandez@atlasgroup.com.ar', 'eugeniazanotti@atlasgroup.com.ar'}

    # ------------------------------------------------------------------
    # TEST 1: VENTAS -> ACTIVIDAD (🕒) + NOTIFICACIÓN BANDEJA INBOX (💬)
    # ------------------------------------------------------------------
    sub('TEST 1: Aprobación de Orden de Venta (notifica solo Hernán F. y Euge; aprueba también Pacetti)')
    so_vals = {
        'partner_id': partner_cliente.id,
        'user_id': u_op.id,
        'company_id': company_bg.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'name': 'Servicio Smoke Test Venta',
            'product_uom_qty': 1,
            'price_unit': 250000.0,
        })],
    }
    if has_field('sale.order', 'project_id'):
        so_vals['project_id'] = project.id
    so = env['sale.order'].sudo().create(so_vals)
    env.flush_all()

    last_msg_id = env['mail.message'].search([], order='id desc', limit=1).id or 0
    res_so = Rule.with_user(u_op).check_approval('sale.order', so.id, 'action_confirm', False)
    env.flush_all()

    test(not res_so.get('approved'), 'OV: check_approval como Operador bloquea confirmación (approved=False)')

    acts_so = env['mail.activity'].sudo().search([('res_model', '=', 'sale.order'), ('res_id', '=', so.id)])
    act_logins_so = set(acts_so.mapped('user_id.login'))
    test(act_logins_so == expected_notif_logins,
         'OV Actividades (🕒): creadas SOLO para Hernán F. y Euge (actual: %s)' % sorted(act_logins_so))
    test('hernanpacetti@atlasgroup.com.ar' not in act_logins_so,
         'OV Actividades (🕒): Hernán Pacetti NO recibe actividad')

    msgs_so = env['mail.message'].sudo().search([
        ('model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', last_msg_id),
    ], order='id')
    atlas_msgs_so = msgs_so.filtered(lambda m: '[Aprobación requerida]' in strip_html(m.body))
    notifs_so = env['mail.notification'].sudo().search([('mail_message_id', 'in', atlas_msgs_so.ids)])
    inbox_so = notifs_so.filtered(lambda n: n.notification_type == 'inbox' and not n.is_read)
    inbox_partners_so = set(inbox_so.mapped('res_partner_id.id'))
    test(len(atlas_msgs_so) == 1,
         'OV Chatter: exactamente 1 nota [Aprobación requerida] sin duplicar (actual: %s)' % len(atlas_msgs_so))
    test(inbox_partners_so == expected_notif_partners and len(inbox_so) == 2,
         'OV Bandeja 💬 (mail.notification inbox sin leer): 2 exactas para Hernán F. y Euge (actual: %s)' % inbox_so.mapped('res_partner_id.name'))
    test(bool(atlas_msgs_so) and '@' in strip_html(atlas_msgs_so[0].body),
         'OV Chatter: mensaje incluye @mención visible (%s)' % (strip_html(atlas_msgs_so[0].body)[:120] if atlas_msgs_so else '-'))

    # Verificar que Hernán Pacetti SÍ puede aprobar por grupo y eso dispara users_to_notify (inbox)
    last_msg_id2 = env['mail.message'].search([], order='id desc', limit=1).id or 0
    approved_by_pac = rule_so.with_user(u_pac).set_approval(so.id, True)
    env.flush_all()
    test(bool(approved_by_pac), 'OV: Hernán Pacetti aprueba correctamente por grupo (sin haber recibido notificación previa)')

    msgs_so_appr = env['mail.message'].sudo().search([
        ('model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', last_msg_id2),
    ])
    inbox_so_appr = env['mail.notification'].sudo().search([
        ('mail_message_id', 'in', msgs_so_appr.ids),
        ('notification_type', '=', 'inbox'),
    ])
    test(set(inbox_so_appr.mapped('res_partner_id.id')) == expected_notif_partners,
         'OV al aprobar Pacetti: Studio notifica en bandeja 💬 a Hernán F. y Euge (%s)' % inbox_so_appr.mapped('res_partner_id.name'))

    res_so_after = Rule.with_user(u_op).check_approval('sale.order', so.id, 'action_confirm', False)
    test(bool(res_so_after.get('approved')), 'OV: tras aprobación, check_approval devuelve approved=True')

    # ------------------------------------------------------------------
    # TEST 2: COMPRAS A OTRO PROVEEDOR -> NO EXIGE APROBACIÓN
    # ------------------------------------------------------------------
    sub('TEST 2: Compra a proveedor regular (NO es el contacto tercero) -> confirma sin aprobación')
    po_normal = env['purchase.order'].sudo().create({
        'partner_id': partner_otro_prov.id,
        'user_id': u_op.id,
        'company_id': company_bg.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'name': 'Compra regular sin aprobación',
            'product_qty': 1,
            'price_unit': 50000.0,
        })],
    })
    env.flush_all()
    res_po_normal = Rule.with_user(u_op).check_approval('purchase.order', po_normal.id, 'button_confirm', False)
    test(bool(res_po_normal.get('approved')) and not res_po_normal.get('rules'),
         'OC otro proveedor: NO aplica regla de aprobación (approved=True, 0 reglas)')

    # ------------------------------------------------------------------
    # TEST 3: COMPRAS AL CONTACTO TERCERO -> EXIGE APROBACIÓN + NOTIFICA + VÍNCULO relacion_oc_ov
    # ------------------------------------------------------------------
    sub('TEST 3: Compra al contacto tercero + aprobación + vínculo OC <-> OV (relacion_oc_ov)')
    po_vals = {
        'partner_id': partner_tercero.id,
        'user_id': u_op.id,
        'company_id': company_bg.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'name': 'Gasto de tercero - circuito aprobación',
            'product_qty': 1,
            'price_unit': 120000.0,
        })],
    }
    if has_field('purchase.order', 'project_id'):
        po_vals['project_id'] = project.id
    po_terc = env['purchase.order'].sudo().create(po_vals)
    env.flush_all()

    last_msg_po = env['mail.message'].search([], order='id desc', limit=1).id or 0
    res_po_terc = Rule.with_user(u_op).check_approval('purchase.order', po_terc.id, 'button_confirm', False)
    env.flush_all()

    test(not res_po_terc.get('approved'),
         'OC contacto tercero (%s): bloqueada al intentar confirmar como Operador' % partner_tercero.name)

    acts_po = env['mail.activity'].sudo().search([('res_model', '=', 'purchase.order'), ('res_id', '=', po_terc.id)])
    test(set(acts_po.mapped('user_id.login')) == expected_notif_logins,
         'OC Actividades (🕒): creadas para Hernán F. y Euge (%s)' % sorted(acts_po.mapped('user_id.login')))

    msgs_po = env['mail.message'].sudo().search([
        ('model', '=', 'purchase.order'),
        ('res_id', '=', po_terc.id),
        ('id', '>', last_msg_po),
    ])
    atlas_msgs_po = msgs_po.filtered(lambda m: '[Aprobación requerida]' in strip_html(m.body))
    inbox_po = env['mail.notification'].sudo().search([
        ('mail_message_id', 'in', atlas_msgs_po.ids),
        ('notification_type', '=', 'inbox'),
        ('is_read', '=', False),
    ])
    test(len(atlas_msgs_po) == 1,
         'OC Chatter: exactamente 1 nota [Aprobación requerida] sin duplicar (actual: %s)' % len(atlas_msgs_po))
    test(set(inbox_po.mapped('res_partner_id.id')) == expected_notif_partners and len(inbox_po) == 2,
         'OC Bandeja 💬 (mail.notification inbox sin leer): 2 exactas para Hernán F. y Euge (%s)' % inbox_po.mapped('res_partner_id.name'))

    # Eugenia aprueba y se confirma la OC
    approved_po = rule_po.with_user(u_euge).set_approval(po_terc.id, True)
    test(bool(approved_po), 'OC contacto tercero: Eugenia aprueba correctamente')
    res_po_after = Rule.with_user(u_op).check_approval('purchase.order', po_terc.id, 'button_confirm', False)
    test(bool(res_po_after.get('approved')), 'OC contacto tercero: tras aprobación, check_approval devuelve approved=True')

    po_terc.sudo().button_confirm()
    test(po_terc.state in ('purchase', 'done'), 'OC contacto tercero: confirmada (state=%s)' % po_terc.state)

    # Verificar circuito relacion_oc_ov (conectar OC confirmada a OV con el mismo proyecto)
    has_rel = has_field('purchase.order', 'related_sale_order_id') and has_field('sale.order', 'related_purchase_order_ids')
    test(has_rel, 'Módulo relacion_oc_ov: campos related_sale_order_id y related_purchase_order_ids presentes')

    if has_rel:
        # Verificar el dominio exacto de la vista de relacion_oc_ov
        view_domain = [
            ('state', 'in', ('purchase', 'done')),
            ('project_id', '=', project.id),
            '|', ('related_sale_order_id', '=', False),
                 ('related_sale_order_id', '=', so.id),
        ]
        selectable_pos = env['purchase.order'].with_user(u_op).with_company(company_bg).search(view_domain)
        test(po_terc in selectable_pos,
             'relacion_oc_ov: OC confirmada es seleccionable por Operador en la OV (mismo proyecto)')

        # Conectar desde la OV como Operador (usando el inverse de related_purchase_order_ids)
        so.with_user(u_op).with_company(company_bg).write({'related_purchase_order_ids': [(4, po_terc.id)]})
        env.flush_all()
        so.invalidate_recordset()
        po_terc.invalidate_recordset()

        test(po_terc.related_sale_order_id.id == so.id,
             'relacion_oc_ov: PO.related_sale_order_id apunta a la OV (%s)' % po_terc.related_sale_order_id.name)
        test(so.related_purchase_order_count == 1 and po_terc in so.related_purchase_order_ids,
             'relacion_oc_ov: OV muestra related_purchase_order_count=1 y contiene la OC (%s)' % po_terc.name)

    print('\n' + '=' * 100)
    print('RESUMEN SMOKE TEST: %s/%s PRUEBAS EXITOSAS' % (passed, total))
    print('=' * 100)
    if passed != total:
        print('!! ERROR: Fallaron %s pruebas en Smoke Test.' % (total - passed))

except Exception:
    traceback.print_exc(file=sys.stdout)
    print('!! ERROR INESPERADO EN SMOKE TEST')
finally:
    env.cr.rollback()
    print('>> ROLLBACK FINAL EJECUTADO: Ningún dato temporal de prueba fue persistido.')
__EOF_AUDIT__
cat > ~/tmp/atlas_aprobaciones/scripts/03_generar_casos_prueba_ui.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 03 - Genera casos de prueba visuales para validar en UI (solo staging; respeta DRY_RUN / APPLY=1)
import odoo

h('03 - GENERACIÓN DE CASOS DE PRUEBA VISUALES PARA UI (STAGING)')
print('DB:   %s | Odoo %s' % (env.cr.dbname, odoo.release.version))
print('MODO: %s' % ('DRY-RUN (Simulación con ROLLBACK)' if DRY_RUN else 'REAL (APPLY=1 -> COMMIT)'))

try:
    check_db_safety()
    if is_production_db():
        print('  ℹ Base de producción detectada: se omite la creación de documentos demo de UI.')
    else:
        if DRY_RUN:
            print('  ℹ DRY-RUN: aplicando configuración temporal en memoria para simular los casos UI...')
            ctx = apply_atlas_configuration(verbose=False)
            company_bg = ctx['company_bg']
            partner_tercero = ctx['partner_tercero']
            u_op = ctx['users']['mandatario@atlasgroup.com.ar']
            u_euge = ctx['users']['eugeniazanotti@atlasgroup.com.ar']
            u_hf = ctx['users']['hernanfernandez@atlasgroup.com.ar']
        else:
            company_bg = get_company(COMPANY_NAME)
            partner_tercero = env['res.partner'].sudo().search([('name', '=', CONTACTO_CIRCUITO_COMPRA)], limit=1)
            u_op = find_user('mandatario@atlasgroup.com.ar')
            u_euge = find_user('eugeniazanotti@atlasgroup.com.ar')
            u_hf = find_user('hernanfernandez@atlasgroup.com.ar')

        if not (company_bg and partner_tercero and u_op and u_euge and u_hf):
            raise Exception('Faltan usuarios, compañía BG o contacto tercero. Correr Script 01 primero.')

        # 1. Asegurar proyecto, cliente demo y proveedor normal demo
        sub('1. Datos base para pruebas visuales (Proyecto, Cliente Demo y Proveedor Regular)')
        Project = env['project.project'].sudo()
        project = Project.search([('name', '=', PROYECTO_CIRCUITO_NAME), ('company_id', '=', company_bg.id)], limit=1)
        if not project:
            project = Project.create({
                'name': PROYECTO_CIRCUITO_NAME,
                'company_id': company_bg.id,
                'privacy_visibility': 'employees',
            })
            print('  [creado]    Proyecto: %s (id=%s)' % (project.name, project.id))
        else:
            project.write({'privacy_visibility': 'employees'})
            print('  [existente] Proyecto: %s (id=%s)' % (project.name, project.id))

        Partner = env['res.partner'].sudo()
        partner_cliente = Partner.search([('name', '=', CLIENTE_DEMO_NAME)], limit=1)
        if not partner_cliente:
            partner_cliente = Partner.create({
                'name': CLIENTE_DEMO_NAME,
                'is_company': True,
                'company_id': company_bg.id,
                'customer_rank': 1,
                'street': 'Av. Libertador 1000',
                'city': 'Buenos Aires',
            })
            print('  [creado]    Cliente demo: %s (id=%s)' % (partner_cliente.name, partner_cliente.id))
        else:
            print('  [existente] Cliente demo: %s (id=%s)' % (partner_cliente.name, partner_cliente.id))

        partner_normal = Partner.search([('name', '=', PROV_NORMAL_DEMO_NAME)], limit=1)
        if not partner_normal:
            partner_normal = Partner.create({
                'name': PROV_NORMAL_DEMO_NAME,
                'is_company': True,
                'company_id': company_bg.id,
                'supplier_rank': 1,
                'street': 'Av. Santa Fe 1500',
                'city': 'Buenos Aires',
            })
            print('  [creado]    Proveedor regular demo: %s (id=%s)' % (partner_normal.name, partner_normal.id))
        else:
            print('  [existente] Proveedor regular demo: %s (id=%s)' % (partner_normal.name, partner_normal.id))

        Product = env['product.product'].sudo()
        prod = Product.search([('sale_ok', '=', True), ('purchase_ok', '=', True)], limit=1) \
            or Product.search([], limit=1)
        print('  [producto]  %s (id=%s)' % (prod.display_name, prod.id))

        # 2. Limpiar casos demo previos (DEMO-ATLAS-*)
        sub('2. Limpieza de casos demo previos (DEMO-ATLAS-*)')
        old_sos = env['sale.order'].sudo().search([('client_order_ref', '=like', 'DEMO-ATLAS-%')])
        if old_sos:
            old_sos.filtered(lambda s: s.state != 'draft').action_cancel()
            old_sos.unlink()
            print('  Eliminadas %s OV demo anteriores' % len(old_sos))
        old_pos = env['purchase.order'].sudo().search([('partner_ref', '=like', 'DEMO-ATLAS-%')])
        if old_pos:
            if has_field('purchase.order', 'related_sale_order_id'):
                old_pos.write({'related_sale_order_id': False})
            old_pos.filtered(lambda p: p.state != 'draft').button_cancel()
            old_pos.unlink()
            print('  Eliminadas %s OC demo anteriores' % len(old_pos))

        Rule = env['studio.approval.rule']

        # 3. Caso UI A: Orden de Venta pendiente de aprobación (con proyecto compartido)
        sub('3. Caso UI A: Orden de Venta pendiente de aprobación (notifica a Hernán F. y Euge)')
        so_vals = {
            'partner_id': partner_cliente.id,
            'user_id': u_op.id,
            'company_id': company_bg.id,
            'client_order_ref': 'DEMO-ATLAS-OV',
            'note': (
                'CASO UI VENTAS: Creada por Operador. Solicitud de aprobación enviada a Hernán F. y Eugenia '
                '(reloj 🕒 + Bandeja 💬). Una vez confirmada la OC de tercero del mismo proyecto, '
                'vincularla en el campo "Órdenes de Compra relacionadas".'
            ),
            'order_line': [(0, 0, {
                'product_id': prod.id,
                'name': 'Servicio Operativo Integral - Prueba Aprobación Ventas',
                'product_uom_qty': 1,
                'price_unit': 250000.0,
            })],
        }
        if has_field('sale.order', 'project_id'):
            so_vals['project_id'] = project.id
        so_demo = env['sale.order'].sudo().create(so_vals)
        env.flush_all()

        # Disparar solicitud COMO OPERADOR para generar actividad 🕒 + notificación bandeja 💬
        last_msg_so = env['mail.message'].search([], order='id desc', limit=1).id or 0
        res_so = Rule.with_user(u_op).check_approval('sale.order', so_demo.id, 'action_confirm', False)
        env.flush_all()
        acts_so = env['mail.activity'].sudo().search([('res_model', '=', 'sale.order'), ('res_id', '=', so_demo.id)])
        notifs_so = env['mail.notification'].sudo().search([
            ('mail_message_id.model', '=', 'sale.order'),
            ('mail_message_id.res_id', '=', so_demo.id),
            ('mail_message_id', '>', last_msg_so),
            ('notification_type', '=', 'inbox'),
        ])
        print('  ✔ OV %s (id=%s) | approved=%s | proyecto=%s' % (so_demo.name, so_demo.id, res_so.get('approved'), project.name))
        print('    Actividades 🕒: %s' % acts_so.mapped('user_id.login'))
        print('    Bandeja 💬:     %s' % notifs_so.mapped('res_partner_id.name'))

        # 4. Caso UI B: Compra al contacto tercero pendiente de aprobación (mismo proyecto)
        sub('4. Caso UI B: OC a Tercero pendiente de aprobación (circuito contacto particular + relacion_oc_ov)')
        po_terc_vals = {
            'partner_id': partner_tercero.id,
            'user_id': u_op.id,
            'company_id': company_bg.id,
            'partner_ref': 'DEMO-ATLAS-OC-TERCERO',
            'notes': (
                'CASO UI COMPRAS TERCERO: Proveedor = %s. Exige aprobación de Eugenia o Hernán F. '
                'Luego de aprobar y confirmar, abrir la OV %s y seleccionarla en "Órdenes de Compra relacionadas".'
                % (partner_tercero.name, so_demo.name)
            ),
            'order_line': [(0, 0, {
                'product_id': prod.id,
                'name': 'Gasto de Terceros - Requiere Aprobación',
                'product_qty': 1,
                'price_unit': 120000.0,
            })],
        }
        if has_field('purchase.order', 'project_id'):
            po_terc_vals['project_id'] = project.id
        po_terc_demo = env['purchase.order'].sudo().create(po_terc_vals)
        env.flush_all()

        last_msg_po = env['mail.message'].search([], order='id desc', limit=1).id or 0
        res_po = Rule.with_user(u_op).check_approval('purchase.order', po_terc_demo.id, 'button_confirm', False)
        env.flush_all()
        acts_po = env['mail.activity'].sudo().search([('res_model', '=', 'purchase.order'), ('res_id', '=', po_terc_demo.id)])
        notifs_po = env['mail.notification'].sudo().search([
            ('mail_message_id.model', '=', 'purchase.order'),
            ('mail_message_id.res_id', '=', po_terc_demo.id),
            ('mail_message_id', '>', last_msg_po),
            ('notification_type', '=', 'inbox'),
        ])
        print('  ✔ OC Tercero %s (id=%s) | partner=%s | approved=%s | proyecto=%s' % (
            po_terc_demo.name, po_terc_demo.id, partner_tercero.name, res_po.get('approved'), project.name
        ))
        print('    Actividades 🕒: %s' % acts_po.mapped('user_id.login'))
        print('    Bandeja 💬:     %s' % notifs_po.mapped('res_partner_id.name'))

        # 5. Caso UI C: Compra a proveedor regular (NO debe exigir aprobación)
        sub('5. Caso UI C: OC a proveedor regular (debe confirmar directo sin pedir aprobación)')
        po_norm_demo = env['purchase.order'].sudo().create({
            'partner_id': partner_normal.id,
            'user_id': u_op.id,
            'company_id': company_bg.id,
            'partner_ref': 'DEMO-ATLAS-OC-NORMAL',
            'notes': 'CASO UI COMPRAS SIN APROBACIÓN: Proveedor distinto al tercero. Confirmar Pedido debe avanzar directo.',
            'order_line': [(0, 0, {
                'product_id': prod.id,
                'name': 'Insumo Regular - Sin Aprobación',
                'product_qty': 1,
                'price_unit': 35000.0,
            })],
        })
        print('  ✔ OC Regular %s (id=%s) | partner=%s (sin aprobación)' % (
            po_norm_demo.name, po_norm_demo.id, partner_normal.name
        ))

        env.flush_all()
        if DRY_RUN:
            env.cr.rollback()
            print('\n>> DRY-RUN COMPLETADO -> ROLLBACK (casos UI no persistidos aún).')
        else:
            env.cr.commit()
            print('\n>> COMMIT EXITOSO: Casos UI guardados en Staging.')
            print('   - OV pendiente:         %s (ref: DEMO-ATLAS-OV)' % so_demo.name)
            print('   - OC tercero pendiente: %s (ref: DEMO-ATLAS-OC-TERCERO)' % po_terc_demo.name)
            print('   - OC regular libre:     %s (ref: DEMO-ATLAS-OC-NORMAL)' % po_norm_demo.name)
            print('   - Proyecto compartido:  %s' % project.name)
            if SET_STAGING_PASSWORDS:
                print('   - Clave staging:        %s' % TEST_PASSWORD)

except Exception:
    traceback.print_exc(file=sys.stdout)
    env.cr.rollback()
    print('!! ERROR -> ROLLBACK EJECUTADO')
__EOF_AUDIT__
chmod +x ~/tmp/atlas_aprobaciones/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/atlas_aprobaciones:'; ls -R ~/tmp/atlas_aprobaciones | head -50
