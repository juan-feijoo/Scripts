# -*- coding: utf-8 -*-
"""
================================================================================
05 - HABILITACIÓN DE MÉTODO DE COSTO PROMEDIO (AVCO) EN CATEGORÍAS DE PRODUCTOS
================================================================================
Analiza y actualiza las categorías de productos a Costo Promedio (AVCO)
(property_cost_method = 'average') para que el costo unitario se actualice
automáticamente cada vez que entra mercadería con una compra/recepción.
"""
import os

h('05 - HABILITACIÓN DE MÉTODO DE COSTO PROMEDIO (AVCO) EN CATEGORÍAS')

# -------------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------------
env_dry_run = os.environ.get('DRY_RUN', '1').lower()
DRY_RUN = env_dry_run not in ('0', 'false', 'no')

mode_str = 'DRY-RUN (Simulación sin persistir)' if DRY_RUN else 'PRODUCCIÓN (PERSISTENTE / COMMIT)'
sub('Modo de Ejecución: %s' % mode_str)

# -------------------------------------------------------------------------
# 1. RELEVAMIENTO DE CATEGORÍAS ACTUALES
# -------------------------------------------------------------------------
sub('1. Relevamiento Actual de Categorías')
Category = env['product.category']
all_cats = Category.search([])

por_metodo = {}
por_valuacion = {}

for c in all_cats:
    m = c.property_cost_method or 'sin_definir'
    v = c.property_valuation or 'sin_definir'
    por_metodo.setdefault(m, []).append(c)
    por_valuacion.setdefault(v, []).append(c)

print('Total categorías en Odoo: %d' % len(all_cats))
print('\nMétodos de Costo actuales:')
for m, lista in por_metodo.items():
    print('  - %-15s : %d categorías' % (m, len(lista)))

print('\nMétodos de Valuación actuales:')
for v, lista in por_valuacion.items():
    print('  - %-15s : %d categorías' % (v, len(lista)))

# -------------------------------------------------------------------------
# 2. INSPECCIÓN DE CUENTAS CONTABLES EN CATEGORÍAS PADRE
# -------------------------------------------------------------------------
sub('2. Cuentas Contables en Categorías Principales')
padres = Category.search([('parent_id', '=', False)])
print('Categorías Raíz encontradas (%d):' % len(padres))

for p in padres:
    cta_inv = getattr(p, 'property_stock_valuation_account_id', None)
    cta_var = getattr(p, 'property_stock_variation_account_id', None)
    cta_ing = getattr(p, 'property_account_income_categ_id', None)
    cta_gas = getattr(p, 'property_account_expense_categ_id', None)
    print('  [%s] %s' % (p.id, p.name))
    print('      Ingresos   : %s' % (cta_ing.display_name if cta_ing else '<Hereda/Vacío>'))
    print('      Gastos     : %s' % (cta_gas.display_name if cta_gas else '<Hereda/Vacío>'))
    print('      Inventario : %s' % (cta_inv.display_name if cta_inv else '<Hereda/Vacío>'))
    print('      Variación  : %s' % (cta_var.display_name if cta_var else '<Hereda/Vacío>'))

# -------------------------------------------------------------------------
# 3. ACTUALIZACIÓN A COSTO PROMEDIO (AVCO)
# -------------------------------------------------------------------------
sub('3. Actualización de Categorías a Costo Promedio (AVCO)')

actualizadas = 0
ya_en_avco = 0
errores = 0

for c in all_cats:
    if c.property_cost_method != 'average':
        try:
            c.write({'property_cost_method': 'average'})
            actualizadas += 1
            if actualizadas <= 10 or actualizadas % 100 == 0:
                print('  [AVCO] %s' % c.complete_name)
        except Exception as e:
            print('  [!] Error en categoría %s: %s' % (c.complete_name, e))
            errores += 1
    else:
        ya_en_avco += 1

sub('4. Resumen de Categorías')
print('  Total categorías procesadas   : %d' % len(all_cats))
print('  Categorías pasadas a AVCO     : %d' % actualizadas)
print('  Categorías que ya eran AVCO   : %d' % ya_en_avco)
print('  Errores                       : %d' % errores)

# -------------------------------------------------------------------------
# 4. CONTROL TRANSACCIONAL
# -------------------------------------------------------------------------
sub('5. Control Transaccional')
if DRY_RUN:
    env.cr.rollback()
    print('\n[SIMULACIÓN COMPLETADA] Rollback ejecutado. No se modificó la configuración.')
    print('Para aplicar los cambios en la base de datos, ejecutar con DRY_RUN=0.')
else:
    env.cr.commit()
    print('\n[PRODUCCIÓN / PERSISTIDO] Commit ejecutado exitosamente. Todas las categorías en AVCO.')
