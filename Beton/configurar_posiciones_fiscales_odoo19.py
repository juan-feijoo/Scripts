#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
CONFIGURACIÓN Y AUDITORÍA DE POSICIONES FISCALES E IMPUESTOS EN ODOO 19.0+e
Empresa: BETON SRL | Odoo.sh | Localización Argentina (l10n_ar / l10n_ar_withholding)
================================================================================

CONTEXTO TÉCNICO ODOO 18 vs ODOO 19:
  1. En Odoo 18:
     - El modelo 'account.fiscal.position.tax' manejaba el mapeo tradicional:
       (tax_src_id -> tax_dest_id).
  2. En Odoo 19 (Arquitectura Tax-Centric):
     - El modelo 'account.fiscal.position.tax' fue ELIMINADO.
     - En 'account.fiscal.position', el campo 'tax_ids' es un Many2many directo hacia 'account.tax'.
     - En 'account.tax', los campos 'fiscal_position_ids' y 'original_tax_ids' ("Replaces")
       definen qué impuestos sustituye o en qué posiciones aplica.
     - Nuevos campos en 'account.fiscal.position':
       • 'l10n_ar_tax_type': Clasificación técnica del impuesto/régimen.
       • 'l10n_ar_tax_ids': Impuestos específicos de la localización (retenciones/percepciones).
       • 'l10n_ar_afip_responsibility_type_ids': Tipos de responsabilidad AFIP asociados.
       • 'is_domestic': Booleano calculado para limitar impuestos locales vs internacionales.

OBJETIVO DE ESTE SCRIPT:
  1. Inspeccionar en profundidad los nuevos campos y su metadata (selection, comodel, etc.).
  2. Comparar las posiciones nativas de Odoo 19 ([7] AR Domestic, [8], [10]) con las de IIBB ([34] a [56]).
  3. Configurar correctamente las posiciones fiscales de Percepciones y Responsabilidades AFIP
     según el estándar de Odoo 19.
  4. Modo DRY-RUN estricto con rollback() por defecto.

EJECUCIÓN EN ODOO.SH:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < configurar_posiciones_fiscales_odoo19.py
"""

import sys
import pprint

if 'env' not in globals():
    raise RuntimeError("Este script debe ejecutarse dentro del entorno 'odoo-bin shell'.")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = True                  # True: Modo seguro (rollback()). False: Persiste cambios (commit()).
COMPANY_ID = 1                  # BETON SRL
AUDITAR_METADATA = True         # Imprime la definición técnica de los campos nuevos
ACTUALIZAR_POSICIONES = False   # True: Modifica las posiciones de IIBB con los campos correctos

def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80)

def print_sub(title):
    print(f"\n--- {title} " + "-" * (75 - len(title)))

def safe_field_info(model_name, field_name):
    if model_name not in env:
        return None
    field = env[model_name]._fields.get(field_name)
    if not field:
        return None
    info = {
        'name': field_name,
        'type': field.type,
        'string': field.string,
        'help': getattr(field, 'help', None),
        'store': getattr(field, 'store', False),
        'readonly': getattr(field, 'readonly', False),
    }
    if field.type == 'selection':
        info['selection'] = getattr(field, 'selection', [])
    elif field.type in ('many2one', 'many2many', 'one2many'):
        info['comodel_name'] = getattr(field, 'comodel_name', None)
    return info

def execute():
    company = env['res.company'].browse(COMPANY_ID)
    if not company.exists():
        company = env.company

    print_header("DIAGNÓSTICO Y CONFIGURACIÓN: POSICIONES FISCALES EN ODOO 19")
    print(f">> Compañía: [{company.id}] {company.name}")
    print(f">> Modo: {'[DRY-RUN - SIMULACIÓN SIN CAMBIOS]' if DRY_RUN else '[*** LIVE - APLICANDO CAMBIOS ***]'}")

    # --------------------------------------------------------------------------
    # 1. INSPECCIÓN TÉCNICA DE CAMPOS EN account.fiscal.position y account.tax
    # --------------------------------------------------------------------------
    if AUDITAR_METADATA:
        print_sub("1. Metadata de Campos Nuevos en 'account.fiscal.position' (v19)")
        campos_fp = [
            'l10n_ar_tax_type',
            'l10n_ar_tax_ids',
            'l10n_ar_afip_responsibility_type_ids',
            'tax_ids',
            'is_domestic',
            'shared_to_branches',
            'foreign_vat',
        ]
        for fname in campos_fp:
            finfo = safe_field_info('account.fiscal.position', fname)
            if finfo:
                print(f"  • Campo: '{fname}' [{finfo['type']}] - '{finfo['string']}'")
                if 'selection' in finfo:
                    print(f"      Valores Selection: {finfo['selection']}")
                if 'comodel_name' in finfo:
                    print(f"      Comodel Relacionado: '{finfo['comodel_name']}'")
                if finfo.get('help'):
                    print(f"      Ayuda: {finfo['help']}")
            else:
                print(f"  • Campo: '{fname}' -> [NO EXISTE en este modelo]")

        print_sub("2. Metadata de Campos de Mapeo en 'account.tax' (v19)")
        campos_tax = [
            'fiscal_position_ids',
            'original_tax_ids',
            'tax_scope',
            'l10n_ar_tax_type',
            'l10n_ar_type_tax_use',
        ]
        for fname in campos_tax:
            finfo = safe_field_info('account.tax', fname)
            if finfo:
                print(f"  • Campo: '{fname}' [{finfo['type']}] - '{finfo['string']}'")
                if 'selection' in finfo:
                    print(f"      Valores Selection: {finfo['selection']}")
                if 'comodel_name' in finfo:
                    print(f"      Comodel Relacionado: '{finfo['comodel_name']}'")
            else:
                print(f"  • Campo: '{fname}' -> [NO EXISTE en este modelo]")

    # --------------------------------------------------------------------------
    # 2. COMPARATIVA DE CONFIGURACIÓN ENTRE POSICIONES NATIVAS Y CREADAS
    # --------------------------------------------------------------------------
    print_sub("3. Inspección Comparativa de Registros de Posición Fiscal")
    posiciones_analizar = [7, 8, 9, 10, 42] # Nativas + 42 (1% IIBB Salta)
    
    for pid in posiciones_analizar:
        fp = env['account.fiscal.position'].browse(pid)
        if not fp.exists():
            print(f"  Posición ID {pid} no existe.")
            continue
        print(f"\n  Posición [{fp.id}] '{fp.name}':")
        print(f"    - Auto-apply: {fp.auto_apply} | is_domestic: {getattr(fp, 'is_domestic', 'N/A')}")
        print(f"    - l10n_ar_tax_type: {getattr(fp, 'l10n_ar_tax_type', 'N/A')}")
        
        # Resp AFIP
        resp_afip = fp.l10n_ar_afip_responsibility_type_ids.mapped('name') if 'l10n_ar_afip_responsibility_type_ids' in fp._fields else []
        print(f"    - Resp. AFIP ({len(resp_afip)}): {', '.join(resp_afip) if resp_afip else '[NINGUNA]'}")
        
        # l10n_ar_tax_ids
        if 'l10n_ar_tax_ids' in fp._fields:
            l10n_taxes = [f"[{t.id}] {t.name}" for t in fp.l10n_ar_tax_ids]
            print(f"    - l10n_ar_tax_ids ({len(l10n_taxes)}): {', '.join(l10n_taxes) if l10n_taxes else '[VACÍO]'}")
        
        # tax_ids estándar (v19)
        std_taxes = [f"[{t.id}] {t.name}" for t in fp.tax_ids]
        print(f"    - tax_ids ({len(std_taxes)}): {', '.join(std_taxes) if std_taxes else '[VACÍO]'}")

    # --------------------------------------------------------------------------
    # 3. INSPECCIÓN DEL IMPUESTO 374 (1% IIBB Salta) EN ODOO 19
    # --------------------------------------------------------------------------
    print_sub("4. Diagnóstico del Impuesto [374] '1% IIBB Salta'")
    tax_374 = env['account.tax'].browse(374)
    if tax_374.exists():
        print(f"  Impuesto: [{tax_374.id}] {tax_374.name}")
        print(f"    - Tipo de Uso: {tax_374.type_tax_use} | Importe: {tax_374.amount}% | Grupo: {tax_374.tax_group_id.name if tax_374.tax_group_id else 'N/A'}")
        if 'fiscal_position_ids' in tax_374._fields:
            fp_names = [f"[{fp.id}] {fp.name}" for fp in tax_374.fiscal_position_ids]
            print(f"    - fiscal_position_ids vinculadas: {', '.join(fp_names) if fp_names else '[NINGUNA]'}")
        if 'original_tax_ids' in tax_374._fields:
            orig_names = [f"[{ot.id}] {ot.name}" for ot in tax_374.original_tax_ids]
            print(f"    - original_tax_ids ('Replaces'): {', '.join(orig_names) if orig_names else '[NINGUNO - NO SUSTITUYE OTRO IMPUESTO]'}")
    else:
        print("  Impuesto 374 no encontrado.")

    # --------------------------------------------------------------------------
    # 4. RECOMENDACIÓN Y APLICACIÓN DE CAMBIOS
    # --------------------------------------------------------------------------
    print_sub("5. Propuesta de Ajuste y Configuración para Posiciones de IIBB")
    
    # Buscamos todas las posiciones fiscales de percepciones de IIBB creadas
    fp_iibb = env['account.fiscal.position'].search([
        ('company_id', 'in', [company.id, False]),
        ('id', '>=', 34),
        '|', '|',
        ('name', 'ilike', 'IIBB'),
        ('name', 'ilike', 'Salta'),
        ('name', 'ilike', 'Jujuy'),
    ])

    print(f"  Total posiciones de percepciones detectadas para revisar: {len(fp_iibb)}")
    
    # Responsabilidad AFIP IVA Responsable Inscripto (código 1)
    resp_ri = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '1')], limit=1)

    if ACTUALIZAR_POSICIONES:
        print("\n  >> Aplicando ajustes a las Posiciones Fiscales...")
        for fp in fp_iibb:
            vals = {}
            # Si se desea vincular con Responsable Inscripto:
            if resp_ri and 'l10n_ar_afip_responsibility_type_ids' in fp._fields:
                if resp_ri not in fp.l10n_ar_afip_responsibility_type_ids:
                    vals['l10n_ar_afip_responsibility_type_ids'] = [(4, resp_ri.id)]
            
            # Si country_id no está seteado o is_domestic da False
            if 'country_id' in fp._fields and not fp.country_id:
                ar_country = env['res.country'].search([('code', '=', 'AR')], limit=1)
                if ar_country:
                    vals['country_id'] = ar_country.id

            if vals:
                fp.write(vals)
                print(f"    [ACTUALIZADA] [{fp.id}] {fp.name}: {vals}")
    else:
        print("  [INFO] ACTUALIZAR_POSICIONES = False. No se ejecutaron modificaciones.")

    # --------------------------------------------------------------------------
    # 5. TRANSACCIÓN FINAL
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    if DRY_RUN:
        env.cr.rollback()
        print(">> [DRY-RUN]: SE EJECUTÓ ROLLBACK(). NINGÚN REGISTRO FUE MODIFICADO EN LA BASE.")
        print(">> Para persistir cambios: cambia 'DRY_RUN = False' y 'ACTUALIZAR_POSICIONES = True'.")
    else:
        env.cr.commit()
        print(">> [LIVE]: SE EJECUTÓ COMMIT() CON ÉXITO.")
    print("=" * 80 + "\n")

if __name__ == '__main__' or 'env' in globals():
    execute()

