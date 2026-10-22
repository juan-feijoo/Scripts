# -*- coding: utf-8 -*-
"""
================================================================================
DIAGNÓSTICO ESPECÍFICO: POR QUÉ NO SE VE EL CAMPO Y QUÉ ROMPE A STUDIO
================================================================================
Este script averigua con precisión quirúrgica:
1. Qué vista exacta carga la Acción 536 (la de la URL en producción).
2. Si la acción 536 tiene campos filtrados, vistas personalizadas o dominios.
3. Qué datos devuelve web_read para la orden 246520 (S228753).
4. Si el campo x_studio_obra_padre_id está habilitado en fields_get para el usuario.
5. Simula las operaciones de Studio sobre la vista de formulario para capturar el error exacto.
================================================================================
"""

from lxml import etree

print("=" * 80)
print("1. INSPECCIÓN DE LA ACCIÓN 536 (LA QUE SE ABRE EN EL NAVEGADOR)")
print("=" * 80)

action = env['ir.actions.act_window'].browse(536)
if action.exists():
    print(f"Acción ID: {action.id} | Nombre: {action.name} | Res Model: {action.res_model}")
    print(f"View Mode: {action.view_mode}")
    print(f"Views configuradas en la acción:")
    for v in action.view_ids:
        print(f"  - Modo: {v.view_mode:6s} | Vista ID: {v.view_id.id:5d} | Nombre: {v.view_id.name}")
    if action.view_id:
        print(f"Vista directa (view_id): ID {action.view_id.id} ({action.view_id.name})")
else:
    print("[AVISO] No se encontró la acción 536.")

print("\n" + "=" * 80)
print("2. SIMULACIÓN DE web_read SOBRE LA ORDEN S228753 (ID: 246520)")
print("=" * 80)

order_246520 = env['sale.order'].browse(246520)
if order_246520.exists():
    fields_to_read = [
        'name',
        'x_studio_nv_numero_de_orfa',
        'x_studio_obra_padre_id',
        'x_studio_nv_numero_de_obra_padre',
        'studio_almacen' if 'studio_almacen' in env['sale.order']._fields else 'warehouse_id',
        'opportunity_id'
    ]
    try:
        read_res = order_246520.read(fields_to_read)
        print("Datos leídos por el ORM para la orden 246520:")
        for k, val in read_res[0].items():
            print(f"  - {k}: {val}")
    except Exception as e:
        print(f"[ERROR al leer campos]: {e}")
else:
    print("No se encontró la orden 246520.")

print("\n" + "=" * 80)
print("3. VERIFICACIÓN DE SEGURIDAD / PERMISOS DE 'x_studio_obra_padre_id'")
print("=" * 80)

field_info = env['sale.order'].fields_get(['x_studio_obra_padre_id'])
if 'x_studio_obra_padre_id' in field_info:
    info = field_info['x_studio_obra_padre_id']
    print(f"Atributos en fields_get:")
    print(f"  - string: {info.get('string')}")
    print(f"  - type: {info.get('type')}")
    print(f"  - readonly: {info.get('readonly')}")
    print(f"  - relation: {info.get('relation')}")
    print(f"  - groups: {info.get('groups') or 'Público (sin restricción de grupo)'}")
else:
    print("[ALERTA CRÍTICA] 'x_studio_obra_padre_id' NO aparece en fields_get de sale.order!")

print("\n" + "=" * 80)
print("4. SIMULACIÓN DE ODOO STUDIO (BUSCANDO EL RPC_ERROR)")
print("=" * 80)

# Buscamos simular los métodos que Studio ejecuta al editar la vista
sale_form = env.ref('sale.view_order_form')

# Método 1: get_combined_arch en ir.ui.view
try:
    print("Probando get_combined_arch...")
    combined = env['ir.ui.view'].browse(sale_form.id)._get_combined_arch()
    print("[OK] get_combined_arch compila correctamente.")
except Exception as e:
    print(f"[ERROR en _get_combined_arch]: {e}")

# Método 2: Simular si la vista 4170 o 4609 causan problemas en Studio
print("\nProbando si Studio falla por la Vista 4170 (Reserva de Materiales):")
v4170 = env['ir.ui.view'].browse(4170)
if v4170.exists():
    print(f"Vista 4170 está activa: {v4170.active}")
    # Verificar si tiene page sin name
    tree_4170 = etree.fromstring(v4170.arch_db.encode('utf-8'))
    pages_without_name = tree_4170.xpath("//page[not(@name)]")
    print(f"Páginas sin atributo 'name' en vista 4170: {len(pages_without_name)}")
    for p in pages_without_name:
        print(f"  -> Page con string='{p.get('string')}' NO TIENE ATRIBUTO name='...'!")

print("\nProbando si Studio falla por la Vista 4609:")
v4609 = env['ir.ui.view'].browse(4609)
if v4609.exists():
    print(f"Vista 4609: Modelo={v4609.model} | Activa={v4609.active}")
    tree_4609 = etree.fromstring(v4609.arch_db.encode('utf-8'))
    pages_4609 = tree_4609.xpath("//page[not(@name)]")
    print(f"Páginas sin atributo 'name' en vista 4609: {len(pages_4609)}")

print("\n" + "=" * 80)
print("FIN DEL DIAGNÓSTICO.")
print("=" * 80)
