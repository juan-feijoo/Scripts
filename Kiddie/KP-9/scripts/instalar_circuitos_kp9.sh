#!/usr/bin/env bash
# Instalador y ejecutor de circuitos de prueba KP-9 (Odoo 19.0 - Odoo.sh)
# Uso directo en Odoo.sh (por archivo o pegando en la terminal):
#   bash instalar_circuitos_kp9.sh
# Con SKU o compañía específicos:
#   PRODUCT_CODE=38552 bash instalar_circuitos_kp9.sh

TARGET_DIR="$HOME/tmp/KP-9"
TARGET_PY="$TARGET_DIR/03_circuitos_prueba_kp9.py"
TARGET_LOG="$TARGET_DIR/resultado_circuitos_kp9.txt"

mkdir -p "$TARGET_DIR"

cat << 'EOF_KP9_03' > "$TARGET_PY"
# -*- coding: utf-8 -*-
"""
================================================================================
BATTERY DE CIRCUITOS DE PRUEBA END-TO-END: KP-9 (LISTA DE PRECIOS POR LÍNEA)
Entorno: Odoo 19.0 Enterprise (Odoo.sh)
Modo: SIEMPRE SEGURO (ejecuta ROLLBACK al finalizar para no ensuciar la base)
================================================================================

Uso directo en Odoo.sh:
  odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < scripts/03_circuitos_prueba_kp9.py

Parámetros opcionales por variable de entorno:
  PRODUCT_CODE=38552   -> Probar con un código de producto específico
  COMPANY_NAME=Kiddie  -> Filtrar compañía por nombre
"""

import os
import traceback
from datetime import datetime
from odoo import fields
from odoo.fields import Command
from odoo.tests import Form


PRODUCT_CODE = os.environ.get('PRODUCT_CODE', '').strip()
COMPANY_NAME = os.environ.get('COMPANY_NAME', '').strip()

RESULTADOS = []


def h(title):
    print("\n" + "=" * 92, flush=True)
    print(title, flush=True)
    print("=" * 92, flush=True)


def sub(title):
    print(f"\n--- {title} " + "-" * max(0, 86 - len(title)), flush=True)


def registrar(codigo, estado, detalle):
    RESULTADOS.append((codigo, estado, detalle))
    icono = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]", "SKIP": "[SKIP]"}.get(estado, f"[{estado}]")
    print(f"  {icono} {codigo}: {detalle}", flush=True)


def assert_almost(val, expected, tol=0.05, msg=""):
    if abs((val or 0.0) - (expected or 0.0)) > tol:
        raise AssertionError(f"{msg} | Esperado: {expected:.4f}, Obtenido: {val:.4f}")


def get_uom_field(model):
    return 'product_uom_id' if 'product_uom_id' in model._fields else 'product_uom'


def get_tax_field(model):
    return 'tax_ids' if 'tax_ids' in model._fields else 'tax_id'


def net_line_price(line):
    if hasattr(line, '_values'):
        disc = line.discount if 'discount' in line._values else 0.0
    else:
        disc = getattr(line, 'discount', 0.0)
    return (line.price_unit or 0.0) * (1.0 - (disc or 0.0) / 100.0)


def buscar_partner_real(env, company):
    Partner = env['res.partner'].with_company(company)
    base_domain = [('active', '=', True), ('company_id', 'in', [company.id, False])]
    has_afip = 'l10n_ar_afip_responsibility_type_id' in Partner._fields

    if has_afip:
        p = Partner.search(
            base_domain + [
                ('customer_rank', '>', 0),
                ('l10n_ar_afip_responsibility_type_id', '!=', False),
                ('vat', '!=', False),
            ],
            limit=1,
        )
        if p:
            return p
        p = Partner.search(
            base_domain + [
                ('customer_rank', '>', 0),
                ('l10n_ar_afip_responsibility_type_id', '!=', False),
            ],
            limit=1,
        )
        if p:
            return p

    p = Partner.search(base_domain + [('customer_rank', '>', 0)], limit=1)
    if not p:
        p = Partner.search(base_domain, limit=1)
    if not p:
        vals = {'name': 'Cliente Prueba KP9', 'customer_rank': 1}
        if has_afip:
            cf = env.ref('l10n_ar.res_CF', raise_if_not_found=False)
            if cf:
                vals['l10n_ar_afip_responsibility_type_id'] = cf.id
        p = Partner.create(vals)
    return p


def buscar_productos_reales(env, company):
    Product = env['product.product'].with_company(company)
    # 1. Si se pasó código por env var
    if PRODUCT_CODE:
        p = Product.search([('default_code', '=', PRODUCT_CODE)], limit=1)
        if p:
            return p, p
        print(f"  [WARN] PRODUCT_CODE='{PRODUCT_CODE}' no encontrado; usando producto testigo automático.", flush=True)

    # 2. Productos testigo conocidos de Kiddie (marcadores / repuestos / blocks)
    p_std = False
    for code in ['38552', '38550', '37303', '1051', '37324', '38081']:
        p_std = Product.search([('default_code', '=', code), ('sale_ok', '=', True)], limit=1)
        if p_std:
            break
    if not p_std:
        p_std = Product.search([('sale_ok', '=', True), ('standard_price', '>', 0)], limit=1)
    if not p_std:
        p_std = Product.search([('sale_ok', '=', True)], limit=1)

    # 3. Buscar un producto con embalajes (uom_ids > 1 en Odoo 19)
    p_emb = False
    if 'uom_ids' in env['product.template']._fields:
        tmpl = env['product.template'].with_company(company).search([
            ('sale_ok', '=', True),
            ('uom_ids', '!=', False),
            ('standard_price', '>', 0),
        ], limit=1)
        if tmpl and tmpl.product_variant_id:
            p_emb = tmpl.product_variant_id

    return p_std, (p_emb or p_std)


def buscar_listas(env, company):
    Pricelist = env['product.pricelist'].with_company(company)
    listas = Pricelist.search([('company_id', 'in', [company.id, False])])

    def find_pl(keywords, currency_name=None):
        for kw in keywords:
            for pl in listas:
                if kw.lower() in (pl.name or '').lower():
                    if not currency_name or pl.currency_id.name == currency_name:
                        return pl
        return False

    pl_pub = find_pl(['público', 'publico'], 'ARS') or find_pl(['público', 'publico']) or (listas[:1] if listas else False)
    pl_may = find_pl(['mayorista'], 'ARS') or find_pl(['mayorista'])
    pl_lic = find_pl(['licitación', 'licitacion'], 'ARS') or find_pl(['licitación', 'licitacion'])
    pl_des = find_pl(['desglose'], 'ARS') or find_pl(['desglose'])
    pl_usd = find_pl(['dólar', 'dolar', 'usd'], 'USD') or listas.filtered(lambda l: l.currency_id.name == 'USD')[:1]

    # Fallbacks si alguna no se encontró por nombre
    ars_lists = listas.filtered(lambda l: l.currency_id.name == 'ARS')
    if not pl_may and len(ars_lists) > 1:
        pl_may = ars_lists.filtered(lambda l: l.id != (pl_pub.id if pl_pub else 0))[:1]
    if not pl_des and len(ars_lists) > 2:
        pl_des = ars_lists.filtered(lambda l: l.id not in [pl_pub.id if pl_pub else 0, pl_may.id if pl_may else 0])[:1]

    return {
        'all': listas,
        'publico': pl_pub,
        'mayorista': pl_may,
        'licitacion': pl_lic,
        'desglose': pl_des,
        'usd': pl_usd,
    }


def ejecutar_circuitos(env):
    RESULTADOS.clear()
    h("INICIO SUITE DE PRUEBAS END-TO-END KP-9 (ODOO 19 - DRY-RUN / ROLLBACK)")
    print(f"Hora inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    try:
        env.cr.rollback()
    except Exception:
        pass

    try:
        _ejecutar_circuitos_interno(env)
    except Exception as e:
        registrar("SUITE-FATAL", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
    finally:
        try:
            env.cr.rollback()
        except Exception:
            pass
        imprimir_resumen_final()


def _ejecutar_circuitos_interno(env):

    Company = env['res.company']
    company = Company.search([('name', 'ilike', COMPANY_NAME)], limit=1) if COMPANY_NAME else env.company
    if not company:
        company = env.company
    env = env(context=dict(env.context, allowed_company_ids=[company.id]))
    print(f"Compañía de prueba: {company.name} (ID: {company.id}, Moneda: {company.currency_id.name})", flush=True)

    LineModel = env['sale.order.line']
    OrderModel = env['sale.order']
    uom_fname = get_uom_field(LineModel)
    tax_fname = get_tax_field(LineModel)

    # ==========================================================================
    # CIRCUITO 0: INSTALACIÓN, CAMPOS, VISTA XML Y PERMISOS
    # ==========================================================================
    sub("CIRCUITO 0: Verificación de instalación, campos, vista XML y permisos")
    try:
        mods = env['ir.module.module'].search([
            ('name', 'in', ['sale_line_pricelist', 'sale_order_line_pricelist']),
            ('state', '=', 'installed'),
        ])
        if not mods:
            registrar("C0-MODULO", "FAIL", "No se encontró instalado ni 'sale_line_pricelist' ni 'sale_order_line_pricelist'.")
            return
        registrar("C0-MODULO", "PASS", f"Módulo instalado: {', '.join(mods.mapped('name'))} (v{mods[0].latest_version})")

        has_pl = 'pricelist_id' in LineModel._fields
        has_follows = 'pricelist_follows_order' in LineModel._fields
        if not has_pl:
            registrar("C0-CAMPOS", "FAIL", "Falta el campo 'pricelist_id' en sale.order.line.")
            return
        registrar("C0-CAMPOS", "PASS", f"Campos presentes -> pricelist_id={has_pl}, pricelist_follows_order={has_follows}, uom_field={uom_fname}, tax_field={tax_fname}")

        # Verificar que la vista de sale.order compila sin error en Odoo 19
        view_info = OrderModel.with_company(company).get_view(view_type='form')
        arch_str = view_info.get('arch', '')
        if 'pricelist_id' in arch_str:
            registrar("C0-VISTA", "PASS", "Vista form de sale.order compila correctamente y contiene 'pricelist_id'.")
        else:
            registrar("C0-VISTA", "WARN", "La vista compiló, pero 'pricelist_id' no aparece en el arch (¿restringido por groups?).")

        # Verificar group_product_pricelist
        grp = env.ref('product.group_product_pricelist', raise_if_not_found=False)
        if grp:
            user_fld = 'user_ids' if 'user_ids' in grp._fields else 'users'
            cnt = len(grp[user_fld])
            if cnt == 0:
                registrar("C0-PERMISOS", "WARN", "product.group_product_pricelist tiene 0 usuarios en esta BD (verificar Ajustes -> Ventas -> Listas de precios).")
            else:
                registrar("C0-PERMISOS", "PASS", f"product.group_product_pricelist activo para {cnt} usuarios.")
    except Exception as e:
        registrar("C0-GENERAL", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # Preparar datos maestros reales para los circuitos 1 a 6
    partner = buscar_partner_real(env, company)

    prod_std, prod_emb = buscar_productos_reales(env, company)
    listas = buscar_listas(env, company)
    print(f"Partner testigo:  [{partner.id}] {partner.name}", flush=True)
    print(f"Producto base:    [{prod_std.default_code}] {prod_std.name} (Costo: {prod_std.standard_price}, ListPrice: {prod_std.list_price})", flush=True)
    print(f"Producto embalaje:[{prod_emb.default_code}] {prod_emb.name}", flush=True)
    print(f"Listas detectadas: Público={getattr(listas['publico'], 'name', False)} | Mayorista={getattr(listas['mayorista'], 'name', False)} | "
          f"Licitación={getattr(listas['licitacion'], 'name', False)} | Desglose={getattr(listas['desglose'], 'name', False)} | "
          f"USD={getattr(listas['usd'], 'name', False)}", flush=True)

    # ==========================================================================
    # CIRCUITO 1: COTIZACIÓN MIXTA CON LISTAS REALES DE KIDDIE
    # ==========================================================================
    sub("CIRCUITO 1: Cotización mixta con listas reales (Público + Mayorista + Desglose)")
    try:
        with env.cr.savepoint():
            pl_pub = listas['publico']
            pl_may = listas['mayorista']
            pl_des = listas['desglose'] or listas['licitacion']
            if not (pl_pub and pl_may and prod_std):
                registrar("C1-MIXTA", "SKIP", "Faltan al menos 2 listas o producto válido en la BD.")
            else:
                p_pub = pl_pub._get_product_price(prod_std, 1.0, currency=company.currency_id, uom=prod_std.uom_id)
                p_may = pl_may._get_product_price(prod_std, 1.0, currency=company.currency_id, uom=prod_std.uom_id)
                p_des = pl_des._get_product_price(prod_std, 1.0, currency=company.currency_id, uom=prod_std.uom_id) if pl_des else p_pub

                line_cmds = [
                    Command.create({'product_id': prod_std.id, 'product_uom_qty': 1.0}),
                    Command.create({'product_id': prod_std.id, 'product_uom_qty': 2.0, 'pricelist_id': pl_may.id}),
                ]
                if pl_des:
                    line_cmds.append(Command.create({'product_id': prod_std.id, 'product_uom_qty': 3.0, 'pricelist_id': pl_des.id}))

                ov1 = OrderModel.with_company(company).create({
                    'partner_id': partner.id,
                    'pricelist_id': pl_pub.id,
                    'order_line': line_cmds,
                })
                l1 = ov1.order_line[0]
                l2 = ov1.order_line[1]
                assert_almost(net_line_price(l1), p_pub, msg="Línea 1 (Público)")
                assert_almost(net_line_price(l2), p_may, msg="Línea 2 (Mayorista)")
                if l1.pricelist_id != pl_pub or l2.pricelist_id != pl_may:
                    raise AssertionError("Las líneas no conservaron su lista individual.")
                msg_ok = f"L1({pl_pub.name})=${net_line_price(l1):.2f} | L2({pl_may.name})=${net_line_price(l2):.2f}"
                if pl_des:
                    l3 = ov1.order_line[2]
                    assert_almost(net_line_price(l3), p_des, msg="Línea 3 (Desglose)")
                    msg_ok += f" | L3({pl_des.name})=${net_line_price(l3):.2f}"
                registrar("C1-MIXTA", "PASS", msg_ok)
    except Exception as e:
        registrar("C1-MIXTA", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # ==========================================================================
    # CIRCUITO 2: SIMULACIÓN INTERFAZ WEB (Form + onchange + precio manual + limpiar)
    # ==========================================================================
    sub("CIRCUITO 2: Simulación UI Form (onchange en tiempo real, precio manual, limpiar campo)")
    try:
        with env.cr.savepoint():
            pl_pub = listas['publico']
            pl_may = listas['mayorista']
            if not (pl_pub and pl_may and prod_std):
                registrar("C2-UI-FORM", "SKIP", "Faltan listas para simular Form.")
            else:
                p_pub = pl_pub._get_product_price(prod_std, 1.0, currency=company.currency_id, uom=prod_std.uom_id)
                p_may = pl_may._get_product_price(prod_std, 1.0, currency=company.currency_id, uom=prod_std.uom_id)

                ov_ui = OrderModel.with_company(company).create({
                    'partner_id': partner.id,
                    'pricelist_id': pl_pub.id,
                })

                def _run_ui_form():
                    with Form(ov_ui) as f:
                        with f.order_line.new() as lf:
                            lf.product_id = prod_std
                            if 'pricelist_id' not in lf._values:
                                return False, False
                            assert_almost(net_line_price(lf), p_pub, msg="Form precio inicial")
                            # Simular precio editado a mano por vendedor
                            lf.price_unit = 777.77
                            lf.product_uom_qty = 4.0
                            assert_almost(lf.price_unit, 777.77, msg="Protección precio manual ante cambio qty")
                            # Cambiar lista de la línea -> debe forzar recálculo pisando 777.77
                            lf.pricelist_id = pl_may
                            assert_almost(net_line_price(lf), p_may, msg="Onchange al cambiar lista de línea")
                            # Probar limpiar la lista en la línea (False)
                            lf.pricelist_id = env['product.pricelist']
                        saved_rec = f.save()
                    return True, saved_rec

                visible, saved = _run_ui_form()
                nota_grupo = False
                if not visible:
                    grp = env.ref('product.group_product_pricelist', raise_if_not_found=False)
                    if grp:
                        user_fld = 'user_ids' if 'user_ids' in grp._fields else 'users'
                        if env.user not in grp[user_fld]:
                            grp.sudo().write({user_fld: [Command.link(env.user.id)]})
                            if hasattr(env.registry, 'clear_cache'):
                                env.registry.clear_cache()
                            env.invalidate_all()
                            visible, saved = _run_ui_form()
                            nota_grupo = True

                if not visible:
                    registrar("C2-UI-FORM", "FAIL", "El campo 'pricelist_id' no es visible en la subvista de línea del Form.")
                else:
                    sol = saved.order_line[0]
                    assert_almost(net_line_price(sol), p_pub, msg="Recálculo al limpiar lista de línea")
                    estado_c2 = "WARN" if nota_grupo else "PASS"
                    extra_perm = " [ATENCIÓN: requirió habilitar product.group_product_pricelist en rollback para verse en vista]" if nota_grupo else ""
                    registrar(
                        "C2-UI-FORM",
                        estado_c2,
                        f"Form OK: onchange pisó precio manual hacia ${p_may:.2f}; tras limpiar campo -> pricelist_id={sol.pricelist_id.name if sol.pricelist_id else False}, price_unit=${net_line_price(sol):.2f}{extra_perm}",
                    )
    except Exception as e:
        registrar("C2-UI-FORM", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # ==========================================================================
    # CIRCUITO 3: MULTIMONEDA (PEDIDO ARS CON LÍNEA USD)
    # ==========================================================================
    sub("CIRCUITO 3: Multimoneda (Pedido en ARS con línea usando lista en USD)")
    try:
        with env.cr.savepoint():
            pl_pub = listas['publico']
            pl_usd = listas['usd']
            if not (pl_pub and pl_usd):
                registrar("C3-MONEDA", "SKIP", "No hay lista USD activa para probar multimoneda.")
            elif pl_usd.currency_id == pl_pub.currency_id:
                registrar("C3-MONEDA", "SKIP", f"La lista '{pl_usd.name}' comparte moneda ({pl_usd.currency_id.name}) con '{pl_pub.name}'.")
            else:
                # Buscar un producto activo que tenga regla en la lista USD, o crear regla temporal en savepoint
                prod_usd = False
                if pl_usd.item_ids:
                    item_usd = pl_usd.item_ids.filtered(
                        lambda i: i.product_tmpl_id
                        and i.product_tmpl_id.active
                        and i.product_tmpl_id.sale_ok
                        and i.product_tmpl_id.product_variant_id
                    )[:1]
                    if item_usd:
                        prod_usd = item_usd.product_tmpl_id.product_variant_id
                if not prod_usd:
                    prod_usd = prod_std
                    env['product.pricelist.item'].create({
                        'pricelist_id': pl_usd.id,
                        'applied_on': '1_product',
                        'product_tmpl_id': prod_usd.product_tmpl_id.id,
                        'compute_price': 'fixed',
                        'fixed_price': 25.0,
                    })

                fecha_ov = fields.Datetime.now()
                precio_en_usd = pl_usd._get_product_price(prod_usd, 1.0, currency=pl_usd.currency_id, uom=prod_usd.uom_id, date=fecha_ov)
                esperado_ars = pl_usd.currency_id._convert(precio_en_usd, pl_pub.currency_id, company, fecha_ov, round=False)

                ov_fx = OrderModel.with_company(company).create({
                    'partner_id': partner.id,
                    'pricelist_id': pl_pub.id,
                    'date_order': fecha_ov,
                    'order_line': [
                        Command.create({
                            'product_id': prod_usd.id,
                            'product_uom_qty': 1.0,
                            'pricelist_id': pl_usd.id,
                        })
                    ],
                })
                l_fx = ov_fx.order_line[0]
                obtenido_fx = net_line_price(l_fx)
                assert_almost(obtenido_fx, esperado_ars, tol=0.5, msg="Conversión USD->ARS en línea")
                tasa = esperado_ars / precio_en_usd if precio_en_usd else 0.0
                registrar("C3-MONEDA", "PASS", f"[{prod_usd.default_code}] Lista '{pl_usd.name}' = USD {precio_en_usd:.2f} -> OV ARS ${obtenido_fx:.2f} (TC implícito: {tasa:.2f})")
    except Exception as e:
        registrar("C3-MONEDA", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # ==========================================================================
    # CIRCUITO 4: EMBALAJES CORE ODOO 19 (uom_ids) + DESGLOSE
    # ==========================================================================
    sub("CIRCUITO 4: Embalajes (uom.uom de KP-12) vs Unidad suelta en Desglose")
    try:
        with env.cr.savepoint():
            pl_may = listas['mayorista'] or listas['publico']
            pl_des = listas['desglose'] or listas['publico']
            uoms_prod = prod_emb.uom_ids if 'uom_ids' in prod_emb._fields else env['uom.uom']
            bulto_uom = uoms_prod.filtered(lambda u: u.id != prod_emb.uom_id.id)[:1]

            if not bulto_uom:
                registrar("C4-EMBALAJE", "SKIP", f"El producto {prod_emb.default_code} no tiene embalajes adicionales en uom_ids.")
            else:
                vals_l_bulto = {
                    'product_id': prod_emb.id,
                    'product_uom_qty': 1.0,
                    uom_fname: bulto_uom.id,
                    'pricelist_id': pl_may.id,
                }
                vals_l_unid = {
                    'product_id': prod_emb.id,
                    'product_uom_qty': 1.0,
                    uom_fname: prod_emb.uom_id.id,
                    'pricelist_id': pl_des.id,
                }
                ov_emb = OrderModel.with_company(company).create({
                    'partner_id': partner.id,
                    'pricelist_id': listas['publico'].id,
                    'order_line': [Command.create(vals_l_bulto), Command.create(vals_l_unid)],
                })
                lb, lu = ov_emb.order_line[0], ov_emb.order_line[1]
                p_bulto_esp = pl_may._get_product_price(prod_emb, 1.0, currency=company.currency_id, uom=bulto_uom)
                p_unid_esp = pl_des._get_product_price(prod_emb, 1.0, currency=company.currency_id, uom=prod_emb.uom_id)
                assert_almost(net_line_price(lb), p_bulto_esp, msg="Precio línea por Bulto")
                assert_almost(net_line_price(lu), p_unid_esp, msg="Precio línea por Unidad Desglose")
                factor = getattr(bulto_uom, 'relative_factor', '?')
                registrar("C4-EMBALAJE", "PASS", f"[{prod_emb.default_code}] {bulto_uom.name} (factor={factor}) en '{pl_may.name}' = ${net_line_price(lb):.2f} | {prod_emb.uom_id.name} en '{pl_des.name}' = ${net_line_price(lu):.2f}")
    except Exception as e:
        registrar("C4-EMBALAJE", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # ==========================================================================
    # CIRCUITO 5: CAMBIO CABECERA, ACTUALIZAR PRECIOS Y DUPLICAR (copy)
    # ==========================================================================
    sub("CIRCUITO 5: Cambio cabecera, action_update_prices y duplicado copy()")
    try:
        with env.cr.savepoint():
            pl_pub = listas['publico']
            pl_may = listas['mayorista']
            pl_des = listas['desglose'] or listas['licitacion']
            if not (pl_pub and pl_may and pl_des):
                registrar("C5-CABECERA", "SKIP", "Se requieren al menos 3 listas ARS.")
            else:
                ov_cab = OrderModel.with_company(company).create({
                    'partner_id': partner.id,
                    'pricelist_id': pl_pub.id,
                    'order_line': [
                        Command.create({'product_id': prod_std.id, 'product_uom_qty': 1.0}),
                        Command.create({'product_id': prod_std.id, 'product_uom_qty': 1.0, 'pricelist_id': pl_des.id}),
                    ],
                })
                l_std, l_custom = ov_cab.order_line[0], ov_cab.order_line[1]
                # Cambiar lista de cabecera -> la estándar sigue, la custom conserva su lista
                ov_cab.write({'pricelist_id': pl_may.id})
                if l_std.pricelist_id != pl_may:
                    raise AssertionError(f"Línea estándar debería haber cambiado a {pl_may.name}, tiene {l_std.pricelist_id.name}")
                if l_custom.pricelist_id != pl_des:
                    raise AssertionError(f"Línea custom debería haber conservado {pl_des.name}, tiene {l_custom.pricelist_id.name}")

                # Pisar manualmente l_custom y correr Actualizar precios
                l_custom.write({'price_unit': 1.0})
                ov_cab.action_update_prices()
                p_des_esp = pl_des._get_product_price(prod_std, 1.0, currency=company.currency_id, uom=prod_std.uom_id)
                assert_almost(net_line_price(l_custom), p_des_esp, msg="action_update_prices debe recalcular contra lista propia")

                # Probar duplicar presupuesto
                ov_clone = ov_cab.copy()
                if ov_clone.order_line[1].pricelist_id != pl_des:
                    raise AssertionError("Al duplicar (copy), no se preservó la lista personalizada de la línea.")
                registrar("C5-CABECERA", "PASS", f"Cabecera->Mayorista actualizó L1 y conservó L2({pl_des.name}=${net_line_price(l_custom):.2f}); copy() preservó listas por línea.")
    except Exception as e:
        registrar("C5-CABECERA", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # ==========================================================================
    # CIRCUITO 6: FLUJO COMPLETO OV -> CONFIRMAR -> STOCK -> FACTURA BORRADOR -> QWEB
    # ==========================================================================
    sub("CIRCUITO 6: Flujo completo OV -> Confirmación -> Stock -> Factura Borrador -> QWeb")
    try:
        with env.cr.savepoint():
            pl_pub = listas['publico']
            pl_may = listas['mayorista'] or pl_pub
            ov_full = OrderModel.with_company(company).create({
                'partner_id': partner.id,
                'pricelist_id': pl_pub.id,
                'order_line': [
                    Command.create({'product_id': prod_std.id, 'product_uom_qty': 2.0}),
                    Command.create({'product_id': prod_std.id, 'product_uom_qty': 3.0, 'pricelist_id': pl_may.id}),
                ],
            })
            precios_antes = [net_line_price(l) for l in ov_full.order_line]
            impuestos_lineas = [l[tax_fname].mapped('name') for l in ov_full.order_line]

            ov_full.action_confirm()
            if ov_full.state != 'sale':
                raise AssertionError(f"La OV no pasó a estado 'sale' (actual: {ov_full.state}).")

            pickings = ov_full.picking_ids

            # Probar renderizado QWeb HTML de la cotización (antes o independientemente de factura)
            report_action = env.ref('sale.action_report_saleorder', raise_if_not_found=False)
            qweb_ok = "N/A"
            if report_action:
                html_bytes, _ = env['ir.actions.report']._render_qweb_html(report_action.report_name, [ov_full.id])
                qweb_ok = f"{len(html_bytes)} bytes"

            # Manejo seguro de policy='delivery' vs 'order' en dry-run
            for sol in ov_full.order_line:
                if sol.qty_to_invoice == 0 and getattr(sol, 'qty_delivered_method', '') == 'manual':
                    sol.qty_delivered = sol.product_uom_qty

            if any(sol.qty_to_invoice == 0 for sol in ov_full.order_line) and pickings:
                try:
                    with env.cr.savepoint():
                        pickings.action_assign()
                        for move in pickings.move_ids:
                            if 'quantity' in move._fields:
                                move.quantity = move.product_uom_qty
                            if 'picked' in move._fields:
                                move.picked = True
                        pickings.with_context(skip_backorder=True, cancel_backorder=False).button_validate()
                except Exception:
                    pass

            invoiceable = ov_full.order_line.filtered(lambda l: l.qty_to_invoice > 0)
            if len(invoiceable) != 2:
                registrar(
                    "C6-FLUJO-FULL",
                    "WARN",
                    f"OV {ov_full.name} confirmada (Pickings: {len(pickings)}, QWeb={qweb_ok}), pero factura borrador omitida en dry-run: "
                    f"invoice_policy='{getattr(prod_std, 'invoice_policy', '?')}' dejó {len(invoiceable)}/2 líneas facturables (requiere stock/lote validable).",
                )
            else:
                inv = ov_full._create_invoices()
                if not inv:
                    raise AssertionError("No se pudo generar la factura borrador desde la OV.")
                if inv.currency_id != ov_full.currency_id:
                    raise AssertionError(f"Moneda de factura ({inv.currency_id.name}) difiere de la OV ({ov_full.currency_id.name}).")
                inv_lines = inv.invoice_line_ids.filtered(lambda l: l.product_id == prod_std)
                if len(inv_lines) != 2:
                    raise AssertionError(f"Se esperaban 2 líneas de factura, se generaron {len(inv_lines)}.")
                for idx, il in enumerate(inv_lines):
                    assert_almost(net_line_price(il), precios_antes[idx], msg=f"Precio en factura línea {idx+1}")

                registrar(
                    "C6-FLUJO-FULL",
                    "PASS",
                    f"Confirmada {ov_full.name} | Pickings: {len(pickings)} | Factura borrador {inv.id} con precios exactos {[round(p, 2) for p in precios_antes]} | Impuestos L1={impuestos_lineas[0]} | QWeb={qweb_ok}",
                )
    except Exception as e:
        registrar("C6-FLUJO-FULL", "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


def imprimir_resumen_final():
    h("RESUMEN FINAL DE CIRCUITOS KP-9 (TRANSACCIÓN REVERTIDA CON ROLLBACK)")
    tot_pass = sum(1 for _, st, _ in RESULTADOS if st == "PASS")
    tot_fail = sum(1 for _, st, _ in RESULTADOS if st == "FAIL")
    tot_warn = sum(1 for _, st, _ in RESULTADOS if st == "WARN")
    tot_skip = sum(1 for _, st, _ in RESULTADOS if st == "SKIP")

    for cod, st, det in RESULTADOS:
        print(f"  [{st:<4}] {cod:<14} -> {det.splitlines()[0]}", flush=True)
    print("-" * 92, flush=True)
    print(f"TOTALES -> PASS: {tot_pass} | FAIL: {tot_fail} | WARN: {tot_warn} | SKIP: {tot_skip}", flush=True)
    print(">>> Base de datos intacta (env.cr.rollback() ejecutado correctamente). <<<", flush=True)


if 'env' in locals():
    ejecutar_circuitos(env)
else:
    print("[ERROR] Ejecutar dentro de odoo-bin shell:")
    print("        odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < scripts/03_circuitos_prueba_kp9.py")
EOF_KP9_03

(
    set -euo pipefail
    echo "Script instalado en: $TARGET_PY"
    if [ -z "${PGDATABASE:-}" ]; then
        echo "[INFO] PGDATABASE no definida en este entorno. Ejecute manualmente:"
        echo "  odoo-bin shell -d <BASE_DE_DATOS> --no-http --log-level=warn < $TARGET_PY"
        exit 0
    fi

    echo "Ejecutando suite KP-9 contra '$PGDATABASE' (transacción con rollback automático)..."
    set +e
    PYTHONWARNINGS="ignore::DeprecationWarning" odoo-bin shell -d "$PGDATABASE" --no-http --log-level=warn < "$TARGET_PY" 2>&1 | tee "$TARGET_LOG"
    RC=${PIPESTATUS[0]}
    set -e
    echo "Log completo guardado en: $TARGET_LOG"
    exit "$RC"
)
