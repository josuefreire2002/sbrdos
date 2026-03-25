import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from datetime import date
from django.db.models import Sum
from .models import Transaccion, CategoriaTransaccion
from Aplicaciones.sbr_app_dos.models import Contrato

def calcular_ganancias_lotes(mes=None, anio=None):
    total_general = Decimal('0.00')
    contratos = Contrato.objects.prefetch_related('pago_set__detalles').all()
    
    for contrato in contratos:
        total_pagado = Decimal('0.00')
        ids_entradas = set(contrato.pago_set.filter(es_entrada=True).values_list('id', flat=True))
        
        if contrato.valor_entrada > 0 and not ids_entradas:
            pago_entrada_obj_fallback = contrato.pago_set.order_by('id').first()
            if pago_entrada_obj_fallback:
                ids_entradas.add(pago_entrada_obj_fallback.id)

        # Si el contrato no tiene pago de entrada manual registrado como objeto Pago
        if contrato.valor_entrada > 0 and not ids_entradas:
            fecha_ref = contrato.fecha_contrato
            if not mes or (fecha_ref.month == int(mes) and fecha_ref.year == int(anio)):
                total_pagado += contrato.valor_entrada
        
        for pago in contrato.pago_set.all():
            fecha_pago = pago.fecha_pago
            if mes and (fecha_pago.month != int(mes) or fecha_pago.year != int(anio)):
                continue

            detalles = pago.detalles.all()
            if detalles.exists():
                for detalle in detalles:
                    total_pagado += (detalle.monto_aplicado or Decimal('0.00'))
            elif pago.id not in ids_entradas:
                total_pagado += (pago.monto or Decimal('0.00'))
            else:
                # Es entrada procesada nativamente como Pago en BD
                total_pagado += (pago.monto or Decimal('0.00'))
                
        if contrato.estado == 'DEVOLUCION':
            total_general -= total_pagado
        else:
            total_general += total_pagado
            
    return total_general

@login_required
def dashboard_gestor_view(request):
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')
    
    hoy = date.today()
    filtro_fecha = request.GET.get('mes_filtro', '') # formato: "YYYY-MM"
    if filtro_fecha:
        parts = filtro_fecha.split('-')
        if len(parts) == 2:
            anio, mes = parts[0], parts[1]
    
    movimientos = Transaccion.objects.all().order_by('-fecha_registro', '-id')
    
    if mes and anio:
        movimientos = movimientos.filter(fecha__year=int(anio), fecha__month=int(mes))
        total_ganancias_lotes = calcular_ganancias_lotes(mes=mes, anio=anio)
        context_mes_filtro = f"{anio}-{str(mes).zfill(2)}"
    else:
        total_ganancias_lotes = calcular_ganancias_lotes()
        context_mes_filtro = ''
        
    total_ingresos = sum(m.valor for m in movimientos if m.tipo == 'INGRESO')
    total_gastos = sum(m.valor for m in movimientos if m.tipo == 'GASTO')
    saldo_actual = total_ganancias_lotes + total_ingresos - total_gastos
    
    # JSON para Chart.js - GASTOS
    gastos = [m for m in movimientos if m.tipo == 'GASTO']
    dict_categorias = {}
    for g in gastos:
        cat_name = g.categoria.nombre if g.categoria else 'Sin Categoría'
        dict_categorias[cat_name] = dict_categorias.get(cat_name, Decimal('0.00')) + g.valor
        
    categorias_nombres = list(dict_categorias.keys())
    categorias_valores = [float(v) for v in dict_categorias.values()]
    chart_data = json.dumps({'labels': categorias_nombres, 'data': categorias_valores})

    # JSON para Chart.js - INGRESOS
    ingresos = [m for m in movimientos if m.tipo == 'INGRESO']
    dict_ingresos = {}
    if total_ganancias_lotes > 0:
        dict_ingresos['Venta de Lotes'] = total_ganancias_lotes
        
    for i in ingresos:
        cat_name = i.categoria.nombre if i.categoria else 'Otros Ingresos'
        dict_ingresos[cat_name] = dict_ingresos.get(cat_name, Decimal('0.00')) + i.valor
        
    chart_ingresos = json.dumps({
        'labels': list(dict_ingresos.keys()),
        'data': [float(v) for v in dict_ingresos.values()]
    })

    context = {
        'movimientos': movimientos,
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
        'total_ganancias_lotes': total_ganancias_lotes,
        'saldo_actual': saldo_actual,
        'categorias': CategoriaTransaccion.objects.all().order_by('nombre'),
        'hoy': hoy,
        'mes_filtro': context_mes_filtro,
        'chart_data': chart_data,
        'chart_ingresos': chart_ingresos
    }
    return render(request, 'sbr_gestor/dashboard.html', context)

@login_required
def registrar_transaccion_view(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo', '')
        monto_str = request.POST.get('monto', '0')
        fecha = request.POST.get('fecha', '')
        descripcion = request.POST.get('descripcion', '')
        numero_recibo = request.POST.get('numero_recibo', '')
        foto_recibo = request.FILES.get('foto_recibo')
        categoria_id = request.POST.get('categoria', '')
        
        try:
            monto = Decimal(monto_str.replace(',', '.'))
            if monto <= 0:
                messages.error(request, "El monto debe ser mayor a 0.")
                return redirect('gestor_dashboard')
                
            categoria = None
            if categoria_id:
                categoria = CategoriaTransaccion.objects.filter(id=categoria_id).first()

            Transaccion.objects.create(
                tipo=tipo,
                valor=monto,
                fecha=fecha,
                descripcion=descripcion,
                numero_recibo=numero_recibo,
                foto_recibo=foto_recibo,
                categoria=categoria,
                registrado_por=request.user
            )
            messages.success(request, f"¡{tipo.capitalize()} por ${monto:.2f} registrado con éxito!")
            
        except Exception as e:
            messages.error(request, f"Error al registrar: {str(e)}")
            
    return redirect('gestor_dashboard')

@login_required
def editar_transaccion_view(request, tr_id):
    if request.method == 'POST':
        tr = get_object_or_404(Transaccion, id=tr_id)
        monto_str = request.POST.get('monto', '0')
        fecha = request.POST.get('fecha', '')
        descripcion = request.POST.get('descripcion', '')
        numero_recibo = request.POST.get('numero_recibo', '')
        categoria_id = request.POST.get('categoria', '')

        try:
            monto = Decimal(monto_str.replace(',', '.'))
            if monto <= 0:
                messages.error(request, "El monto debe ser mayor a 0.")
                return redirect('gestor_dashboard')
                
            categoria = None
            if categoria_id:
                categoria = CategoriaTransaccion.objects.filter(id=categoria_id).first()

            tr.valor = monto
            tr.fecha = fecha
            tr.descripcion = descripcion
            tr.numero_recibo = numero_recibo
            tr.categoria = categoria
            
            if 'foto_recibo' in request.FILES:
                tr.foto_recibo = request.FILES['foto_recibo']
                
            tr.save()
            messages.success(request, f"Transacción #{tr.id} actualizada correctamente.")
            
        except Exception as e:
            messages.error(request, f"Error al editar: {str(e)}")
            
    return redirect('gestor_dashboard')

@login_required
@csrf_exempt
def crear_categoria_api(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        tipo = request.POST.get('tipo', 'GASTO')
        
        if nombre:
            cat = CategoriaTransaccion.objects.create(nombre=nombre, tipo=tipo)
            return JsonResponse({'success': True, 'id': cat.id, 'nombre': cat.nombre, 'tipo': cat.tipo})
    
    return JsonResponse({'success': False, 'error': 'Datos inválidos'})
