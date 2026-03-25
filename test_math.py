import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from decimal import Decimal
from django.db.models import Sum
from Aplicaciones.sbr_app_dos.models import Contrato, Pago

# 1. Metodo de reporte_general
total_general_reporte = Decimal('0.00')
for contrato in Contrato.objects.prefetch_related('pago_set__detalles').all():
    total_pagado = contrato.valor_entrada or Decimal('0.00')
    ids_entradas = set(contrato.pago_set.filter(es_entrada=True).values_list('id', flat=True))
    if contrato.valor_entrada > 0 and not ids_entradas:
        pago_entrada_obj_fallback = contrato.pago_set.order_by('id').first()
        if pago_entrada_obj_fallback:
            ids_entradas.add(pago_entrada_obj_fallback.id)

    for pago in contrato.pago_set.all():
        detalles = pago.detalles.all()
        if detalles.exists():
            for detalle in detalles:
                total_pagado += (detalle.monto_aplicado or Decimal('0.00'))
        elif pago.id not in ids_entradas:
            total_pagado += (pago.monto or Decimal('0.00'))
            
    if contrato.estado == 'DEVOLUCION':
        total_general_reporte -= total_pagado
    else:
        total_general_reporte += total_pagado

# 2. Metodo Aggregation simple
pagos_sanos = Pago.objects.exclude(contrato__estado='DEVOLUCION').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
pagos_devueltos = Pago.objects.filter(contrato__estado='DEVOLUCION').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
total_general_agg = pagos_sanos - pagos_devueltos

# 3. Metodo Pago con Excedentes? The simple aggregation ignores "valor_entrada" if it's not a Pago, but is there any `valor_entrada` without a `Pago`? Let's check contracts without Pagos but with valor_entrada.
contratos_sin_pagos = Contrato.objects.filter(pago__isnull=True, valor_entrada__gt=0)
suma_entradas_huerfanas = contratos_sin_pagos.aggregate(t=Sum('valor_entrada'))['t'] or Decimal('0.00')

total_general_agg_final = total_general_agg + suma_entradas_huerfanas

print(f"Total Metodo Reporte: {total_general_reporte}")
print(f"Total Metodo Simple: {total_general_agg}")
print(f"Diferencia: {total_general_reporte - total_general_agg_final}")
