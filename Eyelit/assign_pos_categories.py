# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT: ASIGNACIÓN INTELIGENTE DE CATEGORÍAS DE PUNTO DE VENTA (TPV / POS)
================================================================================
Problema resuelto:
    El TPV 'Caja Registradora' tiene activado limit_categories=True.
    Como los productos nuevos tenían 'pos_categ_ids' vacío, el TPV los filtraba al 100%.

Este script:
    1. Clasifica cada plantilla activa en su categoría de TPV correspondiente según su nombre:
       - Boxers -> 'Boxers' (ID 8)
       - Slips -> 'Slips' (ID 9)
       - Femenina (Soutien, Bombacha, Vedetina, etc.) -> 'Femenina' (ID 10)
       - Camisetas / Remeras / Musculosas -> 'Camisetas y Remeras' (ID 4)
       - Medias -> 'Medias' (ID 5)
       - Pantalones / Shorts -> 'Pantalones' (ID 6)
       - Pijamas -> 'Pijamas' (ID 7)
       - Todo lo demás -> 'Others' (ID 3)
    2. Asegura que el TPV 'Caja Registradora' tenga habilitadas todas estas categorías.
    3. Limpia repeticiones en los nombres tipo '(P0A) (P0A)'.
    4. Confirma los cambios con COMMIT.
"""
import re
from collections import Counter

print("=" * 80)
print("[*] ASIGNANDO CATEGORÍAS DE PUNTO DE VENTA A LOS PRODUCTOS")
print("=" * 80)

Template = env['product.template']
PosCategory = env['pos.category']
PosConfig = env['pos.config']

# 1. Obtener IDs de las categorías de TPV existentes
cat_map = {c.name.strip().lower(): c.id for c in PosCategory.search([])}
print(f"Categorías TPV encontradas: {list(cat_map.keys())}")

# Resolver IDs de categorías clave
id_boxers = cat_map.get('boxers')
id_slips = cat_map.get('slips')
id_femenina = cat_map.get('femenina')
id_camisetas = cat_map.get('camisetas y remeras') or cat_map.get('upper body')
id_medias = cat_map.get('medias')
id_pantalones = cat_map.get('pantalones')
id_pijamas = cat_map.get('pijamas')
id_others = cat_map.get('others') or cat_map.get('otros')

def classify_product(name):
    n = (name or '').lower()
    if 'boxer' in n:
        return id_boxers
    elif 'slip' in n:
        return id_slips
    elif any(k in n for k in ['soutien', 'femenin', 'bombacha', 'colaless', 'vedetina', 'culotte', 'tanga']):
        return id_femenina
    elif any(k in n for k in ['remera', 'camiseta', 'musculosa', 'chomba', 'top']):
        return id_camisetas or id_others
    elif any(k in n for k in ['media', 'soquete', 'pantys']):
        return id_medias or id_others
    elif any(k in n for k in ['pantalon', 'short', 'bermuda', 'calzoncillo']):
        return id_pantalones or id_others
    elif any(k in n for k in ['pijama', 'camison']):
        return id_pijamas or id_others
    else:
        return id_others

# 2. Leer todas las plantillas activas de TPV
templates = Template.search([('available_in_pos', '=', True), ('active', '=', True)])
print(f"Total plantillas activas en TPV a categorizar: {len(templates)}")

assigned_counter = Counter()

for tmpl in templates:
    # Limpiar nombre de repeticiones tipo (P0A) (P0A)
    clean_name = tmpl.name or ''
    # Si tiene múltiples (P0A) o similares, normalizar a uno solo
    match = re.search(r'(\([A-Z0-9]+\)\s*)+$', clean_name)
    if match:
        tag = re.findall(r'\([A-Z0-9]+\)', clean_name)[0]
        base = clean_name[:match.start()].strip()
        tmpl.name = f"{base} {tag}"

    cat_id = classify_product(tmpl.name)
    if cat_id:
        tmpl.write({'pos_categ_ids': [(6, 0, [cat_id])]})
        assigned_counter[cat_id] += 1

print("\n[*] RESUMEN DE ASIGNACIÓN POR CATEGORÍA:")
for cat_id, count in assigned_counter.items():
    cat_rec = PosCategory.browse(cat_id)
    print(f"  - Categoría '{cat_rec.name}': {count} productos asignados")

# 3. Configurar 'Caja Registradora' para que incluya todas las categorías válidas
configs = PosConfig.search([])
all_active_cats = list(assigned_counter.keys())
for cfg in configs:
    if hasattr(cfg, 'pos_category_ids'):
        cfg.write({
            'limit_categories': True,
            'pos_category_ids': [(6, 0, all_active_cats)]
        })
        print(f"\n[+] TPV '{cfg.name}' actualizado con todas las categorías activas.")

env.cr.commit()
print("\n" + "=" * 80)
print("[✓] ¡CATEGORÍAS DE TPV ASIGNADAS Y CONFIRMADAS (COMMIT) CON ÉXITO!")
print("    Ahora recarga el TPV en tu navegador con Ctrl + F5.")
print("=" * 80)
