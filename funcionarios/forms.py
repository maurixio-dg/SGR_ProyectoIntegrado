
from django import forms
from django.core.exceptions import ValidationError

from .models import Funcionario
from .rut import normalizar_rut
from delegaciones.models import Delegacion
from catalogos.models import Cargo


class FuncionarioForm(forms.ModelForm):

    class Meta:
        model = Funcionario

        fields = [
            "rut",
            "nombre",
            "email",
            "delegacion",
            "cargo",
            "usuario",
        ]

        labels = {
            "rut": "RUT del funcionario",
            "nombre": "Nombre completo",
            "email": "Correo electrónico",
            "delegacion": "Delegación municipal",
            "cargo": "Cargo",
            "usuario": "Cuenta de usuario (opcional)",
        }

        widgets = {
            "rut": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "12.345.678-5",
                "maxlength": 12,
            }),
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre y apellido",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "funcionario@ejemplo.cl",
            }),
            "delegacion": forms.Select(attrs={
                "class": "form-select",
            }),
            "cargo": forms.Select(attrs={
                "class": "form-select",
            }),
            "usuario": forms.Select(attrs={
                "class": "form-select",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        delegaciones = Delegacion.objects.filter(
            estado=True
        )

        if self.instance.pk:
            delegaciones = (
                Delegacion.objects.filter(estado=True)
                | Delegacion.objects.filter(
                    pk=self.instance.delegacion_id
                )
            ).distinct()

        self.fields["delegacion"].queryset = delegaciones

        self.fields["delegacion"].empty_label = (
            "Seleccione una delegación"
        )

        self.fields["cargo"].queryset = (
            Cargo.objects.all()
        )

        self.fields["cargo"].empty_label = (
            "Seleccione un cargo"
        )

        self.fields["usuario"].empty_label = (
            "Sin cuenta asociada"
        )

    def clean_nombre(self):
        nombre = " ".join(
            self.cleaned_data["nombre"].split()
        )

        if len(nombre) < 3:
            raise ValidationError(
                "Ingrese un nombre válido."
            )

        return nombre

    def clean_rut(self):
        return normalizar_rut(self.cleaned_data["rut"])
