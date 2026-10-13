# Auditoría y posiciones fiscales de Sabra

Scripts para revisar impuestos y preparar posiciones fiscales de IIBB y retención
de Ganancias en la localización argentina de Odoo. Están pensados para ejecutarse
en Odoo.sh desde `odoo-bin shell`.

## Auditoría de solo lectura

```bash
python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < auditoria_impuestos_posiciones_fiscales.py
```

Lista los impuestos de la compañía (incluidos archivados y compartidos), grupos,
alícuotas, posiciones fiscales y reglas de localización. También resume contactos
sin posición fiscal o responsabilidad AFIP. No escribe en la base de datos.

## Diagnóstico detallado antes de configurar

```bash
python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < diagnostico_impuestos_posiciones_fiscales.py
```

Úsalo si hay que confirmar qué módulo/campos fiscales ofrece la base y distinguir
impuestos activos de archivados, percepciones, retenciones, grupos y cuentas/
etiquetas contables. Es estrictamente de solo lectura y no modifica registros.
Comparte su salida antes de habilitar cualquier cambio del configurador.

## Planificar posiciones fiscales (solo lectura)

Después de la auditoría detallada, ejecuta el planificador:

```bash
python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < planificar_posiciones_fiscales_sabra.py
```

Agrupa retenciones IIBB activas por código provincial y Ganancias por cada
impuesto/régimen que Odoo identifica como `earnings` o `earnings_scale`. Presenta
las posiciones sugeridas y avisa si hay tasas duplicadas, jurisdicciones sin
código reconocido o posiciones coincidentes. Omite tasas IIBB cero/negativas.
Es un plan estrictamente de solo lectura: no crea posiciones ni reglas, no cambia
contactos y no depende de `rollback()`.

El configurador `crear_posiciones_retenciones_sabra.py` implementa ese plan
usando los impuestos activos identificados por código provincial y por
`l10n_ar_tax_type`. Su valor inicial es `DRY_RUN = True`: simula la creación o
actualización de posiciones y reglas especializadas `l10n_ar_tax_ids` y luego
revierte la transacción. No altera los mapeos genéricos `tax_ids`, impuestos ni
contactos. Verifica con el planificador primero; solo cambia `DRY_RUN = False`
después de revisar toda la simulación y confirmar que la compañía/base de datos
son las correctas.

```bash
python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < crear_posiciones_retenciones_sabra.py
```

Para la primera ejecución, deja `DRY_RUN = True` y revisa que reporte las
24 posiciones candidatas de IIBB y las 29 de Ganancias esperadas.

No ejecutes `implementar_posiciones_fiscales_iibb_ganancias.py` en esta base:
fue preparado antes del diagnóstico detallado y busca percepciones de IIBB en
ventas y nombres españoles para Ganancias, distintos de los impuestos observados.

La asignación de impuestos de IIBB o Ganancias a contactos queda fuera de este
plan. Depende de jurisdicción, régimen, padrón y situación fiscal de cada
contacto; los criterios deben confirmarse antes de automatizarla.

## Contexto recuperado de commits anteriores

Los scripts existentes en `Beton` documentan estos modelos y campos de Odoo 19:

- `account.fiscal.position.l10n_ar_tax` con tipos `perception` y `withholding`,
  campos `tax_group_id`, `default_tax_id` y `aliquot`.
- El campo `l10n_ar_tax_type` de `account.fiscal.position` para clasificar posiciones de
  percepción y retención.
- `res.partner.l10n_ar_afip_responsibility_type_id` para la condición AFIP del
  contacto; los códigos 1 y 5 se usan para Responsable Inscripto y Consumidor
  Final, respectivamente.

Las configuraciones de empresa e ID de `Beton` no se copian: estos scripts usan
la compañía activa de Odoo por defecto. Se puede indicar un `COMPANY_ID` al
inicio de cada archivo.
