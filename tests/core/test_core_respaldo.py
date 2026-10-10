import json
import re
import zipfile

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command

from apps.core.respaldo import ErrorRespaldo, crear_respaldo, rotar

pytestmark = pytest.mark.django_db


def test_respaldo_incluye_manifiesto_datos_y_archivos(catalogo):
    default_storage.save("documentos/1/abc.pdf", ContentFile(b"%PDF-1.4 prueba"))

    destino = crear_respaldo()

    with zipfile.ZipFile(destino) as respaldo:
        nombres = set(respaldo.namelist())
        manifiesto = json.loads(respaldo.read("manifiesto.json"))
        datos = json.loads(respaldo.read("datos.json"))
    assert {"manifiesto.json", "datos.json", "media/documentos/1/abc.pdf"} <= nombres
    assert manifiesto["formato"] == 1
    assert "0001_initial" in manifiesto["migraciones"]["catalogos"]
    assert manifiesto["registros"]["catalogos.cuenta"] == 4
    assert any(registro["model"] == "core.usuario" for registro in datos)
    excluidos = ("contenttypes.", "auth.permission", "sessions.", "django_q.")
    assert not any(registro["model"].startswith(excluidos) for registro in datos)


def test_nombre_con_fecha_y_sin_archivos_a_medias(hogar):
    destino = crear_respaldo()

    assert destino.parent == settings.RESPALDOS_DIR
    assert re.fullmatch(r"finanzas-\d{8}-\d{6}\.zip", destino.name)
    assert list(settings.RESPALDOS_DIR.glob("*.tmp")) == []


def test_rotacion_conserva_los_mas_recientes_y_los_de_seguridad(tmp_path):
    for dia in range(1, 6):
        (tmp_path / f"finanzas-2026100{dia}-030000.zip").write_bytes(b"x")
    seguridad = tmp_path / "finanzas-antes-de-restaurar-20261001-030000.zip"
    seguridad.write_bytes(b"x")

    borrados = rotar(tmp_path, 3)

    assert len(borrados) == 2
    assert sorted(p.name for p in tmp_path.glob("finanzas-2*.zip")) == [
        "finanzas-20261003-030000.zip",
        "finanzas-20261004-030000.zip",
        "finanzas-20261005-030000.zip",
    ]
    assert seguridad.exists()


def test_carpeta_invalida_da_error_claro(hogar, tmp_path):
    archivo = tmp_path / "no-es-carpeta"
    archivo.write_text("x")

    with pytest.raises(ErrorRespaldo, match="carpeta de respaldos"):
        crear_respaldo(archivo / "respaldos")


def test_comando_respaldar(hogar, capsys):
    call_command("respaldar", conservar=2)

    assert "Respaldo creado" in capsys.readouterr().out
    assert len(list(settings.RESPALDOS_DIR.glob("finanzas-*.zip"))) == 1
