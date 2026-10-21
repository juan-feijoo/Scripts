# Runbook de Implementación: Seguridad, Aprobaciones y Roles Atlas (Odoo 18.0+e / Odoo.sh)

> **Cliente**: Atlas Group / Bulgueroni Group  
> **Entorno**: Odoo.sh (Staging DB: `outsource-argentina-atlas-group1-staging-40016719`)  
> **Versión**: Odoo Enterprise 18.0+e (Localización Argentina)  

---

## 1. Resumen de la Solución Técnica

Para satisfacer el 100% de la matriz de requerimientos sin alterar el core ni depender de intervenciones manuales propensas a perderse en rebuilds de Odoo.sh, la arquitectura implementada se compone de:

1. **Módulo Custom Liviano (`atlas_security_approvals`)**:
   - **Restricción estricta de borrado (`unlink`)**: En Odoo estándar, cualquier usuario con permisos de edición en borradores puede eliminar registros (`unlink`). Studio no permite retirar permisos de borrado otorgados por grupos base de XML. El módulo sobreescribe `unlink` en `sale.order`, `purchase.order`, `account.move` y `account.payment`, permitiendo la eliminación únicamente a usuarios con el grupo `group_atlas_can_unlink` (Responsable de Administración y Responsable General) o superusuarios.
   - **Restricción de creación de Contactos y Productos**: Controla `create` en `res.partner` y `product.template` para que Operador y Responsable de Operaciones no puedan dar de alta clientes, proveedores ni productos.
   - **Definición de Categoría y Grupos**: Define la jerarquía de roles (`group_role_operador`, `group_role_resp_operaciones`, `group_role_administrativo`, `group_role_resp_administracion`, `group_role_resp_general`) y grupos funcionales.
   - **Reglas Studio Nativas (`studio.approval.rule`)**: Define las reglas para aprobación de Órdenes de Venta (`action_confirm`) y Requerimiento de Compras (`button_confirm`).

2. **Scripts en Shell (`odoo-bin shell`)**:
   - `01_auditoria_entorno.py`: Script de solo lectura para diagnóstico de compañías, módulos y usuarios.
   - `02_configurar_usuarios_aprobaciones.py`: Script idempotente con switch **`DRY_RUN`**, control de base de datos esperada, alta técnica de usuarios sin correo de reseteo, asignación multi-compañía estricta (aislamiento de 1066 S.A.) y vinculación de `approver_ids` para notificaciones y actividades en el chatter de Odoo 18.
   - `03_smoke_test_seguridad.py`: Suite de validación automatizada mediante transacciones atómicas (`savepoint`) con rollback inmediato para comprobar en vivo todas las restricciones.

---

## 2. Estructura de Archivos

```text
Permisos/
├── Perfiles Odoo.xlsx
├── RUNBOOK_ATLAS.md
├── atlas_security_approvals/
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── unlink_security.py
│   │   └── partner_product_security.py
│   ├── security/
│   │   └── security_groups.xml
│   └── data/
│       └── studio_approval_rules.xml
└── scripts/
    ├── 01_auditoria_entorno.py
    ├── 02_configurar_usuarios_aprobaciones.py
    └── 03_smoke_test_seguridad.py
```

---

## 3. Matriz de Roles y Mapeo en Odoo 18

| Requerimiento (Planilla) | Operador | Resp. Operaciones | Administrativo | Resp. Administración | Resp. General | Implementación Técnica Odoo 18 |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **Requerimiento OC Gastos 3ros** | ✔ | ✔ | ✔ | ✔ | ✔ | `purchase.order` en estado borrador (`draft`) |
| **Aprobación Requerimiento OC** | ✘ | ✘ | ✘ | ✔ | ✔ | `studio.approval.rule` sobre `purchase.order.button_confirm` (Grupo: `group_atlas_aprob_compra`) |
| **Orden de Compra por Gastos** | ✔ | ✔ | ✔ | ✔ | ✔ | Requiere aprobación previa de la regla Studio para confirmar |
| **Registro de Compra Gastos** | ✔ | ✔ | ✔ | ✔ | ✔ | `purchase.group_purchase_user` |
| **Requerimiento Orden de Venta** | ✔ | ✔ | ✔ | ✔ | ✔ | `sale.order` en estado borrador (`draft`) |
| **Aprobación de Orden de Venta** | ✘ | ✔ | ✘ | ✔ | ✔ | `studio.approval.rule` sobre `sale.order.action_confirm` (Grupo: `group_atlas_aprob_venta`) |
| **Facturación (Modifica datos OV)** | ✘ | ✘ | ✔ | ✔ | ✔ | `account.group_account_user` + `sales_team.group_sale_salesman_all_leads` |
| **Registración Pagos Clientes** | ✘ | ✘ | ✔ | ✔ | ✔ | `account.payment` inbound |
| **Carga Contactos (Clie / Prov)** | ✘ | ✘ | ✔ | ✔ | ✔ | Restricción en `res.partner.create` (`group_atlas_can_manage_contacts`) |
| **Carga de Productos** | ✘ | ✘ | ✔ | ✔ | ✔ | Restricción en `product.template.create` (`group_atlas_can_manage_products`) |
| **Registro Factura Proveedores** | ✘ | ✘ | ✔ | ✔ | ✔ | `account.move` (`in_invoice`) |
| **Certificados de Retención** | ✘ | ✘ | ✔ | ✔ | ✔ | `l10n_ar` retenciones en pagos |
| **Solicitud Orden de Pago** | ✘ | ✘ | ✔ | ✔ | ✔ | `account.payment` outbound borrador (sin obligatoriedad de OC) |
| **Registro Pago Proveedores** | ✘ | ✘ | ✔ | ✔ | ✔ | `account.payment` outbound confirmado |
| **Bancos, Caja y Conciliación** | ✘ | ✘ | ✔ | ✔ | ✔ | `account.group_account_user` (Conciliación bancaria habilitada) |
| **Módulo Contable** | ✘ | ✘ | ✔ | ✔ | ✔ | Asientos contables habilitados |
| **Módulo Configuración** | ✘ | ✘ | ✘ | ✔ | ✔ | Protegido: Administrativo NO tiene `base.group_system` |
| **Eliminación de Documentos** | ✘ | ✘ | ✘ | ✔ | ✔ | Sobreescritura de `unlink` en `atlas_security_approvals` (`group_atlas_can_unlink`) |
| **Módulo Reportes** | ✔ | ✔ | ✔ | ✔ | ✔ | Acceso nativo según módulos autorizados |
| **Acceso a 1066 S.A.** | ✘ | ✘ | ✔ | ✔ | ✔ | Restricción estricta en `res.users.company_ids` (Operador y Resp Op solo BG) |

---

## 4. Guía de Ejecución Paso a Paso en Odoo.sh

### Paso 1: Subir el Módulo al Repositorio
Copiar la carpeta `atlas_security_approvals/` a la raíz de tu repositorio de Odoo.sh (o en la carpeta de addons correspondiente a tu proyecto) en la rama de trabajo / staging:
```bash
git add atlas_security_approvals/
git commit -m "feat(security): agregar modulo atlas_security_approvals con reglas y restriccion de unlink"
git push
```

### Paso 2: Instalar el Módulo en la Base de Datos
1. Ingresar al entorno de Odoo con usuario Administrador.
2. Activar el **Modo Desarrollador** (Ajustes → Activar modo desarrollador).
3. Ir a **Aplicaciones** → en el menú superior hacer clic en **Actualizar lista de aplicaciones**.
4. Buscar `atlas_security_approvals` (o "Atlas - Seguridad y Reglas de Aprobación") y hacer clic en **Activar / Instalar**.

### Paso 3: Ejecutar Script de Configuración en Shell (DRY-RUN)
1. En Odoo.sh, seleccionar la rama (staging o producción) y hacer clic en la pestaña **Shell**.
2. Conectarse al shell interactivo ejecutando:
   ```bash
   odoo-bin shell
   ```
3. Copiar y pegar el contenido completo de [`scripts/02_configurar_usuarios_aprobaciones.py`](file:///c:/Users/juanf/Documents/Scripts/Atlas/Permisos/scripts/02_configurar_usuarios_aprobaciones.py) (por defecto `DRY_RUN = True`).
4. Verificar la salida en consola:
   - Debe listar los usuarios procesados.
   - Todas las líneas de validación deben mostrar `✔`.
   - Al final debe imprimir: `>> ROLLBACK EJECUTADO: Ningún cambio fue persistido en la base de datos.`

### Paso 4: Aplicar Cambios Definitivos (COMMIT)
1. En el script [`scripts/02_configurar_usuarios_aprobaciones.py`](file:///c:/Users/juanf/Documents/Scripts/Atlas/Permisos/scripts/02_configurar_usuarios_aprobaciones.py), cambiar la línea:
   ```python
   DRY_RUN = False
   ```
2. Pegar nuevamente el código en `odoo-bin shell`.
3. Verificar que al final imprima:
   ```text
   RESULTADO FINAL: ✔ TODO OK
   >> COMMIT EXITOSO: Todos los usuarios, accesos y aprobadores fueron guardados en la base de datos.
   ```

### Paso 5: Ejecutar Smoke Test Automatizado
En el mismo shell (o abriendo uno nuevo), pegar el contenido de [`scripts/03_smoke_test_seguridad.py`](file:///c:/Users/juanf/Documents/Scripts/Atlas/Permisos/scripts/03_smoke_test_seguridad.py).
El script verificará:
- Que Operador y Resp Operaciones no tengan acceso a 1066 S.A.
- Que el borrado esté bloqueado para Operador y Administrativo, pero permitido para Resp Administración.
- Que las reglas de aprobación Studio funcionen según los permisos esperados.
- Que la carga de contactos y productos esté bloqueada para Operador y permitida para Administrativo.
- Confirmará: `RESUMEN SMOKE TEST: X/X PRUEBAS EXITOSAS` y ejecutará rollback de seguridad.

---

## 5. Pruebas de Humo Manuales en la Interfaz Web (UI)

| Prueba | Usuario a Probar | Acción en UI | Resultado Esperado |
|---|---|---|---|
| **Multi-Compañía** | `mandatario@atlasgroup.com.ar` | Mirar el selector de compañías (arriba a la derecha) | Solo figura **BULGHERONI GROUP S.A.**. 1066 S.A. no existe para él. |
| **Aprobación de Venta** | `mandatario@atlasgroup.com.ar` | Crear presupuesto de venta y pulsar **Confirmar** | El sistema muestra alerta de aprobación requerida. En el chatter se genera la actividad "Aprobación pendiente" dirigida a Hernán Pacetti, Eugenia Zanotti y Hernán Fernández. |
| **Aprobación de Compra** | `hernanpacetti@atlasgroup.com.ar` | Crear Solicitud de Presupuesto y pulsar **Confirmar Pedido** | El sistema bloquea la confirmación exigiendo aprobación de Eugenia Zanotti o Hernán Fernández. |
| **Bloqueo de Borrado** | `administracion@atlasgroup.com.ar` | Abrir un presupuesto borrador de venta o compra → Menú Acción → **Suprimir** | Salta un cartel de error informativo (`UserError`): *"Acción denegada: Su rol no tiene permisos para eliminar registros..."* |
| **Bloqueo Alta Contacto** | `mandatario@atlasgroup.com.ar` | Ir a Contactos → botón **Nuevo** | Salta cartel de error indicando que la creación está reservada para Administración y Gerencia. |
| **Edición OV al Facturar** | `administracion@atlasgroup.com.ar` | Abrir una orden de venta confirmada para emitir factura | Puede acceder a los datos de la orden y facturación con permisos contables. |

---

## 6. Procedimiento de Rollback / Contingencia

Si en algún momento se requiere desactivar temporalmente las reglas o revertir los cambios:

1. **Desactivar Reglas Studio**:
   En `odoo-bin shell`:
   ```python
   env['studio.approval.rule'].search([('name', '=like', '[ATLAS]%')]).write({'active': False})
   env.cr.commit()
   ```
2. **Desinstalar Módulo**:
   Ir a **Aplicaciones** → buscar `atlas_security_approvals` → Menú tres puntos → **Desinstalar**. Al desinstalarse, se eliminan los interceptores de unlink y validaciones de creación sin tocar datos del negocio.
