from django import forms
from django.db.models import Q
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from .models import AgendaCompromiso, MetaIndicador, Periodo
from .actividades_eva3 import es_admin


def usuario_funcionario(usuario):
    if not usuario or not usuario.is_authenticated:
        return None
    return Funcionario.objects.filter(usuario=usuario).first()


def es_jefatura(usuario):
    return es_admin(usuario) or getattr(usuario, "rol", "") in ("COORD", "DELEG")


def adaptar_widgets(formulario):
    for campo in formulario.fields.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs["class"] = "form-check-input"
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs["class"] = "form-select"
        else:
            campo.widget.attrs["class"] = "form-control"


class AgendaForm(forms.ModelForm):
    class Meta:
        model = AgendaCompromiso
        fields = ["titulo", "descripcion", "fecha", "hora_inicio", "hora_fin", "delegacion", "responsable", "periodo", "actividad", "lugar", "estado", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        propio = usuario_funcionario(usuario)
        delegaciones = Delegacion.objects.filter(estado=True)
        responsables = Funcionario.objects.select_related("delegacion")
        if self.instance.pk:
            delegaciones = Delegacion.objects.filter(Q(estado=True) | Q(pk=self.instance.delegacion_id))
        if usuario and not es_admin(usuario):
            delegaciones = delegaciones.filter(pk=propio.delegacion_id) if propio else delegaciones.none()
            responsables = responsables.filter(delegacion_id=propio.delegacion_id) if propio and es_jefatura(usuario) else responsables.filter(pk=propio.pk) if propio else responsables.none()
        self.fields["delegacion"].queryset = delegaciones
        self.fields["responsable"].queryset = responsables
        from .actividades_eva3 import actividades_visibles
        self.fields["actividad"].queryset = actividades_visibles(usuario) if usuario else self.fields["actividad"].queryset.none()
        self.fields["actividad"].required = False
        self.fields["periodo"].required = False
        self.fields["hora_inicio"].required = False
        self.fields["hora_fin"].required = False
        if propio and not self.is_bound and not self.instance.pk:
            self.initial.update({"delegacion": propio.delegacion_id, "responsable": propio.pk})
        adaptar_widgets(self)


class MetaIndicadorForm(forms.ModelForm):
    class Meta:
        model = MetaIndicador
        fields = ["nombre", "delegacion", "periodo", "meta_cantidad", "ponderacion", "activo"]

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        propio = usuario_funcionario(usuario)
        if usuario and not es_admin(usuario):
            self.fields["delegacion"].queryset = Delegacion.objects.filter(pk=propio.delegacion_id) if propio else Delegacion.objects.none()
            if propio and not self.instance.pk:
                self.initial["delegacion"] = propio.delegacion_id
        adaptar_widgets(self)

    def clean(self):
        datos = super().clean()
        if not datos.get("activo"):
            return datos
        delegacion=datos.get("delegacion")
        periodo=datos.get("periodo")
        if not delegacion or not periodo:
            return datos
        from .ponderaciones_sgr import comprobar_ponderacion, config_de_meta
        # El ámbito de una meta ya configurada permanece estable durante la edición.
        conf=config_de_meta(self.instance) if self.instance.pk else None
        texto=comprobar_ponderacion(
            delegacion_id=delegacion.pk, periodo_id=periodo.pk,
            ponderacion=datos.get("ponderacion"),
            funcionario_id=conf.funcionario_id if conf else None,
            cargo_id=conf.cargo_id if conf else None,
            excluir_meta_id=self.instance.pk,
        )
        if texto:
            self.add_error("ponderacion", texto)
        return datos


class RevisionActividadForm(forms.Form):
    observacion = forms.CharField(label="Observación", required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class RevisionActividadConMetaForm(RevisionActividadForm):
    meta = forms.ModelChoiceField(label="Ítem/meta al que se asigna esta actividad (si corresponde)", queryset=MetaIndicador.objects.none(), required=False, empty_label="Sin asignar a un indicador", widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, actividad=None, **kwargs):
        super().__init__(*args, **kwargs)
        if actividad:
            self.fields["meta"].queryset = MetaIndicador.objects.filter(
                delegacion_id=actividad.delegacion_id,
                periodo__fecha_inicio__lte=actividad.fecha_actividad,
                periodo__fecha_fin__gte=actividad.fecha_actividad,
                activo=True,
            ).select_related("periodo", "delegacion")
