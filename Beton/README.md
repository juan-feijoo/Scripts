# Auditoría y Configuración: Impuestos (Percepciones), Posiciones Fiscales y Contactos

**Entorno:** Odoo.sh (Enterprise 17.0+e / 18.0+e / 19.0+e)  
**Localización:** Argentina (`l10n_ar`)  
**Directorio:** `C:\Users\juanf\Documents\Scripts\Beton`

---

## 1. Contenido del Directorio

1. **[auditoria_impuestos_posiciones_fiscales.py](file:///C:/Users/juanf/Documents/Scripts/Beton/auditoria_impuestos_posiciones_fiscales.py)**:
   - Script para ejecutar en `odoo-bin shell`.
   - Incluye **Modo DRY-RUN** (`DRY_RUN = True`) por defecto (ejecuta `env.cr.rollback()`).
   - Audita módulos instalados, impuestos de percepciones (IIBB CABA, ARBA, CM, IVA, Ganancias), posiciones fiscales, y contactos con inconsistencias o sin configuración.
   - Permite activar creación automática (`AUTO_CREATE_TAXES`), enlace de posiciones fiscales (`AUTO_LINK_FISCAL_POS`) y asignación masiva a contactos (`AUTO_FIX_PARTNERS`).

2. **[diagnostico_contactos_impuestos.sql](file:///C:/Users/juanf/Documents/Scripts/Beton/diagnostico_contactos_impuestos.sql)**:
   - Consultas SQL directas para ejecutar en la consola `psql` de Odoo.sh para diagnósticos rápidos de volumen y discrepancias.

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
