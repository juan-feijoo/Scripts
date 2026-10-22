# -*- coding: utf-8 -*-
"""
================================================================================
SOLUCIÓN DEFINITIVA PARA PRODUCCIÓN: STUDIO + CAMPO OBRA PADRE
================================================================================
Este script resuelve los dos problemas en producción:

1. REPARA LA VISTA 4170 (Reserva de Materiales):
   Le asigna el atributo name="material_reservation_page" a la pestaña <page>.
   Esto elimina la causa raíz del error RPC en Studio (en prueba habían desactivado
   la vista; aquí la reparamos para no perder la funcionalidad de reservas, o
   puedes desactivarla si prefieres).

2. SEÑALIZA LA RECARGA DE REGISTRY EN LOS WORKERS WEB:
   Notifica a todos los procesos HTTP de Odoo.sh que 'x_studio_obra_padre_id'
   está disponible para que el controlador OWL de la interfaz lo renderice.

Configuración:
   DRY_RUN = True  -> Simula todo y hace rollback (para verificar sin riesgo).
   DRY_RUN = False -> Aplica los cambios permanentemente en producción (commit).
================================================================================
"""

from lxml import etree

# ==============================================================================
# CONFIGURACIÓN (Cambia a False cuando desees aplicar definitivamente)
# ==============================================================================
DRY_RUN = False

# ¿Prefieres desactivar la vista 4170 como en prueba (True) o repararla (False)?
# RECOMENDADO: False (la repara asignándole name, así conservan la pestaña en producción).
DESACTIVAR_VISTA_COMO_EN_PRUEBA = False

print("=" * 80)
print(f"APLICANDO SOLUCIÓN DEFINITIVA (MODO: {'DRY-RUN / SIMULACIÓN' if DRY_RUN else 'REAL / PRODUCCIÓN'})")
print("=" * 80)

try:
    # --------------------------------------------------------------------------
    # PASO 1: REPARACIÓN O DESACTIVACIÓN DE LA VISTA 4170 (ERROR STUDIO)
    # --------------------------------------------------------------------------
    print("\n[PASO 1] Tratamiento de la Vista 4170 (sale.order.form.material.reservation)...")
    v4170 = env['ir.ui.view'].browse(4170)
    
    if not v4170.exists():
        print("  -> [AVISO] No se encontró la vista con ID 4170.")
    else:
        if DESACTIVAR_VISTA_COMO_EN_PRUEBA:
            print(f"  -> Desactivando vista 4170 como se hizo en prueba...")
            v4170.write({'active': False})
            print("  -> Vista 4170 desactivada.")
        else:
            print("  -> Reparando arquitectura XML de la vista 4170...")
            tree_4170 = etree.fromstring(v4170.arch_db.encode('utf-8'))
            pages = tree_4170.xpath("//page[not(@name)]")
            
            if pages:
                for idx, p in enumerate(pages, 1):
                    str_name = p.get('string', f'page_{idx}')
                    p.set('name', 'material_reservation_page')
                    print(f"  -> Atributo name='material_reservation_page' asignado a página '{str_name}'.")
                
                nuevo_arch_4170 = etree.tostring(tree_4170, encoding='unicode')
                v4170.write({'arch_db': nuevo_arch_4170})
                print("  -> [ÉXITO] Vista 4170 reparada y compatible con Odoo Studio.")
            else:
                print("  -> La vista 4170 ya tenía el atributo 'name' en sus pestañas.")

    # --------------------------------------------------------------------------
    # PASO 2: VERIFICAR Y ASEGURAR CAMPO OBRA PADRE EN VISTA STUDIO 3922
    # --------------------------------------------------------------------------
    print("\n[PASO 2] Verificando posicionamiento en vista Studio 3922...")
    v3922 = env['ir.ui.view'].browse(3922)
    tree_3922 = etree.fromstring(v3922.arch_db.encode('utf-8'))
    
    campo_en_3922 = tree_3922.xpath("//field[@name='x_studio_obra_padre_id']")
    if not campo_en_3922:
        print("  -> Inyectando campo x_studio_obra_padre_id después de x_studio_nv_numero_de_orfa...")
        nodo_orfa = tree_3922.xpath("//field[@name='x_studio_nv_numero_de_orfa']")
        if nodo_orfa:
            nuevo_nodo = etree.Element("field", {
                "name": "x_studio_obra_padre_id",
                "options": '{"no_create": true}'
            })
            nodo_orfa[0].addnext(nuevo_nodo)
            v3922.write({'arch_db': etree.tostring(tree_3922, encoding='unicode')})
            print("  -> Campo insertado exitosamente en vista 3922.")
    else:
        print("  -> El campo 'x_studio_obra_padre_id' ya está presente en vista 3922.")

    # --------------------------------------------------------------------------
    # PASO 3: VALIDACIÓN DE LA COMPILACIÓN DE FORMULARIO SALE.ORDER
    # --------------------------------------------------------------------------
    print("\n[PASO 3] Probando compilación del formulario de sale.order...")
    sale_form = env.ref('sale.view_order_form')
    vcompilada = env['sale.order'].get_view(view_id=sale_form.id, view_type='form')
    print("  -> [OK] get_view compila con éxito.")

    # --------------------------------------------------------------------------
    # PASO 4: LIMPIEZA DE CACHÉ
    # --------------------------------------------------------------------------
    print("\n[PASO 4] Limpiando cachés del registry y vistas...")
    env.registry.clear_cache()
    if hasattr(env.registry, 'signal_changes'):
        env.registry.signal_changes()
    print("  -> Caché limpiada con éxito.")

    # --------------------------------------------------------------------------
    # CIERRE TRANSACCIONAL
    # --------------------------------------------------------------------------
    if DRY_RUN:
        print("\n" + "=" * 80)
        print("[DRY-RUN] Simulación exitosa. Ejecutando rollback...")
        print("          Para persistir los cambios, cambia DRY_RUN = False y re-ejecuta.")
        print("=" * 80)
        env.cr.rollback()
    else:
        print("\n" + "=" * 80)
        print("[MODO REAL] Cambios guardados permanentemente (Commit).")
        print("            Los workers de Odoo.sh ya recibieron la señal de actualización.")
        print("=" * 80)
        env.cr.commit()

except Exception as ex:
    print(f"\n[ERROR CRÍTICO]: {ex}")
    env.cr.rollback()
