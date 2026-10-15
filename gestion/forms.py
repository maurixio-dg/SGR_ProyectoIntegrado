
from django import forms
from .models import Periodo


class PeriodoForm(forms.ModelForm):

    class Meta:
        model = Periodo

        fields = [
            "nombre",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "descripcion",
        ]

        labels = {
            "nombre": "Nombre del período",
            "fecha_inicio": "Fecha de inicio",
            "fecha_fin": "Fecha de término",
            "estado": "Estado del período",
            "descripcion": "Descripción",
        }

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej.: Gestión Municipal 2026",
                    "maxlength": 150,
                }
            ),

            "fecha_inicio": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "fecha_fin": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "estado": forms.Select(
                attrs={"class": "form-select"}
            ),

            "descripcion": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describa el propósito del período",
                }
            ),
        }

    def clean_nombre(self):
        nombre = " ".join(
            self.cleaned_data["nombre"].split()
        )

        if len(nombre) < 3:
            raise forms.ValidationError(
                "El nombre debe contener al menos 3 caracteres."
            )

        return nombre
