import urllib.request
import urllib.error
import sys

try:
    urllib.request.urlopen('http://127.0.0.1:8000/contrato/1/pagar/')
except urllib.error.HTTPError as e:
    with open('error.html', 'w', encoding='utf-8') as f:
        f.write(e.read().decode('utf-8'))
    print("Error guardado en error.html")
except Exception as e:
    print(f"Connection failed: {e}")
