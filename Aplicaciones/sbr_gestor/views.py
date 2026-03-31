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

def calcular_ganancias_lotes_rapido(mes=None, anio=None):
    from django.db.models import Sum
    from Aplicaciones.sbr_app_dos.models import Pago, Contrato
    from decimal import Decimal
    
    total_pagos = Decimal('0.00')
    
    # 1. Pagos reales
    pagos_qs = Pago.objects.exclude(contrato__estado='DEVOLUCION')
    if mes and anio:
        pagos_qs = pagos_qs.filter(fecha_pago__year=int(anio), fecha_pago__month=int(mes))
        
    suma_pagos = pagos_qs.aggregate(total=Sum('monto'))['total']
    if suma_pagos:
        total_pagos += suma_pagos
        
    # 2. Entradas "Fantasma" (Contratos con valor de entrada pero sin Pago en BD)
    fantasmas_qs = Contrato.objects.filter(valor_entrada__gt=0, pago__isnull=True).exclude(estado='DEVOLUCION')
    if mes and anio:
        fantasmas_qs = fantasmas_qs.filter(fecha_contrato__year=int(anio), fecha_contrato__month=int(mes))
        
    suma_fantasmas = fantasmas_qs.aggregate(total=Sum('valor_entrada'))['total']
    if suma_fantasmas:
        total_pagos += suma_fantasmas
        
    return total_pagos

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
        ingresos_lotes = calcular_ganancias_lotes_rapido(mes=mes, anio=anio)
        context_mes_filtro = f"{anio}-{str(mes).zfill(2)}"
    else:
        ingresos_lotes = calcular_ganancias_lotes_rapido()
        context_mes_filtro = ''
        
    ingresos_caja = sum(m.valor for m in movimientos if m.tipo == 'INGRESO')
    total_ingresos = ingresos_caja + ingresos_lotes
    total_gastos = sum(m.valor for m in movimientos if m.tipo == 'GASTO')
    saldo_actual = total_ingresos - total_gastos
    
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
    
    if ingresos_lotes > 0:
        dict_ingresos['Venta de Lotes'] = ingresos_lotes
        
    for i in ingresos:
        cat_name = i.categoria.nombre if i.categoria else 'Otros Ingresos'
        dict_ingresos[cat_name] = dict_ingresos.get(cat_name, Decimal('0.00')) + i.valor
        
    chart_ingresos = json.dumps({
        'labels': list(dict_ingresos.keys()),
        'data': [float(v) for v in dict_ingresos.values()]
    })

    # Unificación de datos para la tabla
    lista_movimientos = []
    
    for m in movimientos:
        lista_movimientos.append({
            'id': m.id,
            'is_lote': False,
            'fecha': m.fecha,
            'tipo': m.tipo,
            'categoria_nombre': m.categoria.nombre if m.categoria else 'SN Categoría',
            'valor': m.valor,
            'descripcion': m.descripcion,
            'numero_recibo': m.numero_recibo,
            'foto_url': m.foto_recibo.url if m.foto_recibo else None,
            'mov_obj': m
        })
        
    # Obtener pagos de lotes
    from Aplicaciones.sbr_app_dos.models import Pago, Contrato
    pagos_qs = Pago.objects.select_related('contrato', 'contrato__cliente').exclude(contrato__estado='DEVOLUCION')
    fantasmas_qs = Contrato.objects.select_related('cliente').filter(valor_entrada__gt=0, pago__isnull=True).exclude(estado='DEVOLUCION')
    
    if mes and anio:
        pagos_qs = pagos_qs.filter(fecha_pago__year=int(anio), fecha_pago__month=int(mes))
        fantasmas_qs = fantasmas_qs.filter(fecha_contrato__year=int(anio), fecha_contrato__month=int(mes))
        
    for p in pagos_qs:
        desc = f"Entrada Lote - Contrato #{p.contrato.id} ({p.contrato.cliente})" if p.es_entrada else f"Cuota Lote - Contrato #{p.contrato.id} ({p.contrato.cliente})"
        if p.observacion: desc += f" | {p.observacion[:40]}"
        
        lista_movimientos.append({
            'id': p.id,
            'is_lote': True,
            'fecha': p.fecha_pago,
            'tipo': 'INGRESO',
            'categoria_nombre': 'Venta de Lotes',
            'valor': p.monto,
            'descripcion': desc,
            'numero_recibo': f"PGO-{p.id}",
            'foto_url': p.comprobante_imagen.url if p.comprobante_imagen else None,
            'contrato_id': p.contrato.id
        })
        
    for f in fantasmas_qs:
        lista_movimientos.append({
            'id': f.id,
            'is_lote': True,
            'fecha': f.fecha_contrato,
            'tipo': 'INGRESO',
            'categoria_nombre': 'Venta de Lotes',
            'valor': f.valor_entrada,
            'descripcion': f"Entrada Automática - Contrato #{f.id} ({f.cliente})",
            'numero_recibo': f"CTR-{f.id}",
            'foto_url': None,
            'contrato_id': f.id
        })
        
    # Ordenar todo por fecha
    lista_movimientos.sort(key=lambda x: x['fecha'], reverse=True)

    context = {
        'movimientos': lista_movimientos,
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
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
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'msg': 'Registrado correctamente'})
            
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
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
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'msg': 'Actualizado correctamente'})
            
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            messages.error(request, f"Error al editar: {str(e)}")
            
    return redirect('gestor_dashboard')

@login_required
def eliminar_transaccion_view(request, tr_id):
    if request.method == 'POST':
        try:
            tr = Transaccion.objects.get(id=tr_id)
            tr_id_str = str(tr.id)
            tr.delete()
            messages.success(request, f"Transacción #{tr_id_str} eliminada correctamente.")
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'msg': 'Eliminado correctamente'})
        except Transaccion.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'La transacción no existe'})
            messages.error(request, "La transacción no existe.")
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            messages.error(request, f"Error al eliminar: {str(e)}")
            
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

@login_required
def api_totales_view(request):
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')
    
    filtro_fecha = request.GET.get('mes_filtro', '') # formato: "YYYY-MM"
    if filtro_fecha:
        parts = filtro_fecha.split('-')
        if len(parts) == 2:
            anio, mes = parts[0], parts[1]
            
    movimientos = Transaccion.objects.all()
    if mes and anio:
        movimientos = movimientos.filter(fecha__year=int(anio), fecha__month=int(mes))
        ingresos_lotes = calcular_ganancias_lotes_rapido(mes=mes, anio=anio)
    else:
        ingresos_lotes = calcular_ganancias_lotes_rapido()
        
    ingresos_caja = sum(m.valor for m in movimientos if m.tipo == 'INGRESO')
    total_ingresos = ingresos_caja + ingresos_lotes
    total_gastos = sum(m.valor for m in movimientos if m.tipo == 'GASTO')
    saldo_actual = total_ingresos - total_gastos
    
    return JsonResponse({
        'success': True,
        'total_ingresos': f"{total_ingresos:.2f}",
        'total_gastos': f"{total_gastos:.2f}",
        'saldo_actual': f"{saldo_actual:.2f}"
    })
