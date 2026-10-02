# Script de auditoría para secuencias de Órdenes de Venta (sale.order)
# Ejecutar en Odoo Shell: odoo-bin shell -c <tu_config> -d <tu_base_de_datos>

print("\n" + "="*50)
print(" INICIANDO AUDITORÍA DE SECUENCIAS DE VENTAS")
print("="*50 + "\n")

# 1. Obtener todas las compañías activas
companies = env['res.company'].search([])
print(f"📍 Compañías Activas en la BD ({len(companies)}):")
for comp in companies:
    print(f"  - ID: {comp.id} | Nombre: {comp.name}")

# 2. Obtener todas las secuencias para 'sale.order'
sequences = env['ir.sequence'].search([('code', '=', 'sale.order')])
print(f"\n📍 Secuencias encontradas para 'sale.order' ({len(sequences)}):")
for seq in sequences:
    company_name = seq.company_id.name if seq.company_id else 'COMPARTIDA (Sin Compañía Asignada)'
    print(f"  - ID: {seq.id} | Nombre: {seq.name} | Prefijo: {seq.prefix} | Próx. Número: {seq.number_next_actual} | Compañía: {company_name}")

# 3. Analizar el uso de secuencias en las últimas 15 Órdenes de Venta
print("\n📍 Análisis de las últimas 15 Órdenes de Venta (Ordenadas por creación):")
sales = env['sale.order'].search([], order='create_date desc', limit=15)
for sale in sales:
    # Mostramos la OV, la compañía y la fecha para evidenciar el salto numérico entre compañías
    print(f"  - Creada: {sale.create_date.strftime('%Y-%m-%d %H:%M:%S')} | OV: {sale.name} | Compañía: {sale.company_id.name} | Estado: {sale.state}")

# 4. Diagnóstico Automatizado (DRY-RUN / Solo lectura)
print("\n" + "="*50)
print(" RESULTADO DEL DIAGNÓSTICO (DRY-RUN)")
print("="*50)

shared_sequences = sequences.filtered(lambda s: not s.company_id)
if shared_sequences:
    print("\n🚨 PROBLEMA DETECTADO: Tienes secuencias sin una compañía asignada (Compartidas).")
    print("   Odoo utiliza esta secuencia como 'comodín' para cualquier compañía que no tenga una secuencia propia.")
    print("   Esto es lo que causa que Eco Norte y GreenTeck compartan la numeración (ej. S01006 y S01007).")

if len(sequences) < len(companies):
    print(f"\n⚠️ ADVERTENCIA: Hay menos secuencias ({len(sequences)}) que compañías ({len(companies)}).")
    print("   Debes tener exactamente una secuencia de 'sale.order' por cada compañía para evitar cruces.")

print("\n✅ ACCIONES RECOMENDADAS:")
print("   1. Crear una secuencia independiente para cada compañía desde Técnico -> Secuencias y asignarle la Compañía correspondiente.")
print("   2. Asegurarse de que ninguna secuencia activa para 'sale.order' tenga el campo 'Compañía' vacío.")

print("\n" + "="*50)
print(" FIN DE LA AUDITORÍA")
print("="*50 + "\n")
