"""Configuración de medición y ausencias de la matriz SGR (sin alterar tablas maestras)."""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class ConfiguracionMetaSGR(models.Model):
    meta = models.OneToOneField("gestion.MetaIndicador", on_delete=models.CASCADE, related_name="configuracion_sgr")
    cargo = models.ForeignKey("catalogos.Cargo", on_delete=models.PROTECT, null=True, blank=True)
    funcion = models.ForeignKey("catalogos.Funcion", on_delete=models.PROTECT, null=True, blank=True)
    funcionario = models.ForeignKey("funcionarios.Funcionario", on_delete=models.PROTECT, null=True, blank=True)
    tope_porcentaje = models.DecimalField(
        "Tope de cumplimiento (%)", max_digits=6, decimal_places=2,
        default=Decimal("120.00"), validators=[MinValueValidator(Decimal("100")), MaxValueValidator(Decimal("200"))],
    )

    class Meta:
        verbose_name = "Configuración de meta SGR"
        verbose_name_plural = "Configuraciones de metas SGR"

    def clean(self):
        super().clean()
        errores = {}
        if self.funcionario_id and self.meta_id:
            if self.funcionario.delegacion_id != self.meta.delegacion_id:
                errores["funcionario"] = "El funcionario debe pertenecer a la delegación de la meta."
            if self.cargo_id and self.funcionario.cargo_id != self.cargo_id:
                errores["cargo"] = "El cargo debe coincidir con el del funcionario."
        if self.funcion_id and self.cargo_id and self.funcion.cargo_id != self.cargo_id:
            errores["funcion"] = "La función debe pertenecer al cargo indicado."
        if self.funcion_id and self.funcionario_id and self.funcion.cargo_id != self.funcionario.cargo_id:
            errores["funcion"] = "La función no corresponde al cargo del funcionario."
        # Validaciones adicionales de la hoja de origen y su ámbito de ponderación.
        from .ponderaciones_sgr import estado_cargo_matriz, comprobar_ponderacion
        if self.tope_porcentaje is not None and self.tope_porcentaje > Decimal("120.00"):
            errores["tope_porcentaje"] = "El tope municipal máximo es 120%."
        if self.meta_id:
            extra, _ = estado_cargo_matriz(
                self.meta,
                funcionario=self.funcionario if self.funcionario_id else None,
                cargo=self.cargo if self.cargo_id else None,
                funcion=self.funcion if self.funcion_id else None,
            )
            errores.update(extra)
            if self.meta.activo:
                advertencia = comprobar_ponderacion(
                    delegacion_id=self.meta.delegacion_id,
                    periodo_id=self.meta.periodo_id,
                    ponderacion=self.meta.ponderacion,
                    funcionario_id=self.funcionario_id,
                    cargo_id=self.cargo_id,
                    excluir_meta_id=self.meta_id,
                )
                if advertencia:
                    errores["__all__"] = advertencia
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f"Configuración de {self.meta.nombre}"


class AusenciaSGR(models.Model):
    class Tipo(models.TextChoices):
        VACACIONES = "VAC", "Vacaciones"
        LICENCIA = "LIC", "Licencia médica"
        DIA_LIBRE = "LIB", "Día libre"
        ADMINISTRATIVO = "ADM", "Día administrativo"

    funcionario = models.ForeignKey("funcionarios.Funcionario", on_delete=models.PROTECT, related_name="ausencias_sgr")
    periodo = models.ForeignKey("gestion.Periodo", on_delete=models.PROTECT, related_name="ausencias_sgr")
    tipo = models.CharField(max_length=3, choices=Tipo.choices)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ausencias_sgr_registradas")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_inicio", "-pk"]
        verbose_name = "Ausencia para ajuste de metas"
        verbose_name_plural = "Ausencias para ajuste de metas"

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errores["fecha_fin"] = "La fecha final debe ser igual o posterior a la inicial."
        if self.periodo_id and self.fecha_inicio and self.fecha_fin:
            if self.fecha_inicio < self.periodo.fecha_inicio or self.fecha_fin > self.periodo.fecha_fin:
                errores["fecha_inicio"] = "Las fechas deben estar dentro del período seleccionado."
        if self.funcionario_id and self.fecha_inicio and self.fecha_fin and self.fecha_fin >= self.fecha_inicio:
            repetidas = type(self).objects.filter(
                funcionario_id=self.funcionario_id,
                fecha_inicio__lte=self.fecha_fin,
                fecha_fin__gte=self.fecha_inicio,
            )
            if self.pk:
                repetidas = repetidas.exclude(pk=self.pk)
            if repetidas.exists():
                errores["fecha_inicio"] = "Ya existe una ausencia registrada en esas fechas."
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f"{self.funcionario} - {self.get_tipo_display()}"
