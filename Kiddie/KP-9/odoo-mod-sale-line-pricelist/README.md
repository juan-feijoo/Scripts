# odoo-mod-sale-line-pricelist

Módulo para Odoo 19.0 Enterprise que permite seleccionar una lista de precios (`product.pricelist`) independiente por cada línea de cotización y orden de venta (`sale.order.line`).

## Características Técnicas (Odoo 19.0)
- **Campo `pricelist_id` + `pricelist_follows_order` en `sale.order.line`**: Por defecto la línea sigue a la lista del pedido; al seleccionar otra lista en el renglón deja de seguirla y recalcula el precio.
- **`pre_init_hook` en SQL (`hooks.py`)**: Crea e inicializa las columnas directamente en PostgreSQL al instalar el módulo para evitar que el ORM recalcule o modifique precios de pedidos históricos o confirmados.
- **Multimoneda nativo de Odoo 19.0**: Evalúa la regla de la lista en su propia moneda mediante `_get_pricelist_kwargs()` (necesario en Odoo 19 porque `product.pricelist.item._compute_price` no convierte `fixed_price` ni `price_surcharge`) y convierte el resultado a la moneda del pedido con `_convert_to_sol_currency()`.
- **Protección de precios manuales (`technical_price_unit`)**: Al cambiar la lista en la línea (vía UI `@api.onchange` o vía `write()`), pasa `force_price_recomputation=True` para recalcular incluso si el usuario había editado el precio a mano previamente. Ante cambios posteriores de cantidad, conserva la protección de edición manual de Odoo 19.
- **Actualización de precios (`action_update_prices`)**: Recalcula cada renglón respetando su propia lista asignada.
