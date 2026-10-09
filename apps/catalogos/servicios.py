from apps.catalogos.models import Categoria

# Las 12 categorías del Excel "Financial Planner template", en su orden original.
CATEGORIAS_INICIALES = [
    ("Casa", "🏡"),
    ("Comida", "🥑"),
    ("Familia", "❤️"),
    ("Transporte", "🚓"),
    ("Viajes", "✈️"),
    ("Deudas", "🏦"),
    ("Salud", "🚑"),
    ("Suscripciones", "📺"),
    ("Gastos anuales", "🗓️"),
    ("Cuidado personal", "💅"),
    ("Entretenimiento", "📽️"),
    ("Otros", "🛸"),
]


def sembrar_catalogos(hogar):
    """Crea las categorías iniciales que falten. Devuelve cuántas creó."""
    creadas = 0
    for orden, (nombre, icono) in enumerate(CATEGORIAS_INICIALES, start=1):
        _, nueva = Categoria.objects.get_or_create(
            hogar=hogar, nombre=nombre, defaults={"icono": icono, "orden": orden}
        )
        creadas += nueva
    return creadas
