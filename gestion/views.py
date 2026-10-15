from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from functools import wraps

from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from catalogos.models import Cargo
from gestion.models import Periodo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from .models import Periodo
from .forms import PeriodoForm

@login_required
def dashboard(request):
    contexto = {
        "total_delegaciones": Delegacion.objects.count(),
        "total_funcionarios": Funcionario.objects.count(),
        "total_cargos": Cargo.objects.count(),
        "total_actividades": 0,  # temporal mientras no exista el modelo Actividad
    }
    return render(request, "dashboard.html", contexto)


# ==========================================
# CONTROL DE ACCESO A PERIODOS
# ==========================================

def solo_administrador(vista):
    @wraps(vista)
    @login_required
    def protegida(request, *args, **kwargs):

        usuario = request.user

        if not (
            usuario.is_superuser
            or getattr(usuario, "rol", None) == "ADMIN"
        ):
            raise PermissionDenied(
                "No tiene permisos para administrar períodos."
            )

        return vista(request, *args, **kwargs)

    return protegida


# ==========================================
# LISTAR PERIODOS
# ==========================================

@solo_administrador
def listar_periodos(request):

    buscar = request.GET.get("buscar", "").strip()
    estado = request.GET.get("estado", "").strip()

    periodos = Periodo.objects.all()

    if buscar:
        periodos = periodos.filter(
            Q(nombre__icontains=buscar)
            | Q(descripcion__icontains=buscar)
        )

    estados_validos = [
        valor for valor, etiqueta in Periodo.Estado.choices
    ]

    if estado in estados_validos:
        periodos = periodos.filter(estado=estado)

    contexto = {
        "periodos": periodos,
        "buscar": buscar,
        "estado": estado,
        "estados": Periodo.Estado.choices,
        "total": periodos.count(),
    }

    return render(
        request,
        "gestion/periodos/listar.html",
        contexto
    )


# ==========================================
# CREAR PERIODO
# ==========================================

@solo_administrador
def crear_periodo(request):

    formulario = PeriodoForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():

        formulario.save()

        messages.success(
            request,
            "Período registrado correctamente."
        )

        return redirect("gestion:listar_periodos")

    return render(
        request,
        "gestion/periodos/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Registrar período",
            "accion": "Registrar período",
        }
    )


# ==========================================
# EDITAR PERIODO
# ==========================================

@solo_administrador
def editar_periodo(request, pk):

    periodo = get_object_or_404(Periodo, pk=pk)

    formulario = PeriodoForm(
        request.POST or None,
        instance=periodo
    )

    if request.method == "POST" and formulario.is_valid():

        formulario.save()

        messages.success(
            request,
            "Período actualizado correctamente."
        )

        return redirect("gestion:listar_periodos")

    return render(
        request,
        "gestion/periodos/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Editar período",
            "accion": "Guardar cambios",
        }
    )



# ==========================================
# INTERFACES DE ACTIVIDADES
# ETAPA 2: SOLO TEMPLATES
# ==========================================

@login_required
def listar_actividades(request):
    return render(
        request,
        "gestion/actividades/listar.html"
    )


@login_required
def registrar_actividad(request):
    contexto = {
        "delegaciones": Delegacion.objects.filter(estado=True),
        "funcionarios": Funcionario.objects.select_related(
            "delegacion", "cargo"
        ).all(),
        "periodos": Periodo.objects.all(),
    }

    return render(
        request,
        "gestion/actividades/registrar.html",
        contexto
    )



# ==========================================
# VALIDACIÓN DE EVIDENCIAS
# ETAPA 2 - INTERFAZ DEMOSTRATIVA
# ==========================================

@login_required
def validar_evidencias(request):
    return render(
        request,
        "gestion/actividades/validar_evidencias.html"
    )



# ==========================================
# AGENDA COLECTIVA - INTERFAZ DEMOSTRATIVA
# ==========================================

@login_required
def agenda_colectiva(request):
    return render(
        request,
        "gestion/agenda/listar.html"
    )


@login_required
def detalle_compromiso(request, codigo):
    compromisos = {
        "SGR-AG-001": {
            "codigo": "SGR-AG-001",
            "fecha": "15/10/2026",
            "solicitante": "Organización vecinal A",
            "territorio": "Sector Norte",
            "responsable": "Funcionario A",
            "area": "Operaciones",
            "estado": "Ingresado",
            "descripcion": "Solicitud de coordinación para una jornada comunitaria.",
            "observaciones": "Pendiente de revisión inicial.",
        },
        "SGR-AG-002": {
            "codigo": "SGR-AG-002",
            "fecha": "16/10/2026",
            "solicitante": "Organización territorial B",
            "territorio": "Sector Centro",
            "responsable": "Funcionario B",
            "area": "Área social",
            "estado": "Pendiente",
            "descripcion": "Coordinar atención municipal para vecinos.",
            "observaciones": "Esperando confirmación de disponibilidad.",
        },
        "SGR-AG-003": {
            "codigo": "SGR-AG-003",
            "fecha": "18/10/2026",
            "solicitante": "Comité comunitario C",
            "territorio": "Sector Sur",
            "responsable": "Funcionario C",
            "area": "Infraestructura",
            "estado": "En proceso",
            "descripcion": "Seguimiento de solicitud de mejoramiento de espacio público.",
            "observaciones": "Coordinación inicial realizada.",
        },
        "SGR-AG-004": {
            "codigo": "SGR-AG-004",
            "fecha": "20/10/2026",
            "solicitante": "Junta vecinal D",
            "territorio": "Sector Norte",
            "responsable": "Funcionario A",
            "area": "Territorial",
            "estado": "Realizado",
            "descripcion": "Reunión informativa con representantes del sector.",
            "observaciones": "Actividad de demostración finalizada.",
        },
    }

    from django.http import Http404

    compromiso = compromisos.get(codigo)

    if compromiso is None:
        raise Http404("Compromiso no encontrado")

    return render(
        request,
        "gestion/agenda/detalle.html",
        {"compromiso": compromiso}
    )


# ==========================================
# INDICADORES Y METAS - INTERFAZ DEMOSTRATIVA
# ==========================================

@login_required
def indicadores(request):
    from gestion.models import Periodo

    return render(
        request,
        "gestion/indicadores/listar.html",
        {
            "periodos": Periodo.objects.all()
        }
    )



# ==========================================
# INFORMES DE GESTIÓN - ETAPA 2
# INTERFAZ DEMOSTRATIVA
# ==========================================

@login_required
def informes_gestion(request):
    from delegaciones.models import Delegacion
    from gestion.models import Periodo

    contexto = {
        "delegaciones": Delegacion.objects.all(),
        "periodos": Periodo.objects.all(),
    }

    return render(
        request,
        "gestion/informes/listar.html",
        contexto
    )
