import sys
import os
import django
from decimal import Decimal
from datetime import date

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sbr_dos.settings')
django.setup()

from Aplicaciones.sbr_app_dos.models import Cliente, Contrato, Cuota, Pago, User
from Aplicaciones.sbr_app_dos.services import registrar_pago_cliente, generar_tabla_amortizacion

def run_test():
    print("--- STARTING REPRODUCTION TEST ---")
    
    # 1. Setup Test Data
    user = User.objects.first()
    if not user:
        user = User.objects.create_superuser('admin_test', 'admin@test.com', 'password')

    cliente, _ = Cliente.objects.get_or_create(
        cedula="9999999999",
        defaults={
            "nombres": "Test", "apellidos": "Bug", 
            "celular": "000", "direccion": "Test",
            "vendedor": user
        }
    )
    
    # Create Contract with 3 quotas of $500 each
    contrato = Contrato.objects.create(
        cliente=cliente,
        fecha_contrato=date.today(),
        precio_venta_final=Decimal('1500.00'),
        valor_entrada=Decimal('0.00'),
        saldo_a_financiar=Decimal('1500.00'),
        numero_cuotas=3,
        estado='ACTIVO'
    )
    
    # Generate Quotas manually to be exact
    Cuota.objects.create(contrato=contrato, numero_cuota=1, fecha_vencimiento=date.today(), valor_capital=Decimal('500.00'), valor_pagado=0, estado='PENDIENTE')
    Cuota.objects.create(contrato=contrato, numero_cuota=2, fecha_vencimiento=date.today(), valor_capital=Decimal('500.00'), valor_pagado=0, estado='PENDIENTE')
    Cuota.objects.create(contrato=contrato, numero_cuota=3, fecha_vencimiento=date.today(), valor_capital=Decimal('500.00'), valor_pagado=0, estado='PENDIENTE')
    
    print(f"Contract {contrato.id} created with 3 quotas of $500.")
    
    # 2. Execute Payment of $700
    # Expected: 
    # - Quota 1: Paid $500 (Full)
    # - Quota 2: Paid $200 (Partial)
    # - Quota 3: Paid $0 (Touched? NO)
    
    print("Registering payment of $700...")
    registrar_pago_cliente(
        contrato_id=contrato.id,
        monto=Decimal('700.00'),
        metodo_pago='EFECTIVO',
        evidencia_img=None,
        usuario_vendedor=user
    )
    
    # 3. Verify Results
    q1 = Cuota.objects.get(contrato=contrato, numero_cuota=1)
    q2 = Cuota.objects.get(contrato=contrato, numero_cuota=2)
    q3 = Cuota.objects.get(contrato=contrato, numero_cuota=3)
    
    print(f"Quota 1 Paid: {q1.valor_pagado} (Expected: 500.00)")
    print(f"Quota 2 Paid: {q2.valor_pagado} (Expected: 200.00)")
    print(f"Quota 3 Paid: {q3.valor_pagado} (Expected: 0.00)")
    
    if q3.valor_pagado > 0:
        print("FAIL: Quota 3 received payment! Bug reproduced.")
    elif q2.valor_pagado != 200:
        print("FAIL: Quota 2 has incorrect payment.")
    else:
        print("PASS: Logic correct (or bug not reproduced).")

    # Cleanup
    contrato.delete()
    cliente.delete()

if __name__ == '__main__':
    try:
        run_test()
    except Exception as e:
        print(f"Error: {e}")
