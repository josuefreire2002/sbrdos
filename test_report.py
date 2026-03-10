import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sbr_app_dos.settings')
django.setup()

from sbr_app_dos.models import Contrato, Cuota, Pago, DetallePago

contratos = Contrato.objects.all()[:1]
if contratos.exists():
    c = contratos[0]
    print(f"Contrato: {c.id} - Cliente: {c.cliente.nombres}")
    for cuota in c.cuotas.all()[:5]:
        print(f"Cuota {cuota.numero_cuota} (Vence: {cuota.fecha_vencimiento}) - A Pagar: {cuota.total_a_pagar} | Pagado: {cuota.valor_pagado}")
        
    print("\nPagos registrados:")
    for pago in c.pago_set.all():
        print(f" Pago {pago.id} en fecha {pago.fecha_pago} por ${pago.monto}")
        for d in pago.detalles.all():
            print(f"   -> Aplica a Cuota {d.cuota.numero_cuota} (${d.monto_aplicado})")
