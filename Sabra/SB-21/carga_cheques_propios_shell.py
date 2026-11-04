# -*- coding: utf-8 -*-
"""
================================================================================
CARGA DE CHEQUES PROPIOS EMITIDOS (ODOO 19 ENTERPRISE - l10n_latam_check)
================================================================================
Empresa: JORGE FADY SABRA Y HEKMAT SABRA S.H. (CUIT: 30712284281)
Localización: Argentina (l10n_ar)
Diario Destino: [BNK1] Bank (ID: 36) | Método: 'own_checks' (ID: 35)
Modelo: account.payment -> l10n_latam.check (l10n_latam_new_check_ids)

CARACTERÍSTICAS:
  1. Integración nativa con Odoo 19: crea el pago y genera el registro en
     'l10n_latam.check' con Número de Cheque, Fecha de Pago diferida y CUIT emisor.
  2. Resolución y creación automática de proveedores con CUIT y tipo de doc.
  3. Soporte DRY_RUN para simulación completa con rollback garantizado.
  4. Detalle y resumen de apuntes contables generados.

EJECUCIÓN EN ODOO.SH:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < carga_cheques_propios_shell.py
================================================================================
"""

import sys
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN DE PARÁMETROS
# ==============================================================================
CONFIG = {
    # True: Simula la carga, valida asientos contables y hace ROLLBACK.
    # False: Ejecuta la carga y confirma los cambios en la base con COMMIT definitivo.
    'DRY_RUN': False,

    # Diario Bancario: Código 'BNK1' (ID: 36)
    'JOURNAL_CODE': 'BNK1',

    # Si es True: Ejecuta payment.action_post() confirmando el pago.
    # Si es False: Deja los pagos en borrador ('draft') para revisión en UI.
    'AUTO_POST': True,

    # Si se desea imputar a una cuenta específica de contrapartida (ej: saldos iniciales),
    # indicar el código aquí (ej: '3.1.01.01.001'). Si es False, imputa a Proveedores.
    'OVERRIDE_PAYABLE_ACCOUNT_CODE': False,
}

# ==============================================================================
# DATOS DE LOS 20 CHEQUES EXTRAÍDOS DEL BANCO
# ==============================================================================
CHEQUES_DATA = [
    {"nro": "70747825", "emision": "2026-10-28", "pago": "2026-11-28", "monto": 1135295.00, "cuit": "30710094337", "razon": "INDUSTRIAS TECNOMATRIC SRL", "expected_id": 5776},
    {"nro": "70747758", "emision": "2026-10-28", "pago": "2026-11-14", "monto": 2200977.00, "cuit": "30709221791", "razon": "RESPONTECH SRL", "expected_id": 4869},
    {"nro": "70727307", "emision": "2026-10-28", "pago": "2026-11-12", "monto": 3991339.59, "cuit": "30707437541", "razon": "DOLKIN S.A.", "expected_id": 5079},
    {"nro": "70602201", "emision": "2026-10-22", "pago": "2026-11-30", "monto": 6504006.84, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "expected_id": 4957},
    {"nro": "70602136", "emision": "2026-10-22", "pago": "2026-11-07", "monto": 6504006.84, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "expected_id": 4957},
    {"nro": "70596946", "emision": "2026-10-22", "pago": "2026-10-29", "monto": 3824041.65, "cuit": "33708547749", "razon": "MENAJE EL SIGLO SRL", "expected_id": 6258},
    {"nro": "70584209", "emision": "2026-10-21", "pago": "2026-11-06", "monto": 514765.19, "cuit": "30525274450", "razon": "FED. ARG.DE EMP. DE COMERCIO Y SERVICIOS", "expected_id": None},
    {"nro": "70584118", "emision": "2026-10-21", "pago": "2026-12-01", "monto": 2468428.00, "cuit": "30714148954", "razon": "MILVER SRL", "expected_id": None},
    {"nro": "70167732", "emision": "2026-10-02", "pago": "2026-11-11", "monto": 2730486.00, "cuit": "30687799042", "razon": "ELECTROCLICK SA", "expected_id": None},
    {"nro": "70167434", "emision": "2026-10-02", "pago": "2026-10-31", "monto": 3120763.00, "cuit": "30707032924", "razon": "STAR COMPANY S.A.", "expected_id": 7542},
    {"nro": "70159578", "emision": "2026-10-01", "pago": "2026-11-12", "monto": 2643503.30, "cuit": "30709009245", "razon": "INDUSTRIAS PROFILA SA", "expected_id": None},
    {"nro": "69866205", "emision": "2026-09-18", "pago": "2026-12-08", "monto": 4060437.33, "cuit": "30709009245", "razon": "INDUSTRIAS PROFILA SA", "expected_id": None},
    {"nro": "69866159", "emision": "2026-09-18", "pago": "2026-11-07", "monto": 4060437.33, "cuit": "30709009245", "razon": "INDUSTRIAS PROFILA SA", "expected_id": None},
    {"nro": "69832120", "emision": "2026-09-17", "pago": "2026-10-31", "monto": 5069874.29, "cuit": "30709542695", "razon": "DISTRIBUIDORA BRASIM S.A", "expected_id": None},
    {"nro": "69716928", "emision": "2026-09-14", "pago": "2026-11-08", "monto": 2515928.50, "cuit": "30714148954", "razon": "MILVER SRL", "expected_id": None},
    {"nro": "69063854", "emision": "2026-08-14", "pago": "2026-11-16", "monto": 426521.32, "cuit": "30517060018", "razon": "CINCAM S A C I F A E I", "expected_id": 4732},
    {"nro": "69011343", "emision": "2026-08-12", "pago": "2026-12-31", "monto": 4579060.00, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "expected_id": 4957},
    {"nro": "69011266", "emision": "2026-08-12", "pago": "2026-11-30", "monto": 4579060.00, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "expected_id": 4957},
    {"nro": "69011209", "emision": "2026-08-12", "pago": "2026-10-31", "monto": 4579060.00, "cuit": "30701481670", "razon": "CRYSTAL ROCK S.A.", "expected_id": 4957},
    {"nro": "68881036", "emision": "2026-08-06", "pago": "2026-11-16", "monto": 1583447.57, "cuit": "30517060018", "razon": "CINCAM S A C I F A E I", "expected_id": 4732},
]


def format_currency(val):
    return f"${val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_or_create_partner(env, cuit, name, expected_id):
    partner_obj = env['res.partner']
    doc_type_cuit = env.ref('l10n_ar.it_cuit', raise_if_not_found=False)

    # 1. Por CUIT
    partner = partner_obj.search([('vat', '=', cuit)], limit=1)
    if partner:
        return partner

    # 2. Por ID esperado
    if expected_id:
        p = partner_obj.browse(expected_id)
        if p.exists():
            p.write({
                'vat': cuit,
                'supplier_rank': max(p.supplier_rank, 1),
                'l10n_latam_identification_type_id': doc_type_cuit.id if doc_type_cuit else p.l10n_latam_identification_type_id.id
            })
            return p

    # 3. Por nombre exacto
    partner = partner_obj.search([('name', '=ilike', name)], limit=1)
    if partner:
        partner.write({
            'vat': cuit,
            'supplier_rank': max(partner.supplier_rank, 1),
            'l10n_latam_identification_type_id': doc_type_cuit.id if doc_type_cuit else partner.l10n_latam_identification_type_id.id
        })
        return partner

    # 4. Crear nuevo
    vals = {
        'name': name,
        'vat': cuit,
        'is_company': True,
        'supplier_rank': 1,
    }
    if doc_type_cuit:
        vals['l10n_latam_identification_type_id'] = doc_type_cuit.id

    return partner_obj.create(vals)


def execute_carga(env):
    company = env.company
    print("\n" + "=" * 80)
    print("PROCESAMIENTO DE CHEQUES PROPIOS EMITIDOS (ODOO 19 ENTERPRISE)")
    print("=" * 80)
    print(f"Modo: {'*** DRY-RUN (SIMULACIÓN - ROLLBACK AL FINAL) ***' if CONFIG['DRY_RUN'] else '!!! COMMIT DEFINITIVO !!!'}")
    print(f"Compañía: {company.name} (ID: {company.id}) | CUIT: {company.vat}")

    # 1. Diario y Método de Pago
    journal = env['account.journal'].search([
        ('code', '=', CONFIG['JOURNAL_CODE']),
        ('company_id', '=', company.id)
    ], limit=1)
    if not journal:
        raise ValueError(f"No se encontró el diario {CONFIG['JOURNAL_CODE']} en la compañía.")

    pml = journal.outbound_payment_method_line_ids.filtered(
        lambda l: l.payment_method_id.code == 'own_checks'
    )[:1]
    if not pml:
        pml = journal.outbound_payment_method_line_ids[:1]

    print(f"Diario Seleccionado: [{journal.code}] {journal.name} (ID: {journal.id})")
    print(f"Línea de Método de Egreso: {pml.name} (Código: {pml.payment_method_id.code}, ID: {pml.id})")

    # 2. Control de cheques ya existentes en l10n_latam.check
    check_model = env['l10n_latam.check']
    check_numbers = [c['nro'] for c in CHEQUES_DATA]
    existing_checks = check_model.search([
        ('name', 'in', check_numbers),
        ('company_id', '=', company.id)
    ])
    existing_numbers = set(existing_checks.mapped('name'))
    if existing_numbers:
        print(f"Aviso: {len(existing_numbers)} cheques ya están registrados en 'l10n_latam.check': {existing_numbers}")

    # 3. Procesamiento cheque por cheque
    payment_model = env['account.payment']
    created_payments = []
    total_monto = 0.0

    print("\n" + "-" * 80)
    print("CREANDO PAGOS Y REGISTROS DE CHEQUES PROPIOS...")
    print("-" * 80)

    for item in CHEQUES_DATA:
        nro = item['nro']
        cuit = item['cuit']
        monto = item['monto']
        femis = item['emision']
        fpago = item['pago']
        razon = item['razon']
        exp_id = item.get('expected_id')

        if nro in existing_numbers:
            print(f"[OMITIDO] Cheque {nro} ya existe en 'l10n_latam.check'.")
            continue

        # Resolver proveedor
        partner = get_or_create_partner(env, cuit, razon, exp_id)

        # Preparar valores de account.payment con l10n_latam_new_check_ids
        payment_vals = {
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': partner.id,
            'amount': monto,
            'date': femis,
            'journal_id': journal.id,
            'payment_method_line_id': pml.id,
            'company_id': company.id,
            'l10n_latam_new_check_ids': [(0, 0, {
                'name': nro,
                'payment_date': fpago,
                'amount': monto,
                'partner_id': partner.id,
                'memo': f"ECHEQ {nro}",
            })],
        }
        if 'memo' in payment_model._fields:
            payment_vals['memo'] = f"ECHEQ {nro} - {razon}"

        # Crear pago
        payment = payment_model.create(payment_vals)
        if payment.move_id:
            payment.move_id.ref = f"ECHEQ {nro} - {razon}"

        # Confirmar si AUTO_POST es True
        asiento_info = "BORRADOR"
        if CONFIG['AUTO_POST']:
            payment.action_post()
            asiento_info = f"Asiento: {payment.move_id.name}"

        created_payments.append(payment)
        total_monto += monto
        print(f"[OK] Cheque {nro} | {format_currency(monto).rjust(15)} | Emisión: {femis} | Cobro: {fpago} | {partner.name[:25].ljust(25)} | {asiento_info}")

    # 4. Resumen y Balance
    print("\n" + "=" * 80)
    print("RESUMEN DE OPERACIÓN")
    print("=" * 80)
    print(f"Total cheques creados: {len(created_payments)} / {len(CHEQUES_DATA)}")
    print(f"Monto Total Emitido: {format_currency(total_monto)}")

    if created_payments and CONFIG['AUTO_POST']:
        sample_move = created_payments[0].move_id
        print(f"\nEjemplo de apunte contable del primer pago ({sample_move.name}):")
        for line in sample_move.line_ids:
            print(f"  - [{line.account_id.code}] {line.account_id.name.ljust(35)} | Debe: ${line.debit:,.2f} | Haber: ${line.credit:,.2f}")

    if CONFIG['DRY_RUN']:
        print("\n" + "*" * 80)
        print(">>> RESULTADO DRY-RUN: Simulación completada con éxito. Ejecutando ROLLBACK.")
        print(">>> NINGÚN REGISTRO FUE GUARDADO PERMANENTEMENTE.")
        print(">>> Para aplicar los cambios reales, configure CONFIG['DRY_RUN'] = False y vuelva a ejecutar.")
        print("*" * 80 + "\n")
        env.cr.rollback()
    else:
        print("\n" + "#" * 80)
        print(">>> RESULTADO REAL: Todos los registros fueron guardados permanentemente. COMMIT.")
        print("#" * 80 + "\n")
        env.cr.commit()


try:
    execute_carga(env)
except Exception as e:
    import traceback
    print("\n[ERROR CRÍTICO DURANTE LA EJECUCIÓN]:")
    traceback.print_exc()
    env.cr.rollback()
