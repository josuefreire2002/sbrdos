import os
import django
from decimal import Decimal
from datetime import date
import time

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from django.contrib.auth.models import User
from Aplicaciones.sbr_app_dos.models import Lote, Cliente, Contrato, Cuota, Pago, DetallePago, ConfiguracionSistema
from Aplicaciones.sbr_app_dos.services import generar_tabla_amortizacion, registrar_pago_cliente, recalcular_deuda_contrato

def print_header(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

def run_test():
    print_header("1. Preparación de Entorno")
    
    # 1. Config
    ConfiguracionSistema.objects.get_or_create(
        id=1, 
        defaults={'nombre_empresa': 'SBR Test', 'ruc_empresa': '1234567890001', 'mora_porcentaje': Decimal('3.0')}
    )
    
    # Usuario
    user, created = User.objects.get_or_create(username='test_admin2', defaults={'email': 'admin@test.com'})
    if created:
        user.set_password('adminpass123')
        user.is_superuser = True
        user.is_staff = True
        user.save()
    
    # 2. Agregar un Lote
    lote_numero = f"TESTLOTE-{int(time.time())}"
    lote = Lote.objects.create(
        manzana='T',
        numero_lote=lote_numero,
        dimensiones='10x20',
        precio_contado=Decimal('10000.00'),
        estado='DISPONIBLE',
        creado_por=user
    )
    print(f"✓ Lote creado: Mz {lote.manzana} Lote {lote.numero_lote} - Precio: {lote.precio_contado}")

    print_header("2. Crear un Cliente y Generar Contrato (Venta)")
    cedula_test = f"09{str(int(time.time()))[-8:]}"
    cliente = Cliente.objects.create(
        vendedor=user,
        cedula=cedula_test,
        nombres='Test',
        apellidos='Integration',
        celular='0900000000',
        direccion='Testing st.'
    )

    contrato = Contrato.objects.create(
        cliente=cliente,
        fecha_contrato=date.today(),
        precio_venta_final=Decimal('10000.00'),
        valor_entrada=Decimal('2000.00'),
        saldo_a_financiar=Decimal('8000.00'),
        numero_cuotas=10, # 10 cuotas de 800
        observacion="Test venta"
    )
    contrato.lotes.add(lote)
    contrato.lote = lote
    contrato.save()
    lote.estado = 'VENDIDO'
    lote.save()

    # PAGO ENTRADA
    Pago.objects.create(
        contrato=contrato,
        fecha_pago=date.today(),
        monto=Decimal('2000.00'),
        metodo_pago='EFECTIVO',
        observacion="Entrada",
        registrado_por=user,
        es_entrada=True # NUEVO FIELD VITAL
    )

    # GENERAR TABLA
    generar_tabla_amortizacion(contrato.id, fecha_inicio_pago_str=date.today().strftime('%Y-%m-%d'))
    
    print(f"✓ Contrato Creado: ID {contrato.id} para {contrato.cliente}")
    print(f"✓ Saldo a financiar: ${contrato.saldo_a_financiar}")
    print(f"✓ Cuotas generadas: {contrato.cuotas.count()}")

    print_header("3. Ver Tabla de Amortización Inicial")
    cuotas = list(contrato.cuotas.order_by('numero_cuota')[:3])
    for c in cuotas:
         print(f"  - Cuota #{c.numero_cuota} - Capital: ${c.valor_capital} - Vencimiento: {c.fecha_vencimiento} - Total a Pagar: ${c.total_a_pagar} - Estado: {c.estado}")

    print_header("4. Hacer un Pago Parcial (Cuota 1 -> $500)")
    # Cuota 1 es de $800. Faltarían $300.
    cuota_1 = contrato.cuotas.get(numero_cuota=1)
    
    nuevo_pago = registrar_pago_cliente(
        contrato_id=contrato.id, 
        monto=Decimal('500.00'), 
        metodo_pago='EFECTIVO', 
        evidencia_img=None, 
        usuario_vendedor=user, 
        fecha_pago=date.today(), 
        cuota_origen_id=cuota_1.id
    )
    
    cuota_1.refresh_from_db()
    print(f"✓ Pago registrado (ID: {nuevo_pago.id}). Estado Cuota 1: {cuota_1.estado} (Pagado: ${cuota_1.valor_pagado}/${cuota_1.total_a_pagar})")
    assert cuota_1.estado == 'PARCIAL', f"Cuota 1 debería estar PARCIAL, pero está {cuota_1.estado}"
    
    print_header("5. Hacer Pago $1000 (Cubre el Resto Cuota 1 y Sobrante Cuota 2)")
    # Falta $300 para cuota 1. Pagaremos $1000.
    # $300 a Cuota 1 -> queda PAGADA. $700 a Cuota 2 -> queda PARCIAL
    nuevo_pago_2 = registrar_pago_cliente(
        contrato_id=contrato.id, 
        monto=Decimal('1000.00'), 
        metodo_pago='TRANSFERENCIA', 
        evidencia_img=None, 
        usuario_vendedor=user, 
        fecha_pago=date.today()
    )
    
    cuota_1.refresh_from_db()
    cuota_2 = contrato.cuotas.get(numero_cuota=2)
    
    print(f"✓ Pago registrado ($1000, ID: {nuevo_pago_2.id}).")
    print(f"  - Cuota 1 Estado: {cuota_1.estado} (Pagado: ${cuota_1.valor_pagado}/${cuota_1.total_a_pagar})")
    print(f"  - Cuota 2 Estado: {cuota_2.estado} (Pagado: ${cuota_2.valor_pagado}/${cuota_2.total_a_pagar})")
    
    assert cuota_1.estado == 'PAGADO', f"Cuota 1 debería estar PAGADA, pero está {cuota_1.estado}"
    assert cuota_2.estado == 'PARCIAL', f"Cuota 2 debería estar PARCIAL, pero está {cuota_2.estado}"
    assert cuota_2.valor_pagado == Decimal('700.00'), f"Cuota 2 abonado {cuota_2.valor_pagado}"
    
    print_header("6. Probar Edición Destructiva (Recalcular Deuda)")
    # Bug 1 en reporte: editar el pago DESTRUÍA el salto manual si estaba aplicado. 
    # Aquí vamos a simular la edición: cambiar $1000 a $900
    print(f"  -> Editando Pago ID {nuevo_pago_2.id} de $1000 a $900...")
    nuevo_pago_2.monto = Decimal('900.00')
    nuevo_pago_2.save()
    recalcular_deuda_contrato(contrato.id)
    
    cuota_1.refresh_from_db()
    cuota_2.refresh_from_db()
    
    print(f"✓ Recálculo completado.")
    print(f"  - Cuota 1 Estado: {cuota_1.estado} (Pagado: ${cuota_1.valor_pagado}/${cuota_1.total_a_pagar})")
    print(f"  - Cuota 2 Estado: {cuota_2.estado} (Pagado: ${cuota_2.valor_pagado}/${cuota_2.total_a_pagar})")
    
    assert cuota_1.estado == 'PAGADO'
    assert cuota_2.valor_pagado == Decimal('600.00'), f"Cuota 2 debería ser $600 depositado, fue: {cuota_2.valor_pagado}"

    print_header("==== PRUEBA CORE MATH RE-VERIFICADA CON ÉXITO ====")

if __name__ == '__main__':
    try:
        run_test()
    except Exception as e:
        import traceback
        traceback.print_exc()
        exit(1)
