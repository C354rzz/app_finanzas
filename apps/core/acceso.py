from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def requiere_hogar(vista):
    """Exige sesión iniciada y un hogar activo (request.hogar)."""

    @wraps(vista)
    @login_required
    def envoltura(request, *args, **kwargs):
        if request.hogar is None:
            return render(request, "core/sin_hogar.html", status=403)
        return vista(request, *args, **kwargs)

    return envoltura
