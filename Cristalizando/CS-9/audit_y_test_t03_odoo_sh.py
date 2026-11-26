"""
Script de auditoría y verificación T03 para ejecutar en `odoo-bin shell` (Odoo.sh).

Uso recomendado en Odoo.sh (siempre probar primero en staging):
    DRY_RUN=1 MODE=audit odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < audit_y_test_t03_odoo_sh.py
    DRY_RUN=1 MODE=verify_staging ORDER_NAME=S12345 odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < audit_y_test_t03_odoo_sh.py

Variables de entorno:
    DRY_RUN        : "1" (default, hace rollback al finalizar; nunca persiste cambios).
                     "0" solo aplica al modo `recompute` si se necesitara persistir recálculos.
    MODE           : "audit" (default) | "verify_staging" | "recompute"
    ORDER_NAME     : opcional, filtra una OV específica en modo audit o la usa en verify_staging.
    LIMIT          : máximo de líneas/remitos a mostrar en modo audit (default 50).
"""
import os
from odoo.exceptions import UserError

DRY_RUN = os.environ.get("DRY_RUN", "1").strip().lower() not in ("0", "false", "no")
MODE = os.environ.get("MODE", "audit").strip().lower()
ORDER_NAME = os.environ.get("ORDER_NAME", "").strip()
LIMIT = int(os.environ.get("LIMIT", "50"))


def header(title):
    print("\n" + "=" * 78)
    print(f" {title}")
    print("=" * 78)


def has_field(model_name, field_name):
    return field_name in env[model_name]._fields


def run_audit():
    header(f"T03 AUDIT (DRY_RUN={DRY_RUN}, DB={env.cr.dbname}, ORDER_NAME={ORDER_NAME or 'TODAS'})")

    # 1. Verificar si los campos del fix T03 ya están instalados
    checks = [
        ("sale.order.material.reservation.line", "qty_cancelled"),
        ("stock.move", "cancelled_by_qty_reduction"),
        ("sale.order.reservation", "reservation_state"),
        ("sale.order", "material_reservation_state"),
    ]
    print("\n[1] Estado de instalación de campos T03:")
    for model_name, fname in checks:
        print(f"  - {model_name}.{fname}: {'OK' if has_field(model_name, fname) else 'NO INSTALADO'}")

    group = env.ref("material_reservation.group_material_reservation_cancel", raise_if_not_found=False)
    print(f"  - Grupo material_reservation.group_material_reservation_cancel: "
          f"{'OK (' + str(len(group.users)) + ' usuarios)' if group else 'NO INSTALADO'}")

    # 2. Revisar acción de servidor de Studio 'Anular reserva' (Punto 4 del ticket)
    print("\n[2] Acciones de servidor en stock.picking relacionadas con reserva / cantidades:")
    server_actions = env["ir.actions.server"].sudo().search([
        ("model_id.model", "=", "stock.picking"),
    ])
    for act in server_actions:
        name_l = (act.name or "").lower()
        if any(k in name_l for k in ("reserv", "anular", "cero", "cantidad", "validar", "desech")):
            print(f"  - ID={act.id} | {act.name} | state={act.state} | binding_model={act.binding_model_id.model or '-'}")

    # 3. Revisar campos Studio en stock.picking (para confirmar que no quedan bloqueados)
    studio_fields = [f for f in env["stock.picking"]._fields if f.startswith("x_studio_")]
    print(f"\n[3] Campos x_studio_* en stock.picking ({len(studio_fields)} encontrados):")
    print("  " + (", ".join(sorted(studio_fields)[:20]) or "(ninguno)"))

    # 4. Auditar líneas de reserva que tienen moves cancelados
    print("\n[4] Líneas de reserva con movimientos cancelados (salida a cliente):")
    domain = [
        ("state", "=", "cancel"),
        ("reservation_line_id", "!=", False),
        ("location_dest_id.usage", "=", "customer"),
        ("origin_returned_move_id", "=", False),
    ]
    if ORDER_NAME:
        domain.append(("reservation_line_id.order_id.name", "=", ORDER_NAME))

    cancelled_moves = env["stock.move"].sudo().search(domain, order="id desc", limit=LIMIT * 3)
    lines = cancelled_moves.mapped("reservation_line_id")[:LIMIT]
    print(f"  Total moves cancelados encontrados (muestra): {len(cancelled_moves)} | Líneas distintas: {len(lines)}")

    has_qty_cancelled = has_field("sale.order.material.reservation.line", "qty_cancelled")
    has_flag = has_field("stock.move", "cancelled_by_qty_reduction")
    suspicious_two_step = []

    for line in lines:
        c_moves = line.move_ids.filtered(
            lambda m: m.state == "cancel"
            and m.location_dest_id.usage == "customer"
            and not m.origin_returned_move_id
            and (not has_flag or not m.cancelled_by_qty_reduction)
        )
        calc_cancelled = sum(c_moves.mapped("product_uom_qty"))
        stored_cancelled = line.qty_cancelled if has_qty_cancelled else None
        expected_pending = max(0.0, line.product_uom_qty - line.qty_done - calc_cancelled)

        # Detectar posible caso histórico T02 donde product_uom_qty bajó a 0 sin poner move en 0
        if line.product_uom_qty < (line.qty_done + calc_cancelled):
            suspicious_two_step.append((line, calc_cancelled))

        print(
            f"  OV={line.order_id.name} | Line={line.id} | Prod={line.product_id.default_code or line.product_id.id} | "
            f"qty={line.product_uom_qty:g} | done={line.qty_done:g} | "
            f"in_res={getattr(line, 'qty_in_reservation', 0.0):g} | "
            f"cancel_calc={calc_cancelled:g} (stored={stored_cancelled}) | "
            f"pending_actual={line.qty_pending:g} -> esperado={expected_pending:g}"
        )

    if suspicious_two_step:
        print(f"\n[!] ATENCIÓN: {len(suspicious_two_step)} línea(s) donde qty < qty_done + qty_cancelled "
              f"(posible reducción histórica antes del fix o cancelación posterior a baja de cantidad):")
        for line, calc_c in suspicious_two_step[:20]:
            print(f"    - OV={line.order_id.name} Line={line.id}: qty={line.product_uom_qty:g}, "
                  f"done={line.qty_done:g}, cancel_calc={calc_c:g}")


def run_verify_staging():
    header(f"T03 VERIFY_STAGING (SIEMPRE ROLLBACK AL FINAL - DRY_RUN={DRY_RUN})")
    if not has_field("sale.order.material.reservation.line", "qty_cancelled"):
        print("!! ERROR: El módulo material_reservation todavía no tiene instalado el fix T03.")
        return

    try:
        company = env.company
        wh_one = env["stock.warehouse"].search([
            ("company_id", "=", company.id),
            ("reservation_location_id", "=", False),
        ], limit=1)
        wh_two = env["stock.warehouse"].search([
            ("company_id", "=", company.id),
            ("reservation_location_id", "!=", False),
            ("reservation_type_id", "!=", False),
            ("reservation_drop_type_id", "!=", False),
        ], limit=1)

        print(f"  Empresa: {company.name}")
        print(f"  Almacén 1 tramo: {wh_one.display_name if wh_one else 'No encontrado'}")
        print(f"  Almacén 2 tramos: {wh_two.display_name if wh_two else 'No encontrado'}")

        partner_domain = [("active", "=", True)]
        if has_field("res.partner", "l10n_latam_identification_type_id"):
            partner_domain += [("l10n_latam_identification_type_id", "!=", False), ("vat", "!=", False)]
        partner = env["res.partner"].search(partner_domain, limit=1)
        if not partner:
            print("!! ERROR: No se encontró un contacto activo con identificación fiscal para la prueba.")
            return
        products = env["product.product"].search([("type", "=", "product")], limit=3)
        if len(products) < 2:
            print("!! ERROR: Se necesitan al menos 2 productos almacenables en la base.")
            return

        stage = env["material.reservation.stage"].create({"name": "[TEST T03] Etapa Temporal"})
        p1, p2 = products[0], products[1]

        for label, wh in [("1 TRAMO", wh_one), ("2 TRAMOS", wh_two)]:
            if not wh:
                print(f"\n[SKIP] {label}: no hay almacén configurado en {company.name}.")
                continue
            print(f"\n--- Probando {label} en almacén {wh.display_name} ---")
            order = env["sale.order"].create({
                "partner_id": partner.id,
                "company_id": company.id,
                "warehouse_id": wh.id,
                "studio_almacen": wh.id,
                "order_line": [(0, 0, {"product_id": p1.id, "product_uom_qty": 1.0, "price_unit": 10.0})],
            })
            l1 = env["sale.order.material.reservation.line"].create({
                "order_id": order.id, "product_id": p1.id, "product_uom_qty": 10.0, "stage_id": stage.id,
            })
            l2 = env["sale.order.material.reservation.line"].create({
                "order_id": order.id, "product_id": p2.id, "product_uom_qty": 5.0, "stage_id": stage.id,
            })
            order.action_confirm()

            pickings_before = order.sale_stock_link_id.picking_ids
            print(f"  Remitos iniciales: {pickings_before.mapped('name')}")

            # Caso A: cancelar remito(s) abiertos
            res_p = pickings_before.filtered(lambda p: p.reservation_flow == "reserve")
            to_cancel = res_p or pickings_before
            to_cancel.action_cancel()
            assert l1.qty_cancelled == 10.0 and l2.qty_cancelled == 5.0, (
                f"Esperado qty_cancelled=(10,5), obtenido=({l1.qty_cancelled},{l2.qty_cancelled})"
            )
            assert l1.qty_pending == 0.0 and l2.qty_pending == 0.0, "qty_pending debe ser 0"
            print("  [OK] Caso A.1: qty_cancelled y qty_pending correctos tras cancelar.")

            # Editar sin subir cantidad -> no crea remito
            count_after_cancel = len(order.sale_stock_link_id.picking_ids)
            l2.write({"product_uom_qty": 5.0})
            assert len(order.sale_stock_link_id.picking_ids) == count_after_cancel, "No debía crear remitos!"
            print("  [OK] Caso A.2: editar sin subir cantidad no regenera remitos.")

            # Subir l1 de 10 a 15 -> delta = 5
            l1.write({"product_uom_qty": 15.0})
            open_p = order.sale_stock_link_id.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
            assert open_p, "Debía crear remito por el delta de 5"
            for op in open_p:
                assert op.move_ids.mapped("product_uom_qty") == [5.0], f"Delta incorrecto en {op.name}: {op.move_ids.mapped('product_uom_qty')}"
            print(f"  [OK] Caso A.3: aumento 10->15 generó solo delta=5 en {open_p.mapped('name')}.")

            # Caso B: intentar reabrir el primer remito cancelado
            cancelled_p = to_cancel[0]
            try:
                env["stock.move"].create({
                    "name": "Test Caso B",
                    "product_id": p2.id,
                    "product_uom_qty": 1.0,
                    "product_uom": p2.uom_id.id,
                    "location_id": cancelled_p.location_id.id,
                    "location_dest_id": cancelled_p.location_dest_id.id,
                    "picking_id": cancelled_p.id,
                    "company_id": company.id,
                })
                raise AssertionError("Caso B FALLÓ: permitió agregar move a remito cancelado!")
            except UserError as err:
                print(f"  [OK] Caso B.1 (bloqueo move.create): {err}")

            cancelled_p.write({"note": "Nota permitida en cancelado"})
            cancelled_p.message_post(body="Chatter permitido en cancelado")
            print("  [OK] Caso B.2: notas y chatter permitidos en remito cancelado.")

            # Punto 3: Cancelar reserva completa
            reservation = order._get_or_create_material_reservation()
            reservation.action_cancel_reservation()
            assert reservation.reservation_state == "cancel"
            assert all(p.state in ("done", "cancel") for p in order.sale_stock_link_id.picking_ids)
            try:
                l1.write({"product_uom_qty": 20.0})
                raise AssertionError("Punto 3 FALLÓ: permitió editar línea tras cancelar reserva!")
            except UserError as err:
                print(f"  [OK] Punto 3 (bloqueo total): {err}")

        print("\n>>> TODAS LAS VERIFICACIONES T03 PASARON EXITOSAMENTE <<<")
    finally:
        # En verificación de staging SIEMPRE hacemos rollback para no dejar datos de prueba
        env.cr.rollback()
        print("\n[ROLLBACK] Transacción revertida limpiamente; no se modificó la base.")


def run_recompute():
    header(f"T03 RECOMPUTE (DRY_RUN={DRY_RUN})")
    if not has_field("sale.order.material.reservation.line", "qty_cancelled"):
        print("!! ERROR: Falta actualizar el módulo material_reservation primero.")
        return

    domain = [("order_id.name", "=", ORDER_NAME)] if ORDER_NAME else []
    lines = env["sale.order.material.reservation.line"].sudo().search(domain)
    before = {l.id: (l.qty_cancelled, l.qty_pending) for l in lines}

    lines._compute_qty_cancelled()
    lines._compute_qty_pending()
    changed = 0
    for l in lines:
        old_c, old_p = before[l.id]
        if old_c != l.qty_cancelled or old_p != l.qty_pending:
            changed += 1
            if changed <= LIMIT:
                print(f"  OV={l.order_id.name} Line={l.id}: "
                      f"qty_cancelled {old_c:g}->{l.qty_cancelled:g} | "
                      f"qty_pending {old_p:g}->{l.qty_pending:g}")

    print(f"\nTotal líneas revisadas: {len(lines)} | Con cambios: {changed}")
    if DRY_RUN:
        env.cr.rollback()
        print("[DRY_RUN=1] Rollback ejecutado. Para persistir, correr con DRY_RUN=0 MODE=recompute.")
    else:
        env.cr.commit()
        print("[DRY_RUN=0] Cambios confirmados (commit).")


if MODE == "audit":
    run_audit()
elif MODE == "verify_staging":
    run_verify_staging()
elif MODE == "recompute":
    run_recompute()
else:
    print(f"MODE desconocido: {MODE}. Usar 'audit', 'verify_staging' o 'recompute'.")
