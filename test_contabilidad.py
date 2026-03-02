import os
import sys
import django
from decimal import Decimal
from datetime import date

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sbr_dos.settings')
django.setup()

from Aplicaciones.sbr_app_dos.models import Cliente, Contrato, Cuota, Pago, DetallePago, User
from Aplicaciones.sbr_app_dos.services import registrar_pago_cliente, recalcular_deuda_contrato

def log(msg):
    with open('test_log.txt', 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    print(msg)

def check(condition, msg):
    if condition:
        log(f"✅ PASS: {msg}")
    else:
        log(f"❌ FAIL: {msg}")
        
def show_estado_contrato(contrato):
    log("\n--- Estado Actual del Contrato ---")
    pagos = Pago.objects.filter(contrato=contrato)
    total_pagos = sum(p.monto for p in pagos)
    
    suma_detalles = sum(d.monto_aplicado for p in pagos for d in p.detalles.all())
    suma_cuotas_pagadas = sum(c.valor_pagado for c in contrato.cuotas.all())
    
    log(f"Suma de Pago.monto: {total_pagos}")
    log(f"Suma de DetallePago.monto_aplicado: {suma_detalles}")
    log(f"Suma de Cuota.valor_pagado: {suma_cuotas_pagadas}")
    
    if total_pagos != suma_detalles:
        log("❌ INCONSISTENCIA: La suma de los pagos reales no cuadra con la suma de la distribución (Detalles)")
    if suma_detalles != suma_cuotas_pagadas:
        log("❌ INCONSISTENCIA: La distribución de dinero (Detalles) no coincide con el saldo abonado a las Cuotas.")
    if total_pagos != suma_cuotas_pagadas:
        log("❌ INCONSISTENCIA: Se recaudó un monto distinto al que se liquidó en las cuotas.")
        
    for c in contrato.cuotas.order_by('numero_cuota'):
        log(f"Cuota {c.numero_cuota}: Deuda={c.total_a_pagar}, Pagado={c.valor_pagado}, Estado={c.estado}")

from django.db import transaction

def run_test():
    open('test_log.txt', 'w', encoding='utf-8').close()  # Clear file
    log("\n================ TEST EXHAUSTIVO CONTABLE ================\n")
    try:
        with transaction.atomic():
            user = User.objects.first()
            cliente, _ = Cliente.objects.get_or_create(cedula="8888888888", defaults={"nombres": "Auditoria", "apellidos": "Test", "celular": "0", "vendedor": user})
            
            contrato = Contrato.objects.create(
                cliente=cliente, fecha_contrato=date.today(), precio_venta_final=Decimal('1000.00'),
                valor_entrada=Decimal('0.00'), saldo_a_financiar=Decimal('1000.00'), numero_cuotas=2, estado='ACTIVO'
            )
            
            # Cuotas: 1 = $500, 2 = $500
            c1 = Cuota.objects.create(contrato=contrato, numero_cuota=1, fecha_vencimiento=date.today(), valor_capital=Decimal('500.00'), valor_pagado=0, estado='PENDIENTE')
            c2 = Cuota.objects.create(contrato=contrato, numero_cuota=2, fecha_vencimiento=date.today(), valor_capital=Decimal('500.00'), valor_pagado=0, estado='PENDIENTE')
            
            # Escenario 1: Pago normal Exacto
            log("\n--- ESCENARIO 1: Pago de 500 para la Cuota 1 ---")
            p1 = registrar_pago_cliente(contrato.id, Decimal('500.00'), 'EFECTIVO', None, user)
            show_estado_contrato(contrato)
            
            # Escenario 2: Pago Excedente
            log("\n--- ESCENARIO 2: Abono excedente de 600 (500 a la Cuota 2, 100 sobran) ---")
            p2 = registrar_pago_cliente(contrato.id, Decimal('600.00'), 'EFECTIVO', None, user)
            show_estado_contrato(contrato)
            
            # Escenario 3: Borrar el Pago 1 desde el admin (simulado)
            log("\n--- ESCENARIO 3: Administrador elimina el Pago #1 (Recálculo masivo) ---")
            p1.delete()
            recalcular_deuda_contrato(contrato.id)
            show_estado_contrato(contrato)
            
            # Forzamos rollback para no dejar basura en la DB real
            raise Exception("Rollback provocado para limpiar DB.")
    
    except Exception as e:
        log(f"\nFinalizando test: {str(e)}")

if __name__ == '__main__':
    run_test()
