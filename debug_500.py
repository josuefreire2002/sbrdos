import os
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sbr_dos.settings')
django.setup()

from Aplicaciones.sbr_app_dos.models import Contrato

def check_url():
    # Find a valid contract ID
    c = Contrato.objects.first()
    if not c:
        print("No contracts found.")
        return

    # Preparar Usuario
    from Aplicaciones.sbr_app_dos.models import User
    u = User.objects.filter(is_superuser=True).first()
    if not u:
        u = User.objects.first()
    print(f"Logging in as {u.username}")

    # Preparar URL
    url = f"/contrato/{c.id}/detalle/" 
    print(f"Requesting {url}")

    from django.test import RequestFactory
    from Aplicaciones.sbr_app_dos.views import detalle_contrato_view
    
    factory = RequestFactory()
    request = factory.get(url)
    request.user = u
    
    # We need to add messages middleware support manually if the view uses it
    from django.contrib.messages.middleware import MessageMiddleware
    from django.contrib.sessions.middleware import SessionMiddleware
    
    # Process request through middleware to add session/messages
    middleware = SessionMiddleware(lambda x: x)
    middleware.process_request(request)
    request.session.save()
    
    messages = MessageMiddleware(lambda x: x)
    messages.process_request(request)

    print(f"Calling view directly...")
    try:
        response = detalle_contrato_view(request, pk=c.id)
        print(f"Status Code: {response.status_code}")
    except Exception as e:
        import traceback
        print("--- EXCEPTION CAUGHT ---")
        traceback.print_exc()

if __name__ == '__main__':
    check_url()
