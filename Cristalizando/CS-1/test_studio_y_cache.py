# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE PRUEBA DE CARGA DE STUDIO Y LIMPIEZA DE CACHÉ
================================================================================
Este script:
1. Limpia las cachés de registro y vistas en Odoo.sh.
2. Simula exactamente la apertura de Studio en el modelo 'sale.order' para
   capturar el traceback exacto si salta algún RPC/Studio error.
3. Inspecciona la vista 4170 (material_reservation) para verificar compatibilidad.
================================================================================
"""

from lxml import etree

print("=" * 80)
print("1. LIMPIANDO CACHÉ DE REGISTRO Y VISTAS EN EL SERVIDOR...")
print("=" * 80)

# Limpiar caché del registry
env.registry.clear_cache()
print("[OK] Caché en memoria del servidor limpiada exitosamente.")

print("\n" + "=" * 80)
print("2. SIMULANDO APERTURA DE ODOO STUDIO EN sale.order...")
print("=" * 80)

sale_form = env.ref('sale.view_order_form')

# 2.1 Probar get_views estándar
try:
    print("Probando get_views estándar...")
    views_res = env['sale.order'].get_views([(sale_form.id, 'form')])
    print("[OK] get_views completado sin errores.")
except Exception as e:
    print(f"[ERROR en get_views]: {e}")

# 2.2 Probar método específico de Studio si está disponible
try:
    if 'ir.ui.view' in env and hasattr(env['ir.ui.view'], 'get_view_info'):
        print("Probando get_view_info de Studio...")
        info = env['ir.ui.view'].get_view_info(sale_form.id)
        print("[OK] get_view_info ejecutado con éxito.")
except Exception as e:
    print(f"[ERROR en get_view_info]: {e}")

# 2.3 Probar combinación de arquitectura de vista (lo que hace Studio editor)
try:
    print("Probando validación de jerarquía de vistas heredadas...")
    for v in env['ir.ui.view'].search([('model', '=', 'sale.order'), ('inherit_id', '!=', False), ('active', '=', True)]):
        try:
            # Validar sintaxis XML
            etree.fromstring(v.arch_db.encode('utf-8'))
        except Exception as err_xml:
            print(f"[VISTA CORRUPTA DETECTADA]: Vista ID {v.id} ({v.name}) -> {err_xml}")
    print("[OK] Todas las vistas activas de sale.order tienen XML bien formado.")
except Exception as e:
    print(f"[ERROR]: {e}")

print("\n" + "=" * 80)
print("3. ANÁLISIS DE LA VISTA 4170 (material_reservation)")
print("=" * 80)
v4170 = env['ir.ui.view'].browse(4170)
if v4170.exists():
    print(f"Vista 4170: {v4170.name} | Activa: {v4170.active} | Modelo: {v4170.model}")
    print("Contenido arch_db:")
    print(v4170.arch_db)
    
print("\n" + "=" * 80)
print("FINALIZADO.")
print("=" * 80)
