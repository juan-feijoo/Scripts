# -*- coding: utf-8 -*-
"""
================================================================================
AUDITORÍA LOCAL: ANÁLISIS DE PADRÓN ARBA (PadronRGS112026.zip)
================================================================================
Analiza la estructura, volumetría, fechas y distribución de alícuotas tanto
para Retenciones como para Percepciones, evaluando el impacto de la regla
de Droguerías (RN 42/12: mínimo 2.50% para retenciones activas > 0%).
================================================================================
"""

import zipfile
import sys
from collections import Counter

ZIP_PATH = "PadronRGS112026.zip"

def analyze_zip():
    print("=" * 80)
    print(" AUDITORÍA TÉCNICA DEL ARCHIVO PADRÓN ".center(80, "="))
    print("=" * 80)

    try:
        zf = zipfile.ZipFile(ZIP_PATH, 'r')
    except Exception as e:
        print(f"ERROR al abrir {ZIP_PATH}: {e}")
        return

    entries = [info for info in zf.infolist() if not info.is_dir() and info.file_size > 0]
    print(f"\n[*] Archivos encontrados en el ZIP ({len(entries)}):")
    for info in entries:
        print(f"    - {info.filename:<35} | Tamaño: {info.file_size / (1024*1024):.2f} MB (Comprimido: {info.compress_size / (1024*1024):.2f} MB)")

    for info in entries:
        fname = info.filename
        short_name = fname.split('/')[-1]
        is_ret = "ret" in short_name.lower()
        is_per = "per" in short_name.lower()
        tipo_label = "RETENCIONES" if is_ret else ("PERCEPCIONES" if is_per else "DESCONOCIDO")

        print("\n" + "-" * 80)
        print(f" PROCESANDO: {short_name} ({tipo_label}) ".center(80, "-"))
        print("-" * 80)

        total_lines = 0
        aliquot_counts = Counter()
        dates_desde = Counter()
        dates_hasta = Counter()
        contrib_types = Counter()
        
        # Conteo específico para regla de Droguerías (RN 42/12)
        count_zero = 0
        count_between_0_and_25 = 0  # > 0 and < 2.50 -> se transforman a 2.50%
        count_equal_25 = 0
        count_greater_25 = 0
        
        sample_rows = []

        with zf.open(fname) as f:
            for line_bytes in f:
                line = line_bytes.decode('latin1', errors='replace').rstrip('\r\n')
                if not line:
                    continue
                parts = line.split(';')
                total_lines += 1

                if total_lines <= 5:
                    sample_rows.append(parts)

                # Formato esperado:
                # 0: Tipo (P/R)
                # 1: Fecha Publicacion (DDMMAAAA)
                # 2: Fecha Desde (DDMMAAAA)
                # 3: Fecha Hasta (DDMMAAAA)
                # 4: CUIT (11 digitos)
                # 5: Tipo Contribuyente (D/C)
                # 6: Marca Alta/Baja
                # 7: Marca Cambio
                # 8: Alicuota (ej. '2,50')
                # 9: Grupo
                if len(parts) >= 9:
                    f_desde = parts[2]
                    f_hasta = parts[3]
                    tipo_c = parts[5]
                    ali_str = parts[8].strip().replace(',', '.')
                    
                    dates_desde[f_desde] += 1
                    dates_hasta[f_hasta] += 1
                    contrib_types[tipo_c] += 1

                    try:
                        ali_val = float(ali_str)
                    except ValueError:
                        ali_val = -1.0

                    aliquot_counts[ali_str] += 1

                    if ali_val == 0.0:
                        count_zero += 1
                    elif 0.0 < ali_val < 2.50:
                        count_between_0_and_25 += 1
                    elif ali_val == 2.50:
                        count_equal_25 += 1
                    elif ali_val > 2.50:
                        count_greater_25 += 1

        print(f"[*] Total registros: {total_lines:,}")
        print(f"[*] Rango de Vigencia:")
        for d, c in dates_desde.most_common(2):
            print(f"    - Desde: {d} ({c:,} registros)")
        for d, c in dates_hasta.most_common(2):
            print(f"    - Hasta: {d} ({c:,} registros)")

        print(f"[*] Tipo de Contribuyente:")
        for t, c in contrib_types.items():
            print(f"    - Tipo '{t}': {c:,} ({c/total_lines*100:.1f}%)")

        print(f"\n[*] Distribución de Alícuotas frente a Regla Droguerías (RN 42/12):")
        print(f"    - Alícuota = 0,00% (Sin retención / No pasible):    {count_zero:,} ({count_zero/total_lines*100:.2f}%)")
        print(f"    - 0 < Alícuota < 2,50% (MODIFICADOS A 2,50%):       {count_between_0_and_25:,} ({count_between_0_and_25/total_lines*100:.2f}%)")
        print(f"    - Alícuota = 2,50% (Ya están en 2,50%):             {count_equal_25:,} ({count_equal_25/total_lines*100:.2f}%)")
        print(f"    - Alícuota > 2,50% (Mantienen alícuota de padrón):  {count_greater_25:,} ({count_greater_25/total_lines*100:.2f}%)")

        print(f"\n[*] Top 10 Alícuotas más frecuentes:")
        for ali, cnt in aliquot_counts.most_common(10):
            print(f"    - {ali:>6}% : {cnt:,} ({cnt/total_lines*100:.2f}%)")

        print(f"\n[*] Primeras 3 muestras de datos brutos:")
        for i, s in enumerate(sample_rows[:3], 1):
            print(f"    [{i}] {';'.join(s)}")

    print("\n" + "=" * 80)
    print(" FIN DE AUDITORÍA LOCAL DE PADRÓN ".center(80, "="))
    print("=" * 80 + "\n")

if __name__ == "__main__":
    analyze_zip()
