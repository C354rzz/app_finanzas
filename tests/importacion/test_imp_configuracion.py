from django.conf import settings


def test_dependencias_de_importacion_instaladas():
    import anthropic
    import django_q
    import pydantic
    import pypdf

    assert anthropic.__version__.startswith("1.")
    assert pypdf.__version__ >= "6"
    assert pydantic.VERSION.startswith("2.")
    assert django_q is not None


def test_cola_de_tareas_en_la_base_de_datos():
    assert "django_q" in settings.INSTALLED_APPS
    assert settings.Q_CLUSTER["orm"] == "default"
    assert settings.Q_CLUSTER["workers"] == 1
    assert settings.Q_CLUSTER["retry"] > settings.Q_CLUSTER["timeout"]
    assert settings.IMPORTACION_EXTRACTOR == "apps.importacion.extractor.ExtractorClaude"
    assert settings.DATA_UPLOAD_MAX_NUMBER_FILES == 20


def test_docker_compose_tiene_worker():
    texto = (settings.BASE_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    assert "worker:" in texto
    assert "qcluster" in texto
