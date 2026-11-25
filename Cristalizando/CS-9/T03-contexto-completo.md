# Contexto — T03: bloqueo de reservas y remitos cancelados

> Documento de apoyo del ticket. Explica **por qué** pasa el bug, **cómo reproducirlo** y **qué decidió el cliente**. El "qué hay que hacer" está en el ticket.

---

## 1. El negocio en 1 minuto

- **Cristalizando** y **NOA Aberturas** son 2 compañías en la misma base Odoo 17 Enterprise (Odoo.sh).
- En la OV, la pestaña custom **"Reserva de materiales"** lleva los insumos de la obra. Cada cambio en esa pestaña crea o actualiza **remitos de reserva** (`stock.picking` vinculados por `sale_stock_link_id`).
- Lo que **genera necesidad de stock** ("pendiente de salida", el pronóstico) son los **remitos abiertos** (borrador, en espera, listo). Uno cancelado o hecho ya no genera necesidad.

## 2. Qué pasó en la reunión (17/11/2026)

**Necesidad (Hernán):** a veces queda un remanente de 200 artículos que no se va a entregar, porque se cambió el material o se eligió otra alternativa. Quieren anularlo todo junto, sin ajustar stock y sin que aparezca como necesidad de compra.
> **Joaquín:** "Con eliminarlo o cancelarlo ya se borra… del pendiente de salida."
> **Hernán:** "Ah, entonces ya estaría resuelto."

⇒ **Cancelar el remito es la herramienta correcta.** No hay que inventar otra.

**Bug (Matías y Hernán, mostrado en vivo):** un usuario canceló por error, y después:
> **Matías:** "una reserva o un remito que hemos cancelado, después nos dio la posibilidad de agregar una reserva de material y se volvía a habilitar todo el material que tenías antes de cancelarlo."
> **Matías:** "Desde el remito sí te deja agregar una línea… y ya te vuelve al estado original con la demanda."
> **Joaquín (lo reprodujo):** "yo cancelo esta, cancelo esta, vengo aquí y quiero agregar otro. Mirá: me crea uno nuevo con todo. Eso tampoco debería pasar."

**Pedido:**
> **Matías:** "debería estar bloqueado en el momento que yo cancelé la reserva… que me bloquee cualquier tipo de movimiento, ya sea entrando desde el remito, desde la orden de venta, desde cualquier lado… que no se pueda ni descancelar."
> **Joaquín:** "Perfecto."

**Sobre "Anular reserva":** Matías preguntó por el botón "Anular reserva". Joaquín lo probó: solo cambia el estado de Listo a En espera (`do_unreserve`) y el pendiente de salida sigue igual. "No sirve para nada" para este fin.

## 3. Cómo reproducir (staging, código actual)

**Caso A: la OV regenera lo cancelado**
1. Tomar una OV confirmada con reserva: producto P1 = 10 y P2 = 5. Existe el remito R1 (Listo o En espera) con P1 10 y P2 5.
2. Cancelar R1. El pronóstico de P1 y P2 baja.
3. En la OV, pestaña Reserva, cambiar P2 de 5 a 6 (o agregar una línea P3 = 1). Guardar.
4. **Bug:** se crea R2 con P1 10, P2 6 (y P3 1). Volvió todo lo cancelado.

**Caso B: el remito cancelado se reabre**
1. Abrir el remito cancelado R1.
2. En Operaciones, agregar una línea (cualquier producto). Guardar.
3. **Bug:** R1 deja de estar cancelado y vuelve con toda la demanda original más la línea nueva.

## 4. Por qué pasa (código)

**Repo:** `git@github.com:Joaquin-04/material_reservation.git`, `main@ecdd902` (25/02/2026).
**Archivo:** `models/sale_order_material_reservation.py`

### Caso A
```
line.write (≈ línea 545) ──▶ _handle_material_reservation (línea 591)
    pickings = sale_stock_link_id.picking_ids.filtered(state not in ('done','cancel'))
    if reusable_picking: ...                       # no hay: R1 está cancelado
    else:
        all_lines = order.material_reservation_ids
        lines_with_pending_qty = [l for l in all_lines if l.qty_pending >= 0]   # ← TODAS las líneas (>= 0)
        _create_new_picking_for_lines(...)         # ← crea R2 con todo
```
- `qty_pending` = `product_uom_qty - qty_done` (`_compute_qty_pending`). **No descuenta lo cancelado.**
- `qty_done` solo sube en `stock.move._action_done` (`models/stock_picking_extension.py`). Cancelar no lo toca.
- ⇒ Para la línea, lo cancelado sigue pendiente, y cualquier write a cualquier línea dispara la regeneración de **todas**.
- Además, `>= 0` mete líneas con pendiente 0 → moves con cantidad 0.

### Caso B
- Odoo nativo: agregar un move a un picking cancelado crea el move en `draft`. El estado del picking se recalcula según sus moves (`_compute_state`) y sale de `cancel`.
- En v17 el formulario del remito no bloquea la edición de operaciones con `state == 'cancel'` para todos los casos, y el módulo no agrega ningún control.

## 5. Modelo de "cancelado" propuesto (2 niveles)

| Nivel | Qué lo dispara | Qué bloquea | Por qué |
|---|---|---|---|
| **Remito cancelado** | Botón nativo "Cancelar" en el remito (uso actual para anular remanentes) | Ese remito no se reabre y lo cancelado no se regenera (`qty_cancelled`). La OV puede seguir reservando **otras** cosas o subir cantidades | La reserva va **por etapas**. Si cancelar un remanente bloqueara la OV entera, no se podría seguir trabajando la obra |
| **Reserva cancelada** | Botón nuevo explícito "Cancelar reserva" | **Todo**: líneas, remitos y moves de esa OV. Sin descancelar | Es lo que pidió Matías ("desde cualquier lado") para la decisión "esta obra no va más" |

⚠️ **Hay que confirmarlo con el cliente** (punto abierto 2 del ticket). La frase de Matías se puede leer como "cancelar un remito bloquea toda la OV". La propuesta separa los dos casos para no romper el trabajo por etapas.

## 6. Detalles de implementación
- **`qty_cancelled` no tiene que contar** los moves que el propio módulo cancela al bajar la cantidad a 0 (`_add_or_update_moves_in_picking`, línea 627: pone `product_uom_qty = 0` y `state = 'cancel'`). Como su cantidad ya es 0, sumar `product_uom_qty` de los cancelados da 0. Verificarlo con un test.
- **Devoluciones:** los moves con `origin_returned_move_id` no cuentan en `qty_cancelled`.
- **Bypass interno:** el propio módulo escribe `state='cancel'` en moves. Usar un contexto (`material_reservation_internal=True`) para que los bloqueos de write no se disparen con sus propias escrituras.
- **Campos Studio en el picking** (`x_studio_estado`, observaciones 1-3, `x_studio_remito_original`, etc.): **no** bloquearlos en remitos cancelados. Depósito los usa para anotar.
- **Acciones de servidor de Studio** sobre el remito ("Cambiar cantidades", "Todo en cero", "Validar", "Anular reserva", "Desechar") escriben en los moves. Con el bloqueo en el ORM van a fallar si se usan sobre un cancelado, que es lo esperado. Probarlas.
- **Si T02 ya está:** cancelar un RES cancela su BAJ encadenada (`propagate_cancel`). Las 2 suman a `qty_cancelled` solo una vez: contar solo el tramo de baja (destino `customer`) o el tramo que corresponda según la definición de `qty_pending` en T02.

## 7. Referencias
- T01 (botón "Remitos reserva" + filtros): `../T01-remitos-reserva-filtros/`
- T02 (2 tramos): `../T02-remitos-2-tramos-almacen-intermedio/`
- Relevamiento del módulo (acciones Studio, campos Studio del picking): `Cristalizando/dudas/01-intercompany-stock-mrp/09-modulos-del-flujo.md` §1 y §3


---

# Anexo: ticket de Jira (título y descripción)


## Título
```
[Cristalizando] Reserva de materiales: un remito cancelado no se regenera ni se reabre, y una reserva cancelada queda bloqueada
```

## Descripción
```markdown
## Objetivo
Hoy cancelar un remito de reserva no sirve: el material vuelve a aparecer.
Se reproduce de 2 formas:
- **(A)** Cancelo el remito y después edito cualquier línea de la reserva en la OV → se crea un remito nuevo con **todo** el pendiente, incluido lo que había cancelado.
- **(B)** Abro el remito cancelado y le agrego una línea → el remito vuelve a su estado anterior con toda la demanda.

El cliente lo pidió en la reunión del 17/11: "en el momento que yo cancelé la reserva, que me bloquee cualquier tipo de movimiento, ya sea entrando desde el remito, desde la orden de venta, desde cualquier lado" (Matías Medina).
Cancelar un remito sigue siendo la forma de anular un remanente sin afectar stock (Hernán); eso no cambia. El contexto completo y la reproducción paso a paso están en el .md adjunto.

## Módulo
material_reservation (repo Joaquin-04/material_reservation, rama main)

## Se relaciona con
- T02 (2 tramos): toca _handle_material_reservation y las cantidades de la línea. Coordinar el merge.
- Gonzalo (formulario nuevo de reserva): el bloqueo total (punto 3) va en el modelo nuevo de reserva si ya existe. Si no, va en sale.stock.link.

## Qué hay que hacer

### 1. Lo cancelado no se regenera (arregla el caso A)
- En `sale.order.material.reservation.line` agregar `qty_cancelled` (compute, store): suma de product_uom_qty de los moves de la línea en estado cancel, sin contar devoluciones ni los moves cancelados por bajar la cantidad a 0.
- `qty_pending` = product_uom_qty - qty_done - qty_cancelled (mínimo 0).
- En `_handle_material_reservation`, al crear un remito nuevo, incluir solo las líneas con `qty_pending > 0` (hoy usa `>= 0` y mete todas).
- Si técnica realmente necesita más, sube la cantidad de la línea, y solo ese delta genera un remito nuevo.
- Mostrar `qty_cancelled` en la solapa o formulario de reserva (optional="show").

### 2. Un remito de reserva cancelado no se puede reabrir (arregla el caso B)
Solo para remitos con sale_stock_link_id:
- stock.move create: UserError si el picking destino está cancelado.
- stock.move write: UserError si el move está cancelado y se intenta cambiar product_uom_qty, quantity o state (salvo contexto interno del propio módulo).
- stock.picking write: UserError si está cancelado y se tocan move_ids / move_ids_without_package. El chatter, las notas y los campos Studio de observaciones se siguen pudiendo editar.
- Vista del remito: `readonly="state == 'cancel'"` en la pestaña de operaciones (refuerzo visual; el bloqueo real es en el ORM).
- Mensaje sugerido: "El remito {name} está cancelado y no se puede modificar. Si necesitás más material, aumentá la cantidad en la reserva de la OV {origin}."

### 3. Cancelar la reserva completa (bloqueo total de la OV)
- Botón "Cancelar reserva" en la reserva (formulario de Gonzalo, o en la OV si todavía no existe). Solo para el grupo de responsables (definir). Pide confirmación.
  - Cancela todos los remitos de reserva abiertos (los hechos no se tocan).
  - Marca la reserva como cancelada: `reservation_state = 'cancel'`, con fecha y usuario.
  - Deja un mensaje en el chatter.
- Con la reserva cancelada, UserError en:
  - alta, edición o baja de líneas de reserva (create, write, unlink), venga de la OV, del formulario de reserva o de import
  - creación de remitos o moves con ese sale_stock_link_id
  - `_handle_material_reservation` (guard al inicio)
- No hay "descancelar" desde la UI. Si hace falta, se hace con una acción técnica solo para el administrador (fuera de alcance; documentarlo).

### 4. "Anular reserva" de Studio
La acción de servidor "Anular reserva" (Studio) solo hace `do_unreserve`: no cancela ni libera el pendiente. Confirmar si se oculta o se renombra ("Liberar stock reservado") para que no la confundan con cancelar. Es configuración, no código.

## Fuera de alcance
- Descancelar desde la UI.
- Cancelar o anular remitos ya hechos (eso es una devolución).
- Liberar material que ya está en el almacén intermedio (T02 / futuro).

## Criterios de aceptación
- [ ] Caso A: cancelo el único remito abierto (3 productos), edito una línea de la reserva sin subir cantidades → no se crea ningún remito.
- [ ] Caso A con aumento: subo una línea de 10 a 15 después de cancelar → se crea un remito solo por 5.
- [ ] Caso B: abro un remito cancelado y agrego una línea → UserError. Lo mismo editando cantidades o desde importación.
- [ ] En un remito cancelado se pueden escribir mensajes en el chatter y editar observaciones.
- [ ] Remito parcial: valido una parte, cancelo el backorder → la línea queda con qty_done + qty_cancelled = product_uom_qty y no se regenera.
- [ ] El pendiente de salida (pronóstico) del producto baja al cancelar y no vuelve a subir.
- [ ] Cancelar reserva: cancela los remitos abiertos, deja los hechos como están y bloquea alta, edición y baja de líneas (OV, formulario e import) con un mensaje claro.
- [ ] Los remitos que no son de reserva (sin sale_stock_link_id) no se ven afectados en nada.
- [ ] Bajar la cantidad de una línea a lo ya hecho sigue funcionando: el move pasa a 0 y se cancela sin error ni doble conteo en qty_cancelled.

## Pruebas en staging
Reproducir primero los casos A y B **sin** el fix, para confirmar el bug, y después con el fix. Pasos en el contexto.md §3.

## Para confirmar con el cliente o el equipo
1. ¿Quién puede usar "Cancelar reserva" (bloqueo total)? ¿Responsable de depósito o técnica?
2. ¿Cancelar un remito suelto (remanente) tiene que bloquear la OV entera? Propuesta: **no**. Solo deja de regenerarse lo cancelado; el bloqueo total es el botón explícito. Si se bloqueara la OV entera, no se podría seguir reservando por etapas.
3. ¿Se oculta o se renombra la acción Studio "Anular reserva"?

Adjunto: contexto.md
```
