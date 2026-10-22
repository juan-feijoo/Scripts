# LF-16: Auditoría y Configuración de Modelos de Distribución Analítica (Odoo 17/18/19 Enterprise)

Este directorio contiene la suite de scripts para auditar, crear y verificar automáticamente los **Modelos de Distribución Analítica** (`account.analytic.distribution.model`) en Odoo.sh para **La Francisca**.

---

## 📌 Contexto Técnico de la Arquitectura Analítica (Odoo 17/18/19)

A partir de Odoo 16 y consolidado en versiones 17, 18 y 19:
1. **Multi-Plan Analítico**: Las cuentas analíticas (`account.analytic.account`) se agrupan en **Planes** (`account.analytic.plan`), por ejemplo:
   - **Plan Sucursales**: Contiene las cuentas de cada sucursal (`SUCURSAL ARENALES`, `SUCURSAL RAGONE`, etc.).
   - **Plan Fábrica / Centros de Costos**: Contiene la cuenta de la fábrica (`FABRICA DE PASTAS`).
2. **Campo `analytic_distribution`**:
   - Es un campo de tipo **`fields.Json`** almacenado en PostgreSQL como JSONB.
   - **Caso 1 (Unidimensional / Una sola cuenta)**:
     ```json
     {"3": 100.0}
     ```
     *(Donde `3` es el ID de la cuenta analítica de la sucursal).*
   - **Caso 2 (Multi-Plan / Cuentas simultáneas en diferentes planes)**:
     Cuando una línea aplica al 100% en la Sucursal y al 100% en la Fábrica, Odoo serializa la fila combinando los IDs separados por coma:
     ```json
     {"3,7": 100.0}
     ```
     En la interfaz web (widget `analytic_distribution`), esto se renderiza automáticamente como una etiqueta unificada separada por barra vertical:  
     `[SUCURSAL ARENALES | FABRICA PASTAS]`.

---

## 📁 Archivos Disponibles

| Archivo | Propósito | Modo de Seguridad |
| :--- | :--- | :--- |
| [`audit_analytic_models.py`](./audit_analytic_models.py) | Audita compañías, planes, cuentas, categorías de producto y modelos analíticos existentes. | **Solo Lectura** (genera `analytic_audit_output.json`) |
| [`create_analytic_distribution_models.py`](./create_analytic_distribution_models.py) | Crea y actualiza los modelos para todas las sucursales (Regla general y Regla Pastas). | **DRY-RUN** activado por defecto (`DRY_RUN = True`) |
| [`test_analytic_simulation.py`](./test_analytic_simulation.py) | Simula una venta estándar vs venta de pastas en una factura borrador para verificar el motor contable. | **Rollback automático** |

---

## 🚀 Flujo de Trabajo Recomendado en Odoo.sh

### Paso 1: Ejecutar la Auditoría
Conéctate a la shell del contenedor en Odoo.sh (vía Web Shell o SSH) y ejecuta:

```bash
python3 odoo-bin shell -c /home/odoo/src/odoo.conf -d <NOMBRE_BASE_DATOS> < audit_analytic_models.py
```
*O si estás dentro del prompt interactivo de python:*
```python
exec(open('audit_analytic_models.py').read())
```

**¿Qué revisar en la salida?**
1. Los nombres e IDs exactos de las sucursales (`res.company`).
2. Los nombres e IDs exactos de las cuentas analíticas (`account.analytic.account`).
3. El ID y nombre de la categoría "Pastas" (`product.category`).
4. El modelo de prueba existente (ej. ID 15 y el modelo visible en la imagen).

---

### Paso 2: Ajustar Configuración y Probar en DRY-RUN
Abre [`create_analytic_distribution_models.py`](./create_analytic_distribution_models.py) y verifica las variables del encabezado:
```python
DRY_RUN = True  # Mantener en True para la primera prueba
FABRICA_PASTAS_ACCOUNT_SEARCH = "FABRICA"  # Ajustar si el nombre difiere
PASTAS_CATEGORY_SEARCH = "Pastas"          # Ajustar según auditoría
```

Ejecuta el script:
```bash
python3 odoo-bin shell -c /home/odoo/src/odoo.conf -d <NOMBRE_BASE_DATOS> < create_analytic_distribution_models.py
```
El script mostrará la tabla con:
- Modelos que se crearían (`[+] SE CREARÍA`).
- Modelos que se actualizarían (`[~] SE ACTUALIZARÍA`).
- Modelos que ya coinciden y no se tocan (`[=] SIN CAMBIOS`).
- Ejecutará un `ROLLBACK` automático para garantizar cero modificaciones.

---

### Paso 3: Aplicar Cambios Definitivos
Una vez que el plan de acción en el log sea 100% el deseado:
1. Cambia en [`create_analytic_distribution_models.py`](./create_analytic_distribution_models.py):
   ```python
   DRY_RUN = False
   ```
2. Vuelve a ejecutar el script en la shell de Odoo.
3. El script realizará `env.cr.commit()` y los modelos quedarán guardados en Odoo.

---

### Paso 4: Validar con la Simulación
Ejecuta el script de pruebas para confirmar que Odoo asigna las analíticas esperadas:
```bash
python3 odoo-bin shell -c /home/odoo/src/odoo.conf -d <NOMBRE_BASE_DATOS> < test_analytic_simulation.py
```

---

## 🔍 Consultas SQL de Soporte (Directas en PostgreSQL)

Si deseas verificar los datos directamente en psql:

```sql
-- Ver todos los modelos de distribución analítica configurados
SELECT 
    m.id,
    c.name AS company,
    pc.name AS product_category,
    p.name AS product,
    m.analytic_distribution
FROM account_analytic_distribution_model m
LEFT JOIN res_company c ON c.id = m.company_id
LEFT JOIN product_category pc ON pc.id = m.product_categ_id
LEFT JOIN product_template p ON p.id = (SELECT product_tmpl_id FROM product_product WHERE id = m.product_id)
ORDER BY m.company_id, m.id;

-- Ver cuentas analíticas y sus planes
SELECT 
    a.id,
    a.code,
    a.name AS account_name,
    p.name AS plan_name,
    c.name AS company_name
FROM account_analytic_account a
LEFT JOIN account_analytic_plan p ON p.id = a.plan_id
LEFT JOIN res_company c ON c.id = a.company_id
ORDER BY p.name, a.name;
```
