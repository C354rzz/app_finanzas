from apps.core.models import Membresia


class HogarMiddleware:
    """Expone en request.hogar el hogar activo del usuario autenticado (o None)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.hogar = None
        if request.user.is_authenticated:
            membresia = (
                Membresia.objects.select_related("hogar")
                .filter(usuario=request.user)
                .order_by("creado_en", "id")
                .first()
            )
            if membresia:
                request.hogar = membresia.hogar
        return self.get_response(request)
