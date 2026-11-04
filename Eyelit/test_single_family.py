# -*- coding: utf-8 -*-
"""
Test quirúrgico en 1 sola familia (Template 10623 - 7 productos Slip)
Diagnostica la creación de PTAL, PTAV y re-parenting.
"""
print("=" * 80)
print("[*] TEST QUIRÚRGICO EN FAMILIA 10623 (7 productos)")
print("=" * 80)

cr = env.cr
cr.execute("SAVEPOINT test_single_sp")

Product = env['product.product']
Template = env['product.template']
Attribute = env['product.attribute']
AttrValue = env['product.attribute.value']
PTAL = env['product.template.attribute.line']
PTAV = env['product.template.attribute.value']

# 1. Atributos
attr_talle = Attribute.search([('name', '=ilike', 'Talle')], limit=1)
if not attr_talle:
    attr_talle = Attribute.create({'name': 'Talle', 'display_type': 'pills', 'create_variant': 'always'})
else:
    attr_talle.write({'create_variant': 'always', 'display_type': 'pills'})

attr_color = Attribute.search([('name', '=ilike', 'Color')], limit=1)
if not attr_color:
    attr_color = Attribute.create({'name': 'Color', 'display_type': 'select', 'create_variant': 'always'})
else:
    attr_color.write({'create_variant': 'always', 'display_type': 'select'})

print(f"Atributo Talle: ID {attr_talle.id}, create_variant={attr_talle.create_variant}")
print(f"Atributo Color: ID {attr_color.id}, create_variant={attr_color.create_variant}")

# 2. Productos de la muestra
prod_ids = [10612, 10613, 7659, 10694, 10869, 8969, 8970]
prods = Product.browse(prod_ids)
master_tmpl = prods[0].product_tmpl_id
master_tmpl_id = master_tmpl.id
print(f"Master Template: ID {master_tmpl_id} - Nombre: '{master_tmpl.name}'")

# 3. Crear valores
talles = ['2', '3', '4', '5', '6', '7/8', '9/10']
talle_vals = []
for t in talles:
    val = AttrValue.search([('attribute_id', '=', attr_talle.id), ('name', '=', t)], limit=1)
    if not val:
        val = AttrValue.create({'attribute_id': attr_talle.id, 'name': t})
    talle_vals.append(val.id)

color_vals = []
val_c = AttrValue.search([('attribute_id', '=', attr_color.id), ('name', '=', '90')], limit=1)
if not val_c:
    val_c = AttrValue.create({'attribute_id': attr_color.id, 'name': '90'})
color_vals.append(val_c.id)

print(f"Valores Talle IDs: {talle_vals}")
print(f"Valores Color IDs: {color_vals}")

# 4. Crear PTAL
ptal_talle = PTAL.search([('product_tmpl_id', '=', master_tmpl_id), ('attribute_id', '=', attr_talle.id)], limit=1)
if not ptal_talle:
    ptal_talle = PTAL.create({
        'product_tmpl_id': master_tmpl_id,
        'attribute_id': attr_talle.id,
        'value_ids': [(6, 0, talle_vals)]
    })
else:
    ptal_talle.write({'value_ids': [(6, 0, talle_vals)]})

ptal_color = PTAL.search([('product_tmpl_id', '=', master_tmpl_id), ('attribute_id', '=', attr_color.id)], limit=1)
if not ptal_color:
    ptal_color = PTAL.create({
        'product_tmpl_id': master_tmpl_id,
        'attribute_id': attr_color.id,
        'value_ids': [(6, 0, color_vals)]
    })
else:
    ptal_color.write({'value_ids': [(6, 0, color_vals)]})

# Asegurar sincronización de PTAVs
if hasattr(ptal_talle, '_update_product_template_attribute_values'):
    ptal_talle._update_product_template_attribute_values()
if hasattr(ptal_color, '_update_product_template_attribute_values'):
    ptal_color._update_product_template_attribute_values()

env.flush_all()

# 5. Inspeccionar PTAVs generados
ptavs_line_talle = ptal_talle.product_template_value_ids
ptavs_line_color = ptal_color.product_template_value_ids
print(f"PTAVs generados para Talle ({len(ptavs_line_talle)}): {[(p.id, p.product_attribute_value_id.name) for p in ptavs_line_talle]}")
print(f"PTAVs generados para Color ({len(ptavs_line_color)}): {[(p.id, p.product_attribute_value_id.name) for p in ptavs_line_color]}")

# PTAVs vía búsqueda
ptavs_search = PTAV.search([('product_tmpl_id', '=', master_tmpl_id)])
print(f"PTAVs encontrados vía PTAV.search ({len(ptavs_search)}): {[(p.id, p.product_attribute_value_id.name) for p in ptavs_search]}")

cr.execute("ROLLBACK TO SAVEPOINT test_single_sp")
print("\n[*] ROLLBACK ejecutado con éxito.")
