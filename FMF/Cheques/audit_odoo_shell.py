# Script de Auditoría de Modelos para Cheques Diferidos
# Para ejecutar en la Odoo Shell:
# odoo-bin shell -d tu_base_de_datos --xmlrpc-port=8069 (o cargar mediante exec)
# Dentro de la shell: exec(open('audit_odoo_shell.py').read())

import logging

_logger = logging.getLogger(__name__)

def auditar_entorno_cheques(env):
    print("="*60)
    print(" INICIANDO AUDITORÍA DE ENTORNO PARA CHEQUES PROPIOS ")
    print("="*60)

    # 1. Verificar Módulos Instalados (Localización Argentina u otros de cheques)
    print("\n1. VERIFICANDO MÓDULOS DE LOCALIZACIÓN Y CHEQUES...")
    modulos_clave = ['l10n_ar', 'l10n_latam_check', 'account_check']
    for mod in modulos_clave:
        module = env['ir.module.module'].search([('name', '=', mod)])
        estado = module.state if module else 'No instalado/No encontrado'
        print(f" - Módulo '{mod}': {estado}")

    # 2. Verificar Modelos de Cheques disponibles
    print("\n2. VERIFICANDO MODELOS DISPONIBLES...")
    modelos_posibles = ['account.payment', 'l10n_latam.check', 'account.check']
    modelos_activos = []
    for model_name in modelos_posibles:
        if model_name in env.registry:
            print(f" - [OK] Modelo '{model_name}' está disponible en el entorno.")
            modelos_activos.append(model_name)
        else:
            print(f" - [  ] Modelo '{model_name}' NO está disponible.")

    # 3. Inspeccionar Campos Relevantes en account.payment (u otros si aplican)
    print("\n3. INSPECCIONANDO CAMPOS EN MODELO PRINCIPAL (account.payment)...")
    if 'account.payment' in env.registry:
        campos_pago = env['account.payment'].fields_get()
        # Campos que nos interesan según el Excel:
        campos_buscar = ['check_number', 'l10n_latam_check_payment_date', 'date', 
                         'amount', 'partner_id', 'journal_id', 'bank_id', 'ref', 'name']
        
        for cb in campos_buscar:
            if cb in campos_pago:
                tipo = campos_pago[cb]['type']
                print(f" - Campo encontrado: '{cb}' (Tipo: {tipo})")
            else:
                print(f" - Campo NO encontrado: '{cb}' -> Podría requerir desarrollo o revisar localización.")

    # 4. Diarios (Journals) Configurados para Cheques (Bank / Checks)
    print("\n4. VERIFICANDO DIARIOS FINANCIEROS (account.journal)...")
    diarios = env['account.journal'].search([('type', '=', 'bank')])
    for d in diarios:
        metodos_pago_out = d.outbound_payment_method_line_ids.mapped('name')
        print(f" - Diario: {d.name} (ID: {d.id})")
        print(f"   * Métodos de Pago Salientes: {', '.join(metodos_pago_out) if metodos_pago_out else 'Ninguno'}")

    # 5. Bancos y Proveedores (Muestreo rápido)
    print("\n5. ESTADÍSTICAS RÁPIDAS DE DATOS MAESTROS...")
    cant_bancos = env['res.bank'].search_count([])
    cant_proveedores = env['res.partner'].search_count([('supplier_rank', '>', 0)])
    print(f" - Cantidad de Bancos registrados: {cant_bancos}")
    print(f" - Cantidad de Proveedores registrados: {cant_proveedores}")
    
    print("\n" + "="*60)
    print(" FIN DE LA AUDITORÍA ")
    print("="*60)

# Ejecución (Dry-Run / Sólo lectura)
auditar_entorno_cheques(env)
