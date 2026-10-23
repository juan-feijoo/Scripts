# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT UNIVERSAL DE REPARACIÓN DE IMPUESTOS Y POSICIONES FISCALES (ODOO 18+)
================================================================================
Entorno: Odoo 18.0+ / 19.0+ Enterprise (Localización Argentina - Multi-Compañía)
Propósito: Detectar y corregir automáticamente inconsistencias en impuestos de
           Percepciones de Ventas (IIBB) para CUALQUIER compañía o base de datos:
           1. Corrige Nombres, Etiquetas y Descripciones según su alícuota real.
           2. Asigna la Provincia (l10n_ar_state_id) correspondiente.
           3. Inyecta la Cuenta Contable de Pasivo correspondiente a la jurisdicción
              en las líneas de repartición de facturas y reembolsos.
           4. Protege la base: Solo repara impuestos NO usados en asientos contables.

Modo de uso en odoo-bin shell:
    exec(open('repair_taxes.py').read())
================================================================================
"""
import re
import logging

_logger = logging.getLogger("TAX_REPAIR")

# ------------------------------------------------------------------------------
# PARÁMETROS DE CONFIGURACIÓN
# ------------------------------------------------------------------------------
DRY_RUN = True  # CAMBIAR A False ÚNICAMENTE CUANDO ESTÉS CONFORME CON LA SIMULACIÓN
TARGET_COMPANY_ID = None  # None = Toma automáticamente la compañía activa (env.company)

# Diccionario de Jurisdicciones Argentinas (Códigos AFIP / ISO y palabras clave)
ARGENTINA_JURISDICTIONS = {
    "CABA": {"code": "C", "keywords": ["caba", "ciudad autonoma", "capital federal", "agip"]},
    "Buenos Aires": {"code": "B", "keywords": ["buenos aires", "pba", "arba"]},
    "Catamarca": {"code": "K", "keywords": ["catamarca"]},
    "Córdoba": {"code": "X", "keywords": ["cordoba", "cba"]},
    "Corrientes": {"code": "W", "keywords": ["corrientes", "cts"]},
    "Entre Ríos": {"code": "E", "keywords": ["entre rios", "entre ríos", "er"]},
    "Jujuy": {"code": "Y", "keywords": ["jujuy"]},
    "Mendoza": {"code": "M", "keywords": ["mendoza", "mza"]},
    "La Rioja": {"code": "F", "keywords": ["la rioja", "lr"]},
    "Salta": {"code": "A", "keywords": ["salta"]},
    "San Juan": {"code": "J", "keywords": ["san juan", "sj"]},
    "San Luis": {"code": "D", "keywords": ["san luis", "sl"]},
    "Santa Fe": {"code": "S", "keywords": ["santa fe", "sf"]},
    "Santiago del Estero": {"code": "G", "keywords": ["santiago del estero", "santiago", "se"]},
    "Tucumán": {"code": "T", "keywords": ["tucuman", "tucumán"]},
    "Chaco": {"code": "H", "keywords": ["chaco", "cho"]},
    "Chubut": {"code": "U", "keywords": ["chubut", "cht"]},
    "Formosa": {"code": "P", "keywords": ["formosa"]},
    "Misiones": {"code": "N", "keywords": ["misiones", "ms"]},
    "Neuquén": {"code": "Q", "keywords": ["neuquen", "neuquén"]},
    "La Pampa": {"code": "L", "keywords": ["la pampa", "lp"]},
    "Río Negro": {"code": "R", "keywords": ["rio negro", "río negro", "rn"]},
    "Santa Cruz": {"code": "Z", "keywords": ["santa cruz", "sc"]},
    "Tierra del Fuego": {"code": "V", "keywords": ["tierra del fuego", "tais"]},
}

company = env["res.company"].browse(TARGET_COMPANY_ID) if TARGET_COMPANY_ID else env.company

print("\n" + "=" * 90)
print(f" [*] SCRIPT UNIVERSAL DE REPARACIÓN DE IMPUESTOS (ODOO 18+) | DRY_RUN = {DRY_RUN}")
print(f" [*] Compañía activa: [{company.id}] {company.name} (País: {company.country_id.code})")
print("=" * 90 + "\n")

# ------------------------------------------------------------------------------
# 1. PRE-RESOLVER PROVINCIAS Y CUENTAS CONTABLES DE PASIVO PARA ESTA COMPAÑÍA
# ------------------------------------------------------------------------------
print("[i] Mapeando Jurisdicciones y Cuentas de Percepción en la compañía...")
jurisdiction_cache = {}

for name, info in ARGENTINA_JURISDICTIONS.items():
    # 1.1 Buscar Provincia en res.country.state
    state = env["res.country.state"].search([
        ("country_id.code", "=", "AR"),
        "|",
        ("code", "=", info["code"]),
        ("name", "ilike", name),
    ], limit=1)

    # 1.2 Buscar Cuenta de Percepciones a Depositar (Pasivo, clase 2)
    # Busca por nombre de la jurisdicción + percep/iibb en el pasivo de esta empresa
    account = env["account.account"].search([
        ("company_ids", "in", [company.id]),
        ("code", "=like", "2.%"),
        ("name", "ilike", name),
    ], limit=1)

    # Si no la encuentra con el nombre directo, intenta buscar por código estándar 2.1.3.02.xxx
    if not account and name in ["Jujuy", "Salta", "Tucumán"]:
        std_codes = {"Jujuy": "2.1.3.02.160", "Salta": "2.1.3.02.220", "Tucumán": "2.1.3.02.320"}
        account = env["account.account"].search([
            ("company_ids", "in", [company.id]),
            ("code", "=", std_codes[name]),
        ], limit=1)

    jurisdiction_cache[name] = {
        "state": state,
        "account": account,
        "keywords": info["keywords"],
    }

# ------------------------------------------------------------------------------
# 2. IDENTIFICAR DINÁMICAMENTE IMPUESTOS CON ANOMALÍAS
# ------------------------------------------------------------------------------
regex_percent = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")

# Buscamos impuestos de venta de percepciones IIBB de esta compañía
domain = [
    ("company_id", "=", company.id),
    ("type_tax_use", "=", "sale"),
    ("active", "in", [True, False]),
    "|", "|",
    ("tax_group_id.name", "ilike", "perc"),
    ("tax_group_id.name", "ilike", "iibb"),
    ("name", "ilike", "iibb"),
]
all_sales_taxes = env["account.tax"].search(domain, order="id asc")
print(f"[i] Impuestos de percepción de ventas encontrados: {len(all_sales_taxes)}")

taxes_to_repair = []

for tax in all_sales_taxes:
    # Chequear si tiene alguna anomalía:
    has_issues = False

    # Anomalía A: Repartition lines sin cuenta contable
    tax_rep_lines = tax.repartition_line_ids.filtered(lambda l: l.repartition_type == "tax")
    if tax_rep_lines.filtered(lambda l: not l.account_id):
        has_issues = True

    # Anomalía B: Discrepancia nombre vs alícuota
    matches = regex_percent.findall(tax.name or "")
    if matches:
        try:
            nominal_rate = float(matches[0].replace(",", "."))
            if abs(nominal_rate - tax.amount) > 0.0001:
                has_issues = True
        except ValueError:
            pass

    # Anomalía C: Provincia vacía
    if hasattr(tax, "l10n_ar_state_id") and not tax.l10n_ar_state_id:
        has_issues = True

    if has_issues:
        taxes_to_repair.append(tax)

print(f"[!] Total de impuestos que requieren reparación: {len(taxes_to_repair)}\n")

# ------------------------------------------------------------------------------
# 3. EJECUTAR REPARACIÓN
# ------------------------------------------------------------------------------
modified_count = 0
skipped_due_to_moves = 0

for tax in taxes_to_repair:
    # Medida de Seguridad Crítica: si ya se usó en asientos reales, no tocar
    move_count = len(tax.account_move_line_ids)
    if move_count > 0:
        print(f"[ADVERTENCIA] Tax ID {tax.id} ({tax.name}) tiene {move_count} asientos contables. SE OMITE por seguridad.")
        skipped_due_to_moves += 1
        continue

    # Detectar jurisdicción analizando el nombre y grupo
    search_text = f"{tax.name or ''} {tax.tax_group_id.name or ''}".lower()
    matched_jur = None

    for jur_name, jur_data in jurisdiction_cache.items():
        for kw in jur_data["keywords"]:
            # Búsqueda de palabra completa o token
            if re.search(r'\b' + re.escape(kw) + r'\b', search_text):
                matched_jur = jur_name
                break
        if matched_jur:
            break

    if not matched_jur:
        print(f"[?] Tax ID {tax.id} ({tax.name}): No se pudo identificar la jurisdicción argentina. Se omite.")
        continue

    target_state = jurisdiction_cache[matched_jur]["state"]
    target_account = jurisdiction_cache[matched_jur]["account"]

    # Calcular nombre consistente con el amount real
    rate_str = f"{tax.amount:.4g}%"
    corrected_name = f"{rate_str} IIBB {matched_jur}"

    changes = []
    vals_to_write = {}

    # 1. Sincronizar Nombre y Etiquetas
    if tax.name != corrected_name:
        changes.append(f"Nombre: '{tax.name}' -> '{corrected_name}'")
        vals_to_write["name"] = corrected_name
        vals_to_write["tax_label"] = corrected_name
        vals_to_write["description"] = corrected_name

    # 2. Asignar Provincia
    if target_state and tax.l10n_ar_state_id != target_state:
        changes.append(f"Provincia: '{tax.l10n_ar_state_id.name or 'Vacía'}' -> '{target_state.name}'")
        vals_to_write["l10n_ar_state_id"] = target_state.id

    # 3. Código AFIP de tributo (07 = Percepción)
    if getattr(tax, "l10n_ar_tribute_afip_code", False) != "07":
        changes.append("Tributo AFIP: '07' (Percepciones)")
        vals_to_write["l10n_ar_tribute_afip_code"] = "07"

    # 4. Asignar Cuentas Contables en Repartición
    tax_rep_lines = tax.repartition_line_ids.filtered(lambda l: l.repartition_type == "tax")
    lines_to_fix = [l for l in tax_rep_lines if target_account and l.account_id != target_account]
    if lines_to_fix:
        acc_str = f"{target_account.code} - {target_account.name}" if target_account else "[SIN CUENTA CONFIGURADA]"
        changes.append(f"Cuentas Repartición: Asignando {acc_str} en {len(lines_to_fix)} línea(s)")

    if changes:
        modified_count += 1
        print(f"[*] [Tax ID {tax.id}] Amount: {tax.amount}% | Jurisdicción: {matched_jur}")
        for c in changes:
            print(f"      + {c}")

        if not DRY_RUN:
            if vals_to_write:
                tax.write(vals_to_write)
            if target_account:
                for line in lines_to_fix:
                    line.account_id = target_account.id

        print("-" * 90)

# ------------------------------------------------------------------------------
# RESUMEN DE EJECUCIÓN
# ------------------------------------------------------------------------------
print("\n" + "=" * 90)
if DRY_RUN:
    print(f" [SIMULACIÓN COMPLETADA] Se repararían {modified_count} impuestos en la compañía '{company.name}'.")
    if skipped_due_to_moves > 0:
        print(f" [PROTECCIÓN] Se omitieron {skipped_due_to_moves} impuestos porque ya tienen asientos contables reales.")
    print(" [NOTA] Como DRY_RUN = True, NO se aplicó ningún cambio real en la base de datos.")
    print(" Para aplicar los cambios reales, edita 'DRY_RUN = False' y vuelve a ejecutar.")
else:
    env.cr.commit()
    print(f" [ÉXITO] Se actualizaron y repararon {modified_count} impuestos correctamente en la compañía '{company.name}'.")
print("=" * 90 + "\n")
