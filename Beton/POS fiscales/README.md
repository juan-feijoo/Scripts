# Auditoría y Configuración: Impuestos (Percepciones), Posiciones Fiscales y Contactos

**Entorno:** Odoo.sh (Enterprise 17.0+e / 18.0+e / 19.0+e)  
**Localización:** Argentina (`l10n_ar`)  
**Directorio:** `C:\Users\juanf\Documents\Scripts\Beton`

---

## 1. Contenido del Directorio

1. **[implementar_posiciones_fiscales_iibb_odoo19.py](file:///C:/Users/juanf/Documents/Scripts/Beton/implementar_posiciones_fiscales_iibb_odoo19.py)**:
   - Script para Percepciones de IIBB en Odoo 19.
   - Configura las Posiciones Fiscales de IIBB con el modelo `account.fiscal.position.l10n_ar_tax`.
   - Ajusta `l10n_ar_tax_type = 'perception'`, limpia auto-reemplazos en `account.tax` y enlaza posiciones base (RI / Consumidor Final).
   - Soporte **DRY-RUN** estricto (`DRY_RUN = True`).

2. **[implementar_posiciones_fiscales_retenciones_odoo19.py](file:///C:/Users/juanf/Documents/Scripts/Beton/implementar_posiciones_fiscales_retenciones_odoo19.py)**:
   - Script para Retenciones (Withholdings) a Proveedores en Odoo 19.
   - Crea y configura las Posiciones Fiscales de Retención por Jurisdicción (Salta, Jujuy, Tucumán, CABA, PBA, etc.) y Nacionales (Ganancias/IVA).
   - Configura `l10n_ar_tax_type = 'withholding'` y crea la posición unificada 'Retenciones Proveedores'.
   - Soporte **DRY-RUN** estricto (`DRY_RUN = True`).

3. **[configurar_posiciones_fiscales_odoo19.py](file:///C:/Users/juanf/Documents/Scripts/Beton/configurar_posiciones_fiscales_odoo19.py)**:
   - Script de diagnóstico técnico de metadata y campos nuevos en Odoo 19 (`l10n_ar_tax_type`, `l10n_ar_tax_ids`, `is_domestic`).

4. **[resolver_ticket_percepciones_posiciones.py](file:///C:/Users/juanf/Documents/Scripts/Beton/resolver_ticket_percepciones_posiciones.py)**:
   - Crea los impuestos de percepción en ventas para las 24 jurisdicciones provinciales a partir de los impuestos de compras.

5. **[auditoria_impuestos_posiciones_fiscales.py](file:///C:/Users/juanf/Documents/Scripts/Beton/auditoria_impuestos_posiciones_fiscales.py)**:
   - Auditoría general de módulos, impuestos, posiciones fiscales y contactos.

6. **[diagnostico_contactos_impuestos.sql](file:///C:/Users/juanf/Documents/Scripts/Beton/diagnostico_contactos_impuestos.sql)**:
   - Consultas SQL para `psql` compatibles con Odoo 17, 18 y 19.

---

## 2. Instrucciones de Ejecución en Odoo.sh

### Opción A: Ejecución en Shell no interactiva (Recomendado para reporte)
```bash
python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < auditoria_impuestos_posiciones_fiscales.py
```

### Opción B: Ejecución en Shell interactiva
```bash
python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE
```
Dentro de la consola de Python:
```python
>>> exec(open('auditoria_impuestos_posiciones_fiscales.py').read())
```

---

## 3. Flags de Configuración en el Script

En el archivo `auditoria_impuestos_posiciones_fiscales.py`:

```python
DRY_RUN = True                # True: Simula y ejecuta rollback. False: Aplica commit a la BD.
COMPANY_ID = None             # None = Compañía actual de env, o ID específico.
AUTO_FIX_PARTNERS = False     # True: Corrige la posición fiscal de contactos según su Resp. AFIP.
AUTO_CREATE_TAXES = False     # True: Crea los impuestos de percepción estándar si faltan.
AUTO_LINK_FISCAL_POS = False  # True: Asocia responsabilidades AFIP a posiciones fiscales si no están vinculadas.
```

---

## 4. Consideraciones Clave para Odoo 17 / 18 / 19 (Enterprise)

- **Vistas XML:** No utilizar `attrs` ni `states`. En Odoo 17+, las condiciones se declaran directamente con expresiones de Python en los atributos:
  ```xml
  <!-- Correcto en v17/v18/v19 -->
  <field name="property_account_position_id" invisible="not l10n_ar_afip_responsibility_type_id"/>
  ```
- **Posición Fiscal Automática:** En Odoo Enterprise con `l10n_ar`, al asignar la Responsabilidad AFIP (`l10n_ar_afip_responsibility_type_id`), Odoo calcula la Posición Fiscal sugerida mediante la regla de mapeo en `account.fiscal.position`.
- **Percepciones:** Si se requiere cálculo automático por padrón mensual (ARBA/AGIP), se recomienda verificar si la empresa utiliza importación de padrones o alícuota fija en el contacto.
