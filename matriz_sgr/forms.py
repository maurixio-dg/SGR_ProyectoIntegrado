from django import forms
from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.models import Periodo


class VincularMetaMatrizForm(forms.Form):
    delegacion = forms.ModelChoiceField(queryset=Delegacion.objects.all(), label='Delegación')
    periodo = forms.ModelChoiceField(queryset=Periodo.objects.all(), label='Período de medición')
    funcionario = forms.ModelChoiceField(queryset=Funcionario.objects.all(), required=False, label='Funcionario (opcional)')
    cargo = forms.ModelChoiceField(queryset=Cargo.objects.all(), required=False, label='Cargo (opcional)')

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.item_matriz=item

    def clean(self):
        datos = super().clean()
        funcionario=datos.get('funcionario')
        delegacion=datos.get('delegacion')
        cargo=datos.get('cargo')
        periodo=datos.get('periodo')
        if funcionario and delegacion and funcionario.delegacion_id != delegacion.pk:
            self.add_error('funcionario','Debe pertenecer a la delegación seleccionada.')
        if funcionario and cargo and funcionario.cargo_id != cargo.pk:
            self.add_error('cargo','El cargo no coincide con el funcionario.')
        item=self.item_matriz
        if item is None:
            return datos
        from .models import CorrespondenciaHojaCargoSGR
        from gestion.ponderaciones_sgr import comprobar_ponderacion
        mapa=CorrespondenciaHojaCargoSGR.objects.select_related('cargo').filter(
            catalogo_id=item.catalogo_id, hoja=item.hoja,
        ).first()
        if mapa is None:
            self.add_error(None,f'Antes de crear esta meta asocie la hoja «{item.hoja}» a un cargo municipal desde «Cargos por hoja».')
            return datos
        if funcionario and funcionario.cargo_id != mapa.cargo_id:
            self.add_error('funcionario',f'El cargo de esta hoja es «{mapa.cargo.nombre_cargo}». El funcionario no corresponde.')
        if cargo and cargo.pk != mapa.cargo_id:
            self.add_error('cargo',f'La hoja «{item.hoja}» exige «{mapa.cargo.nombre_cargo}».')
        if cargo is None:
            datos['cargo']=mapa.cargo
            cargo=mapa.cargo
        if delegacion and periodo and item.ponderacion is not None:
            texto=comprobar_ponderacion(
                delegacion_id=delegacion.pk, periodo_id=periodo.pk,
                ponderacion=item.ponderacion,
                funcionario_id=funcionario.pk if funcionario else None,
                cargo_id=cargo.pk,
            )
            if texto:
                self.add_error(None,texto)
        return datos
