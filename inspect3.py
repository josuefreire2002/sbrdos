import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from Aplicaciones.sbr_app_dos.models import Contrato, Pago, Cuota

c = Contrato.objects.get(id=3)
print(f"--- CONTRATO #3 ---")
print(f"Saldo a financiar: {c.saldo_a_financiar}")
print(f"Total pagado caja: {sum(p.monto for p in c.pago_set.filter(es_entrada=False))}")
print("Pagos:")
for p in c.pago_set.all():
    print(f"  ID:{p.id} | Monto:{p.monto} | Entrada:{p.es_entrada}")
print("Cuotas con pago:")
for cu in c.cuotas.filter(valor_pagado__gt=0):
    print(f"  #{cu.numero_cuota} | Aplicado:{cu.valor_pagado}")
