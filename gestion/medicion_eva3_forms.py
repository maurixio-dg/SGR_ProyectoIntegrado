"""Formularios de ajustes de metas y ausencias."""
from django import forms
from django.db.models import Q
from catalogos.models import Cargo, Funcion
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from .models import ConfiguracionMetaSGR, AusenciaSGR, Periodo
from .operativa_eva3_forms import adaptar_widgets, usuario_funcionario
from .actividades_eva3 import es_admin


class ConfiguracionMetaSGRForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionMetaSGR
        fields = ("funcionario", "cargo", "funcion", "tope_porcentaje")

    def __init__(self, *args, usuario=None, meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta_objetivo = meta
        propios = Funcionario.objects.select_related("delegacion", "cargo")
        if meta is not None:
            propios = propios.filter(delegacion_id=meta.delegacion_id)
        if usuario and not es_admin(usuario):
            vinculado = usuario_funcionario(usuario)
            propios = propios.filter(delegacion_id=vinculado.delegacion_id) if vinculado else propios.none()
        self.fields["funcionario"].queryset = propios
        self.fields["cargo"].queryset = Cargo.objects.all()
        self.fields["funcion"].queryset = Funcion.objects.all()
        self.fields["funcionario"].required = False
        self.fields["cargo"].required = False
        self.fields["funcion"].required = False
        adaptar_widgets(self)

    def clean(self):
        datos = super().clean()
        from .ponderaciones_sgr import estado_cargo_matriz, comprobar_ponderacion
        meta = self.meta_objetivo
        if not meta:
            return datos
        cargo = datos.get("cargo")
        funcionario = datos.get("funcionario")
        funcion = datos.get("funcion")
        extras, _ = estado_cargo_matriz(meta, funcionario, cargo, funcion)
        for campo, texto in extras.items():
            self.add_error(None if campo == "__all__" else campo, texto)
        tope = datos.get("tope_porcentaje")
        if tope is not None and tope > 120:
            self.add_error("tope_porcentaje", "El límite municipal es 120% por ítem.")
        if meta.activo:
            advertencia = comprobar_ponderacion(
                delegacion_id=meta.delegacion_id, periodo_id=meta.periodo_id,
                ponderacion=meta.ponderacion,
                funcionario_id=funcionario.pk if funcionario else None,
                cargo_id=cargo.pk if cargo else None,
                excluir_meta_id=meta.pk,
            )
            if advertencia:
                self.add_error(None, advertencia)
        return datos

    def save(self, commit=True):
        configuracion = super().save(commit=False)
        configuracion.meta = self.meta_objetivo
        if commit:
            configuracion.full_clean()
            configuracion.save()
        return configuracion


class AusenciaSGRForm(forms.ModelForm):
    class Meta:
        model = AusenciaSGR
        fields = ("funcionario", "periodo", "tipo", "fecha_inicio", "fecha_fin")
        widgets = {
            "fecha_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        funcionarios = Funcionario.objects.select_related("delegacion")
        propio = usuario_funcionario(usuario)
        if usuario and not es_admin(usuario):
            funcionarios = funcionarios.filter(delegacion_id=propio.delegacion_id) if propio else funcionarios.none()
        self.fields["funcionario"].queryset = funcionarios
        self.fields["periodo"].queryset = Periodo.objects.all()
        adaptar_widgets(self)
