# -*- coding: utf-8 -*-
"""
================================================================================
AUDITORÍA INTEGRAL DE VISTAS Y CAMPOS: CRM -> VENTAS (Odoo 17 / 18 / 19)
================================================================================
Propósito:
1. Revelar qué contiene exactamente la vista Studio 3922 y dónde quedó 'x_studio_obra_padre_id'.
2. Localizar la VERDADERA vista que contiene 'material_reservation_ids' (la que no estaba en 3922).
3. Verificar la consistencia del campo 'obra_padre_id' entre crm.lead y sale.order.
4. Inspeccionar el árbol XML final compilado (get_view) para ver visibilidad y posición relativa.
5. Probar datos reales sobre la última orden de venta y la orden S228753.

Modo: 100% LECTURA (AUDITORÍA). No realiza ningún commit ni altera la base de datos.
================================================================================
"""

import sys
from lxml import etree

def print_separator(title=""):
    print("\n" + "=" * 80)
    if title:
        print(f"  {title.upper()}")
        print("=" * 80)

print_separator("INICIANDO AUDITORÍA INTEGRAL DE DIAGNÓSTICO (ODOO 17/18/19)")

# ==============================================================================
# 1. INSPECCIÓN EXHAUSTIVA DE LA VISTA STUDIO 3922
# ==============================================================================
print_separator("1. INSPECCIÓN DE LA VISTA STUDIO 3922")

v3922 = env['ir.ui.view'].browse(3922)
if not v3922.exists():
    print("[ERROR CRÍTICO] La vista con ID 3922 no existe en esta base de datos.")
else:
    print(f"ID: {v3922.id} | Nombre: {v3922.name} | Modelo: {v3922.model} | Activa: {v3922.active}")
    print(f"XML ID: {v3922.xml_id or 'Sin XML ID'} | Hereda de: {v3922.inherit_id.name} (ID: {v3922.inherit_id.id})")
    print(f"Última modificación: {v3922.write_date} por usuario {v3922.write_uid.name}")
    
    print("\n--- CONTENIDO XML COMPLETO (arch_db) DE LA VISTA 3922 ---")
    arch_str = v3922.arch_db or ""
    print(arch_str)
    
    # Análisis de nodos dentro de 3922
    try:
        parser = etree.XMLParser(remove_blank_text=False)
        tree_3922 = etree.fromstring(arch_str.encode('utf-8'), parser)
        
        # Buscar campo x_studio_obra_padre_id
        nodes_obra = tree_3922.xpath("//field[@name='x_studio_obra_padre_id']")
        print(f"\n[DIAGNÓSTICO CAMPO 'x_studio_obra_padre_id' EN VISTA 3922]:")
        if nodes_obra:
            for idx, no in enumerate(nodes_obra, 1):
                parent = no.getparent()
                parent_tag = parent.tag if parent is not None else 'None'
                parent_expr = parent.get('expr') if parent is not None else ''
                print(f"  Coincidencia #{idx}: Dentro de <{parent_tag} expr=\"{parent_expr}\"> | Atributos: {dict(no.attrib)}")
        else:
            print("  -> NO se encontró <field name='x_studio_obra_padre_id'/> en el XML de 3922.")
            
        # Buscar campo x_studio_nv_numero_de_orfa
        nodes_orfa = tree_3922.xpath("//field[@name='x_studio_nv_numero_de_orfa']")
        print(f"\n[DIAGNÓSTICO CAMPO 'x_studio_nv_numero_de_orfa' EN VISTA 3922]:")
        if nodes_orfa:
            for idx, no in enumerate(nodes_orfa, 1):
                parent = no.getparent()
                parent_tag = parent.tag if parent is not None else 'None'
                parent_expr = parent.get('expr') if parent is not None else ''
                print(f"  Coincidencia #{idx}: Dentro de <{parent_tag} expr=\"{parent_expr}\"> | Atributos: {dict(no.attrib)}")
        else:
            print("  -> NO se encontró <field name='x_studio_nv_numero_de_orfa'/> en 3922 (puede estar en otra vista heredada o en la vista base).")

        # Buscar si material_reservation_ids existe aquí
        nodes_mat = tree_3922.xpath("//*[contains(@expr, 'material_reservation_ids')] | //field[@name='material_reservation_ids']")
        print(f"\n[MATERIAL RESERVATION EN 3922]: Encontrados = {len(nodes_mat)}")

    except Exception as e:
        print(f"[ERROR al parsear XML de 3922]: {e}")

# ==============================================================================
# 2. LOCALIZACIÓN GLOBAL DE 'material_reservation_ids' EN TODAS LAS VISTAS
# ==============================================================================
print_separator("2. RASTREO GLOBAL DE 'material_reservation_ids' (BUSCANDO LA VISTA CULPABLE)")

views_mat = env['ir.ui.view'].search([
    ('arch_db', 'ilike', 'material_reservation_ids')
])

print(f"Total de vistas encontradas con 'material_reservation_ids': {len(views_mat)}")

for v in views_mat:
    print("-" * 80)
    print(f"VISTA ID: {v.id} | Nombre: {v.name}")
    print(f"  - Modelo: {v.model} | Modo: {v.mode} | Activa: {v.active}")
    print(f"  - XML ID: {v.xml_id or 'Sin XML ID (Studio / Manual)'}")
    print(f"  - Padre: {v.inherit_id.name} (ID: {v.inherit_id.id if v.inherit_id else 'None'})")
    
    # Extraer los fragmentos relevantes
    for line_idx, line in enumerate((v.arch_db or '').splitlines(), 1):
        if any(term in line for term in ['material_reservation_ids', 'product_id', 'page', 'xpath']):
            print(f"    L{line_idx:03d}: {line.strip()}")

# ==============================================================================
# 3. AUDITORÍA DE CAMPOS CRM -> SALE.ORDER
# ==============================================================================
print_separator("3. COMPARATIVA TÉCNICA DE CAMPOS (crm.lead vs sale.order)")

# 3.1 Campo en CRM
crm_fields = env['ir.model.fields'].search([
    ('model', '=', 'crm.lead'),
    '|', ('name', 'ilike', 'obra_padre'), ('field_description', 'ilike', 'obra padre')
])
print("Campos en CRM (crm.lead):")
crm_target_name = None
for f in crm_fields:
    print(f"  -> Nombre: '{f.name}' | Label: '{f.field_description}' | Tipo: {f.ttype} | Comodel: {f.relation} | Stored: {f.store}")
    if f.relation == 'project.project':
        crm_target_name = f.name

# 3.2 Campo en Ventas
sale_fields = env['ir.model.fields'].search([
    ('model', '=', 'sale.order'),
    '|', ('name', 'ilike', 'obra_padre'), ('field_description', 'ilike', 'obra padre')
])
print("\nCampos en Ventas (sale.order):")
for f in sale_fields:
    print(f"  -> Nombre: '{f.name}' | Label: '{f.field_description}' | Tipo: {f.ttype} | Comodel: {f.relation}")
    print(f"     Related: '{f.related}' | Stored: {f.store} | Readonly: {f.readonly}")

# 3.3 Campo ORFA en Ventas
orfa_fields = env['ir.model.fields'].search([
    ('model', '=', 'sale.order'),
    '|', ('name', 'ilike', 'orfa'), ('field_description', 'ilike', 'orfa')
])
print("\nCampos de ORFA en Ventas (sale.order):")
for f in orfa_fields:
    print(f"  -> Nombre: '{f.name}' | Label: '{f.field_description}' | Tipo: {f.ttype}")

# ==============================================================================
# 4. PRUEBA DE DATOS EN VIVO (REGISTRO REAL DE SALE.ORDER)
# ==============================================================================
print_separator("4. VERIFICACIÓN DE DATOS EN REGISTRO REAL (PRUEBA DE FLUJO CRM -> SALE)")

# Intentar buscar la orden S228753 de la captura
order = env['sale.order'].search([('name', '=', 'S228753')], limit=1)
if not order:
    order = env['sale.order'].search([], order='id desc', limit=1)

if order:
    print(f"Analizando orden: {order.name} (ID: {order.id})")
    opp = getattr(order, 'opportunity_id', False)
    print(f"  - Oportunidad vinculada (opportunity_id): {opp.name if opp else 'NO TIENE OPORTUNIDAD VINCULADA'}")
    
    if opp and crm_target_name:
        val_crm = getattr(opp, crm_target_name, False)
        print(f"  - Valor en CRM ({crm_target_name}): {val_crm.display_name if val_crm else 'VACÍO (False)'}")
        
    for sf in sale_fields:
        val_sale = getattr(order, sf.name, False)
        display_val = val_sale.display_name if hasattr(val_sale, 'display_name') else val_sale
        print(f"  - Valor en sale.order ({sf.name}): {display_val}")
        
    for of in orfa_fields:
        val_orfa = getattr(order, of.name, False)
        print(f"  - Valor ORFA ({of.name}): {val_orfa}")
else:
    print("[AVISO] No hay órdenes de venta registradas para probar datos.")

# ==============================================================================
# 5. INSPECCIÓN DE LA VISTA FORMULARIO COMPILADA (get_view)
# ==============================================================================
print_separator("5. COMPILACIÓN FORMULARIO SALE.ORDER (get_view)")

try:
    sale_form = env.ref('sale.view_order_form')
    view_data = env['sale.order'].get_view(view_id=sale_form.id, view_type='form')
    arch_compiled = view_data['arch']
    
    doc = etree.fromstring(arch_compiled.encode('utf-8'))
    
    # Buscar x_studio_obra_padre_id en el árbol compilado
    nodes_compiled_obra = doc.xpath("//field[@name='x_studio_obra_padre_id']")
    print(f"Presencia de 'x_studio_obra_padre_id' en DOM final: {len(nodes_compiled_obra)}")
    if nodes_compiled_obra:
        n = nodes_compiled_obra[0]
        parent = n.getparent()
        print(f"  -> Tag padre: <{parent.tag}> con atributos: {dict(parent.attrib)}")
        print(f"  -> Atributos del campo: {dict(n.attrib)}")
        
        # Verificar hermano anterior y posterior
        prev = n.getprevious()
        nxt = n.getnext()
        print(f"  -> Elemento anterior: <{prev.tag if prev is not None else 'None'} name='{prev.get('name') if prev is not None else ''}'>")
        print(f"  -> Elemento siguiente: <{nxt.tag if nxt is not None else 'None'} name='{nxt.get('name') if nxt is not None else ''}'>")
    else:
        print("  -> [ALERTA] El campo 'x_studio_obra_padre_id' NO aparece en el DOM final de get_view!")

    # Buscar x_studio_nv_numero_de_orfa en el árbol compilado
    nodes_compiled_orfa = doc.xpath("//field[@name='x_studio_nv_numero_de_orfa']")
    print(f"\nPresencia de 'x_studio_nv_numero_de_orfa' en DOM final: {len(nodes_compiled_orfa)}")
    if nodes_compiled_orfa:
        n_orfa = nodes_compiled_orfa[0]
        parent_orfa = n_orfa.getparent()
        print(f"  -> Tag padre: <{parent_orfa.tag}> con atributos: {dict(parent_orfa.attrib)}")
        print(f"  -> Atributos del campo: {dict(n_orfa.attrib)}")
        nxt_orfa = n_orfa.getnext()
        print(f"  -> Elemento inmediatamente siguiente a ORFA: <{nxt_orfa.tag if nxt_orfa is not None else 'None'} name='{nxt_orfa.get('name') if nxt_orfa is not None else ''}'>")

except Exception as e:
    print(f"[ERROR al compilar vista de sale.order]: {e}")

# ==============================================================================
# 6. TODAS LAS VISTAS DE STUDIO ACTIVAS SOBRE SALE.ORDER
# ==============================================================================
print_separator("6. VISTAS DE STUDIO ACTIVAS EN sale.order")

studio_views = env['ir.ui.view'].search([
    ('model', '=', 'sale.order'),
    ('active', '=', True),
    '|', '|',
    ('name', 'ilike', 'studio'),
    ('xml_id', 'ilike', 'studio'),
    ('key', 'ilike', 'studio')
], order='priority, id')

print(f"Total de vistas Studio activas en sale.order: {len(studio_views)}")
for sv in studio_views:
    print(f"  ID: {sv.id:5d} | Prio: {sv.priority:3d} | Nombre: {sv.name} | XML ID: {sv.xml_id}")

print_separator("AUDITORÍA CONCLUIDA EXITOSAMENTE")
