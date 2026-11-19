"""Categorizar solo registros importados y aún sin clasificar; requiere --aplicar."""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from organizaciones.clasificacion import sugerir_tipo
from organizaciones.models import OrganizacionComunitaria


class Command(BaseCommand):
    help = 'Previsualiza o aplica tipos sugeridos, sin alterar la verificación municipal.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Confirma el guardado de los tipos sugeridos en MariaDB.')

    def handle(self, *args, **options):
        base = (OrganizacionComunitaria.objects
                .filter(tipo=OrganizacionComunitaria.Tipo.SIN_CLASIFICAR)
                .exclude(fuente_archivo='')
                .only('pk', 'nombre', 'tipo'))
        total = 0
        candidatos = []
        conteo = Counter()
        for org in base.iterator(chunk_size=500):
            total += 1
            sugerencia = sugerir_tipo(org.nombre)
            if sugerencia:
                conteo[sugerencia] += 1
                candidatos.append((org.pk, sugerencia))
        self.stdout.write(f'Registros importados sin clasificar: {total}')
        for clave, etiqueta in OrganizacionComunitaria.Tipo.choices:
            if conteo[clave]:
                self.stdout.write(f'  {etiqueta}: {conteo[clave]}')
        self.stdout.write(f'  Sin coincidencia clara: {total - len(candidatos)}')
        if not options['aplicar']:
            self.stdout.write(self.style.WARNING(
                'VISTA PREVIA: no se modificó la base de datos. '
                'Para guardar las sugerencias: python manage.py clasificar_organizaciones --aplicar'
            ))
            return
        actualizadas = 0
        with transaction.atomic():
            for pk, tipo in candidatos:
                actualizadas += OrganizacionComunitaria.objects.filter(
                    pk=pk, tipo=OrganizacionComunitaria.Tipo.SIN_CLASIFICAR
                ).exclude(fuente_archivo='').update(tipo=tipo)
        self.stdout.write(self.style.SUCCESS(
            f'Se clasificaron {actualizadas} registros. '
            'El estado de verificación, datos originales y otros CRUD no cambiaron.'
        ))
