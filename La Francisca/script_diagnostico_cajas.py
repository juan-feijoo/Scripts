# ==============================================================================
# PARCHE DE PRODUCCIÓN: CORRECCIÓN DE CAJAS EN FACTURACIÓN (TELY)
# ==============================================================================
print("\n--- APLICANDO PARCHE DE CAJAS EN PRODUCCIÓN ---")

# Buscamos la acción automatizada original defectuosa de account.move
fantasma_move = env['ir.actions.server'].search([
    ('model_id.model', '=', 'account.move'), 
    ('name', '=', 'Ejecutar código'),
    ('code', 'ilike', 'x_studio_cajas')
], limit=1)

if fantasma_move:
    # Nuevo código corregido
    nuevo_codigo = """
if record:
    if record.invoice_origin:
        # Buscar la orden de venta
        sale_order = env['sale.order'].search([('name', '=', record.invoice_origin)], limit=1)
        if sale_order:
            # Conservar funcionalidad original de Tely
            record['x_studio_remito_electronico'] = sale_order.x_studio_remito_electronico
            record['x_studio_remito_de_entrega'] = sale_order.x_studio_remito_de_entrega
            record['x_studio_domicilio_fiscal'] = sale_order.x_studio_domicilio_fiscal

            # CÁLCULO PROPORCIONAL DE CAJAS DE INVENTARIO
            for line in record.invoice_line_ids:
                if line.product_id and line.sale_line_ids:
                    sol = line.sale_line_ids[0]
                    
                    # 1. Sumamos totales reales despachados (Remitos en estado 'done')
                    cant_entregada = sum(move.quantity for move in sol.move_ids if move.state == 'done')
                    cajas_entregadas = sum(move.x_studio_cajas for move in sol.move_ids if move.state == 'done')
                    
                    if cant_entregada > 0 and cajas_entregadas > 0:
                        # 2. Calculamos proporción según lo que se está facturando
                        proporcion = line.quantity / cant_entregada
                        line['x_studio_cajas'] = int(round(cajas_entregadas * proporcion))
                    else:
                        # Fallback al pedido de venta original (por si no requiere remito)
                        if sol.product_uom_qty > 0 and sol.x_studio_cajas > 0:
                            proporcion = line.quantity / sol.product_uom_qty
                            line['x_studio_cajas'] = int(round(sol.x_studio_cajas * proporcion))
                        else:
                            line['x_studio_cajas'] = 0
"""
    # Aplicar el parche y guardar
    fantasma_move.write({'code': nuevo_codigo.strip()})
    env.cr.commit()
    print("✅ Parche aplicado con éxito. La Acción de Servidor ha sido corregida.")
else:
    print("⚠️ No se encontró la Acción de Servidor. Verifica que el nombre sea 'Ejecutar código'.")
