from django import forms
from django.core.exceptions import ValidationError
from funcionarios.models import Funcionario
from gestion.models import Periodo
from .models import ItemMatrizSGR
from .modelos_valoraciones import ValoracionCiudadanaSGR


class ValoracionCiudadanaForm(forms.ModelForm):
    periodo = forms.ModelChoiceField(queryset=Periodo.objects.all(), label='Período de medición')

    class Meta:
        model = ValoracionCiudadanaSGR
        fields = ['item','periodo','funcionario','fecha_documento','referencia','remitente',
                  'medio','descripcion','respaldo']
        widgets = {
            'fecha_documento': forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d'),
            'descripcion': forms.Textarea(attrs={'rows':4}),
        }

    def __init__(self, *args, delegacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = ItemMatrizSGR.objects.filter(clase='ESP').order_by('-catalogo_id','hoja','fila')
        self.fields['funcionario'].queryset = Funcionario.objects.filter(delegacion=delegacion) if delegacion else Funcionario.objects.none()
        self.fields['funcionario'].required = False
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'

    def clean_respaldo(self):
        archivo = self.cleaned_data.get('respaldo')
        if not archivo:
            raise ValidationError('Adjunte un documento formal de respaldo.')
        if getattr(archivo, 'size', 0) > 5 * 1024 * 1024:
            raise ValidationError('El respaldo no puede superar 5 MB.')
        return archivo


class ResolverValoracionForm(forms.Form):
    decision = forms.ChoiceField(choices=[('VAL','Validar respaldo'),('REC','Rechazar')],label='Decisión')
    observacion = forms.CharField(min_length=15, max_length=1800, widget=forms.Textarea(attrs={'rows':3}),
                                  label='Fundamento de la revisión')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['decision'].widget.attrs['class']='form-select'
        self.fields['observacion'].widget.attrs['class']='form-control'
