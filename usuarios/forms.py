
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

Usuario = get_user_model()


class UsuarioCrearForm(UserCreationForm):

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "rol",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            if isinstance(campo.widget, forms.Select):
                campo.widget.attrs["class"] = "form-select"
            else:
                campo.widget.attrs["class"] = "form-control"

        self.fields["username"].label = "Nombre de usuario"
        self.fields["first_name"].label = "Nombres"
        self.fields["last_name"].label = "Apellidos"
        self.fields["email"].label = "Correo electrónico"
        self.fields["rol"].label = "Rol institucional"

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Este correo electrónico ya está registrado."
            )

        return email


class UsuarioEditarForm(forms.ModelForm):

    class Meta:
        model = Usuario
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "rol",
            "is_active",
        ]

        widgets = {
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            if isinstance(campo.widget, forms.Select):
                campo.widget.attrs["class"] = "form-select"
            elif not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "form-control"

        self.fields["username"].label = "Nombre de usuario"
        self.fields["first_name"].label = "Nombres"
        self.fields["last_name"].label = "Apellidos"
        self.fields["email"].label = "Correo electrónico"
        self.fields["rol"].label = "Rol institucional"
        self.fields["is_active"].label = "Cuenta activa"

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        existe = Usuario.objects.filter(
            email__iexact=email
        ).exclude(pk=self.instance.pk).exists()

        if existe:
            raise forms.ValidationError(
                "Este correo electrónico ya pertenece a otra cuenta."
            )

        return email
