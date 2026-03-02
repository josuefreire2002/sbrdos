import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from Aplicaciones.sbr_app_dos.models import Contrato, Cuota, Pago, DetallePago

def audit_database():
    contratos = Contrato.objects.all()
    print(f"Iniciando auditoría de {contratos.count()} contratos...")
    
    errores = []
    advertencias = []

    for contrato in contratos:
        info = f"Contrato #{contrato.id} ({contrato.cliente})"
        
        # 1. Verificar Cuadre de Saldo a Financiar vs Cuotas Generadas
        saldo_financiar = contrato.saldo_a_financiar
        total_capital_cuotas = sum(c.valor_capital for c in contrato.cuotas.all())
        
        if abs(saldo_financiar - total_capital_cuotas) > Decimal('0.05'):
             errores.append(f"[{info}] DESCUADRE CAPITAL: Saldo a financiar es ${saldo_financiar} pero la suma del capital de las cuotas es ${total_capital_cuotas}")
             
        # 2. Re-verificar que las cuotas pagadas no superen el total_a_pagar
        for cuota in contrato.cuotas.all():
            if cuota.valor_pagado > cuota.total_a_pagar + Decimal('0.05'):
                errores.append(f"[{info}] SOBREPAGO EN CUOTA: Cuota #{cuota.numero_cuota} tiene pagado ${cuota.valor_pagado} pero su total a pagar es ${cuota.total_a_pagar}")

            if cuota.estado == 'PAGADO' and cuota.valor_pagado < cuota.total_a_pagar - Decimal('0.05'):
                errores.append(f"[{info}] FALSO PAGADO: Cuota #{cuota.numero_cuota} esta como PAGADO pero solo tiene ${cuota.valor_pagado} de ${cuota.total_a_pagar}")

            if cuota.estado == 'PENDIENTE' and cuota.valor_pagado > Decimal('0'):
                errores.append(f"[{info}] FALSO PENDIENTE: Cuota #{cuota.numero_cuota} esta como PENDIENTE pero tiene pagado ${cuota.valor_pagado}")

        # 3. Sumatoria de pagos vs sumatoria de cuotas pagadas
        pagos_validos = contrato.pago_set.filter(es_entrada=False)
        total_pagado_caja = sum(p.monto for p in pagos_validos)
        
        total_aplicado_cuotas = sum(c.valor_pagado for c in contrato.cuotas.all())
        
        if total_aplicado_cuotas > total_pagado_caja + Decimal('0.01'):
            errores.append(f"[{info}] DINERO FANTASMA: Las cuotas tienen aplicado ${total_aplicado_cuotas}, pero solo entraron ${total_pagado_caja} en pagos válidos (sin contar entrada).")
        
        if total_pagado_caja > total_aplicado_cuotas + Decimal('0.01'):
            advertencias.append(f"[{info}] SALDO A FAVOR / SIN APLICAR: Han ingresado ${total_pagado_caja} pero solo hay ${total_aplicado_cuotas} aplicado a cuotas. Sobra ${total_pagado_caja - total_aplicado_cuotas}.")

        # 4. Verificar entrada
        pagos_entrada = contrato.pago_set.filter(es_entrada=True)
        total_entrada_caja = sum(p.monto for p in pagos_entrada)
        if getattr(contrato, 'valor_entrada', 0) > 0:
            if abs(contrato.valor_entrada - total_entrada_caja) > Decimal('0.01'):
                advertencias.append(f"[{info}] DISCREPANCIA ENTRADA: Contrato dice entrada ${contrato.valor_entrada}, pero hay pagos marcados como entrada por ${total_entrada_caja}")

    print("\n--- RESULTADOS DE LA AUDITORIA ---")
    if not errores and not advertencias:
        print("✅ Todo perfecto. La base de datos está 100% libre de errores matemáticos o lógicos.")
    
    if advertencias:
        print("\n\n⚠️ ADVERTENCIAS:")
        for w in advertencias:
            print(f" - {w}")
            
    if errores:
        print("\n\n❌ ERRORES GRAVES:")
        for e in errores:
            print(f" - {e}")
        print("\nRecomendación: Correr recalcular_deuda_contrato sobre los contratos con errores.")

if __name__ == '__main__':
    audit_database()
