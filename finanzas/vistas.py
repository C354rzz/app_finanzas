from django.db import connection
from django.http import JsonResponse


def salud(request):
    """Responde ok si la app y la base de datos están disponibles."""
    connection.ensure_connection()
    return JsonResponse({"estado": "ok"})
