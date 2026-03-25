import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from Aplicaciones.sbr_app_dos.models import Cliente, Lote, Contrato, Pago, DetallePago, Cuota
from Aplicaciones.sbr_gestor.models import Transaccion, CategoriaTransaccion
from Aplicaciones.sbr_gestor.views import calcular_ganancias_lotes

def print_separator(title):
    print(f"\n{'='*50}\n--- {title} ---\n{'='*50}")

def run_tests():
    # 0. Set up Test User
    user, _ = User.objects.get_or_create(username='test_admin', is_superuser=True)
    
    print_separator("TEST 1: Cálculo de Ganancias de Lotes")
    
    ganancias_iniciales = calcular_ganancias_lotes()
    print(f"Ganancias iniciales (Globales): ${ganancias_iniciales}")

    # Create dummy client and lot
    print("Creando Cliente y Lote de prueba...")
    cliente, _ = Cliente.objects.get_or_create(cedula='0000000000', defaults={'nombres': 'Test', 'apellidos': 'User', 'vendedor': user})
    lote, _ = Lote.objects.get_or_create(manzana='TEST', numero_lote='1', defaults={'precio_contado': 5000, 'estado': 'DISPONIBLE'})

    # Create contract with 1000 entry and 4000 to finance
    print("Creando Contrato de prueba (Entrada: $1000)...")
    contrato = Contrato.objects.create(
        cliente=cliente, lote=lote, fecha_contrato=date.today(),
        precio_venta_final=5000, numero_cuotas=10, valor_entrada=Decimal('1000.00'),
        saldo_a_financiar=Decimal('4000.00'), estado='ACTIVO'
    )
    
    # Simulate a payment for the entry
    print("Registrando Pago de Entrada ($1000)...")
    pago_entrada = Pago.objects.create(
        contrato=contrato, fecha_pago=date.today(), monto=Decimal('1000.00'),
        es_entrada=True, metodo_pago='EFECTIVO', registrado_por=user, numero_transaccion=99991
    )
    
    ganancias_lotes_post_entrada = calcular_ganancias_lotes()
    diff1 = ganancias_lotes_post_entrada - ganancias_iniciales
    print(f"Nuevas Ganancias (post-entrada): ${ganancias_lotes_post_entrada}")
    if diff1 == Decimal('1000.00'):
        print("✅ TEST PASSED: La entrada de lote se sumó correctamente a las ganancias matemáticas.")
    else:
        print(f"❌ TEST FAILED: Se esperaba sumar $1000, se sumaron ${diff1}")
        
    # Test adding a partial payment to a generic quota
    print("Creando Cuota de $400 y pagando $150...")
    cuota = Cuota.objects.create(
        contrato=contrato, numero_cuota=1, fecha_vencimiento=date.today(), 
        valor_capital=Decimal('400.00'), estado='PENDIENTE', valor_pagado=Decimal('150.00')
    )
    pago_cuota = Pago.objects.create(
        contrato=contrato, fecha_pago=date.today(), monto=Decimal('150.00'),
        es_entrada=False, metodo_pago='EFECTIVO', registrado_por=user, numero_transaccion=99992
    )
    DetallePago.objects.create(pago=pago_cuota, cuota=cuota, monto_aplicado=Decimal('150.00'))
    
    ganancias_lotes_post_cuota = calcular_ganancias_lotes()
    diff2 = ganancias_lotes_post_cuota - ganancias_lotes_post_entrada
    print(f"Nuevas Ganancias (post-cuota): ${ganancias_lotes_post_cuota}")
    if diff2 == Decimal('150.00'):
        print("✅ TEST PASSED: El pago de la cuota se sumó correctamente a las ganancias matemáticas.")
    else:
        print(f"❌ TEST FAILED: Se esperaba sumar $150, se sumaron ${diff2}")

    print_separator("TEST 2: Integración con el Gestor de Gastos")
    
    # 2. Test Gestor de Transacciones
    saldo_gestor_inicial = sum(m.valor for m in Transaccion.objects.filter(tipo='INGRESO')) - sum(m.valor for m in Transaccion.objects.filter(tipo='GASTO'))
    print(f"Saldo Gestor Actual (Sin lotes): ${saldo_gestor_inicial}")
    
    # Create category and expense
    print("Creando Categoría y Gasto de $50...")
    cat, _ = CategoriaTransaccion.objects.get_or_create(nombre='MANTENIMIENTO TEST', tipo='GASTO')
    gasto = Transaccion.objects.create(
        tipo='GASTO', valor=Decimal('50.00'), descripcion='Test Gasto',
        fecha=date.today(), categoria=cat, registrado_por=user
    )
    
    ingreso = Transaccion.objects.create(
        tipo='INGRESO', valor=Decimal('30.00'), descripcion='Test Ingreso Externo',
        fecha=date.today(), registrado_por=user
    )
    
    saldo_gestor_post = sum(m.valor for m in Transaccion.objects.filter(tipo='INGRESO')) - sum(m.valor for m in Transaccion.objects.filter(tipo='GASTO'))
    diff_gestor = saldo_gestor_post - saldo_gestor_inicial
    
    if diff_gestor == Decimal('-20.00'):  # +30 - 50 = -20
        print("✅ TEST PASSED: El balance de Ingresos y Gastos del gestor cuadra perfectamente.")
    else:
        print(f"❌ TEST FAILED: El balance se desajustó. Dif = ${diff_gestor}")
        
    print_separator("TEST 3: Saldo Total Global")
    saldo_total_esperado = ganancias_lotes_post_cuota + saldo_gestor_post
    print(f"Matemática Gestor: Lotes (${ganancias_lotes_post_cuota}) + Otros Ingresos y Gastos (${saldo_gestor_post}) = Saldo Final ${saldo_total_esperado}")
    
    # CLEANUP (To not pollute real DB)
    print_separator("CLEANUP")
    print("Borrando datos de prueba...")
    ingreso.delete()
    gasto.delete()
    cat.delete()
    pago_cuota.delete()
    pago_entrada.delete()
    contrato.delete()
    lote.delete()
    cliente.delete()
    print("Cleanup finalizado con éxito.")

if __name__ == '__main__':
    run_tests()
