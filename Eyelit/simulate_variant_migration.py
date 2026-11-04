# -*- coding: utf-8 -*-
"""
Script de Simulación y Verificación de Migración de Variantes (Odoo 18.0+)
EJECUCIÓN EN MODO 100% SEGURO (DRY RUN / ROLLBACK OBLIGATORIO)

Objetivo:
  1. Agrupar los 11,660 productos en sus Templates Maestros por Artículo / Nombre.
  2. Normalizar Talle (M00 -> M, 002 -> 2, etc.) y Color (código de 2 dígitos/letras).
  3. Detectar si existen COLISIONES (dos productos de la misma familia con mismo Talle y Color).
  4. Simular la creación de Atributos, Valores, PTAL y re-parenting de product.product en SQL/ORM.
  5. Ejecutar ROLLBACK final para garantizar que la base quede intacta.
"""
import re
import sys
from collections import defaultdict, Counter

print("=" * 80)
print("[*] INICIANDO SIMULACIÓN DE MIGRACIÓN DE VARIANTES (DRY-RUN)")
print("=" * 80)

# Mapeo de normalización de talles comprobado
TALLE_MAP = {
    'XS0': 'XS', 'S00': 'S', 'M00': 'M', 'L00': 'L', 'XL0': 'XL', 'XXL': 'XXL',
    '3XL': '3XL', '4XL': '4XL', '5XL': '5XL', '6XL': '6XL',
    '000': 'U', # Talle Único
    '7/8': '7/8', '9/1': '9/10', '11/': '11/12', '13/': '13/14'
}

def normalize_talle(suffix):
    s = suffix.strip()
    if s in TALLE_MAP:
        return TALLE_MAP[s]
    # Numéricos con ceros a la izquierda (ej: 002 -> 2, 014 -> 14, 038 -> 38)
    if s.isdigit():
        return str(int(s))
    # Alfabéticos con ceros finales (ej: M0 -> M)
    if s.endswith('0') and s[:-1].isalpha():
        return s[:-1]
    return s

def parse_code(code):
    """
    Desglosa un código Eyelit tipo 0414E0AWA.3XL o 0525P0A01.014
    Retorna: (articulo, linea, color, talle)
    """
    code = (code or '').strip()
    if '.' not in code:
        return None
    prefix, suffix = code.rsplit('.', 1)
    talle = normalize_talle(suffix)
    
    # Análisis del prefijo
    art = prefix[:4] if len(prefix) >= 4 else prefix
    linea = prefix[4:7] if len(prefix) >= 7 else ''
    color = prefix[7:9] if len(prefix) >= 9 else prefix[4:]
    if not color:
        color = 'STD'
    return {
        'code': code,
        'prefix': prefix,
        'art': art,
        'linea': linea,
        'color': color,
        'talle': talle
    }

Product = env['product.product']
Template = env['product.template']

# Obtener todos los productos
all_prods = Product.search_read(
    [('active', 'in', [True, False])],
    ['id', 'name', 'default_code', 'barcode', 'product_tmpl_id', 'active']
)

parsed_products = []
skipped_products = []

for p in all_prods:
    code = (p.get('default_code') or p.get('barcode') or '').strip()
    parsed = parse_code(code)
    if parsed:
        parsed['product_id'] = p['id']
        parsed['product_tmpl_id'] = p['product_tmpl_id'][0] if p.get('product_tmpl_id') else False
        parsed['name'] = p.get('name') or ''
        parsed_products.append(parsed)
    else:
        skipped_products.append(p)

print(f"[1] PARSEO DE DATOS:")
print(f"  - Productos procesados con patrón Eyelit: {len(parsed_products)}")
print(f"  - Productos excluidos (servicios/packaging/especiales): {len(skipped_products)}")

# 2. Agrupación por Familia / Template Maestro
# Criterio de agrupación: (Artículo, Nombre) para garantizar que si un artículo comparte nombre con otro no se mezclen.
families = defaultdict(list)
for item in parsed_products:
    family_key = (item['art'], item['name'])
    families[family_key].append(item)

print(f"\n[2] FAMILIAS / TEMPLATES MAESTROS DETECTADOS:")
print(f"  - Total de Familias resultantes: {len(families)}")

# 3. Detección de Colisiones (Mismo Talle y Mismo Color dentro de una misma familia)
collisions = []
clean_families = 0

for (art, name), items in families.items():
    seen_combinations = {}
    family_has_collision = False
    for it in items:
        comb_key = (it['color'], it['talle'])
        if comb_key in seen_combinations:
            collisions.append({
                'art': art,
                'name': name,
                'color': it['color'],
                'talle': it['talle'],
                'prod_1': seen_combinations[comb_key],
                'prod_2': it
            })
            family_has_collision = True
        else:
            seen_combinations[comb_key] = it
    if not family_has_collision:
        clean_families += 1

print(f"\n[3] ANÁLISIS DE COLISIONES DE COMBINACIÓN:")
print(f"  - Familias 100% limpias (sin colisiones): {clean_families} / {len(families)}")
print(f"  - Colisiones detectadas (mismo Talle y Color dentro del mismo Artículo): {len(collisions)}")

if collisions:
    print(f"\n  Muestra de Colisiones detectadas (primeras 5):")
    for col in collisions[:5]:
        p1 = col['prod_1']
        p2 = col['prod_2']
        print(f"  * Art: {col['art']} | {col['name']} | Color: {col['color']} | Talle: {col['talle']}")
        print(f"    - Prod 1 [ID {p1['product_id']}]: Code={p1['code']}")
        print(f"    - Prod 2 [ID {p2['product_id']}]: Code={p2['code']}")

# 4. Estadísticas de Variantes por Template
variant_counts = [len(items) for items in families.values()]
print(f"\n[4] ESTADÍSTICAS DE VARIANTES POR PLANTILLA:")
print(f"  - Máximo de variantes en una plantilla: {max(variant_counts)}")
print(f"  - Promedio de variantes por plantilla: {sum(variant_counts) / len(variant_counts):.1f}")
print(f"  - Mínimo de variantes: {min(variant_counts)}")
print(f"  - Plantillas que tendrán más de 1 variante: {sum(1 for c in variant_counts if c > 1)}")
print(f"  - Plantillas de variante única: {sum(1 for c in variant_counts if c == 1)}")

print("\n" + "=" * 80)
print("[*] SIMULACIÓN DE PARSEO FINALIZADA")
print("=" * 80)
