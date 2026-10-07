#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
INVESTIGACIÓN Y EXPORTACIÓN/IMPORTACIÓN DE PERCEPCIONES Y POSICIONES FISCALES
Compatible: Odoo 17.0+e / 18.0+e / 19.0+e | Localización Argentina (l10n_ar)
================================================================================

COMPATIBILIDAD CRÍTICA ODOO 18 vs ODOO 19:
  - En Odoo 17 y 18: El mapeo se maneja en el modelo 'account.fiscal.position.tax'
    con campos (position_id, tax_src_id, tax_dest_id).
  - En Odoo 19: 'account.fiscal.position.tax' fue ELIMINADO. La arquitectura es
    Tax-Centric: en cada impuesto (account.tax) se asignan:
      • fiscal_position_ids: Posiciones fiscales donde aplica el impuesto.
      • original_tax_ids: Impuestos que este impuesto reemplaza ("Replaces").
      • fp.tax_ids apunta directamente a 'account.tax' (Many2many).
"""

import json
import os
import sys

if 'env' not in globals():
    raise RuntimeError("Este script debe ejecutarse dentro de 'odoo-bin shell'.")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
MODO = 'AUTO'                 # 'EXPORTAR' (en Russo), 'IMPORTAR' (en Beton), o 'AUTO'
DRY_RUN = False                # False: Aplica Commit en la base de datos
JSON_FILE = 'datos_percepciones_posiciones.json'

def safe_field_exists(model_name, field_name):
    return model_name in env and field_name in env[model_name]._fields

# ==============================================================================
# 1. FUNCIÓN DE INVESTIGACIÓN Y EXPORTACIÓN (Para ejecutar en RUSSO - Odoo 18)
# ==============================================================================
def investigar_y_exportar(company):
    print("\n" + "=" * 80)
    print(f" INVESTIGACIÓN Y EXPORTACIÓN - COMPAÑÍA: [{company.id}] {company.name} ".center(80, "="))
    print(f">> VERSIÓN ODOO: {env['ir.module.module'].sudo().search([('name', '=', 'base')], limit=1).latest_version or '18/19'}")
    print("=" * 80)

    # 1.1 Descubrir módulos instalados relacionados
    print("\n--- 1. Módulos Instalados (Adhoc / Localización / Impuestos) ---")
    installed_modules = env['ir.module.module'].sudo().search([
        ('state', '=', 'installed'),
        '|', '|', '|', '|',
        ('name', 'ilike', 'adhoc'),
        ('name', 'ilike', 'l10n_ar'),
        ('name', 'ilike', 'tax'),
        ('name', 'ilike', 'padron'),
        ('name', 'ilike', 'perception'),
    ], order='name')
    
    print(f"Total módulos relevantes encontrados: {len(installed_modules)}")
    for m in installed_modules:
        author = m.author or 'Desconocido'
        print(f"  • {m.name:<35} | Autor: {author:<25} | Versión: {m.latest_version}")

    # 1.2 Inspección de Posiciones Fiscales de IIBB y su origen (ir.model.data)
    print("\n--- 2. Análisis de Posiciones Fiscales de IIBB y Mapeos ---")
    fp_iibb = env['account.fiscal.position'].search([
        ('company_id', 'in', [company.id, False]),
        '|', '|', '|',
        ('name', 'ilike', 'IIBB'),
        ('name', 'ilike', 'Salta'),
        ('name', 'ilike', 'Jujuy'),
        ('name', 'ilike', 'Tucuman'),
    ])

    print(f"Total posiciones fiscales de IIBB encontradas: {len(fp_iibb)}")
    
    IrModelData = env['ir.model.data'].sudo()
    data_export = {
        'company_source': company.name,
        'tax_groups': [],
        'taxes': [],
        'fiscal_positions': [],
    }

    tax_groups_seen = set()
    taxes_seen = set()
    has_legacy_fp_tax = 'account.fiscal.position.tax' in env

    for fp in fp_iibb:
        xml_record = IrModelData.search([
            ('model', '=', 'account.fiscal.position'),
            ('res_id', '=', fp.id),
        ], limit=1)
        origen = f"{xml_record.module}.{xml_record.name}" if xml_record else "[Manual/Sin XMLID]"

        mappings = []
        if has_legacy_fp_tax:
            # Odoo 17 / 18: modelo account.fiscal.position.tax
            for m in fp.tax_ids:
                src_name = m.tax_src_id.name if m.tax_src_id else None
                src_use = m.tax_src_id.type_tax_use if m.tax_src_id else None
                dest_name = m.tax_dest_id.name if m.tax_dest_id else None
                dest_use = m.tax_dest_id.type_tax_use if m.tax_dest_id else None
                
                mappings.append({
                    'tax_src_name': src_name,
                    'tax_src_use': src_use,
                    'tax_dest_name': dest_name,
                    'tax_dest_use': dest_use,
                })

                if m.tax_dest_id and m.tax_dest_id.id not in taxes_seen:
                    taxes_seen.add(m.tax_dest_id.id)
                    t = m.tax_dest_id
                    tg = t.tax_group_id
                    if tg and tg.id not in tax_groups_seen:
                        tax_groups_seen.add(tg.id)
                        data_export['tax_groups'].append({'name': tg.name})

                    data_export['taxes'].append({
                        'name': t.name,
                        'description': t.description,
                        'type_tax_use': t.type_tax_use,
                        'amount_type': t.amount_type,
                        'amount': t.amount,
                        'tax_group_name': tg.name if tg else False,
                        'tax_scope': getattr(t, 'tax_scope', False),
                    })
        else:
            # Odoo 19: fp.tax_ids es account.tax directamente
            for dest_t in fp.tax_ids:
                dest_name = dest_t.name
                dest_use = dest_t.type_tax_use
                orig_taxes = getattr(dest_t, 'original_tax_ids', False)
                if orig_taxes:
                    for src_t in orig_taxes:
                        mappings.append({
                            'tax_src_name': src_t.name,
                            'tax_src_use': src_t.type_tax_use,
                            'tax_dest_name': dest_name,
                            'tax_dest_use': dest_use,
                        })
                else:
                    mappings.append({
                        'tax_src_name': None,
                        'tax_src_use': None,
                        'tax_dest_name': dest_name,
                        'tax_dest_use': dest_use,
                    })

                if dest_t.id not in taxes_seen:
                    taxes_seen.add(dest_t.id)
                    tg = dest_t.tax_group_id
                    if tg and tg.id not in tax_groups_seen:
                        tax_groups_seen.add(tg.id)
                        data_export['tax_groups'].append({'name': tg.name})
                    data_export['taxes'].append({
                        'name': dest_t.name,
                        'description': dest_t.description,
                        'type_tax_use': dest_t.type_tax_use,
                        'amount_type': dest_t.amount_type,
                        'amount': dest_t.amount,
                        'tax_group_name': tg.name if tg else False,
                        'tax_scope': getattr(dest_t, 'tax_scope', False),
                    })

        print(f"  • Posición: '{fp.name}' | Origen XML: {origen}")
        for mp in mappings:
            print(f"      Mapeo: '{mp['tax_src_name']}' -> '{mp['tax_dest_name']}'")

        data_export['fiscal_positions'].append({
            'name': fp.name,
            'auto_apply': fp.auto_apply,
            'origen_xml': origen,
            'mappings': mappings,
        })

    # Guardar en archivo JSON local
    try:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_export, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Datos exportados exitosamente a: '{JSON_FILE}'")
        print(f"     Tax Groups: {len(data_export['tax_groups'])} | Impuestos: {len(data_export['taxes'])} | Posiciones: {len(data_export['fiscal_positions'])}")
    except Exception as e:
        print(f"\n[!] Error guardando archivo JSON: {e}")

    return data_export


# ==============================================================================
# 2. FUNCIÓN DE IMPORTACIÓN / CARGA (Para ejecutar en BETON SRL - Odoo 19)
# ==============================================================================
def importar_a_beton(company):
    print("\n" + "=" * 80)
    print(f" CARGA DE PERCEPCIONES Y POSICIONES - COMPAÑÍA: [{company.id}] {company.name} ".center(80, "="))
    print(f" MODO: {'[DRY-RUN - SIMULACIÓN SIN CAMBIOS]' if DRY_RUN else '[*** LIVE - APLICANDO CAMBIOS ***]'} ".center(80, "="))
    print("=" * 80)

    if not os.path.exists(JSON_FILE):
        print(f"\n[!] No se encontró el archivo '{JSON_FILE}'.")
        print("    Asegúrate de que el archivo JSON esté en el directorio de trabajo.")
        return

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    country_ar = env.ref('base.ar', raise_if_not_found=False) or env['res.country'].search([('code', '=', 'AR')], limit=1)
    is_odoo19 = 'account.fiscal.position.tax' not in env

    if is_odoo19:
        print(">> DETECTADO ODOO 19 (Arquitectura Tax-Centric: sin 'account.fiscal.position.tax')")
    else:
        print(">> DETECTADO ODOO 17/18 (Arquitectura Legacy: con 'account.fiscal.position.tax')")

    # 2.1 Carga de Tax Groups
    print("\n--- 1. Creación / Verificación de Tax Groups ---")
    tg_cache = {}
    for tg_data in data.get('tax_groups', []):
        name = tg_data['name']
        tg = env['account.tax.group'].search([
            ('company_id', 'in', [company.id, False]),
            ('name', '=', name),
        ], limit=1)
        if not tg:
            tg_vals = {'name': name, 'company_id': company.id}
            if safe_field_exists('account.tax.group', 'country_id') and country_ar:
                tg_vals['country_id'] = country_ar.id
            tg = env['account.tax.group'].create(tg_vals)
            print(f"  [+ CREADO] Tax Group: '{name}'")
        else:
            print(f"  [OK] Tax Group existente: '{name}'")
        tg_cache[name] = tg.id

    # 2.2 Carga de Impuestos
    print("\n--- 2. Creación / Verificación de Impuestos de Percepción ---")
    tax_cache = {}
    for t_data in data.get('taxes', []):
        name = t_data['name']
        type_use = t_data['type_tax_use']
        tax = env['account.tax'].search([
            ('company_id', '=', company.id),
            ('name', '=', name),
            ('type_tax_use', '=', type_use),
        ], limit=1)

        tg_id = tg_cache.get(t_data.get('tax_group_name'))
        if not tg_id and t_data.get('tax_group_name'):
            tg = env['account.tax.group'].search([
                ('company_id', 'in', [company.id, False]),
                ('name', '=', t_data['tax_group_name']),
            ], limit=1)
            tg_id = tg.id if tg else False

        if not tax:
            tax_vals = {
                'name': name,
                'description': t_data.get('description') or name,
                'type_tax_use': type_use,
                'amount_type': t_data.get('amount_type', 'percent'),
                'amount': t_data.get('amount', 0.0),
                'tax_group_id': tg_id,
                'company_id': company.id,
            }
            if safe_field_exists('account.tax', 'tax_scope') and t_data.get('tax_scope'):
                tax_vals['tax_scope'] = t_data['tax_scope']
            if safe_field_exists('account.tax', 'country_id') and country_ar:
                tax_vals['country_id'] = country_ar.id

            tax = env['account.tax'].create(tax_vals)
            print(f"  [+ CREADO] Impuesto: [{tax.id}] '{name}' ({type_use}) - {tax.amount}%")
        else:
            print(f"  [OK] Impuesto existente: [{tax.id}] '{name}' ({type_use})")
        tax_cache[(name, type_use)] = tax.id

    # 2.3 Carga de Posiciones Fiscales y Mapeos
    print("\n--- 3. Creación / Verificación de Posiciones Fiscales y Mapeos ---")
    for fp_data in data.get('fiscal_positions', []):
        fp_name = fp_data['name']
        fp = env['account.fiscal.position'].search([
            ('company_id', 'in', [company.id, False]),
            ('name', '=', fp_name),
        ], limit=1)

        if not fp:
            fp_vals = {
                'name': fp_name,
                'auto_apply': fp_data.get('auto_apply', False),
                'company_id': company.id,
                'country_id': country_ar.id if country_ar else False,
            }
            fp = env['account.fiscal.position'].create(fp_vals)
            print(f"  [+ CREADA] Posición Fiscal: [{fp.id}] '{fp_name}'")
        else:
            print(f"  [OK] Posición Fiscal existente: [{fp.id}] '{fp_name}'")

        # Configurar mapeos de impuestos según versión de Odoo
        for mp in fp_data.get('mappings', []):
            src_name = mp.get('tax_src_name')
            src_use = mp.get('tax_src_use')
            dest_name = mp.get('tax_dest_name')
            dest_use = mp.get('tax_dest_use')

            src_tax = env['account.tax'].search([
                ('company_id', '=', company.id),
                ('name', '=', src_name),
                ('type_tax_use', '=', src_use),
            ], limit=1) if src_name else False

            dest_tax = env['account.tax'].search([
                ('company_id', '=', company.id),
                ('name', '=', dest_name),
                ('type_tax_use', '=', dest_use),
            ], limit=1) if dest_name else False

            if is_odoo19:
                # -------------------------------------------------------------
                # ODOO 19: Arquitectura Tax-Centric
                # -------------------------------------------------------------
                if dest_tax:
                    # 1. Asociar el impuesto a la posición fiscal
                    if 'fiscal_position_ids' in dest_tax._fields:
                        if fp not in dest_tax.fiscal_position_ids:
                            dest_tax.write({'fiscal_position_ids': [(4, fp.id)]})
                    elif 'tax_ids' in fp._fields and fp._fields['tax_ids'].comodel_name == 'account.tax':
                        if dest_tax not in fp.tax_ids:
                            fp.write({'tax_ids': [(4, dest_tax.id)]})

                    # 2. Si reemplaza a un impuesto original ("Replaces")
                    if src_tax:
                        if 'original_tax_ids' in dest_tax._fields:
                            if src_tax not in dest_tax.original_tax_ids:
                                dest_tax.write({'original_tax_ids': [(4, src_tax.id)]})
                        elif 'source_tax_ids' in dest_tax._fields:
                            if src_tax not in dest_tax.source_tax_ids:
                                dest_tax.write({'source_tax_ids': [(4, src_tax.id)]})

                    print(f"      [+ MAPEO ODOO 19]: '{src_name or '[Directo]'}' -> '{dest_name}' en Posición '{fp.name}'")
            else:
                # -------------------------------------------------------------
                # ODOO 17 / 18: Modelo account.fiscal.position.tax
                # -------------------------------------------------------------
                existing_map = fp.tax_ids.filtered(
                    lambda m: m.tax_src_id == src_tax and m.tax_dest_id == dest_tax
                )
                if not existing_map:
                    map_vals = {
                        'position_id': fp.id,
                        'tax_src_id': src_tax.id if src_tax else False,
                        'tax_dest_id': dest_tax.id if dest_tax else False,
                    }
                    env['account.fiscal.position.tax'].create(map_vals)
                    print(f"      [+ MAPEO ODOO 17/18]: '{src_name}' -> '{dest_name}'")

    print("\n" + "=" * 80)
    if DRY_RUN:
        env.cr.rollback()
        print(">> [DRY-RUN]: SE EJECUTÓ ROLLBACK(). NINGÚN REGISTRO FUE GUARDADO EN LA BASE.")
        print(">> Para persistir los cambios en BETON SRL:")
        print("    1. Abre 'investigar_y_replicar_adhoc.py'")
        print("    2. Cambia 'DRY_RUN = False'")
        print("    3. Vuelve a ejecutar el script en Odoo.sh.")
    else:
        env.cr.commit()
        print(">> [LIVE]: SE EJECUTÓ COMMIT() CON ÉXITO. TODOS LOS IMPUESTOS Y POSICIONES FUERON GUARDADOS EN BETON SRL.")
    print("=" * 80 + "\n")


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    company = env.company
    print(f"\nDetectada compañía activa: [{company.id}] {company.name}")
    
    if MODO == 'EXPORTAR':
        investigar_y_exportar(company)
    elif MODO == 'IMPORTAR':
        importar_a_beton(company)
    else: # AUTO
        if 'RUSSO' in company.name.upper():
            print("Detectado entorno RUSSO -> Ejecutando INVESTIGACIÓN Y EXPORTACIÓN...")
            investigar_y_exportar(company)
        else:
            print("Detectado entorno BETON SRL u otro -> Ejecutando IMPORTACIÓN...")
            importar_a_beton(company)

if __name__ == '__main__' or 'env' in globals():
    main()
