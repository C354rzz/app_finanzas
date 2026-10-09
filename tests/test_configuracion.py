import os
import subprocess
import sys

CODIGO = "import finanzas.settings as s; print(s.SECRET_KEY)"


def _cargar_settings(**entorno):
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    env.update(entorno)
    return subprocess.run(
        [sys.executable, "-c", CODIGO], env=env, capture_output=True, text=True, check=False
    )


def test_produccion_sin_secret_key_no_arranca():
    resultado = _cargar_settings(DJANGO_DEBUG="0")

    assert resultado.returncode != 0
    assert "DJANGO_SECRET_KEY" in resultado.stderr


def test_produccion_con_secret_key_arranca():
    resultado = _cargar_settings(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="clave-real-larga")

    assert resultado.returncode == 0
    assert resultado.stdout.strip() == "clave-real-larga"


def test_desarrollo_usa_clave_por_defecto():
    resultado = _cargar_settings(DJANGO_DEBUG="1")

    assert resultado.returncode == 0
    assert resultado.stdout.strip() == "solo-para-desarrollo-no-usar-en-produccion"
