from django.conf import settings


def test_env_de_ejemplo_listo_para_uso_diario():
    texto = (settings.BASE_DIR / ".env.example").read_text(encoding="utf-8")

    assert "DJANGO_DEBUG=0" in texto
    assert "DJANGO_CSRF_TRUSTED_ORIGINS=" in texto
    assert ".ts.net" in texto


def test_readme_explica_tailscale_y_el_modo_de_uso_diario():
    texto = (settings.BASE_DIR / "README.md").read_text(encoding="utf-8")

    assert "## Uso diario y acceso desde el celular" in texto
    assert "tailscale serve --bg 8000" in texto
    assert "docker compose -f docker-compose.yml up -d --build" in texto


def test_scripts_de_respaldo_documentados():
    scripts = settings.BASE_DIR / "scripts"
    readme = (settings.BASE_DIR / "README.md").read_text(encoding="utf-8")

    for nombre in ("respaldar.ps1", "restaurar.ps1", "programar_respaldo.ps1"):
        assert (scripts / nombre).is_file(), nombre
        assert nombre in readme
    assert "RESTAURAR" in (scripts / "restaurar.ps1").read_text(encoding="utf-8")
