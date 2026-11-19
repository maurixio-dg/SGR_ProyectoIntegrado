"""Catálogo histórico de metas de la matriz municipal: importación nunca modifica mediciones existentes."""
from django.conf import settings
from django.db import models


class CatalogoMatrizSGR(models.Model):
    nombre_archivo = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, unique=True)
    fecha_importacion = models.DateTimeField(auto_now_add=True)
    importado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    origen = models.CharField(max_length=120, default='Matriz SGR Trimestre 2026')

    class Meta:
        ordering = ['-fecha_importacion', '-pk']
        verbose_name = 'Importación de matriz SGR'

    def __str__(self):
        return f'{self.origen} — {self.fecha_importacion:%d/%m/%Y}'


class ItemMatrizSGR(models.Model):
    class Clase(models.TextChoices):
        CANTIDAD = 'CANT', 'Cantidad trimestral'
        PORCENTAJE = 'PORC', 'Meta porcentual'
        DINAMICA = 'DIN', 'Meta variable'
        ESPECIAL = 'ESP', 'Felicitaciones / reclamos'
        REVISAR = 'REV', 'Requiere revisión'

    catalogo = models.ForeignKey(CatalogoMatrizSGR, on_delete=models.PROTECT, related_name='items')
    hoja = models.CharField(max_length=50)
    fila = models.PositiveIntegerField()
    nombre = models.CharField(max_length=200)
    ponderacion = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    meta_original = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    clase = models.CharField(max_length=4, choices=Clase.choices, default=Clase.REVISAR)
    celda_item = models.CharField(max_length=10)
    celda_meta = models.CharField(max_length=10, blank=True)
    formula_meta = models.CharField(max_length=350, blank=True)

    class Meta:
        ordering = ['hoja', 'fila']
        unique_together = [('catalogo', 'hoja', 'fila')]
        verbose_name = 'Ítem de matriz SGR'

    def __str__(self):
        return f'{self.hoja} — {self.nombre}'

    @property
    def es_vinculable(self):
        return (self.clase == self.Clase.CANTIDAD and self.meta_original is not None
                and self.meta_original == self.meta_original.to_integral_value()
                and self.meta_original > 0 and self.ponderacion is not None
                and 0 < self.ponderacion <= 100)


class VinculoMatrizSGR(models.Model):
    """La meta existente calcula el resultado con las actividades aprobadas de siempre."""
    item = models.ForeignKey(ItemMatrizSGR, on_delete=models.PROTECT, related_name='vinculos')
    meta = models.OneToOneField('gestion.MetaIndicador', on_delete=models.PROTECT, related_name='vinculo_matriz_sgr')
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vinculación de matriz SGR'

    def __str__(self):
        return f'{self.item} → {self.meta}'

# Fase 5.3: mediciones especiales de la matriz, sin cambiar MetaIndicador.
from .modelos_especiales import MedicionEspecialSGR, AuditoriaMedicionEspecialSGR


# Validación de cargos por hoja; no cambia las metas anteriores.
# Fragmento añadido al final de matriz_sgr/models.py por el instalador.
class CorrespondenciaHojaCargoSGR(models.Model):
    """Equivalencia explícita hoja del Excel → cargo real, sin adivinar por abreviaturas."""
    catalogo = models.ForeignKey('matriz_sgr.CatalogoMatrizSGR', on_delete=models.PROTECT, related_name='correspondencias_cargo')
    hoja = models.CharField(max_length=50)
    cargo = models.ForeignKey('catalogos.Cargo', on_delete=models.PROTECT, related_name='hojas_matriz_sgr')
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['catalogo', 'hoja'], name='uq_hoja_cargo_matriz_sgr')]
        verbose_name = 'Correspondencia hoja/cargo de la matriz'

    def __str__(self):
        return f'{self.hoja} → {self.cargo}'

# SGR_VALORACIONES_FORMALES_2026
from .modelos_valoraciones import ValoracionCiudadanaSGR, AuditoriaValoracionCiudadanaSGR
