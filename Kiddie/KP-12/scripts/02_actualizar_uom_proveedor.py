# -*- coding: utf-8 -*-
import gzip
import base64
import json
import os

h('02 - ACTUALIZAR UNIDAD DE MEDIDA DE COMPRA EN PROVEEDORES (product.supplierinfo)')

# -------------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------------
env_dry_run = os.environ.get('DRY_RUN', '1').lower()
DRY_RUN = env_dry_run not in ('0', 'false', 'no')

env_up_price = os.environ.get('UPDATE_PRICE', '0').lower()
ACTUALIZAR_PRECIO = env_up_price in ('1', 'true', 'si', 'yes')

mode_str = 'DRY-RUN (Simulación sin persistir)' if DRY_RUN else 'PRODUCCIÓN (PERSISTENTE / COMMIT)'
sub('Modo de Ejecución: %s' % mode_str)
sub('Ajuste de Precio a Bulto Completo: %s' % ('ACTIVADO' if ACTUALIZAR_PRECIO else 'DESACTIVADO (Mantiene precio original)'))

# -------------------------------------------------------------------------
# 0. INSPECCIÓN DE CAMPOS DE product.supplierinfo EN ODOO 19
# -------------------------------------------------------------------------
sub('0. Inspección de Campos en product.supplierinfo')
SupplierInfo = env['product.supplierinfo']
uom_field_name = None

for fname, f in sorted(SupplierInfo._fields.items()):
    comodel = getattr(f, 'comodel_name', '')
    fstring = f.string or ''
    is_uom_cand = comodel == 'uom.uom' or 'uom' in fname.lower() or 'unidad' in fstring.lower() or 'unit' in fstring.lower()
    if is_uom_cand:
        print('  -> Campo candidato: %-25s | Tipo: %-10s | Etiqueta: %r | Comodel: %s' % (fname, f.type, fstring, comodel))
        if comodel == 'uom.uom' and not uom_field_name:
            uom_field_name = fname

# Dump de un registro de prueba (producto 37303)
test_tmpl = env['product.template'].search([('default_code', '=', '37303')], limit=1)
if test_tmpl and test_tmpl.seller_ids:
    test_seller = test_tmpl.seller_ids[0]
    print('\n  Ejemplo producto [37303] - Registro seller actual:')
    for fname in sorted(test_seller._fields):
        val = getattr(test_seller, fname, None)
        f = test_seller._fields[fname]
        if f.type in ('many2one', 'char', 'float', 'integer', 'selection'):
            print('    %-30s = %r (%s)' % (fname, val.display_name if f.type == 'many2one' and val else val, f.type))

if not uom_field_name:
    print('\n[!] AVISO: No se detectó un campo Many2one hacia uom.uom en product.supplierinfo.')
    print('    Campos disponibles en product.supplierinfo: %s' % list(SupplierInfo._fields.keys()))

# Payload con 961 productos donde uni_compra > 1
PAYLOAD_B64 = '''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'''

try:
    raw_json = gzip.decompress(base64.b64decode(PAYLOAD_B64)).decode('utf-8')
    data = json.loads(raw_json)
    print('\n[*] Payload desempacado correctamente: %s productos con uni_compra > 1.' % len(data))
except Exception as e:
    print('[!] Error desempacando payload: %s' % e)
    data = {}

if not data or not uom_field_name:
    print('Deteniendo ejecución hasta confirmar el campo de unidad en product.supplierinfo.')
else:
    print('[*] Campo de Unidad de Medida detectado para product.supplierinfo: %r' % uom_field_name)

    # 1. Identificar la Unidad Base de Medida
    sub('1. Identificación de Unidad Base')
    base_uom = env.ref('uom.product_uom_unit', raise_if_not_found=False)
    if not base_uom:
        base_uom = env['uom.uom'].search([('name', 'in', ['Units', 'Unidades', 'Unit(s)'])], limit=1)
    if not base_uom:
        base_uom = env['uom.uom'].search([('relative_uom_id', '=', False), ('active', '=', True)], limit=1)
    print('[*] Unidad base de referencia: [%s] %s' % (base_uom.id, base_uom.name))

    # 2. Cachear / Buscar las UdMs de compra en uom.uom
    sub('2. Verificación de Unidades de Compra en uom.uom')
    distinct_ucs = sorted(list(set(item['uc'] for item in data.values())))
    uom_by_uc = {}
    for uc in distinct_ucs:
        fuc = float(uc)
        uom_rec = env['uom.uom'].search([
            ('relative_uom_id', '=', base_uom.id),
            ('relative_factor', '=', fuc)
        ], limit=1)
        if not uom_rec:
            uom_rec = env['uom.uom'].search([
                ('name', 'in', ['Bulto x %s' % uc, 'Caja x %s' % uc, 'Pack of %s' % uc])
            ], limit=1)
        if not uom_rec:
            uom_rec = env['uom.uom'].create({
                'name': 'Bulto x %s' % uc,
                'relative_uom_id': base_uom.id,
                'relative_factor': fuc,
                'rounding': 0.001,
                'active': True,
            })
        uom_by_uc[uc] = uom_rec
    print('[*] %s unidades de compra listas en memoria.' % len(uom_by_uc))

    # 3. Buscar productos en Odoo y actualizar su product.supplierinfo
    sub('3. Actualización de %s en Líneas de Proveedor' % uom_field_name)
    codes = list(data.keys())
    tmpls = env['product.template'].search([('default_code', 'in', codes)])
    tmpl_by_code = {t.default_code: t for t in tmpls}

    stats = {
        'total_productos_en_planilla': len(codes),
        'productos_encontrados': len(tmpl_by_code),
        'productos_no_encontrados': 0,
        'productos_sin_proveedor': 0,
        'lineas_proveedor_actualizadas': 0,
        'lineas_proveedor_ya_correctas': 0,
        'precios_actualizados_a_bulto': 0,
        'errores': 0
    }
    sin_proveedor = []
    no_encontrados = []

    for code, info in data.items():
        tmpl = tmpl_by_code.get(code)
        if not tmpl:
            stats['productos_no_encontrados'] += 1
            if len(no_encontrados) < 15:
                no_encontrados.append(code)
            continue

        uc = info['uc']
        costo_unitario = info.get('costo', 0.0)
        target_uom = uom_by_uc.get(uc)
        if not target_uom:
            stats['errores'] += 1
            continue

        sellers = tmpl.seller_ids
        if not sellers:
            stats['productos_sin_proveedor'] += 1
            if len(sin_proveedor) < 15:
                sin_proveedor.append(code)
            continue

        for seller in sellers:
            vals_to_write = {}
            current_uom = getattr(seller, uom_field_name, None)
            if current_uom != target_uom:
                vals_to_write[uom_field_name] = target_uom.id

            if ACTUALIZAR_PRECIO and costo_unitario > 0:
                precio_bulto = round(costo_unitario * uc, 3)
                if abs(seller.price - precio_bulto) > 0.01:
                    vals_to_write['price'] = precio_bulto
                    stats['precios_actualizados_a_bulto'] += 1

            if vals_to_write:
                try:
                    seller.write(vals_to_write)
                    stats['lineas_proveedor_actualizadas'] += 1
                except Exception as e:
                    stats['errores'] += 1
                    print('[!] Error actualizando seller en [%s] %s: %s' % (code, tmpl.name, e))
            else:
                stats['lineas_proveedor_ya_correctas'] += 1

        # Asegurar también que target_uom esté en tmpl.uom_ids (Embalajes del producto)
        if target_uom.id not in tmpl.uom_ids.ids:
            tmpl.write({'uom_ids': [(4, target_uom.id)]})

    # 4. Resumen Estadístico
    sub('4. Resumen de Resultados')
    for k, v in stats.items():
        print('  %-35s: %s' % (k.replace('_', ' ').capitalize(), v))

    if sin_proveedor:
        print('\nPrimeros productos sin línea de proveedor en Odoo:\n  %s' % ', '.join(sin_proveedor))
    if no_encontrados:
        print('\nPrimeros productos no encontrados en Odoo:\n  %s' % ', '.join(no_encontrados))

    # Cierre transaccional
    if DRY_RUN:
        env.cr.rollback()
        print('\n' + '>' * 12 + ' [DRY-RUN] Se ejecutó ROLLBACK. Base de datos 100%% intacta. ' + '<' * 12)
    else:
        env.cr.commit()
        print('\n' + '>' * 12 + ' [PRODUCCIÓN] Se ejecutó COMMIT. Unidades de compra guardadas con éxito! ' + '<' * 12)
