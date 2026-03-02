import os
import django
from django.db.models import F

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sbr_dos.settings')
django.setup()

from Aplicaciones.sbr_app_dos.models import Contrato, Pago

def fix_numbers():
    print("Iniciando numeración de pagos...")
    contratos = Contrato.objects.all()
    total_updated = 0
    
    for c in contratos:
        pagos = c.pago_set.all().order_by('fecha_pago', 'id')
        contador = 1
        for p in pagos:
            p.numero_transaccion = contador
            p.save(update_fields=['numero_transaccion'])
            contador += 1
            total_updated += 1
            
    print(f"Finalizado. Se actualizaron {total_updated} pagos.")

if __name__ == '__main__':
    fix_numbers()
