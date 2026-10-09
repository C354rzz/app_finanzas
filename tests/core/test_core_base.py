from django.conf import settings
from django.template.loader import render_to_string


def test_base_incluye_estilos_htmx_csrf_y_modal(rf, django_user_model):
    solicitud = rf.get("/")
    solicitud.user = django_user_model(email="x@example.com")
    solicitud.hogar = None

    html = render_to_string("base.html", request=solicitud)

    assert "css/app.css" in html
    assert "vendor/htmx-2.0.11.min.js" in html
    assert "X-CSRFToken" in html
    assert 'id="modal-contenido"' in html


def test_htmx_esta_en_el_repositorio():
    archivo = settings.BASE_DIR / "static" / "vendor" / "htmx-2.0.11.min.js"

    assert archivo.stat().st_size > 10_000
