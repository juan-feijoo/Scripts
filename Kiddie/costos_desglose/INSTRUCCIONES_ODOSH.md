# KP-13: Normalización de Costos y Listas de Precio para Productos con Desglose

## 1. Diagnóstico del Problema y Causa Raíz

En Odoo 19 Enterprise (Odoo.sh), para los **969 productos** que en el sistema anterior tenían `desglose == 1` (por ejemplo, `[37324] GOMA LAPIZ RAL40 - EZCO` con `uni_bulto = 40`):

1. **Causa Raíz:** En la migración inicial, el campo `standard_price` (Costo) se pobló con `costoreal` (el costo de la **caja/bulto completo de 40 unidades**: `$4.437,785`), pero la UdM base del producto se definió en `Unidades`.
2. **Impacto en Ventas:**
   - Odoo asume que **1 unidad** cuesta `$4.437,785`.
   - En la lista `Público` (+85% de margen): Odoo calcula `$4.437,785 * 1.85 = $8.209,90`. Por eso, al cotizar **1 sola goma**, el sistema cobraba `$8.209,90`.
   - Al cotizar **1 Bulto x 40**, como la UdM `Bulto x 40` tiene factor relativo 40 sobre la unidad base, Odoo multiplicaba el precio unitario por 40: `$8.209,90 * 40 = $328.396,00`.
3. **¿Por qué NO se debe cambiar la UdM base (`uom_id`) a Paquete/Bulto?**
   - En la arquitectura estándar de Odoo, la unidad base (`uom_id`) debe ser siempre la menor unidad discreta indivisible inventariable (`Unidades`).
   - Si se cambia la unidad base a "Paquete por 12" o "Bulto x 40", Odoo bloquea o dificulta vender fracciones (unidades sueltas), arruina los movimientos de inventario y genera descuadres en el stock.

---

## 2. La Solución Estándar Odoo Core + `sale_line_pricelist`

Con los scripts de esta carpeta, el circuito queda 100% estándar e integrado:

| Nivel | Configuración Odoo | Caso Ejemplo `[37324]` |
| :--- | :--- | :--- |
| **UdM Base (`uom_id`)** | Siempre `Unidades` | `Unidades` |
| **Costo Base (`standard_price`)** | Normalizado a unidad: `costoreal / uni_bulto` | `$4.437,785 / 40 = $110,9446` |
| **UdM Embalaje (`uom_ids`)** | `Bulto x {uni_bulto}` (factor 40) | `Bulto x 40` |
| **Proveedor (`product.supplierinfo`)** | UdM: `Bulto x 40` \| Precio: `$4.437,79` | Se compra la caja a precio de bulto |
| **Venta 1 Bulto Cerrado (`Público`)** | UdM `Bulto x 40` \| Lista `Público` | `$110,9446 * 1.85 * 40 = $8.209,90` |
| **Venta 1 Bulto Cerrado (`Mayorista`)** | UdM `Bulto x 40` \| Lista `Mayorista` | `$110,9446 * 1.30 * 40 = $5.769,12` |
| **Venta 1 Unidad Suelta (`Desglose`)** | UdM `Unidades` \| Lista `Desglose` | `$110,9446 * (1 + 100%) = $221,89` |
| **Venta 1 Unidad Suelta (`Público`)** | UdM `Unidades` \| Lista `Público` | `$110,9446 * 1.85 = $205,25` |

---

## 3. Estructura de la Carpeta `KP-13_costos_desglose`

- **`instalar_en_sh.sh`**: Instalador pegable en un solo paso para Odoo.sh.
- **`run_all.sh`**: Ejecutor por lotes que corre cada script en `odoo-bin shell`, captura los resultados en `.txt` y genera un archivo `.zip`.
- **`scripts/_lib.py`**: Helpers de entorno, formato y diagnóstico seguro.
- **`scripts/01_diagnostico_costos_y_listas.py`**: Releva el estado actual de los 969 productos y muestra la comparativa actual vs esperada (solo lectura).
- **`scripts/02_corregir_costos_y_proveedores_desglose.py`**: Normaliza `standard_price = costoreal / uni_bulto` y actualiza `product.supplierinfo` a UdM Bulto y precio bulto. (Soporta `DRY_RUN=1` y `DRY_RUN=0`).
- **`scripts/03_actualizar_reglas_desglose.py`**: Actualiza las reglas de `Desglose - Venta por Unidad (ARS)` aplicando `margen7` directamente sobre el costo unitario normalizado. (Soporta `DRY_RUN=1` y `DRY_RUN=0`).
- **`scripts/04_simulacion_venta_y_verificacion.py`**: Simula cotizaciones de venta y órdenes de compra para productos testigo y muestra la tabla comparativa con estados `[OK]` (solo lectura).

---

## 4. Paso a Paso de Ejecución en Odoo.sh

### PASO 1: Probar primero en STAGING

1. Entrar al terminal web de Odoo.sh de **Staging** (`outsource-argentina-kiddie-staging-41062173`).
2. Abrir en tu editor local el archivo [instalar_en_sh.sh](file:///c:/Users/juanf/Documents/Scripts/Kiddie/KP-13_costos_desglose/instalar_en_sh.sh), copiar **TODO** su contenido y pegarlo en el shell de Staging.
3. Verificar la instalación:
   ```bash
   cd ~/tmp/KP-13_costos_desglose && sed -i 's/\r$//' run_all.sh scripts/*.py && chmod +x run_all.sh && md5sum run_all.sh scripts/*.py
   ```
4. **Ejecutar en modo SIMULACIÓN (DRY-RUN, sin modificar nada):**
   ```bash
   cd ~/tmp/KP-13_costos_desglose && DRY_RUN=1 bash run_all.sh
   ```
5. Revisar que no haya errores:
   ```bash
   grep -l "Traceback\|!! ERROR" resultados_*/*.txt || echo "Sin errores"
   ```
6. **Ejecutar en modo PERSISTENTE (Aplica los cambios en Staging):**
   ```bash
   cd ~/tmp/KP-13_costos_desglose && DRY_RUN=0 bash run_all.sh
   ```
7. Probar en la interfaz web de Odoo:
   - Ir a **Ventas > Cotizaciones > Crear**.
   - Elegir cualquier cliente.
   - **Línea 1:** Producto `[37324] GOMA LAPIZ RAL40 - EZCO`, Cantidad `1.00`, Unidad `Bulto x 40`, Lista de precios `Público (ARS)`.
     - **Resultado:** Precio unitario e importe: **$ 8.209,90**.
   - **Línea 2:** Producto `[37324] GOMA LAPIZ RAL40 - EZCO`, Cantidad `1.00`, Unidad `Unidades`, Lista de precios `Desglose - Venta por Unidad (ARS)`.
     - **Resultado:** Precio unitario e importe: **$ 221,89**.

---

### PASO 2: Despliegue en PRODUCCIÓN

Una vez validado en Staging:
1. Conectarse al Shell del build de **Producción** (verificar que el prompt indique `[production/19.0]`).
2. Pegar el contenido de [instalar_en_sh.sh](file:///c:/Users/juanf/Documents/Scripts/Kiddie/KP-13_costos_desglose/instalar_en_sh.sh).
3. Correr la simulación previa:
   ```bash
   cd ~/tmp/KP-13_costos_desglose && DRY_RUN=1 bash run_all.sh
   ```
4. Aplicar definitivamente en Producción:
   ```bash
   cd ~/tmp/KP-13_costos_desglose && DRY_RUN=0 bash run_all.sh
   ```
5. Descargar el `.zip` de respaldo generado desde la pestaña **Editor** (`tmp/KP-13_costos_desglose/KP-13_costos_desglose_YYYYMMDD_HHMMSS.zip`).
