# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE REVISIÓN Y ALTA DE PROVEEDORES DE CHEQUES EN ODOO 19
================================================================================
Empresa: JORGE FADY SABRA Y HEKMAT SABRA S.H. (CUIT: 30712284281)
Localización: Argentina (l10n_ar)

OBJETIVO:
  1. Localizar los 12 proveedores del listado de cheques por CUIT o Razón Social exacta.
  2. Actualizar el CUIT (vat) si el proveedor ya existe por nombre pero no tenía CUIT.
  3. Crear los proveedores faltantes con su CUIT y tipo de responsabilidad AFIP (RI).
  4. Evitar asignaciones cruzadas erróneas (ej: INDUSTRIAS PROFILA vs BOSCH).

EJECUCIÓN:
  python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < preparar_proveedores_cheques.py
================================================================================
"""

CONFIG = {
    # True: Solo simula y hace rollback.
    # False: Crea/actualiza los proveedores y hace commit.
    'DRY_RUN': True,
}

PROVEEDORES_LIST = [
    {"cuit": "30710094337", "name": "INDUSTRIAS TECNOMATRIC SRL", "expected_id": 5776},
    {"cuit": "30709221791", "name": "RESPONTECH SRL", "expected_id": 4869},
    {"cuit": "30707437541", "name": "DOLKIN S.A.", "expected_id": 5079},
    {"cuit": "30701481670", "name": "CRYSTAL ROCK S.A.", "expected_id": 4957},
    {"cuit": "33708547749", "name": "MENAJE EL SIGLO SRL", "expected_id": 6258},
    {"cuit": "30525274450", "name": "FED. ARG.DE EMP. DE COMERCIO Y SERVICIOS", "expected_id": None},
    {"cuit": "30714148954", "name": "MILVER SRL", "expected_id": None},
    {"cuit": "30687799042", "name": "ELECTROCLICK SA", "expected_id": None},
    {"cuit": "30707032924", "name": "STAR COMPANY S.A.", "expected_id": 7542},
    {"cuit": "30709009245", "name": "INDUSTRIAS PROFILA SA", "expected_id": None},
    {"cuit": "30709542695", "name": "DISTRIBUIDORA BRASIM S.A", "expected_id": None},
    {"cuit": "30517060018", "name": "CINCAM S A C I F A E I", "expected_id": 4732},
]

def run(env):
    partner_obj = env['res.partner']
    doc_type_cuit = env.ref('l10n_ar.it_cuit', raise_if_not_found=False)
    afip_ri = env.ref('l10n_ar.res_IVARI', raise_if_not_found=False) # Responsable Inscripto

    print("\n" + "=" * 80)
    print("PROCESANDO NORMALIZACIÓN DE PROVEEDORES PARA CHEQUES")
    print("=" * 80)
    print(f"Modo: {'DRY-RUN (Simulación con rollback)' if CONFIG['DRY_RUN'] else 'COMMIT DEFINITIVO'}\n")

    for p in PROVEEDORES_LIST:
        cuit = p['cuit']
        name = p['name']
        exp_id = p['expected_id']

        # 1. Buscar por CUIT
        partner = partner_obj.search([('vat', '=', cuit)], limit=1)

        # 2. Si no se encuentra por CUIT pero hay un ID conocido
        if not partner and exp_id:
            candidate = partner_obj.browse(exp_id)
            if candidate.exists():
                print(f"[ACTUALIZAR CUIT] ID {candidate.id} '{candidate.name}' -> Asignar CUIT {cuit}")
                partner = candidate
                partner.write({
                    'vat': cuit,
                    'l10n_latam_identification_type_id': doc_type_cuit.id if doc_type_cuit else partner.l10n_latam_identification_type_id.id,
                    'supplier_rank': max(partner.supplier_rank, 1),
                })

        # 3. Si no se encuentra por CUIT, buscar por nombre exacto o muy aproximado
        if not partner:
            partner = partner_obj.search([('name', '=ilike', name)], limit=1)
            if partner:
                print(f"[ASOCIAR CUIT] Partner '{partner.name}' (ID {partner.id}) encontrado por nombre -> Asignando CUIT {cuit}")
                partner.write({
                    'vat': cuit,
                    'l10n_latam_identification_type_id': doc_type_cuit.id if doc_type_cuit else partner.l10n_latam_identification_type_id.id,
                    'supplier_rank': max(partner.supplier_rank, 1),
                })

        # 4. Si definitivamente no existe, crearlo
        if not partner:
            print(f"[CREAR NUEVO] Creando proveedor: '{name}' | CUIT: {cuit}")
            create_vals = {
                'name': name,
                'vat': cuit,
                'is_company': True,
                'supplier_rank': 1,
            }
            if doc_type_cuit:
                create_vals['l10n_latam_identification_type_id'] = doc_type_cuit.id
            if afip_ri and hasattr(partner_obj, 'l10n_ar_afip_responsibility_type_id'):
                create_vals['l10n_ar_afip_responsibility_type_id'] = afip_ri.id

            partner = partner_obj.create(create_vals)
            print(f"  -> Creado con ID {partner.id}")
        else:
            print(f"[OK] ID {partner.id}: '{partner.name}' [VAT: {partner.vat}]")

    print("\n" + "=" * 80)
    if CONFIG['DRY_RUN']:
        print(">>> Simulación finalizada. Aplicando ROLLBACK.")
        env.cr.rollback()
    else:
        print(">>> Cambios aplicados permanentemente. COMMIT.")
        env.cr.commit()
    print("=" * 80 + "\n")

try:
    run(env)
except Exception as e:
    import traceback
    traceback.print_exc()
    env.cr.rollback()
