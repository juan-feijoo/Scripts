# -*- coding: utf-8 -*-
"""
Script de Pruebas Unitarias/Validación para Secuencias Multi-Compañía en Odoo (sale.order).
Soporta Odoo 17.0+e, 18.0+e, 19.0+e.

Prueba para cada compañía activa:
1. Inspección estática: Verifica que exista una secuencia propia y que NO sea compartida.
2. Simulación real (Savepoint / Rollback): Simula la creación de una Orden de Venta en cada empresa
   usando 'with_company(comp)', evalúa el correlativo generado y revierte la transacción para NO quemar números.
"""

print("\n" + "=" * 70)
print(" TEST MULTI-COMPAÑÍA: VERIFICACIÓN DE SECUENCIAS (SALE.ORDER)")
print("=" * 70)

companies = env['res.company'].search([])
test_results = []
partner = env['res.partner'].search([('customer_rank', '>', 0)], limit=1) or env['res.partner'].search([], limit=1)

print(f"\n🔍 Probando en {len(companies)} compañías registradas...")

for comp in companies:
    print(f"\n" + "-" * 70)
    print(f"🏢 COMPAÑÍA: [{comp.id}] {comp.name}")
    print("-" * 70)

    # 1. Búsqueda exacta que hace Odoo internamente al crear una OV
    seq = env['ir.sequence'].with_company(comp).search([
        ('code', '=', 'sale.order'),
        ('company_id', 'in', [comp.id, False])
    ], order='company_id desc', limit=1)

    if not seq:
        print(f"  ❌ ERROR CRÍTICO: No se encontró ninguna secuencia para 'sale.order' en esta compañía.")
        test_results.append((comp.name, False, "Sin secuencia"))
        continue

    # Validar si es propia o compartida
    is_shared = not bool(seq.company_id)
    if is_shared:
        print(f"  ❌ ERROR: Está tomando una secuencia compartida (ID {seq.id}). Debe tener una propia.")
        test_results.append((comp.name, False, "Secuencia Compartida"))
        continue
    elif seq.company_id.id != comp.id:
        print(f"  ❌ ERROR: Está tomando la secuencia de otra compañía (Pertenece a ID {seq.company_id.id}).")
        test_results.append((comp.name, False, "Secuencia de otra compañía"))
        continue

    print(f"  ✔ Secuencia detectada correctamente: ID {seq.id} | Nombre: '{seq.name}'")
    print(f"  ✔ Configuración: Prefijo: '{seq.prefix}' | Padding: {seq.padding} | Próx: {seq.number_next_actual}")

    # 2. Prueba dinámica con SAVEPOINT (Rollback garantizado al 100%)
    # Probamos la creación real de una OV bajo el contexto de esta compañía
    try:
        with env.cr.savepoint():
            # Creamos la OV en memoria en el contexto de la empresa
            so = env['sale.order'].with_company(comp).create({
                'partner_id': partner.id,
                'company_id': comp.id,
            })
            generated_name = so.name
            print(f"  🎯 SIMULACIÓN REAL DE CREACIÓN:")
            print(f"     ➔ Orden de Venta generada: '{generated_name}'")

            # Verificamos que el prefijo coincida
            if seq.prefix and not generated_name.startswith(seq.prefix):
                print(f"     ⚠️ Alerta: El nombre generado no comienza con el prefijo esperado '{seq.prefix}'.")
                test_results.append((comp.name, False, f"Prefijo incorrecto ({generated_name})"))
            else:
                print(f"     ✔ Formato y correlativo validados exitosamente.")
                test_results.append((comp.name, True, f"Generó '{generated_name}'"))

            # Al salir del bloque 'with savepoint', Odoo revierte automáticamente el savepoint si lanzamos una excepción,
            # pero para ser 100% seguros y limpios sin contaminar el log con Tracebacks, forzamos el rollback del savepoint:
            raise UserWarning("ROLLBACK_SIMULACION_EXITOSA")

    except UserWarning as e:
        if str(e) == "ROLLBACK_SIMULACION_EXITOSA":
            pass  # Rollback exitoso esperado
        else:
            raise e
    except Exception as e:
        print(f"  ❌ Excepción durante la simulación: {str(e)}")
        test_results.append((comp.name, False, f"Error: {str(e)}"))

# Resumen Final
print("\n" + "=" * 70)
print(" TABLA RESUMEN DE RESULTADOS DE PRUEBA")
print("=" * 70)
print(f"{'Compañía':<35} | {'Estado':<10} | {'Detalle'}")
print("-" * 70)
for comp_name, status, detail in test_results:
    status_str = "✅ PASS" if status else "❌ FAIL"
    print(f"{comp_name:<35} | {status_str:<10} | {detail}")
print("=" * 70)

# Asegurar que nada quede pendiente en la transacción
env.cr.rollback()
print("\nℹ️ Nota: Todos los números simulados fueron devueltos a la secuencia gracias al rollback.")
print("=" * 70 + "\n")
