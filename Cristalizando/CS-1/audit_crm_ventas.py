# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE AUDITORÍA: ERROR DE VISTAS Y CAMPOS CRM -> VENTAS (Odoo 17 / 18 / 19)
================================================================================
Uso en Odoo.sh / Terminal:
    python3 odoo-bin shell -d <nombre_bd> --command="exec(open('audit_crm_ventas.py').read())"
o simplemente copiar y pegar el contenido en la shell interactiva de Odoo (`odoo-bin shell`).

Modo: LECTURA / AUDITORÍA (100% seguro, sin modificaciones en la base de datos).
================================================================================
"""

import logging
from lxml import etree

_logger = logging.getLogger("odoo.audit")

print("=" * 80)
print("INICIANDO AUDITORÍA TÉCNICA: VISTAS Y CAMPOS (CRM -> VENTAS)")
print("=" * 80)

# ----------------------------------------------------------------------
# 1. AUDITORÍA DE LA VISTA QUE CAUSA EL ERROR EN STUDIO
# ----------------------------------------------------------------------
print("\n" + "=" * 50)
print("1. LOCALIZANDO LA VISTA CONFLICTIVA (ir.ui.view)")
print("=" * 50)

# Buscamos en ir.ui.view cualquier vista que contenga el campo o xpath conflictivo
search_terms = ['material_reservation_ids', 'obra_padre_id', 'NV Numero de ORFA']

views_conflictivas = env['ir.ui.view'].search([
    ('arch_db', 'ilike', 'material_reservation_ids')
])

print(f"Total de vistas que mencionan 'material_reservation_ids': {len(views_conflictivas)}")

for view in views_conflictivas:
    is_studio = 'studio' in (view.xml_id or '').lower() or 'studio' in (view.name or '').lower() or 'Odoo Studio' in (view.name or '')
    print("-" * 50)
    print(f"ID: {view.id}")
    print(f"Nombre: {view.name}")
    print(f"XML ID: {view.xml_id or 'Sin XML ID (Creada por UI/Studio)'}")
    print(f"Modelo: {view.model}")
    print(f"Activa: {view.active}")
    print(f"Es de Studio?: {'SÍ' if is_studio else 'NO'}")
    print(f"Vista Padre (inherit_id): {view.inherit_id.id} - {view.inherit_id.name} ({view.inherit_id.xml_id})")
    
    # Inspeccionar si tiene el xpath del error
    arch_str = view.arch_db or ""
    if 'product_id' in arch_str and 'material_reservation_ids' in arch_str:
        print("  >>> [ALERTA] Esta vista contiene la combinación 'material_reservation_ids' + 'product_id' <<<")
    if 'page[not(@name)]' in arch_str:
        print("  >>> [ALERTA CRÍTICA] Contiene el selector frágil 'page[not(@name)]' <<<")
        
    print("\nFragmento del XML (Arch):")
    for line in arch_str.splitlines():
        if any(term in line for term in ['material_reservation_ids', 'product_id', 'xpath', 'page']):
            print(f"    {line.strip()}")

# ----------------------------------------------------------------------
# 2. INSPECCIÓN DE LA VISTA FORMULARIO BASE DE SALE.ORDER
# ----------------------------------------------------------------------
print("\n" + "=" * 50)
print("2. REVISANDO ESTRUCTURA DE PÁGINAS (NOTEBOOK) EN sale.order")
print("=" * 50)

try:
    sale_order_form = env.ref('sale.view_order_form', raise_if_not_found=False)
    if not sale_order_form:
        sale_order_form = env['ir.ui.view'].search([('model', '=', 'sale.order'), ('type', '=', 'form')], limit=1)
    
    print(f"Vista Base Formulario Sale Order: ID {sale_order_form.id} - {sale_order_form.name}")
    
    # Obtenemos la vista combinada / renderizada
    try:
        combined_arch = env['sale.order'].get_view(view_id=sale_order_form.id, view_type='form')['arch']
        doc = etree.fromstring(combined_arch.encode('utf-8'))
        
        pages = doc.xpath('//notebook/page')
        print(f"\nTotal de pestañas (page) encontradas en el formulario combinado: {len(pages)}")
        for idx, page in enumerate(pages, start=1):
            name_attr = page.get('name')
            string_attr = page.get('string')
            has_no_name = name_attr is None
            print(f"  Pestaña #{idx}: string='{string_attr}', name='{name_attr}' {'[SIN ATRIBUTO NAME!]' if has_no_name else ''}")
            
            # Revisar si dentro de esta pestaña está material_reservation_ids
            m_res = page.xpath('.//field[@name="material_reservation_ids"]')
            if m_res:
                print(f"    -> [ENCONTRADO] material_reservation_ids está en esta pestaña!")
                # Verificar si usa tree o list
                inner_trees = m_res[0].xpath('.//tree')
                inner_lists = m_res[0].xpath('.//list')
                print(f"    -> Elementos hijos: tree={len(inner_trees)}, list={len(inner_lists)}")
                if inner_lists and not inner_trees:
                    print("    -> [NOTA Odoo 18] La vista interna usa <list>, por lo que un xpath a /tree[1] FALLARÁ.")
                    
    except Exception as e:
        print(f"Error al combinar la vista de sale.order: {e}")
        
except Exception as e:
    print(f"Error inspeccionando sale_order_form: {e}")

# ----------------------------------------------------------------------
# 3. AUDITORÍA DEL CAMPO CRM (obra_padre_id)
# ----------------------------------------------------------------------
print("\n" + "=" * 50)
print("3. AUDITORÍA DEL CAMPO obra_padre_id EN crm.lead")
print("=" * 50)

crm_fields = env['ir.model.fields'].search([
    ('model', '=', 'crm.lead'),
    ('name', 'in', ['obra_padre_id', 'x_studio_obra_padre_id'])
])

if not crm_fields:
    # Buscar aproximado
    crm_fields = env['ir.model.fields'].search([
        ('model', '=', 'crm.lead'),
        ('name', 'ilike', 'obra_padre')
    ])

for f in crm_fields:
    print(f"Nombre técnico: {f.name}")
    print(f"Etiqueta: {f.field_description}")
    print(f"Tipo: {f.ttype}")
    print(f"Modelo Relacionado (comodel): {f.relation}")
    print(f"Dominio: {f.domain}")
    print(f"Solo Lectura: {f.readonly}")
    print(f"Requerido: {f.required}")
    print(f"Almacenado (stored): {f.store}")
    print(f"Relacionado (related): {f.related or 'No es related'}")
    print(f"Módulos origen: {f.modules}")

# ----------------------------------------------------------------------
# 4. AUDITORÍA DE CAMPOS EN sale.order ("Numero de ORFA" y destino)
# ----------------------------------------------------------------------
print("\n" + "=" * 50)
print("4. AUDITORÍA DE CAMPOS EN sale.order (ORFA y obra_padre_id)")
print("=" * 50)

orfa_fields = env['ir.model.fields'].search([
    ('model', '=', 'sale.order'),
    '|', ('name', 'ilike', 'orfa'), ('field_description', 'ilike', 'orfa')
])

print(f"Campos relacionados con 'ORFA' en sale.order encontrados: {len(orfa_fields)}")
for f in orfa_fields:
    print(f"  - Técnico: '{f.name}' | Etiqueta: '{f.field_description}' | Tipo: {f.ttype}")

# Revisar si ya existe obra_padre_id en sale.order
sale_obra_fields = env['ir.model.fields'].search([
    ('model', '=', 'sale.order'),
    ('name', 'ilike', 'obra_padre')
])
print(f"\nCampos relacionados con 'obra_padre' en sale.order: {len(sale_obra_fields)}")
for f in sale_obra_fields:
    print(f"  - Técnico: '{f.name}' | Etiqueta: '{f.field_description}' | Tipo: {f.ttype} | Related: {f.related}")

# Verificar relación oportunidad en sale.order
opp_field = env['ir.model.fields'].search([
    ('model', '=', 'sale.order'),
    ('name', '=', 'opportunity_id')
], limit=1)
if opp_field:
    print(f"\nCampo 'opportunity_id' verificado en sale.order: ID {opp_field.id} (Relación: {opp_field.relation})")

print("\n" + "=" * 80)
print("AUDITORÍA FINALIZADA.")
print("=" * 80)
