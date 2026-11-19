"""Equivalencias de cargos de la matriz. Jamás reasigna metas existentes."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_http_methods
from catalogos.models import Cargo
from .models import CatalogoMatrizSGR, CorrespondenciaHojaCargoSGR

@login_required
@require_http_methods(['GET','POST'])
def equivalencias(request,pk):
    if not (request.user.is_superuser or getattr(request.user,'rol','')=='ADMIN'):
        raise PermissionDenied('Solo un administrador puede asociar hojas y cargos.')
    catalogo = get_object_or_404(CatalogoMatrizSGR,pk=pk)
    hojas = sorted(set(catalogo.items.values_list('hoja',flat=True)))
    if request.method == 'POST':
        hoja=request.POST.get('hoja','')
        cargo_id=request.POST.get('cargo','')
        if hoja not in hojas:
            messages.error(request,'La hoja no existe en este catálogo.')
        elif not cargo_id.isdecimal() or not Cargo.objects.filter(pk=int(cargo_id)).exists():
            messages.error(request,'Seleccione un cargo municipal registrado.')
        else:
            CorrespondenciaHojaCargoSGR.objects.update_or_create(
                catalogo=catalogo,hoja=hoja,defaults={'cargo_id':int(cargo_id)}
            )
            messages.success(request,f'Equivalencia de la hoja «{hoja}» guardada. Las metas existentes NO fueron modificadas.')
            return redirect('matriz_sgr:equivalencias',pk=catalogo.pk)
    mapas={m.hoja:m for m in CorrespondenciaHojaCargoSGR.objects.filter(catalogo=catalogo).select_related('cargo')}
    filas=[{'hoja':h,'mapa':mapas.get(h)} for h in hojas]
    return render(request,'matriz_sgr/equivalencias.html',{
        'catalogo':catalogo,'filas':filas,'cargos':Cargo.objects.all(),
    })
