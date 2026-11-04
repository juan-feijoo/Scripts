# -*- coding: utf-8 -*-
"""
================================================================================
AUDITORÍA DE MODELOS Y DATOS PARA CHEQUES PROPIOS (ODOO 17 / 18 / 19 ENTERPRISE)
================================================================================
Entorno: Odoo.sh (odoo-bin shell)
Localización: Argentina (l10n_ar)
Empresa: JORGE FADY SABRA Y HEKMAT SABRA SH (CUIT: 30712284281)

OBJETIVO:
  1. Identificar versión exacta de Odoo y módulos instalados relacionados a cheques.
  2. Determinar el modelo y campos técnicos donde se registran los cheques emitidos.
  3. Auditar Diarios Bancarios y Métodos de Pago disponibles (egreso / outbound).
  4. Auditar los 12 Proveedores (CUITs) del listado: existencia, cuentas por pagar y facturas abiertas.
  5. Verificar colisión / duplicación de números de cheque en la base de datos.
  6. Diagnóstico contable sobre el impacto en saldos (Proveedores, Cheques Diferidos, Banco).

EJECUCIÓN EN ODOO.SH:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < auditoria_cheques_propios.py

MODO: ESTRICTAMENTE SOLO LECTURA (Garantizado con rollback al finalizar).
================================================================================
"""

import sys
import logging
from datetime import datetime

# Lista de CUITs y Razones Sociales a auditar extraídos del Excel
CHEQUES_DATA = [
    {"nro": "70747825", "emision": "2026-10-28", "pago": "2026-11-28", "monto": 1135295.00, "cuit": "30710094337", "razon": "INDUSTRIAS TECNOMATRIC SRL", "estado_banco": "EMITIDO-PENDIENTE"},
    {"nro": "70747758", "emision": "2026-10-28", "pago": "2026-11-14", "monto": 2200977.00, "cuit": "30709221791", "razon": "RESPONTECH SRL", "estado_banco": "ACTIVO"},
    {"nro": "70727307", "emision": "2026-10-28", "pago": "2026-11-12", "monto": 3991339.59, "cuit": "30707437541", "razon": "DOLKIN S.A.", "estado_banco": "EMITIDO-PENDIENTE"},
    {"nro": "70602201", "emision": "2026-10-22", "pago": "2026-11-30", "monto": 6504006.84, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "estado_banco": "CUSTODIA"},
    {"nro": "70602136", "emision": "2026-10-22", "pago": "2026-11-07", "monto": 6504006.84, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "estado_banco": "CUSTODIA"},
    {"nro": "70596946", "emision": "2026-10-22", "pago": "2026-10-29", "monto": 3824041.65, "cuit": "33708547749", "razon": "MENAJE EL SIGLO SRL", "estado_banco": "DEPOSITADO"},
    {"nro": "70584209", "emision": "2026-10-21", "pago": "2026-11-06", "monto": 514765.19, "cuit": "30525274450", "razon": "FED. ARG.DE EMP. DE COMERCIO Y SERVICIOS", "estado_banco": "ACTIVO"},
    {"nro": "70584118", "emision": "2026-10-21", "pago": "2026-12-01", "monto": 2468428.00, "cuit": "30714148954", "razon": "MILVER SRL", "estado_banco": "ACTIVO"},
    {"nro": "70167732", "emision": "2026-10-02", "pago": "2026-11-11", "monto": 2730486.00, "cuit": "30687799042", "razon": "ELECTROCLICK SA", "estado_banco": "ACTIVO-PENDIENTE"},
    {"nro": "70167434", "emision": "2026-10-02", "pago": "2026-10-31", "monto": 3120763.00, "cuit": "30707032924", "razon": "STAR COMPANY S.A.", "estado_banco": "ACTIVO"},
    {"nro": "70159578", "emision": "2026-10-01", "pago": "2026-11-12", "monto": 2643503.30, "cuit": "30709009245", "razon": "INDUSTRIAS PROFILA SA", "estado_banco": "ACTIVO"},
    {"nro": "69866205", "emision": "2026-09-18", "pago": "2026-12-08", "monto": 4060437.33, "cuit": "30709009245", "razon": "INDUSTRIAS PROFILA SA", "estado_banco": "ACTIVO"},
    {"nro": "69866159", "emision": "2026-09-18", "pago": "2026-11-07", "monto": 4060437.33, "cuit": "30709009245", "razon": "INDUSTRIAS PROFILA SA", "estado_banco": "ACTIVO"},
    {"nro": "69832120", "emision": "2026-09-17", "pago": "2026-10-31", "monto": 5069874.29, "cuit": "30709542695", "razon": "DISTRIBUIDORA BRASIM S.A", "estado_banco": "ACTIVO"},
    {"nro": "69716928", "emision": "2026-09-14", "pago": "2026-11-08", "monto": 2515928.50, "cuit": "30714148954", "razon": "MILVER SRL", "estado_banco": "ACTIVO"},
    {"nro": "69063854", "emision": "2026-08-14", "pago": "2026-11-16", "monto": 426521.32, "cuit": "30517060018", "razon": "CINCAM S A C I F A E I", "estado_banco": "CUSTODIA"},
    {"nro": "69011343", "emision": "2026-08-12", "pago": "2026-12-31", "monto": 4579060.00, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "estado_banco": "CUSTODIA"},
    {"nro": "69011266", "emision": "2026-08-12", "pago": "2026-11-30", "monto": 4579060.00, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "estado_banco": "CUSTODIA"},
    {"nro": "69011209", "emision": "2026-08-12", "pago": "2026-10-31", "monto": 4579060.00, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "estado_banco": "CUSTODIA"},
    {"nro": "68881036", "emision": "2026-08-06", "pago": "2026-11-16", "monto": 1583447.57, "cuit": "30517060018", "razon": "CINCAM S A C I F A E I", "estado_banco": "CUSTODIA"},
]

def format_currency(val):
    return f"${val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def run_audit(env):
    print("\n" + "=" * 80)
    print("INICIO DE AUDITORÍA: CARGA DE CHEQUES PROPIOS EMITIDOS")
    print("=" * 80)

    # 1. VERIFICACIÓN DE ENTORNO Y VERSIÓN
    from odoo import release
    company = env.company
    print(f"Versión de Odoo: {release.version} ({release.version_info})")
    print(f"Compañía Activa: {company.name} (ID: {company.id})")
    print(f"CUIT Compañía: {getattr(company.partner_id, 'vat', 'N/A')}")
    print(f"Moneda Compañía: {company.currency_id.name}")

    # 2. MÓDULOS INSTALADOS
    print("\n" + "-" * 80)
    print("1. MÓDULOS INSTALADOS RELEVANTES")
    print("-" * 80)
    check_modules = [
        'account', 'account_check_printing', 'l10n_latam_check',
        'l10n_ar', 'l10n_ar_account_check', 'account_check'
    ]
    installed_mods = env['ir.module.module'].search([
        ('name', 'in', check_modules),
        ('state', '=', 'installed')
    ])
    for mod in installed_mods:
        print(f"  [INSTALADO] {mod.name.ljust(30)}: {mod.shortdesc} (v{mod.installed_version})")
    
    missing_mods = set(check_modules) - set(installed_mods.mapped('name'))
    for m in missing_mods:
        print(f"  [NO INSTALADO] {m}")

    # 3. INSPECCIÓN DE MODELOS Y CAMPOS DE CHEQUES
    print("\n" + "-" * 80)
    print("2. INSPECCIÓN DE MODELOS Y CAMPOS DE CHEQUES EN EL SISTEMA")
    print("-" * 80)
    payment_model = env['account.payment']
    payment_fields = payment_model.fields_get()

    candidate_check_fields = [
        'check_number', 'check_payment_date', 'l10n_latam_check_payment_date',
        'l10n_latam_check_id', 'l10n_latam_check_number', 'l10n_latam_manual_checks',
        'check_amount_in_words', 'payment_method_line_id'
    ]
    print("Campos relevantes en 'account.payment':")
    for fld in candidate_check_fields:
        if fld in payment_fields:
            finfo = payment_fields[fld]
            print(f"  - {fld.ljust(32)}: Tipo={finfo['type']}, String='{finfo.get('string', '')}'")
        else:
            print(f"  - {fld.ljust(32)}: [NO EXISTE]")

    # Verificar si existe modelo específico de cheques
    for model_name in ['l10n_latam.check', 'account.check', 'account.checkbook']:
        if model_name in env:
            m_obj = env[model_name]
            count = m_obj.search_count([])
            print(f"Modelo '{model_name}': EXISTE en el ORM ({count} registros)")
            m_fields = m_obj.fields_get()
            sample_flds = [f for f in ['payment_date', 'issue_date', 'check_number', 'type', 'state'] if f in m_fields]
            print(f"    Campos clave: {sample_flds}")
        else:
            print(f"Modelo '{model_name}': NO existe en esta base.")

    # 4. AUDITORÍA DE DIARIOS BANCARIOS Y MÉTODOS DE PAGO
    print("\n" + "-" * 80)
    print("3. DIARIOS BANCARIOS DISPONIBLES (type='bank')")
    print("-" * 80)
    bank_journals = env['account.journal'].search([
        ('company_id', '=', company.id),
        ('type', '=', 'bank')
    ])
    if not bank_journals:
        print("  ¡ALERTA!: No se encontraron diarios de tipo 'bank' en esta compañía.")
    for j in bank_journals:
        print(f"\nDiario: [{j.code}] {j.name} (ID: {j.id})")
        print(f"  Cuenta de Banco (default_account_id): {j.default_account_id.code} - {j.default_account_id.name}")
        suspense = getattr(j, 'suspense_account_id', False)
        if suspense:
            print(f"  Cuenta Transitoria (suspense): {suspense.code} - {suspense.name}")
        out_account = getattr(j, 'outstanding_payments_account_id', False)
        if out_account:
            print(f"  Cuenta Pagos Pendientes (outstanding_payments): {out_account.code} - {out_account.name}")

        print("  Métodos de Pago de Egreso (outbound_payment_method_line_ids):")
        for line in j.outbound_payment_method_line_ids:
            pm = line.payment_method_id
            print(f"    - Línea ID {line.id}: '{line.name}' (Código: '{pm.code}', Tipo: '{pm.payment_type}')")

    # 5. AUDITORÍA DE PROVEEDORES (CUITS) Y FACTURAS PENDIENTES
    print("\n" + "-" * 80)
    print("4. AUDITORÍA DE PROVEEDORES Y DEUDA / FACTURAS ABIERTAS")
    print("-" * 80)
    
    unique_partners = {}
    for item in CHEQUES_DATA:
        c = item['cuit']
        if c not in unique_partners:
            unique_partners[c] = {
                'cuit': c,
                'razon': item['razon'],
                'cheques': [],
                'monto_total': 0.0
            }
        unique_partners[c]['cheques'].append(item)
        unique_partners[c]['monto_total'] += item['monto']

    total_general = sum(p['monto_total'] for p in unique_partners.values())
    print(f"Total proveedores a verificar: {len(unique_partners)}")
    print(f"Total importe de los 20 cheques: {format_currency(total_general)}\n")

    partner_obj = env['res.partner']
    move_obj = env['account.move']

    for cuit, pdata in unique_partners.items():
        # Buscar por CUIT con o sin guiones
        clean_cuit = cuit.replace('-', '').strip()
        partners = partner_obj.search([
            ('vat', 'like', clean_cuit)
        ])
        if not partners:
            # Buscar por nombre similar
            partners = partner_obj.search([
                ('name', 'ilike', pdata['razon'].split()[0])
            ])

        status_partner = ""
        p_id = False
        if len(partners) == 1:
            p_id = partners[0]
            status_partner = f"ENCONTRADO (ID: {p_id.id}) - '{p_id.name}' [VAT: {p_id.vat}]"
        elif len(partners) > 1:
            p_id = partners[0]
            status_partner = f"MÚLTIPLES COINCIDENCIAS ({len(partners)}). Seleccionado ID {p_id.id}: '{p_id.name}'"
        else:
            status_partner = "NO ENCONTRADO EN ODOO (Requerirá creación o asignación previa)"

        print(f"CUIT {cuit} | {pdata['razon'].ljust(35)}: {status_partner}")
        print(f"  Cheques a emitir: {len(pdata['cheques'])} por un total de {format_currency(pdata['monto_total'])}")

        if p_id:
            # Buscar facturas de proveedor impagas (in_invoice, no pagadas o parcialmente pagadas)
            open_bills = move_obj.search([
                ('partner_id', 'child_of', p_id.id),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial'])
            ])
            if open_bills:
                total_residual = sum(open_bills.mapped('amount_residual'))
                print(f"  -> Facturas abiertas encontradas: {len(open_bills)} | Deuda pendiente: {format_currency(total_residual)}")
                for b in open_bills[:3]:
                    print(f"     * Factura {b.name or b.ref} ({b.invoice_date}) - Saldo: {format_currency(b.amount_residual)}")
                if len(open_bills) > 3:
                    print(f"     * (... y {len(open_bills) - 3} facturas más)")
            else:
                print(f"  -> Facturas abiertas encontradas: NINGUNA (Si se registra el pago sin factura, generará saldo a favor del proveedor).")
        print()

    # 6. VERIFICACIÓN DE NÚMEROS DE CHEQUE EXISTENTES
    print("-" * 80)
    print("5. VERIFICACIÓN DE COLISIÓN DE NÚMEROS DE CHEQUE")
    print("-" * 80)
    check_numbers = [item['nro'] for item in CHEQUES_DATA]
    
    # Buscar en account.payment
    if 'check_number' in payment_fields:
        existing_pmts = payment_model.search([
            ('check_number', 'in', check_numbers),
            ('company_id', '=', company.id)
        ])
        if existing_pmts:
            print(f"¡ALERTA!: Se encontraron {len(existing_pmts)} pagos con estos números de cheque ya cargados:")
            for ep in existing_pmts:
                print(f"  - Cheque Nro: {ep.check_number} | Pago ID: {ep.id} | Fecha: {ep.date} | Monto: {format_currency(ep.amount)} | Estado: {ep.state}")
        else:
            print("  [OK] Ninguno de los 20 números de cheque existe actualmente en 'account.payment'.")
    else:
        print("  Nota: El campo 'check_number' no existe directamente en 'account.payment'.")

    # 7. RESUMEN CONTABLE Y RECOMENDACIÓN TÉCNICA
    print("\n" + "=" * 80)
    print("DIAGNÓSTICO CONTABLE Y ESTRATEGIA DE SALDOS")
    print("=" * 80)
    print("""
Al registrar pagos de cheques propios diferidos emitidos:
  - Asiento de Pago (Fecha de Emisión):
      Debe:  Proveedores / Cuentas a Pagar (o Cuenta Puente si es Apertura)
      Haber: Cheques Diferidos Emitidos / Pagos Pendientes (outstanding_payments_account_id)
  - Asiento de Extracto Bancario (Fecha de Cobro/Débito real en el Banco):
      Debe:  Cheques Diferidos Emitidos / Pagos Pendientes
      Haber: Banco Cuenta Corriente

CONSIDERACIONES CRÍTICAS SEGÚN EL ESCENARIO:
1. Si es MIGRACIÓN DE SALDOS INICIALES:
   - Si la deuda con proveedores ya se migró NETA de estos cheques, NO debe imputarse a Proveedores,
     sino a la cuenta de Saldos Iniciales / Ajuste de Apertura.
   - Si la deuda con proveedores se cargó BRUTA (con las facturas impagas completas),
     los pagos deben crearse e imputarse contra las facturas para cancelar el saldo deudor/acreedor.
2. Si es OPERATORIA NORMAL EN CURSO:
   - Se registran como account.payment asociados al diario bancario correspondiente.
   - Si existen facturas abiertas, se concilian automáticamente.
""")
    print("=" * 80)
    print("FIN DE AUDITORÍA (No se han realizado modificaciones en la base de datos)")
    print("=" * 80 + "\n")

# Ejecutar auditoría dentro del contexto de Odoo shell
try:
    run_audit(env)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    # Garantizar estrictamente que no quede ninguna transacción abierta
    env.cr.rollback()
