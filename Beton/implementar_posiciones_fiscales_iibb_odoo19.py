#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IMPLEMENTACIÓN Y VINCULACIÓN DE POSICIONES FISCALES DE PERCEPCIONES / RETENCIONES
Versión: Odoo 19.0+e | Localización Argentina (l10n_ar_tax / ingadhoc) | Odoo.sh
Empresa: BETON SRL (ID: 1)
================================================================================

ARQUITECTURA DE LOCALIZACIÓN ARGENTINA EN ODOO 19:
  1. Posiciones Fiscales Base (Condición de IVA / AFIP):
     - 'AR Domestic' (RI), 'Consumidor Final', 'Exento', 'Monotributo', 'Exterior'.
     - Campo 'l10n_ar_tax_type' = 'none'.
     - 'auto_apply' = True.
     - 'l10n_ar_afip_responsibility_type_ids' vinculado con la responsabilidad AFIP.
     - Se asignan AUTOMÁTICAMENTE a los contactos según su CUIT / Tipo de Responsabilidad.

  2. Posiciones Fiscales de Percepciones / Retenciones provinciales (IIBB):
     - Ejemplos: '1% IIBB Salta', '1.6% IIBB Jujuy', '2.5% IIBB Tucumán'.
     - Campo 'l10n_ar_tax_type' = 'perception' (Ventas) o 'withholding' (Compras).
     - Líneas en 'l10n_ar_tax_ids' (modelo 'account.fiscal.position.l10n_ar_tax'):
         • tax_type = 'perception' (o 'withholding')
         • tax_group_id = Grupo de impuesto provincial (ej. Perc IIBB Salta)
         • aliquot = Alícuota correspondiente (%)
         • default_tax_id = Impuesto de percepción (ej. [374] 1% IIBB Salta)
     - Limpieza de 'original_tax_ids' en 'account.tax': las percepciones se suman, no
       se sustituyen a sí mismas ('[374] Replaces [374]' era una anomalía de migración).

  3. Asignación a Contactos (res.partner):
     - Contactos sujetos a percepción fija llevan su Posición Fiscal provincial asignada
       en 'property_account_position_id' (o mediante padrón mensual ARBA/AGIP).

USO EN ODOO.SH:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < implementar_posiciones_fiscales_iibb_odoo19.py
"""

import re
import sys

if 'env' not in globals():
    raise RuntimeError("Este script debe ejecutarse dentro de 'odoo-bin shell'.")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False                  # True: Simula y ejecuta rollback(). False: Aplica commit().
COMPANY_ID = 1                  # BETON SRL
AJUSTAR_POSICIONES_BASE = True  # Vincula AFIP RI y crea/vincula Consumidor Final
CONFIGURAR_LINEAS_L10N = True   # Crea las líneas en 'l10n_ar_tax_ids' para cada posición de IIBB
LIMPIAR_REPLACES_TAX = True     # Elimina autoreemplazo erróneo (original_tax_ids == tax_id)
ASIGNAR_CONTACTOS_BASE = True   # Asigna posición base según AFIP a contactos sin posición

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def extract_aliquot_from_name(name):
    """Extrae el porcentaje del nombre, ej '1% IIBB Salta' -> 1.0, '0.38%' -> 0.38"""
    match = re.search(r'([0-9]+(?:[\.,][0-9]+)?)\s*%', name)
    if match:
        val_str = match.group(1).replace(',', '.')
        try:
            return float(val_str)
        except ValueError:
            pass
    return None

def execute():
    company = env['res.company'].browse(COMPANY_ID)
    if not company.exists():
        company = env.company

    print("\n" + "=" * 80)
    print(" IMPLEMENTACIÓN DE POSICIONES FISCALES Y RET/PERC - ODOO 19 ".center(80, "="))
    print(f" Compañía: [{company.id}] {company.name} | Localización: l10n_ar_tax ".center(80, "="))
    print(f" MODO: {'[DRY-RUN - SIMULACIÓN SIN CAMBIOS]' if DRY_RUN else '[*** LIVE - APLICANDO CAMBIOS ***]'} ".center(80, "="))
    print("=" * 80 + "\n")

    country_ar = env.ref('base.ar', raise_if_not_found=False) or env['res.country'].search([('code', '=', 'AR')], limit=1)

    # --------------------------------------------------------------------------
    # FASE 1: POSICIONES FISCALES BASE (CONDICIÓN AFIP / IVA GENERAL)
    # --------------------------------------------------------------------------
    print("--- FASE 1: Asegurar Posiciones Fiscales Base (Condición IVA / AFIP) ---")
    
    # 1.1 Posición AR Domestic (IVA Responsable Inscripto)
    fp_domestic = env['account.fiscal.position'].search([
        ('company_id', 'in', [company.id, False]),
        ('name', '=', 'AR Domestic'),
    ], limit=1)
    
    resp_ri = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '1')], limit=1) # IVA Responsable Inscripto
    if fp_domestic and resp_ri and AJUSTAR_POSICIONES_BASE:
        fp_domestic.write({
            'l10n_ar_tax_type': 'none',
            'auto_apply': True,
        })
        if resp_ri not in fp_domestic.l10n_ar_afip_responsibility_type_ids:
            fp_domestic.write({'l10n_ar_afip_responsibility_type_ids': [(4, resp_ri.id)]})
        log(f"Posición Base [{fp_domestic.id}] 'AR Domestic' -> Tipo 'none' | AFIP: '{resp_ri.name}'")

    # 1.2 Posición Consumidor Final
    resp_cf = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '5')], limit=1) # Consumidor Final
    fp_cf = env['account.fiscal.position'].search([
        ('company_id', 'in', [company.id, False]),
        '|',
        ('name', 'ilike', 'Consumidor Final'),
        ('name', 'ilike', 'Consumer'),
    ], limit=1)

    if not fp_cf and AJUSTAR_POSICIONES_BASE and resp_cf:
        fp_cf = env['account.fiscal.position'].create({
            'name': 'Consumidor Final',
            'auto_apply': True,
            'company_id': company.id,
            'country_id': country_ar.id if country_ar else False,
            'l10n_ar_tax_type': 'none',
            'l10n_ar_afip_responsibility_type_ids': [(4, resp_cf.id)],
        })
        log(f"Creada Posición Base [{fp_cf.id}] 'Consumidor Final' -> Tipo 'none' | AFIP: '{resp_cf.name}'")
    elif fp_cf and AJUSTAR_POSICIONES_BASE:
        fp_cf.write({'l10n_ar_tax_type': 'none', 'auto_apply': True})
        if resp_cf and resp_cf not in fp_cf.l10n_ar_afip_responsibility_type_ids:
            fp_cf.write({'l10n_ar_afip_responsibility_type_ids': [(4, resp_cf.id)]})
        log(f"Posición Base [{fp_cf.id}] '{fp_cf.name}' -> Tipo 'none' | AFIP: '{resp_cf.name}'")

    # --------------------------------------------------------------------------
    # FASE 2: LIMPIEZA DE 'original_tax_ids' (REPLACES ERRÓNEO EN IMPUESTOS DE IIBB)
    # --------------------------------------------------------------------------
    if LIMPIAR_REPLACES_TAX:
        print("\n--- FASE 2: Saneamiento de 'original_tax_ids' en Impuestos de Percepción ---")
        taxes_iibb = env['account.tax'].search([
            ('company_id', '=', company.id),
            '|', '|',
            ('name', 'ilike', 'IIBB'),
            ('name', 'ilike', 'Perc'),
            ('description', 'ilike', 'Perc'),
        ])
        cleaned_taxes = 0
        for t in taxes_iibb:
            # Si el impuesto se reemplaza a sí mismo o tiene original_tax_ids erróneo
            if t in t.original_tax_ids:
                t.write({'original_tax_ids': [(3, t.id)]})
                log(f"Impuesto [{t.id}] '{t.name}': Eliminado autoreemplazo ('Replaces' a sí mismo).")
                cleaned_taxes += 1
        print(f"Total impuestos de percepción saneados: {cleaned_taxes}")

    # --------------------------------------------------------------------------
    # FASE 3: CONFIGURACIÓN DE POSICIONES FISCALES DE PERCEPCIÓN DE IIBB (v19)
    # --------------------------------------------------------------------------
    print("\n--- FASE 3: Configuración de Posiciones de IIBB en 'l10n_ar_tax_ids' ---")
    fp_iibb_list = env['account.fiscal.position'].search([
        ('company_id', 'in', [company.id, False]),
        '|', '|', '|',
        ('name', 'ilike', 'IIBB'),
        ('name', 'ilike', 'Salta'),
        ('name', 'ilike', 'Jujuy'),
        ('name', 'ilike', 'Tucuman'),
    ])

    print(f"Se encontraron {len(fp_iibb_list)} Posiciones Fiscales de IIBB para configurar.")

    L10nArTax = env['account.fiscal.position.l10n_ar_tax']
    configured_fps = 0

    for fp in fp_iibb_list:
        target_aliquot = extract_aliquot_from_name(fp.name)
        sale_taxes = fp.tax_ids.filtered(lambda t: t.type_tax_use == 'sale')

        if not sale_taxes:
            # Buscar por nombre similar
            found_tax = env['account.tax'].search([
                ('company_id', '=', company.id),
                ('type_tax_use', '=', 'sale'),
                ('name', '=', fp.name),
            ], limit=1)
            if found_tax:
                sale_taxes = found_tax
            else:
                sale_taxes = fp.tax_ids[:1]

        if not sale_taxes:
            log(f"Posición [{fp.id}] '{fp.name}': SIN impuesto de venta vinculado en tax_ids. Omitida.", "WARN")
            continue

        # Agrupar impuestos por tax_group_id para evitar violación de _check_tax_group_overlap
        taxes_by_group = {}
        for t in sale_taxes:
            tg = t.tax_group_id
            if tg not in taxes_by_group:
                taxes_by_group[tg] = []
            taxes_by_group[tg].append(t)

        chosen_taxes = []
        for tg, t_list in taxes_by_group.items():
            if len(t_list) == 1:
                chosen_taxes.append(t_list[0])
            else:
                best = None
                if target_aliquot is not None:
                    for cand in t_list:
                        if abs(cand.amount - target_aliquot) < 0.001:
                            best = cand
                            break
                if not best:
                    for cand in t_list:
                        if cand.name.lower() in fp.name.lower() or fp.name.lower() in cand.name.lower():
                            best = cand
                            break
                if not best:
                    best = t_list[0]
                chosen_taxes.append(best)

        if CONFIGURAR_LINEAS_L10N:
            # 1. Seteamos el tipo de posición fiscal
            fp.write({
                'l10n_ar_tax_type': 'perception',
                'auto_apply': False,  # Las percepciones específicas no se autoaplican por país
            })

            # 2. Limpiamos líneas anteriores si las hubiera
            fp.l10n_ar_tax_ids.unlink()

            # 3. Creamos la línea para cada impuesto elegido (1 por grupo de impuesto)
            for tax_dest in chosen_taxes:
                aliquot = tax_dest.amount if tax_dest.amount else (target_aliquot or 0.0)
                tax_group = tax_dest.tax_group_id

                line_vals = {
                    'fiscal_position_id': fp.id,
                    'tax_type': 'perception',
                    'default_tax_id': tax_dest.id,
                    'tax_group_id': tax_group.id if tax_group else False,
                    'aliquot': aliquot,
                }
                L10nArTax.create(line_vals)
                log(f"Posición [{fp.id}] '{fp.name}': Creada línea L10N -> Grupo: '{tax_group.name if tax_group else 'N/A'}' | Alícuota: {aliquot}% | Impuesto: [{tax_dest.id}] {tax_dest.name}")

            # Sincronizamos tax_ids de la posición fiscal para mantener coherencia
            fp.write({'tax_ids': [(6, 0, [t.id for t in chosen_taxes])]})
            configured_fps += 1

    print(f"Total Posiciones Fiscales de IIBB configuradas: {configured_fps}")

    # --------------------------------------------------------------------------
    # FASE 4: ASIGNACIÓN DE POSICIÓN FISCAL BASE EN CONTACTOS (res.partner)
    # --------------------------------------------------------------------------
    if ASIGNAR_CONTACTOS_BASE:
        print("\n--- FASE 4: Sincronización de Contactos Comerciales con Posición Base ---")
        partners = env['res.partner'].search([
            ('active', '=', True),
            ('parent_id', '=', False),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', company.id),
        ])

        # Mapeo de Resp. AFIP -> Posición Base
        mapping_base = {
            '1': fp_domestic,  # Responsable Inscripto -> AR Domestic
            '5': fp_cf,        # Consumidor Final -> Consumidor Final
        }

        updated_partners = 0
        for p in partners:
            if not p.l10n_ar_afip_responsibility_type_id:
                continue

            code = p.l10n_ar_afip_responsibility_type_id.code
            target_fp = mapping_base.get(code)

            # Solo asignamos si no tiene posición fiscal asignada
            if target_fp and not p.property_account_position_id:
                p.write({'property_account_position_id': target_fp.id})
                log(f"Contacto [{p.id}] {p.name}: Asignada Posición Base '{target_fp.name}'")
                updated_partners += 1
            elif p.property_account_position_id:
                log(f"Contacto [{p.id}] {p.name}: Ya tiene posición asignada ('{p.property_account_position_id.name}')", "DEBUG")

        print(f"Total contactos con Posición Base asignada: {updated_partners}")

    # --------------------------------------------------------------------------
    # FASE 5: TRANSACCIÓN FINAL
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    if DRY_RUN:
        env.cr.rollback()
        print(">> [DRY-RUN]: SE EJECUTÓ ROLLBACK(). NINGÚN CAMBIO FUE GUARDADO EN LA BASE.")
        print(">> Para persistir los cambios definitivamente:")
        print("    1. Abre 'implementar_posiciones_fiscales_iibb_odoo19.py'")
        print("    2. Cambia 'DRY_RUN = False'")
        print("    3. Vuelve a ejecutar el script en la terminal de Odoo.sh.")
    else:
        env.cr.commit()
        print(">> [LIVE]: SE EJECUTÓ COMMIT() CON ÉXITO. POSICIONES E IMPUESTOS ACTUALIZADOS.")
    print("=" * 80 + "\n")

if __name__ == '__main__' or 'env' in globals():
    execute()

