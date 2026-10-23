# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE AUDITORÍA DE IMPUESTOS Y POSICIONES FISCALES (ODOO 18+ ENTERPRISE)
================================================================================
Entorno: Odoo.sh / Multi-Compañía
Modelo compatible: Odoo 18.0+ / 19.0+ (Mapeo de impuestos invertido en account.tax)
Localización: Argentina (l10n_ar)

Modo de uso en odoo-bin shell:
    exec(open('audit_taxes.py').read())
================================================================================
"""
import re
import csv
import logging

_logger = logging.getLogger("TAX_AUDIT")

# ------------------------------------------------------------------------------
# PARÁMETROS DE CONFIGURACIÓN
# ------------------------------------------------------------------------------
DRY_RUN = True  # Script de solo lectura / diagnóstico
TARGET_COMPANY_ID = None  # None = Toma automáticamente la compañía activa (env.company)
FILTER_DATE = None  # None = Audita todos los impuestos sin filtrar por fecha
EXPORT_CSV = True  # Genera archivo CSV con el detalle
CSV_FILENAME = "tax_audit_report.csv"

# Determinar compañía
company = env["res.company"].browse(TARGET_COMPANY_ID) if TARGET_COMPANY_ID else env.company

print("=" * 90)
print(f"[*] INICIANDO AUDITORÍA DE IMPUESTOS (ODOO 18+) | DRY_RUN = {DRY_RUN}")
print(f"[*] Compañía auditada: [{company.id}] {company.name} (País: {company.country_id.code})")
print("=" * 90)

# Construir dominio de búsqueda
domain = [("company_id", "=", company.id), ("active", "in", [True, False])]
if FILTER_DATE:
    domain.append(("create_date", ">=", FILTER_DATE))

taxes = env["account.tax"].search(domain, order="type_tax_use desc, id asc")
print(f"[i] Impuestos totales encontrados a auditar: {len(taxes)}")

regex_percent = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
clean_html = re.compile(r"<.*?>")

audit_records = []
total_with_issues = 0

for tax in taxes:
    issues = []
    severity = "INFO"

    # 1. Chequeo de Nombre vs Amount
    tax_name = tax.name or ""
    matches_name = regex_percent.findall(tax_name)
    if matches_name:
        try:
            nominal_rate = float(matches_name[0].replace(",", "."))
            if abs(nominal_rate - tax.amount) > 0.0001:
                issues.append(
                    f"INCONSISTENCIA TASA: Nombre indica {nominal_rate}% pero amount es {tax.amount}%"
                )
                severity = "ERROR"
        except ValueError:
            pass

    # 2. Chequeo de Nombre vs Descripción (limpiando tags html)
    raw_desc = clean_html.sub("", tax.description or "").strip()
    if raw_desc:
        matches_desc = regex_percent.findall(raw_desc)
        if matches_desc:
            try:
                desc_rate = float(matches_desc[0].replace(",", "."))
                if abs(desc_rate - tax.amount) > 0.0001:
                    issues.append(
                        f"DESCRIPCIÓN DESALINEADA: Descripción '{raw_desc}' vs amount {tax.amount}%"
                    )
                    if severity != "ERROR":
                        severity = "WARNING"
            except ValueError:
                pass

    # 3. Chequeo de Cuentas Contables en Repartition Lines
    tax_rep_lines = tax.repartition_line_ids.filtered(lambda l: l.repartition_type == "tax")
    lines_without_account = tax_rep_lines.filtered(lambda l: not l.account_id)
    if lines_without_account:
        issues.append(
            f"FALTA CUENTA CONTABLE: {len(lines_without_account)} línea(s) de impuesto sin cuenta"
        )
        severity = "ERROR"

    # 4. Chequeo de Localización Argentina (l10n_ar)
    group_name = (tax.tax_group_id.name or "").lower()
    is_perception = (
        "perc" in group_name
        or "iibb" in group_name
        or getattr(tax, "l10n_ar_tribute_afip_code", False) in ["06", "07", "08"]
    )

    if is_perception:
        if hasattr(tax, "l10n_ar_state_id") and not tax.l10n_ar_state_id:
            issues.append("l10n_ar: Provincia vacía (l10n_ar_state_id no configurado)")
            if severity != "ERROR":
                severity = "WARNING"
        if hasattr(tax, "l10n_ar_code") and not tax.l10n_ar_code:
            issues.append("l10n_ar: Código Régimen vacío (l10n_ar_code para SIRCAR/TXT)")
            if severity != "ERROR":
                severity = "WARNING"

    # 5. Mapeo en Posiciones Fiscales (Odoo 18+)
    fp_names = tax.fiscal_position_ids.mapped("name") if hasattr(tax, "fiscal_position_ids") else []
    original_taxes = tax.original_tax_ids.mapped("name") if hasattr(tax, "original_tax_ids") else []
    replacing_taxes = tax.replacing_tax_ids.mapped("name") if hasattr(tax, "replacing_tax_ids") else []

    for fp_name in fp_names:
        matches_fp = regex_percent.findall(fp_name)
        if matches_fp:
            try:
                fp_rate = float(matches_fp[0].replace(",", "."))
                if abs(fp_rate - tax.amount) > 0.0001:
                    issues.append(
                        f"POSICIÓN FISCAL DISPAREJA: Asignado a FP '{fp_name}' ({fp_rate}%) pero tasa={tax.amount}%"
                    )
                    severity = "ERROR"
            except ValueError:
                pass

    # 6. Impacto contable: Uso real
    move_lines_count = len(tax.account_move_line_ids)
    is_used = getattr(tax, "is_used", move_lines_count > 0)
    safe_to_delete = (move_lines_count == 0)

    if issues:
        total_with_issues += 1
        audit_records.append({
            "id": tax.id,
            "name": tax.name,
            "amount": tax.amount,
            "type_tax_use": tax.type_tax_use,
            "tax_group": tax.tax_group_id.name if tax.tax_group_id else "",
            "state": tax.l10n_ar_state_id.name if hasattr(tax, "l10n_ar_state_id") and tax.l10n_ar_state_id else "",
            "sircar_code": getattr(tax, "l10n_ar_code", "") or "",
            "fiscal_positions": ", ".join(fp_names),
            "replaces": ", ".join(original_taxes),
            "replaced_by": ", ".join(replacing_taxes),
            "severity": severity,
            "is_used": is_used,
            "move_lines_count": move_lines_count,
            "safe_to_delete": safe_to_delete,
            "issues": " | ".join(issues),
            "issues_list": issues,
        })

# ------------------------------------------------------------------------------
# IMPRESIÓN DEL REPORTE
# ------------------------------------------------------------------------------
print(f"\n[!] RESULTADOS: {total_with_issues} impuestos con anomalías detectadas de {len(taxes)} analizados.\n")

# Mostramos primero los ERROR (críticos) y luego WARNING
audit_records.sort(key=lambda x: (0 if x["severity"] == "ERROR" else 1, x["id"]))

for r in audit_records:
    tag = f"[{r['severity']}]"
    print(f"{tag:9} Tax ID: {r['id']:<4} | {r['name']:<28} | Amount: {r['amount']}% | Uso: {r['type_tax_use']}")
    print(f"          Grupo: {r['tax_group']:<18} | Usado en Asientos: {r['move_lines_count']:<3} | ¿Seguro Borrar/Modificar?: {r['safe_to_delete']}")
    if r['fiscal_positions']:
        print(f"          Posiciones Fiscales: {r['fiscal_positions']}")
    if r['replaces']:
        print(f"          Reemplaza a: {r['replaces']}")
    for iss in r['issues_list']:
        print(f"          -> {iss}")
    print("-" * 90)

# Exportación CSV
if EXPORT_CSV and audit_records:
    try:
        keys = [
            "id", "name", "amount", "type_tax_use", "tax_group", "state",
            "sircar_code", "fiscal_positions", "replaces", "replaced_by",
            "severity", "is_used", "move_lines_count", "safe_to_delete", "issues"
        ]
        with open(CSV_FILENAME, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in audit_records:
                row = {k: r[k] for k in keys}
                writer.writerow(row)
        print(f"\n[+] Reporte CSV exportado exitosamente a: {CSV_FILENAME}")
    except Exception as e:
        print(f"\n[-] Error al exportar CSV: {e}")

print("=" * 90)
print(f"[*] AUDITORÍA FINALIZADA (DRY_RUN = {DRY_RUN}) para compañía: {company.name}.")
print("=" * 90)
