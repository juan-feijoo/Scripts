# Procedimiento de Despliegue en Producción: Embalajes y Presentaciones de Compra (KP-12)

**Entorno:** Odoo.sh (Odoo 19.0 Enterprise)  
**Proyecto:** Kiddie Distribuciones  
**Tarea:** KP-12 - Carga de embalajes de venta y presentaciones de compra

---

## 1. Alcance de los Cambios (Core de Odoo 19)

1. **Embalajes de Productos (`product.template.uom_ids`)**:
   - Se vinculan **2.903 productos** a sus respectivas unidades comerciales de embalaje en `uom.uom` (60 tamaños únicos: ej. *Bulto x 10*, *Bulto x 12*, *Caja x 48*, etc.).
   - Impacto visible: En la pestaña **Ventas** del producto, campo **Embalajes**.
2. **Unidad de Medida de Compra (`product.supplierinfo.product_uom_id`)**:
   - Se actualizan **961 productos** (962 líneas de proveedor) que tienen `uni_compra > 1`.
   - Impacto visible: En la pestaña **Compras** del producto, tabla de proveedores, columna **Unidad** cambia de `Unidades` a `Bulto x {uni_compra}` (ej. *Bulto x 10* para repuestos Ledesma).

---

## 2. Paso a Paso para Producción

### Paso 1: Verificar el Entorno
Abrir la terminal del build de **Producción** en Odoo.sh y verificar el prompt:
```bash
whoami; hostname; echo "PGDATABASE=$PGDATABASE"
```
> El prompt debe mostrar `[production/19.0]` y `$PGDATABASE` debe apuntar a la base productiva.

---

### Paso 2: Instalar los Scripts en Producción
Copiar y pegar en la terminal de Odoo.sh el contenido íntegro del archivo local:
[`instalar_en_sh.sh`](file:///c:/Users/juanf/Documents/Scripts/Kiddie/KP-12/instalar_en_sh.sh)

> **Nota:** El instalador es 100% autocontenido. Limpia scripts previos y descomprime toda la matriz de datos en memoria (no requiere subir archivos JSON manualmente).

---

### Paso 3: Simulación de Seguridad (DRY-RUN en Producción)
Antes de persistir cualquier cambio, correr la simulación obligatoria:

```bash
cd ~/tmp/KP-12 && DRY_RUN=1 bash run_all.sh
```

**Verificación esperada en el log:**
- `01_cargar_embalajes_core_19`:
  - `Productos encontrados: 2903 de 2903`
  - `Errores: 0`
  - `[DRY-RUN] Se ejecutó ROLLBACK`
- `02_actualizar_uom_proveedor`:
  - `Productos encontrados: 961 de 961`
  - `Lineas proveedor actualizadas: 962`
  - `Errores: 0`
  - `[DRY-RUN] Se ejecutó ROLLBACK`

---

### Paso 4: Ejecución Definitiva (COMMIT)
Una vez validados los números de la simulación, ejecutar la carga definitiva:

```bash
cd ~/tmp/KP-12 && DRY_RUN=0 bash run_all.sh
```

O si se prefiere ejecutar de forma granular script por script:

```bash
cd ~/tmp/KP-12

# 1. Cargar embalajes en productos (Ventas / Stock)
DRY_RUN=0 odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < scripts/01_cargar_embalajes_core_19.py

# 2. Actualizar unidades de compra en proveedores (Compras)
DRY_RUN=0 odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < scripts/02_actualizar_uom_proveedor.py
```

> **Mensaje de cierre esperado:**  
> `>>>>>>>>>>>> [PRODUCCIÓN] Se ejecutó COMMIT. Embalajes guardados en Odoo core con éxito! <<<<<<<<<<<<`

---

### Paso 5: Prueba de Humo en Interfaz Web (Smoke Test)

Revisar dos productos testigo en Odoo Web:

1. **Producto con Presentación Dual:**  
   - Código: `[1051] BLOCKL PEG ANOTADOR ÉXITO 48H RY 48U`
   - Pestaña **Ventas**: Debe mostrar en *Embalajes* las etiquetas `Caja x 48` y `Bulto x 8`.
   - Pestaña **Compras**: Proveedor Ledesma con Unidad `Bulto x 48`.

2. **Producto con Bulto Estándar:**  
   - Código: `[37303] "OFERTA" REPUESTO EXITO A4 MARGEN REF 192 HJ - CUAD`
   - Pestaña **Ventas**: Debe mostrar en *Embalajes* la etiqueta `Bulto x 10`.
   - Pestaña **Compras**: Proveedor Ledesma con Unidad `Bulto x 10`.

---

### Paso 6: Limpieza (Opcional)
Una vez verificado el funcionamiento en producción:
```bash
rm -rf ~/tmp/KP-12
```
