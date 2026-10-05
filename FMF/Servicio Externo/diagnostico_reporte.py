# -*- coding: utf-8 -*-
"""
==============================================================================
FMF GROUP - SCRIPT DE DIAGNÓSTICO DE IMPRESIÓN Y WKHTMLTOPDF
==============================================================================
Uso en Odoo Shell:
    >>> exec(open('diagnostico_reporte.py').read())
==============================================================================
"""

import sys

def diagnosticar_impresion(env):
    print("\n" + "=" * 75)
    print("  DIAGNÓSTICO DE IMPRESIÓN Y REPORTE QWEB")
    print("=" * 75)

    # 1. Parámetros del Sistema (web.base.url / report.url)
    web_base_url = env['ir.config_parameter'].sudo().get_param('web.base.url')
    report_url = env['ir.config_parameter'].sudo().get_param('report.url')
    print(f"\n[1] PARÁMETROS DEL SISTEMA:")
    print(f"  * web.base.url: {web_base_url}")
    print(f"  * report.url:   {report_url or 'NO DEFINIDO (wkhtmltopdf usará web.base.url)'}")

    # 2. Localizar la Tarea OT
    task = env['project.task'].search([
        ('numero_ot', '=', '2215')
    ], limit=1)
    if not task:
        task = env['project.task'].search([('name', 'ilike', 'OT 2215')], limit=1)
    if not task:
        task = env['project.task'].search([], limit=1)

    print(f"\n[2] TAREA DE PRUEBA: [{task.id}] {task.name}")

    # 3. Localizar la Acción de Reporte
    report_action = env.ref('fmf_fleet_taller.action_report_ot_taller_fmf', raise_if_not_found=False)
    if not report_action:
        print("  [!] ERROR: No se encontró la acción 'fmf_fleet_taller.action_report_ot_taller_fmf'.")
        return

    print(f"  * Acción de reporte encontrada: {report_action.name} (Modelo: {report_action.model})")

    # 4. Probar Renderizado HTML (sin wkhtmltopdf)
    print("\n[3] PRUEBA 1: RENDERIZADO QWEB A HTML...")
    try:
        html_content, _ = report_action._render_qweb_html(report_action.id, [task.id])
        print(f"  [EXITO] HTML generado correctamente ({len(html_content)} bytes).")
    except Exception as e:
        print(f"  [ERROR] Falló el renderizado HTML: {e}")
        return

    # 5. Probar Renderizado PDF (con wkhtmltopdf)
    print("\n[4] PRUEBA 2: RENDERIZADO A PDF (WKHTMLTOPDF)...")
    try:
        pdf_content, _ = report_action._render_qweb_pdf(report_action.id, [task.id])
        print(f"  [EXITO] ¡PDF generado correctamente! Tamaño: {len(pdf_content)} bytes.")
        print("  * La generación de PDF funciona a nivel de servidor.")
    except Exception as e:
        print(f"  [ERROR] Falló la generación de PDF con wkhtmltopdf:")
        print(f"  {type(e).__name__}: {e}")

    print("\n" + "=" * 75 + "\n")

if 'env' in locals() or 'env' in globals():
    diagnosticar_impresion(env)
