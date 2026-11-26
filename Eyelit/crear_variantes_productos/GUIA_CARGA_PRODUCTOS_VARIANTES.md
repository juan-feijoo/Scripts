# Guía Rápida: Cómo Cargar Productos y Variantes en Odoo 18 (Eyelit)

---

## Caso A: Crear un producto nuevo con variantes

### 1. Datos generales del producto
1. Ir a **Inventario > Productos > Productos** (o **Punto de Venta > Productos > Productos**) y hacer clic en **Nuevo**.
2. Completar la pestaña **Información general**:
   - **Nombre**: Nombre del modelo + línea entre paréntesis, ej. `Boxer alg. lycra (P0A)`.
   - **Tipo de producto**: `Bienes` con **[✓] Rastrear inventario** tildado.
   - **Precio de venta**: dejar en **`$ 1,00`** *(los precios reales se cargan en las Listas de precios)*.
   - **Costo**: costo unitario base (se puede ajustar luego por variante).
   - **Categoría**: elegir la categoría interna (ej. `Ropa Interior / Boxers`, `Ropa Interior / Slips`, etc.).
   - **Impuesto de ventas / compras**: igual al resto del catálogo (si corresponde, dejar vacío o el IVA habitual).
3. En la pestaña **Punto de Venta**:
   - Tildar **[✓] Disponible en el TPV**.
   - Seleccionar la **Categoría** de TPV correspondiente (`Boxers`, `Slips`, `Femenina`, `Camisetas y Remeras`, `Medias`, `Pantalones`, `Pijamas` u `Otros`).

### 2. Cargar Atributos (Talle y Color)
1. Ir a la pestaña **Atributos y variantes** y hacer clic en **Agregar una línea**:
   - Línea 1 — **Atributo**: `Talle` | **Valores**: seleccionar todos los talles disponibles (`S`, `M`, `L`, `XL`, etc.).
   - Línea 2 — **Atributo**: `Color` | **Valores**: seleccionar los códigos de color (`05`, `24`, `83`, `90`, etc.).
2. **Guardar**. Odoo generará automáticamente todas las combinaciones (`Talle × Color`).

### 3. Cargar Códigos de Barra y Referencias por Variante
1. Hacer clic en el botón inteligente superior **Variantes** (o ir a **Productos > Variantes de producto** y buscar el artículo).
2. Abrir cada variante que exista comercialmente y completar:
   - **Referencia interna**: código Eyelit exacto (ej. `0329P0A83.002`).
   - **Código de barras**: el mismo código exacto (ej. `0329P0A83.002`) para que el lector en el POS identifique esa variante al instante.
   - **Costo**: costo específico si difiere del base.
3. Si alguna combinación de la matriz **no existe** (ej. un color que no viene en talle `XXL`), abrirla y elegir **Acción (⚙) > Archivar** para ocultarla del POS.

### 4. Cargar Precios en las Listas de Precios
1. Desde la ficha del producto, hacer clic en el botón inteligente **Listas de precios / Precios extra** (o ir a **Ventas / Punto de Venta > Productos > Listas de precios**).
2. En cada lista activa del POS (por ej. **Lista Efectivo-QR-Transferencia...** y **Lista de Precios con Variantes**), agregar una regla por cada variante (o por producto si todos los talles valen lo mismo):
   - **Aplicar en**: `Variante de producto` (si varía por talle/color) o `Producto` (si toda la familia tiene el mismo precio).
   - **Producto**: la plantilla creada.
   - **Variante**: la variante puntual (si eligió `Variante de producto`).
   - **Precio fijo**: ingresar el precio real de venta (IVA incluido).
3. **Guardar**.

### 5. Cargar Stock Inicial (si tiene existencias)
1. Abrir la variante (o desde **Inventario > Operaciones > Inventario físico**).
2. Hacer clic en **Actualizar cantidad** (o **A mano**) -> **Nuevo**, seleccionar ubicación `WH/Existencias`, cargar la **Cantidad contada** y hacer clic en **Aplicar**.

---

## Caso B: Agregar un talle o color nuevo a un producto ya existente

1. Abrir la plantilla del producto en **Productos > Productos**.
2. Ir a la pestaña **Atributos y variantes** y agregar el nuevo valor en la línea de `Talle` o `Color`.
3. **Guardar** *(Odoo crea automáticamente solo las variantes nuevas sin tocar las anteriores ni su stock)*.
4. Entrar al botón inteligente **Variantes**, asignar **Referencia interna** y **Código de barras** a las variantes nuevas (y archivar las combinaciones que no existan).
5. Agregar su regla de precio en las **Listas de precios** activas del POS y cargar su stock si corresponde.

---

## Checklist rápido antes de vender en el POS
- [ ] `[✓] Disponible en el TPV` y **Categoría TPV** asignada.
- [ ] **Referencia interna** y **Código de barras** cargados en cada variante activa.
- [ ] **Precio fijo** cargado en las listas de precios que usa la caja.
- [ ] Si la caja ya estaba abierta, presionar **`Ctrl + F5`** (o recargar datos en el POS) y escanear la etiqueta para comprobar precio y variante.
