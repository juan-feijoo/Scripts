# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE CARGA E IMPORTACIÓN DE PRODUCTOS Y CATEGORÍAS EN ODOO ENTERPRISE
Versiones soportadas: 17.0+e, 18.0+e, 19.0+e
Entorno: Odoo.sh (Odoo Shell)
Localización: Argentina (l10n_ar)
================================================================================

INSTRUCCIONES DE USO EN ODOO.SH:
1. Subir este script y los archivos JSON generados al directorio de trabajo en Odoo.sh:
   - cargar_productos_odoo_shell.py
   - categorias_preparadas.json
   - productos_preparados.json
   - proveedores_preparados.json (opcional)

2. Ejecutar en modo DRY-RUN (simulación sin persistir cambios):
   python3 odoo-bin shell -d <nombre_bd> < cargar_productos_odoo_shell.py

3. Cuando los resultados de la auditoría y simulación sean satisfactorios:
   Cambiar abajo 'DRY_RUN = False' y volver a ejecutar para persistir (COMMIT).
"""

import os
import sys
import json
import logging
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN GENERAL
# ==============================================================================
DRY_RUN = True                # True: Simulación con ROLLBACK | False: Escritura con COMMIT
PRECIO_VENTA_NETO = True      # True: list_price = precio_neto | False: list_price = precio (con IVA)
CREAR_PROVEEDORES = True      # True: Crea o vincula suppliers en res.partner y product.supplierinfo
CREAR_MARCAS = True           # True: Asigna marcas a campo de marca o a product.tag
BATCH_SIZE = 250              # Tamaño del lote para loguear progreso

# Rutas de archivos JSON de datos preparados
JSON_CATEGORIAS = "categorias_preparadas.json"
JSON_PRODUCTOS = "productos_preparados.json"
JSON_PROVEEDORES = "proveedores_preparados.json"

_logger = logging.getLogger("odoo.migracion_kiddie")

def ejecutar_migracion(env):
    print("=" * 80)
    print(f"INICIANDO MIGRACIÓN DE PRODUCTOS Y CATEGORÍAS (ODOO ENTERPRISE)")
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Modo: {'*** DRY-RUN (SIMULACIÓN - ROLLBACK FINAL) ***' if DRY_RUN else '*** PRODUCCIÓN (COMMIT DEFINITIVO) ***'}")
    print(f"Base de Datos: {env.cr.dbname}")
    print(f"Compañía: {env.company.name} (ID: {env.company.id})")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 0. Verificación de Archivos
    # --------------------------------------------------------------------------
    for fpath in [JSON_CATEGORIAS, JSON_PRODUCTOS]:
        if not os.path.exists(fpath):
            print(f"ERROR CRÍTICO: No se encuentra el archivo '{fpath}'.")
            print("Asegúrate de haber ejecutado previamente 'python preparar_datos_odoo.py'.")
            return

    with open(JSON_CATEGORIAS, 'r', encoding='utf-8') as f:
        data_cat = json.load(f)

    with open(JSON_PRODUCTOS, 'r', encoding='utf-8') as f:
        data_prod = json.load(f)

    data_prov = []
    if CREAR_PROVEEDORES and os.path.exists(JSON_PROVEEDORES):
        with open(JSON_PROVEEDORES, 'r', encoding='utf-8') as f:
            data_prov = json.load(f)

    # --------------------------------------------------------------------------
    # 1. Cacheo y Mapeo de Impuestos (Localización Argentina)
    # --------------------------------------------------------------------------
    print("\n[PASO 1/5] Mapeando Impuestos de Venta (account.tax)...")
    Tax = env['account.tax']
    company_id = env.company.id
    
    # Buscar impuestos de venta de la compañía activa
    sale_taxes = Tax.search([
        ('company_id', '=', company_id),
        ('type_tax_use', '=', 'sale')
    ])
    
    tax_map = {}
    for rate in [21.0, 10.5, 0.0]:
        # Buscar por monto exacto
        matched = sale_taxes.filtered(lambda t: abs(t.amount - rate) < 0.01 and t.active)
        if matched:
            # Si hay varios, preferir el estándar o el que contenga el número en su nombre
            best_match = matched[0]
            for m in matched:
                if str(int(rate) if rate.is_integer() else rate) in m.name:
                    best_match = m
                    break
            tax_map[rate] = best_match
            print(f"  -> Tasa {rate}% mapeada a impuesto: '{best_match.name}' (ID: {best_match.id})")
        else:
            print(f"  [AVISO] No se encontró impuesto de venta para alícuota {rate}%.")

    # --------------------------------------------------------------------------
    # 2. Creación / Búsqueda Jerárquica de Categorías (product.category)
    # --------------------------------------------------------------------------
    print("\n[PASO 2/5] Procesando Estructura Jerárquica de Categorías...")
    Category = env['product.category']
    category_map = {}  # full_path -> record

    # A. Categorías Padre (Subrubros)
    parent_map = {}
    for parent_name in data_cat.get('padres', []):
        parent_cat = Category.search([
            ('name', '=', parent_name),
            ('parent_id', '=', False)
        ], limit=1)
        if not parent_cat:
            parent_cat = Category.create({
                'name': parent_name,
                'parent_id': False
            })
            print(f"  + Categoría Padre creada: '{parent_name}' (ID: {parent_cat.id})")
        parent_map[parent_name] = parent_cat

    # B. Categorías Hijas (Rubros)
    creadas_cat = 0
    existentes_cat = 0
    for h in data_cat.get('hijas', []):
        parent_name = h['parent_name']
        child_name = h['name']
        full_path = h['full_path']

        parent_cat = parent_map.get(parent_name)
        parent_id = parent_cat.id if parent_cat else False

        cat = Category.search([
            ('name', '=', child_name),
            ('parent_id', '=', parent_id)
        ], limit=1)

        if not cat:
            cat = Category.create({
                'name': child_name,
                'parent_id': parent_id
            })
            creadas_cat += 1
        else:
            existentes_cat += 1

        category_map[full_path] = cat

    print(f"  -> Total Categorías Hijas: {creadas_cat} creadas, {existentes_cat} ya existentes.")

    # --------------------------------------------------------------------------
    # 3. Mapeo / Creación de Proveedores (res.partner)
    # --------------------------------------------------------------------------
    partner_map = {}  # numprv -> record
    if CREAR_PROVEEDORES and data_prov:
        print("\n[PASO 3/5] Procesando Proveedores (res.partner)...")
        Partner = env['res.partner']
        creados_prv = 0
        for prv in data_prov:
            numprv = prv['numprv']
            nombre = prv['nombre']
            cuit = prv.get('cuit', '')

            # Búsqueda por referencia interna o por nombre
            domain = ['|', ('ref', '=', numprv), ('name', '=', nombre), ('supplier_rank', '>', 0)]
            partner = Partner.search(domain, limit=1)
            if not partner:
                partner_vals = {
                    'name': nombre,
                    'ref': numprv,
                    'supplier_rank': 1,
                    'is_company': True,
                    'street': prv.get('domicilio', ''),
                    'city': prv.get('localidad', ''),
                    'phone': prv.get('telefono', ''),
                    'email': prv.get('email', '')
                }
                if cuit:
                    partner_vals['vat'] = cuit
                partner = Partner.create(partner_vals)
                creados_prv += 1
            partner_map[numprv] = partner
        print(f"  -> Proveedores mapeados: {len(partner_map)} (nuevos creados: {creados_prv})")

    # --------------------------------------------------------------------------
    # 4. Mapeo de Marcas (Brand / Product Tag)
    # --------------------------------------------------------------------------
    brand_field = None
    ProductTemplate = env['product.template']
    for candidate in ['brand_id', 'x_marca_id', 'product_brand_id']:
        if candidate in ProductTemplate._fields:
            brand_field = candidate
            break

    tags_map = {}
    if not brand_field and CREAR_MARCAS and 'product.tag' in env:
        Tag = env['product.tag']
        todas_marcas = {p['marca'] for p in data_prod if p.get('marca') and p['marca'] != 'S/MARCAS'}
        for m in todas_marcas:
            tag = Tag.search([('name', '=', m)], limit=1)
            if not tag:
                tag = Tag.create({'name': m})
            tags_map[m] = tag

    # --------------------------------------------------------------------------
    # 5. Creación / Actualización de Productos (product.template)
    # --------------------------------------------------------------------------
    print(f"\n[PASO 4/5] Procesando {len(data_prod)} Productos en lotes de {BATCH_SIZE}...")
    SupplierInfo = env['product.supplierinfo']
    
    # Determinar compatibilidad de campos entre Odoo 17, 18 y 19
    has_is_storable = 'is_storable' in ProductTemplate._fields
    has_detailed_type = 'detailed_type' in ProductTemplate._fields

    # Cache de productos existentes por default_code para máxima performance
    print("  -> Indexando productos existentes en base de datos...")
    existentes = ProductTemplate.search_read(
        [('default_code', '!=', False)],
        ['id', 'default_code', 'name', 'barcode']
    )
    prod_cache = {p['default_code']: p['id'] for p in existentes}
    existing_barcodes = {p['barcode'] for p in existentes if p['barcode']}
    print(f"  -> {len(prod_cache)} productos ya existen actualmente en la base.")

    creados_prod = 0
    actualizados_prod = 0
    errores_prod = 0

    for idx, p in enumerate(data_prod, start=1):
        numpro = p['default_code']
        nombre = p['name']
        full_cat = p['category_full_path']
        categ = category_map.get(full_cat)
        
        # Precio de venta
        pv = p['list_price'] if PRECIO_VENTA_NETO else p['list_price_con_iva']
        costo = p['standard_price']
        
        # Impuesto IVA
        tasa = p['tasa_iva']
        tax_rec = tax_map.get(tasa)
        taxes_ids = [(6, 0, [tax_rec.id])] if tax_rec else [(6, 0, [])]

        # Código de barras (evitar duplicados existentes)
        bc = p.get('barcode', '')
        if bc and bc in existing_barcodes and numpro not in prod_cache:
            bc = False  # Omitir si ya lo tiene otro producto en la BD

        vals = {
            'name': nombre,
            'default_code': numpro,
            'list_price': pv,
            'standard_price': costo,
            'categ_id': categ.id if categ else env.ref('product.product_category_all').id,
            'taxes_id': taxes_ids,
            'active': not p.get('inactivo', False)
        }

        if bc:
            vals['barcode'] = bc
            existing_barcodes.add(bc)

        # Ajuste de tipo almacenable según versión
        if has_is_storable:
            vals['is_storable'] = True
            vals['type'] = 'consu'
        elif has_detailed_type:
            vals['detailed_type'] = 'product'
        else:
            vals['type'] = 'product'

        # Asignación de Marca
        marca = p.get('marca')
        if marca and marca != 'S/MARCAS':
            if brand_field:
                # Si existe un modelo para la marca
                rel_model = ProductTemplate._fields[brand_field].comodel_name
                if rel_model and rel_model in env:
                    b_rec = env[rel_model].search([('name', '=', marca)], limit=1)
                    if not b_rec:
                        b_rec = env[rel_model].create({'name': marca})
                    vals[brand_field] = b_rec.id
            elif marca in tags_map:
                vals['product_tag_ids'] = [(4, tags_map[marca].id)]

        try:
            prod_id = prod_cache.get(numpro)
            if prod_id:
                # Actualización de producto existente
                template = ProductTemplate.browse(prod_id)
                template.write(vals)
                actualizados_prod += 1
            else:
                # Creación de nuevo producto
                template = ProductTemplate.create(vals)
                prod_cache[numpro] = template.id
                creados_prod += 1

            # Vincular Regla de Proveedor (product.supplierinfo)
            numprv = p.get('numprv')
            partner = partner_map.get(numprv)
            if partner and template:
                # Verificar si ya tiene el proveedor cargado
                supp_info = SupplierInfo.search([
                    ('product_tmpl_id', '=', template.id),
                    ('partner_id', '=', partner.id)
                ], limit=1)
                if not supp_info:
                    SupplierInfo.create({
                        'product_tmpl_id': template.id,
                        'partner_id': partner.id,
                        'product_code': p.get('codartpro', ''),
                        'price': costo,
                        'min_qty': 1.0
                    })

        except Exception as e:
            errores_prod += 1
            print(f"  [ERROR] Producto numpro={numpro}: {e}")

        if idx % BATCH_SIZE == 0 or idx == len(data_prod):
            print(f"  ... Procesados {idx}/{len(data_prod)} productos ({creados_prod} creados, {actualizados_prod} actualizados, {errores_prod} errores)")

    # --------------------------------------------------------------------------
    # RESUMEN Y GESTIÓN TRANSACCIONAL
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("RESUMEN DE EJECUCIÓN")
    print(f"- Total Productos Procesados: {len(data_prod)}")
    print(f"  * Creados:     {creados_prod}")
    print(f"  * Actualizados:{actualizados_prod}")
    print(f"  * Errores:     {errores_prod}")
    print(f"- Categorías Hijas Creadas:   {creadas_cat}")
    print(f"- Categorías Existentes:      {existentes_cat}")
    print("=" * 80)

    if DRY_RUN:
        env.cr.rollback()
        print("\n>>> MODO DRY-RUN: Transacción REVERTIDA (ROLLBACK). Ningún dato fue modificado en la base. <<<")
        print("Para aplicar los cambios definitivamente en producción, establece 'DRY_RUN = False' y vuelve a ejecutar.\n")
    else:
        env.cr.commit()
        print("\n>>> MODO PRODUCCIÓN: Transacción CONFIRMADA (COMMIT). Los cambios se aplicaron exitosamente. <<<\n")

# Ejecución automática al correr en Odoo Shell
if 'env' in locals():
    ejecutar_migracion(env)
else:
    print("[INFO] Este script está diseñado para ejecutarse dentro de Odoo Shell ('odoo-bin shell').")
    print("Ejemplo de comando: python3 odoo-bin shell -d <mi_bd> < cargar_productos_odoo_shell.py")

