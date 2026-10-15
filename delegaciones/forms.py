
from django import forms
from .models import Delegacion


class DelegacionForm(forms.ModelForm):

    class Meta:
        model = Delegacion
        fields = ["nombre", "estado"]

        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre de la delegación",
                "maxlength": 150,
                "autofocus": True,
            }),
            "estado": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }

        labels = {
            "nombre": "Nombre de la delegación",
            "estado": "Delegación activa",
        }

    def clean_nombre(self):
        nombre = " ".join(
            self.cleaned_data["nombre"].split()
        )

        if len(nombre) < 3:
            raise forms.ValidationError(
                "El nombre debe tener al menos 3 caracteres."
            )

        return nombre
