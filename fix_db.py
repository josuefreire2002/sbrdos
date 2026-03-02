import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbr_dos.settings")
django.setup()

from Aplicaciones.sbr_app_dos.models import Contrato
from Aplicaciones.sbr_app_dos.services import recalcular_deuda_contrato

def fix_all_contracts():
    contratos = Contrato.objects.all()
    print(f"Recalculando {contratos.count()} contratos...")
    
    for contrato in contratos:
        try:
            recalcular_deuda_contrato(contrato.id)
            print(f"Contrato #{contrato.id} recalculado exitosamente.")
        except Exception as e:
            print(f"Error recalculando contrato #{contrato.id}: {e}")

if __name__ == '__main__':
    fix_all_contracts()
