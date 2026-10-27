# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE CARGA Y CONFIRMACIÓN DE INVENTARIO INICIAL (ODOO 17 / 18 ENTERPRISE)
================================================================================
Diseñado para: Odoo.sh (odoo-bin shell) o ejecución directa mediante ORM.
Empresa / Localización: Argentina (l10n_ar) / Sabra Bazar.
Modelos involucrados:
  - product.product (búsqueda por barcode y default_code)
  - stock.quant (con contexto inventory_mode=True y action_apply_inventory())
  - stock.location (ubicación interna de stock)

CARACTERÍSTICAS CLAVE:
  1. Configuración DRY-RUN (Simulación completa con rollback garantizado).
  2. Detección automática de versión Odoo 17 vs 18 (soporte para 'is_storable').
  3. Filtro automático de servicios o gastos (ignora adelanto de sueldos, alquileres, etc.).
  4. Manejo y unificación de códigos duplicados con alertas en el log.
  5. Procesamiento por lotes (Batch) para evitar sobrecarga de memoria en miles de registros.
  6. Reporte detallado de productos no encontrados, inactivos y totales confirmados.
================================================================================
"""

import os
import csv
import zipfile
import xml.etree.ElementTree as ET
import logging

_logger = logging.getLogger("odoo.inventory.importer")

# ==============================================================================
# CONFIGURACIÓN DE PARÁMETROS
# ==============================================================================
CONFIG = {
    # True: Simula la carga, genera estadísticas y hace ROLLBACK (No modifica la base)
    # False: Ejecuta los ajustes de stock y hace COMMIT
    'DRY_RUN': False,

    # Ruta del archivo de inventario en el servidor / contenedor
    # Soporta tanto .csv como .xls / .xlsx
    'FILE_PATH': 'inventario_preparado.csv',

    # Nombre técnico o referencia de la ubicación destino.
    # Si es False o None, busca automáticamente la ubicación interna principal del almacén (WH/Stock)
    'LOCATION_BARCODE_OR_NAME': False,

    # Si es True, solo ajusta productos cuya cantidad en el archivo sea > 0.
    # Si es False, también ajusta los productos con cantidad 0 (útil si hay stock previo que debe quedar en 0)
    'ONLY_POSITIVE_QTY': True,

    # Tamaño del lote para llamar a action_apply_inventory()
    'BATCH_SIZE': 200,

    # Si se encuentran códigos repetidos en el archivo:
    # True: Suma las cantidades y emite advertencia
    # False: Sobrescribe con el último valor encontrado
    'SUM_DUPLICATES': True,
}


def parse_inventory_file(file_path):
    """
    Lee archivos CSV o Excel (.xls/.xlsx) sin requerir librerías externas (solo standard library).
    Retorna una lista de diccionarios con formato:
    [{'code': '7795587005014', 'name': '...', 'qty': 10.0, 'line': 4}, ...]
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    items = []

    if ext == '.csv':
        with open(file_path, mode='r', encoding='utf-8-sig', errors='replace') as f:
            # Detectar delimitador (coma o punto y coma)
            sample = f.read(2048)
            f.seek(0)
            delimiter = ';' if ';' in sample and sample.count(';') > sample.count(',') else ','
            reader = csv.reader(f, delimiter=delimiter)
            
            headers = [h.strip().lower() for h in next(reader, [])]
            
            # Mapeo flexible de columnas
            col_code = next((i for i, h in enumerate(headers) if any(k in h for k in ['código', 'codigo', 'code', 'barcode', 'referencia'])), 0)
            col_name = next((i for i, h in enumerate(headers) if any(k in h for k in ['nombre', 'name', 'descripcion', 'producto'])), 1)
            col_qty = next((i for i, h in enumerate(headers) if any(k in h for k in ['cantidad', 'qty', 'stock', 'cant'])), 3 if len(headers) > 3 else len(headers) - 1)

            for line_no, row in enumerate(reader, start=2):
                if not row or len(row) <= max(col_code, col_qty):
                    continue
                code = row[col_code].strip()
                name = row[col_name].strip() if len(row) > col_name else ''
                qty_raw = row[col_qty].strip().replace(',', '.')
                
                if not code:
                    continue
                
                try:
                    qty = float(qty_raw)
                except ValueError:
                    qty = 0.0

                items.append({
                    'code': code,
                    'name': name,
                    'qty': qty,
                    'line': line_no,
                })

    elif ext in ['.xls', '.xlsx']:
        # Parser nativo openxml para archivos xlsx (incluso si tienen extensión .xls)
        with zipfile.ZipFile(file_path) as z:
            sst = []
            if 'xl/sharedStrings.xml' in z.namelist():
                tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                sst = [''.join(t.text or '' for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')) 
                       for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si')]
            
            sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
            ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows = sheet.findall('.//ns:row', ns)
            
            for line_no, r in enumerate(rows[1:], start=2):
                cells = r.findall('ns:c', ns)
                if not cells or len(cells) < 4:
                    continue
                
                def get_cell_val(cell):
                    t = cell.get('t')
                    v = cell.find('ns:v', ns)
                    val = v.text if v is not None else ''
                    if t == 's' and val.isdigit() and int(val) < len(sst):
                        val = sst[int(val)]
                    return val.strip() if val else ''

                code = get_cell_val(cells[0])
                name = get_cell_val(cells[1]) if len(cells) > 1 else ''
                qty_raw = get_cell_val(cells[3]) if len(cells) > 3 else '0'
                qty_raw = qty_raw.replace(',', '.')

                if not code:
                    continue

                try:
                    qty = float(qty_raw)
                except ValueError:
                    qty = 0.0

                items.append({
                    'code': code,
                    'name': name,
                    'qty': qty,
                    'line': line_no,
                })
    else:
        raise ValueError(f"Extensión de archivo no soportada: {ext}")

    return items


def is_storable_product(product):
    """
    Compatibilidad Odoo 17 y 18:
    En Odoo 18: campo booleano 'is_storable' (type suele ser 'consu').
    En Odoo 17: campo selection 'type' == 'product'.
    """
    if hasattr(product, 'is_storable'):
        return product.is_storable
    return product.type == 'product'


def run_inventory_import(env, config_overrides=None):
    """
    Función principal ejecutada dentro del entorno Odoo (env).
    """
    cfg = dict(CONFIG)
    if config_overrides:
        cfg.update(config_overrides)

    dry_run = cfg['DRY_RUN']
    file_path = cfg['FILE_PATH']
    batch_size = cfg['BATCH_SIZE']

    print("=" * 80)
    print(f" INICIANDO CARGA DE INVENTARIO INICIAL | MODO: {'[DRY-RUN - SIMULACIÓN]' if dry_run else '[EJECUCIÓN REAL - COMMIT]'}")
    print("=" * 80)
    print(f"Archivo: {file_path}")
    print(f"Compañía actual: {env.company.name} (ID: {env.company.id})")
    print(f"Usuario: {env.user.name} (ID: {env.user.id})")

    # 1. Determinar ubicación de inventario
    Location = env['stock.location']
    location = None
    if cfg['LOCATION_BARCODE_OR_NAME']:
        loc_str = cfg['LOCATION_BARCODE_OR_NAME']
        location = Location.search([
            ('usage', '=', 'internal'),
            '|', ('barcode', '=', loc_str), ('name', '=', loc_str)
        ], limit=1)

    if not location:
        warehouse = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
        if not warehouse:
            raise ValueError(f"No se encontró un almacén activo para la compañía {env.company.name}")
        location = warehouse.lot_stock_id

    print(f"Ubicación de destino: {location.complete_name} (ID: {location.id})")

    # 2. Parsear archivo
    raw_items = parse_inventory_file(file_path)
    print(f"Filas leídas del archivo: {len(raw_items)}")

    # 3. Agrupar y detectar duplicados
    grouped_items = {}
    duplicates = {}
    for item in raw_items:
        code = item['code']
        qty = item['qty']
        
        if code in grouped_items:
            duplicates[code] = duplicates.get(code, 1) + 1
            if cfg['SUM_DUPLICATES']:
                grouped_items[code]['qty'] += qty
            else:
                grouped_items[code]['qty'] = qty
        else:
            grouped_items[code] = {
                'code': code,
                'name': item['name'],
                'qty': qty,
                'lines': [item['line']]
            }

    if duplicates:
        print(f"\n[AVISO] Se detectaron {len(duplicates)} códigos duplicados en el archivo:")
        for dup_code, count in list(duplicates.items())[:10]:
            print(f"   - Código: '{dup_code}' apareció {count} veces. Qty consolidada: {grouped_items[dup_code]['qty']}")
        if len(duplicates) > 10:
            print(f"   ... y {len(duplicates) - 10} más.")

    # 4. Procesar productos y quants
    Product = env['product.product']
    Quant = env['stock.quant']

    matched_products = []
    not_found_products = []
    skipped_non_storable = []
    skipped_zero_qty = []

    print("\nProcesando productos en la base de datos de Odoo...")
    
    total_to_process = len(grouped_items)
    for idx, (code, data) in enumerate(grouped_items.items(), start=1):
        target_qty = data['qty']

        if cfg['ONLY_POSITIVE_QTY'] and target_qty <= 0:
            skipped_zero_qty.append((code, data['name'], target_qty))
            continue

        # Búsqueda por barcode y por default_code (considerando productos archivados)
        product = Product.with_context(active_test=False).search([
            '|', ('barcode', '=', code), ('default_code', '=', code)
        ], limit=1)

        if not product:
            not_found_products.append((code, data['name'], target_qty))
            continue

        if not product.active:
            print(f"   [ALERTA] Producto archivado encontrado: [{code}] {product.display_name}. Se reactivará.")
            product.active = True

        if not is_storable_product(product):
            skipped_non_storable.append((code, product.display_name, getattr(product, 'type', 'n/a')))
            continue

        matched_products.append({
            'product': product,
            'code': code,
            'qty': target_qty,
        })

    print(f"\nResultados del análisis previo:")
    print(f" - Productos coincidentes y almacenables: {len(matched_products)}")
    print(f" - Productos omitidos con cantidad <= 0: {len(skipped_zero_qty)}")
    print(f" - Productos NO encontrados en Odoo: {len(not_found_products)}")
    print(f" - Productos NO almacenables (servicios/gastos omitidos): {len(skipped_non_storable)}")

    if skipped_non_storable:
        print("\nEjemplos de productos no almacenables omitidos:")
        for scode, sname, stype in skipped_non_storable[:5]:
            print(f"   * [{scode}] {sname} (Tipo: {stype})")

    if not_found_products:
        print(f"\n[ATENCIÓN] {len(not_found_products)} códigos no existen en Odoo (Revisar antes del Día D):")
        for nf_code, nf_name, nf_qty in not_found_products[:10]:
            print(f"   * Código: {nf_code} | {nf_name} | Qty solicitada: {nf_qty}")
        if len(not_found_products) > 10:
            print(f"   ... y {len(not_found_products) - 10} más.")

    # 5. Crear o actualizar stock.quant
    print(f"\nGenerando líneas de conteo de inventario (stock.quant)...")
    
    # Obtener campos permitidos en modo inventario (evita UserError por campos restringidos como company_id)
    allowed_create = set(Quant._get_inventory_fields_create()) if hasattr(Quant, '_get_inventory_fields_create') else {'product_id', 'location_id', 'inventory_quantity'}
    allowed_write = set(Quant._get_inventory_fields_write()) if hasattr(Quant, '_get_inventory_fields_write') else {'inventory_quantity'}

    total_matched = len(matched_products)
    quant_ids_list = []

    for idx, item in enumerate(matched_products, start=1):
        product = item['product']
        target_qty = item['qty']

        # Buscar quant existente para este producto en la ubicación
        quant = Quant.search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
            ('lot_id', '=', False),
            ('package_id', '=', False),
            ('owner_id', '=', False),
            ('company_id', '=', env.company.id),
        ], limit=1)

        # Usar contexto inventory_mode=True (CRÍTICO en Odoo 17 y 18)
        # Nota técnica: company_id no debe enviarse en vals porque stock.quant lo hereda de location_id
        if quant:
            vals = {'inventory_quantity': target_qty, 'user_id': env.user.id}
            vals = {k: v for k, v in vals.items() if k in allowed_write or k.startswith('x_')}
            quant.with_context(inventory_mode=True).write(vals)
        else:
            vals = {
                'product_id': product.id,
                'location_id': location.id,
                'inventory_quantity': target_qty,
                'user_id': env.user.id,
            }
            vals = {k: v for k, v in vals.items() if k in allowed_create or k.startswith('x_')}
            quant = Quant.with_company(env.company).with_context(inventory_mode=True).create(vals)

        quant_ids_list.append(quant.id)

        if idx % 500 == 0 or idx == total_matched:
            print(f"   Progreso quants preparados: {idx} / {total_matched}")

    all_quants = Quant.browse(quant_ids_list)
    print(f"\nTotal de quants preparados para ajuste: {len(all_quants)}")

    # 6. Aplicar ajustes (action_apply_inventory)
    try:
        if not dry_run:
            print(f"\nAplicando ajustes de inventario en lotes de {batch_size}...")
            quant_ids = all_quants.ids
            for i in range(0, len(quant_ids), batch_size):
                batch_ids = quant_ids[i:i + batch_size]
                batch_quants = Quant.browse(batch_ids)
                batch_quants.action_apply_inventory()
                print(f"   Lote aplicado: {min(i + batch_size, len(quant_ids))} / {len(quant_ids)}")

            # Confirmar transacción
            env.cr.commit()
            print("\n" + "=" * 80)
            print(" [OK] INVENTARIO APLICADO Y CONFIRMADO EXITOSAMENTE EN LA BASE DE DATOS.")
            print("=" * 80)
        else:
            # En modo Dry Run, simulamos la aplicación en todos los lotes para validar integridad total
            print(f"\n[DRY-RUN] Simulando aplicación de ajustes en lotes de {batch_size} para probar validaciones...")
            quant_ids = all_quants.ids
            for i in range(0, len(quant_ids), batch_size):
                batch_ids = quant_ids[i:i + batch_size]
                batch_quants = Quant.browse(batch_ids)
                batch_quants.action_apply_inventory()
                print(f"   [DRY-RUN] Lote verificado: {min(i + batch_size, len(quant_ids))} / {len(quant_ids)}")
            
            # Rollback absoluto garantizado
            env.cr.rollback()
            print("\n" + "=" * 80)
            print(" [DRY-RUN] SIMULACIÓN COMPLETADA CON ÉXITO - SE EJECUTÓ ROLLBACK.")
            print(" TODOS LOS QUANTS FUERON VALIDADOS CORRECTAMENTE.")
            print(" NINGÚN DATO FUE MODIFICADO EN LA BASE DE DATOS.")
            print("=" * 80)
    except Exception as e:
        env.cr.rollback()
        print(f"\n[ERROR] Ocurrió un error durante la aplicación de inventario: {e}")
        print("Se ha ejecutado ROLLBACK para proteger la base de datos.")
        raise e

    # 7. Resumen final
    print("\nRESUMEN FINAL DE LA OPERACIÓN:")
    print(f"  * Total líneas procesadas: {len(raw_items)}")
    print(f"  * Códigos únicos consolidados: {len(grouped_items)}")
    print(f"  * Quants ajustados: {len(all_quants)}")
    print(f"  * Códigos no encontrados: {len(not_found_products)}")
    print(f"  * Servicios omitidos: {len(skipped_non_storable)}")
    print("=" * 80)


if __name__ == '__main__':
    if 'env' in locals() or 'env' in globals():
        run_inventory_import(env)
    else:
        print("Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell) donde 'env' esté disponible.")
        print("Ejemplo: run_inventory_import(env, {'DRY_RUN': True})")
