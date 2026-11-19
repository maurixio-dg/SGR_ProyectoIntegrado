from pathlib import Path
from django import forms
from .models import Actividad
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario

EXTENSIONES_PERMITIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"}
MAX_EVIDENCIA_BYTES = 5 * 1024 * 1024


class ActividadForm(forms.ModelForm):
    class Meta:
        model = Actividad
        fields = [
            "fecha_actividad", "periodo", "delegacion", "funcionario",
            "tipo_accion", "titulo", "descripcion", "accion_realizada",
            "nombre_solicitante", "telefono_solicitante",
            "solicitante_es_delegado", "evidencia",
        ]
        widgets = {
            "fecha_actividad": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "accion_realizada": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delegacion"].queryset = Delegacion.objects.filter(estado=True)
        self.fields["funcionario"].queryset = Funcionario.objects.select_related("delegacion")
        administrador = bool(usuario and (usuario.is_superuser or getattr(usuario, "rol", "") == "ADMIN"))
        if usuario and not administrador:
            propios = Funcionario.objects.filter(usuario=usuario)
            self.fields["funcionario"].queryset = propios
            self.fields["delegacion"].queryset = Delegacion.objects.filter(
                pk__in=propios.values_list("delegacion_id", flat=True)
            )
            if propios.exists() and not self.is_bound and not self.instance.pk:
                self.initial.setdefault("funcionario", propios.first().pk)
                self.initial.setdefault("delegacion", propios.first().delegacion_id)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "form-check-input"
            elif isinstance(campo.widget, forms.Select):
                campo.widget.attrs["class"] = "form-select"
            else:
                campo.widget.attrs["class"] = "form-control"
        self.fields["periodo"].required = False
        self.fields["nombre_solicitante"].required = False
        self.fields["telefono_solicitante"].required = False
        self.fields["evidencia"].help_text = "PDF, JPG, PNG, DOCX o XLSX; máximo 5 MB."

    def clean_evidencia(self):
        archivo = self.cleaned_data.get("evidencia")
        if archivo and hasattr(archivo, "size"):
            if archivo.size > MAX_EVIDENCIA_BYTES:
                raise forms.ValidationError("La evidencia no puede superar 5 MB.")
            if Path(archivo.name).suffix.lower() not in EXTENSIONES_PERMITIDAS:
                raise forms.ValidationError("Tipo de archivo no permitido.")
        return archivo
