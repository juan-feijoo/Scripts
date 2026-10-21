# Guía de Pruebas Visuales en UI (Odoo 18.0+e / Staging)

> **Objetivo**: Probar en la interfaz web de Odoo (mediante ventanas de incógnito) todos los flujos de la matriz de perfiles Atlas con registros persistidos en la base de datos de Staging.

---

## 1. Generación de Datos en Base de Datos

Abrir la pestaña **Shell** de Odoo.sh en el branch de Staging (`odoo-bin shell`) y pegar el contenido de:
[`scripts/04_generar_casos_prueba_ui.py`](file:///c:/Users/juanf/Documents/Scripts/Atlas/Permisos/scripts/04_generar_casos_prueba_ui.py)

Este script:
1. Asigna la contraseña temporal **`Atlas2026!`** a los 5 usuarios del ticket para que puedas loguearte inmediatamente sin depender de correos de invitación.
2. Crea los clientes y proveedores demo requeridos.
3. Genera y guarda con **COMMIT** los siguientes documentos de prueba:
   - **Orden de Venta** pendiente de aprobación con actividades agendadas en el chatter para los aprobadores.
   - **Solicitud de Compra** pendiente de aprobación para Gastos de Terceros.
   - **Presupuesto de Venta y Solicitud de Compra de prueba de borrado** para verificar el bloqueo del botón *Suprimir*.

---

## 2. Credenciales para Pruebas en Staging

> **Contraseña común**: `12345`

| Rol Atlas | Usuario (Login) | Permisos Clave a Observar |
|---|---|---|
| **Operador** | `mandatario@atlasgroup.com.ar` | Solo compañía BG (sin acceso a 1066). No aprueba ventas ni compras. No borra. No crea contactos ni productos. |
| **Resp. Operaciones** | `hernanpacetti@atlasgroup.com.ar` | Solo compañía BG. **Aprueba Ventas**, pero NO compras. No borra. No crea contactos ni productos. |
| **Administrativo** | `administracion@atlasgroup.com.ar` | Acceso a BG y 1066. Acceso contable, facturación y pagos. Puede crear contactos y productos. **NO borra** movimientos. No aprueba OV ni OC. |
| **Resp. Administración** | `eugeniazanotti@atlasgroup.com.ar` | Acceso a BG y 1066. **Aprueba Ventas y Compras**. **SÍ puede borrar** movimientos (`unlink`). Acceso contable total. |
| **Resp. General** | `hernanfernandez@atlasgroup.com.ar` | Máximo nivel jerárquico. Mismos permisos que Resp. Administración. |

---

## 3. Guion de Pruebas Paso a Paso en la UI

### Prueba 1: Aislamiento Multi-Compañía (BG vs 1066 S.A.)
1. Abrir una ventana de incógnito en el navegador e ingresar a la URL de tu staging de Odoo.
2. Iniciar sesión con **`mandatario@atlasgroup.com.ar`** (clave: `Atlas2026!`).
3. Mirar en la esquina superior derecha el **selector de compañías**:
   - **Resultado Esperado**: Solo aparece **BULGHERONI GROUP S.A.**. La compañía 1066 S.A. no existe para este usuario.
4. Repetir el login con **`hernanpacetti@atlasgroup.com.ar`**:
   - **Resultado Esperado**: Solo tiene acceso a BULGHERONI GROUP S.A.
5. Iniciar sesión con **`administracion@atlasgroup.com.ar`**:
   - **Resultado Esperado**: El selector muestra ambas compañías (**BULGHERONI GROUP S.A.** y **1066 S.A.**) y puede alternar entre ellas.

---

### Prueba 2: Flujo de Aprobación de Orden de Venta
1. Con la sesión de **`mandatario@atlasgroup.com.ar`** (Operador):
   - Ir a la app **Ventas**.
   - Abrir el presupuesto creado por el script (con referencia `DEMO-APROB-OV`).
   - Observar el chatter: figura la actividad de aprobación pendiente.
   - Hacer clic en el botón **Confirmar**:
   - **Resultado Esperado**: Odoo no confirma la venta; muestra el mensaje de Studio indicando que se requiere la aprobación de Responsable de Operaciones, Responsable de Administración o Responsable General.
2. Abrir otra ventana de incógnito e ingresar con **`hernanpacetti@atlasgroup.com.ar`** (Resp. Operaciones):
   - En la barra superior derecha, hacer clic en el **ícono del reloj** (Actividades 🕒):
     - Aparece la actividad "Grant Approval" en Ventas vinculada a la orden de venta.
   - Abrir la orden de venta:
     - Sobre el botón **Confirmar** aparece el ícono de escudo/aprobación de Studio.
     - Pulsar el botón de **Aprobar**: la aprobación se registra en el chatter con su nombre y fecha.
     - Ahora sí, pulsar **Confirmar**: la orden de venta pasa al estado confirmado (*Orden de Venta*).

---

### Prueba 3: Flujo de Aprobación de Requerimiento de Compra
1. Con la sesión de **`hernanpacetti@atlasgroup.com.ar`** (Resp. Operaciones) o `mandatario@`:
   - Ir a la app **Compras**.
   - Abrir la Solicitud de Presupuesto creada por el script (referencia `DEMO-APROB-OC`).
   - Hacer clic en **Confirmar Pedido**:
   - **Resultado Esperado**: El sistema bloquea la confirmación. Resp. Operaciones **NO** tiene permiso para aprobar compras (solo Resp. Administración y Resp. General).
2. Iniciar sesión con **`eugeniazanotti@atlasgroup.com.ar`** (Resp. Administración):
   - Ver la actividad en el reloj 🕒 y abrir la Solicitud de Presupuesto.
   - Visualizar el ícono de aprobación de Studio en el botón **Confirmar Pedido**.
   - Pulsar **Aprobar** y luego **Confirmar Pedido**: la orden de compra queda confirmada.

---

### Prueba 4: Bloqueo de Eliminación de Documentos (`unlink`)
1. Iniciar sesión con **`administracion@atlasgroup.com.ar`** (Administrativo):
   - Ir a **Ventas** → abrir el presupuesto de prueba de borrado (`TEST-BORRADO-OV`).
   - Hacer clic en el engranaje de **Acción** (arriba a la izquierda) → **Suprimir**.
   - Confirmar en el diálogo "Eliminar registro":
   - **Resultado Esperado**: Salta una ventana modal de Odoo con el siguiente mensaje de seguridad:
     > *"Acción denegada: Su rol no tiene permisos para eliminar registros de Órdenes de Venta.*  
     > *Según las políticas de seguridad de Atlas, la eliminación de documentos y movimientos está restringida exclusivamente a Responsable de Administración y Responsable General."*
2. Probar lo mismo en **Compras** con la solicitud de compra `TEST-BORRADO-OC`:
   - **Resultado Esperado**: Salta el mismo bloqueo informativo impidiendo eliminar la compra.
3. Iniciar sesión con **`eugeniazanotti@atlasgroup.com.ar`** (Resp. Administración):
   - Abrir `TEST-BORRADO-OV` → Acción → **Suprimir**:
   - **Resultado Esperado**: El registro se elimina correctamente sin errores.

---

### Prueba 5: Restricción de Alta de Contactos y Productos
1. Con la sesión de **`mandatario@atlasgroup.com.ar`** (Operador):
   - Ir a la app **Contactos** → hacer clic en el botón **Nuevo**.
   - Ingresar un nombre de prueba y pulsar Guardar (o intentar crearlo):
   - **Resultado Esperado**: Salta un mensaje modal indicando que su rol no tiene permisos para crear contactos nuevos.
   - Ir a **Ventas → Productos** → botón **Nuevo**:
   - **Resultado Esperado**: Salta un mensaje modal indicando que la creación de productos está reservada para Administración y Gerencia.
2. Iniciar sesión con **`administracion@atlasgroup.com.ar`** (Administrativo):
   - Ir a **Contactos** → botón **Nuevo**: puede crear clientes y proveedores normalmente.
   - Ir a **Productos** → botón **Nuevo**: puede dar de alta productos en el catálogo normalmente.
