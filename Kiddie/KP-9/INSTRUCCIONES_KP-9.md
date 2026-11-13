# Procedimiento Técnico y Despliegue: Lista de Precios por Línea en OV (KP-9)

**Proyecto:** Kiddie Distribuciones  
**Entorno:** Odoo.sh (Odoo 19.0 Enterprise)  
**Ticket:** [KP-9](https://odoonoa.atlassian.net/browse/KP-9) - Agregar lista de precios por línea en OV  
**Módulo:** [`odoo-mod-sale-line-pricelist/sale_line_pricelist`](file:///c:/Users/juanf/Documents/Scripts/Kiddie/KP-9/odoo-mod-sale-line-pricelist/sale_line_pricelist)

---

## 1. Investigación de Repositorios Existentes

Antes de escribir código custom se revisaron las fuentes públicas y el repositorio del proyecto:
- **OCA (`OCA/sale-workflow` 19.0) e Ingadhoc (`ingadhoc/sale`):** Ningún módulo permite seleccionar una `product.pricelist` independiente por `sale.order.line` (solo hay trazabilidad con `sale_order_line_price_source`, selección por tipo de pedido a nivel cabecera con `sale_order_type`, recálculo con `sale_order_price_recalculation` o categoría de producto).
- **Copia local del cliente (`sale-workflow-19.0`, relevada en [`listas_precio_por_linea.zip`](file:///c:/Users/juanf/Documents/Scripts/Kiddie/KP-9/listas_precio_por_linea.zip)):** Es una copia estándar de 92 módulos OCA 19.0 sin módulos extra instalados ni overrides sobre `sale.order.line`.
- **Odoo Apps Store / otros repositorios:** Solo existen módulos pagos de terceros (*Multi Pricelist per Order Line*, *Sale Order Multiple Pricelist*) o selectores de tipo de precio distintos (`franck-prelium/odoo-sale-price-selector`, `Mint-System/sale_order_line_pricelist_fixed_discount`).

---

## 2. Arquitectura del Módulo `sale_line_pricelist` (Odoo 19.0)

* **`hooks.py` (`pre_init_hook`):**
  * Crea e inicializa `pricelist_follows_order` y `pricelist_id` en SQL al instalar para evitar que el ORM recalcule o altere precios en pedidos existentes/confirmados.
* **`models/sale_order_line.py`:**
  * Campos `pricelist_id` (`store=True`, `readonly=False`, `precompute=True`, `check_company=True`, `index="btree_not_null"`) y `pricelist_follows_order` (`default=True`).
  * **Comportamiento de herencia y cambio de lista:**
    - Al agregar una línea nueva sigue la lista de cabecera (`pricelist_follows_order=True`).
    - Al elegir una lista distinta en la línea (UI `@api.onchange` o backend `write()`), desactiva `pricelist_follows_order`, fuerza el recálculo (`force_price_recomputation=True` en contexto, venciendo la traba de `technical_price_unit` si hubo edición manual previa) y recalcula `pricelist_item_id`, `price_unit` y `discount`.
    - Si el usuario borra la lista de la línea en la UI (`False`), restablece la de cabecera y reactiva `pricelist_follows_order=True`.
    - Al cambiar la lista de cabecera, las líneas que siguen al pedido se actualizan y las líneas personalizadas conservan su lista.
  * **Multimoneda (ARS / USD):**
    - Usa `_get_pricelist_kwargs()` (evaluando reglas en la moneda de la lista de la línea) y `_convert_to_sol_currency()` en `_get_pricelist_price()` y `_get_pricelist_price_before_discount()`. Esto evita que `product.pricelist.item._compute_price` mezcle monedas en precios fijos o recargos.
* **`views/sale_order_views.xml`:**
  * Inserta `pricelist_id` antes de `price_unit` en `<list>` y `<form>` de `order_line` (sin `attrs` ni `states`, `readonly="qty_invoiced > 0 or parent.state in ['sale', 'cancel']"`).
  * **Nota importante sobre visibilidad:** En el relevamiento de staging se detectó que `product.group_product_pricelist` tenía 0 usuarios. Por eso la vista no restringe la columna por ese grupo (usa `optional="show"`). De igual modo, conviene validar en *Ajustes → Ventas → Precios* que las listas de precios estén habilitadas para los vendedores.
* **`tests/test_sale_line_pricelist.py`:**
  * 7 casos de prueba sobre `SaleCommon`: fórmulas sobre costo, escalas por cantidad, pedidos ARS con líneas USD, precios fijos en moneda extranjera, cambios de cabecera, override manual + onchange/write y botón *Actualizar precios*.

---

## 3. Verificación y Despliegue en Odoo.sh

### Paso 1 (Opcional - Solo Lectura): Auditar el build actual antes del deploy
```bash
odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < scripts/01_auditar_entorno_sale_19.py
```

### Paso 2: Subir el módulo al repositorio de Odoo.sh
1. Copiar `sale_line_pricelist/` al repositorio custom del proyecto (o agregar `odoo-mod-sale-line-pricelist` como submódulo en la rama `19.0` / staging).
2. Hacer `push` a **Staging** en Odoo.sh.
3. Instalar el módulo **`sale_line_pricelist`** (`Lista de Precios por Línea en Ventas`).

### Paso 3: Ejecutar los tests automatizados en Staging
```bash
odoo-bin -d $PGDATABASE --test-tags /sale_line_pricelist --stop-after-init --no-http
```

### Paso 4: Prueba funcional en Staging (Smoke Test)
1. Crear Cotización con lista de cabecera `Público (ARS)`.
2. **Línea 1:** Marcador `[38552]` -> toma `Público (ARS)`.
3. **Línea 2:** Mismo artículo, cambiar `Lista de precios` a `Mayorista (ARS)` -> recalcula al instante.
4. **Línea 3:** Cambiar `Lista de precios` a `Desglose - Venta por Unidad (ARS)` -> aplica el margen de desglose.
5. **Línea 4:** Seleccionar una lista en USD (`Lista en Dólares`) dentro del pedido en ARS -> verifica la conversión a la cotización de la fecha del pedido.
6. Editar `price_unit` manualmente en Línea 1 y cambiar cantidad -> confirma que protege el precio manual; luego cambiar la lista de Línea 1 -> confirma que recalcula.
7. Confirmar y facturar -> validar que los importes e impuestos (`IVA` + `IB Salta 1,4%`) pasen intactos a `account.move.line`.
