# Plan 4 — Importación con IA: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subir estados de cuenta, recibos de nómina y recibos de servicios en PDF (o ZIP), extraer su texto, pedir a Claude los movimientos propuestos y revisarlos antes de guardarlos como movimientos.

**Architecture:** Nueva app `apps/importacion` con `Documento`, `MovimientoPropuesto` y `ReglaClasificacion`. La subida guarda el PDF (deduplicado por SHA-256) y encola el procesamiento en **Django-Q2** usando la base de datos como cola; un contenedor `worker` (misma imagen, `python manage.py qcluster`) extrae el texto con **pypdf**, oculta datos personales, llama a **Claude** (`claude-opus-5-5`, salida JSON con esquema) y crea propuestas aplicando primero las reglas del hogar (RN-12) y marcando posibles duplicados (RN-11). La pantalla de revisión acepta, edita o descarta; aceptar crea el movimiento con `guardar_movimiento` (RN-14) y `origen = importado`.

**Tech Stack:** Django 5.2, django-q2 1.11, pypdf 6 (con `cryptography` para PDFs cifrados), anthropic 1.13 (SDK oficial de Python), pydantic 2, HTMX 2.0.11, PostgreSQL 17.

**Spec:** `docs/DEF.md` (§3.10 IMP-01..14, RN-11, RN-12, RNF-03, RNF-07), `docs/ARQUITECTURA.md` (flujo de importación, contenedor worker), `docs/modelo-datos.dbml` (documento, movimiento_propuesto, regla_clasificacion).

### Hoja de ruta (este es el plan 4 de 5)
| Plan | Contenido |
|---|---|
| 1 — Fundación ✅ | Docker, CI, usuario, hogar, catálogos (admin), motor de cálculos |
| 2 — Operación diaria ✅ | Login y UI, movimientos, presupuesto, tablero, catálogos en UI |
| 3 — Planeación ✅ | Metas, deudas, patrimonio, simulador |
| **4 — Importación IA (este)** | Subida, worker, texto, Claude, reglas, duplicados, revisión |
| 5 — Operación | PWA, Tailscale, respaldo, importación inicial desde Excel |

Requisitos del DEF que cubre: IMP-01..14 (incluye los deseables IMP-12 actualizar saldo e IMP-14 ver original), RN-11, RN-12, RNF-03 y RNF-07.

### Decisiones de este plan (para revisión del usuario)
1. **Cola sin Redis:** Django-Q2 usa la propia base de datos. Nuevo contenedor `worker` con la misma imagen. Tras cambiar código hay que reiniciarlo (`docker compose restart worker`).
2. **Privacidad antes de enviar a la IA:** se ocultan RFC, CURP y cualquier número de 10 o más dígitos (tarjeta, CLABE, NSS, número de servicio), conservando los últimos 4 (`****1234`). No se envía el nombre del archivo ni el PDF, solo el texto. Sí se envían los nombres de tus catálogos y las direcciones de tus domicilios (para deducir a qué casa pertenece un recibo).
3. **IA:** `claude-opus-5-5` con `effort: low`, salida en JSON con esquema fijo y respaldo automático del servidor (`fallbacks: "default"`) si el modelo se niega. Se registra modelo, tokens y costo por documento (precios: US$4 / US$20 por millón de tokens de entrada / salida).
4. **Nómina:** un ingreso "salario" por el neto, **menos** las percepciones extraordinarias (aguinaldo, PTU, bono), que van como ingresos aparte marcados como extraordinarios; así no se cuenta dos veces.
5. **Pago a tarjeta dentro del estado de cuenta de la tarjeta:** la tarjeta queda como cuenta destino y eliges la cuenta de origen al revisar.
6. **"Recordar clasificación"** crea una regla con las dos primeras palabras de la descripción (sin números ni acentos; ej. "OXXO SUC 1234" → `oxxo suc`), limitada al mismo emisor. Las reglas se ajustan en el admin.
7. **Posible duplicado (RN-11):** mismo monto, fecha a ±2 días y la misma cuenta (como origen o destino) o un movimiento sin cuenta.
8. **Barra inferior como en el DEF:** Inicio · Movimientos · **+** · Importar · Más. En el celular, Presupuesto pasa a "Más"; en la computadora sigue en la barra lateral.
9. **Los PDFs se guardan en el volumen de Docker** y solo se pueden ver desde la app (no hay URL pública de media).
10. **Límites:** 20 MB por archivo, hasta 20 PDFs por ZIP y 20 archivos por subida. Un PDF sin texto (escaneado) queda en error "requiere OCR".
11. **Prueba real al final** con tu clave de API: se hace **solo con tu autorización**, porque cuesta dinero (centavos de dólar) y envía el texto protegido de un documento tuyo a Anthropic.

## Global Constraints

- Python **3.12**; Django **>=5.2,<5.3**; PostgreSQL **17**; `anthropic>=1.13,<2`; `django-q2>=1.11`; `pypdf[crypto]>=6`; `pydantic>=2.10`.
- Modelo de IA: **`claude-opus-5-5`** (cadena exacta), `output_config={"effort": "low", "format": {"type": "json_schema", "schema": ...}}`, beta `server-side-fallback-2026-07-01` con `fallbacks="default"`, vía `client.beta.messages.create`. **No** enviar `thinking` ni `budget_tokens`. Revisar `stop_reason` (`refusal`, `max_tokens`) antes de leer el contenido.
- A la IA **solo** se envía texto ya pasado por `proteger_datos` (RNF-03). Nunca el PDF, nunca el nombre del archivo.
- La clave `ANTHROPIC_API_KEY` vive en `.env` (fuera de git). **Las pruebas nunca llaman a la API real**: usan clientes o extractores falsos.
- Dinero: `Decimal`; montos de la IA se convierten con `Decimal(str(valor))` y se redondean a centavos. **Nunca `float`** en lo que se guarda.
- Todo modelo hereda de `ModeloDeHogar`; toda consulta filtra por `request.hogar`; id ajeno → 404 o error de formulario.
- Vistas con `requiere_hogar`; formularios del hogar con `FormularioDeHogar`; modal con `responder_formulario`; tras guardar con HTMX, `datos_actualizados()`.
- **Ningún dato personal en el repo**: los PDFs de prueba se generan en las pruebas con texto ficticio (RFC `XAXX010101000`, CURP `XEXX010101HNEXXXA4`, tarjeta `4152 3131 2345 6789`, etc.).
- Comandos desde PowerShell en `Finanzas\app_finanzas\`, dentro de Docker. Antes de cada commit: `ruff format apps tests` y `ruff check --no-cache .` sin errores.
- Cada commit termina con la línea: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Archivos hostiles o raros** (ZIP dañado, con contraseña, sin PDFs o con demasiados; PDF dañado, cifrado, escaneado, de más de 20 MB, o un `.pdf` que no es PDF) → rechazo con motivo o documento en error con mensaje claro; nunca un 500 ni un documento atascado en "procesando". *Pruebas en Task 3, Task 4, Task 7 y Task 8.*
2. **Respuesta inesperada de la IA** (JSON inválido, campos faltantes, montos negativos, en cero o enormes, fechas mal escritas, nombres de catálogo inventados, negativa del modelo, respuesta cortada) → propuestas válidas más un aviso, o error claro en el documento. *Pruebas en Task 6 y Task 8.*
3. **Procesar dos veces** (el worker reintenta, botón Reintentar, documento ya por revisar) → no se duplican propuestas ni movimientos; aceptar dos veces la misma propuesta no crea dos movimientos. *Pruebas en Task 8 y Task 9.*
4. **Ids de otro hogar** (documento, propuesta, cuenta al subir, categoría al editar, PDF original) → 404 o error de formulario; el PDF de otro hogar nunca se sirve. *Pruebas en Task 10 y Task 11.*
5. **Privacidad del texto enviado** → no lleva RFC, CURP, números de tarjeta o CLABE completos ni el nombre del archivo; los PDFs no tienen URL pública. *Pruebas en Task 4, Task 6, Task 8 y Task 10.*

---

## Estructura de archivos

```
app_finanzas\
├── pyproject.toml / uv.lock              (T1) django-q2, pypdf[crypto], anthropic, pydantic
├── .env.example                          (T1) ANTHROPIC_API_KEY
├── docker-compose.yml                    (T1) servicio worker
├── docker-compose.override.yml           (T1) worker con el código montado
├── README.md                             (T1, T12)
├── finanzas\settings.py                  (T1 django_q, Q_CLUSTER, IMPORTACION_EXTRACTOR; T2 apps.importacion)
├── finanzas\urls.py                      (T10) importar/
├── apps\movimientos\models.py            (T2) Movimiento.documento + migración 0002
├── apps\importacion\
│   ├── __init__.py apps.py admin.py      (T2)
│   ├── models.py migrations\             (T2) Documento, MovimientoPropuesto, ReglaClasificacion
│   ├── errores.py                        (T3) ErrorImportacion y subclases
│   ├── archivos.py                       (T3) sha256, es_pdf, pdfs_del_archivo (PDF o ZIP)
│   ├── texto.py                          (T4) extraer_texto (pypdf), proteger_datos
│   ├── clasificacion.py                  (T5) normalizar, reglas (RN-12), duplicados (RN-11)
│   ├── extractor.py                      (T6) esquema, instrucciones, ExtractorClaude, costo
│   ├── servicios.py                      (T7 registro; T8 procesamiento; T9 revisión)
│   ├── tareas.py                         (T8) tarea de Django-Q2
│   ├── formularios.py vistas.py urls.py  (T10, T11)
├── templates\importacion\ importar.html _documentos.html revisar.html   (T10, T11)
├── templates\componentes\navegacion.html (T10) Importar en la barra
├── templates\catalogos\indice.html       (T10) Presupuesto del mes en "Más"
└── tests\
    ├── conftest.py                       (T2) media temporal y fábrica de PDFs ficticios
    └── importacion\ test_imp_configuracion.py (T1) test_imp_modelos.py (T2)
                     test_imp_archivos.py (T3) test_imp_texto.py (T4) test_imp_clasificacion.py (T5)
                     test_imp_extractor.py (T6) test_imp_registro.py (T7) test_imp_procesamiento.py (T8)
                     test_imp_revision.py (T9) test_imp_vistas_importar.py (T10) test_imp_vistas_revisar.py (T11)
```

Los nombres de archivo de prueba son únicos a propósito (pytest con `--import-mode=importlib`, sin `__init__.py` en `tests/`).

---

### Task 1: Dependencias, cola de tareas y contenedor worker

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (regenerado), `finanzas/settings.py`, `docker-compose.yml`, `docker-compose.override.yml`, `.env.example`, `README.md`
- Test: `tests/importacion/test_imp_configuracion.py`

**Interfaces:**
- Produces: `settings.Q_CLUSTER` (cola ORM, 1 worker), `settings.IMPORTACION_EXTRACTOR = "apps.importacion.extractor.ExtractorClaude"` (ruta del extractor; se puede cambiar por variable de entorno), `settings.DATA_UPLOAD_MAX_NUMBER_FILES = 20`; servicio `worker` en Docker Compose.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_configuracion.py`:
```python
from django.conf import settings


def test_dependencias_de_importacion_instaladas():
    import anthropic
    import django_q
    import pypdf
    import pydantic

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
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_configuracion.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'anthropic'` y `assert 'django_q' in ...`.

- [ ] **Step 3: Dependencias**

En `pyproject.toml`, `dependencies` queda:
```toml
dependencies = [
    "django>=5.2,<5.3",
    "psycopg[binary]>=3.2",
    "django-environ>=0.12",
    "gunicorn>=23",
    "whitenoise>=6.8",
    "django-q2>=1.11",
    "pypdf[crypto]>=6",
    "anthropic>=1.13,<2",
    "pydantic>=2.10",
]
```
Regenerar el lock y la imagen:
```powershell
docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock
docker compose build
```
Expected: `uv.lock` actualizado con `django-q2`, `pypdf`, `cryptography`, `anthropic`, `pydantic`; la imagen se construye sin errores.

- [ ] **Step 4: Configuración**

En `finanzas/settings.py`, agregar `"django_q",` después de `"django.contrib.staticfiles",` en `INSTALLED_APPS`, y al final del archivo:
```python
# Cola de tareas (Django-Q2) usando la base de datos; el worker corre `manage.py qcluster`.
Q_CLUSTER = {
    "name": "finanzas",
    "orm": "default",
    "workers": 1,
    "timeout": 900,
    "retry": 1200,
    "max_attempts": 1,
    "catch_up": False,
}

# Importación de documentos (plan 4).
IMPORTACION_EXTRACTOR = env(
    "IMPORTACION_EXTRACTOR", default="apps.importacion.extractor.ExtractorClaude"
)
DATA_UPLOAD_MAX_NUMBER_FILES = 20
```

En `docker-compose.yml`, después del servicio `web` (antes de `volumes:` de nivel superior):
```yaml
  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: python manage.py qcluster
    env_file:
      - path: .env
        required: false
    environment:
      DJANGO_MIGRAR: "0"
    depends_on:
      db:
        condition: service_healthy
      web:
        condition: service_started
    restart: unless-stopped
    volumes:
      - media:/app/media
```

En `docker-compose.override.yml`, agregar:
```yaml
  worker:
    environment:
      DJANGO_DEBUG: "1"
    volumes:
      - .:/app
```

En `.env.example`, al final:
```
# Clave de la API de Claude para importar documentos (https://platform.claude.com).
ANTHROPIC_API_KEY=
```

En `README.md`, en la tabla de "Desarrollo", después de la fila "Recompilar estilos":
```
| Reiniciar el worker (cambié código de importación) | `docker compose restart worker` |
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_configuracion.py` 3 passed; todo verde (las migraciones de `django_q` se aplican en la base de pruebas).

Run: `docker compose up -d` y luego `docker compose ps`
Expected: `db`, `web` y `worker` en estado `running`; `docker compose logs worker --tail 20` muestra que el cluster de Django-Q2 arrancó (`Q Cluster ... running`).

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add pyproject.toml uv.lock finanzas/settings.py docker-compose.yml docker-compose.override.yml .env.example README.md tests/importacion/test_imp_configuracion.py
git commit -m "feat(importacion): dependencias, cola Django-Q2 en la base de datos y contenedor worker" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Modelos de importación

**Files:**
- Create: `apps/importacion/__init__.py` (vacío), `apps/importacion/apps.py`, `apps/importacion/models.py`, `apps/importacion/admin.py`, `apps/importacion/migrations/__init__.py` (vacío), `apps/importacion/migrations/0001_initial.py` (generado)
- Modify: `apps/movimientos/models.py` (campo `documento`), `apps/movimientos/migrations/0002_movimiento_documento.py` (generado), `finanzas/settings.py`, `tests/conftest.py`
- Test: `tests/importacion/test_imp_modelos.py`

**Interfaces:**
- Consumes: `ModeloDeHogar`; `Categoria`, `Concepto`, `Cuenta`, `Persona`, `Domicilio`, `DINERO`; `Movimiento`, `TipoIngreso`, `MetodoPago`.
- Produces:
  - `Documento(hogar, archivo, nombre_original, sha256, tipo, emisor, cuenta, periodo_inicio, periodo_fin, saldo_al_corte, paginas, estado, error, aviso, modelo_ia, tokens_entrada, tokens_salida, costo_estimado_usd, subido_por)` con `Documento.Tipo` (`estado_cuenta, nomina, recibo_servicio, otro`), `Documento.Estado` (`subido, procesando, por_revisar, confirmado, descartado, error`), `Documento.ESTADOS_EN_CURSO = (subido, procesando)`; único por `(hogar, sha256)`; el archivo se guarda en `documentos/<hogar_id>/<sha256>.pdf`.
  - `ReglaClasificacion(hogar, patron, emisor, categoria, concepto, persona, domicilio, es_hormiga, prioridad, veces_aplicada)`.
  - `MovimientoPropuesto(hogar, documento, fecha, descripcion_original, descripcion, monto, tipo, tipo_ingreso, es_extraordinario, metodo_pago, categoria, concepto, persona, domicilio, cuenta, cuenta_destino, es_hormiga, confianza, regla, posible_duplicado_de, estado, movimiento, error)` con `MovimientoPropuesto.Estado` (`pendiente, aceptado, descartado`); related name `documento.propuestas`.
  - `Movimiento.documento` (FK opcional, `SET_NULL`, related name `movimientos`).
  - Fixtures en `tests/conftest.py`: `media_temporal` (autouse: `MEDIA_ROOT` en una carpeta temporal) y `crear_pdf` (fábrica `crear_pdf(*paginas: str) -> bytes`, un PDF válido con el texto dado por página).

- [ ] **Step 1: Fixtures de prueba**

En `tests/conftest.py`, agregar al final:
```python
@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    """Los archivos subidos en las pruebas van a una carpeta temporal."""
    settings.MEDIA_ROOT = tmp_path / "media"


def _pdf_minimo(paginas):
    """PDF válido con una página por texto (Helvetica, WinAnsi). Solo para pruebas."""

    def escapar(linea):
        return linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objetos = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    hijos = []
    numero = 4
    for texto in paginas:
        lineas = " ".join(f"({escapar(linea)}) Tj T*" for linea in texto.split("\n"))
        flujo = f"BT /F1 10 Tf 12 TL 40 800 Td {lineas} ET".encode("latin-1")
        objetos[numero] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + f"{numero + 1} 0 R >>".encode()
        )
        objetos[numero + 1] = (
            f"<< /Length {len(flujo)} >>\nstream\n".encode() + flujo + b"\nendstream"
        )
        hijos.append(f"{numero} 0 R")
        numero += 2
    objetos[2] = f"<< /Type /Pages /Kids [{' '.join(hijos)}] /Count {len(hijos)} >>".encode()
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = {}
    for clave in sorted(objetos):
        posiciones[clave] = len(salida)
        salida += f"{clave} 0 obj\n".encode() + objetos[clave] + b"\nendobj\n"
    inicio_xref = len(salida)
    total = max(objetos) + 1
    salida += f"xref\n0 {total}\n0000000000 65535 f \n".encode()
    for clave in range(1, total):
        salida += f"{posiciones[clave]:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return bytes(salida)


@pytest.fixture
def crear_pdf():
    """Fábrica de PDFs ficticios: crear_pdf("texto página 1", "texto página 2")."""
    return lambda *paginas: _pdf_minimo(paginas or ("",))
```

- [ ] **Step 2: Escribir las pruebas que fallan**

`tests/importacion/test_imp_modelos.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError

from apps.catalogos.models import Categoria
from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
HUELLA = "a" * 64


def documento(hogar, huella=HUELLA, contenido=b"%PDF-1.4 prueba"):
    doc = Documento(hogar=hogar, nombre_original="estado.pdf", sha256=huella)
    doc.archivo.save("x.pdf", ContentFile(contenido), save=False)
    doc.save()
    return doc


def test_el_archivo_se_guarda_por_hogar_y_huella(hogar):
    doc = documento(hogar)

    assert doc.archivo.name == f"documentos/{hogar.pk}/{HUELLA}.pdf"
    assert doc.estado == Documento.Estado.SUBIDO
    with doc.archivo.open("rb") as archivo:
        assert archivo.read() == b"%PDF-1.4 prueba"


def test_la_huella_es_unica_por_hogar(hogar, otro_hogar):
    documento(hogar)
    documento(otro_hogar)

    with pytest.raises(IntegrityError):
        documento(hogar)


def test_propuesta_con_categoria_de_otro_hogar_es_invalida(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Ajena")
    propuesta = MovimientoPropuesto(
        hogar=hogar,
        documento=documento(hogar),
        fecha=date(2026, 10, 5),
        descripcion_original="OXXO",
        descripcion="OXXO",
        monto=D("85.50"),
        tipo=Movimiento.Tipo.GASTO,
        categoria=ajena,
    )

    with pytest.raises(ValidationError) as error:
        propuesta.full_clean()

    assert "categoria" in error.value.message_dict


def test_movimiento_con_documento_de_otro_hogar_es_invalido(catalogo, otro_hogar):
    movimiento = Movimiento(
        hogar=catalogo.gasolina.hogar,
        tipo=Movimiento.Tipo.GASTO,
        monto=D("10"),
        concepto=catalogo.gasolina,
        documento=documento(otro_hogar),
    )

    with pytest.raises(ValidationError) as error:
        movimiento.full_clean()

    assert "documento" in error.value.message_dict


def test_borrar_el_documento_conserva_los_movimientos(catalogo, hogar):
    doc = documento(hogar)
    movimiento = guardar_movimiento(
        Movimiento(
            hogar=hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("10"),
            concepto=catalogo.gasolina,
            origen=Movimiento.Origen.IMPORTADO,
            documento=doc,
        )
    )

    doc.delete()

    movimiento.refresh_from_db()
    assert movimiento.documento is None


def test_borrar_el_hogar_borra_su_importacion(catalogo, hogar):
    doc = documento(hogar)
    ReglaClasificacion.objects.create(hogar=hogar, patron="oxxo")
    MovimientoPropuesto.objects.create(
        hogar=hogar,
        documento=doc,
        fecha=date(2026, 10, 5),
        descripcion_original="OXXO",
        descripcion="OXXO",
        monto=D("1"),
        tipo=Movimiento.Tipo.GASTO,
    )

    hogar.delete()

    assert not Documento.objects.exists()
    assert not MovimientoPropuesto.objects.exists()
    assert not ReglaClasificacion.objects.exists()


def test_fabrica_de_pdfs_de_prueba(crear_pdf):
    datos = crear_pdf("Hola mundo", "Segunda página")

    assert datos.startswith(b"%PDF-1.4")
    assert datos.rstrip().endswith(b"%%EOF")
```

- [ ] **Step 3: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_modelos.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.importacion'`.

- [ ] **Step 4: Implementar**

`apps/importacion/apps.py`:
```python
from django.apps import AppConfig


class ImportacionConfig(AppConfig):
    name = "apps.importacion"
    verbose_name = "Importación"
```

`apps/importacion/models.py`:
```python
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalogos.models import DINERO, Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.core.models import ModeloDeHogar
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso


def ruta_documento(documento, _nombre):
    """Los PDFs se guardan por hogar y por huella; nunca con el nombre original."""
    return f"documentos/{documento.hogar_id}/{documento.sha256}.pdf"


class Documento(ModeloDeHogar):
    class Tipo(models.TextChoices):
        ESTADO_CUENTA = "estado_cuenta", "Estado de cuenta"
        NOMINA = "nomina", "Recibo de nómina"
        RECIBO_SERVICIO = "recibo_servicio", "Recibo de servicio"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        SUBIDO = "subido", "Subido"
        PROCESANDO = "procesando", "Procesando"
        POR_REVISAR = "por_revisar", "Por revisar"
        CONFIRMADO = "confirmado", "Confirmado"
        DESCARTADO = "descartado", "Descartado"
        ERROR = "error", "Error"

    ESTADOS_EN_CURSO = (Estado.SUBIDO, Estado.PROCESANDO)

    archivo = models.FileField(upload_to=ruta_documento, max_length=255)
    nombre_original = models.CharField("nombre original", max_length=255)
    sha256 = models.CharField(max_length=64)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, blank=True)
    emisor = models.CharField(max_length=80, blank=True)
    cuenta = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.SET_NULL, related_name="documentos"
    )
    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fin = models.DateField(null=True, blank=True)
    saldo_al_corte = models.DecimalField("saldo al corte", null=True, blank=True, **DINERO)
    paginas = models.PositiveSmallIntegerField("páginas", null=True, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.SUBIDO)
    error = models.TextField(blank=True)
    aviso = models.CharField(max_length=255, blank=True)
    modelo_ia = models.CharField("modelo de IA", max_length=40, blank=True)
    tokens_entrada = models.PositiveIntegerField(null=True, blank=True)
    tokens_salida = models.PositiveIntegerField(null=True, blank=True)
    costo_estimado_usd = models.DecimalField(
        "costo estimado (USD)", max_digits=8, decimal_places=4, null=True, blank=True
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["-creado_en"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "sha256"], name="documento_unico_por_hogar")
        ]

    def __str__(self):
        return self.nombre_original


class ReglaClasificacion(ModeloDeHogar):
    patron = models.CharField(
        "patrón",
        max_length=120,
        help_text="Palabras que contiene la descripción (sin mayúsculas ni acentos), ej. «oxxo».",
    )
    emisor = models.CharField(
        max_length=80, blank=True, help_text="Opcional: aplica solo a documentos de este emisor."
    )
    categoria = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    concepto = models.ForeignKey(
        Concepto, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    domicilio = models.ForeignKey(
        Domicilio, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    es_hormiga = models.BooleanField("hormiga 🐜", null=True, blank=True)
    prioridad = models.PositiveSmallIntegerField(default=100)
    veces_aplicada = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "regla de clasificación"
        verbose_name_plural = "reglas de clasificación"
        ordering = ["prioridad", "patron"]

    def __str__(self):
        return self.patron


class MovimientoPropuesto(ModeloDeHogar):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADO = "aceptado", "Aceptado"
        DESCARTADO = "descartado", "Descartado"

    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="propuestas")
    fecha = models.DateField()
    descripcion_original = models.CharField("descripción original", max_length=255)
    descripcion = models.CharField("descripción", max_length=255)
    monto = models.DecimalField(validators=[MinValueValidator(Decimal("0.01"))], **DINERO)
    tipo = models.CharField(max_length=15, choices=Movimiento.Tipo.choices)
    tipo_ingreso = models.CharField(
        "tipo de ingreso", max_length=20, choices=TipoIngreso.choices, blank=True
    )
    es_extraordinario = models.BooleanField("extraordinario", default=False)
    metodo_pago = models.CharField(
        "método de pago", max_length=15, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO
    )
    categoria = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="categoría",
    )  # fmt: skip
    concepto = models.ForeignKey(
        Concepto, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    domicilio = models.ForeignKey(
        Domicilio, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cuenta = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cuenta_destino = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="cuenta destino",
    )  # fmt: skip
    es_hormiga = models.BooleanField("hormiga 🐜", default=False)
    confianza = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    regla = models.ForeignKey(
        ReglaClasificacion, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="propuestas",
    )  # fmt: skip
    posible_duplicado_de = models.ForeignKey(
        Movimiento, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    movimiento = models.OneToOneField(
        Movimiento, null=True, blank=True, on_delete=models.SET_NULL, related_name="propuesta"
    )
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "movimiento propuesto"
        verbose_name_plural = "movimientos propuestos"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} {self.descripcion} {self.monto}"
```

`apps/importacion/admin.py`:
```python
from django.contrib import admin

from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("nombre_original", "tipo", "emisor", "estado", "costo_estimado_usd", "hogar")
    list_filter = ("hogar", "estado", "tipo")
    readonly_fields = ("sha256", "modelo_ia", "tokens_entrada", "tokens_salida")


@admin.register(MovimientoPropuesto)
class MovimientoPropuestoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "descripcion", "monto", "tipo", "estado", "documento")
    list_filter = ("hogar", "estado", "tipo")


@admin.register(ReglaClasificacion)
class ReglaClasificacionAdmin(admin.ModelAdmin):
    list_display = ("patron", "emisor", "categoria", "concepto", "prioridad", "veces_aplicada")
    list_filter = ("hogar",)
    search_fields = ("patron", "emisor")
```

En `apps/movimientos/models.py`, dentro de `Movimiento`, después del campo `origen`:
```python
    documento = models.ForeignKey(
        "importacion.Documento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movimientos",
    )
```

En `finanzas/settings.py`, agregar `"apps.importacion",` después de `"apps.planeacion",` en `INSTALLED_APPS`.

- [ ] **Step 5: Generar las migraciones**

Run: `docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations importacion movimientos`
Expected: `apps/importacion/migrations/0001_initial.py` (`Create model Documento`, `ReglaClasificacion`, `MovimientoPropuesto` y la restricción `documento_unico_por_hogar`) y `apps/movimientos/migrations/0002_movimiento_documento.py` (`Add field documento to movimiento`), que depende de `importacion.0001_initial`.

- [ ] **Step 6: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_modelos.py` 7 passed; todo verde.

- [ ] **Step 7: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion apps/movimientos finanzas/settings.py tests/conftest.py tests/importacion/test_imp_modelos.py
git commit -m "feat(importacion): documentos, movimientos propuestos y reglas de clasificacion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Archivos subidos: huella, PDF y ZIP (IMP-01, IMP-02)

**Files:**
- Create: `apps/importacion/errores.py`, `apps/importacion/archivos.py`
- Test: `tests/importacion/test_imp_archivos.py`

**Interfaces:**
- Produces:
  - `apps.importacion.errores`: `ErrorImportacion(Exception)` (mensaje para el usuario) y subclases `ArchivoInvalidoError`, `PdfInvalidoError`, `PdfProtegidoError`, `SinTextoError`, `ErrorExtraccion`.
  - `apps.importacion.archivos`: `TAMANO_MAXIMO = 20 MB`, `MAX_PDFS_POR_ZIP = 20`, `huella(datos) -> str` (SHA-256 hex), `es_pdf(datos) -> bool`, `es_zip(datos) -> bool`, `megas() -> int`, `pdfs_del_archivo(nombre, datos) -> list[(nombre, bytes)]` (un PDF suelto o los PDFs de un ZIP; lanza `ArchivoInvalidoError` con el motivo).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_archivos.py`:
```python
import hashlib
import io
import zipfile

import pytest

from apps.importacion import archivos
from apps.importacion.archivos import es_pdf, huella, pdfs_del_archivo
from apps.importacion.errores import ArchivoInvalidoError


def hacer_zip(miembros):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as comprimido:
        for nombre, datos in miembros.items():
            comprimido.writestr(nombre, datos)
    return buffer.getvalue()


def test_huella_sha256():
    assert huella(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_reconoce_un_pdf(crear_pdf):
    assert es_pdf(crear_pdf("Hola"))
    assert es_pdf(b"\n\n%PDF-1.7 resto")
    assert not es_pdf(b"hola")


def test_un_pdf_se_devuelve_tal_cual(crear_pdf):
    datos = crear_pdf("Hola")

    assert pdfs_del_archivo("estado.pdf", datos) == [("estado.pdf", datos)]


def test_zip_con_pdfs_y_otros_archivos(crear_pdf):
    estado, factura = crear_pdf("Estado"), crear_pdf("Factura")
    comprimido = hacer_zip(
        {
            "carpeta/estado.pdf": estado,
            "factura.PDF": factura,
            "leeme.txt": b"hola",
            "__MACOSX/._estado.pdf": b"basura",
            "falso.pdf": b"no soy un pdf",
        }
    )

    assert pdfs_del_archivo("internet.zip", comprimido) == [
        ("estado.pdf", estado),
        ("factura.PDF", factura),
    ]


def test_archivo_que_no_es_pdf_ni_zip():
    with pytest.raises(ArchivoInvalidoError, match="no es un PDF ni un ZIP"):
        pdfs_del_archivo("foto.jpg", b"\xff\xd8\xff imagen")


def test_zip_sin_pdfs():
    with pytest.raises(ArchivoInvalidoError, match="no contiene PDFs"):
        pdfs_del_archivo("vacio.zip", hacer_zip({"leeme.txt": b"hola"}))


def test_zip_danado(crear_pdf):
    comprimido = hacer_zip({"estado.pdf": crear_pdf("Estado")})

    with pytest.raises(ArchivoInvalidoError, match="dañado"):
        pdfs_del_archivo("roto.zip", comprimido[:-30])


def test_zip_con_demasiados_pdfs(monkeypatch, crear_pdf):
    monkeypatch.setattr(archivos, "MAX_PDFS_POR_ZIP", 2)
    comprimido = hacer_zip({f"{n}.pdf": crear_pdf(str(n)) for n in range(3)})

    with pytest.raises(ArchivoInvalidoError, match="más de 2 PDFs"):
        pdfs_del_archivo("muchos.zip", comprimido)


def test_pdf_demasiado_grande_dentro_del_zip(monkeypatch, crear_pdf):
    monkeypatch.setattr(archivos, "TAMANO_MAXIMO", 100)
    comprimido = hacer_zip({"grande.pdf": crear_pdf("Texto largo " * 50)})

    with pytest.raises(ArchivoInvalidoError, match="grande.pdf pesa más de"):
        pdfs_del_archivo("grande.zip", comprimido)
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_archivos.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.importacion.archivos'`.

- [ ] **Step 3: Implementar**

`apps/importacion/errores.py`:
```python
"""Errores de importación. Su mensaje se muestra tal cual al usuario."""


class ErrorImportacion(Exception):
    pass


class ArchivoInvalidoError(ErrorImportacion):
    pass


class PdfInvalidoError(ErrorImportacion):
    pass


class PdfProtegidoError(ErrorImportacion):
    pass


class SinTextoError(ErrorImportacion):
    pass


class ErrorExtraccion(ErrorImportacion):
    pass
```

`apps/importacion/archivos.py`:
```python
"""Archivos subidos (IMP-01): huella, detección de PDF y PDFs dentro de un ZIP."""

import hashlib
import io
import zipfile
from pathlib import PurePosixPath

from apps.importacion.errores import ArchivoInvalidoError

TAMANO_MAXIMO = 20 * 1024 * 1024
MAX_PDFS_POR_ZIP = 20


def huella(datos):
    return hashlib.sha256(datos).hexdigest()


def es_pdf(datos):
    return b"%PDF-" in datos[:1024]


def es_zip(datos):
    return datos[:4] == b"PK\x03\x04"


def megas():
    return TAMANO_MAXIMO // (1024 * 1024)


def pdfs_del_archivo(nombre, datos):
    """Lista de (nombre, contenido) de los PDFs de un archivo subido: PDF suelto o ZIP."""
    if es_pdf(datos):
        return [(nombre, datos)]
    if es_zip(datos):
        return _pdfs_del_zip(datos)
    raise ArchivoInvalidoError("no es un PDF ni un ZIP")


def _pdfs_del_zip(datos):
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as comprimido:
            miembros = [
                miembro
                for miembro in comprimido.infolist()
                if not miembro.is_dir()
                and miembro.filename.lower().endswith(".pdf")
                and not miembro.filename.startswith("__MACOSX/")
            ]
            if len(miembros) > MAX_PDFS_POR_ZIP:
                raise ArchivoInvalidoError(f"el ZIP tiene más de {MAX_PDFS_POR_ZIP} PDFs")
            pdfs = []
            for miembro in miembros:
                nombre = PurePosixPath(miembro.filename).name
                with comprimido.open(miembro) as archivo:
                    contenido = archivo.read(TAMANO_MAXIMO + 1)
                if len(contenido) > TAMANO_MAXIMO:
                    raise ArchivoInvalidoError(f"{nombre} pesa más de {megas()} MB")
                if es_pdf(contenido):
                    pdfs.append((nombre, contenido))
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as error:
        raise ArchivoInvalidoError("el ZIP está dañado o protegido con contraseña") from error
    if not pdfs:
        raise ArchivoInvalidoError("el ZIP no contiene PDFs")
    return pdfs
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_archivos.py` 9 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion tests/importacion/test_imp_archivos.py
git commit -m "feat(importacion): huella SHA-256 y lectura de PDFs sueltos o dentro de ZIP" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Texto del PDF y protección de datos personales (IMP-04, RNF-03)

**Files:**
- Create: `apps/importacion/texto.py`
- Test: `tests/importacion/test_imp_texto.py`

**Interfaces:**
- Consumes: errores (Task 3); fixture `crear_pdf` (Task 2).
- Produces: `apps.importacion.texto.extraer_texto(datos: bytes) -> (texto: str, paginas: int)` (texto con encabezado `--- Página N ---` por página; lanza `PdfProtegidoError`, `PdfInvalidoError` o `SinTextoError`), `proteger_datos(texto: str) -> str` (oculta RFC, CURP, tarjetas con separadores y números de 10+ dígitos dejando los últimos 4).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_texto.py`:
```python
import io

import pytest
from pypdf import PdfWriter

from apps.importacion.errores import PdfInvalidoError, PdfProtegidoError, SinTextoError
from apps.importacion.texto import extraer_texto, proteger_datos


def cifrar(datos, clave_usuario):
    escritor = PdfWriter(clone_from=io.BytesIO(datos))
    escritor.encrypt(user_password=clave_usuario, owner_password="duenio", algorithm="AES-256")
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def test_extrae_el_texto_por_pagina(crear_pdf):
    texto, paginas = extraer_texto(
        crear_pdf("BANCO DEMO\nCompra OXXO 85.50", "Pago recibido 2000.00")
    )

    assert paginas == 2
    assert "Compra OXXO 85.50" in texto
    assert "--- Página 2 ---" in texto
    assert "Pago recibido 2000.00" in texto


def test_pdf_sin_texto_requiere_ocr(crear_pdf):
    with pytest.raises(SinTextoError, match="OCR"):
        extraer_texto(crear_pdf("", ""))


def test_pdf_danado():
    with pytest.raises(PdfInvalidoError):
        extraer_texto(b"%PDF-1.4 esto no es un pdf completo")


def test_pdf_protegido_con_contrasena(crear_pdf):
    with pytest.raises(PdfProtegidoError, match="contraseña"):
        extraer_texto(cifrar(crear_pdf("Estado de cuenta secreto"), "clave"))


def test_pdf_cifrado_sin_contrasena_de_apertura_se_lee(crear_pdf):
    texto, _ = extraer_texto(cifrar(crear_pdf("Estado de cuenta Banco Demo"), ""))

    assert "Estado de cuenta Banco Demo" in texto


def test_proteger_datos_personales():
    texto = (
        "RFC XAXX010101000 CURP XEXX010101HNEXXXA4 tarjeta 4152 3131 2345 6789 "
        "CLABE 012180001234567891 servicio 123456789012 monto 1,234.56 fecha 2026-10-05"
    )

    protegido = proteger_datos(texto)

    for dato in ("XAXX010101000", "XEXX010101HNEXXXA4", "4152", "012180001234567891",
                 "123456789012"):  # fmt: skip
        assert dato not in protegido
    for marca in ("[RFC]", "[CURP]", "****6789", "****7891", "****9012", "1,234.56",
                  "2026-10-05"):  # fmt: skip
        assert marca in protegido
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_texto.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.importacion.texto'`.

- [ ] **Step 3: Implementar**

`apps/importacion/texto.py`:
```python
"""Texto de un PDF (IMP-04) y protección de datos antes de enviarlo a la IA (RNF-03)."""

import io
import re

from pypdf import PdfReader

from apps.importacion.errores import (
    ErrorImportacion,
    PdfInvalidoError,
    PdfProtegidoError,
    SinTextoError,
)

MINIMO_CARACTERES = 20

_CURP = re.compile(r"\b[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b")
_RFC = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")
_TARJETA = re.compile(r"\b(?:\d{4}[ -]){3}(\d{4})\b")
_NUMERO_LARGO = re.compile(r"\b\d{6,}(\d{4})\b")


def extraer_texto(datos):
    """Devuelve (texto con un encabezado por página, número de páginas)."""
    try:
        lector = PdfReader(io.BytesIO(datos))
        if lector.is_encrypted and not lector.decrypt(""):
            raise PdfProtegidoError(
                "El PDF está protegido con contraseña; quítasela y vuelve a subirlo."
            )
        if not lector.pages:
            raise PdfInvalidoError("El PDF está dañado o no tiene páginas.")
        paginas = [(pagina.extract_text() or "").strip() for pagina in lector.pages]
    except ErrorImportacion:
        raise
    except Exception as error:  # pypdf lanza distintos errores ante PDFs dañados
        raise PdfInvalidoError("El PDF está dañado o no se puede leer.") from error
    if sum(len(texto) for texto in paginas) < MINIMO_CARACTERES:
        raise SinTextoError(
            "El PDF no tiene texto (parece escaneado) y requiere OCR, que aún no está disponible."
        )
    texto = "\n\n".join(f"--- Página {n} ---\n{t}" for n, t in enumerate(paginas, start=1))
    return texto, len(paginas)


def proteger_datos(texto):
    """Oculta RFC, CURP y números largos (tarjeta, CLABE, NSS, servicio) dejando 4 dígitos."""
    texto = _CURP.sub("[CURP]", texto)
    texto = _RFC.sub("[RFC]", texto)
    texto = _TARJETA.sub(lambda m: f"****{m.group(1)}", texto)
    return _NUMERO_LARGO.sub(lambda m: f"****{m.group(1)}", texto)
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_texto.py` 6 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion/texto.py tests/importacion/test_imp_texto.py
git commit -m "feat(importacion): texto del PDF con pypdf y ocultamiento de datos personales" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Reglas de clasificación (RN-12) y posibles duplicados (RN-11)

**Files:**
- Create: `apps/importacion/clasificacion.py`
- Test: `tests/importacion/test_imp_clasificacion.py`

**Interfaces:**
- Consumes: `ReglaClasificacion`, `MovimientoPropuesto` (Task 2); `Movimiento`, `guardar_movimiento`; fixture `catalogo`.
- Produces: `normalizar(texto) -> str` (sin acentos, minúsculas, espacios simples), `palabras(texto) -> str` (solo letras), `patron_sugerido(descripcion) -> str` (dos primeras palabras de 3+ letras), `buscar_regla(hogar, emisor, descripcion) -> ReglaClasificacion | None` (palabras completas, por prioridad), `aplicar_regla(propuesta, regla) -> None` (copia los valores no vacíos, confianza 1, suma `veces_aplicada`), `buscar_duplicado(hogar, fecha, monto, cuenta=None) -> Movimiento | None`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_clasificacion.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria
from apps.importacion.clasificacion import (
    aplicar_regla,
    buscar_duplicado,
    buscar_regla,
    normalizar,
    palabras,
    patron_sugerido,
)
from apps.importacion.models import MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
OCTUBRE_5 = date(2026, 10, 5)


def regla(hogar, patron, **campos):
    return ReglaClasificacion.objects.create(hogar=hogar, patron=patron, **campos)


def gasto(catalogo, monto="450", fecha=OCTUBRE_5, **campos):
    return guardar_movimiento(
        Movimiento(
            hogar=catalogo.gasolina.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D(monto),
            concepto=catalogo.gasolina,
            fecha=fecha,
            **campos,
        )
    )


def test_normalizar_y_palabras():
    assert normalizar("  Café  OXXO\tSuc. ") == "cafe oxxo suc."
    assert palabras("OXXO SUC 1234 MTY.") == "oxxo suc mty"


def test_patron_sugerido():
    assert patron_sugerido("OXXO SUC 1234 MONTERREY") == "oxxo suc"
    assert patron_sugerido("CFE SUMINISTRADOR DE SERVICIOS") == "cfe suministrador"
    assert patron_sugerido("PAGO A TARJETA") == "pago tarjeta"
    assert patron_sugerido("12 34") == ""


def test_regla_por_palabras_completas(catalogo):
    oxxo = regla(catalogo.gasolina.hogar, "oxxo", categoria=catalogo.categorias["Comida"])
    hogar = catalogo.gasolina.hogar

    assert buscar_regla(hogar, "Banco Demo", "OXXO 1234 SUC") == oxxo
    assert buscar_regla(hogar, "Banco Demo", "OXXOGAS") is None
    assert buscar_regla(hogar, "Banco Demo", "WALMART") is None


def test_regla_limitada_al_emisor(catalogo):
    hogar = catalogo.gasolina.hogar
    pago = regla(hogar, "pago", emisor="Banco Demo")

    assert buscar_regla(hogar, "BANCO DEMO S.A.", "PAGO RECIBIDO") == pago
    assert buscar_regla(hogar, "Otro Banco", "PAGO RECIBIDO") is None


def test_gana_la_regla_de_mayor_prioridad(catalogo):
    hogar = catalogo.gasolina.hogar
    regla(hogar, "oxxo", prioridad=50)
    especifica = regla(hogar, "oxxo suc", prioridad=10)

    assert buscar_regla(hogar, "", "OXXO SUC 1234") == especifica


def test_reglas_de_otro_hogar_no_aplican(catalogo, otro_hogar):
    regla(otro_hogar, "oxxo")

    assert buscar_regla(catalogo.gasolina.hogar, "", "OXXO") is None


def test_aplicar_regla(catalogo):
    hogar = catalogo.gasolina.hogar
    con_concepto = regla(
        hogar, "pemex", concepto=catalogo.gasolina, persona=catalogo.monze, es_hormiga=True
    )
    propuesta = MovimientoPropuesto(hogar=hogar, categoria=catalogo.categorias["Comida"])

    aplicar_regla(propuesta, con_concepto)

    assert propuesta.concepto == catalogo.gasolina
    assert propuesta.categoria == catalogo.categorias["Transporte"]
    assert (propuesta.persona, propuesta.es_hormiga) == (catalogo.monze, True)
    assert (propuesta.regla, propuesta.confianza) == (con_concepto, D("1"))
    con_concepto.refresh_from_db()
    assert con_concepto.veces_aplicada == 1


def test_aplicar_regla_no_borra_lo_que_no_define(catalogo):
    hogar = catalogo.gasolina.hogar
    solo_persona = regla(hogar, "farmacia", persona=catalogo.monze)
    comida = catalogo.categorias["Comida"]
    propuesta = MovimientoPropuesto(hogar=hogar, categoria=comida)

    aplicar_regla(propuesta, solo_persona)

    assert (propuesta.categoria, propuesta.persona) == (comida, catalogo.monze)


def test_regla_con_otra_categoria_quita_el_concepto(catalogo):
    hogar = catalogo.gasolina.hogar
    salud = Categoria.objects.get(hogar=hogar, nombre="Salud")
    propuesta = MovimientoPropuesto(
        hogar=hogar, concepto=catalogo.gasolina, categoria=catalogo.categorias["Transporte"]
    )

    aplicar_regla(propuesta, regla(hogar, "farmacia", categoria=salud))

    assert (propuesta.categoria, propuesta.concepto) == (salud, None)


def test_duplicado_por_monto_fecha_y_cuenta(catalogo):
    hogar = catalogo.gasolina.hogar
    existente = gasto(catalogo, cuenta=catalogo.nomina, metodo_pago=MetodoPago.TARJETA_DEBITO)

    assert buscar_duplicado(hogar, date(2026, 10, 7), D("450"), catalogo.nomina) == existente
    assert buscar_duplicado(hogar, date(2026, 10, 3), D("450"), None) == existente
    assert buscar_duplicado(hogar, date(2026, 10, 8), D("450"), catalogo.nomina) is None
    assert buscar_duplicado(hogar, OCTUBRE_5, D("451"), catalogo.nomina) is None
    assert buscar_duplicado(hogar, OCTUBRE_5, D("450"), catalogo.efectivo) is None


def test_duplicado_contra_movimiento_sin_cuenta(catalogo):
    existente = gasto(catalogo)

    hogar = catalogo.gasolina.hogar
    assert buscar_duplicado(hogar, OCTUBRE_5, D("450"), catalogo.nomina) == existente


def test_duplicado_por_cuenta_destino(catalogo):
    pago = guardar_movimiento(
        Movimiento(
            hogar=catalogo.tarjeta.hogar,
            tipo=Movimiento.Tipo.PAGO_DEUDA,
            monto=D("1000"),
            cuenta=catalogo.nomina,
            cuenta_destino=catalogo.tarjeta,
            fecha=OCTUBRE_5,
        )
    )

    assert buscar_duplicado(catalogo.tarjeta.hogar, OCTUBRE_5, D("1000"), catalogo.tarjeta) == pago


def test_movimientos_de_otro_hogar_no_son_duplicados(catalogo, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    guardar_movimiento(
        Movimiento(
            hogar=otro_hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("450"),
            categoria=ajena,
            fecha=OCTUBRE_5,
        )
    )

    assert buscar_duplicado(catalogo.gasolina.hogar, OCTUBRE_5, D("450")) is None
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_clasificacion.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.importacion.clasificacion'`.

- [ ] **Step 3: Implementar**

`apps/importacion/clasificacion.py`:
```python
"""Reglas de clasificación del hogar (RN-12) y posibles duplicados (RN-11)."""

import re
import unicodedata
from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Q

from apps.importacion.models import ReglaClasificacion
from apps.movimientos.models import Movimiento

DIAS_DUPLICADO = 2


def normalizar(texto):
    """Sin acentos, en minúsculas y con espacios simples."""
    sin_acentos = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().split())


def palabras(texto):
    """Solo las palabras (letras) del texto normalizado: «OXXO SUC 1234» → «oxxo suc»."""
    return " ".join(re.findall(r"[a-z]+", normalizar(texto)))


def patron_sugerido(descripcion):
    """Patrón para «recordar clasificación»: las dos primeras palabras de 3 o más letras."""
    utiles = [palabra for palabra in palabras(descripcion).split() if len(palabra) >= 3]
    return " ".join(utiles[:2])


def buscar_regla(hogar, emisor, descripcion):
    """RN-12: la primera regla (por prioridad) cuyas palabras aparecen completas."""
    texto = f" {palabras(descripcion)} "
    emisor_normal = normalizar(emisor)
    for regla in ReglaClasificacion.objects.del_hogar(hogar).order_by("prioridad", "-id"):
        if regla.emisor and normalizar(regla.emisor) not in emisor_normal:
            continue
        patron = palabras(regla.patron)
        if patron and f" {patron} " in texto:
            return regla
    return None


def aplicar_regla(propuesta, regla):
    """Copia a la propuesta los valores que la regla define; la regla manda sobre la IA."""
    if regla.concepto_id:
        propuesta.concepto = regla.concepto
        propuesta.categoria = regla.concepto.categoria
    elif regla.categoria_id:
        propuesta.categoria = regla.categoria
        if propuesta.concepto and propuesta.concepto.categoria_id != regla.categoria_id:
            propuesta.concepto = None
    if regla.persona_id:
        propuesta.persona = regla.persona
    if regla.domicilio_id:
        propuesta.domicilio = regla.domicilio
    if regla.es_hormiga is not None:
        propuesta.es_hormiga = regla.es_hormiga
    propuesta.regla = regla
    propuesta.confianza = Decimal("1")
    ReglaClasificacion.objects.filter(pk=regla.pk).update(veces_aplicada=F("veces_aplicada") + 1)


def buscar_duplicado(hogar, fecha, monto, cuenta=None):
    """RN-11: mismo monto, fecha a ±2 días y la misma cuenta (origen o destino) o sin cuenta."""
    consulta = Movimiento.objects.del_hogar(hogar).filter(
        monto=monto,
        fecha__range=(fecha - timedelta(days=DIAS_DUPLICADO), fecha + timedelta(days=DIAS_DUPLICADO)),
    )
    if cuenta is not None:
        consulta = consulta.filter(
            Q(cuenta=cuenta) | Q(cuenta_destino=cuenta) | Q(cuenta__isnull=True)
        )
    return consulta.order_by("fecha", "id").first()
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_clasificacion.py` 13 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion/clasificacion.py tests/importacion/test_imp_clasificacion.py
git commit -m "feat(importacion): reglas de clasificacion del hogar y deteccion de posibles duplicados" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Extractor con Claude (IMP-05, IMP-10, IMP-11, IMP-13)

**Files:**
- Create: `apps/importacion/extractor.py`
- Test: `tests/importacion/test_imp_extractor.py`

**Interfaces:**
- Consumes: `ErrorExtraccion` (Task 3); `TipoIngreso`; `redondear`; SDK `anthropic` 1.x (`client.beta.messages.create` con `betas`, `fallbacks`, `output_config`).
- Produces:
  - Constantes `MODELO = "claude-opus-5-5"`, `BETA_RESPALDO = "server-side-fallback-2026-07-01"`, `MAX_TOKENS = 16000`, `PRECIOS_POR_MILLON`, `ESQUEMA` (JSON schema estricto), `INSTRUCCIONES`.
  - Modelos Pydantic `DocumentoIA(tipo_documento, emisor, periodo_inicio, periodo_fin, ultimos_digitos_cuenta, saldo_al_corte)` y `MovimientoIA(fecha, descripcion, monto, tipo, tipo_ingreso, es_extraordinario, categoria, concepto, persona, domicilio, confianza)`.
  - Dataclasses `Uso(modelo, tokens_entrada, tokens_salida, costo_usd)` y `ResultadoExtraccion(documento, movimientos, descartados, uso)`.
  - `construir_mensaje(texto, catalogos: dict) -> str`, `interpretar(texto_json, uso) -> ResultadoExtraccion`, `costo_usd(modelo, entrada, salida) -> Decimal`, `uso_de(respuesta) -> Uso`.
  - `ExtractorClaude(cliente=None)` con `extraer(texto, catalogos) -> ResultadoExtraccion`; el cliente real (`anthropic.Anthropic()`) se crea hasta el primer uso y, si no hay `ANTHROPIC_API_KEY` (ni `ANTHROPIC_AUTH_TOKEN`), lanza `ErrorExtraccion` con un mensaje claro.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_extractor.py`:
```python
import json
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from apps.importacion.errores import ErrorExtraccion
from apps.importacion.extractor import (
    ESQUEMA,
    ExtractorClaude,
    construir_mensaje,
)

MOVIMIENTO = {
    "fecha": "2026-09-10",
    "descripcion": "OXXO SUC 1234",
    "monto": 85.5,
    "tipo": "gasto",
    "tipo_ingreso": "",
    "es_extraordinario": False,
    "categoria": "Comida",
    "concepto": "",
    "persona": "",
    "domicilio": "",
    "confianza": 0.9,
}


def movimiento(**campos):
    return {**MOVIMIENTO, **campos}


RESPUESTA = {
    "tipo_documento": "estado_cuenta",
    "emisor": "Banco Demo",
    "periodo_inicio": "2026-09-06",
    "periodo_fin": "2026-10-05",
    "ultimos_digitos_cuenta": "****1234",
    "saldo_al_corte": "6,839.01",
    "movimientos": [
        MOVIMIENTO,
        movimiento(fecha="2026-09-15", descripcion="DEPOSITO NOMINA", monto=15000,
                   tipo="ingreso", tipo_ingreso="salario", categoria="", confianza=0.95),
        movimiento(fecha="2026-09-20", descripcion="PAGO TARJETA", monto=-2000,
                   tipo="pago_deuda", categoria="", confianza=1.5),
        movimiento(descripcion="CARGO EN CERO", monto=0),
        movimiento(descripcion="FECHA MAL", fecha="21/09/2026"),
        movimiento(descripcion="TIPO RARO", tipo="regalo"),
        movimiento(descripcion="ENORME", monto=1e12),
    ],
}  # fmt: skip


class ClienteFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        self.llamadas.append(kwargs)
        return self.respuesta


def respuesta(datos=RESPUESTA, stop_reason="end_turn", modelo="claude-opus-5-5", texto=None):
    contenido = [SimpleNamespace(type="text", text=texto if texto is not None else json.dumps(datos))]
    return SimpleNamespace(
        content=contenido,
        stop_reason=stop_reason,
        model=modelo,
        usage=SimpleNamespace(
            input_tokens=10000,
            output_tokens=2000,
            cache_creation_input_tokens=None,
            cache_read_input_tokens=None,
        ),
    )


def extraer(cliente):
    return ExtractorClaude(cliente).extraer("texto del estado", {"categorias": ["Comida"]})


def objetos(esquema):
    if esquema.get("type") == "object":
        yield esquema
        for propiedad in esquema["properties"].values():
            yield from objetos(propiedad)
    elif esquema.get("type") == "array":
        yield from objetos(esquema["items"])


def test_esquema_estricto():
    for objeto in objetos(ESQUEMA):
        assert objeto["additionalProperties"] is False
        assert set(objeto["required"]) == set(objeto["properties"])


def test_peticion_a_claude():
    cliente = ClienteFalso(respuesta())

    extraer(cliente)

    (llamada,) = cliente.llamadas
    assert llamada["model"] == "claude-opus-5-5"
    assert llamada["betas"] == ["server-side-fallback-2026-07-01"]
    assert llamada["fallbacks"] == "default"
    assert llamada["output_config"]["effort"] == "low"
    assert llamada["output_config"]["format"] == {"type": "json_schema", "schema": ESQUEMA}
    assert "thinking" not in llamada
    (mensaje,) = llamada["messages"]
    assert mensaje["role"] == "user"
    assert isinstance(mensaje["content"], str)
    assert "texto del estado" in mensaje["content"]


def test_interpreta_la_respuesta():
    resultado = extraer(ClienteFalso(respuesta()))

    documento = resultado.documento
    assert (documento.tipo_documento, documento.emisor) == ("estado_cuenta", "Banco Demo")
    assert (documento.periodo_inicio, documento.periodo_fin) == (date(2026, 9, 6), date(2026, 10, 5))
    assert (documento.ultimos_digitos_cuenta, documento.saldo_al_corte) == ("1234", D("6839.01"))
    assert [m.monto for m in resultado.movimientos] == [D("85.50"), D("15000.00"), D("2000.00")]
    assert resultado.movimientos[1].tipo_ingreso == "salario"
    assert resultado.movimientos[2].confianza == D("1.00")
    assert resultado.descartados == 4


def test_uso_y_costo():
    uso = extraer(ClienteFalso(respuesta())).uso

    assert (uso.modelo, uso.tokens_entrada, uso.tokens_salida) == ("claude-opus-5-5", 10000, 2000)
    assert uso.costo_usd == D("0.0800")


def test_costo_si_respondio_el_modelo_de_respaldo():
    uso = extraer(ClienteFalso(respuesta(modelo="claude-opus-4-8"))).uso

    assert uso.costo_usd == D("0.1000")


@pytest.mark.parametrize(
    ("falsa", "mensaje"),
    [
        (respuesta(stop_reason="refusal"), "no aceptó"),
        (respuesta(stop_reason="max_tokens"), "demasiado largo"),
        (respuesta(texto="esto no es json"), "no se pudo leer"),
        (respuesta(texto=""), "no devolvió datos"),
        (respuesta({**RESPUESTA, "tipo_documento": "factura"}), "incompletos"),
    ],
)
def test_respuestas_problematicas(falsa, mensaje):
    with pytest.raises(ErrorExtraccion, match=mensaje):
        extraer(ClienteFalso(falsa))


def test_datos_opcionales_vacios_o_mal_escritos():
    datos = {**RESPUESTA, "periodo_inicio": "", "periodo_fin": "5 de octubre",
             "saldo_al_corte": "", "ultimos_digitos_cuenta": "", "movimientos": []}  # fmt: skip

    documento = extraer(ClienteFalso(respuesta(datos))).documento

    assert (documento.periodo_inicio, documento.periodo_fin, documento.saldo_al_corte) == (
        None,
        None,
        None,
    )
    assert documento.ultimos_digitos_cuenta == ""


def test_descripcion_larga_se_recorta():
    datos = {**RESPUESTA, "movimientos": [movimiento(descripcion="X " * 300)]}

    (unico,) = extraer(ClienteFalso(respuesta(datos))).movimientos

    assert len(unico.descripcion) == 255


def test_mensaje_con_catalogos_y_texto():
    mensaje = construir_mensaje("Compra OXXO 85.50", {"categorias": ["Comida", "Café"]})

    assert "<documento>\nCompra OXXO 85.50\n</documento>" in mensaje
    assert "Café" in mensaje


def test_el_cliente_real_se_crea_hasta_usarlo():
    assert ExtractorClaude()._cliente is None


def test_sin_clave_de_api(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    with pytest.raises(ErrorExtraccion, match="ANTHROPIC_API_KEY"):
        ExtractorClaude().extraer("texto", {})
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_extractor.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.importacion.extractor'`.

- [ ] **Step 3: Implementar**

`apps/importacion/extractor.py`:
```python
"""Extracción de movimientos con Claude (IMP-05, IMP-10, IMP-11, IMP-13).

Solo recibe texto ya protegido (RNF-03). La respuesta es JSON con un esquema fijo; se valida
con Pydantic y los movimientos que no pasan la validación se descartan y se cuentan.
"""

import json
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

import anthropic
from pydantic import BaseModel, field_validator
from pydantic import ValidationError as ErrorDeValidacion

from apps.calculos.comun import redondear
from apps.importacion.errores import ErrorExtraccion
from apps.movimientos.models import TipoIngreso

MODELO = "claude-opus-5-5"
BETA_RESPALDO = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
MONTO_MAXIMO = Decimal("9999999999.99")
# US$ por millón de tokens (entrada, salida) según el modelo que respondió.
PRECIOS_POR_MILLON = {
    "claude-opus-5-5": (Decimal("4"), Decimal("20")),
    "claude-opus-5": (Decimal("5"), Decimal("25")),
    "claude-opus-4-8": (Decimal("5"), Decimal("25")),
}

INSTRUCCIONES = """\
Extraes movimientos de documentos financieros de una familia en México: estados de cuenta \
(débito, tarjetas de crédito y créditos), recibos de nómina y recibos de servicios (luz, agua, \
internet). Recibes el texto del PDF, con algunos datos personales ocultos (por ejemplo [RFC] o \
****1234), y los catálogos del hogar.

Devuelve el tipo de documento, el emisor, el periodo, los últimos 4 dígitos de la cuenta, el saldo \
al corte (solo estados de cuenta) y los movimientos:
- Montos siempre positivos; el tipo da el sentido: gasto (compra, cargo, retiro, comisión), \
ingreso (depósito, abono, nómina, reembolso), pago_deuda (pago a una tarjeta o crédito) o \
transferencia (entre cuentas propias).
- Estado de cuenta: un movimiento por cada operación del periodo; sin saldos, totales ni resúmenes.
- Recibo de nómina: un ingreso con tipo_ingreso «salario» por el neto pagado menos las \
percepciones extraordinarias, con el periodo en la descripción; cada percepción extraordinaria \
(aguinaldo, ptu, bono) es otro ingreso con su tipo_ingreso y es_extraordinario = true.
- Recibo de servicio: un solo gasto por el total a pagar con la fecha límite de pago; elige el \
concepto del servicio y el domicilio cuya dirección coincida con la del recibo.
- categoria, concepto, persona y domicilio: copia exactamente un nombre de los catálogos, o "" si \
ninguno aplica. No inventes nombres.
- confianza: de 0 a 1, qué tan seguro estás de la clasificación del movimiento.
- Fechas en formato AAAA-MM-DD. Usa "" para los datos que no aparezcan.
"""


def _objeto(propiedades):
    return {
        "type": "object",
        "properties": propiedades,
        "required": list(propiedades),
        "additionalProperties": False,
    }


_TEXTO = {"type": "string"}
ESQUEMA = _objeto(
    {
        "tipo_documento": {
            "type": "string",
            "enum": ["estado_cuenta", "nomina", "recibo_servicio", "otro"],
        },
        "emisor": {"type": "string", "description": "Banco o empresa que emite el documento."},
        "periodo_inicio": {"type": "string", "description": "AAAA-MM-DD o vacío."},
        "periodo_fin": {"type": "string", "description": "AAAA-MM-DD o vacío."},
        "ultimos_digitos_cuenta": {"type": "string", "description": "Últimos 4 dígitos o vacío."},
        "saldo_al_corte": {
            "type": "string",
            "description": "Solo estados de cuenta, ej. 6839.01; vacío si no aplica.",
        },
        "movimientos": {
            "type": "array",
            "items": _objeto(
                {
                    "fecha": {"type": "string", "description": "AAAA-MM-DD"},
                    "descripcion": _TEXTO,
                    "monto": {"type": "number", "description": "Siempre positivo."},
                    "tipo": {
                        "type": "string",
                        "enum": ["gasto", "ingreso", "transferencia", "pago_deuda"],
                    },
                    "tipo_ingreso": {"type": "string", "enum": ["", *TipoIngreso.values]},
                    "es_extraordinario": {"type": "boolean"},
                    "categoria": _TEXTO,
                    "concepto": _TEXTO,
                    "persona": _TEXTO,
                    "domicilio": _TEXTO,
                    "confianza": {"type": "number", "description": "De 0 a 1."},
                }
            ),
        },
    }
)


def _decimal(valor):
    try:
        return Decimal(str(valor).replace(",", "").strip())
    except InvalidOperation as error:
        raise ValueError("no es un número") from error


class DocumentoIA(BaseModel):
    tipo_documento: Literal["estado_cuenta", "nomina", "recibo_servicio", "otro"]
    emisor: str
    periodo_inicio: date | None
    periodo_fin: date | None
    ultimos_digitos_cuenta: str
    saldo_al_corte: Decimal | None

    @field_validator("periodo_inicio", "periodo_fin", mode="before")
    @classmethod
    def _fecha_opcional(cls, valor):
        try:
            return date.fromisoformat(str(valor))
        except ValueError:
            return None

    @field_validator("saldo_al_corte", mode="before")
    @classmethod
    def _saldo(cls, valor):
        try:
            saldo = redondear(_decimal(valor))
        except ValueError:
            return None
        return saldo if abs(saldo) <= MONTO_MAXIMO else None

    @field_validator("emisor")
    @classmethod
    def _emisor(cls, valor):
        return valor.strip()[:80]

    @field_validator("ultimos_digitos_cuenta")
    @classmethod
    def _digitos(cls, valor):
        return "".join(caracter for caracter in valor if caracter.isdigit())[-4:]


class MovimientoIA(BaseModel):
    fecha: date
    descripcion: str
    monto: Decimal
    tipo: Literal["gasto", "ingreso", "transferencia", "pago_deuda"]
    tipo_ingreso: str
    es_extraordinario: bool
    categoria: str
    concepto: str
    persona: str
    domicilio: str
    confianza: Decimal

    @field_validator("monto", "confianza", mode="before")
    @classmethod
    def _numero(cls, valor):
        return _decimal(valor)

    @field_validator("monto")
    @classmethod
    def _monto(cls, valor):
        monto = redondear(abs(valor))
        if not Decimal("0.01") <= monto <= MONTO_MAXIMO:
            raise ValueError("monto fuera de rango")
        return monto

    @field_validator("confianza")
    @classmethod
    def _confianza(cls, valor):
        return redondear(min(max(valor, Decimal("0")), Decimal("1")))

    @field_validator("descripcion")
    @classmethod
    def _descripcion(cls, valor):
        texto = " ".join(valor.split())[:255]
        if not texto:
            raise ValueError("sin descripción")
        return texto

    @field_validator("tipo_ingreso")
    @classmethod
    def _tipo_ingreso(cls, valor):
        return valor if valor in TipoIngreso.values else ""


@dataclass(frozen=True)
class Uso:
    modelo: str
    tokens_entrada: int
    tokens_salida: int
    costo_usd: Decimal


@dataclass(frozen=True)
class ResultadoExtraccion:
    documento: DocumentoIA
    movimientos: list
    descartados: int
    uso: Uso


def construir_mensaje(texto, catalogos):
    return (
        "Catálogos del hogar (usa estos nombres tal cual):\n<catalogos>\n"
        + json.dumps(catalogos, ensure_ascii=False, indent=1)
        + "\n</catalogos>\n\nTexto del documento:\n<documento>\n"
        + texto
        + "\n</documento>"
    )


def costo_usd(modelo, entrada, salida):
    por_entrada, por_salida = PRECIOS_POR_MILLON.get(modelo, PRECIOS_POR_MILLON[MODELO])
    return redondear((entrada * por_entrada + salida * por_salida) / Decimal(1_000_000), 4)


def uso_de(respuesta):
    uso = respuesta.usage
    entrada = (
        uso.input_tokens
        + (getattr(uso, "cache_creation_input_tokens", None) or 0)
        + (getattr(uso, "cache_read_input_tokens", None) or 0)
    )
    salida = uso.output_tokens
    return Uso(
        modelo=respuesta.model,
        tokens_entrada=entrada,
        tokens_salida=salida,
        costo_usd=costo_usd(respuesta.model, entrada, salida),
    )


def interpretar(texto_json, uso):
    try:
        datos = json.loads(texto_json)
    except json.JSONDecodeError as error:
        raise ErrorExtraccion("La IA devolvió una respuesta que no se pudo leer.") from error
    if not isinstance(datos, dict):
        raise ErrorExtraccion("La IA devolvió una respuesta que no se pudo leer.")
    crudos = datos.pop("movimientos", None) or []
    try:
        documento = DocumentoIA.model_validate(datos)
    except ErrorDeValidacion as error:
        raise ErrorExtraccion("La IA devolvió datos del documento incompletos.") from error
    movimientos, descartados = [], 0
    for crudo in crudos if isinstance(crudos, list) else []:
        try:
            movimientos.append(MovimientoIA.model_validate(crudo))
        except ErrorDeValidacion:
            descartados += 1
    return ResultadoExtraccion(documento, movimientos, descartados, uso)


class ExtractorClaude:
    """Envía el texto protegido a Claude y devuelve los datos estructurados."""

    def __init__(self, cliente=None):
        self._cliente = cliente

    @property
    def cliente(self):
        if self._cliente is None:
            if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                raise ErrorExtraccion(
                    "Falta configurar la clave de la API de Claude (ANTHROPIC_API_KEY) en el "
                    "archivo .env."
                )
            self._cliente = anthropic.Anthropic()
        return self._cliente

    def extraer(self, texto, catalogos):
        respuesta = self.cliente.beta.messages.create(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            betas=[BETA_RESPALDO],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
            system=INSTRUCCIONES,
            messages=[{"role": "user", "content": construir_mensaje(texto, catalogos)}],
        )
        if respuesta.stop_reason == "refusal":
            raise ErrorExtraccion("La IA no aceptó procesar este documento.")
        if respuesta.stop_reason == "max_tokens":
            raise ErrorExtraccion("El documento es demasiado largo para procesarlo de una sola vez.")
        texto_json = next((b.text for b in respuesta.content if b.type == "text"), "")
        if not texto_json:
            raise ErrorExtraccion("La IA no devolvió datos.")
        return interpretar(texto_json, uso_de(respuesta))
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_extractor.py` 15 passed; todo verde. Ninguna prueba llama a la API real.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion/extractor.py tests/importacion/test_imp_extractor.py
git commit -m "feat(importacion): extractor con Claude Opus 5.5, esquema JSON estricto, validacion y costo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Registro de archivos y cola de procesamiento (IMP-01, IMP-02, IMP-13)

**Files:**
- Create: `apps/importacion/servicios.py`
- Test: `tests/importacion/test_imp_registro.py`

**Interfaces:**
- Consumes: `Documento` (Task 2); `archivos` (Task 3); `async_task` de `django_q.tasks`.
- Produces (en `apps.importacion.servicios`):
  - `Rechazo(nombre, motivo)` (dataclass).
  - `registrar_archivos(hogar, usuario, subidos, cuenta=None) -> (list[Documento], list[Rechazo])`: guarda cada PDF (o los PDFs de un ZIP), rechaza duplicados por SHA-256 con la fecha de importación, y encola cada documento.
  - `encolar_procesamiento(documento)`: `async_task("apps.importacion.tareas.procesar", documento.pk)`.
  - `costo_del_mes(hogar, hoy=None) -> Decimal` (suma de `costo_estimado_usd` de los documentos del mes).
  - `reintentar(documento)` (vuelve a `subido`, limpia el error y encola) y `eliminar_documento(documento)` (borra el archivo y el registro; los movimientos se conservan).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_registro.py`:
```python
import io
import zipfile
from datetime import date
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django_q.models import OrmQ

from apps.importacion import archivos, servicios
from apps.importacion.archivos import huella
from apps.importacion.models import Documento
from apps.importacion.servicios import costo_del_mes, registrar_archivos

pytestmark = pytest.mark.django_db


@pytest.fixture
def encolados(monkeypatch):
    lista = []
    monkeypatch.setattr(
        servicios, "async_task", lambda funcion, documento_id: lista.append((funcion, documento_id))
    )
    return lista


def subir(nombre, datos):
    return SimpleUploadedFile(nombre, datos)


def hacer_zip(miembros):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as comprimido:
        for nombre, datos in miembros.items():
            comprimido.writestr(nombre, datos)
    return buffer.getvalue()


def test_registra_un_pdf_y_lo_encola(hogar, usuario, crear_pdf, encolados):
    datos = crear_pdf("Estado de cuenta")

    documentos, rechazos = registrar_archivos(hogar, usuario, [subir("estado.pdf", datos)])

    (documento,) = documentos
    assert rechazos == []
    assert (documento.nombre_original, documento.sha256) == ("estado.pdf", huella(datos))
    assert (documento.subido_por, documento.estado) == (usuario, Documento.Estado.SUBIDO)
    with documento.archivo.open("rb") as archivo:
        assert archivo.read() == datos
    assert encolados == [("apps.importacion.tareas.procesar", documento.pk)]


def test_rechaza_un_archivo_ya_importado(hogar, usuario, crear_pdf, encolados):
    datos = crear_pdf("Estado")
    registrar_archivos(hogar, usuario, [subir("a.pdf", datos)])

    documentos, (rechazo,) = registrar_archivos(hogar, usuario, [subir("copia.pdf", datos)])

    assert documentos == []
    assert rechazo.nombre == "copia.pdf"
    assert rechazo.motivo == f"ya se importó el {timezone.localdate():%d/%m/%Y}"
    assert Documento.objects.count() == 1


def test_el_mismo_pdf_en_otro_hogar_si_se_importa(hogar, otro_hogar, usuario, crear_pdf, encolados):
    datos = crear_pdf("Estado")
    registrar_archivos(hogar, usuario, [subir("a.pdf", datos)])

    documentos, rechazos = registrar_archivos(otro_hogar, usuario, [subir("a.pdf", datos)])

    assert (len(documentos), rechazos) == (1, [])


def test_zip_con_varios_pdfs(hogar, usuario, crear_pdf, encolados):
    comprimido = hacer_zip({"estado.pdf": crear_pdf("Estado"), "factura.pdf": crear_pdf("Factura")})

    documentos, rechazos = registrar_archivos(hogar, usuario, [subir("internet.zip", comprimido)])

    assert sorted(d.nombre_original for d in documentos) == ["estado.pdf", "factura.pdf"]
    assert (rechazos, len(encolados)) == ([], 2)


def test_archivos_invalidos_o_grandes(monkeypatch, hogar, usuario, crear_pdf, encolados):
    monkeypatch.setattr(archivos, "TAMANO_MAXIMO", 200)

    _, rechazos = registrar_archivos(
        hogar,
        usuario,
        [subir("foto.jpg", b"\xff\xd8 imagen"), subir("grande.pdf", crear_pdf("Texto " * 100))],
    )

    assert [(r.nombre, r.motivo) for r in rechazos] == [
        ("foto.jpg", "no es un PDF ni un ZIP"),
        ("grande.pdf", "pesa más de 0 MB"),
    ]
    assert not Documento.objects.exists()
    assert encolados == []


def test_cuenta_elegida_al_subir(catalogo, usuario, crear_pdf, encolados):
    (documento,), _ = registrar_archivos(
        catalogo.tarjeta.hogar, usuario, [subir("tarjeta.pdf", crear_pdf("x"))], cuenta=catalogo.tarjeta
    )

    assert documento.cuenta == catalogo.tarjeta


def test_encolar_crea_una_tarea_en_la_base(hogar, usuario, crear_pdf):
    registrar_archivos(hogar, usuario, [subir("estado.pdf", crear_pdf("Estado"))])

    assert OrmQ.objects.count() == 1


def test_costo_del_mes(hogar, otro_hogar):
    for destino, letra, costo in [(hogar, "a", "0.0800"), (hogar, "b", "0.0350"),
                                  (otro_hogar, "c", "1")]:  # fmt: skip
        Documento.objects.create(
            hogar=destino, nombre_original="x.pdf", sha256=letra * 64, costo_estimado_usd=D(costo)
        )

    assert costo_del_mes(hogar) == D("0.1150")
    assert costo_del_mes(hogar, date(2000, 1, 1)) == 0
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_registro.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.importacion.servicios'`.

- [ ] **Step 3: Implementar**

`apps/importacion/servicios.py`:
```python
"""Servicios de importación: registro, procesamiento (worker) y revisión de propuestas."""

import logging
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone
from django_q.tasks import async_task

from apps.calculos.comun import CERO
from apps.importacion import archivos
from apps.importacion.errores import ErrorImportacion
from apps.importacion.models import Documento

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rechazo:
    nombre: str
    motivo: str


def registrar_archivos(hogar, usuario, subidos, cuenta=None):
    """IMP-01/02: guarda cada PDF (o los PDFs de un ZIP) y lo encola."""
    documentos, rechazos = [], []
    for subido in subidos:
        if subido.size > archivos.TAMANO_MAXIMO:
            rechazos.append(Rechazo(subido.name, f"pesa más de {archivos.megas()} MB"))
            continue
        try:
            pdfs = archivos.pdfs_del_archivo(subido.name, subido.read())
        except ErrorImportacion as error:
            rechazos.append(Rechazo(subido.name, str(error)))
            continue
        for nombre, contenido in pdfs:
            huella = archivos.huella(contenido)
            previo = Documento.objects.del_hogar(hogar).filter(sha256=huella).first()
            if previo:
                fecha = timezone.localtime(previo.creado_en)
                rechazos.append(Rechazo(nombre, f"ya se importó el {fecha:%d/%m/%Y}"))
                continue
            documentos.append(_registrar_pdf(hogar, usuario, nombre, contenido, huella, cuenta))
    return documentos, rechazos


def _registrar_pdf(hogar, usuario, nombre, contenido, huella, cuenta):
    documento = Documento(
        hogar=hogar, nombre_original=nombre[:255], sha256=huella, cuenta=cuenta, subido_por=usuario
    )
    documento.archivo.save(f"{huella}.pdf", ContentFile(contenido), save=False)
    documento.save()
    encolar_procesamiento(documento)
    return documento


def encolar_procesamiento(documento):
    async_task("apps.importacion.tareas.procesar", documento.pk)


def costo_del_mes(hogar, hoy=None):
    """IMP-13: costo de IA acumulado en el mes (US$)."""
    hoy = hoy or timezone.localdate()
    total = (
        Documento.objects.del_hogar(hogar)
        .filter(creado_en__year=hoy.year, creado_en__month=hoy.month)
        .aggregate(total=Sum("costo_estimado_usd"))["total"]
    )
    return total or CERO


def reintentar(documento):
    documento.estado = Documento.Estado.SUBIDO
    documento.error = ""
    documento.save(update_fields=["estado", "error", "actualizado_en"])
    encolar_procesamiento(documento)


def eliminar_documento(documento):
    """Borra el PDF y el documento; los movimientos ya aceptados se conservan."""
    documento.archivo.delete(save=False)
    documento.delete()
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_registro.py` 8 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion/servicios.py tests/importacion/test_imp_registro.py
git commit -m "feat(importacion): registro de PDFs y ZIPs, rechazo de duplicados por huella y cola de procesamiento" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Procesamiento en el worker (IMP-03..07, IMP-10, IMP-11, IMP-13)

**Files:**
- Modify: `apps/importacion/servicios.py`
- Create: `apps/importacion/tareas.py`
- Test: `tests/importacion/test_imp_procesamiento.py`

**Interfaces:**
- Consumes: `extraer_texto`, `proteger_datos` (Task 4); `normalizar`, `buscar_regla`, `aplicar_regla`, `buscar_duplicado` (Task 5); `interpretar`, `Uso`, `ResultadoExtraccion` (Task 6); `metodo_para_cuenta` (`apps.movimientos.servicios`); `settings.IMPORTACION_EXTRACTOR` (Task 1).
- Produces:
  - `servicios.obtener_extractor()` (instancia la clase de `settings.IMPORTACION_EXTRACTOR`; las pruebas la reemplazan).
  - `servicios.Catalogo` con `del_hogar(hogar)`, `buscar(tipo, nombre)` (`tipo` ∈ `categorias, conceptos, personas, domicilios`), `cuenta_por_digitos(digitos)` y `para_ia() -> dict`.
  - `servicios.procesar_documento(documento_id)`: solo procesa documentos en `subido` o `error`; pasa a `procesando`, extrae texto, protege datos, llama al extractor y crea propuestas (reemplaza las anteriores) → `por_revisar`. Ante cualquier falla deja el documento en `error` con un mensaje claro.
  - `apps.importacion.tareas.procesar(documento_id)` (tarea de Django-Q2).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_procesamiento.py`:
```python
import json
from datetime import date
from decimal import Decimal as D

import anthropic
import httpx2
import pytest
from django.core.files.base import ContentFile

from apps.importacion import servicios, tareas
from apps.importacion.archivos import huella
from apps.importacion.errores import ErrorExtraccion
from apps.importacion.extractor import Uso, interpretar
from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
USO = Uso("claude-opus-5-5", 10000, 2000, D("0.0800"))
TEXTO = "BANCO DEMO estado de cuenta\nRFC XAXX010101000\nCompra OXXO 85.50"


def movimiento_ia(**campos):
    datos = {
        "fecha": "2026-09-10",
        "descripcion": "OXXO SUC 1234",
        "monto": 85.5,
        "tipo": "gasto",
        "tipo_ingreso": "",
        "es_extraordinario": False,
        "categoria": "Comida",
        "concepto": "",
        "persona": "",
        "domicilio": "",
        "confianza": 0.9,
    }
    datos.update(campos)
    return datos


def resultado(movimientos, **documento):
    datos = {
        "tipo_documento": "estado_cuenta",
        "emisor": "Banco Demo",
        "periodo_inicio": "2026-09-06",
        "periodo_fin": "2026-10-05",
        "ultimos_digitos_cuenta": "",
        "saldo_al_corte": "6839.01",
        **documento,
        "movimientos": movimientos,
    }
    return interpretar(json.dumps(datos), USO)


class ExtractorFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def extraer(self, texto, catalogos):
        self.llamadas.append((texto, catalogos))
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


@pytest.fixture
def usar_extractor(monkeypatch):
    def usar(respuesta):
        falso = ExtractorFalso(respuesta)
        monkeypatch.setattr(servicios, "obtener_extractor", lambda: falso)
        return falso

    return usar


@pytest.fixture
def documento_pdf(hogar, crear_pdf):
    def crear(*paginas, cuenta=None):
        datos = crear_pdf(*paginas)
        documento = Documento(
            hogar=hogar, nombre_original="estado.pdf", sha256=huella(datos), cuenta=cuenta
        )
        documento.archivo.save("x.pdf", ContentFile(datos), save=False)
        documento.save()
        return documento

    return crear


def procesar(documento):
    servicios.procesar_documento(documento.pk)
    documento.refresh_from_db()
    return documento


def test_procesa_y_crea_propuestas(catalogo, documento_pdf, usar_extractor):
    usar_extractor(
        resultado(
            [
                movimiento_ia(concepto="gasolina", persona="MONZE", monto=650),
                movimiento_ia(descripcion="INVENTADO", categoria="Inexistente"),
            ]
        )
    )

    documento = procesar(documento_pdf(TEXTO, cuenta=catalogo.nomina))

    assert documento.estado == Documento.Estado.POR_REVISAR
    assert (documento.tipo, documento.emisor, documento.paginas) == ("estado_cuenta", "Banco Demo", 1)
    assert (documento.periodo_fin, documento.saldo_al_corte) == (date(2026, 10, 5), D("6839.01"))
    assert (documento.modelo_ia, documento.tokens_entrada, documento.tokens_salida) == (
        "claude-opus-5-5",
        10000,
        2000,
    )
    assert documento.costo_estimado_usd == D("0.0800")
    gasolina, inventado = documento.propuestas.all()
    assert (gasolina.concepto, gasolina.categoria) == (
        catalogo.gasolina,
        catalogo.categorias["Transporte"],
    )
    assert (gasolina.persona, gasolina.cuenta, gasolina.monto) == (
        catalogo.monze,
        catalogo.nomina,
        D("650.00"),
    )
    assert gasolina.metodo_pago == MetodoPago.TARJETA_DEBITO
    assert gasolina.estado == MovimientoPropuesto.Estado.PENDIENTE
    assert (inventado.categoria, inventado.concepto) == (None, None)


def test_a_la_ia_solo_va_texto_protegido_y_catalogos(catalogo, documento_pdf, usar_extractor):
    extractor = usar_extractor(resultado([]))

    procesar(documento_pdf(TEXTO))

    ((texto, catalogos),) = extractor.llamadas
    assert "XAXX010101000" not in texto
    assert "[RFC]" in texto
    assert "Compra OXXO 85.50" in texto
    assert "estado.pdf" not in texto
    assert "Gasolina" in [c["concepto"] for c in catalogos["conceptos"]]
    assert {"alias": "Casa Fidel", "direccion": ""} in catalogos["domicilios"]


def test_la_regla_del_hogar_manda_sobre_la_ia(catalogo, documento_pdf, usar_extractor):
    casa = catalogo.categorias["Casa"]
    regla = ReglaClasificacion.objects.create(
        hogar=catalogo.gasolina.hogar, patron="oxxo", categoria=casa, persona=catalogo.monze
    )
    usar_extractor(resultado([movimiento_ia(categoria="Comida")]))

    propuesta = procesar(documento_pdf(TEXTO)).propuestas.get()

    assert (propuesta.categoria, propuesta.persona, propuesta.regla) == (casa, catalogo.monze, regla)
    assert propuesta.confianza == D("1")


def test_marca_posible_duplicado(catalogo, documento_pdf, usar_extractor):
    existente = guardar_movimiento(
        Movimiento(
            hogar=catalogo.nomina.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("85.50"),
            concepto=catalogo.gasolina,
            cuenta=catalogo.nomina,
            fecha=date(2026, 9, 11),
        )
    )
    usar_extractor(resultado([movimiento_ia()]))

    propuesta = procesar(documento_pdf(TEXTO, cuenta=catalogo.nomina)).propuestas.get()

    assert propuesta.posible_duplicado_de == existente


def test_pago_a_la_tarjeta_en_su_estado_de_cuenta(catalogo, documento_pdf, usar_extractor):
    usar_extractor(
        resultado([movimiento_ia(tipo="pago_deuda", descripcion="PAGO RECIBIDO", monto=2000)])
    )

    propuesta = procesar(documento_pdf(TEXTO, cuenta=catalogo.tarjeta)).propuestas.get()

    assert (propuesta.cuenta, propuesta.cuenta_destino) == (None, catalogo.tarjeta)
    assert (propuesta.metodo_pago, propuesta.categoria) == (MetodoPago.TRANSFERENCIA, None)


def test_cuenta_por_ultimos_digitos(catalogo, documento_pdf, usar_extractor):
    catalogo.nomina.ultimos_digitos = "1234"
    catalogo.nomina.save()
    usar_extractor(resultado([movimiento_ia()], ultimos_digitos_cuenta="****1234"))

    documento = procesar(documento_pdf(TEXTO))

    assert documento.cuenta == catalogo.nomina
    assert documento.propuestas.get().cuenta == catalogo.nomina


def test_nomina(catalogo, documento_pdf, usar_extractor):
    usar_extractor(
        resultado(
            [
                movimiento_ia(tipo="ingreso", descripcion="NETO QUINCENA", monto=8000),
                movimiento_ia(
                    tipo="ingreso", tipo_ingreso="aguinaldo", es_extraordinario=True, monto=20000
                ),
            ],
            tipo_documento="nomina",
        )
    )

    salario, aguinaldo = procesar(documento_pdf(TEXTO)).propuestas.all()

    assert (salario.tipo_ingreso, salario.es_extraordinario, salario.categoria) == (
        "salario",
        False,
        None,
    )
    assert (aguinaldo.tipo_ingreso, aguinaldo.es_extraordinario) == ("aguinaldo", True)


def test_aviso_si_hubo_movimientos_ilegibles(catalogo, documento_pdf, usar_extractor):
    usar_extractor(resultado([movimiento_ia(), movimiento_ia(monto=0)]))

    documento = procesar(documento_pdf(TEXTO))

    assert "1 movimiento(s) no se pudieron leer" in documento.aviso
    assert documento.propuestas.count() == 1


def test_pdf_sin_texto_queda_en_error(documento_pdf, usar_extractor):
    extractor = usar_extractor(resultado([]))

    documento = procesar(documento_pdf("", ""))

    assert documento.estado == Documento.Estado.ERROR
    assert "OCR" in documento.error
    assert extractor.llamadas == []


def test_error_de_la_ia_queda_en_el_documento(documento_pdf, usar_extractor):
    usar_extractor(ErrorExtraccion("La IA no aceptó procesar este documento."))

    documento = procesar(documento_pdf(TEXTO))

    assert (documento.estado, documento.error) == (
        Documento.Estado.ERROR,
        "La IA no aceptó procesar este documento.",
    )


def test_sin_conexion_con_la_ia(documento_pdf, usar_extractor):
    peticion = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    usar_extractor(anthropic.APIConnectionError(request=peticion))

    documento = procesar(documento_pdf(TEXTO))

    assert documento.estado == Documento.Estado.ERROR
    assert "No se pudo contactar a la IA" in documento.error


def test_error_inesperado_no_deja_el_documento_atascado(documento_pdf, usar_extractor):
    usar_extractor(RuntimeError("falla interna"))

    documento = procesar(documento_pdf(TEXTO))

    assert documento.estado == Documento.Estado.ERROR
    assert "error inesperado" in documento.error


def test_reprocesar_reemplaza_las_propuestas(catalogo, documento_pdf, usar_extractor):
    usar_extractor(resultado([movimiento_ia(), movimiento_ia(descripcion="OTRO")]))
    documento = procesar(documento_pdf(TEXTO))
    Documento.objects.filter(pk=documento.pk).update(estado=Documento.Estado.ERROR)

    documento = procesar(documento)

    assert documento.propuestas.count() == 2


def test_documento_ya_procesado_no_se_vuelve_a_procesar(catalogo, documento_pdf, usar_extractor):
    extractor = usar_extractor(resultado([movimiento_ia()]))
    documento = procesar(documento_pdf(TEXTO))

    procesar(documento)

    assert len(extractor.llamadas) == 1
    assert documento.propuestas.count() == 1


def test_tarea_del_worker(catalogo, documento_pdf, usar_extractor):
    usar_extractor(resultado([movimiento_ia()]))
    documento = documento_pdf(TEXTO)

    tareas.procesar(documento.pk)

    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.POR_REVISAR
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_procesamiento.py -v`
Expected: ERROR con `ImportError: cannot import name 'tareas'` (o `AttributeError: ... 'obtener_extractor'`).

- [ ] **Step 3: Implementar**

En `apps/importacion/servicios.py`, reemplazar los imports por:
```python
import logging
from dataclasses import dataclass

import anthropic
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.module_loading import import_string
from django_q.tasks import async_task

from apps.calculos.comun import CERO
from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.importacion import archivos
from apps.importacion.clasificacion import (
    aplicar_regla,
    buscar_duplicado,
    buscar_regla,
    normalizar,
)
from apps.importacion.errores import ErrorImportacion
from apps.importacion.models import Documento, MovimientoPropuesto
from apps.importacion.texto import extraer_texto, proteger_datos
from apps.movimientos.models import TIPOS_DEUDA, MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import metodo_para_cuenta
```
y agregar al final:
```python
def obtener_extractor():
    return import_string(settings.IMPORTACION_EXTRACTOR)()


@dataclass
class Catalogo:
    """Catálogos activos del hogar, buscables por nombre normalizado."""

    categorias: dict
    conceptos: dict
    personas: dict
    domicilios: dict
    cuentas: list

    @classmethod
    def del_hogar(cls, hogar):
        def activos(modelo):
            return modelo.objects.del_hogar(hogar).filter(activo=True)

        conceptos = activos(Concepto).select_related("categoria", "domicilio")
        return cls(
            categorias={normalizar(c.nombre): c for c in activos(Categoria)},
            conceptos={normalizar(str(c)): c for c in conceptos},
            personas={normalizar(p.nombre): p for p in activos(Persona)},
            domicilios={normalizar(d.alias): d for d in activos(Domicilio)},
            cuentas=list(activos(Cuenta)),
        )

    def buscar(self, tipo, nombre):
        return getattr(self, tipo).get(normalizar(nombre)) if nombre else None

    def cuenta_por_digitos(self, digitos):
        coincidencias = [c for c in self.cuentas if digitos and c.ultimos_digitos == digitos]
        return coincidencias[0] if len(coincidencias) == 1 else None

    def para_ia(self):
        return {
            "categorias": [c.nombre for c in self.categorias.values()],
            "conceptos": [
                {"concepto": str(c), "categoria": c.categoria.nombre}
                for c in self.conceptos.values()
            ],
            "personas": [p.nombre for p in self.personas.values()],
            "domicilios": [
                {"alias": d.alias, "direccion": d.direccion} for d in self.domicilios.values()
            ],
            "cuentas": [
                {"nombre": c.nombre, "tipo": c.get_tipo_display(), "ultimos_digitos": c.ultimos_digitos}
                for c in self.cuentas
            ],
        }


def procesar_documento(documento_id):
    """Texto → datos protegidos → IA → reglas y duplicados → propuestas por revisar."""
    documento = Documento.objects.select_related("hogar", "cuenta").filter(pk=documento_id).first()
    if documento is None or documento.estado not in (
        Documento.Estado.SUBIDO,
        Documento.Estado.ERROR,
    ):
        return
    documento.estado = Documento.Estado.PROCESANDO
    documento.save(update_fields=["estado", "actualizado_en"])
    try:
        with documento.archivo.open("rb") as archivo:
            texto, documento.paginas = extraer_texto(archivo.read())
        catalogo = Catalogo.del_hogar(documento.hogar)
        resultado = obtener_extractor().extraer(proteger_datos(texto), catalogo.para_ia())
        _guardar_resultado(documento, catalogo, resultado)
    except ErrorImportacion as error:
        _marcar_error(documento, str(error))
    except anthropic.AuthenticationError:
        _marcar_error(
            documento,
            "Falta configurar la clave de la API de Claude (ANTHROPIC_API_KEY) en el archivo .env.",
        )
    except anthropic.APIError as error:
        _marcar_error(
            documento,
            f"No se pudo contactar a la IA ({type(error).__name__}). Intenta de nuevo más tarde.",
        )
    except Exception:
        logger.exception("Error al procesar el documento %s", documento_id)
        _marcar_error(documento, "Ocurrió un error inesperado al procesar el documento.")


def _marcar_error(documento, mensaje):
    documento.estado = Documento.Estado.ERROR
    documento.error = mensaje
    documento.save(update_fields=["estado", "error", "paginas", "actualizado_en"])


@transaction.atomic
def _guardar_resultado(documento, catalogo, resultado):
    datos = resultado.documento
    documento.tipo = datos.tipo_documento
    documento.emisor = datos.emisor
    documento.periodo_inicio = datos.periodo_inicio
    documento.periodo_fin = datos.periodo_fin
    documento.saldo_al_corte = datos.saldo_al_corte
    if documento.cuenta is None:
        documento.cuenta = catalogo.cuenta_por_digitos(datos.ultimos_digitos_cuenta)
    uso = resultado.uso
    documento.modelo_ia = uso.modelo
    documento.tokens_entrada = uso.tokens_entrada
    documento.tokens_salida = uso.tokens_salida
    documento.costo_estimado_usd = uso.costo_usd
    documento.aviso = (
        f"{resultado.descartados} movimiento(s) no se pudieron leer; revisa el PDF original."
        if resultado.descartados
        else ""
    )
    documento.error = ""
    documento.propuestas.all().delete()
    for movimiento in resultado.movimientos:
        _crear_propuesta(documento, catalogo, movimiento)
    documento.estado = Documento.Estado.POR_REVISAR
    documento.save()


def _crear_propuesta(documento, catalogo, datos):
    tipo = datos.tipo
    cuenta, cuenta_destino = documento.cuenta, None
    if tipo == Movimiento.Tipo.PAGO_DEUDA and cuenta is not None and cuenta.tipo in TIPOS_DEUDA:
        cuenta, cuenta_destino = None, documento.cuenta
    tipo_ingreso = ""
    if tipo == Movimiento.Tipo.INGRESO:
        por_defecto = (
            TipoIngreso.SALARIO if documento.tipo == Documento.Tipo.NOMINA else TipoIngreso.OTRO
        )
        tipo_ingreso = datos.tipo_ingreso or por_defecto
    concepto = categoria = None
    if tipo == Movimiento.Tipo.GASTO:
        concepto = catalogo.buscar("conceptos", datos.concepto)
        categoria = concepto.categoria if concepto else catalogo.buscar("categorias", datos.categoria)
    propuesta = MovimientoPropuesto(
        hogar=documento.hogar,
        documento=documento,
        fecha=datos.fecha,
        descripcion_original=datos.descripcion,
        descripcion=datos.descripcion,
        monto=datos.monto,
        tipo=tipo,
        tipo_ingreso=tipo_ingreso,
        es_extraordinario=tipo == Movimiento.Tipo.INGRESO and datos.es_extraordinario,
        metodo_pago=_metodo(tipo, cuenta),
        categoria=categoria,
        concepto=concepto,
        persona=catalogo.buscar("personas", datos.persona),
        domicilio=catalogo.buscar("domicilios", datos.domicilio),
        cuenta=cuenta,
        cuenta_destino=cuenta_destino,
        confianza=datos.confianza,
    )
    regla = buscar_regla(documento.hogar, documento.emisor, datos.descripcion)
    if regla is not None:
        aplicar_regla(propuesta, regla)
    propuesta.posible_duplicado_de = buscar_duplicado(
        documento.hogar, datos.fecha, datos.monto, cuenta or cuenta_destino
    )
    propuesta.save()


def _metodo(tipo, cuenta):
    if tipo != Movimiento.Tipo.GASTO:
        return MetodoPago.TRANSFERENCIA
    return metodo_para_cuenta(cuenta)
```

`apps/importacion/tareas.py`:
```python
"""Tareas de Django-Q2; las ejecuta el contenedor worker (`manage.py qcluster`)."""

from apps.importacion import servicios


def procesar(documento_id):
    servicios.procesar_documento(documento_id)
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_procesamiento.py` 15 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion tests/importacion/test_imp_procesamiento.py
git commit -m "feat(importacion): procesamiento en el worker con texto protegido, IA, reglas y duplicados" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Revisión de propuestas (IMP-08, IMP-09, IMP-12)

**Files:**
- Modify: `apps/importacion/servicios.py`
- Test: `tests/importacion/test_imp_revision.py`

**Interfaces:**
- Consumes: `MovimientoPropuesto`, `ReglaClasificacion`, `Documento` (Task 2); `patron_sugerido` (Task 5); `guardar_movimiento` (RN-14).
- Produces (en `apps.importacion.servicios`):
  - `aceptar_propuesta(propuesta, usuario=None, recordar=False) -> Movimiento`: crea el movimiento con `origen = importado` y el documento; si los datos no son válidos guarda el mensaje en `propuesta.error` y relanza `ValidationError`; nunca crea dos movimientos para la misma propuesta.
  - `recordar_clasificacion(propuesta) -> ReglaClasificacion | None`, `descartar_propuesta(propuesta)`, `aceptar_no_duplicados(documento, usuario) -> (aceptadas, con_error)`, `descartar_todas(documento)`, `actualizar_estado_documento(documento)` (sin pendientes → `confirmado` si alguna se aceptó, si no `descartado`), `actualizar_saldo(documento) -> bool` (IMP-12).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_revision.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.importacion.servicios import (
    aceptar_no_duplicados,
    aceptar_propuesta,
    actualizar_saldo,
    descartar_propuesta,
    descartar_todas,
)
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
PENDIENTE = MovimientoPropuesto.Estado.PENDIENTE


@pytest.fixture
def documento(hogar):
    return Documento.objects.create(
        hogar=hogar,
        nombre_original="estado.pdf",
        sha256="a" * 64,
        emisor="Banco Demo",
        estado=Documento.Estado.POR_REVISAR,
    )


def propuesta(catalogo, documento, **campos):
    datos = {
        "hogar": documento.hogar,
        "documento": documento,
        "fecha": date(2026, 9, 10),
        "descripcion_original": "OXXO SUC 1234 MTY",
        "descripcion": "OXXO SUC 1234 MTY",
        "monto": D("85.50"),
        "tipo": Movimiento.Tipo.GASTO,
        "categoria": catalogo.categorias["Comida"],
        "cuenta": catalogo.nomina,
        "metodo_pago": MetodoPago.TARJETA_DEBITO,
    }
    datos.update(campos)
    return MovimientoPropuesto.objects.create(**datos)


def test_aceptar_crea_el_movimiento(catalogo, documento, usuario):
    pendiente = propuesta(catalogo, documento)

    movimiento = aceptar_propuesta(pendiente, usuario)

    assert (movimiento.origen, movimiento.documento, movimiento.creado_por) == (
        Movimiento.Origen.IMPORTADO,
        documento,
        usuario,
    )
    assert (movimiento.monto, movimiento.descripcion) == (D("85.50"), "OXXO SUC 1234 MTY")
    pendiente.refresh_from_db()
    assert (pendiente.estado, pendiente.movimiento) == (MovimientoPropuesto.Estado.ACEPTADO, movimiento)
    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.CONFIRMADO


def test_el_documento_sigue_por_revisar_con_pendientes(catalogo, documento, usuario):
    primera = propuesta(catalogo, documento)
    propuesta(catalogo, documento, descripcion="OTRA")

    aceptar_propuesta(primera, usuario)

    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.POR_REVISAR


def test_datos_incompletos_guardan_el_error(catalogo, documento, usuario):
    incompleta = propuesta(catalogo, documento, categoria=None)

    with pytest.raises(ValidationError):
        aceptar_propuesta(incompleta, usuario)

    incompleta.refresh_from_db()
    assert incompleta.estado == PENDIENTE
    assert "No se pudo aceptar" in incompleta.error
    assert "categoría del gasto" in incompleta.error
    assert not Movimiento.objects.exists()


def test_no_se_acepta_dos_veces(catalogo, documento, usuario):
    pendiente = propuesta(catalogo, documento)
    copia_vieja = MovimientoPropuesto.objects.get(pk=pendiente.pk)
    aceptar_propuesta(pendiente, usuario)

    for intento in (pendiente, copia_vieja):
        with pytest.raises(ValidationError):
            aceptar_propuesta(intento, usuario)

    assert Movimiento.objects.count() == 1


def test_aceptar_pago_de_deuda_reduce_el_saldo(catalogo, documento, usuario):
    pago = propuesta(
        catalogo,
        documento,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        categoria=None,
        monto=D("2000"),
        cuenta_destino=catalogo.tarjeta,
        metodo_pago=MetodoPago.TRANSFERENCIA,
    )

    aceptar_propuesta(pago, usuario)

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("4839.01")


def test_recordar_crea_una_regla(catalogo, documento, usuario):
    aceptar_propuesta(propuesta(catalogo, documento, persona=catalogo.monze), usuario, recordar=True)

    regla = ReglaClasificacion.objects.get()
    assert (regla.patron, regla.emisor) == ("oxxo suc", "Banco Demo")
    assert (regla.categoria, regla.persona) == (catalogo.categorias["Comida"], catalogo.monze)


def test_recordar_actualiza_la_regla_existente(catalogo, documento, usuario):
    aceptar_propuesta(propuesta(catalogo, documento), usuario, recordar=True)
    casa = catalogo.categorias["Casa"]

    aceptar_propuesta(propuesta(catalogo, documento, categoria=casa), usuario, recordar=True)

    assert ReglaClasificacion.objects.get().categoria == casa


def test_descartar(catalogo, documento):
    descartada = propuesta(catalogo, documento)

    descartar_propuesta(descartada)

    descartada.refresh_from_db()
    documento.refresh_from_db()
    assert descartada.estado == MovimientoPropuesto.Estado.DESCARTADO
    assert documento.estado == Documento.Estado.DESCARTADO


def test_aceptar_todo_lo_no_duplicado(catalogo, documento, usuario):
    existente = guardar_movimiento(
        Movimiento(
            hogar=documento.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("999"),
            concepto=catalogo.gasolina,
            fecha=date(2026, 9, 10),
        )
    )
    buena = propuesta(catalogo, documento)
    duplicada = propuesta(catalogo, documento, monto=D("999"), posible_duplicado_de=existente)
    invalida = propuesta(catalogo, documento, categoria=None, descripcion="SIN CATEGORIA")

    assert aceptar_no_duplicados(documento, usuario) == (1, 1)

    for revisada, estado in [(buena, "aceptado"), (duplicada, "pendiente"), (invalida, "pendiente")]:
        revisada.refresh_from_db()
        assert revisada.estado == estado
    assert invalida.error


def test_descartar_todas(catalogo, documento):
    propuesta(catalogo, documento)
    propuesta(catalogo, documento, descripcion="OTRA")

    descartar_todas(documento)

    assert set(documento.propuestas.values_list("estado", flat=True)) == {"descartado"}
    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.DESCARTADO


def test_actualizar_saldo_al_corte(catalogo, documento):
    documento.cuenta = catalogo.tarjeta
    documento.saldo_al_corte = D("7000.00")
    documento.periodo_fin = date(2026, 10, 5)
    documento.save()

    assert actualizar_saldo(documento) is True

    catalogo.tarjeta.refresh_from_db()
    assert (catalogo.tarjeta.saldo_actual, catalogo.tarjeta.fecha_saldo) == (
        D("7000.00"),
        date(2026, 10, 5),
    )


def test_sin_cuenta_no_se_actualiza_ningun_saldo(documento):
    documento.saldo_al_corte = D("1")
    documento.save()

    assert actualizar_saldo(documento) is False
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_revision.py -v`
Expected: ERROR con `ImportError: cannot import name 'aceptar_no_duplicados'`.

- [ ] **Step 3: Implementar**

En `apps/importacion/servicios.py`:

1. Agregar a los imports:
```python
from django.core.exceptions import ValidationError

from apps.importacion.clasificacion import patron_sugerido
from apps.importacion.models import ReglaClasificacion
from apps.movimientos.servicios import guardar_movimiento
```
(Unir con los imports existentes de los mismos módulos; ruff ordena el resultado.)

2. Agregar al final:
```python
ESTADO = MovimientoPropuesto.Estado


def aceptar_propuesta(propuesta, usuario=None, recordar=False):
    """IMP-09: crea el movimiento importado. Si no es válido, guarda el error y lo relanza."""
    if propuesta.estado != ESTADO.PENDIENTE:
        raise ValidationError("Esta propuesta ya se revisó.")
    movimiento = _movimiento_de(propuesta)
    try:
        movimiento.full_clean()
    except ValidationError as error:
        propuesta.error = "No se pudo aceptar: " + " ".join(error.messages)
        propuesta.save(update_fields=["error", "actualizado_en"])
        raise
    with transaction.atomic():
        bloqueada = MovimientoPropuesto.objects.select_for_update().get(pk=propuesta.pk)
        if bloqueada.estado != ESTADO.PENDIENTE:
            raise ValidationError("Esta propuesta ya se revisó.")
        guardar_movimiento(movimiento, usuario=usuario)
        propuesta.estado = ESTADO.ACEPTADO
        propuesta.movimiento = movimiento
        propuesta.error = ""
        propuesta.save()
        if recordar:
            recordar_clasificacion(propuesta)
        actualizar_estado_documento(propuesta.documento)
    return movimiento


def _movimiento_de(propuesta):
    return Movimiento(
        hogar=propuesta.hogar,
        fecha=propuesta.fecha,
        tipo=propuesta.tipo,
        monto=propuesta.monto,
        descripcion=propuesta.descripcion,
        categoria=propuesta.categoria,
        concepto=propuesta.concepto,
        tipo_ingreso=propuesta.tipo_ingreso,
        es_extraordinario=propuesta.es_extraordinario,
        metodo_pago=propuesta.metodo_pago,
        cuenta=propuesta.cuenta,
        cuenta_destino=propuesta.cuenta_destino,
        persona=propuesta.persona,
        domicilio=propuesta.domicilio,
        es_hormiga=propuesta.es_hormiga,
        origen=Movimiento.Origen.IMPORTADO,
        documento=propuesta.documento,
    )


def recordar_clasificacion(propuesta):
    """IMP-09: «recordar esta clasificación» crea o actualiza una regla del hogar."""
    patron = patron_sugerido(propuesta.descripcion_original)
    if not patron:
        return None
    regla, _ = ReglaClasificacion.objects.update_or_create(
        hogar=propuesta.hogar,
        patron=patron,
        emisor=propuesta.documento.emisor,
        defaults={
            "categoria": propuesta.categoria,
            "concepto": propuesta.concepto,
            "persona": propuesta.persona,
            "domicilio": propuesta.domicilio,
            "es_hormiga": propuesta.es_hormiga,
        },
    )
    return regla


def descartar_propuesta(propuesta):
    if propuesta.estado == ESTADO.PENDIENTE:
        propuesta.estado = ESTADO.DESCARTADO
        propuesta.error = ""
        propuesta.save(update_fields=["estado", "error", "actualizado_en"])
        actualizar_estado_documento(propuesta.documento)


def aceptar_no_duplicados(documento, usuario):
    """Acepta las pendientes que no parecen duplicadas; devuelve (aceptadas, con error)."""
    aceptadas = con_error = 0
    pendientes = documento.propuestas.filter(
        estado=ESTADO.PENDIENTE, posible_duplicado_de__isnull=True
    ).order_by("fecha", "id")
    for propuesta in pendientes:
        try:
            aceptar_propuesta(propuesta, usuario)
            aceptadas += 1
        except ValidationError:
            con_error += 1
    return aceptadas, con_error


def descartar_todas(documento):
    documento.propuestas.filter(estado=ESTADO.PENDIENTE).update(estado=ESTADO.DESCARTADO)
    actualizar_estado_documento(documento)


def actualizar_estado_documento(documento):
    estados = set(documento.propuestas.values_list("estado", flat=True))
    if not estados or ESTADO.PENDIENTE in estados:
        return
    documento.estado = (
        Documento.Estado.CONFIRMADO if ESTADO.ACEPTADO in estados else Documento.Estado.DESCARTADO
    )
    documento.save(update_fields=["estado", "actualizado_en"])


def actualizar_saldo(documento):
    """IMP-12: usa el saldo al corte del estado de cuenta como saldo actual de la cuenta."""
    if documento.cuenta is None or documento.saldo_al_corte is None:
        return False
    cuenta = documento.cuenta
    cuenta.saldo_actual = documento.saldo_al_corte
    cuenta.fecha_saldo = documento.periodo_fin or timezone.localdate()
    cuenta.save(update_fields=["saldo_actual", "fecha_saldo", "actualizado_en"])
    return True
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_revision.py` 12 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion/servicios.py tests/importacion/test_imp_revision.py
git commit -m "feat(importacion): aceptar, descartar y recordar propuestas; actualizar saldo al corte" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Pantalla Importar (P10), revisión de solo lectura y navegación

**Files:**
- Create: `apps/importacion/formularios.py`, `apps/importacion/vistas.py`, `apps/importacion/urls.py`
- Create: `templates/importacion/importar.html`, `templates/importacion/_documentos.html`, `templates/importacion/revisar.html`
- Modify: `finanzas/urls.py`, `templates/componentes/navegacion.html`, `templates/catalogos/indice.html`
- Test: `tests/importacion/test_imp_vistas_importar.py`

**Interfaces:**
- Consumes: `registrar_archivos`, `costo_del_mes`, `reintentar`, `eliminar_documento` (Task 7); `Documento`, `MovimientoPropuesto` (Task 2); `requiere_hogar`, `redondear`.
- Produces:
  - `apps.importacion.formularios.FormularioSubida(data, files, hogar=)` con `archivos` (lista de archivos subidos) y `cuenta` (opcional, cuentas activas del hogar).
  - Rutas (app `importacion`, prefijo `/importar/`): `importacion:importar` (GET/POST), `importacion:documentos` (lista parcial con sondeo), `importacion:revisar` (`<pk>/`), `importacion:original` (`<pk>/original/`), `importacion:reintentar` (POST), `importacion:eliminar` (POST).
  - Helpers en `vistas.py`: `_documento(request, pk)` y `_propuestas(documento) -> (pendientes, revisadas)`, que la Task 11 reutiliza.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_vistas_importar.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalogos.models import Cuenta
from apps.importacion import servicios
from apps.importacion.archivos import huella
from apps.importacion.models import Documento, MovimientoPropuesto
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db


@pytest.fixture
def encolados(monkeypatch):
    lista = []
    monkeypatch.setattr(
        servicios, "async_task", lambda funcion, documento_id: lista.append(documento_id)
    )
    return lista


def pdf_subido(crear_pdf, nombre="estado.pdf", texto="Estado de cuenta"):
    return SimpleUploadedFile(nombre, crear_pdf(texto), content_type="application/pdf")


def documento_con_pdf(hogar, crear_pdf, **campos):
    datos = crear_pdf("Estado de cuenta Banco Demo")
    documento = Documento(hogar=hogar, nombre_original="estado.pdf", sha256=huella(datos), **campos)
    documento.archivo.save("x.pdf", ContentFile(datos), save=False)
    documento.save()
    return documento, datos


def test_pantalla_importar(cliente, hogar):
    Documento.objects.create(
        hogar=hogar, nombre_original="viejo.pdf", sha256="a" * 64, costo_estimado_usd=D("0.0800")
    )

    contenido = cliente.get("/importar/").content.decode()

    assert "Importar documentos" in contenido
    assert "US$0.08" in contenido
    assert "viejo.pdf" in contenido


def test_subir_un_pdf(cliente, crear_pdf, encolados):
    respuesta = cliente.post("/importar/", {"archivos": pdf_subido(crear_pdf)}, follow=True)

    assert Documento.objects.count() == 1
    assert len(encolados) == 1
    assert "Se subieron 1 documento(s)" in respuesta.content.decode()


def test_subir_varios_archivos(cliente, crear_pdf, encolados):
    archivos = [pdf_subido(crear_pdf, "a.pdf", "Uno"), pdf_subido(crear_pdf, "b.pdf", "Dos")]

    cliente.post("/importar/", {"archivos": archivos})

    assert Documento.objects.count() == 2


def test_subir_un_duplicado_muestra_el_motivo(cliente, crear_pdf, encolados):
    cliente.post("/importar/", {"archivos": pdf_subido(crear_pdf)})

    respuesta = cliente.post("/importar/", {"archivos": pdf_subido(crear_pdf)}, follow=True)

    assert "ya se importó" in respuesta.content.decode()
    assert Documento.objects.count() == 1


def test_cuenta_de_otro_hogar_es_error(cliente, otro_hogar, crear_pdf, encolados):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.CREDITO)

    respuesta = cliente.post(
        "/importar/", {"archivos": pdf_subido(crear_pdf), "cuenta": ajena.pk}
    )

    assert respuesta.status_code == 200
    assert "cuenta" in respuesta.context["formulario"].errors
    assert not Documento.objects.exists()


def test_la_lista_se_actualiza_mientras_hay_documentos_en_proceso(cliente, hogar):
    documento = Documento.objects.create(hogar=hogar, nombre_original="a.pdf", sha256="a" * 64)

    assert 'hx-trigger="every 3s"' in cliente.get("/importar/documentos/").content.decode()

    Documento.objects.filter(pk=documento.pk).update(estado=Documento.Estado.POR_REVISAR)
    assert 'hx-trigger="every 3s"' not in cliente.get("/importar/documentos/").content.decode()


def test_ver_el_pdf_original(cliente, hogar, crear_pdf):
    documento, datos = documento_con_pdf(hogar, crear_pdf)

    respuesta = cliente.get(f"/importar/{documento.pk}/original/")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"
    assert b"".join(respuesta.streaming_content) == datos


def test_pdf_de_otro_hogar_da_404(cliente, otro_hogar, crear_pdf):
    ajeno, _ = documento_con_pdf(otro_hogar, crear_pdf)

    assert cliente.get(f"/importar/{ajeno.pk}/original/").status_code == 404


def test_los_pdfs_no_tienen_url_publica(cliente, hogar, crear_pdf):
    documento, _ = documento_con_pdf(hogar, crear_pdf)

    assert cliente.get(f"/media/{documento.archivo.name}").status_code == 404


def test_reintentar_un_documento_con_error(cliente, hogar, encolados):
    documento = Documento.objects.create(
        hogar=hogar, nombre_original="a.pdf", sha256="a" * 64,
        estado=Documento.Estado.ERROR, error="Falla",
    )  # fmt: skip

    cliente.post(f"/importar/{documento.pk}/reintentar/")

    documento.refresh_from_db()
    assert (documento.estado, documento.error) == (Documento.Estado.SUBIDO, "")
    assert encolados == [documento.pk]


def test_reintentar_no_aplica_a_documentos_procesados(cliente, hogar, encolados):
    documento = Documento.objects.create(
        hogar=hogar, nombre_original="a.pdf", sha256="a" * 64, estado=Documento.Estado.POR_REVISAR
    )

    cliente.post(f"/importar/{documento.pk}/reintentar/")

    documento.refresh_from_db()
    assert (documento.estado, encolados) == (Documento.Estado.POR_REVISAR, [])


def test_eliminar_conserva_los_movimientos(cliente, catalogo, hogar, crear_pdf):
    documento, _ = documento_con_pdf(hogar, crear_pdf)
    nombre = documento.archivo.name
    movimiento = guardar_movimiento(
        Movimiento(
            hogar=hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("10"),
            concepto=catalogo.gasolina,
            origen=Movimiento.Origen.IMPORTADO,
            documento=documento,
        )
    )

    cliente.post(f"/importar/{documento.pk}/eliminar/")

    assert not Documento.objects.exists()
    assert not default_storage.exists(nombre)
    movimiento.refresh_from_db()
    assert movimiento.documento is None


def test_pantalla_revisar_lista_las_propuestas(cliente, catalogo, hogar):
    documento = Documento.objects.create(
        hogar=hogar, nombre_original="estado.pdf", sha256="a" * 64,
        estado=Documento.Estado.POR_REVISAR,
    )  # fmt: skip
    MovimientoPropuesto.objects.create(
        hogar=hogar,
        documento=documento,
        fecha=date(2026, 9, 10),
        descripcion_original="OXXO SUC 1234",
        descripcion="OXXO SUC 1234",
        monto=D("85.50"),
        tipo=Movimiento.Tipo.GASTO,
    )

    contenido = cliente.get(f"/importar/{documento.pk}/").content.decode()

    assert "OXXO SUC 1234" in contenido
    assert "$85.50" in contenido


def test_documento_de_otro_hogar_da_404(cliente, otro_hogar):
    ajeno = Documento.objects.create(hogar=otro_hogar, nombre_original="a.pdf", sha256="a" * 64)

    assert cliente.get(f"/importar/{ajeno.pk}/").status_code == 404
    assert cliente.post(f"/importar/{ajeno.pk}/eliminar/").status_code == 404
    assert Documento.objects.filter(pk=ajeno.pk).exists()


def test_navegacion_con_importar(cliente):
    contenido = cliente.get("/catalogos/").content.decode()

    assert "/importar/" in contenido
    assert "Presupuesto del mes" in contenido
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_vistas_importar.py -v`
Expected: FAIL con 404 en `/importar/...`.

- [ ] **Step 3: Formulario, vistas y URLs**

`apps/importacion/formularios.py`:
```python
from django import forms

from apps.catalogos.models import Cuenta


class EntradaDeVariosArchivos(forms.ClearableFileInput):
    allow_multiple_selected = True


class CampoDeVariosArchivos(forms.FileField):
    """Acepta uno o varios archivos y siempre devuelve una lista."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            EntradaDeVariosArchivos(attrs={"accept": ".pdf,.zip,application/pdf,application/zip"}),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpiar = super().clean
        if isinstance(data, (list, tuple)):
            return [limpiar(archivo, initial) for archivo in data]
        return [limpiar(data, initial)]


class FormularioSubida(forms.Form):
    archivos = CampoDeVariosArchivos(
        label="Archivos PDF o ZIP", help_text="Hasta 20 archivos de 20 MB cada uno."
    )
    cuenta = forms.ModelChoiceField(
        Cuenta.objects.none(),
        required=False,
        label="Cuenta (opcional)",
        help_text="Para estados de cuenta; si no la eliges, se busca por los últimos 4 dígitos.",
    )

    def __init__(self, *args, hogar, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cuenta"].queryset = Cuenta.objects.del_hogar(hogar).filter(activo=True)
```

`apps/importacion/vistas.py`:
```python
"""Pantallas de importación (P10) y revisión de documentos (P11)."""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.calculos.comun import redondear
from apps.core.acceso import requiere_hogar
from apps.importacion import servicios
from apps.importacion.formularios import FormularioSubida
from apps.importacion.models import Documento, MovimientoPropuesto

PENDIENTE = MovimientoPropuesto.Estado.PENDIENTE


def _lista(hogar):
    documentos = list(
        Documento.objects.del_hogar(hogar)
        .annotate(pendientes=Count("propuestas", filter=Q(propuestas__estado=PENDIENTE)))
        .order_by("-creado_en")[:50]
    )
    en_curso = any(d.estado in Documento.ESTADOS_EN_CURSO for d in documentos)
    return {"documentos": documentos, "hay_pendientes": en_curso}


def _documento(request, pk):
    return get_object_or_404(Documento.objects.del_hogar(request.hogar), pk=pk)


def _propuestas(documento):
    propuestas = documento.propuestas.select_related(
        "categoria", "concepto__categoria", "persona", "domicilio", "cuenta", "cuenta_destino",
        "posible_duplicado_de", "regla",
    )  # fmt: skip
    pendientes = [p for p in propuestas if p.estado == PENDIENTE]
    revisadas = [p for p in propuestas if p.estado != PENDIENTE]
    return pendientes, revisadas


@requiere_hogar
def importar(request):
    if request.method == "POST":
        formulario = FormularioSubida(request.POST, request.FILES, hogar=request.hogar)
        if formulario.is_valid():
            documentos, rechazos = servicios.registrar_archivos(
                request.hogar,
                request.user,
                formulario.cleaned_data["archivos"],
                cuenta=formulario.cleaned_data["cuenta"],
            )
            if documentos:
                messages.success(
                    request, f"Se subieron {len(documentos)} documento(s); se están procesando."
                )
            for rechazo in rechazos:
                messages.error(request, f"{rechazo.nombre}: {rechazo.motivo}.")
            return redirect("importacion:importar")
    else:
        formulario = FormularioSubida(hogar=request.hogar)
    contexto = {
        "formulario": formulario,
        "costo_mes": f"{redondear(servicios.costo_del_mes(request.hogar))}",
        **_lista(request.hogar),
    }
    return render(request, "importacion/importar.html", contexto)


@requiere_hogar
def documentos(request):
    return render(request, "importacion/_documentos.html", _lista(request.hogar))


@requiere_hogar
def revisar(request, pk):
    documento = _documento(request, pk)
    pendientes, revisadas = _propuestas(documento)
    contexto = {"documento": documento, "pendientes": pendientes, "revisadas": revisadas}
    return render(request, "importacion/revisar.html", contexto)


@requiere_hogar
def original(request, pk):
    """IMP-14: el PDF solo se sirve a su hogar (no hay URL pública de media)."""
    documento = _documento(request, pk)
    try:
        archivo = documento.archivo.open("rb")
    except (FileNotFoundError, ValueError) as error:
        raise Http404 from error
    return FileResponse(archivo, content_type="application/pdf", filename=documento.nombre_original)


@requiere_hogar
@require_POST
def reintentar(request, pk):
    documento = _documento(request, pk)
    if documento.estado == Documento.Estado.ERROR:
        servicios.reintentar(documento)
        messages.success(request, "El documento se volverá a procesar.")
    return redirect("importacion:importar")


@requiere_hogar
@require_POST
def eliminar(request, pk):
    servicios.eliminar_documento(_documento(request, pk))
    messages.success(request, "Se eliminó el documento; los movimientos aceptados se conservan.")
    return redirect("importacion:importar")
```

`apps/importacion/urls.py`:
```python
from django.urls import path

from apps.importacion import vistas

app_name = "importacion"

urlpatterns = [
    path("", vistas.importar, name="importar"),
    path("documentos/", vistas.documentos, name="documentos"),
    path("<int:pk>/", vistas.revisar, name="revisar"),
    path("<int:pk>/original/", vistas.original, name="original"),
    path("<int:pk>/reintentar/", vistas.reintentar, name="reintentar"),
    path("<int:pk>/eliminar/", vistas.eliminar, name="eliminar"),
]
```

En `finanzas/urls.py`, antes de `path("", include("apps.core.urls")),`:
```python
    path("importar/", include("apps.importacion.urls")),
```

- [ ] **Step 4: Plantillas y navegación**

`templates/importacion/importar.html`:
```html
{% extends "base.html" %}
{% block titulo %}Importar{% endblock %}
{% block contenido %}
<h1 class="mb-1 text-lg font-semibold">Importar documentos</h1>
<p class="mb-4 text-sm text-slate-600">Sube estados de cuenta, recibos de nómina o recibos de luz, agua e internet en PDF (o un ZIP con PDFs). La IA propone los movimientos y tú los revisas antes de guardarlos.</p>

<form method="post" enctype="multipart/form-data" class="tarjeta mb-4 space-y-3">
  {% csrf_token %}
  {% if formulario.non_field_errors %}<div class="rounded bg-red-50 p-2 text-sm text-red-700">{{ formulario.non_field_errors }}</div>{% endif %}
  {% for campo in formulario %}{% include "componentes/campo.html" %}{% endfor %}
  <button class="boton w-full sm:w-auto">Subir y procesar</button>
  <p class="text-xs text-slate-500">A la IA solo se envía el texto del documento, con RFC, CURP y números de cuenta ocultos. Costo de IA este mes: <strong>US${{ costo_mes }}</strong></p>
</form>

{% include "importacion/_documentos.html" %}
{% endblock %}
```

`templates/importacion/_documentos.html`:
```html
<section id="documentos" class="space-y-2" {% if hay_pendientes %}hx-get="{% url 'importacion:documentos' %}" hx-trigger="every 3s" hx-swap="outerHTML"{% endif %}>
  {% for documento in documentos %}
    <article class="tarjeta flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="truncate font-medium">{{ documento.nombre_original }}</p>
        <p class="text-xs text-slate-500">{{ documento.creado_en|date:"d M Y H:i" }}{% if documento.tipo %} · {{ documento.get_tipo_display }}{% endif %}{% if documento.emisor %} · {{ documento.emisor }}{% endif %}{% if documento.periodo_fin %} · al {{ documento.periodo_fin|date:"d M Y" }}{% endif %}{% if documento.costo_estimado_usd is not None %} · US${{ documento.costo_estimado_usd }}{% endif %}</p>
        {% if documento.error %}<p class="text-xs text-red-600">{{ documento.error }}</p>{% endif %}
        {% if documento.aviso %}<p class="text-xs text-amber-700">{{ documento.aviso }}</p>{% endif %}
      </div>
      <div class="flex shrink-0 flex-col items-end gap-1 text-xs">
        <span class="rounded-full px-2 py-0.5 {% if documento.estado == 'error' %}bg-red-100 text-red-700{% elif documento.estado == 'por_revisar' %}bg-amber-100 text-amber-800{% elif documento.estado == 'confirmado' %}bg-emerald-100 text-emerald-800{% else %}bg-slate-100 text-slate-600{% endif %}">{{ documento.get_estado_display }}{% if documento.pendientes %} · {{ documento.pendientes }} por revisar{% endif %}</span>
        {% if documento.estado == 'por_revisar' or documento.estado == 'confirmado' or documento.estado == 'descartado' %}<a class="text-sky-700" href="{% url 'importacion:revisar' documento.pk %}">Revisar</a>{% endif %}
        {% if documento.estado == 'error' %}<form method="post" action="{% url 'importacion:reintentar' documento.pk %}">{% csrf_token %}<button class="text-sky-700">Reintentar</button></form>{% endif %}
        <a class="text-sky-700" href="{% url 'importacion:original' documento.pk %}" target="_blank" rel="noopener">Ver PDF</a>
        <form method="post" action="{% url 'importacion:eliminar' documento.pk %}" onsubmit="return confirm('¿Eliminar este documento? Los movimientos ya aceptados se conservan.')">{% csrf_token %}<button class="text-red-600">Eliminar</button></form>
      </div>
    </article>
  {% empty %}
    <p class="tarjeta text-slate-500">Aún no has importado documentos.</p>
  {% endfor %}
</section>
```

`templates/importacion/revisar.html` (solo lectura; la Task 11 la reemplaza por la versión con acciones):
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Revisar {{ documento }}{% endblock %}
{% block contenido %}
<h1 class="mb-1 text-lg font-semibold"><a class="text-slate-400" href="{% url 'importacion:importar' %}">Importar ›</a> {{ documento.nombre_original }}</h1>
<p class="mb-4 text-sm text-slate-600">{{ documento.get_tipo_display|default:"Documento" }}{% if documento.emisor %} de {{ documento.emisor }}{% endif %}{% if documento.periodo_inicio and documento.periodo_fin %} · del {{ documento.periodo_inicio|date:"d M" }} al {{ documento.periodo_fin|date:"d M Y" }}{% endif %}{% if documento.cuenta %} · cuenta {{ documento.cuenta }}{% endif %} · <a class="text-sky-700" href="{% url 'importacion:original' documento.pk %}" target="_blank" rel="noopener">ver PDF</a></p>
{% if documento.aviso %}<p class="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{{ documento.aviso }}</p>{% endif %}

<section class="space-y-2">
  {% for p in pendientes %}
    <article class="tarjeta flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="font-medium">{{ p.descripcion }}</p>
        <p class="text-xs text-slate-500">{{ p.fecha|date:"d M Y" }} · {{ p.get_tipo_display }} · {% if p.concepto %}{{ p.concepto.nombre_con_categoria }}{% elif p.categoria %}{{ p.categoria }}{% else %}Sin categoría{% endif %}</p>
      </div>
      <p class="shrink-0 font-semibold">{{ p.monto|dinero }}</p>
    </article>
  {% empty %}
    <p class="tarjeta text-slate-500">No hay propuestas pendientes.</p>
  {% endfor %}
</section>
{% endblock %}
```

`templates/componentes/navegacion.html`: reemplazar el enlace de Presupuesto por estos dos (Importar visible siempre; Presupuesto solo en la barra lateral de computadora):
```html
  <a href="{% url 'importacion:importar' %}" class="flex flex-col items-center rounded-lg px-2 py-1 md:flex-row md:gap-2 hover:bg-slate-100"><span>📥</span><span>Importar</span></a>
  <a href="{% url 'presupuesto:inicio' %}" class="hidden flex-col items-center rounded-lg px-2 py-1 md:flex md:flex-row md:gap-2 hover:bg-slate-100"><span>🧮</span><span>Presupuesto</span></a>
```

En `templates/catalogos/indice.html`, en la última sección, antes del enlace "Plantilla de presupuesto":
```html
  <a class="block text-sky-700" href="{% url 'presupuesto:inicio' %}">🧮 Presupuesto del mes</a>
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_vistas_importar.py` 15 passed; todo verde.

Run: `docker compose run --rm css`
Expected: recompila `static/css/app.css` con las clases nuevas.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion finanzas/urls.py templates tests/importacion/test_imp_vistas_importar.py
git commit -m "feat(importacion): pantalla para subir documentos, lista con estado y costo, PDF original y navegacion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Acciones de la pantalla de revisión (P11)

**Files:**
- Modify: `apps/importacion/formularios.py`, `apps/importacion/vistas.py`, `apps/importacion/urls.py`
- Modify (reemplazar completa): `templates/importacion/revisar.html`
- Test: `tests/importacion/test_imp_vistas_revisar.py`

**Interfaces:**
- Consumes: `aceptar_propuesta`, `descartar_propuesta`, `aceptar_no_duplicados`, `descartar_todas`, `actualizar_saldo` (Task 9); `_documento`, `_propuestas` (Task 10); `FormularioDeHogar`, `responder_formulario`, `datos_actualizados`, `es_htmx`.
- Produces: `FormularioPropuesta`; rutas `importacion:editar` (`propuesta/<pk>/`), `importacion:aceptar` (`propuesta/<pk>/aceptar/`, POST, campo `recordar`), `importacion:descartar` (POST), `importacion:aceptar_todo` (`<pk>/aceptar-todo/`, POST), `importacion:descartar_todo` (POST), `importacion:saldo` (`<pk>/saldo/`, POST).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/importacion/test_imp_vistas_revisar.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria
from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


@pytest.fixture
def documento(hogar):
    return Documento.objects.create(
        hogar=hogar,
        nombre_original="estado.pdf",
        sha256="a" * 64,
        emisor="Banco Demo",
        estado=Documento.Estado.POR_REVISAR,
    )


def propuesta(catalogo, documento, **campos):
    datos = {
        "hogar": documento.hogar,
        "documento": documento,
        "fecha": date(2026, 9, 10),
        "descripcion_original": "OXXO SUC 1234",
        "descripcion": "OXXO SUC 1234",
        "monto": D("85.50"),
        "tipo": Movimiento.Tipo.GASTO,
        "categoria": catalogo.categorias["Comida"],
        "cuenta": catalogo.nomina,
        "metodo_pago": MetodoPago.TARJETA_DEBITO,
    }
    datos.update(campos)
    return MovimientoPropuesto.objects.create(**datos)


def datos_edicion(catalogo, **campos):
    datos = {
        "fecha": "2026-09-10",
        "descripcion": "Gasolina",
        "monto": "85.50",
        "tipo": "gasto",
        "metodo_pago": "tarjeta_debito",
        "concepto": catalogo.gasolina.pk,
        "cuenta": catalogo.nomina.pk,
    }
    datos.update(campos)
    return datos


def test_editar_una_propuesta(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)

    respuesta = cliente.post(
        f"/importar/propuesta/{pendiente.pk}/", datos_edicion(catalogo), headers=HTMX
    )

    assert respuesta.status_code == 204
    pendiente.refresh_from_db()
    assert (pendiente.concepto, pendiente.descripcion) == (catalogo.gasolina, "Gasolina")


def test_editar_con_categoria_de_otro_hogar_es_error(cliente, catalogo, documento, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Ajena")
    pendiente = propuesta(catalogo, documento)

    respuesta = cliente.post(
        f"/importar/propuesta/{pendiente.pk}/",
        datos_edicion(catalogo, concepto="", categoria=ajena.pk),
        headers=HTMX,
    )

    assert respuesta.status_code == 200
    assert "categoria" in respuesta.context["formulario"].errors


def test_aceptar_y_recordar(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)

    respuesta = cliente.post(
        f"/importar/propuesta/{pendiente.pk}/aceptar/", {"recordar": "on"}, headers=HTMX
    )

    assert respuesta.status_code == 204
    assert Movimiento.objects.get().origen == Movimiento.Origen.IMPORTADO
    assert ReglaClasificacion.objects.get().patron == "oxxo suc"


def test_aceptar_una_propuesta_invalida_muestra_el_error(cliente, catalogo, documento):
    incompleta = propuesta(catalogo, documento, categoria=None)

    cliente.post(f"/importar/propuesta/{incompleta.pk}/aceptar/", headers=HTMX)

    assert not Movimiento.objects.exists()
    contenido = cliente.get(f"/importar/{documento.pk}/").content.decode()
    assert "No se pudo aceptar" in contenido


def test_descartar(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)

    cliente.post(f"/importar/propuesta/{pendiente.pk}/descartar/", headers=HTMX)

    pendiente.refresh_from_db()
    assert pendiente.estado == MovimientoPropuesto.Estado.DESCARTADO


def test_aceptar_todo_lo_no_duplicado(cliente, catalogo, documento):
    existente = guardar_movimiento(
        Movimiento(
            hogar=documento.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("999"),
            concepto=catalogo.gasolina,
            fecha=date(2026, 9, 10),
        )
    )
    propuesta(catalogo, documento)
    duplicada = propuesta(catalogo, documento, monto=D("999"), posible_duplicado_de=existente)

    cliente.post(f"/importar/{documento.pk}/aceptar-todo/", headers=HTMX)

    duplicada.refresh_from_db()
    assert duplicada.estado == MovimientoPropuesto.Estado.PENDIENTE
    assert Movimiento.objects.count() == 2


def test_descartar_todo(cliente, catalogo, documento):
    propuesta(catalogo, documento)

    cliente.post(f"/importar/{documento.pk}/descartar-todo/", headers=HTMX)

    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.DESCARTADO


def test_actualizar_el_saldo_desde_la_pantalla(cliente, catalogo, documento):
    documento.cuenta = catalogo.tarjeta
    documento.saldo_al_corte = D("7000.00")
    documento.periodo_fin = date(2026, 10, 5)
    documento.save()

    respuesta = cliente.post(f"/importar/{documento.pk}/saldo/")

    assert respuesta.status_code == 302
    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("7000.00")


def test_propuesta_de_otro_hogar_da_404(cliente, catalogo, otro_hogar):
    documento_ajeno = Documento.objects.create(
        hogar=otro_hogar, nombre_original="a.pdf", sha256="b" * 64
    )
    ajena = MovimientoPropuesto.objects.create(
        hogar=otro_hogar,
        documento=documento_ajeno,
        fecha=date(2026, 9, 10),
        descripcion_original="X",
        descripcion="X",
        monto=D("1"),
        tipo=Movimiento.Tipo.GASTO,
    )

    assert cliente.get(f"/importar/propuesta/{ajena.pk}/").status_code == 404
    assert cliente.post(f"/importar/propuesta/{ajena.pk}/aceptar/").status_code == 404
    assert cliente.post(f"/importar/{documento_ajeno.pk}/aceptar-todo/").status_code == 404


def test_una_propuesta_aceptada_ya_no_se_edita(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)
    cliente.post(f"/importar/propuesta/{pendiente.pk}/aceptar/", headers=HTMX)

    assert cliente.get(f"/importar/propuesta/{pendiente.pk}/", headers=HTMX).status_code == 404


def test_la_pantalla_muestra_duplicados_y_acciones(cliente, catalogo, documento):
    existente = guardar_movimiento(
        Movimiento(
            hogar=documento.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("85.50"),
            concepto=catalogo.gasolina,
            fecha=date(2026, 9, 10),
        )
    )
    propuesta(catalogo, documento, posible_duplicado_de=existente)

    contenido = cliente.get(f"/importar/{documento.pk}/").content.decode()

    for texto in ("Posible duplicado", "Aceptar todo lo no duplicado", "Recordar clasificación"):
        assert texto in contenido
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_vistas_revisar.py -v`
Expected: FAIL con 404 en `/importar/propuesta/...` y en las acciones nuevas.

- [ ] **Step 3: Formulario, vistas y URLs**

En `apps/importacion/formularios.py`, agregar a los imports:
```python
from apps.core.formularios import FormularioDeHogar
from apps.importacion.models import MovimientoPropuesto
```
y al final:
```python
class FormularioPropuesta(FormularioDeHogar):
    class Meta:
        model = MovimientoPropuesto
        fields = [
            "fecha", "descripcion", "monto", "tipo", "tipo_ingreso", "es_extraordinario",
            "metodo_pago", "concepto", "categoria", "cuenta", "cuenta_destino", "persona",
            "domicilio", "es_hormiga",
        ]  # fmt: skip
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        concepto = self.fields["concepto"]
        concepto.queryset = concepto.queryset.select_related("categoria")
        concepto.label_from_instance = lambda c: c.nombre_con_categoria
```

En `apps/importacion/vistas.py`, agregar a los imports:
```python
from django.core.exceptions import ValidationError

from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.importacion.formularios import FormularioPropuesta, FormularioSubida
```
(reemplaza el import anterior de `FormularioSubida`) y al final:
```python
def _propuesta(request, pk):
    consulta = MovimientoPropuesto.objects.del_hogar(request.hogar).select_related("documento")
    return get_object_or_404(consulta, pk=pk)


def _volver(request, documento):
    if es_htmx(request):
        return datos_actualizados()
    return redirect("importacion:revisar", documento.pk)


@requiere_hogar
def propuesta_editar(request, pk):
    propuesta = _propuesta(request, pk)
    if propuesta.estado != PENDIENTE:
        raise Http404("La propuesta ya se revisó.")
    datos = request.POST if request.method == "POST" else None
    formulario = FormularioPropuesta(datos, instance=propuesta, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        formulario.save()
        return _volver(request, propuesta.documento)
    contexto = {"formulario": formulario, "titulo": "Editar propuesta", "accion": request.path}
    return responder_formulario(request, contexto)


@requiere_hogar
@require_POST
def propuesta_aceptar(request, pk):
    propuesta = _propuesta(request, pk)
    try:
        servicios.aceptar_propuesta(
            propuesta, request.user, recordar=request.POST.get("recordar") == "on"
        )
    except ValidationError:
        messages.error(request, "No se pudo aceptar la propuesta; revisa el mensaje en rojo.")
    return _volver(request, propuesta.documento)


@requiere_hogar
@require_POST
def propuesta_descartar(request, pk):
    propuesta = _propuesta(request, pk)
    servicios.descartar_propuesta(propuesta)
    return _volver(request, propuesta.documento)


@requiere_hogar
@require_POST
def aceptar_todo(request, pk):
    documento = _documento(request, pk)
    aceptadas, con_error = servicios.aceptar_no_duplicados(documento, request.user)
    messages.success(request, f"Se aceptaron {aceptadas} propuesta(s).")
    if con_error:
        messages.error(request, f"{con_error} propuesta(s) necesitan corrección.")
    return _volver(request, documento)


@requiere_hogar
@require_POST
def descartar_todo(request, pk):
    documento = _documento(request, pk)
    servicios.descartar_todas(documento)
    return _volver(request, documento)


@requiere_hogar
@require_POST
def actualizar_saldo(request, pk):
    documento = _documento(request, pk)
    if servicios.actualizar_saldo(documento):
        messages.success(request, f"Se actualizó el saldo de {documento.cuenta}.")
    return redirect("importacion:revisar", documento.pk)
```

En `apps/importacion/urls.py`, agregar a `urlpatterns`:
```python
    path("<int:pk>/aceptar-todo/", vistas.aceptar_todo, name="aceptar_todo"),
    path("<int:pk>/descartar-todo/", vistas.descartar_todo, name="descartar_todo"),
    path("<int:pk>/saldo/", vistas.actualizar_saldo, name="saldo"),
    path("propuesta/<int:pk>/", vistas.propuesta_editar, name="editar"),
    path("propuesta/<int:pk>/aceptar/", vistas.propuesta_aceptar, name="aceptar"),
    path("propuesta/<int:pk>/descartar/", vistas.propuesta_descartar, name="descartar"),
```

- [ ] **Step 4: Plantilla con acciones**

Reemplazar `templates/importacion/revisar.html` completo por:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Revisar {{ documento }}{% endblock %}
{% block contenido %}
<h1 class="mb-1 text-lg font-semibold"><a class="text-slate-400" href="{% url 'importacion:importar' %}">Importar ›</a> {{ documento.nombre_original }}</h1>
<p class="mb-4 text-sm text-slate-600">{{ documento.get_tipo_display|default:"Documento" }}{% if documento.emisor %} de {{ documento.emisor }}{% endif %}{% if documento.periodo_inicio and documento.periodo_fin %} · del {{ documento.periodo_inicio|date:"d M" }} al {{ documento.periodo_fin|date:"d M Y" }}{% endif %}{% if documento.cuenta %} · cuenta {{ documento.cuenta }}{% endif %}{% if documento.paginas %} · {{ documento.paginas }} pág.{% endif %} · <a class="text-sky-700" href="{% url 'importacion:original' documento.pk %}" target="_blank" rel="noopener">ver PDF</a></p>
{% if documento.aviso %}<p class="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{{ documento.aviso }}</p>{% endif %}

{% if documento.saldo_al_corte is not None and documento.cuenta %}
  <form method="post" action="{% url 'importacion:saldo' documento.pk %}" class="tarjeta mb-4 flex flex-wrap items-center justify-between gap-2 text-sm">
    {% csrf_token %}
    <span>Saldo al corte: <strong>{{ documento.saldo_al_corte|dinero }}</strong> · registrado en {{ documento.cuenta }}: {{ documento.cuenta.saldo_actual|dinero }}</span>
    <button class="boton-secundario text-xs">Actualizar saldo de la cuenta</button>
  </form>
{% endif %}

{% if pendientes %}
  <div class="mb-3 flex flex-wrap gap-2">
    <button type="button" class="boton text-sm" hx-post="{% url 'importacion:aceptar_todo' documento.pk %}" hx-confirm="¿Aceptar todas las propuestas que no parecen duplicadas?">Aceptar todo lo no duplicado</button>
    <button type="button" class="boton-secundario text-sm" hx-post="{% url 'importacion:descartar_todo' documento.pk %}" hx-confirm="¿Descartar todas las propuestas pendientes?">Descartar todo</button>
  </div>
{% endif %}

<section class="space-y-2">
  {% for p in pendientes %}
    <article class="tarjeta {% if p.posible_duplicado_de %}ring-2 ring-amber-300{% endif %}">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="font-medium">{{ p.descripcion }}</p>
          <p class="text-xs text-slate-500">{{ p.fecha|date:"d M Y" }} · {{ p.get_tipo_display }}{% if p.tipo_ingreso %} ({{ p.get_tipo_ingreso_display }}){% endif %} · {{ p.get_metodo_pago_display }}{% if p.cuenta %} · {{ p.cuenta }}{% endif %}{% if p.cuenta_destino %} → {{ p.cuenta_destino }}{% endif %}</p>
          <p class="text-xs text-slate-500">{% if p.concepto %}{{ p.concepto.nombre_con_categoria }}{% elif p.categoria %}{{ p.categoria }}{% else %}Sin categoría{% endif %}{% if p.persona %} · {{ p.persona }}{% endif %}{% if p.domicilio %} · {{ p.domicilio }}{% endif %}{% if p.es_hormiga %} · 🐜{% endif %}{% if p.es_extraordinario %} · extra{% endif %}{% if p.regla %} · regla «{{ p.regla.patron }}»{% elif p.confianza is not None %} · confianza {{ p.confianza|porcentaje:0 }}{% endif %}</p>
          {% if p.posible_duplicado_de %}<p class="text-xs text-amber-700">⚠️ Posible duplicado de «{{ p.posible_duplicado_de.descripcion }}» del {{ p.posible_duplicado_de.fecha|date:"d M" }}</p>{% endif %}
          {% if p.error %}<p class="text-xs text-red-600">{{ p.error }}</p>{% endif %}
        </div>
        <p class="shrink-0 font-semibold">{{ p.monto|dinero }}</p>
      </div>
      <form class="mt-2 flex flex-wrap items-center justify-end gap-3 text-xs" hx-post="{% url 'importacion:aceptar' p.pk %}" hx-disabled-elt="find button[type=submit]">
        <label class="flex items-center gap-1"><input type="checkbox" name="recordar"> Recordar clasificación</label>
        <button type="button" class="text-sky-700" hx-get="{% url 'importacion:editar' p.pk %}" hx-target="#modal-contenido">Editar</button>
        <button type="button" class="text-red-600" hx-post="{% url 'importacion:descartar' p.pk %}">Descartar</button>
        <button type="submit" class="boton px-3 py-1 text-xs">Aceptar</button>
      </form>
    </article>
  {% empty %}
    <p class="tarjeta text-slate-500">No hay propuestas pendientes.</p>
  {% endfor %}
</section>

{% if revisadas %}
  <details class="tarjeta mt-4">
    <summary class="cursor-pointer text-sm font-medium">Revisadas ({{ revisadas|length }})</summary>
    <ul class="mt-2 divide-y divide-slate-100 text-sm">
      {% for p in revisadas %}
        <li class="flex justify-between gap-2 py-1"><span>{{ p.fecha|date:"d M" }} · {{ p.descripcion }}</span><span class="{% if p.estado == 'aceptado' %}text-emerald-700{% else %}text-slate-400 line-through{% endif %}">{{ p.monto|dinero }}</span></li>
      {% endfor %}
    </ul>
  </details>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_imp_vistas_revisar.py` 11 passed; `test_imp_vistas_importar.py` sigue verde; todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check --no-cache .
git add apps/importacion templates/importacion tests/importacion/test_imp_vistas_revisar.py
git commit -m "feat(importacion): revisar propuestas: editar, aceptar con recordar, descartar, acciones masivas y saldo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Cierre: documentación, verificación, humo con el worker real y prueba con IA

**Files:**
- Modify: `README.md`
- Modify (fuera del repo): `..\CLAUDE.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: README con la importación; suite, lint, migraciones e imagen verificados; flujo completo probado con el worker real.

- [ ] **Step 1: README**

En `README.md`, después de la sección "Primer uso", agregar:
```markdown
## Importar documentos con IA

1. Crea una clave en https://platform.claude.com y ponla en `.env`: `ANTHROPIC_API_KEY=sk-ant-...`.
2. Reinicia los servicios para que la lean: `docker compose up -d --force-recreate web worker`.
3. En la app: **Importar** → sube PDFs (o un ZIP) → espera a que el estado diga «Por revisar» → **Revisar** → acepta, edita o descarta cada propuesta.

- Solo se envía a la IA el **texto** del documento, con RFC, CURP y números de cuenta ocultos (quedan los últimos 4 dígitos).
- Un estado de cuenta típico cuesta unos centavos de dólar; el costo del mes aparece en la pantalla Importar.
- El contenedor `worker` procesa los documentos. Si cambias código de importación: `docker compose restart worker`.
- Un PDF escaneado (sin texto) queda en error: la v1 no tiene OCR.
```

- [ ] **Step 2: Verificación completa**

```powershell
docker compose build
docker compose run --rm css
docker compose run --rm web pytest --cov=apps --cov-report=term-missing
docker compose run --rm web ruff check --no-cache .
docker compose run --rm web ruff format --no-cache --check .
docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations --check --dry-run
sh tests/verificar_imagen.sh
```
Expected: `0 failed`; `apps/calculos` al 100 % y total ≥ 90 %; ruff sin errores; `No changes detected`; `OK: ningún archivo sensible entró a la imagen`.

- [ ] **Step 3: Prueba de humo con el worker real (sin clave de API)**

Requisito: `.env` **sin** `ANTHROPIC_API_KEY` (o con la línea vacía), para que no se llame a la IA. Con `docker compose up -d --force-recreate web worker` corriendo, guardar este script **fuera del repo** (por ejemplo `$env:TEMP\humo4.py`) y ejecutarlo:
```python
import importlib.util
import time

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.core.servicios import crear_hogar
from apps.importacion.models import Documento
from apps.importacion.servicios import eliminar_documento

spec = importlib.util.spec_from_file_location("conftest_pruebas", "/app/tests/conftest.py")
pruebas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pruebas)
pdf = pruebas._pdf_minimo(["Prueba de humo sin datos personales. Compra ficticia 10.00"])

Usuario = get_user_model()
usuario = Usuario.objects.create_user(email="humo4@example.com", password="humo-12345-x")
hogar = crear_hogar("Hogar de humo 4", usuario)
try:
    c = Client(HTTP_HOST="localhost")
    c.force_login(usuario)
    archivo = SimpleUploadedFile("humo.pdf", pdf, content_type="application/pdf")
    assert c.post("/importar/", {"archivos": archivo}).status_code == 302
    documento = Documento.objects.get(hogar=hogar)
    for _ in range(90):
        documento.refresh_from_db()
        if documento.estado not in Documento.ESTADOS_EN_CURSO:
            break
        time.sleep(1)
    print("ESTADO:", documento.estado, "|", documento.error)
    assert documento.estado == "error" and "ANTHROPIC_API_KEY" in documento.error
    assert c.get(f"/importar/{documento.pk}/original/").status_code == 200
    assert c.get("/importar/").status_code == 200
    print("HUMO 4 OK")
finally:
    for documento in Documento.objects.filter(hogar=hogar):
        eliminar_documento(documento)
    hogar.delete()
    usuario.delete()
```
Run:
```powershell
Get-Content $env:TEMP\humo4.py | docker compose exec -T web python manage.py shell
docker compose exec web python manage.py shell -c "from apps.core.models import Hogar; print(Hogar.objects.filter(nombre='Hogar de humo 4').count())"
```
Expected: `ESTADO: error | Falta configurar la clave de la API de Claude (ANTHROPIC_API_KEY)...`, luego `HUMO 4 OK` y `0`. Esto demuestra que el worker toma la tarea de la cola, lee el PDF y deja un error claro sin la clave.

- [ ] **Step 4: Commit y memoria del proyecto**

```powershell
git add README.md
git commit -m "docs: importacion de documentos con IA en el README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

En `..\CLAUDE.md` (fuera del repo), sección "Estado / siguiente paso": marcar el plan 4 como implementado (rama `plan-4-importacion-ia`) y poner como siguiente el plan 5 (PWA, Tailscale, respaldo, importación inicial desde Excel).

- [ ] **Step 5: Prueba real con la IA — SOLO con autorización explícita del usuario**

**Detenerse y pedir autorización antes de este paso**: cuesta dinero (centavos de dólar) y envía a Anthropic el texto protegido de un documento real. Con la autorización:
1. El usuario agrega `ANTHROPIC_API_KEY` a `.env` y se recrean los servicios: `docker compose up -d --force-recreate web worker`.
2. El usuario sube **un** recibo pequeño (por ejemplo, uno de luz) en la pantalla Importar.
3. Verificar sin imprimir datos personales:
```powershell
docker compose exec web python manage.py shell -c "from apps.importacion.models import Documento as D; d=D.objects.latest('creado_en'); print(d.estado, d.tipo, d.modelo_ia, d.tokens_entrada, d.tokens_salida, d.costo_estimado_usd, d.propuestas.count(), repr(d.error))"
```
Expected: estado `por_revisar`, tipo `recibo_servicio`, modelo `claude-opus-5-5` (o el modelo de respaldo), tokens y costo registrados (centavos), al menos 1 propuesta y `''` como error. El usuario revisa la propuesta en pantalla y la acepta o la descarta.
