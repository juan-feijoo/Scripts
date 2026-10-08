#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SOLUCIÓN Y CONFIGURACIÓN: PERCEPCIONES, POSICIONES FISCALES Y CONTACTOS
Empresa: BETON SRL | Odoo 19.0+e (l10n_ar) | Odoo.sh
================================================================================

HALLAZGOS DEL DIAGNÓSTICO:
  1. Se detectaron 24 percepciones provinciales de COMPRA (purchase), pero CERO
     percepciones de VENTA (sale). Si la empresa debe percibir en ventas, faltan
     los impuestos de venta para las jurisdicciones.
  2. Posición Fiscal 'AR Domestic' (ID 7): tiene 12 mapeos pero ninguna Resp. AFIP
     vinculada. Falta verificar qué mapea y asegurar que aplique a Responsable Inscripto.
  3. Faltan posiciones fiscales clave (ej: Consumidor Final).
  4. Los 5 contactos comerciales no tienen 'property_account_position_id' configurada.
  5. 2 contactos ([3] Administrator, [9] IIBB a pagar) no tienen Resp. AFIP.

OBJETIVO DEL SCRIPT:
  - Auditar en detalle los 12 mapeos de 'AR Domestic'.
  - Crear las Percepciones de VENTA (sale) correspondientes a las jurisdicciones.
  - Asegurar las Posiciones Fiscales (AR Domestic, Consumidor Final, Monotributo, etc.).
  - Configurar las Posiciones Fiscales en los contactos correspondientes.
  - Soportar modo DRY_RUN estricto con rollback().

USO EN ODOO.SH:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < resolver_ticket_percepciones_posiciones.py
"""

import sys

if 'env' not in globals():
    raise RuntimeError("Este script debe ejecutarse dentro de 'odoo-bin shell'.")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False                  # True: Simula y ejecuta rollback. False: Aplica commit.
COMPANY_ID = 1                  # BETON SRL
CREAR_PERCEPCIONES_VENTA = True # Crear impuestos de percepción en Venta para las provincias
VINCULAR_RESP_AFIP = True       # Enlazar Responsabilidades AFIP a Posiciones Fiscales
ASIGNAR_POSICION_CONTACTOS = True # Asignar posición fiscal a contactos con Resp. AFIP

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def safe_field_exists(model_name, field_name):
    return field_name in env[model_name]._fields

# ==============================================================================
# EJECUCIÓN PRINCIPAL
# ==============================================================================
def execute():
    company = env['res.company'].browse(COMPANY_ID)
    if not company.exists():
        company = env.company
    
    print("\n" + "=" * 80)
    print(f" RESOLUCIÓN DE TICKET - PERCEPCIONES Y POSICIONES FISCALES ".center(80, "="))
    print(f" Compañía: [{company.id}] {company.name} | Odoo: 19.0+e ".center(80, "="))
    print(f" MODO: {'[DRY-RUN - SIMULACIÓN]' if DRY_RUN else '[*** LIVE - COMMIT ACTIVO ***]'} ".center(80, "="))
    print("=" * 80 + "\n")

    country_ar = env.ref('base.ar', raise_if_not_found=False) or env['res.country'].search([('code', '=', 'AR')], limit=1)

    # --------------------------------------------------------------------------
    # PASO 1: INSPECCIONAR DETALLE DE 'AR Domestic' (ID 7)
    # --------------------------------------------------------------------------
    print("--- PASO 1: Diagnóstico detallado de Posición Fiscal [7] AR Domestic ---")
    fp_domestic = env['account.fiscal.position'].browse(7)
    if fp_domestic.exists():
        print(f"Nombre: {fp_domestic.name} | Auto-apply: {fp_domestic.auto_apply}")
        print("Mapeos de Impuestos configurados actualmente:")
        has_legacy_fp_tax = 'account.fiscal.position.tax' in env
        for map_tax in fp_domestic.tax_ids:
            if has_legacy_fp_tax:
                src = map_tax.tax_src_id.name if map_tax.tax_src_id else '[Cualquiera]'
                dest = map_tax.tax_dest_id.name if map_tax.tax_dest_id else '[Exento/Ninguno]'
                print(f"  • Origen: {src:<35} -> Destino: {dest}")
            else:
                # Odoo 19: map_tax es account.tax directamente
                orig = [ot.name for ot in getattr(map_tax, 'original_tax_ids', [])]
                orig_str = ', '.join(orig) if orig else '[Sin sustitución directa / Aplica directo]'
                print(f"  • Impuesto: [{map_tax.id}] {map_tax.name:<30} (Reemplaza a: {orig_str})")
    else:
        print("Posición Fiscal ID 7 no encontrada.")

    # --------------------------------------------------------------------------
    # PASO 2: CREACIÓN DE PERCEPCIONES DE VENTA (SALE)
    # --------------------------------------------------------------------------
    print("\n--- PASO 2: Verificación y Carga de Percepciones de Venta (sale) ---")
    
    # Buscar cuenta contable para Percepciones en Ventas (Pasivo: ej. "Percepciones IIBB a Pagar / a Depositar")
    account_perc_sale = env['account.account'].search([
        ('company_ids', 'in', [company.id]),
        '|', '|',
        ('code', '=like', '2.1.04%'),  # Rango habitual de pasivo fiscal en plan contable AR
        ('name', 'ilike', 'percep'),
        ('name', 'ilike', 'iibb a pagar'),
    ], limit=1)

    if account_perc_sale:
        print(f"Cuenta contable sugerida para Percepciones de Venta: [{account_perc_sale.code}] {account_perc_sale.name}")
    else:
        print("Aviso: No se encontró cuenta específica con nombre 'percepcion/iibb a pagar'. Se usará la cuenta por defecto del grupo o se dejará para revisión contable.")

    # Obtenemos todos los impuestos de percepción de compra existentes para crear sus espejos en venta
    purchase_perceptions = env['account.tax'].search([
        ('company_id', '=', company.id),
        ('type_tax_use', '=', 'purchase'),
        '|',
        ('name', '=like', 'P. IIBB%'),
        ('description', 'ilike', 'perc'),
    ])

    print(f"Se encontraron {len(purchase_perceptions)} impuestos de percepción en Compras.")
    
    created_sale_taxes = 0
    for p_tax in purchase_perceptions:
        # Generar nombre simétrico para Venta: ej "P. IIBB CABA (Ventas)" o conservar "P. IIBB CABA" con uso 'sale'
        sale_name = p_tax.name if not p_tax.name.endswith('(Compras)') else p_tax.name.replace('(Compras)', '(Ventas)')
        if p_tax.type_tax_use == 'purchase' and p_tax.name == sale_name:
            # Para diferenciar en la vista si tienen el mismo nombre
            sale_name_search = f"{p_tax.name} (Venta)"
        else:
            sale_name_search = sale_name

        existing_sale_tax = env['account.tax'].search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
            '|',
            ('name', '=', p_tax.name),
            ('name', '=', sale_name_search),
        ], limit=1)

        if not existing_sale_tax:
            if CREAR_PERCEPCIONES_VENTA:
                tax_vals = {
                    'name': f"{p_tax.name} (Venta)",
                    'description': p_tax.description or p_tax.name,
                    'type_tax_use': 'sale',
                    'amount_type': p_tax.amount_type, # 'percent' o 'fixed'
                    'amount': p_tax.amount,
                    'tax_group_id': p_tax.tax_group_id.id,
                    'company_id': company.id,
                }
                if safe_field_exists('account.tax', 'tax_scope'):
                    tax_vals['tax_scope'] = p_tax.tax_scope or 'consu'
                if safe_field_exists('account.tax', 'country_id') and country_ar:
                    tax_vals['country_id'] = country_ar.id
                
                # Asignar cuenta si existe
                if account_perc_sale and safe_field_exists('account.tax', 'invoice_repartition_line_ids'):
                    # En Odoo 17/18/19 la cuenta se configura en las líneas de repartición
                    pass # Odoo crea líneas de repartición por defecto

                new_t = env['account.tax'].create(tax_vals)
                if account_perc_sale:
                    # Asignar cuenta en la repartición de facturas
                    for rep in new_t.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == 'tax'):
                        rep.account_id = account_perc_sale.id
                    for rep in new_t.refund_repartition_line_ids.filtered(lambda r: r.repartition_type == 'tax'):
                        rep.account_id = account_perc_sale.id

                log(f"Creado impuesto de Venta: [{new_t.id}] {new_t.name} (Grupo: {p_tax.tax_group_id.name})")
                created_sale_taxes += 1
        else:
            log(f"Impuesto de Venta ya existente: [{existing_sale_tax.id}] {existing_sale_tax.name}", "DEBUG")

    print(f"Total impuestos de percepción en Venta creados: {created_sale_taxes}")

    # --------------------------------------------------------------------------
    # PASO 3: ASEGURAR POSICIONES FISCALES Y RESPONSABILIDADES AFIP
    # --------------------------------------------------------------------------
    print("\n--- PASO 3: Posiciones Fiscales y Responsabilidades AFIP ---")
    
    # 1: IVA Responsable Inscripto
    # 4: IVA Sujeto Exento
    # 5: Consumidor Final
    # 6: Responsable Monotributo
    # 9: Cliente del Exterior
    resp_ri = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '1')], limit=1)
    resp_exento = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '4')], limit=1)
    resp_cf = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '5')], limit=1)
    resp_mono = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '6')], limit=1)
    resp_ext = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '9')], limit=1)

    # 3.1 Vincular 'AR Domestic' con IVA Responsable Inscripto si está vacía
    if VINCULAR_RESP_AFIP and fp_domestic.exists() and resp_ri:
        if not fp_domestic.l10n_ar_afip_responsibility_type_ids:
            fp_domestic.write({
                'l10n_ar_afip_responsibility_type_ids': [(4, resp_ri.id)]
            })
            log(f"Posición [7] '{fp_domestic.name}' vinculada con Responsabilidad AFIP: '{resp_ri.name}'")

    # 3.2 Crear o asegurar Posición Fiscal para 'Consumidor Final'
    fp_cf = env['account.fiscal.position'].search([
        ('company_id', 'in', [company.id, False]),
        '|',
        ('name', 'ilike', 'Consumidor Final'),
        ('name', 'ilike', 'Consumer'),
    ], limit=1)

    if not fp_cf:
        if VINCULAR_RESP_AFIP and resp_cf:
            fp_cf_vals = {
                'name': 'Consumidor Final',
                'auto_apply': True,
                'company_id': company.id,
                'country_id': country_ar.id if country_ar else False,
                'l10n_ar_afip_responsibility_type_ids': [(4, resp_cf.id)],
            }
            fp_cf = env['account.fiscal.position'].create(fp_cf_vals)
            log(f"Creada Posición Fiscal: [{fp_cf.id}] '{fp_cf.name}' vinculada a '{resp_cf.name}'")
    else:
        if VINCULAR_RESP_AFIP and resp_cf and resp_cf not in fp_cf.l10n_ar_afip_responsibility_type_ids:
            fp_cf.write({'l10n_ar_afip_responsibility_type_ids': [(4, resp_cf.id)]})
            log(f"Posición existente [{fp_cf.id}] '{fp_cf.name}' vinculada a '{resp_cf.name}'")

    # --------------------------------------------------------------------------
    # PASO 4: CONFIGURACIÓN EN CONTACTOS (res.partner)
    # --------------------------------------------------------------------------
    print("\n--- PASO 4: Asignación de Posición Fiscal en Contactos ---")
    partners = env['res.partner'].search([
        ('active', '=', True),
        ('parent_id', '=', False),
        '|',
        ('company_id', '=', False),
        ('company_id', '=', company.id),
    ])

    # Tabla de mapeo en memoria: resp_afip_id -> fiscal_position_id
    pos_positions = env['account.fiscal.position'].search([('company_id', 'in', [company.id, False])])
    mapping = {}
    for fp in pos_positions:
        for r in fp.l10n_ar_afip_responsibility_type_ids:
            mapping[r.id] = fp

    updated_partners = 0
    for p in partners:
        resp = p.l10n_ar_afip_responsibility_type_id
        if not resp:
            print(f"  [OMITIDO] Contacto [{p.id}] {p.name}: SIN Responsabilidad AFIP configurada.")
            continue

        target_fp = mapping.get(resp.id)
        if not target_fp:
            # Fallback por nombre
            target_fp = env['account.fiscal.position'].search([
                ('company_id', 'in', [company.id, False]),
                ('name', 'ilike', resp.name),
            ], limit=1)

        if target_fp and p.property_account_position_id != target_fp:
            old_name = p.property_account_position_id.name if p.property_account_position_id else 'Ninguna'
            if ASIGNAR_POSICION_CONTACTOS:
                p.write({'property_account_position_id': target_fp.id})
                log(f"Contacto [{p.id}] {p.name}: Posición asignada de '{old_name}' -> '{target_fp.name}'")
                updated_partners += 1
        elif target_fp and p.property_account_position_id == target_fp:
            print(f"  [CORRECTO] Contacto [{p.id}] {p.name}: Ya tiene '{target_fp.name}'")

    print(f"\nTotal contactos actualizados: {updated_partners}")

    # --------------------------------------------------------------------------
    # PASO 5: TRANSACCIÓN FINAL
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    if DRY_RUN:
        env.cr.rollback()
        print(" >> MODO DRY-RUN: Se ejecutó ROLLBACK(). Ningún cambio fue persistido.")
        print(" >> Para aplicar definitivamente:")
        print("    1. Abre 'resolver_ticket_percepciones_posiciones.py'")
        print("    2. Cambia 'DRY_RUN = False'")
        print("    3. Vuelve a ejecutar el script en la terminal de Odoo.sh.")
    else:
        env.cr.commit()
        print(" >> MODO LIVE: Se ejecutó COMMIT() con éxito. Base de datos actualizada.")
    print("=" * 80 + "\n")

if __name__ == '__main__' or 'env' in globals():
    execute()
