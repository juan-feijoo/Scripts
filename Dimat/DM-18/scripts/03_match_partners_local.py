# -*- coding: utf-8 -*-
"""
================================================================================
CRUCE LOCAL: CONTACTOS ODOO (partners_cuit.json) VS PADRÓN ARBA 11/2026
================================================================================
Carga en memoria los 1,326 contactos de Odoo y busca sus alícuotas en:
1. PadronRGSRet112026.TXT (Retenciones) -> Aplica regla Droguerías (min 2.50%)
2. PadronRGSPer112026.txt (Percepciones)
Genera estadísticas de cuántos contactos tienen retención y percepción,
y qué alícuotas les corresponden para el período 01/11/2026 al 30/11/2026.
================================================================================
"""

import json
import zipfile
import time

PARTNERS_FILE = "partners_cuit.json"
ZIP_PATH = "PadronRGS112026.zip"

def match_partners():
    print("=" * 80)
    print(" CRUCE DE CONTACTOS ODOO VS PADRÓN ARBA 11/2026 ".center(80, "="))
    print("=" * 80)

    # 1. Cargar contactos
    with open(PARTNERS_FILE, 'r', encoding='utf-8') as f:
        partners = json.load(f)
    print(f"[*] Total contactos Odoo cargados: {len(partners):,}")
    cuit_map = {p['vat']: p for p in partners}

    # 2. Buscar en Retenciones
    print("\n[*] Procesando Retenciones ARBA (PadronRGSRet112026.TXT)...")
    t0 = time.time()
    ret_found = {} # cuit -> {aliquot_orig, aliquot_final, grupo, tipo_contrib}
    
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        with zf.open("PadronRGS112026/PadronRGSRet112026.TXT") as f:
            for line_bytes in f:
                line = line_bytes.decode('latin1', errors='replace').rstrip('\r\n')
                if not line:
                    continue
                parts = line.split(';')
                if len(parts) >= 9:
                    cuit = parts[4]
                    if cuit in cuit_map:
                        try:
                            ali_orig = float(parts[8].replace(',', '.'))
                        except ValueError:
                            ali_orig = 0.0
                        
                        # Regla Droguerías (RN 42/12): si corresponde retención (>0) y es < 2.50%, mínimo 2.50%
                        if 0.0 < ali_orig < 2.50:
                            ali_final = 2.50
                            rule_applied = True
                        else:
                            ali_final = ali_orig
                            rule_applied = False

                        ret_found[cuit] = {
                            'ali_orig': ali_orig,
                            'ali_final': ali_final,
                            'rule_applied': rule_applied,
                            'grupo': parts[9] if len(parts) > 9 else '',
                            'tipo_contrib': parts[5],
                            'desde': parts[2],
                            'hasta': parts[3],
                        }
    t1 = time.time()
    print(f"    - Tiempo de búsqueda en Retenciones: {t1 - t0:.2f}s")
    print(f"    - Contactos encontrados en padrón de Retenciones: {len(ret_found):,} / {len(partners):,}")

    # 3. Buscar en Percepciones
    print("\n[*] Procesando Percepciones ARBA (PadronRGSPer112026.txt)...")
    t0 = time.time()
    per_found = {} # cuit -> {aliquot_orig, aliquot_final, grupo, tipo_contrib}
    
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        with zf.open("PadronRGS112026/PadronRGSPer112026.txt") as f:
            for line_bytes in f:
                line = line_bytes.decode('latin1', errors='replace').rstrip('\r\n')
                if not line:
                    continue
                parts = line.split(';')
                if len(parts) >= 9:
                    cuit = parts[4]
                    if cuit in cuit_map:
                        try:
                            ali_orig = float(parts[8].replace(',', '.'))
                        except ValueError:
                            ali_orig = 0.0

                        per_found[cuit] = {
                            'ali_orig': ali_orig,
                            'ali_final': ali_orig, # En percepciones no hay alícuotas intermedias
                            'grupo': parts[9] if len(parts) > 9 else '',
                            'tipo_contrib': parts[5],
                            'desde': parts[2],
                            'hasta': parts[3],
                        }
    t1 = time.time()
    print(f"    - Tiempo de búsqueda en Percepciones: {t1 - t0:.2f}s")
    print(f"    - Contactos encontrados en padrón de Percepciones: {len(per_found):,} / {len(partners):,}")

    # 4. Estadísticas combinadas
    print("\n" + "=" * 80)
    print(" ANÁLISIS DE RESULTADOS PARA ODOO ".center(80, "="))
    print("=" * 80)

    ret_with_ali = {c: d for c, d in ret_found.items() if d['ali_final'] > 0}
    ret_zero = {c: d for c, d in ret_found.items() if d['ali_final'] == 0}
    ret_modified = {c: d for c, d in ret_found.items() if d['rule_applied']}

    per_with_ali = {c: d for c, d in per_found.items() if d['ali_final'] > 0}
    per_zero = {c: d for c, d in per_found.items() if d['ali_final'] == 0}

    print(f"\n[*] RETENCIONES (Proveedores / Pagos):")
    print(f"    - Encontrados en Padrón:               {len(ret_found):,}")
    print(f"    - Alícuota > 0% (Pasibles de retención): {len(ret_with_ali):,}")
    print(f"    - Alícuota = 0% (Exentos / No retención): {len(ret_zero):,}")
    print(f"    - Modificados por Regla Droguerías:     {len(ret_modified):,} (elevados a 2.50%)")
    print(f"    - No encontrados en padrón:              {len(partners) - len(ret_found):,}")

    print(f"\n[*] PERCEPCIONES (Clientes / Facturas de Venta):")
    print(f"    - Encontrados en Padrón:               {len(per_found):,}")
    print(f"    - Alícuota > 0% (Pasibles de percepción): {len(per_with_ali):,}")
    print(f"    - Alícuota = 0% (Exentos / No percepción): {len(per_zero):,}")
    print(f"    - No encontrados en padrón:              {len(partners) - len(per_found):,}")

    # Distribución de alícuotas finales en Retenciones
    from collections import Counter
    ret_dist = Counter(d['ali_final'] for d in ret_found.values())
    print("\n[*] Distribución de Alícuotas Finales de Retención en Contactos Odoo:")
    for ali, cnt in sorted(ret_dist.items()):
        print(f"    - {ali:>5.2f}% : {cnt:4d} contactos")

    per_dist = Counter(d['ali_final'] for d in per_found.values())
    print("\n[*] Distribución de Alícuotas Finales de Percepción en Contactos Odoo:")
    for ali, cnt in sorted(per_dist.items()):
        print(f"    - {ali:>5.2f}% : {cnt:4d} contactos")

    # Muestra de contactos con regla aplicada (elevados a 2.50%)
    if ret_modified:
        print("\n[*] Muestra de Contactos afectados por Regla Droguerías (Padrón < 2.50% -> Pasan a 2.50%):")
        for i, (cuit, d) in enumerate(list(ret_modified.items())[:10], 1):
            p = cuit_map[cuit]
            print(f"    {i:2d}. [{p['id']}] {p['name']:<40} | CUIT: {cuit} | Orig: {d['ali_orig']:.2f}% -> Final: {d['ali_final']:.2f}%")

    # Guardar resultado consolidado
    matched_results = []
    for p in partners:
        cuit = p['vat']
        r = ret_found.get(cuit)
        pe = per_found.get(cuit)
        matched_results.append({
            'partner_id': p['id'],
            'name': p['name'],
            'vat': cuit,
            'customer_rank': p['customer_rank'],
            'supplier_rank': p['supplier_rank'],
            'retencion': r,
            'percepcion': pe
        })

    with open('matched_partners_padron.json', 'w', encoding='utf-8') as f:
        json.dump(matched_results, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Datos consolidados guardados en 'matched_partners_padron.json'.")

if __name__ == "__main__":
    match_partners()
