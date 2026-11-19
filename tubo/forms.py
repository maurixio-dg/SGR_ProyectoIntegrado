from django import forms
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from organizaciones.models import OrganizacionComunitaria
from .models import (Vecino, Territorio, TipoAtencion, SubtipoAtencion, GestionSocial, CartaTubo)
from .permisos import es_admin, funcionario_usuario


class EstiloMixin:
    def estilos(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                css='form-check-input'
            elif isinstance(field.widget, forms.Select):
                css='form-select'
            else:
                css='form-control'
            field.widget.attrs['class']=css


class VecinoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model=Vecino
        fields=['rut','nombre','telefono','email','direccion','delegacion','territorio','organizacion']

    def __init__(self,*args, usuario=None, **kwargs):
        super().__init__(*args,**kwargs)
        self.fields['delegacion'].queryset=Delegacion.objects.filter(estado=True)
        self.fields['territorio'].queryset=Territorio.objects.filter(activo=True)
        self.fields['organizacion'].queryset=OrganizacionComunitaria.objects.all()
        if usuario and not es_admin(usuario):
            p=funcionario_usuario(usuario)
            ids=[p.delegacion_id] if p else []
            self.fields['delegacion'].queryset=self.fields['delegacion'].queryset.filter(pk__in=ids)
            self.fields['territorio'].queryset=self.fields['territorio'].queryset.filter(delegacion_id__in=ids)
            self.fields['organizacion'].queryset=self.fields['organizacion'].queryset.filter(delegacion_id__in=ids)
            if p and not self.is_bound and not self.instance.pk:
                self.initial.setdefault('delegacion', p.delegacion_id)
        self.estilos()


class GestionForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model=GestionSocial
        fields=['delegacion','vecino','territorio','tipo','subtipo','responsable','titulo','descripcion',
                'ingresa_tubo','solicitante_es_delegado','evidencia']
        widgets={'descripcion':forms.Textarea(attrs={'rows':4})}

    def __init__(self,*args, usuario=None, **kwargs):
        super().__init__(*args,**kwargs)
        self.fields['delegacion'].queryset=Delegacion.objects.filter(estado=True)
        self.fields['vecino'].queryset=Vecino.objects.all()
        self.fields['territorio'].queryset=Territorio.objects.filter(activo=True)
        self.fields['responsable'].queryset=Funcionario.objects.all()
        self.fields['tipo'].queryset=TipoAtencion.objects.filter(activo=True)
        # Subtipos solo del tipo elegido; evita combinaciones incorrectas en el formulario.
        tipo_id = self.data.get('tipo') if self.is_bound else (self.instance.tipo_id or self.initial.get('tipo'))
        try:
            tipo_id = int(tipo_id)
        except (TypeError, ValueError):
            tipo_id = None
        self.fields['subtipo'].queryset = (SubtipoAtencion.objects.filter(activo=True, tipo_id=tipo_id)
                                           if tipo_id else SubtipoAtencion.objects.none())
        if usuario and not es_admin(usuario):
            p=funcionario_usuario(usuario)
            ids=[p.delegacion_id] if p else []
            for campo in ('delegacion','vecino','territorio','responsable'):
                self.fields[campo].queryset=self.fields[campo].queryset.filter(
                    pk__in=ids if campo=='delegacion' else []
                ) if campo == 'delegacion' else self.fields[campo].queryset.filter(delegacion_id__in=ids)
            if p and not self.is_bound and not self.instance.pk:
                self.initial.setdefault('delegacion',p.delegacion_id)
                self.initial.setdefault('responsable',p.pk)
        self.estilos()


class CartaForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model=CartaTubo
        fields=['delegacion','gestion','asunto','destinatario','numero_oficio','descripcion','estado','adjunto']
        widgets={'descripcion':forms.Textarea(attrs={'rows':3})}

    def __init__(self,*args, usuario=None, **kwargs):
        super().__init__(*args,**kwargs)
        if usuario and not es_admin(usuario):
            p=funcionario_usuario(usuario)
            ids=[p.delegacion_id] if p else []
            self.fields['delegacion'].queryset=Delegacion.objects.filter(pk__in=ids)
            self.fields['gestion'].queryset=GestionSocial.objects.filter(delegacion_id__in=ids)
            if p and not self.is_bound and not self.instance.pk:
                self.initial.setdefault('delegacion',p.delegacion_id)
        self.estilos()


class TerritorioForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model=Territorio
        fields=['delegacion','nombre','descripcion','activo']
        widgets={'descripcion':forms.Textarea(attrs={'rows':2})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.estilos()


class TipoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model=TipoAtencion
        fields=['nombre','activo']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.estilos()


class SubtipoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model=SubtipoAtencion
        fields=['tipo','nombre','activo']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.estilos()
