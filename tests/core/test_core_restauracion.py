import json
import zipfile
from decimal import Decimal as D

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalogos.models import Cuenta, Persona
from apps.core.models import Membresia
from apps.core.respaldo import ErrorRespaldo, crear_respaldo, leer_respaldo, restaurar_respaldo

# Restaurar vacía y recarga la base (flush + loaddata): pruebas con transacciones reales.
pytestmark = pytest.mark.django_db(transaction=True)


def zip_con(ruta, **contenido):
    with zipfile.ZipFile(ruta, "w") as archivo:
        for nombre, datos in contenido.items():
            archivo.writestr(nombre.replace("__", "/"), datos)
    return ruta


def test_restaurar_recupera_datos_y_archivos(catalogo, hogar, usuario):
    default_storage.save("documentos/1/abc.pdf", ContentFile(b"%PDF-1.4 prueba"))
    respaldo = crear_respaldo()
    Cuenta.objects.filter(pk=catalogo.tarjeta.pk).update(saldo_actual=D("1"))
    Persona.objects.create(hogar=hogar, nombre="Nueva", parentesco="hija")
    default_storage.delete("documentos/1/abc.pdf")

    resultado = restaurar_respaldo(respaldo)

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")
    assert not Persona.objects.filter(nombre="Nueva").exists()
    assert Membresia.objects.get().usuario.email == usuario.email
    assert get_user_model().objects.get().check_password("clave-segura-123")
    assert default_storage.open("documentos/1/abc.pdf").read() == b"%PDF-1.4 prueba"
    assert resultado.archivos == 1
    assert resultado.seguridad.name.startswith("finanzas-antes-de-restaurar-")


def test_instalacion_limpia_sin_respaldo_de_seguridad(catalogo):
    respaldo = crear_respaldo()
    call_command("flush", interactive=False, verbosity=0)

    resultado = restaurar_respaldo(respaldo)

    assert resultado.seguridad is None
    assert Cuenta.objects.count() == 4


def test_archivo_que_no_es_zip_no_toca_la_base(catalogo, tmp_path):
    roto = tmp_path / "roto.zip"
    roto.write_bytes(b"no es un zip")

    with pytest.raises(ErrorRespaldo, match="No se pudo abrir"):
        restaurar_respaldo(roto)
    assert Cuenta.objects.count() == 4


def test_zip_de_otra_cosa(tmp_path):
    otro = zip_con(tmp_path / "otro.zip", **{"hola.txt": "hola"})

    with pytest.raises(ErrorRespaldo, match="no es un respaldo de Finanzas"):
        leer_respaldo(otro)


def test_rutas_que_salen_de_media_se_rechazan(tmp_path):
    malo = tmp_path / "malo.zip"
    with zipfile.ZipFile(malo, "w") as archivo:
        archivo.writestr("manifiesto.json", json.dumps({"formato": 1, "migraciones": {}}))
        archivo.writestr("datos.json", "[]")
        archivo.writestr("media/../../finanzas/settings.py", "x")

    with pytest.raises(ErrorRespaldo, match="ruta no permitida"):
        leer_respaldo(malo)


def test_respaldo_de_una_version_mas_nueva(catalogo, tmp_path):
    manifiesto = {"formato": 1, "migraciones": {"catalogos": ["9999_futuro"]}}
    nuevo = zip_con(
        tmp_path / "nuevo.zip", **{"manifiesto.json": json.dumps(manifiesto), "datos.json": "[]"}
    )

    with pytest.raises(ErrorRespaldo, match="versión más nueva"):
        restaurar_respaldo(nuevo)
    assert Cuenta.objects.count() == 4


def test_datos_invalidos_revierten_todo(catalogo, tmp_path):
    respaldo = crear_respaldo()
    with zipfile.ZipFile(respaldo) as original:
        manifiesto = original.read("manifiesto.json")
    datos = [{"model": "catalogos.cuenta", "pk": 1, "fields": {"hogar": 999999, "nombre": "X",
              "tipo": "debito", "creado_en": "2026-10-09T00:00:00Z",
              "actualizado_en": "2026-10-09T00:00:00Z"}}]  # fmt: skip
    malo = zip_con(
        tmp_path / "malo.zip", **{"manifiesto.json": manifiesto, "datos.json": json.dumps(datos)}
    )

    with pytest.raises(ErrorRespaldo, match="no se cambió nada"):
        restaurar_respaldo(malo)
    assert Cuenta.objects.count() == 4


def test_comando_pide_confirmacion(catalogo, capsys):
    respaldo = crear_respaldo()

    with pytest.raises(CommandError, match="--confirmar"):
        call_command("restaurar", respaldo.name)
    call_command("restaurar", respaldo.name, confirmar=True)

    assert "Restaurado" in capsys.readouterr().out
    assert Cuenta.objects.count() == 4


def test_comando_con_archivo_inexistente():
    with pytest.raises(CommandError, match="No existe el respaldo"):
        call_command("restaurar", "no-existe.zip", confirmar=True)


@pytest.mark.parametrize("ruta", ["media//tmp/escapado.txt", "media/./x.txt", "media/"])
def test_rutas_media_vacias_absolutas_o_con_punto_se_rechazan(tmp_path, ruta):
    malo = tmp_path / "malo.zip"
    with zipfile.ZipFile(malo, "w") as archivo:
        archivo.writestr("manifiesto.json", json.dumps({"formato": 1, "migraciones": {}}))
        archivo.writestr("datos.json", "[]")
        archivo.writestr(ruta, "x")

    with pytest.raises(ErrorRespaldo, match="ruta no permitida"):
        leer_respaldo(malo)


def test_manifiesto_con_migraciones_invalidas(tmp_path):
    malo = zip_con(
        tmp_path / "malo.zip",
        **{"manifiesto.json": json.dumps({"formato": 1, "migraciones": ["x"]}), "datos.json": "[]"},
    )

    with pytest.raises(ErrorRespaldo, match="formato desconocido"):
        leer_respaldo(malo)


def test_error_al_escribir_los_archivos_da_mensaje_claro(catalogo, settings, tmp_path):
    default_storage.save("documentos/1/abc.pdf", ContentFile(b"%PDF-1.4 prueba"))
    respaldo = crear_respaldo()
    archivo = tmp_path / "no-es-carpeta"
    archivo.write_text("x")
    settings.MEDIA_ROOT = archivo

    with pytest.raises(ErrorRespaldo, match="respaldo de seguridad"):
        restaurar_respaldo(respaldo)
