import os
import django
from decimal import Decimal
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sbr_dos.settings')
django.setup()

from Aplicaciones.sbr_app_dos.models import Cliente, Contrato, Cuota, Pago, User

def run_experiment():
    print("--- EXPERIMENT: MULTIPLE PARTIAL PAYMENTS ---")
    
    # Setup
    user = User.objects.first() or User.objects.create_superuser('admin_test2', 'a@b.com', 'pass')
    cliente, _ = Cliente.objects.get_or_create(cedula="8888888888", defaults={"nombres": "Hist", "apellidos": "Test", "vendedor": user})
    Contrato.objects.filter(cliente=cliente).delete()
    
    contrato = Contrato.objects.create(
        cliente=cliente, fecha_contrato=date.today(),
        precio_venta_final=Decimal('500.00'), valor_entrada=0, saldo_a_financiar=Decimal('500.00'),
        numero_cuotas=1, estado='ACTIVO' # Just 1 quota of $500
    )
    
    # Create Quota manually
    q1 = Cuota.objects.create(
        contrato=contrato, numero_cuota=1, fecha_vencimiento=date.today(),
        valor_capital=Decimal('500.00'), valor_pagado=0, estado='PENDIENTE'
    )
    
    # Execute Payments
    # 1. $100
    p1 = registrar_pago_cliente(contrato.id, Decimal('100.00'), 'EFECTIVO', None, user)
    # 2. $200
    p2 = registrar_pago_cliente(contrato.id, Decimal('200.00'), 'EFECTIVO', None, user)
    # 3. $300
    p3 = registrar_pago_cliente(contrato.id, Decimal('300.00'), 'EFECTIVO', None, user)
    
    print(f"Payment 1: ID {p1.id}, Num Transaccion {p1.numero_transaccion}")
    print(f"Payment 2: ID {p2.id}, Num Transaccion {p2.numero_transaccion}")
    print(f"Payment 3: ID {p3.id}, Num Transaccion {p3.numero_transaccion}")

    if p1.numero_transaccion == 1 and p2.numero_transaccion == 2 and p3.numero_transaccion == 3:
        print("PASS: Transaction numbers are sequential (1, 2, 3).")
    else:
        print("FAIL: Transaction numbers are incorrect.")
    
    q1.refresh_from_db()
    print(f"Quota 1 Status: {q1.estado}, Paid: {q1.valor_pagado}")
    
    # Verify Details
    detalles = q1.pagos_asociados.all().order_by('id')
    print(f"Number of payment details: {detalles.count()}")
    for d in detalles:
        print(f" - Detail ID {d.id} from Payment {d.pago.id} (${d.pago.monto}): Applied ${d.monto_aplicado}")

    # Check View Logic Simulation
    # Is it primary?
    # Map logic
    pago_inicio_map = {}
    from Aplicaciones.sbr_app_dos.models import DetallePago
    all_dets = DetallePago.objects.filter(pago__contrato=contrato)
    for d in all_dets:
        pid = d.pago_id
        q_num = d.cuota.numero_cuota
        if pid not in pago_inicio_map: pago_inicio_map[pid] = q_num
        else:
             if q_num < pago_inicio_map[pid]: pago_inicio_map[pid] = q_num
             
    # Check for Q1
    is_primary = False
    origenes = set()
    for d in detalles:
        start = pago_inicio_map.get(d.pago_id)
        print(f"   -> Payment {d.pago_id} started at Quota #{start}")
        if start == q1.numero_cuota:
            is_primary = True
        else:
            origenes.add(start)
            
    print(f"Is Primary? {is_primary}")
    print(f"Origenes: {origenes}")

    if detalles.count() == 3 and is_primary:
        print("PASS: 3 records found and quota is primary.")
    else:
        print("FAIL: Counts or logic mismatch.")

from Aplicaciones.sbr_app_dos.services import registrar_pago_cliente

if __name__ == '__main__':
    run_experiment()
