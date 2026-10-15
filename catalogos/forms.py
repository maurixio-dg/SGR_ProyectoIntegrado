
from django import forms
from .models import Cargo


class CargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = ["nombre_cargo", "descripcion"]

        labels = {
            "nombre_cargo": "Nombre del cargo",
            "descripcion": "Descripción del cargo",
        }

        widgets = {
            "nombre_cargo": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej.: Gestor territorial",
                "maxlength": 150,
            }),
            "descripcion": forms.Textarea(attrs={
                "class": "form-control",
                "placeholder": "Describa las responsabilidades del cargo",
                "rows": 4,
            }),
        }

    def clean_nombre_cargo(self):
        nombre = " ".join(
            self.cleaned_data["nombre_cargo"].split()
        )

        if len(nombre) < 3:
            raise forms.ValidationError(
                "El nombre debe tener al menos 3 caracteres."
            )

        return nombre



from .models import Funcion


class FuncionForm(forms.ModelForm):

    class Meta:
        model = Funcion

        fields = [
            "cargo",
            "nombre",
            "descripcion",
            "estado",
        ]

        labels = {
            "cargo": "Cargo asociado",
            "nombre": "Nombre de la función",
            "descripcion": "Descripción de la función",
            "estado": "Función activa",
        }

        widgets = {
            "cargo": forms.Select(
                attrs={"class": "form-select"}
            ),
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej.: Coordinar actividades comunitarias",
                    "maxlength": 150,
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describa las responsabilidades de esta función",
                }
            ),
            "estado": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["cargo"].empty_label = (
            "Seleccione un cargo"
        )

    def clean_nombre(self):
        nombre = " ".join(
            self.cleaned_data["nombre"].split()
        )

        if len(nombre) < 3:
            raise forms.ValidationError(
                "El nombre debe contener al menos 3 caracteres."
            )

        return nombre
