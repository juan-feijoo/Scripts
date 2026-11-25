# KP-13: Normalización de Costos y Listas de Precio para Productos con Desglose

Este repositorio / suite contiene las herramientas completas de diagnóstico, simulación (`DRY_RUN=1`) y actualización persistente (`DRY_RUN=0`) para resolver la discrepancia de costos y listas de precios en productos con venta por bulto y desglose en **Odoo 19 Enterprise (Odoo.sh)**.

Consulte la guía completa y el paso a paso en [INSTRUCCIONES_ODOSH.md](file:///c:/Users/juanf/Documents/Scripts/Kiddie/KP-13_costos_desglose/INSTRUCCIONES_ODOSH.md).

## Archivos Principales
- `instalar_en_sh.sh`: Script instalador para pegar en el shell de Odoo.sh.
- `run_all.sh`: Runner por lotes.
- `datos_costos_desglose.json`: Extracción limpia de los 969 productos con desglose.
- `scripts/`: Scripts ejecutables para `odoo-bin shell`.
