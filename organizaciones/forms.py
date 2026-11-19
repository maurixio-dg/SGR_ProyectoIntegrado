from django import forms
from .models import OrganizacionComunitaria


class OrganizacionForm(forms.ModelForm):
    class Meta:
        model = OrganizacionComunitaria
        fields = [
            'nombre', 'tipo', 'domicilio_legal', 'territorio_origen', 'delegacion',
            'socios_activos', 'fecha_constitucion', 'numero_registro_pj',
            'fecha_inscripcion', 'registro_directorio', 'estado_verificacion',
            'observaciones',
        ]
        widgets = {
            'fecha_constitucion': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_inscripcion': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.Select, forms.SelectMultiple)):
                campo.widget.attrs['class'] = 'form-select'
            elif isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs['class'] = 'form-check-input'
            else:
                campo.widget.attrs['class'] = 'form-control'
        self.fields['fecha_constitucion'].input_formats = ['%Y-%m-%d']
        self.fields['fecha_inscripcion'].input_formats = ['%Y-%m-%d']

    def clean_nombre(self):
        valor = (self.cleaned_data.get('nombre') or '').strip()
        if not valor:
            raise forms.ValidationError('El nombre es obligatorio.')
        return valor
