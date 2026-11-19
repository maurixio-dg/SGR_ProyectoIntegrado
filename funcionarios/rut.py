"""Validación y normalización del RUT chileno para formularios del SGR."""
import re
from django.core.exceptions import ValidationError


def normalizar_rut(valor):
    """Devuelve el RUT como 12345678-5; admite puntos, guion y espacios."""
    original = str(valor or "").strip().upper()
    limpio = re.sub(r"[.\s-]", "", original)
    if not re.fullmatch(r"[0-9]{1,8}[0-9K]", limpio):
        raise ValidationError(
            "Ingrese un RUT válido, por ejemplo 12.345.678-5."
        )
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma = sum(int(cifra) * [2, 3, 4, 5, 6, 7][i % 6]
               for i, cifra in enumerate(reversed(cuerpo)))
    resto = 11 - (suma % 11)
    esperado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    if dv != esperado:
        raise ValidationError(
            f"El dígito verificador es incorrecto: para {int(cuerpo)} corresponde {esperado}."
        )
    return f"{int(cuerpo)}-{dv}"
