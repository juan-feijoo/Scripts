#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE AUDITORÍA Y CARGA: IMPUESTOS (PERCEPCIONES), POSICIONES FISCALES Y CONTACTOS
Localización: Argentina (l10n_ar)
Compatibilidad: Odoo 17.0+e / 18.0+e / 19.0+e (Enterprise - Odoo.sh)
================================================================================

MODO DE USO EN ODOO.SH:
  1) Ejecución directa en odoo-bin shell:
     odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < auditoria_impuestos_posiciones_fiscales.py

  2) O dentro de la shell interactiva de Odoo:
     >>> exec(open('auditoria_impuestos_posiciones_fiscales.py').read())

CONFIGURACIÓN:
  - DRY_RUN = True  -> Modo simulación (hace rollback al finalizar, no altera la base).
  - DRY_RUN = False -> Persiste los cambios generados (env.cr.commit()).
"""

import logging
import sys

# Si se ejecuta fuera de odoo shell sin 'env' definido
if 'env' not in globals():
    raise RuntimeError(
        "Este script debe ejecutarse dentro del entorno 'odoo-bin shell' "
        "donde la variable de contexto 'env' esté inicializada."
    )

_logger = logging.getLogger("odoo.audit.l10n_ar")

# ==============================================================================
# PARÁMETROS GENERALES Y CONFIGURACIÓN
# ==============================================================================
DRY_RUN = True                # True: Solo simula y reporta (Rollback). False: Aplica cambios (Commit).
COMPANY_ID = None             # None = Compañía activa en env.company, o especificar un ID entero (ej: 1)
AUTO_FIX_PARTNERS = False     # True: Asigna la posición fiscal sugerida según la responsabilidad AFIP a los contactos sin ella
AUTO_CREATE_TAXES = False     # True: Crea impuestos de percepción estándar sugeridos si faltan en la compañía
AUTO_LINK_FISCAL_POS = False  # True: Asocia responsabilidades AFIP a posiciones fiscales si están huérfanas

# Impuestos de percepción habituales en Argentina a auditar / configurar
PERCEPTION_TAX_TEMPLATES = [
    {
        'name': 'Percepción IIBB CABA (AGIP)',
        'description': 'Perc. IIBB CABA',
        'type_tax_use': 'sale',
        'amount_type': 'percent',
        'amount': 0.0,  # Tasa variable según padrón/alícuota o fija base
        'group_name': 'Percepción IIBB CABA',
        'tax_scope': 'consu',
    },
    {
        'name': 'Percepción IIBB Buenos Aires (ARBA)',
        'description': 'Perc. IIBB ARBA',
        'type_tax_use': 'sale',
        'amount_type': 'percent',
        'amount': 0.0,
        'group_name': 'Percepción IIBB ARBA',
        'tax_scope': 'consu',
    },
    {
        'name': 'Percepción IIBB Convenio Multilateral',
        'description': 'Perc. IIBB CM',
        'type_tax_use': 'sale',
        'amount_type': 'percent',
        'amount': 0.0,
        'group_name': 'Percepción IIBB Convenio Multilateral',
        'tax_scope': 'consu',
    },
    {
        'name': 'Percepción IVA 3%',
        'description': 'Perc. IVA 3%',
        'type_tax_use': 'sale',
        'amount_type': 'percent',
        'amount': 3.0,
        'group_name': 'Percepción IVA',
        'tax_scope': 'consu',
    },
    {
        'name': 'Percepción Ganancias 2%',
        'description': 'Perc. Ganancias 2%',
        'type_tax_use': 'sale',
        'amount_type': 'percent',
        'amount': 2.0,
        'group_name': 'Percepción Ganancias',
        'tax_scope': 'consu',
    },
    # Compras (Proveedores)
    {
        'name': 'Percepción IIBB Sufrida CABA',
        'description': 'Perc. IIBB Sufrida CABA',
        'type_tax_use': 'purchase',
        'amount_type': 'percent',
        'amount': 0.0,
        'group_name': 'Percepción IIBB CABA',
        'tax_scope': 'consu',
    },
    {
        'name': 'Percepción IIBB Sufrida ARBA',
        'description': 'Perc. IIBB Sufrida ARBA',
        'type_tax_use': 'purchase',
        'amount_type': 'percent',
        'amount': 0.0,
        'group_name': 'Percepción IIBB ARBA',
        'tax_scope': 'consu',
    },
]

# ==============================================================================
# HELPERS DE IMPRESIÓN Y FORMATO
# ==============================================================================
def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title.upper()} ".center(80, "="))
    print("=" * 80)

def print_sub(title):
    print(f"\n--- {title} " + "-" * (75 - len(title)))

def safe_field_exists(model_name, field_name):
    return field_name in env[model_name]._fields

# ==============================================================================
# AUDITORÍA PRINCIPAL
# ==============================================================================
def run_audit_and_fix():
    company = env['res.company'].browse(COMPANY_ID) if COMPANY_ID else env.company
    print_header(f"AUDITORÍA FISCAL L10N_AR - COMPAÑÍA: [{company.id}] {company.name}")
    print(f">> MODO EJECUCIÓN: {'[DRY-RUN - SIMULACIÓN SIN CAMBIOS]' if DRY_RUN else '[LIVE - APLICANDO CAMBIOS EN BASE DE DATOS]'}")
    print(f">> VERSIÓN ODOO: {env['ir.module.module'].sudo().search([('name', '=', 'base')], limit=1).latest_version or '17+/18+/19+'}")
    
    country_ar = env.ref('base.ar', raise_if_not_found=False)
    if not country_ar:
        country_ar = env['res.country'].search([('code', '=', 'AR')], limit=1)

    # --------------------------------------------------------------------------
    # 1. VERIFICACIÓN DE MÓDULOS DE LOCALIZACIÓN INSTALADOS
    # --------------------------------------------------------------------------
    print_sub("1. Verificación de Módulos Instalados")
    modules_to_check = [
        'l10n_ar',
        'l10n_ar_edi',
        'l10n_ar_withholding',
        'l10n_ar_reports',
        'account',
        'account_accountant',
    ]
    for mod in modules_to_check:
        m = env['ir.module.module'].sudo().search([('name', '=', mod)], limit=1)
        state = m.state if m else 'no instalado'
        print(f"  • Módulo {mod:<22}: {state.upper()}")

    # --------------------------------------------------------------------------
    # 2. AUDITORÍA DE GRUPOS DE IMPUESTOS Y PERCEPCIONES
    # --------------------------------------------------------------------------
    print_sub("2. Auditoría de Grupos de Impuestos y Percepciones (account.tax)")
    existing_tax_groups = env['account.tax.group'].search([('company_id', 'in', [company.id, False])])
    print(f"  Total Tax Groups encontrados: {len(existing_tax_groups)}")
    
    # Búsqueda de impuestos de tipo percepción
    perception_taxes = env['account.tax'].search([
        ('company_id', '=', company.id),
        '|', '|', '|',
        ('name', 'ilike', 'percep'),
        ('description', 'ilike', 'perc'),
        ('tax_group_id.name', 'ilike', 'percep'),
        ('tax_group_id.name', 'ilike', 'iibb'),
    ])
    
    print(f"  Impuestos vinculados a Percepciones/IIBB detectados: {len(perception_taxes)}")
    for t in perception_taxes:
        print(f"    - [{t.id}] {t.name} | Uso: {t.type_tax_use:<8} | Tipo: {t.amount_type:<7} | Valor: {t.amount}% | Grupo: {t.tax_group_id.name}")

    if AUTO_CREATE_TAXES:
        print("\n  >> Evaluando creación de impuestos de percepción faltantes...")
        for tpl in PERCEPTION_TAX_TEMPLATES:
            existing = env['account.tax'].search([
                ('company_id', '=', company.id),
                ('name', '=', tpl['name']),
                ('type_tax_use', '=', tpl['type_tax_use']),
            ], limit=1)
            
            if not existing:
                # Buscar o crear tax group
                group = env['account.tax.group'].search([
                    ('company_id', 'in', [company.id, False]),
                    ('name', '=', tpl['group_name']),
                ], limit=1)
                
                if not group:
                    group_vals = {
                        'name': tpl['group_name'],
                        'company_id': company.id,
                    }
                    if safe_field_exists('account.tax.group', 'country_id') and country_ar:
                        group_vals['country_id'] = country_ar.id
                    group = env['account.tax.group'].create(group_vals)
                    print(f"    [+ CREADO] Tax Group: '{group.name}'")

                tax_vals = {
                    'name': tpl['name'],
                    'description': tpl['description'],
                    'type_tax_use': tpl['type_tax_use'],
                    'amount_type': tpl['amount_type'],
                    'amount': tpl['amount'],
                    'tax_group_id': group.id,
                    'company_id': company.id,
                }
                if safe_field_exists('account.tax', 'tax_scope'):
                    tax_vals['tax_scope'] = tpl['tax_scope']
                if safe_field_exists('account.tax', 'country_id') and country_ar:
                    tax_vals['country_id'] = country_ar.id

                new_tax = env['account.tax'].create(tax_vals)
                print(f"    [+ CREADO] Impuesto: [{new_tax.id}] {new_tax.name} ({new_tax.type_tax_use})")
            else:
                print(f"    [OK] Impuesto ya existe: [{existing.id}] {existing.name}")

    # --------------------------------------------------------------------------
    # 3. AUDITORÍA DE POSICIONES FISCALES Y RESPONSABILIDADES AFIP
    # --------------------------------------------------------------------------
    print_sub("3. Auditoría de Posiciones Fiscales (account.fiscal.position)")
    fiscal_positions = env['account.fiscal.position'].search([
        ('company_id', 'in', [company.id, False])
    ])
    print(f"  Posiciones Fiscales configuradas en la compañía: {len(fiscal_positions)}")
    
    has_afip_resp_field = safe_field_exists('account.fiscal.position', 'l10n_ar_afip_responsibility_type_ids')
    
    for fp in fiscal_positions:
        resp_names = []
        if has_afip_resp_field:
            resp_names = fp.l10n_ar_afip_responsibility_type_ids.mapped('name')
        mapped_taxes_count = len(fp.tax_ids)
        print(f"  • [{fp.id}] {fp.name}")
        print(f"      Auto-apply: {getattr(fp, 'auto_apply', False)} | Mapeo de Impuestos: {mapped_taxes_count}")
        print(f"      Resp. AFIP vinculadas: {', '.join(resp_names) if resp_names else '[NINGUNA VINCULADA]'}")

    # Mapeo sugerido estándar de Responsabilidades AFIP -> Posiciones Fiscales
    # Responsabilidades clave:
    # 1: IVA Responsable Inscripto
    # 4: IVA Sujeto Exento
    # 5: Consumidor Final
    # 6: Responsable Monotributo
    # 9: Cliente del Exterior
    # 10: IVA No Alcanzado
    afip_to_fp_map = {
        '1': 'IVA Responsable Inscripto',
        '4': 'IVA Sujeto Exento',
        '5': 'Consumidor Final',
        '6': 'Responsable Monotributo',
        '9': 'Cliente / Proveedor del Exterior',
    }

    if AUTO_LINK_FISCAL_POS and has_afip_resp_field:
        print("\n  >> Verificando enlace automático de Responsabilidades AFIP a Posiciones Fiscales...")
        for code, expected_fp_name in afip_to_fp_map.items():
            resp = env['l10n_ar.afip.responsibility.type'].search([('code', '=', code)], limit=1)
            if not resp:
                continue
            fp = env['account.fiscal.position'].search([
                ('company_id', 'in', [company.id, False]),
                '|',
                ('name', 'ilike', expected_fp_name),
                ('name', 'ilike', resp.name),
            ], limit=1)
            if fp and resp not in fp.l10n_ar_afip_responsibility_type_ids:
                fp.write({'l10n_ar_afip_responsibility_type_ids': [(4, resp.id)]})
                print(f"    [+ ENLAZADO] Responsabilidad '{resp.name}' agregada a Posición Fiscal '{fp.name}'")

    # --------------------------------------------------------------------------
    # 4. AUDITORÍA DE CONTACTOS (res.partner)
    # --------------------------------------------------------------------------
    print_sub("4. Auditoría de Contactos (res.partner)")
    
    # Evaluamos partners comerciales activos (parent_id == False o commercial_partner_id)
    Partner = env['res.partner']
    commercial_partners = Partner.search([
        ('active', '=', True),
        ('parent_id', '=', False),
        '|',
        ('company_id', '=', False),
        ('company_id', '=', company.id),
    ])
    total_partners = len(commercial_partners)
    print(f"  Total Contactos Principales (Comerciales): {total_partners}")

    # 4.1 Contactos sin Responsabilidad AFIP
    has_partner_afip = safe_field_exists('res.partner', 'l10n_ar_afip_responsibility_type_id')
    if has_partner_afip:
        partners_without_afip = commercial_partners.filtered(lambda p: not p.l10n_ar_afip_responsibility_type_id)
        print(f"  [!] Contactos SIN Responsabilidad AFIP configurada: {len(partners_without_afip)}")
        if partners_without_afip:
            sample = partners_without_afip[:5]
            print(f"      Ejemplos: {', '.join([f'[{p.id}] {p.name}' for p in sample])}")
    else:
        print("  [!] El campo 'l10n_ar_afip_responsibility_type_id' no existe en res.partner (¿Falta l10n_ar?).")

    # 4.2 Contactos sin Posición Fiscal asignada
    partners_without_fp = commercial_partners.filtered(lambda p: not p.property_account_position_id)
    print(f"  [!] Contactos SIN Posición Fiscal asignada: {len(partners_without_fp)}")

    # 4.3 Inconsistencias entre Responsabilidad AFIP y Posición Fiscal
    inconsistent_partners = []
    if has_partner_afip and has_afip_resp_field:
        for p in commercial_partners:
            if p.l10n_ar_afip_responsibility_type_id and p.property_account_position_id:
                fp = p.property_account_position_id
                # Si la posición fiscal tiene responsabilidades configuradas y no incluye la del partner
                if fp.l10n_ar_afip_responsibility_type_ids and p.l10n_ar_afip_responsibility_type_id not in fp.l10n_ar_afip_responsibility_type_ids:
                    inconsistent_partners.append((p, p.l10n_ar_afip_responsibility_type_id, fp))

        print(f"  [!] Contactos con DISCREPANCIA (Resp. AFIP vs Posición Fiscal): {len(inconsistent_partners)}")
        if inconsistent_partners:
            print("      Primeros 5 casos detectados:")
            for p, resp, fp in inconsistent_partners[:5]:
                print(f"        - Contacto: [{p.id}] {p.name} | AFIP: {resp.name} | Pos. Fiscal actual: {fp.name}")

    # 4.4 Verificación de campos especiales de Percepciones / IIBB en Contactos
    print("\n  >> Verificación de campos de Percepción / IIBB en res.partner:")
    custom_perception_fields = [
        'l10n_ar_gross_income_type',         # Tipo de Ingresos Brutos (CM, Local, Exento, etc.)
        'l10n_ar_gross_income_number',       # Nro de Inscripción IIBB
        'l10n_ar_vat_affidavit',             # Declaración jurada de IVA / Percepciones
        'perception_tax_ids',                # Módulos OCA / Adhoc / Custom de percepciones
        'withholding_tax_ids',               # Retenciones aplicables
    ]
    for fld in custom_perception_fields:
        if safe_field_exists('res.partner', fld):
            count_populated = Partner.search_count([(fld, '!=', False)])
            print(f"    • Campo '{fld}': EXISTE en el modelo | Contactos con valor: {count_populated}")
        else:
            print(f"    • Campo '{fld}': No presente en esta instalación.")

    # --------------------------------------------------------------------------
    # 5. CORRECCIÓN AUTOMÁTICA DE CONTACTOS (SI ESTÁ HABILITADO)
    # --------------------------------------------------------------------------
    if AUTO_FIX_PARTNERS and has_partner_afip:
        print_sub("5. Corrección Automática de Contactos")
        fixed_count = 0
        skipped_count = 0

        # Mapeo en memoria de Responsabilidad AFIP -> Posición Fiscal ID
        resp_fp_lookup = {}
        for fp in fiscal_positions:
            if has_afip_resp_field:
                for resp in fp.l10n_ar_afip_responsibility_type_ids:
                    if resp.id not in resp_fp_lookup:
                        resp_fp_lookup[resp.id] = fp

        for p in commercial_partners:
            if not p.l10n_ar_afip_responsibility_type_id:
                skipped_count += 1
                continue

            target_fp = resp_fp_lookup.get(p.l10n_ar_afip_responsibility_type_id.id)
            if not target_fp:
                # Intentar buscar por nombre similar
                target_fp = env['account.fiscal.position'].search([
                    ('company_id', 'in', [company.id, False]),
                    ('name', 'ilike', p.l10n_ar_afip_responsibility_type_id.name),
                ], limit=1)

            if target_fp and p.property_account_position_id != target_fp:
                old_fp_name = p.property_account_position_id.name if p.property_account_position_id else 'Sin asignar'
                p.write({'property_account_position_id': target_fp.id})
                print(f"    [CORREGIDO] Contacto [{p.id}] {p.name}: '{old_fp_name}' -> '{target_fp.name}'")
                fixed_count += 1

        print(f"\n  Resumen Corrección de Contactos: {fixed_count} actualizados, {skipped_count} omitidos sin Resp. AFIP.")

    # --------------------------------------------------------------------------
    # 6. CIERRE DE TRANSACCIÓN (DRY-RUN vs COMMIT)
    # --------------------------------------------------------------------------
    print_header("RESULTADO FINAL Y TRANSACCIÓN")
    if DRY_RUN:
        env.cr.rollback()
        print(">> [DRY-RUN]: SE HA EJECUTADO 'rollback()'. NINGÚN CAMBIO FUE GUARDADO EN LA BASE DE DATOS.")
        print(">> Para persistir los cambios, edita el script y asigna:")
        print("       DRY_RUN = False")
        print("       AUTO_FIX_PARTNERS = True   (si deseas actualizar contactos)")
        print("       AUTO_CREATE_TAXES = True   (si deseas crear los impuestos faltantes)")
        print("       AUTO_LINK_FISCAL_POS = True(si deseas asociar AFIP a posiciones fiscales)")
    else:
        env.cr.commit()
        print(">> [LIVE]: 'commit()' EJECUTADO EXITOSAMENTE. TODOS LOS CAMBIOS FUERON GUARDADOS EN LA BD.")
    print("=" * 80 + "\n")


# Ejecutar la función
if __name__ == '__main__' or 'env' in globals():
    run_audit_and_fix()
