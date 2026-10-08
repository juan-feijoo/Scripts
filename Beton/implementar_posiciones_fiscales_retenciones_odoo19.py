#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
CREACIÓN Y CONFIGURACIÓN: POSICIONES FISCALES DE RETENCIONES EN ODOO 19.0+e
Empresa: BETON SRL (ID: 1) | Localización: l10n_ar_tax (ingadhoc) | Odoo.sh
================================================================================

OBJETIVO:
  Crear y configurar las Posiciones Fiscales de RETENCIONES (Withholdings) para:
    1. Retenciones de IIBB por Jurisdicción Provincial (CABA, PBA, Salta, Jujuy, Tucumán, etc.)
    2. Retenciones Nacionales (Ganancias e IVA, si están disponibles)
    3. Posición Fiscal Unificada 'Retenciones Proveedores' (opcional) que agrupa
       las retenciones habituales para asignación directa en proveedores.

ARQUITECTURA ODOO 19:
  - En 'account.fiscal.position':
      • l10n_ar_tax_type = 'withholding'
      • auto_apply = False (se asignan al proveedor o se seleccionan en el pago)
      • tax_ids = [impuestos de retención correspondientes]
  - En 'account.fiscal.position.l10n_ar_tax':
      • tax_type = 'withholding'
      • tax_group_id = Grupo de impuesto de retención (ej. 'WTH IIBB Salta')
      • default_tax_id = Impuesto de retención (ej. 'IIBB WTH S')
      • aliquot = Alícuota correspondiente (%)
      • webservice = 'agip' (CABA), 'arba' (PBA), etc., si aplica.

USO EN ODOO.SH:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < implementar_posiciones_fiscales_retenciones_odoo19.py
"""

import sys

if 'env' not in globals():
    raise RuntimeError("Este script debe ejecutarse dentro de 'odoo-bin shell'.")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False                   # True: Simula y ejecuta rollback. False: Aplica commit.
COMPANY_ID = 1                   # BETON SRL
CREAR_POR_JURISDICCION = True    # Crear una Posición Fiscal de Retención por provincia (ej. 'Retención IIBB Salta')
CREAR_POSICION_UNIFICADA = True  # Crear posición 'Retenciones Proveedores' agrupando retenciones clave
ACTUALIZAR_EXISTENTES = True     # Actualiza líneas en posiciones de retención si ya existían

# Mapeo de códigos de provincia / webservice en l10n_ar_tax
WEBSERVICE_MAP = {
    'CABA': 'agip',
    'PBA': 'arba',
    'BUENOS AIRES': 'arba',
    'CBA': 'rentas_cordoba',
    'CORDOBA': 'rentas_cordoba',
    'SF': 'padron',
    'SANTA FE': 'padron',
}

# Nombres amigables de provincias para los nombres de posiciones fiscales
PROVINCIA_NAMES = {
    'CABA': 'CABA (AGIP)',
    'PBA': 'Buenos Aires (ARBA)',
    'C': 'Catamarca',
    'CBA': 'Córdoba',
    'CTS': 'Corrientes',
    'ER': 'Entre Ríos',
    'J': 'Jujuy',
    'MZA': 'Mendoza',
    'LR': 'La Rioja',
    'S': 'Salta',
    'SJ': 'San Juan',
    'SL': 'San Luis',
    'SF': 'Santa Fe',
    'SE': 'Santiago del Estero',
    'T': 'Tucumán',
    'CHO': 'Chaco',
    'CHT': 'Chubut',
    'F': 'Formosa',
    'MS': 'Misiones',
    'N': 'Neuquén',
    'LP': 'La Pampa',
    'RN': 'Río Negro',
    'SC': 'Santa Cruz',
    'TAIS': 'Tierra del Fuego',
}

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def execute():
    company = env['res.company'].browse(COMPANY_ID)
    if not company.exists():
        company = env.company

    print("\n" + "=" * 80)
    print(" IMPLEMENTACIÓN DE POSICIONES FISCALES DE RETENCIÓN - ODOO 19 ".center(80, "="))
    print(f" Compañía: [{company.id}] {company.name} | Localización: l10n_ar_tax ".center(80, "="))
    print(f" MODO: {'[DRY-RUN - SIMULACIÓN SIN CAMBIOS]' if DRY_RUN else '[*** LIVE - APLICANDO CAMBIOS ***]'} ".center(80, "="))
    print("=" * 80 + "\n")

    country_ar = env.ref('base.ar', raise_if_not_found=False) or env['res.country'].search([('code', '=', 'AR')], limit=1)
    L10nArTax = env['account.fiscal.position.l10n_ar_tax']

    # --------------------------------------------------------------------------
    # FASE 1: BÚSQUEDA Y CLASIFICACIÓN DE IMPUESTOS DE RETENCIÓN
    # --------------------------------------------------------------------------
    print("--- FASE 1: Detección de Impuestos de Retención en la Compañía ---")
    
    # Buscamos todos los impuestos de retención existentes en la compañía
    # Suelen tener type_tax_use in ('none', 'supplier') o pertenecer a grupos WTH
    wth_taxes = env['account.tax'].search([
        ('company_id', '=', company.id),
        '|', '|', '|',
        ('tax_group_id.name', 'ilike', 'WTH'),
        ('tax_group_id.name', 'ilike', 'Retenc'),
        ('name', 'ilike', 'WTH'),
        ('name', 'ilike', 'Retenc'),
    ], order='name')

    print(f"Total impuestos de retención detectados: {len(wth_taxes)}")

    # Separar impuestos de IIBB (alícuota > 0) y nacionales (Ganancias, IVA)
    taxes_iibb_wth = {}
    taxes_nacionales_wth = []

    for t in wth_taxes:
        # Excluimos variantes 0% si existe la variante con alícuota positiva
        if t.amount == 0.0 and '0%' in t.name:
            continue

        tg_name = t.tax_group_id.name if t.tax_group_id else ''
        t_name = t.name.upper()

        if 'IIBB' in tg_name.upper() or 'IIBB' in t_name:
            # Detectar código de provincia (ej. 'IIBB WTH S' -> 'S')
            parts = t.name.split()
            code = parts[-1] if parts else ''
            if code in PROVINCIA_NAMES:
                # Guardamos el preferido (alícuota > 0)
                if code not in taxes_iibb_wth or (taxes_iibb_wth[code].amount == 0.0 and t.amount > 0.0):
                    taxes_iibb_wth[code] = t
            else:
                # Búsqueda por coincidencia en nombre
                matched = False
                for c, prov_name in PROVINCIA_NAMES.items():
                    if prov_name.upper() in t_name or f"WTH {c}" in t_name:
                        if c not in taxes_iibb_wth or (taxes_iibb_wth[c].amount == 0.0 and t.amount > 0.0):
                            taxes_iibb_wth[c] = t
                        matched = True
                        break
                if not matched:
                    taxes_iibb_wth[t.name] = t
        elif 'GANANCIAS' in tg_name.upper() or 'PROFITS' in tg_name.upper() or 'GANANCIAS' in t_name:
            taxes_nacionales_wth.append(('Ganancias', t))
        elif 'IVA' in tg_name.upper() or 'VAT' in tg_name.upper() or 'IVA' in t_name:
            taxes_nacionales_wth.append(('IVA', t))

    print(f"  • Retenciones de IIBB identificadas por jurisdicción: {len(taxes_iibb_wth)}")
    for code, t in sorted(taxes_iibb_wth.items()):
        prov = PROVINCIA_NAMES.get(code, code)
        print(f"      [{t.id}] {t.name:<25} | Prov: {prov:<20} | Alícuota: {t.amount}% | Grupo: {t.tax_group_id.name if t.tax_group_id else 'N/A'}")

    print(f"  • Retenciones Nacionales (Ganancias/IVA) identificadas: {len(taxes_nacionales_wth)}")
    for tipo, t in taxes_nacionales_wth:
        print(f"      [{t.id}] {t.name:<25} | Tipo: {tipo:<10} | Alícuota: {t.amount}%")

    # --------------------------------------------------------------------------
    # FASE 2: CREACIÓN DE POSICIONES FISCALES DE RETENCIÓN POR JURISDICCIÓN
    # --------------------------------------------------------------------------
    if CREAR_POR_JURISDICCION:
        print("\n--- FASE 2: Creación de Posiciones Fiscales de Retención por Jurisdicción ---")
        created_fps = 0
        updated_fps = 0

        for code, tax in sorted(taxes_iibb_wth.items()):
            prov_label = PROVINCIA_NAMES.get(code, code)
            fp_name = f"Retención IIBB {prov_label}"

            fp = env['account.fiscal.position'].search([
                ('company_id', 'in', [company.id, False]),
                ('name', '=', fp_name),
            ], limit=1)

            fp_vals = {
                'name': fp_name,
                'l10n_ar_tax_type': 'withholding',
                'auto_apply': False,
                'company_id': company.id,
                'country_id': country_ar.id if country_ar else False,
            }

            if not fp:
                fp = env['account.fiscal.position'].create(fp_vals)
                log(f"[+ CREADA] Posición Fiscal: [{fp.id}] '{fp_name}'")
                created_fps += 1
            else:
                fp.write(fp_vals)
                log(f"[EXISTENTE] Posición Fiscal: [{fp.id}] '{fp_name}'", "DEBUG")
                updated_fps += 1

            # Sincronizar tax_ids
            fp.write({'tax_ids': [(6, 0, [tax.id])]})

            # Detectar webservice si corresponde
            ws = WEBSERVICE_MAP.get(code.upper())

            # Configurar línea en l10n_ar_tax_ids
            fp.l10n_ar_tax_ids.unlink() # Limpiar anteriores
            line_vals = {
                'fiscal_position_id': fp.id,
                'tax_type': 'withholding',
                'default_tax_id': tax.id,
                'tax_group_id': tax.tax_group_id.id if tax.tax_group_id else False,
                'aliquot': tax.amount,
            }
            if ws and 'webservice' in L10nArTax._fields:
                line_vals['webservice'] = ws

            L10nArTax.create(line_vals)
            log(f"  • Línea L10N configurada: Grupo '{tax.tax_group_id.name if tax.tax_group_id else 'N/A'}' | Impuesto [{tax.id}] {tax.name} | WS: {ws or 'Manual'}")

        print(f"\nTotal Posiciones de Retención creadas: {created_fps} | Actualizadas: {updated_fps}")

    # --------------------------------------------------------------------------
    # FASE 3: CREACIÓN DE POSICIONES FISCALES PARA RETENCIONES NACIONALES
    # --------------------------------------------------------------------------
    if CREAR_POR_JURISDICCION and taxes_nacionales_wth:
        print("\n--- FASE 3: Posiciones Fiscales para Retenciones Nacionales (Ganancias / IVA) ---")
        for tipo, tax in taxes_nacionales_wth:
            fp_name = f"Retención {tipo}"
            fp = env['account.fiscal.position'].search([
                ('company_id', 'in', [company.id, False]),
                ('name', '=', fp_name),
            ], limit=1)

            fp_vals = {
                'name': fp_name,
                'l10n_ar_tax_type': 'withholding',
                'auto_apply': False,
                'company_id': company.id,
                'country_id': country_ar.id if country_ar else False,
            }

            if not fp:
                fp = env['account.fiscal.position'].create(fp_vals)
                log(f"[+ CREADA] Posición Fiscal: [{fp.id}] '{fp_name}'")
            else:
                fp.write(fp_vals)

            fp.write({'tax_ids': [(6, 0, [tax.id])]})
            fp.l10n_ar_tax_ids.unlink()

            L10nArTax.create({
                'fiscal_position_id': fp.id,
                'tax_type': 'withholding',
                'default_tax_id': tax.id,
                'tax_group_id': tax.tax_group_id.id if tax.tax_group_id else False,
                'aliquot': tax.amount,
            })
            log(f"  • Línea L10N configurada: Retención '{tipo}' | Impuesto [{tax.id}] {tax.name}")

    # --------------------------------------------------------------------------
    # FASE 4: POSICIÓN FISCAL UNIFICADA 'RETENCIONES PROVEEDORES'
    # --------------------------------------------------------------------------
    if CREAR_POSICION_UNIFICADA:
        print("\n--- FASE 4: Posición Fiscal Unificada 'Retenciones Proveedores' ---")
        unif_name = "Retenciones Proveedores"
        fp_unif = env['account.fiscal.position'].search([
            ('company_id', 'in', [company.id, False]),
            ('name', '=', unif_name),
        ], limit=1)

        unif_vals = {
            'name': unif_name,
            'l10n_ar_tax_type': 'withholding',
            'auto_apply': False,
            'company_id': company.id,
            'country_id': country_ar.id if country_ar else False,
        }

        if not fp_unif:
            fp_unif = env['account.fiscal.position'].create(unif_vals)
            log(f"[+ CREADA] Posición Fiscal Unificada: [{fp_unif.id}] '{unif_name}'")
        else:
            fp_unif.write(unif_vals)
            log(f"[EXISTENTE] Posición Fiscal Unificada: [{fp_unif.id}] '{unif_name}'")

        # Seleccionamos las retenciones habituales para la empresa:
        # Salta (S), Jujuy (J), Tucumán (T), CABA, PBA + Ganancias e IVA si existen
        retenciones_clave = []
        codigos_clave = ['S', 'J', 'T', 'CABA', 'PBA']
        for c in codigos_clave:
            if c in taxes_iibb_wth:
                retenciones_clave.append(taxes_iibb_wth[c])

        for tipo, t in taxes_nacionales_wth:
            retenciones_clave.append(t)

        fp_unif.l10n_ar_tax_ids.unlink()
        taxes_to_link = []

        for tax in retenciones_clave:
            ws = None
            for c in codigos_clave:
                if taxes_iibb_wth.get(c) == tax:
                    ws = WEBSERVICE_MAP.get(c.upper())
                    break

            line_vals = {
                'fiscal_position_id': fp_unif.id,
                'tax_type': 'withholding',
                'default_tax_id': tax.id,
                'tax_group_id': tax.tax_group_id.id if tax.tax_group_id else False,
                'aliquot': tax.amount,
            }
            if ws and 'webservice' in L10nArTax._fields:
                line_vals['webservice'] = ws

            try:
                L10nArTax.create(line_vals)
                taxes_to_link.append(tax.id)
                log(f"  • Agregada retención a Posición Unificada: [{tax.id}] {tax.name} (Grupo: {tax.tax_group_id.name if tax.tax_group_id else 'N/A'})")
            except Exception as e:
                log(f"  [AVISO] No se pudo agregar [{tax.id}] {tax.name}: {e}", "WARN")

        if taxes_to_link:
            fp_unif.write({'tax_ids': [(6, 0, taxes_to_link)]})

    # --------------------------------------------------------------------------
    # FASE 5: TRANSACCIÓN FINAL
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    if DRY_RUN:
        env.cr.rollback()
        print(">> [DRY-RUN]: SE EJECUTÓ ROLLBACK(). NINGÚN CAMBIO FUE PERSISTIDO.")
        print(">> Para persistir los cambios definitivamente:")
        print("    1. Abre 'implementar_posiciones_fiscales_retenciones_odoo19.py'")
        print("    2. Cambia 'DRY_RUN = False'")
        print("    3. Vuelve a ejecutar el script en la terminal de Odoo.sh.")
    else:
        env.cr.commit()
        print(">> [LIVE]: SE EJECUTÓ COMMIT() CON ÉXITO. POSICIONES DE RETENCIÓN CREADAS.")
    print("=" * 80 + "\n")

if __name__ == '__main__' or 'env' in globals():
    execute()

