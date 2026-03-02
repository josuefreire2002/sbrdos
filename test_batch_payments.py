
import os
import django
from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from Aplicaciones.sbr_app_dos.models import Cliente, User, Contrato, Cuota, Pago, DetallePago
from Aplicaciones.sbr_app_dos.services import registrar_pago_cliente, generar_tabla_amortizacion

def run_test():
    print("--- INICIO DE TEST DE PAGOS POR LOTES ---")
    
    # 1. Setup Usuario y Cliente
    user = User.objects.first()
    if not user:
        user = User.objects.create_superuser('admin_test', 'admin@test.com', 'pass')
    
    cliente, _ = Cliente.objects.get_or_create(
        cedula="9999999999",
        defaults={
            'nombres': 'Test', 
            'apellidos': 'BatchPayment', 
            'celular': '0999999999', 
            'direccion': 'Test Dir',
            'vendedor': user
        }
    )
    
    # 2. Crear Contrato
    # Escenario: 4 meses de atraso. Digamos que el contrato empezó hace 5 meses.
    fecha_inicio = date(2026, 1, 1) # Enero 1, 2026
    
    # Limpiar contratos previos de este test
    Contrato.objects.filter(cliente=cliente).delete()
    
    contrato = Contrato.objects.create(
        cliente=cliente,
        fecha_contrato=fecha_inicio,
        precio_venta_final=Decimal('2000.00'),
        valor_entrada=Decimal('0.00'),
        saldo_a_financiar=Decimal('2000.00'),
        numero_cuotas=10, # Cuotas de $200
        estado='ACTIVO'
    )
    
    # Generar cuotas: Cuota 1 (Feb), 2 (Mar), 3 (Abr), 4 (May), 5 (Jun)
    # Valor Capital: $200 cada una
    generar_tabla_amortizacion(contrato.id)
    
    # Simular que estamos en Junio 7, 2026
    # Cuotas vencidas: Feb(1), Mar(2), Abr(3), May(4). Total 4 cuotas.
    # Cuota Jun(5) vencería el 1 de Junio o Julio dependiendo de la lógica, 
    # pero asumamos para el test que 1-4 están vencidas y queremos pagarlas todas.
    
    cuotas = contrato.cuotas.all().order_by('numero_cuota')
    print(f"Cuotas generadas: {cuotas.count()}")
    for c in cuotas:
        print(f"  - #{c.numero_cuota}: Vence {c.fecha_vencimiento}, Estado: {c.estado}, Valor: {c.valor_capital}")
        
    # 3. Ejecutar Pago de $800 (Debería cubrir cuotas 1, 2, 3, 4)
    print("\n>>> Registrando pago de $800...")
    pago = registrar_pago_cliente(
        contrato_id=contrato.id,
        monto=Decimal('800.00'),
        metodo_pago='EFECTIVO',
        evidencia_img=None,
        usuario_vendedor=user,
        fecha_pago=date(2026, 6, 7)
    )
    
    # 4. Verificaciones
    print(f"\nPago ID: {pago.id}, Monto: {pago.monto}")
    print(f"Observación: {pago.observacion}")
    
    # Verificar DetallePago
    detalles = pago.detalles.all().order_by('cuota__numero_cuota')
    print(f"\nDetalles generados: {detalles.count()}")
    for d in detalles:
        print(f"  -> Cubrió Cuota #{d.cuota.numero_cuota} con ${d.monto_aplicado}")
        
    if detalles.count() != 4:
        print("FAIL: Se experaban 4 detalles de pago.")
    else:
        print("PASS: Se generaron 4 detalles correcmante.")
        
    # Verificar Estados de Cuotas
    cnt_pagadas = contrato.cuotas.filter(estado='PAGADO').count()
    print(f"\nCuotas PAGADAS en DB: {cnt_pagadas}")
    
    ids_pagadas = list(contrato.cuotas.filter(estado='PAGADO').values_list('numero_cuota', flat=True))
    print(f"IDs Pagados: {ids_pagadas}")
    
    if ids_pagadas == [1, 2, 3, 4]:
        print("PASS: Las cuotas 1, 2, 3 y 4 están pagadas.")
    else:
        print("FAIL: Las cuotas pagadas no coinciden con lo esperado.")

    # 5. TEST SOBRANTE (SURPLUS)
    # Pagar $250. Debería cubrir Cuota 5 ($200) y sobrar $50 para Cuota 6.
    print("\n>>> Registrando SEGUNDO pago de $250 (Surplus Test)...")
    pago2 = registrar_pago_cliente(
        contrato_id=contrato.id,
        monto=Decimal('250.00'),
        metodo_pago='EFECTIVO',
        evidencia_img=None,
        usuario_vendedor=user,
        fecha_pago=date(2026, 7, 7)
    )
    
    detalles2 = pago2.detalles.all().order_by('cuota__numero_cuota')
    print(f"\nDetalles Pago 2 ({detalles2.count()}):")
    for d in detalles2:
        print(f"  -> Cubrió Cuota #{d.cuota.numero_cuota} con ${d.monto_aplicado}")
        
    cuota6 = contrato.cuotas.get(numero_cuota=6)
    print(f"\nEstado Cuota #6: {cuota6.estado}, Pagado: {cuota6.valor_pagado}, Pendiente: {cuota6.saldo_pendiente}")
    
    if cuota6.valor_pagado == Decimal('50.00') and cuota6.estado == 'PARCIAL':
        print("PASS: El surplus se aplicó correctamente a la Cuota #6.")
    else:
        print("FAIL: El surplus no se aplicó como se esperaba.")

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        import traceback
        traceback.print_exc()
