import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from decimal import Decimal
from Aplicaciones.sbr_app_dos.models import Contrato

total_general = Decimal('0.00')

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
        total_general -= total_pagado
    else:
        total_general += total_pagado

print(f"TOTAL GENERAL (Exact Python Logic): {total_general}")
