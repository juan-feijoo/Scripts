# -*- coding: utf-8 -*-
"""
Script de Análisis Profundo de Patrones Eyelit (Odoo 18.0+)
Analiza la estructura de default_code / barcode:
  Ejemplos: 0414E0AWA.3XL, 0525P0A01.M00, 1311P0A01.002, 0038S3X90.004
Objetivo:
  1. Identificar componentes: [Artículo][Línea/Color].[Talle]
  2. Detectar todos los Talles únicos y mapear su normalización (M00 -> M, 002 -> 2)
  3. Detectar Códigos de Color únicos
  4. Identificar excepciones (productos sin punto, sin código, etc.)
"""
import re
from collections import Counter, defaultdict

Product = env['product.product']

print("=" * 80)
print("[*] ANALIZANDO ESTRUCTURA DE CODIGOS EYELIT (11,687 productos)")
print("=" * 80)

prods = Product.search_read(
    [('active', 'in', [True, False])],
    ['id', 'name', 'default_code', 'barcode', 'active']
)

total = len(prods)
with_dot = 0
without_dot = []
suffixes = Counter()
prefixes = Counter()
articles = Counter()

# Mapeo sugerido de normalización de talles detectados
TALLE_NORMALIZATION = {
    'XS0': 'XS', 'S00': 'S', 'M00': 'M', 'L00': 'L', 'XL0': 'XL', 'XXL': 'XXL',
    '3XL': '3XL', '4XL': '4XL', '5XL': '5XL',
    '001': '1', '002': '2', '003': '3', '004': '4', '005': '5', '006': '6',
    '008': '8', '010': '10', '012': '12', '014': '14', '016': '16',
    '7/8': '7/8', '9/1': '9/10', '11/': '11/12', '13/': '13/14'
}

prefix_pattern_examples = defaultdict(list)

for p in prods:
    code = (p.get('default_code') or '').strip()
    if not code:
        code = (p.get('barcode') or '').strip()
    
    if not code:
        without_dot.append((p['id'], p['name'], 'SIN_CODIGO'))
        continue

    if '.' in code:
        with_dot += 1
        prefix, suffix = code.rsplit('.', 1)
        suffixes[suffix] += 1
        
        # Analizar prefijo (ej: 0414E0AWA -> Art 0414, Subcódigo E0AWA)
        # Típicamente los primeros 4 caracteres son el número de Artículo
        art = prefix[:4] if len(prefix) >= 4 else prefix
        color_sub = prefix[4:] if len(prefix) > 4 else ''
        articles[art] += 1
        prefix_pattern_examples[len(prefix)].append((code, p['name'], art, color_sub, suffix))
    else:
        without_dot.append((p['id'], p['name'], code))

print(f"\n[1] RESULTADOS GENERALES DE CODIFICACIÓN:")
print(f"  - Total productos analizados: {total}")
print(f"  - Productos con estructura con punto '.' : {with_dot} ({with_dot*100/total:.1f}%)")
print(f"  - Productos sin punto o sin código : {len(without_dot)}")

print(f"\n[2] TOP 30 TALLES (Sufijos después del punto):")
for suffix, count in suffixes.most_common(30):
    norm = TALLE_NORMALIZATION.get(suffix, f"? ({suffix})")
    print(f"  - Sufijo '{suffix:<5}' -> Talle Normalizado: '{norm:<6}' | Cantidad: {count}")

print(f"\n[3] ESTRUCTURA DEL PREFIJO (Antes del punto):")
for length, samples in prefix_pattern_examples.items():
    print(f"\n  Longitud prefijo = {length} caracteres (Total encontrados: {len(samples)}):")
    for sample in samples[:3]:
        print(f"    Código: {sample[0]:<16} | Art: '{sample[2]}' | Color/Línea: '{sample[3]}' | Talle: '{sample[4]}' | Nombre: {sample[1]}")

if without_dot:
    print(f"\n[4] MUESTRA DE EXCEPCIONES (Productos sin punto o sin código - Top 10):")
    for item in without_dot[:10]:
        print(f"  ID: {item[0]:<6} | Código: {item[2]:<16} | Nombre: {item[1]}")

print("\n" + "=" * 80)
print("[*] FIN DEL ANÁLISIS DE PATRONES")
print("=" * 80)
