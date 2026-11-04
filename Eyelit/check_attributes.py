# -*- coding: utf-8 -*-
"""
Script de Verificación de Atributos Existentes y Mapeo de Colores (Odoo 18.0+)
Revisa si ya existen atributos (Talle, Color) en la base y si hay tablas de equivalencias.
"""
print("=" * 80)
print("[*] INSPECCIÓN DE ATRIBUTOS EXISTENTES EN LA BASE")
print("=" * 80)

# 1. Atributos existentes
attributes = env['product.attribute'].search([])
print(f"Atributos encontrados: {len(attributes)}")
for attr in attributes:
    values = attr.value_ids.mapped('name')
    print(f"  - Atributo: '{attr.name}' (display_type: {attr.display_type}, create_variant: {attr.create_variant})")
    print(f"    Valores ({len(values)}): {values[:10]} {'...' if len(values) > 10 else ''}")

# 2. Revisar si hay campos personalizados en product.template o product.product
print(f"\nCampos sospechosos de Color/Talle en product.product:")
custom_fields = [f for f in env['product.product']._fields.keys() if any(k in f.lower() for k in ['color', 'talle', 'size', 'art', 'sub'])]
print(f"  Campos: {custom_fields}")

# 3. Analizar los últimos 2 caracteres del prefijo (posible código de color)
from collections import Counter
Product = env['product.product']
prods = Product.search_read([('default_code', '!=', False)], ['default_code'])
colors_counter = Counter()

for p in prods:
    code = p['default_code'].strip()
    if '.' in code:
        prefix, _ = code.rsplit('.', 1)
        if len(prefix) == 9:
            color_code = prefix[7:9]
            colors_counter[color_code] += 1

print(f"\nTop 20 Códigos de Color detectados en prefijos de 9 caracteres (posiciones 8-9):")
for col, cnt in colors_counter.most_common(20):
    print(f"  - Color Code: '{col}' -> {cnt} productos")

print("=" * 80)
