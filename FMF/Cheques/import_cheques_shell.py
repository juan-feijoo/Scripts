# Script de Importación de Cheques Diferidos (Soporte Multi-Empresa y Auto-Creación)
# Para ejecutar en la Odoo Shell:
# odoo-bin shell -d tu_base_de_datos
# exec(open('import_cheques_shell.py').read())

import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN
# ==========================================
DRY_RUN = False  # Cambiar a False para impactar en la BD
RUTA_ARCHIVO = '/tmp/Cheque de pago diferido FMF Mining.xlsx' # Ruta en Odoo.sh

MAPEO_DIARIOS = {
    'Macro': 129,
}

MAPEO_PROVEEDORES = {
    'Industrias Marcelini S.A': 12969,
    'FyL Trans S.R.L': 	16092,          
}

def importar_cheques(env):
    print("="*60)
    print(f" INICIANDO IMPORTACIÓN DE CHEQUES (DRY_RUN={DRY_RUN}) ")
    print("="*60)
    
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: La librería 'pandas' no está instalada en el entorno de Odoo.")
        return

    try:
        df = pd.read_excel(RUTA_ARCHIVO, skiprows=6)
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return
    
    df = df.dropna(subset=['Numero de cheque'])
    
    Payment = env['account.payment']
    Partner = env['res.partner']
    Journal = env['account.journal']
    
    errores = 0
    creados = 0
    
    # Caché en memoria para no duplicar proveedores creados en la misma pasada
    proveedores_cache = {}
    
    for index, row in df.iterrows():
        nro_cheque = str(row['Numero de cheque']).split('.')[0].strip()
        
        if not nro_cheque.isdigit():
            print(f"\n--- Ignorando fila de Totales o texto inválido: {nro_cheque} ---")
            continue
            
        fecha_pago = row['Fecha de Pago']
        proveedor_nombre = str(row['Proveedor']).strip()
        banco_excel = str(row['Banco']).strip()
        importe = float(row['Importe'])
        fecha_emision = row['Fecha de emision']
        pedido_por = str(row['Pedido por']).strip() if pd.notna(row['Pedido por']) else ''
        observacion = str(row['Observación']).strip() if pd.notna(row['Observación']) else ''
        
        print(f"\n--- Procesando Fila {index}: Cheque {nro_cheque} ---")
        
        # 1. Obtener Diario
        journal_id = MAPEO_DIARIOS.get(banco_excel)
        if not journal_id:
            print(f" [ERROR] No hay mapeo configurado para el banco: '{banco_excel}'")
            errores += 1
            continue
            
        journal = Journal.browse(journal_id)
        if not journal.exists():
            print(f" [ERROR] El Diario con ID {journal_id} no existe.")
            errores += 1
            continue
            
        empresa_id = journal.company_id.id
        if not empresa_id:
            print(f" [ERROR] El Diario {journal.name} no tiene una compañía asignada.")
            errores += 1
            continue

        # 2. Buscar Proveedor
        partner = False
        
        # Revisamos si lo acabamos de crear en este mismo script
        if proveedor_nombre in proveedores_cache:
            partner = proveedores_cache[proveedor_nombre]
        else:
            partner_id_mapeado = MAPEO_PROVEEDORES.get(proveedor_nombre, 0)
            if partner_id_mapeado:
                partner = Partner.browse(partner_id_mapeado)
            else:
                nombre_limpio = proveedor_nombre.replace('.', '').replace(' ', '%')
                partner = Partner.with_company(empresa_id).search([
                    ('name', 'ilike', nombre_limpio),
                    ('supplier_rank', '>', 0),
                    '|', ('company_id', '=', False), ('company_id', '=', empresa_id)
                ], limit=1)
                
                if not partner:
                    partner = Partner.with_company(empresa_id).search([
                        ('name', 'ilike', nombre_limpio),
                        '|', ('company_id', '=', False), ('company_id', '=', empresa_id)
                    ], limit=1)
                    
        # Auto-Creación
        if not partner:
            if DRY_RUN:
                print(f" [DRY-RUN] Se auto-crearía el proveedor: '{proveedor_nombre}'. Saltando cheque.")
                continue 
            else:
                print(f" -> Creando proveedor faltante: '{proveedor_nombre}'")
                try:
                    partner = Partner.with_company(empresa_id).create({
                        'name': proveedor_nombre,
                        'company_id': False,
                        'supplier_rank': 1,
                        'is_company': True,
                    })
                    print(f"    [EXITO] Proveedor creado con ID {partner.id}")
                    # Lo guardamos en memoria para que en la próxima fila no lo vuelva a crear
                    proveedores_cache[proveedor_nombre] = partner
                except Exception as e:
                    print(f" [ERROR] No se pudo crear el proveedor: {e}")
                    errores += 1
                    continue
            
        print(f" -> Proveedor localizado: {partner.name if partner else proveedor_nombre} (ID: {partner.id if partner else 'N/A'})")
            
        # 3. Buscar método de pago
        payment_method_line = journal.outbound_payment_method_line_ids.filtered(lambda m: m.code == 'check_printing')
        if not payment_method_line:
            payment_method_line = journal.outbound_payment_method_line_ids.filtered(lambda m: m.code == 'manual')
            if not payment_method_line:
                print(f" [ERROR] El Diario {journal.name} no tiene métodos de pago salientes configurados.")
                errores += 1
                continue
        
        # 4. Preparar Valores del Pago
        ref_text = observacion
        if pedido_por and pedido_por != 'nan':
            ref_text += f" (Pedido por: {pedido_por})"
            
        vals = {
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': partner.id if partner else False,
            'amount': importe,
            'journal_id': journal.id,
            'company_id': empresa_id,
            'payment_method_line_id': payment_method_line[0].id,
            'date': fecha_emision.date() if isinstance(fecha_emision, datetime) else fecha_emision,
            'l10n_latam_check_payment_date': fecha_pago.date() if isinstance(fecha_pago, datetime) else fecha_pago,
            'check_number': nro_cheque,
            'ref': ref_text,
        }
        
        if DRY_RUN:
            print(f" [DRY-RUN] Se crearía pago: Importe={importe}, Cheque={nro_cheque}")
        else:
            try:
                nuevo_pago = Payment.with_company(empresa_id).create(vals)
                print(f" [EXITO] Pago creado con ID {nuevo_pago.id}")
                
                if pedido_por and pedido_por != 'nan':
                    nuevo_pago.message_post(body=f"Cheque pedido por: {pedido_por}")
                    
                creados += 1
            except Exception as e:
                print(f" [ERROR] Falló la creación en Odoo: {e}")
                errores += 1

    print("\n" + "="*60)
    print(f" RESUMEN: {creados} Creados | {errores} Errores ")
    print("="*60)
    
    if DRY_RUN:
        print("\n NOTA: Ejecución en modo DRY_RUN. No se guardó nada en base de datos.")
    else:
        # ======= EL TRUCO MAGICO DE LA SHELL =======
        env.cr.commit()
        print("\n [INFO] ¡COMMIT REALIZADO! Los cambios ya están en la Base de Datos.")

# Ejecutar la función
# importar_cheques(env)
