"""Formularios con edición separada para porcentajes y metas variables."""
from django import forms
from django.core.exceptions import ValidationError
from delegaciones.models import Delegacion
from gestion.models import Periodo
from .modelos_especiales import MedicionEspecialSGR


class CrearMedicionEspecialForm(forms.Form):
    delegacion = forms.ModelChoiceField(queryset=Delegacion.objects.all(), label='Delegación')
    periodo = forms.ModelChoiceField(queryset=Periodo.objects.all(), label='Período de medición')


class EditarMedicionEspecialForm(forms.ModelForm):
    class Meta:
        model = MedicionEspecialSGR
        fields = ['resueltos','recibidos','objetivo_variable','realizado_variable',
                  'unidad_variable','fuente','respaldo']
        widgets = {'fuente': forms.Textarea(attrs={'rows':3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.item.clase == 'PORC':
            for clave in ('objetivo_variable','realizado_variable','unidad_variable'):
                self.fields.pop(clave)
        else:
            for clave in ('resueltos','recibidos'):
                self.fields.pop(clave)
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs['class'] = 'form-control'

    def clean_respaldo(self):
        archivo = self.cleaned_data.get('respaldo')
        if archivo and getattr(archivo, 'size', 0) > 5 * 1024 * 1024:
            raise ValidationError('El respaldo no debe superar 5 MB.')
        return archivo
