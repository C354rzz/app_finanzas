# Plan 2 — Operación diaria: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Usar la app en el día a día sin el admin: iniciar sesión, registrar gastos, ingresos (incluidos aguinaldo y PTU), transferencias y pagos de deuda desde el celular, consultar y filtrar los movimientos del mes, editar el presupuesto (plantilla y mes), ver el tablero del mes con alertas y administrar los catálogos.

**Architecture:** Vistas Django que devuelven HTML; HTMX 2 hace las peticiones parciales (modal de captura, campos sugeridos, borrar). Tras guardar, el servidor responde `204` con el evento `datosActualizados` y el navegador recarga la vista. Los cálculos siguen en `apps/calculos` (Python puro); cada app nueva expone servicios (`servicios.py`, `consultas.py`) que las vistas solo componen. Tailwind v4 (binario standalone) compila el CSS dentro de Docker; no hay Node.

**Tech Stack:** Django 5.2, HTMX 2.0.11 (archivo local), Tailwind CSS v4.3.3 standalone, PostgreSQL 17, pytest-django.

**Spec:** `docs/DEF.md`, `docs/ARQUITECTURA.md`, `docs/modelo-datos.dbml` (v1.0, aprobados 2026-10-09).

### Hoja de ruta (este es el plan 2 de 5)
| Plan | Contenido |
|---|---|
| 1 — Fundación ✅ | Docker, CI, usuario, hogar, catálogos (admin), motor de cálculos |
| **2 — Operación diaria (este)** | Login y UI base, movimientos, presupuesto (plantilla y mes), tablero, catálogos en UI, ajuste del admin de Concepto |
| 3 — Planeación | Metas, deudas, patrimonio, simulador |
| 4 — Importación IA | Django-Q2, worker, pypdf, Claude API, reglas, duplicados, revisión |
| 5 — Operación | PWA (manifest + service worker), Tailscale, respaldo, importación inicial desde Excel |

Requisitos del DEF que cubre: ACC-01 (UI), CAT-01..05 (UI), MOV-01..07, PRE-01..05, TAB-01..04, TAB-05 (solo deudas), TAB-06, RN-01..04 y RN-08/09 aplicados, RN-13, RN-14, RN-15.

### Decisiones de este plan (para revisión del usuario)
1. **Concepto: "Valores sugeridos (opcional)".** Persona, cuenta y domicilio del concepto se agrupan bajo ese título y se etiquetan "… por defecto" (admin y UI). Solo cambian textos (Task 1).
2. **Sin Alpine.js ni Chart.js por ahora.** El modal usa `<dialog>` y unas líneas de JS; las barras por categoría son CSS. Se agregan si una pantalla lo necesita.
3. **PWA instalable (manifest, service worker) queda en el plan 5**, como dice la hoja de ruta. Este plan sí es mobile-first (360 px).
4. **Barra inferior en el celular:** Inicio · Movimientos · **+** · Presupuesto · Más. "Importar" entra en el plan 4.
5. **La descripción del movimiento es opcional:** si se deja vacía se usa el nombre del concepto (o el tipo de ingreso). Así un gasto se registra con monto + concepto + guardar (F2).
6. **Editar un movimiento abre el mismo modal de captura** (no una fila editable): funciona igual en el celular.
7. **RN-14 tal cual:** solo el pago de deuda modifica un saldo (baja el saldo de la tarjeta o préstamo destino); editarlo o borrarlo revierte el efecto. Los gastos con tarjeta no suben el saldo: lo actualiza el estado de cuenta (plan 4).
8. **Las tablas hijas del presupuesto llevan `hogar`** (el dbml no lo tenía): mismo aislamiento por hogar que todo lo demás.
9. **Gasto anual prorrateado se guarda a centavos** en el mes: 1,000 / 12 = 83.33.
10. **"% por categoría" y "gasto anual estimado" del tablero se calculan sobre el presupuesto**, como la hoja "Mis Finanzas".
11. **Filtros del tablero:** persona y domicilio filtran los gastos (presupuestados por el concepto, reales por el movimiento); los ingresos solo se filtran por persona (un domicilio no tiene ingresos). Con filtro activo no se muestran las alertas de disponible ni de meta.
12. **TAB-05:** el resumen de deudas sale de las cuentas; metas y patrimonio llegan con el plan 3.
13. **% de ahorro libre (0–100)** con los mensajes del Excel por rango: < 10 %, 10–14 %, 15–19 %, 20–24 %, ≥ 25 %.
14. **La búsqueda de texto distingue acentos** por ahora ("cafe" no encuentra "café"); se puede mejorar con `unaccent` de Postgres.

## Global Constraints

- Python **3.12**; Django **>=5.2,<5.3**; PostgreSQL **17**.
- Dinero: `Decimal`, `DecimalField(max_digits=12, decimal_places=2)`. **Nunca `float`.** Tasas y porcentajes: fracción (`0.0500` = 5 %).
- Redondeo a 2 decimales **solo al mostrar o al guardar un prorrateo** (`apps.calculos.comun.redondear`).
- Moneda en pantalla: `$1,234.56`; negativos `-$1,234.56` (RNF-08, filtro `dinero`).
- Nombres de dominio en **español** (modelos, campos, funciones, URLs, plantillas). Mensajes en español.
- `apps/calculos/` **no importa nada de Django**.
- Todo modelo de negocio hereda de `apps.core.models.ModeloDeHogar`. Toda consulta filtra por `request.hogar`. Un id de otro hogar en la URL → **404**; en un formulario → **error de validación**.
- Toda vista (salvo login y salud) usa el decorador `apps.core.acceso.requiere_hogar`.
- Todo formulario de un dato del hogar hereda de `apps.core.formularios.FormularioDeHogar`.
- Frontend: HTMX **2.0.11** servido desde `static/vendor/` (sin CDN en tiempo de ejecución); Tailwind **v4.3.3** standalone compilado en Docker; **sin Node**.
- Mobile-first: la captura rápida funciona a 360 px de ancho (RNF-01).
- **Ningún dato personal en el repo**: ejemplos y fixtures ficticios (nada de números de servicio, cuentas ni emails reales).
- Todos los comandos se ejecutan desde PowerShell en `Finanzas\app_finanzas\` y **dentro de Docker** (`docker compose run --rm web ...`).
- Cada commit termina con la línea: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Editar o borrar un pago de deuda** → el saldo de la tarjeta o préstamo cambia una sola vez (sin doble descuento ni saldo perdido). *Pruebas en Task 5 y Task 8.*
2. **Restricción única con el hogar fuera del formulario** (nombre repetido en un catálogo, concepto repetido en el presupuesto) → error en el formulario, nunca un 500 por `IntegrityError`. *Pruebas en Task 2, Task 10 y Task 13.*
3. **Ids de otro hogar** en la URL, en un POST o en los filtros → 404 o error de formulario; nunca se muestran ni se modifican datos ajenos. *Pruebas en Task 6, Task 8, Task 10, Task 12 y Task 13.*
4. **Mes inválido o de borde** (mes 13, día 31, diciembre → enero) → 404 o navegación correcta. *Pruebas en Task 7, Task 8 y Task 12.*
5. **Registros inactivos ya usados** (cuenta desactivada en un movimiento viejo) → al editar se conservan seleccionados; en altas nuevas no aparecen. *Pruebas en Task 2 y Task 13.*

---

## Estructura de archivos

```
app_finanzas\
├── docker\Dockerfile                      (T2) etapa "css" con Tailwind
├── docker-compose.override.yml            (T2) servicio "css" (compila una vez)
├── .gitignore                             (T2) ignora static/css/app.css
├── README.md                              (T2, T14)
├── finanzas\settings.py                   (T2, T4, T9, T12) STATICFILES_DIRS, LOGIN_*, apps nuevas
├── finanzas\urls.py                       (T3, T6, T10, T12, T13)
├── static\
│   ├── css\entrada.css                    (T2) fuente de Tailwind
│   ├── js\app.js                          (T2, T6) modal y recarga tras guardar
│   └── vendor\htmx-2.0.11.min.js          (T2)
├── templates\
│   ├── base.html                          (T2)
│   ├── componentes\ navegacion.html mensajes.html campo.html   (T2; navegacion crece en T3, T6, T8, T10, T13)
│   ├── componentes\ _formulario_modal.html pagina_formulario.html   (T10; los reutiliza T13)
│   ├── core\ entrar.html sin_hogar.html inicio.html             (T3; inicio se borra en T12)
│   ├── movimientos\ captura.html _captura.html _campos_sugeridos.html (T6) lista.html (T8)
│   ├── presupuesto\ pagina.html _resumen.html _acciones.html     (T10)
│   ├── tablero\mes.html                    (T12)
│   └── catalogos\ indice.html lista.html  (T13)
├── apps\core\
│   ├── acceso.py                          (T3) requiere_hogar
│   ├── fechas.py                          (T7) rangos y navegación de meses
│   ├── formularios.py                     (T2 FormularioDeHogar; T3 FormularioEntrada)
│   ├── htmx.py                            (T2) es_htmx, datos_actualizados; (T10) responder_formulario
│   ├── templatetags\formato.py            (T2) dinero, porcentaje, ancho_barra
│   ├── urls.py / vistas.py                (T3; inicio cambia en T12)
├── apps\catalogos\
│   ├── models.py / admin.py               (T1) "valores sugeridos"; (T6) Concepto.nombre_con_categoria
│   ├── migrations\0003_*.py               (T1)
│   ├── servicios.py                       (T11 resumir_deudas; T13 tasa_sugerida)
│   ├── formularios.py / vistas.py / urls.py   (T13)
├── apps\calculos\tablero.py               (T11) avance, semaforo, distribucion
├── apps\movimientos\                      (T4–T8) models, admin, servicios, formularios, consultas, vistas, urls
├── apps\presupuesto\                      (T9–T10) models, admin, mensajes, servicios, formularios, vistas, urls
├── apps\tablero\                          (T11–T12) servicios, formularios, vistas, urls (sin modelos)
└── tests\
    ├── conftest.py                        (T3 cliente; T4 catalogo; T9 plantilla_excel)
    ├── catalogos\ test_catalogos_admin.py (T1) test_catalogos_vistas.py (T13) test_catalogos_servicios.py (T11, T13)
    ├── core\ test_core_formato.py test_core_formularios.py test_core_base.py (T2) test_core_acceso.py (T3, T12) test_core_fechas.py (T7)
    ├── calculos\test_calc_tablero.py      (T11)
    ├── movimientos\ test_mov_modelo.py (T4) test_mov_servicios.py (T5) test_mov_captura.py (T6) test_mov_consultas.py (T7) test_mov_lista.py (T8)
    ├── presupuesto\ test_pre_servicios.py (T9) test_pre_vistas.py (T10)
    └── tablero\ test_tablero_servicio.py (T11) test_tablero_vistas.py (T12)
```

Los nombres de archivo de prueba son únicos a propósito (pytest con `--import-mode=importlib`, sin `__init__.py` en `tests/`).

---

### Task 1: Concepto con "valores sugeridos (opcional)"

**Files:**
- Modify: `apps/catalogos/models.py` (campos `persona`, `domicilio`, `cuenta` de `Concepto`)
- Modify: `apps/catalogos/admin.py` (`ConceptoAdmin.fieldsets`)
- Create: `apps/catalogos/migrations/0003_concepto_valores_sugeridos.py` (generado)
- Test: `tests/catalogos/test_catalogos_admin.py`

**Interfaces:**
- Consumes: `Concepto`, `Categoria` (plan 1); fixtures `hogar`, `admin_client` (pytest-django).
- Produces: `apps.catalogos.models.AYUDA_SUGERIDO: str`; etiquetas "persona por defecto", "cuenta por defecto", "domicilio por defecto" (las reutiliza el formulario de la Task 13).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/catalogos/test_catalogos_admin.py`:
```python
import pytest
from django.urls import reverse

from apps.catalogos.models import Categoria, Concepto

pytestmark = pytest.mark.django_db


def test_formulario_de_concepto_agrupa_los_valores_sugeridos(admin_client):
    respuesta = admin_client.get(reverse("admin:catalogos_concepto_add"))

    contenido = respuesta.content.decode()
    assert "Valores sugeridos (opcional)" in contenido
    assert "Persona por defecto" in contenido
    assert "Cuenta por defecto" in contenido
    assert "Domicilio por defecto" in contenido


def test_concepto_se_guarda_sin_valores_sugeridos(admin_client, hogar):
    transporte = Categoria.objects.create(hogar=hogar, nombre="Transporte")

    respuesta = admin_client.post(
        reverse("admin:catalogos_concepto_add"),
        {"hogar": hogar.pk, "categoria": transporte.pk, "nombre": "Gasolina", "activo": "on"},
    )

    assert respuesta.status_code == 302
    gasolina = Concepto.objects.get(nombre="Gasolina")
    assert (gasolina.persona, gasolina.cuenta, gasolina.domicilio) == (None, None, None)
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/catalogos/test_catalogos_admin.py -v`
Expected: `test_formulario_de_concepto_agrupa_los_valores_sugeridos` FAIL (no aparece "Valores sugeridos (opcional)"). `test_concepto_se_guarda_sin_valores_sugeridos` PASS desde ahora: fija el comportamiento que el usuario necesita (gasolina sin cuenta, recarga sin persona) para que no se pierda.

- [ ] **Step 3: Implementar**

En `apps/catalogos/models.py`, después de `DIA_DEL_MES`:
```python
AYUDA_SUGERIDO = "Opcional. Se precarga al registrar un movimiento y puedes cambiarlo en cada uno."
```
y reemplazar los tres campos de `Concepto`:
```python
    persona = models.ForeignKey(
        Persona,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="persona por defecto",
        help_text=AYUDA_SUGERIDO,
    )
    domicilio = models.ForeignKey(
        Domicilio,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="domicilio por defecto",
        help_text=(
            "Opcional. Distingue el mismo concepto en varios domicilios (ej. Luz de Casa Fidel) "
            "y se precarga al registrar un movimiento."
        ),
    )
    cuenta = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="cuenta por defecto",
        help_text=AYUDA_SUGERIDO,
    )
```

En `apps/catalogos/admin.py`, `ConceptoAdmin` queda:
```python
@admin.register(Concepto)
class ConceptoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "domicilio", "persona", "es_fijo", "es_hormiga")
    list_filter = ("hogar", "categoria", "domicilio", "es_fijo", "es_hormiga")
    search_fields = ("nombre",)
    fieldsets = (
        (None, {"fields": ("hogar", "categoria", "nombre", "es_fijo", "es_hormiga", "activo")}),
        (
            "Valores sugeridos (opcional)",
            {
                "description": (
                    "Se precargan al registrar un movimiento; puedes cambiarlos en cada gasto."
                ),
                "fields": ("persona", "cuenta", "domicilio"),
            },
        ),
    )
```

- [ ] **Step 4: Generar la migración**

Run: `docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations catalogos -n concepto_valores_sugeridos`
Expected: `apps/catalogos/migrations/0003_concepto_valores_sugeridos.py` con tres `Alter field` (`cuenta`, `domicilio`, `persona`). No cambia el esquema de la base, solo metadatos.

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: todo verde (`0 failed`); `test_catalogos_admin.py`: 2 passed.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/catalogos tests/catalogos/test_catalogos_admin.py
git commit -m "feat(catalogos): persona, cuenta y domicilio del concepto como valores sugeridos opcionales" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Base de la interfaz (Tailwind, HTMX, plantilla base, formato y formularios del hogar)

**Files:**
- Create: `static/css/entrada.css`, `static/js/app.js`, `static/vendor/htmx-2.0.11.min.js` (descargado)
- Create: `templates/base.html`, `templates/componentes/navegacion.html`, `templates/componentes/mensajes.html`, `templates/componentes/campo.html`
- Create: `apps/core/templatetags/__init__.py` (vacío), `apps/core/templatetags/formato.py`, `apps/core/htmx.py`, `apps/core/formularios.py`
- Modify: `docker/Dockerfile`, `docker-compose.override.yml`, `.gitignore`, `README.md`, `finanzas/settings.py`
- Test: `tests/core/test_core_formato.py`, `tests/core/test_core_formularios.py`, `tests/core/test_core_base.py`

**Interfaces:**
- Consumes: `ModeloDeHogar` (plan 1), `apps.calculos.comun.redondear`, modelos de catálogos (solo en pruebas).
- Produces:
  - Filtros de plantilla (`{% load formato %}`), también importables como funciones desde `apps.core.templatetags.formato`: `dinero(valor) -> str` (`"$1,234.56"`, `"-$1,234.56"`, `"—"` si es `None`), `porcentaje(fraccion, decimales=2) -> str` (`Decimal("0.9632")` → `"96.32%"`, `"—"` si es `None`), `ancho_barra(fraccion) -> int` (0–100).
  - `apps.core.htmx.es_htmx(request) -> bool`; `apps.core.htmx.datos_actualizados() -> HttpResponse` (204 + cabecera `HX-Trigger: datosActualizados`); `EVENTO_DATOS = "datosActualizados"`.
  - `apps.core.formularios.FormularioDeHogar(forms.ModelForm)`: `__init__(*args, hogar, **kwargs)`; atributo `campos_fijos = ("hogar",)` (las subclases agregan su contenedor). Limita los `ModelChoiceField` a registros del hogar y activos (conserva el valor actual al editar). Valida las restricciones únicas que incluyen `campos_fijos`. Un error del modelo sobre un campo que no está en el formulario se muestra como error general.
  - `templates/base.html` con bloques `titulo` y `contenido`, `<dialog id="modal">` con `<div id="modal-contenido">`, CSRF para HTMX en `<body hx-headers>`.
  - `templates/componentes/campo.html`: dibuja un campo (`campo` en el contexto) con etiqueta, ayuda y errores.
  - `static/js/app.js`: abre el modal cuando HTMX llena `#modal-contenido`; al recibir `datosActualizados` cierra el modal y recarga; `[data-cerrar-modal]` cierra el modal; un `<select data-extraordinarios="a b c">` marca la casilla `es_extraordinario` del mismo formulario.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/core/test_core_formato.py`:
```python
from decimal import Decimal as D

from apps.core.htmx import EVENTO_DATOS, datos_actualizados, es_htmx
from apps.core.templatetags.formato import ancho_barra, dinero, porcentaje


def test_dinero_con_separador_de_miles_y_centavos():
    assert dinero(D("32977.52")) == "$32,977.52"
    assert dinero(D("1648.876")) == "$1,648.88"
    assert dinero(D("0")) == "$0.00"


def test_dinero_negativo_y_vacio():
    assert dinero(D("-3742.5")) == "-$3,742.50"
    assert dinero(D("-0.001")) == "$0.00"
    assert dinero(None) == "—"


def test_porcentaje_de_una_fraccion():
    assert porcentaje(D("0.963226")) == "96.32%"
    assert porcentaje(D("0.05"), 0) == "5%"
    assert porcentaje(None) == "—"


def test_ancho_de_barra_entre_0_y_100():
    assert ancho_barra(D("0.5")) == 50
    assert ancho_barra(D("1.7")) == 100
    assert ancho_barra(D("-0.2")) == 0
    assert ancho_barra(None) == 0


def test_respuesta_de_datos_actualizados(rf):
    respuesta = datos_actualizados()

    assert respuesta.status_code == 204
    assert respuesta["HX-Trigger"] == EVENTO_DATOS
    assert es_htmx(rf.get("/", headers={"HX-Request": "true"}))
    assert not es_htmx(rf.get("/"))
```

`tests/core/test_core_formularios.py`:
```python
import pytest

from apps.catalogos.models import Categoria, Concepto, Persona
from apps.core.formularios import FormularioDeHogar

pytestmark = pytest.mark.django_db


class FormularioPersona(FormularioDeHogar):
    class Meta:
        model = Persona
        fields = ["nombre"]


class FormularioConcepto(FormularioDeHogar):
    class Meta:
        model = Concepto
        fields = ["categoria", "nombre", "persona"]


class FormularioNombreDeConcepto(FormularioDeHogar):
    class Meta:
        model = Concepto
        fields = ["nombre"]


def test_nombre_repetido_en_el_hogar_es_error_del_formulario(hogar):
    Persona.objects.create(hogar=hogar, nombre="Monze")

    formulario = FormularioPersona(data={"nombre": "Monze"}, hogar=hogar)

    assert not formulario.is_valid()
    assert "__all__" in formulario.errors


def test_mismo_nombre_en_otro_hogar_es_valido(hogar, otro_hogar):
    Persona.objects.create(hogar=otro_hogar, nombre="Monze")

    formulario = FormularioPersona(data={"nombre": "Monze"}, hogar=hogar)

    assert formulario.is_valid(), formulario.errors
    assert formulario.save().hogar == hogar


def test_listas_solo_muestran_registros_activos_del_hogar(hogar, otro_hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    Categoria.objects.create(hogar=hogar, nombre="Vieja", activo=False)

    formulario = FormularioConcepto(hogar=hogar)

    assert list(formulario.fields["categoria"].queryset) == [casa]


def test_al_editar_conserva_el_valor_actual_aunque_este_inactivo(hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    abuela = Persona.objects.create(hogar=hogar, nombre="Abuela", activo=False)
    concepto = Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Medicinas", persona=abuela)

    formulario = FormularioConcepto(instance=concepto, hogar=hogar)

    assert abuela in formulario.fields["persona"].queryset
    assert abuela not in FormularioConcepto(hogar=hogar).fields["persona"].queryset


def test_un_id_de_otro_hogar_es_rechazado(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")

    formulario = FormularioConcepto(data={"categoria": ajena.pk, "nombre": "Luz"}, hogar=hogar)

    assert not formulario.is_valid()
    assert "categoria" in formulario.errors


def test_error_de_un_campo_fuera_del_formulario_se_muestra_como_general(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")

    formulario = FormularioNombreDeConcepto(
        data={"nombre": "Luz"}, instance=Concepto(categoria=ajena), hogar=hogar
    )

    assert not formulario.is_valid()
    assert "Pertenece a otro hogar." in str(formulario.non_field_errors())
```

`tests/core/test_core_base.py`:
```python
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
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/core/test_core_formato.py tests/core/test_core_formularios.py tests/core/test_core_base.py -v`
Expected: FAIL / ERROR con `ModuleNotFoundError: No module named 'apps.core.htmx'` (y `apps.core.formularios`), y `TemplateDoesNotExist: base.html`.

- [ ] **Step 3: Formato y respuestas HTMX**

`apps/core/templatetags/__init__.py`: vacío.

`apps/core/templatetags/formato.py`:
```python
"""Filtros de presentación (RNF-08): moneda MXN, porcentajes y barras."""

from decimal import Decimal

from django import template

from apps.calculos.comun import redondear

register = template.Library()


@register.filter
def dinero(valor):
    """$1,234.56; negativos como -$1,234.56; vacío como —."""
    if valor is None or valor == "":
        return "—"
    valor = redondear(Decimal(valor))
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(valor):,.2f}"


@register.filter
def porcentaje(valor, decimales=2):
    """Fracción → porcentaje: 0.9632 → 96.32%."""
    if valor is None or valor == "":
        return "—"
    decimales = int(decimales)
    return f"{redondear(Decimal(valor) * 100, decimales):,.{decimales}f}%"


@register.filter
def ancho_barra(valor):
    """Ancho de una barra de progreso (0–100) a partir de una fracción."""
    if valor is None or valor == "":
        return 0
    return int(min(max(Decimal(valor), Decimal(0)), Decimal(1)) * 100)
```

`apps/core/htmx.py`:
```python
"""Ayudas para vistas que responden a HTMX."""

from django.http import HttpResponse

EVENTO_DATOS = "datosActualizados"


def es_htmx(request):
    return request.headers.get("HX-Request") == "true"


def datos_actualizados():
    """204 + evento: el navegador cierra el modal y recarga la vista (static/js/app.js)."""
    respuesta = HttpResponse(status=204)
    respuesta["HX-Trigger"] = EVENTO_DATOS
    return respuesta
```

- [ ] **Step 4: `FormularioDeHogar`**

`apps/core/formularios.py`:
```python
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.db.models import Q

from apps.core.models import ModeloDeHogar


class FormularioDeHogar(forms.ModelForm):
    """ModelForm de un dato del hogar.

    - Cada lista desplegable muestra solo registros del hogar y activos (al editar conserva el
      valor actual aunque esté inactivo).
    - Valida las restricciones únicas que incluyen los `campos_fijos` (hogar, contenedor), que
      Django omitiría por no estar en el formulario.
    - Un error del modelo sobre un campo que no está en el formulario se muestra como general.
    """

    campos_fijos = ("hogar",)

    def __init__(self, *args, hogar, **kwargs):
        super().__init__(*args, **kwargs)
        self.hogar = hogar
        self.instance.hogar = hogar
        for nombre, campo in self.fields.items():
            if not isinstance(campo, forms.ModelChoiceField):
                continue
            modelo = campo.queryset.model
            if not issubclass(modelo, ModeloDeHogar):
                continue
            consulta = campo.queryset.filter(hogar=hogar)
            if any(f.name == "activo" for f in modelo._meta.fields):
                actual = self.initial.get(nombre)
                consulta = consulta.filter(Q(activo=True) | Q(pk=actual)) if actual else consulta.filter(activo=True)
            campo.queryset = consulta

    def _get_validation_exclusions(self):
        return super()._get_validation_exclusions() - set(self.campos_fijos)

    def add_error(self, field, error):
        if field is None and hasattr(error, "error_dict"):
            for nombre in [n for n in error.error_dict if n != NON_FIELD_ERRORS and n not in self.fields]:
                error.error_dict.setdefault(NON_FIELD_ERRORS, []).extend(error.error_dict.pop(nombre))
        super().add_error(field, error)
```

- [ ] **Step 5: Ajustes de `settings.py`**

En `finanzas/settings.py`, después de `STATIC_ROOT`:
```python
STATICFILES_DIRS = [BASE_DIR / "static"]
```
y al final del archivo:
```python
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"
```
(Las rutas `login` e `inicio` se crean en la Task 3.)

- [ ] **Step 6: HTMX local, CSS y JS**

```powershell
New-Item -ItemType Directory -Force static\vendor, static\css, static\js
curl.exe -sSLo static\vendor\htmx-2.0.11.min.js https://unpkg.com/htmx.org@2.0.11/dist/htmx.min.js
```
Expected: `static\vendor\htmx-2.0.11.min.js` de ~50 KB que empieza con `var htmx=`.

`static/css/entrada.css`:
```css
@import "tailwindcss";
@source "../../templates";
@source "../../apps";

@layer base {
  input:not([type="checkbox"]):not([type="radio"]),
  select,
  textarea {
    @apply w-full rounded-lg border border-slate-300 bg-white px-3 py-2;
  }
  label {
    @apply text-sm font-medium text-slate-700;
  }
}

@layer components {
  .boton {
    @apply inline-block rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700;
  }
  .boton-secundario {
    @apply inline-block rounded-lg border border-slate-300 bg-white px-4 py-2 hover:bg-slate-100;
  }
  .tarjeta {
    @apply rounded-xl bg-white p-4 shadow-sm;
  }
}
```

`static/js/app.js`:
```js
// Comportamiento global de la interfaz. Ver apps/core/htmx.py.
const modal = () => document.getElementById("modal");

// Abrir el modal cuando HTMX coloca contenido en él.
document.addEventListener("htmx:afterSwap", (evento) => {
  if (evento.detail.target.id === "modal-contenido" && !modal().open) {
    modal().showModal();
  }
});

// Tras guardar, el servidor responde 204 + "datosActualizados": cerrar y recargar.
document.addEventListener("datosActualizados", () => {
  if (modal().open) modal().close();
  window.location.reload();
});

document.addEventListener("click", (evento) => {
  if (evento.target.closest("[data-cerrar-modal]")) modal().close();
});

// Un <select data-extraordinarios="a b c"> marca la casilla es_extraordinario de su formulario.
document.addEventListener("change", (evento) => {
  const lista = evento.target.dataset?.extraordinarios;
  if (lista === undefined) return;
  const casilla = evento.target.form?.querySelector("[name=es_extraordinario]");
  if (casilla) casilla.checked = lista.split(" ").includes(evento.target.value);
});
```

En `.gitignore`, sección "Python / herramientas", agregar:
```
static/css/app.css
```

- [ ] **Step 7: Plantillas base**

`templates/base.html`:
```html
{% load static %}<!doctype html>
<html lang="es-MX">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block titulo %}Inicio{% endblock %} · Finanzas</title>
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
  <script src="{% static 'vendor/htmx-2.0.11.min.js' %}" defer></script>
  <script src="{% static 'js/app.js' %}" defer></script>
</head>
<body class="min-h-screen bg-slate-50 text-slate-900" hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  {% if user.is_authenticated and request.hogar %}{% include "componentes/navegacion.html" %}{% endif %}
  <main class="mx-auto max-w-5xl px-4 pb-24 pt-4 md:pb-8 md:pl-60">
    {% include "componentes/mensajes.html" %}
    {% block contenido %}{% endblock %}
  </main>
  <dialog id="modal" class="m-auto w-full max-w-md rounded-xl p-0 backdrop:bg-slate-900/50">
    <div id="modal-contenido"></div>
  </dialog>
</body>
</html>
```

`templates/componentes/navegacion.html` (las Tasks 3, 6, 8, 10 y 13 agregan enlaces):
```html
<nav class="fixed inset-x-0 bottom-0 z-10 flex items-center justify-around border-t border-slate-200 bg-white py-2 text-xs md:inset-y-0 md:left-0 md:right-auto md:w-56 md:flex-col md:items-stretch md:justify-start md:gap-1 md:border-r md:border-t-0 md:p-4 md:text-sm">
  <span class="hidden px-2 pb-4 text-lg font-semibold md:block">💰 Finanzas</span>
</nav>
```

`templates/componentes/mensajes.html`:
```html
{% if messages %}
  <ul class="mb-4 space-y-2">
    {% for mensaje in messages %}
      <li class="rounded-lg px-3 py-2 text-sm {% if mensaje.level_tag == 'error' %}bg-red-50 text-red-700{% elif mensaje.level_tag == 'success' %}bg-emerald-50 text-emerald-800{% else %}bg-sky-50 text-sky-800{% endif %}">{{ mensaje }}</li>
    {% endfor %}
  </ul>
{% endif %}
```

`templates/componentes/campo.html`:
```html
<div class="space-y-1">
  {% if campo.widget_type == "checkbox" %}
    <label class="flex items-center gap-2">{{ campo }} {{ campo.label }}</label>
  {% else %}
    {{ campo.label_tag }}{{ campo }}
  {% endif %}
  {% if campo.help_text %}<p class="text-xs text-slate-500">{{ campo.help_text }}</p>{% endif %}
  {% for error in campo.errors %}<p class="text-sm text-red-600">{{ error }}</p>{% endfor %}
</div>
```

- [ ] **Step 8: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest tests/core -v`
Expected: `test_core_formato.py` 5 passed, `test_core_formularios.py` 6 passed, `test_core_base.py` 2 passed; el resto de `tests/core` sigue verde.

- [ ] **Step 9: Tailwind en Docker**

`docker/Dockerfile` completo (la etapa `css` usa la misma imagen base de Python, así el CI sigue usando el mirror de ECR):
```dockerfile
ARG PYTHON_IMAGE=python:3.12-slim

# --- Etapa css: compila Tailwind con el binario standalone (sin Node) ---
FROM ${PYTHON_IMAGE} AS css
ARG TAILWIND_VERSION=v4.3.3
ADD --chmod=755 https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64 /usr/local/bin/tailwindcss
WORKDIR /app
COPY static/css/entrada.css static/css/entrada.css
COPY templates templates
COPY apps apps
RUN tailwindcss -i static/css/entrada.css -o static/css/app.css --minify
CMD ["tailwindcss", "-i", "static/css/entrada.css", "-o", "static/css/app.css", "--minify"]

# --- Etapa final ---
FROM ${PYTHON_IMAGE}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-groups

COPY . .
COPY --from=css /app/static/css/app.css static/css/app.css
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
CMD ["gunicorn", "finanzas.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

`docker-compose.override.yml` (servicio `css` para desarrollo: compila una vez sobre la carpeta montada; en Windows el modo `--watch` no recibe los cambios de archivos, por eso se vuelve a correr a mano):
```yaml
services:
  web:
    command: python manage.py runserver 0.0.0.0:8000
    environment:
      DJANGO_DEBUG: "1"
    volumes:
      - .:/app

  css:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: css
    volumes:
      - .:/app
```

En `README.md`, en la tabla de "Desarrollo", después de la fila "Levantar":
```
| Recompilar estilos (cambié clases en plantillas) | `docker compose run --rm css` |
```

Run:
```powershell
docker compose build
docker compose run --rm css
docker run --rm --entrypoint sh finanzas-web -c "grep -c bg-slate-50 /app/static/css/app.css"
sh tests/verificar_imagen.sh
```
Expected: el build termina sin errores; `static\css\app.css` existe en la carpeta (ignorado por git); el `grep` imprime `1`; `OK: ningún archivo sensible entró a la imagen`.

- [ ] **Step 10: Suite completa, lint y commit**

```powershell
docker compose run --rm web pytest
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add static templates apps/core finanzas/settings.py docker .gitignore README.md docker-compose.override.yml tests/core
git commit -m "feat(ui): base de la interfaz con Tailwind, HTMX, formato de moneda y formularios por hogar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Expected: `0 failed`; ruff sin cambios pendientes ni errores.

---

### Task 3: Login, salida y acceso por hogar

**Files:**
- Create: `apps/core/acceso.py`, `apps/core/vistas.py`, `apps/core/urls.py`
- Modify: `apps/core/formularios.py` (agregar `FormularioEntrada`), `finanzas/urls.py`, `templates/componentes/navegacion.html`, `tests/conftest.py`
- Create: `templates/core/entrar.html`, `templates/core/sin_hogar.html`, `templates/core/inicio.html`
- Test: `tests/core/test_core_acceso.py`

**Interfaces:**
- Consumes: `HogarMiddleware` (`request.hogar`), `base.html`, `componentes/campo.html` (Task 2).
- Produces:
  - `apps.core.acceso.requiere_hogar(vista)`: exige sesión (si no, redirige a `/entrar/?next=...`) y hogar (si no, 403 con `core/sin_hogar.html`).
  - Rutas sin namespace: `inicio` (`/`), `login` (`/entrar/`), `logout` (`/salir/`, solo POST).
  - `apps.core.formularios.FormularioEntrada` (campo `username` con etiqueta "Email").
  - Fixture `cliente` (en `tests/conftest.py`): `client` con sesión de `usuario`, que ya tiene `hogar`.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `tests/conftest.py`, agregar al final:
```python
@pytest.fixture
def cliente(client, usuario, hogar):
    """Cliente con sesión iniciada de un usuario que ya tiene hogar."""
    client.force_login(usuario)
    return client
```

`tests/core/test_core_acceso.py`:
```python
import pytest

pytestmark = pytest.mark.django_db


def test_sin_sesion_redirige_al_login(client):
    respuesta = client.get("/")

    assert respuesta.status_code == 302
    assert respuesta.url == "/entrar/?next=/"


def test_la_pantalla_de_entrada_pide_email_y_contrasena(client):
    respuesta = client.get("/entrar/")

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Email" in contenido
    assert 'type="password"' in contenido


def test_entra_con_el_email_en_mayusculas(client, hogar):
    respuesta = client.post(
        "/entrar/", {"username": "JULIO@Example.com", "password": "clave-segura-123"}
    )

    assert respuesta.status_code == 302
    assert respuesta.url == "/"
    assert "_auth_user_id" in client.session


def test_contrasena_incorrecta_no_entra(client, usuario):
    respuesta = client.post("/entrar/", {"username": "julio@example.com", "password": "otra"})

    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors
    assert "_auth_user_id" not in client.session


def test_usuario_sin_hogar_ve_un_aviso(client, usuario):
    client.force_login(usuario)

    respuesta = client.get("/")

    assert respuesta.status_code == 403
    assert "no perteneces a ningún hogar" in respuesta.content.decode()


def test_inicio_muestra_la_navegacion(cliente):
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "Salir" in respuesta.content.decode()


def test_salir_cierra_la_sesion(cliente):
    respuesta = cliente.post("/salir/")

    assert respuesta.status_code == 302
    assert respuesta.url == "/entrar/"
    assert cliente.get("/").status_code == 302
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/core/test_core_acceso.py -v`
Expected: FAIL con 404 en `/` y `/entrar/`.

- [ ] **Step 3: Implementar**

En `apps/core/formularios.py`, agregar el import `from django.contrib.auth.forms import AuthenticationForm` y al final:
```python
class FormularioEntrada(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )
```

`apps/core/acceso.py`:
```python
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def requiere_hogar(vista):
    """Exige sesión iniciada y un hogar activo (request.hogar)."""

    @wraps(vista)
    @login_required
    def envoltura(request, *args, **kwargs):
        if request.hogar is None:
            return render(request, "core/sin_hogar.html", status=403)
        return vista(request, *args, **kwargs)

    return envoltura
```

`apps/core/vistas.py`:
```python
from django.shortcuts import render

from apps.core.acceso import requiere_hogar


@requiere_hogar
def inicio(request):
    return render(request, "core/inicio.html")
```

`apps/core/urls.py`:
```python
from django.contrib.auth import views as auth
from django.urls import path

from apps.core import vistas
from apps.core.formularios import FormularioEntrada

urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path(
        "entrar/",
        auth.LoginView.as_view(
            template_name="core/entrar.html",
            authentication_form=FormularioEntrada,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("salir/", auth.LogoutView.as_view(), name="logout"),
]
```

`finanzas/urls.py`:
```python
from django.contrib import admin
from django.urls import include, path

from finanzas.vistas import salud

urlpatterns = [
    path("admin/", admin.site.urls),
    path("salud/", salud, name="salud"),
    path("", include("apps.core.urls")),
]
```

`templates/core/entrar.html`:
```html
{% extends "base.html" %}
{% block titulo %}Entrar{% endblock %}
{% block contenido %}
<div class="mx-auto mt-12 max-w-sm tarjeta">
  <h1 class="mb-4 text-xl font-semibold">💰 Finanzas familiares</h1>
  <form method="post" class="space-y-3">
    {% csrf_token %}
    {% if form.non_field_errors %}<div class="rounded bg-red-50 p-2 text-sm text-red-700">{{ form.non_field_errors }}</div>{% endif %}
    {% for campo in form %}{% include "componentes/campo.html" %}{% endfor %}
    <input type="hidden" name="next" value="{{ next }}">
    <button type="submit" class="boton w-full">Entrar</button>
  </form>
</div>
{% endblock %}
```

`templates/core/sin_hogar.html`:
```html
{% extends "base.html" %}
{% block titulo %}Sin hogar{% endblock %}
{% block contenido %}
<div class="mx-auto mt-12 max-w-md tarjeta space-y-3">
  <h1 class="text-lg font-semibold">Todavía no perteneces a ningún hogar</h1>
  <p class="text-sm text-slate-600">Tu cuenta existe, pero no perteneces a ningún hogar. Créalo con
    <code>python manage.py crear_hogar --nombre "Mi Familia" --email tu@email.com</code>.</p>
  <form method="post" action="{% url 'logout' %}">{% csrf_token %}<button class="boton-secundario">Salir</button></form>
</div>
{% endblock %}
```

`templates/core/inicio.html` (temporal; la Task 12 lo reemplaza por el tablero):
```html
{% extends "base.html" %}
{% block contenido %}
<h1 class="text-xl font-semibold">Hola 👋</h1>
<p class="text-slate-600">{{ request.hogar }}</p>
{% endblock %}
```

`templates/componentes/navegacion.html`: dentro del `<nav>`, después del `<span>`, agregar:
```html
  <a href="{% url 'inicio' %}" class="flex flex-col items-center rounded-lg px-2 py-1 md:flex-row md:gap-2 hover:bg-slate-100"><span>🏠</span><span>Inicio</span></a>
  <!-- más enlaces: Tasks 6, 8, 10, 13 -->
  <form method="post" action="{% url 'logout' %}" class="hidden md:mt-auto md:block">{% csrf_token %}<button class="w-full rounded-lg px-2 py-1 text-left text-slate-500 hover:bg-slate-100">↩ Salir</button></form>
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_core_acceso.py` 7 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/core finanzas/urls.py templates tests/conftest.py tests/core/test_core_acceso.py
git commit -m "feat(core): login por email, salida y acceso exigiendo hogar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Modelo `Movimiento`

**Files:**
- Create: `apps/movimientos/__init__.py` (vacío), `apps/movimientos/apps.py`, `apps/movimientos/models.py`, `apps/movimientos/migrations/__init__.py` (vacío), `apps/movimientos/migrations/0001_initial.py` (generado)
- Modify: `finanzas/settings.py` (INSTALLED_APPS), `tests/conftest.py` (fixture `catalogo`)
- Test: `tests/movimientos/test_mov_modelo.py`

**Interfaces:**
- Consumes: `ModeloDeHogar`; `Categoria`, `Concepto`, `Cuenta`, `Persona`, `Domicilio`, `DINERO` (plan 1); `sembrar_catalogos`.
- Produces:
  - `apps.movimientos.models.TipoIngreso` (TextChoices: `salario, aguinaldo, ptu, bono, beca, prestamo_recibido, reembolso, venta, otro`), `MetodoPago` (`efectivo, transferencia, tarjeta_debito, tarjeta_credito, domiciliacion`), `INGRESOS_EXTRAORDINARIOS: tuple` (aguinaldo, ptu, bono, beca, prestamo_recibido), `es_extraordinario_por_defecto(tipo_ingreso) -> bool`, `TIPOS_DEUDA = (Cuenta.Tipo.CREDITO, Cuenta.Tipo.PRESTAMO)`.
  - `Movimiento(hogar, fecha, tipo, monto, descripcion, categoria, concepto, tipo_ingreso, es_extraordinario, metodo_pago, cuenta, cuenta_destino, persona, domicilio, es_hormiga, notas, origen, creado_por)` con `Movimiento.Tipo.GASTO|INGRESO|TRANSFERENCIA|PAGO_DEUDA` y `Movimiento.Origen.MANUAL|IMPORTADO`. FKs a catálogos con `on_delete=RESTRICT` (RF-CAT-05). `clean()` valida las reglas por tipo; `save()` completa la descripción vacía.
  - Fixture `catalogo` (en `tests/conftest.py`): `SimpleNamespace` con `categorias` (dict nombre → Categoria), `monze` (Persona), `fidel` (Domicilio "Casa Fidel"), cuentas `efectivo`, `nomina` (débito), `tarjeta` (crédito, línea 7,100, saldo 6,839.01, no paga el total), `prestamo` (inicial 41,130, mensualidad 1,500, saldo 38,679.72) y conceptos `gasolina` (Transporte, sin valores sugeridos), `recarga` (Casa, "Recarga móvil"), `luz_fidel` (Casa, "Luz", domicilio Casa Fidel, cuenta Nómina, fijo).

- [ ] **Step 1: Fixture de catálogo**

En `tests/conftest.py`, agregar a los imports:
```python
from decimal import Decimal as D
from types import SimpleNamespace

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.catalogos.servicios import sembrar_catalogos
```
y al final:
```python
@pytest.fixture
def catalogo(hogar):
    """Catálogo mínimo y ficticio de un hogar."""
    sembrar_catalogos(hogar)
    categorias = {c.nombre: c for c in Categoria.objects.del_hogar(hogar)}
    fidel = Domicilio.objects.create(hogar=hogar, alias="Casa Fidel")
    nomina = Cuenta.objects.create(hogar=hogar, nombre="Nómina", tipo=Cuenta.Tipo.DEBITO)
    return SimpleNamespace(
        categorias=categorias,
        monze=Persona.objects.create(hogar=hogar, nombre="Monze", parentesco="hija"),
        fidel=fidel,
        efectivo=Cuenta.objects.create(hogar=hogar, nombre="Efectivo", tipo=Cuenta.Tipo.EFECTIVO),
        nomina=nomina,
        tarjeta=Cuenta.objects.create(
            hogar=hogar,
            nombre="Tarjeta Oro",
            tipo=Cuenta.Tipo.CREDITO,
            linea_credito=D("7100"),
            saldo_actual=D("6839.01"),
            paga_total_mensual=False,
        ),
        prestamo=Cuenta.objects.create(
            hogar=hogar,
            nombre="Préstamo auto",
            tipo=Cuenta.Tipo.PRESTAMO,
            monto_inicial=D("41130"),
            mensualidad=D("1500"),
            saldo_actual=D("38679.72"),
        ),
        gasolina=Concepto.objects.create(
            hogar=hogar, categoria=categorias["Transporte"], nombre="Gasolina"
        ),
        recarga=Concepto.objects.create(
            hogar=hogar, categoria=categorias["Casa"], nombre="Recarga móvil"
        ),
        luz_fidel=Concepto.objects.create(
            hogar=hogar,
            categoria=categorias["Casa"],
            nombre="Luz",
            domicilio=fidel,
            cuenta=nomina,
            es_fijo=True,
        ),
    )
```

- [ ] **Step 2: Escribir las pruebas que fallan**

`tests/movimientos/test_mov_modelo.py`:
```python
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.db.models import RestrictedError

from apps.catalogos.models import Categoria, Persona
from apps.movimientos.models import (
    MetodoPago,
    Movimiento,
    TipoIngreso,
    es_extraordinario_por_defecto,
)

pytestmark = pytest.mark.django_db


def gasto(catalogo, **campos):
    datos = {
        "hogar": catalogo.gasolina.hogar,
        "tipo": Movimiento.Tipo.GASTO,
        "monto": D("500"),
        "concepto": catalogo.gasolina,
    }
    datos.update(campos)
    return Movimiento(**datos)


def entre_cuentas(catalogo, tipo, origen, destino):
    return Movimiento(
        hogar=catalogo.nomina.hogar,
        tipo=tipo,
        monto=D("1000"),
        metodo_pago=MetodoPago.TRANSFERENCIA,
        cuenta=origen,
        cuenta_destino=destino,
    )


def errores(movimiento):
    with pytest.raises(ValidationError) as error:
        movimiento.full_clean()
    return error.value.message_dict


def test_gasto_con_concepto_toma_su_categoria(catalogo):
    movimiento = gasto(catalogo)

    movimiento.full_clean()

    assert movimiento.categoria == catalogo.categorias["Transporte"]


def test_gasto_sin_categoria_ni_concepto_es_invalido(catalogo):
    assert "categoria" in errores(gasto(catalogo, concepto=None))


def test_concepto_de_otra_categoria_es_invalido(catalogo):
    assert "concepto" in errores(gasto(catalogo, categoria=catalogo.categorias["Comida"]))


def test_monto_debe_ser_positivo(catalogo):
    assert "monto" in errores(gasto(catalogo, monto=D("0")))


def test_ingreso_requiere_tipo_de_ingreso(catalogo):
    ingreso = Movimiento(hogar=catalogo.nomina.hogar, tipo=Movimiento.Tipo.INGRESO, monto=D("1000"))

    assert "tipo_ingreso" in errores(ingreso)


def test_solo_los_ingresos_llevan_tipo_de_ingreso(catalogo):
    assert "tipo_ingreso" in errores(gasto(catalogo, tipo_ingreso=TipoIngreso.BONO))


def test_transferencia_requiere_dos_cuentas_distintas(catalogo):
    tipo = Movimiento.Tipo.TRANSFERENCIA

    assert "cuenta" in errores(entre_cuentas(catalogo, tipo, None, catalogo.efectivo))
    assert "cuenta_destino" in errores(entre_cuentas(catalogo, tipo, catalogo.nomina, None))
    misma = entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.nomina)
    assert "cuenta_destino" in errores(misma)


def test_pago_de_deuda_va_a_una_tarjeta_o_prestamo(catalogo):
    tipo = Movimiento.Tipo.PAGO_DEUDA

    a_efectivo = entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.efectivo)
    assert "cuenta_destino" in errores(a_efectivo)
    entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.tarjeta).full_clean()
    entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.prestamo).full_clean()


def test_un_gasto_no_lleva_cuenta_destino(catalogo):
    assert "cuenta_destino" in errores(gasto(catalogo, cuenta_destino=catalogo.tarjeta))


def test_persona_de_otro_hogar_es_invalida(catalogo, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    assert "persona" in errores(gasto(catalogo, persona=ajena))


def test_descripcion_vacia_toma_el_nombre_del_concepto(catalogo):
    movimiento = gasto(catalogo)
    movimiento.full_clean()
    movimiento.save()

    assert movimiento.descripcion == "Gasolina"


def test_descripcion_vacia_de_un_ingreso_toma_el_tipo(catalogo):
    ingreso = Movimiento(
        hogar=catalogo.nomina.hogar,
        tipo=Movimiento.Tipo.INGRESO,
        tipo_ingreso=TipoIngreso.AGUINALDO,
        monto=D("20000"),
    )
    ingreso.full_clean()
    ingreso.save()

    assert ingreso.descripcion == "Aguinaldo"


def test_extraordinarios_por_defecto():
    assert es_extraordinario_por_defecto(TipoIngreso.AGUINALDO)
    assert es_extraordinario_por_defecto(TipoIngreso.PTU)
    assert es_extraordinario_por_defecto(TipoIngreso.PRESTAMO_RECIBIDO)
    assert not es_extraordinario_por_defecto(TipoIngreso.SALARIO)


def test_borrar_el_hogar_borra_sus_movimientos(catalogo, hogar):
    movimiento = gasto(catalogo)
    movimiento.full_clean()
    movimiento.save()

    hogar.delete()

    assert not Movimiento.objects.exists()
    assert not Categoria.objects.exists()


def test_persona_con_movimientos_no_se_puede_borrar(catalogo):
    movimiento = gasto(catalogo, persona=catalogo.monze)
    movimiento.full_clean()
    movimiento.save()

    with pytest.raises(RestrictedError):
        catalogo.monze.delete()
```

- [ ] **Step 3: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/movimientos/test_mov_modelo.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.movimientos'`.

- [ ] **Step 4: Implementar**

`apps/movimientos/apps.py`:
```python
from django.apps import AppConfig


class MovimientosConfig(AppConfig):
    name = "apps.movimientos"
    verbose_name = "Movimientos"
```

`apps/movimientos/models.py`:
```python
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.catalogos.models import DINERO, Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.core.models import ModeloDeHogar


class TipoIngreso(models.TextChoices):
    SALARIO = "salario", "Salario"
    AGUINALDO = "aguinaldo", "Aguinaldo"
    PTU = "ptu", "Utilidades (PTU)"
    BONO = "bono", "Bono"
    BECA = "beca", "Beca"
    PRESTAMO_RECIBIDO = "prestamo_recibido", "Préstamo recibido"
    REEMBOLSO = "reembolso", "Reembolso"
    VENTA = "venta", "Venta"
    OTRO = "otro", "Otro"


class MetodoPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    TRANSFERENCIA = "transferencia", "Transferencia"
    TARJETA_DEBITO = "tarjeta_debito", "Tarjeta de débito"
    TARJETA_CREDITO = "tarjeta_credito", "Tarjeta de crédito"
    DOMICILIACION = "domiciliacion", "Domiciliación"


# RF-MOV-02: tipos de ingreso marcados como extraordinarios por defecto (RN-13).
INGRESOS_EXTRAORDINARIOS = (
    TipoIngreso.AGUINALDO,
    TipoIngreso.PTU,
    TipoIngreso.BONO,
    TipoIngreso.BECA,
    TipoIngreso.PRESTAMO_RECIBIDO,
)
TIPOS_DEUDA = (Cuenta.Tipo.CREDITO, Cuenta.Tipo.PRESTAMO)


def es_extraordinario_por_defecto(tipo_ingreso):
    return tipo_ingreso in INGRESOS_EXTRAORDINARIOS


class Movimiento(ModeloDeHogar):
    class Tipo(models.TextChoices):
        GASTO = "gasto", "Gasto"
        INGRESO = "ingreso", "Ingreso"
        TRANSFERENCIA = "transferencia", "Transferencia"
        PAGO_DEUDA = "pago_deuda", "Pago de deuda"

    class Origen(models.TextChoices):
        MANUAL = "manual", "Manual"
        IMPORTADO = "importado", "Importado"

    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    monto = models.DecimalField(validators=[MinValueValidator(Decimal("0.01"))], **DINERO)
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    categoria = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.RESTRICT, verbose_name="categoría"
    )
    concepto = models.ForeignKey(Concepto, null=True, blank=True, on_delete=models.RESTRICT)
    tipo_ingreso = models.CharField(
        "tipo de ingreso", max_length=20, choices=TipoIngreso.choices, blank=True
    )
    es_extraordinario = models.BooleanField("extraordinario", default=False)
    metodo_pago = models.CharField(
        "método de pago", max_length=15, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO
    )
    cuenta = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.RESTRICT, related_name="movimientos"
    )
    cuenta_destino = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="movimientos_entrantes",
        verbose_name="cuenta destino",
    )
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.RESTRICT, related_name="movimientos"
    )
    domicilio = models.ForeignKey(
        Domicilio, null=True, blank=True, on_delete=models.RESTRICT, related_name="movimientos"
    )
    es_hormiga = models.BooleanField("hormiga 🐜", default=False)
    notas = models.TextField(blank=True)
    origen = models.CharField(max_length=10, choices=Origen.choices, default=Origen.MANUAL)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["hogar", "fecha"], name="mov_hogar_fecha"),
            models.Index(fields=["hogar", "categoria", "fecha"], name="mov_hogar_categoria_fecha"),
            models.Index(fields=["hogar", "cuenta", "fecha"], name="mov_hogar_cuenta_fecha"),
            models.Index(fields=["hogar", "persona"], name="mov_hogar_persona"),
            models.Index(fields=["hogar", "domicilio"], name="mov_hogar_domicilio"),
        ]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} {self.descripcion} {self.monto}"

    def clean(self):
        if self.concepto_id and not self.categoria_id:
            self.categoria = self.concepto.categoria
        super().clean()
        errores = {}
        tipo = self.Tipo
        if self.tipo == tipo.GASTO and not self.categoria_id:
            errores["categoria"] = "Indica la categoría del gasto."
        if (
            self.concepto_id
            and self.categoria_id
            and self.concepto.categoria_id != self.categoria_id
        ):
            errores["concepto"] = "El concepto no pertenece a la categoría elegida."
        if self.tipo == tipo.INGRESO and not self.tipo_ingreso:
            errores["tipo_ingreso"] = "Indica el tipo de ingreso."
        if self.tipo != tipo.INGRESO and (self.tipo_ingreso or self.es_extraordinario):
            errores["tipo_ingreso"] = "Solo los ingresos llevan tipo de ingreso."
        if self.tipo in (tipo.TRANSFERENCIA, tipo.PAGO_DEUDA):
            errores.update(self._errores_de_cuentas())
        elif self.cuenta_destino_id:
            errores["cuenta_destino"] = (
                "Solo las transferencias y los pagos de deuda llevan cuenta destino."
            )
        if errores:
            raise ValidationError(errores)

    def _errores_de_cuentas(self):
        if not self.cuenta_id:
            return {"cuenta": "Indica la cuenta de origen."}
        if not self.cuenta_destino_id:
            return {"cuenta_destino": "Indica la cuenta destino."}
        if self.cuenta_destino_id == self.cuenta_id:
            return {"cuenta_destino": "La cuenta destino debe ser distinta de la de origen."}
        if self.tipo == self.Tipo.PAGO_DEUDA and self.cuenta_destino.tipo not in TIPOS_DEUDA:
            return {
                "cuenta_destino": "El pago de deuda debe ir a una tarjeta de crédito o un préstamo."
            }
        return {}

    def save(self, *args, **kwargs):
        if not self.descripcion:
            self.descripcion = self.descripcion_sugerida()
        super().save(*args, **kwargs)

    def descripcion_sugerida(self):
        if self.concepto_id:
            return self.concepto.nombre
        if self.tipo_ingreso:
            return self.get_tipo_ingreso_display()
        if self.categoria_id:
            return self.categoria.nombre
        return self.get_tipo_display()
```

En `finanzas/settings.py`, agregar `"apps.movimientos",` después de `"apps.catalogos",` en `INSTALLED_APPS`.

- [ ] **Step 5: Generar la migración**

Run: `docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations movimientos`
Expected: `apps/movimientos/migrations/0001_initial.py` con `Create model Movimiento` y 5 índices.

- [ ] **Step 6: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_mov_modelo.py` 15 passed; todo verde.

- [ ] **Step 7: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/movimientos finanzas/settings.py tests/conftest.py tests/movimientos/test_mov_modelo.py
git commit -m "feat(movimientos): modelo de gastos, ingresos, transferencias y pagos de deuda con validaciones por tipo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Servicios de movimientos (RN-14 y valores sugeridos) y admin

**Files:**
- Create: `apps/movimientos/servicios.py`, `apps/movimientos/admin.py`
- Test: `tests/movimientos/test_mov_servicios.py`

**Interfaces:**
- Consumes: `Movimiento`, `MetodoPago`, `Cuenta`, fixture `catalogo` (Task 4).
- Produces:
  - `apps.movimientos.servicios.guardar_movimiento(movimiento, usuario=None) -> Movimiento`: `full_clean()`, guarda y aplica RN-14 (un pago de deuda reduce el `saldo_actual` de la cuenta destino); si el movimiento ya existía, primero revierte el efecto anterior. Atómico. Llena `creado_por` si viene `usuario` y estaba vacío.
  - `eliminar_movimiento(movimiento) -> None`: revierte el efecto y borra. Atómico.
  - `valores_sugeridos(concepto) -> dict` con llaves `categoria`, `cuenta`, `persona`, `domicilio` (ids o `None`), `es_hormiga` (bool) y `metodo_pago` (según el tipo de la cuenta sugerida; `efectivo` si no hay cuenta).
  - `metodo_para_cuenta(cuenta | None) -> str`.
  - Admin de `Movimiento` que guarda y borra con estos servicios (sin borrado masivo).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/movimientos/test_mov_servicios.py`:
```python
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import eliminar_movimiento, guardar_movimiento, valores_sugeridos

pytestmark = pytest.mark.django_db


def pago(catalogo, monto="1000", destino=None):
    return Movimiento(
        hogar=catalogo.tarjeta.hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto=D(monto),
        metodo_pago=MetodoPago.TRANSFERENCIA,
        cuenta=catalogo.nomina,
        cuenta_destino=destino or catalogo.tarjeta,
    )


def saldo(cuenta):
    cuenta.refresh_from_db()
    return cuenta.saldo_actual


def test_pago_de_deuda_reduce_el_saldo_de_la_tarjeta(catalogo):
    guardar_movimiento(pago(catalogo))

    assert saldo(catalogo.tarjeta) == D("5839.01")


def test_editar_el_monto_ajusta_el_saldo_una_sola_vez(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    movimiento.monto = D("1500")
    guardar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("5339.01")


def test_cambiar_la_cuenta_destino_mueve_el_efecto(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    movimiento.cuenta_destino = catalogo.prestamo
    guardar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("6839.01")
    assert saldo(catalogo.prestamo) == D("37679.72")


def test_eliminar_el_pago_devuelve_el_saldo(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    eliminar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("6839.01")
    assert not Movimiento.objects.exists()


def test_un_gasto_con_tarjeta_no_cambia_saldos(catalogo):
    guardar_movimiento(
        Movimiento(
            hogar=catalogo.tarjeta.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("300"),
            concepto=catalogo.gasolina,
            cuenta=catalogo.tarjeta,
            metodo_pago=MetodoPago.TARJETA_CREDITO,
        )
    )

    assert saldo(catalogo.tarjeta) == D("6839.01")


def test_un_movimiento_invalido_no_toca_saldos(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    movimiento.cuenta_destino = catalogo.efectivo
    with pytest.raises(ValidationError):
        guardar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("5839.01")
    assert saldo(catalogo.efectivo) == D("0")


def test_guarda_quien_lo_registro(catalogo, usuario):
    movimiento = guardar_movimiento(pago(catalogo), usuario=usuario)

    assert movimiento.creado_por == usuario


def test_valores_sugeridos_del_concepto(catalogo):
    assert valores_sugeridos(catalogo.luz_fidel) == {
        "categoria": catalogo.categorias["Casa"].pk,
        "cuenta": catalogo.nomina.pk,
        "persona": None,
        "domicilio": catalogo.fidel.pk,
        "es_hormiga": False,
        "metodo_pago": MetodoPago.TARJETA_DEBITO,
    }


def test_concepto_sin_valores_sugiere_efectivo(catalogo):
    sugeridos = valores_sugeridos(catalogo.gasolina)

    assert sugeridos["cuenta"] is None
    assert sugeridos["metodo_pago"] == MetodoPago.EFECTIVO


def test_borrar_desde_el_admin_devuelve_el_saldo(admin_client, catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    admin_client.post(
        reverse("admin:movimientos_movimiento_delete", args=[movimiento.pk]), {"post": "yes"}
    )

    assert saldo(catalogo.tarjeta) == D("6839.01")
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/movimientos/test_mov_servicios.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.movimientos.servicios'`.

- [ ] **Step 3: Implementar**

`apps/movimientos/servicios.py`:
```python
from django.db import transaction
from django.db.models import F

from apps.catalogos.models import Cuenta
from apps.movimientos.models import MetodoPago, Movimiento

METODO_POR_TIPO_DE_CUENTA = {
    Cuenta.Tipo.EFECTIVO: MetodoPago.EFECTIVO,
    Cuenta.Tipo.DEBITO: MetodoPago.TARJETA_DEBITO,
    Cuenta.Tipo.CREDITO: MetodoPago.TARJETA_CREDITO,
}


def metodo_para_cuenta(cuenta):
    if cuenta is None:
        return MetodoPago.EFECTIVO
    return METODO_POR_TIPO_DE_CUENTA.get(cuenta.tipo, MetodoPago.TRANSFERENCIA)


def valores_sugeridos(concepto):
    """RF-MOV-01: valores que el concepto precarga en la captura (todos opcionales)."""
    return {
        "categoria": concepto.categoria_id,
        "cuenta": concepto.cuenta_id,
        "persona": concepto.persona_id,
        "domicilio": concepto.domicilio_id,
        "es_hormiga": concepto.es_hormiga,
        "metodo_pago": metodo_para_cuenta(concepto.cuenta),
    }


@transaction.atomic
def guardar_movimiento(movimiento, usuario=None):
    """Valida y guarda. Aplica RN-14 revirtiendo antes el efecto anterior si ya existía."""
    movimiento.full_clean()
    if movimiento.pk:
        anterior = Movimiento.objects.select_for_update().get(pk=movimiento.pk)
        _aplicar_efecto(anterior, revertir=True)
    if usuario is not None and movimiento.creado_por_id is None:
        movimiento.creado_por = usuario
    movimiento.save()
    _aplicar_efecto(movimiento)
    return movimiento


@transaction.atomic
def eliminar_movimiento(movimiento):
    _aplicar_efecto(movimiento, revertir=True)
    movimiento.delete()


def _aplicar_efecto(movimiento, revertir=False):
    """RN-14: el pago de deuda reduce el saldo de la tarjeta o préstamo destino."""
    if movimiento.tipo != Movimiento.Tipo.PAGO_DEUDA:
        return
    cambio = movimiento.monto if revertir else -movimiento.monto
    Cuenta.objects.filter(pk=movimiento.cuenta_destino_id).update(
        saldo_actual=F("saldo_actual") + cambio
    )
```

`apps/movimientos/admin.py`:
```python
from django.contrib import admin

from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import eliminar_movimiento, guardar_movimiento


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "descripcion", "categoria", "monto", "metodo_pago", "cuenta")
    list_filter = ("hogar", "tipo", "metodo_pago", "categoria")
    search_fields = ("descripcion", "notas")
    date_hierarchy = "fecha"

    def save_model(self, request, obj, form, change):
        guardar_movimiento(obj, usuario=request.user)

    def delete_model(self, request, obj):
        eliminar_movimiento(obj)

    def get_actions(self, request):
        # El borrado masivo no pasaría por eliminar_movimiento (RN-14).
        acciones = super().get_actions(request)
        acciones.pop("delete_selected", None)
        return acciones
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_mov_servicios.py` 10 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/movimientos tests/movimientos/test_mov_servicios.py
git commit -m "feat(movimientos): guardar y eliminar aplicando RN-14, valores sugeridos del concepto y admin" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Captura rápida (P3)

**Files:**
- Create: `apps/movimientos/formularios.py`, `apps/movimientos/vistas.py`, `apps/movimientos/urls.py`
- Create: `templates/movimientos/_captura.html`, `templates/movimientos/_campos_sugeridos.html`, `templates/movimientos/captura.html`
- Modify: `apps/catalogos/models.py` (`Concepto.nombre_con_categoria`), `finanzas/urls.py`, `templates/componentes/navegacion.html`
- Test: `tests/movimientos/test_mov_captura.py`

**Interfaces:**
- Consumes: `FormularioDeHogar`, `requiere_hogar`, `es_htmx`, `datos_actualizados`, `componentes/campo.html` (Tasks 2–3); `Movimiento`, `INGRESOS_EXTRAORDINARIOS`, `TIPOS_DEUDA`, `MetodoPago` (Task 4); `guardar_movimiento`, `valores_sugeridos` (Task 5).
- Produces:
  - `apps.movimientos.formularios`: `FormularioMovimiento` (base: atributos `tipo`, `metodo_inicial`, `campos_sugeridos`; métodos `principales()` y `sugeridos()` que devuelven listas de campos), `FormularioGasto`, `FormularioIngreso`, `FormularioTransferencia`, `FormularioPagoDeuda`, `FORMULARIOS: dict[tipo, clase]`. Todos reciben `hogar=` y fijan `instance.tipo`.
  - Vistas `movimientos:capturar` (`/movimientos/capturar/<tipo>/`, GET/POST) y `movimientos:sugeridos` (`/movimientos/sugeridos/?concepto=<id>`). Helpers internos `_formulario(request, formulario, tipo, tipos, titulo)` y `_guardado(request, movimiento)`, que la Task 8 reutiliza.
  - Plantilla `movimientos/_captura.html` (variables: `titulo`, `tipos` o `None`, `tipo`, `formulario`, `accion`), reutilizada por la Task 8 para editar.
  - `Concepto.nombre_con_categoria` (propiedad): `"🚓 Transporte › Gasolina"`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/movimientos/test_mov_captura.py`:
```python
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria, Concepto
from apps.movimientos.models import Movimiento

pytestmark = pytest.mark.django_db

URL = "/movimientos/capturar/{}/"
HTMX = {"HX-Request": "true"}


def gasto_minimo(concepto, monto="650"):
    return {"monto": monto, "concepto": concepto.pk, "fecha": "2026-10-09", "metodo_pago": "efectivo"}


def concepto_ajeno(otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Ajena")
    return Concepto.objects.create(hogar=otro_hogar, categoria=ajena, nombre="Concepto ajeno")


def test_captura_muestra_los_cuatro_tipos_y_solo_conceptos_del_hogar(cliente, catalogo, otro_hogar):
    concepto_ajeno(otro_hogar)

    respuesta = cliente.get(URL.format("gasto"), headers=HTMX)

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    for etiqueta in ("Gasto", "Ingreso", "Transferencia", "Pago de deuda"):
        assert etiqueta in contenido
    assert "Transporte › Gasolina" in contenido
    assert "Concepto ajeno" not in contenido


def test_gasto_rapido_con_monto_y_concepto(cliente, catalogo, usuario):
    respuesta = cliente.post(URL.format("gasto"), gasto_minimo(catalogo.gasolina), headers=HTMX)

    assert respuesta.status_code == 204
    assert respuesta["HX-Trigger"] == "datosActualizados"
    movimiento = Movimiento.objects.get()
    assert movimiento.categoria == catalogo.categorias["Transporte"]
    assert movimiento.descripcion == "Gasolina"
    assert movimiento.creado_por == usuario
    assert movimiento.hogar == catalogo.gasolina.hogar


def test_errores_se_muestran_en_el_modal(cliente, catalogo):
    respuesta = cliente.post(
        URL.format("gasto"), gasto_minimo(catalogo.gasolina, monto=""), headers=HTMX
    )

    assert respuesta.status_code == 200
    assert "monto" in respuesta.context["formulario"].errors
    assert not Movimiento.objects.exists()


def test_concepto_de_otro_hogar_es_rechazado(cliente, catalogo, otro_hogar):
    respuesta = cliente.post(
        URL.format("gasto"), gasto_minimo(concepto_ajeno(otro_hogar)), headers=HTMX
    )

    assert respuesta.status_code == 200
    assert "concepto" in respuesta.context["formulario"].errors
    assert not Movimiento.objects.exists()


def test_campos_sugeridos_al_elegir_concepto(cliente, catalogo):
    respuesta = cliente.get(
        "/movimientos/sugeridos/", {"concepto": catalogo.luz_fidel.pk}, headers=HTMX
    )

    formulario = respuesta.context["formulario"]
    assert formulario["cuenta"].value() == catalogo.nomina.pk
    assert formulario["domicilio"].value() == catalogo.fidel.pk
    assert formulario["metodo_pago"].value() == "tarjeta_debito"


def test_campos_sugeridos_con_concepto_ajeno_o_invalido(cliente, catalogo, otro_hogar):
    ajeno = concepto_ajeno(otro_hogar)

    assert cliente.get("/movimientos/sugeridos/", {"concepto": ajeno.pk}).status_code == 404
    respuesta = cliente.get("/movimientos/sugeridos/", {"concepto": "abc"})
    assert respuesta.status_code == 200
    assert respuesta.context["formulario"]["cuenta"].value() is None


def test_ingreso_de_aguinaldo_extraordinario(cliente, catalogo):
    respuesta = cliente.post(
        URL.format("ingreso"),
        {
            "monto": "20000",
            "tipo_ingreso": "aguinaldo",
            "es_extraordinario": "on",
            "fecha": "2026-12-15",
            "metodo_pago": "transferencia",
            "cuenta": catalogo.nomina.pk,
        },
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    ingreso = Movimiento.objects.get()
    assert ingreso.tipo == Movimiento.Tipo.INGRESO
    assert ingreso.es_extraordinario
    assert ingreso.descripcion == "Aguinaldo"


def test_formulario_de_ingreso_sabe_cuales_son_extraordinarios(cliente, catalogo):
    contenido = cliente.get(URL.format("ingreso"), headers=HTMX).content.decode()

    assert 'data-extraordinarios="aguinaldo ptu bono beca prestamo_recibido"' in contenido


def test_pago_de_deuda_solo_ofrece_tarjetas_y_prestamos(cliente, catalogo):
    respuesta = cliente.get(URL.format("pago_deuda"), headers=HTMX)

    destinos = set(respuesta.context["formulario"].fields["cuenta_destino"].queryset)
    assert destinos == {catalogo.tarjeta, catalogo.prestamo}


def test_pago_de_deuda_reduce_el_saldo(cliente, catalogo):
    cliente.post(
        URL.format("pago_deuda"),
        {
            "monto": "1000",
            "fecha": "2026-10-09",
            "cuenta": catalogo.nomina.pk,
            "cuenta_destino": catalogo.tarjeta.pk,
            "metodo_pago": "transferencia",
        },
        headers=HTMX,
    )

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("5839.01")


def test_tipo_desconocido_da_404(cliente):
    assert cliente.get(URL.format("otro")).status_code == 404


def test_sin_htmx_redirige_tras_guardar(cliente, catalogo):
    respuesta = cliente.post(URL.format("gasto"), gasto_minimo(catalogo.gasolina))

    assert respuesta.status_code == 302


def test_captura_requiere_sesion(client):
    assert client.get(URL.format("gasto")).status_code == 302
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/movimientos/test_mov_captura.py -v`
Expected: FAIL con 404 en `/movimientos/...`.

- [ ] **Step 3: Formularios**

En `apps/catalogos/models.py`, dentro de `Concepto`, después de `__str__`:
```python
    @property
    def nombre_con_categoria(self):
        return f"{self.categoria} › {self}"
```

`apps/movimientos/formularios.py`:
```python
from django import forms
from django.urls import reverse
from django.utils import timezone

from apps.core.formularios import FormularioDeHogar
from apps.movimientos.models import INGRESOS_EXTRAORDINARIOS, TIPOS_DEUDA, MetodoPago, Movimiento


class FormularioMovimiento(FormularioDeHogar):
    tipo = None
    metodo_inicial = MetodoPago.EFECTIVO
    campos_sugeridos = ()

    class Meta:
        model = Movimiento
        fields = []
        widgets = {
            "monto": forms.NumberInput(
                attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal", "autofocus": True}
            ),
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo = self.tipo
        if not self.instance.pk:
            self.initial.setdefault("fecha", timezone.localdate())
            self.initial.setdefault("metodo_pago", self.metodo_inicial)

    def principales(self):
        return [campo for campo in self if campo.name not in self.campos_sugeridos]

    def sugeridos(self):
        return [campo for campo in self if campo.name in self.campos_sugeridos]


class FormularioGasto(FormularioMovimiento):
    tipo = Movimiento.Tipo.GASTO
    campos_sugeridos = ("metodo_pago", "cuenta", "persona", "domicilio", "es_hormiga")

    class Meta(FormularioMovimiento.Meta):
        fields = [
            "monto", "concepto", "categoria", "fecha", "descripcion", "notas",
            "metodo_pago", "cuenta", "persona", "domicilio", "es_hormiga",
        ]  # fmt: skip

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        concepto = self.fields["concepto"]
        concepto.queryset = concepto.queryset.select_related("categoria")
        concepto.label_from_instance = lambda c: c.nombre_con_categoria
        concepto.widget.attrs.update(
            {
                "hx-get": reverse("movimientos:sugeridos"),
                "hx-target": "#campos-sugeridos",
                "hx-trigger": "change",
                "hx-include": "this",
            }
        )
        self.fields["categoria"].help_text = "Si eliges un concepto, se usa su categoría."


class FormularioIngreso(FormularioMovimiento):
    tipo = Movimiento.Tipo.INGRESO
    metodo_inicial = MetodoPago.TRANSFERENCIA

    class Meta(FormularioMovimiento.Meta):
        fields = [
            "monto", "tipo_ingreso", "es_extraordinario", "fecha", "descripcion",
            "metodo_pago", "cuenta", "persona", "notas",
        ]  # fmt: skip
        labels = {"cuenta": "Cuenta destino"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipo_ingreso = self.fields["tipo_ingreso"]
        tipo_ingreso.required = True
        tipo_ingreso.widget.attrs["data-extraordinarios"] = " ".join(INGRESOS_EXTRAORDINARIOS)
        self.fields["es_extraordinario"].help_text = (
            "Aguinaldo, PTU, bonos…: cuentan en el ingreso real del mes, no en el promedio."
        )


class FormularioTransferencia(FormularioMovimiento):
    tipo = Movimiento.Tipo.TRANSFERENCIA
    metodo_inicial = MetodoPago.TRANSFERENCIA

    class Meta(FormularioMovimiento.Meta):
        fields = ["monto", "fecha", "cuenta", "cuenta_destino", "descripcion", "metodo_pago", "notas"]
        labels = {"cuenta": "De la cuenta", "cuenta_destino": "A la cuenta"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cuenta"].required = True
        self.fields["cuenta_destino"].required = True


class FormularioPagoDeuda(FormularioTransferencia):
    tipo = Movimiento.Tipo.PAGO_DEUDA

    class Meta(FormularioTransferencia.Meta):
        labels = {"cuenta": "Pagar desde", "cuenta_destino": "Tarjeta o préstamo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        destino = self.fields["cuenta_destino"]
        destino.queryset = destino.queryset.filter(tipo__in=TIPOS_DEUDA)


FORMULARIOS = {
    formulario.tipo: formulario
    for formulario in (
        FormularioGasto,
        FormularioIngreso,
        FormularioTransferencia,
        FormularioPagoDeuda,
    )
}
```

- [ ] **Step 4: Vistas, URLs y plantillas**

`apps/movimientos/vistas.py`:
```python
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalogos.models import Concepto
from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx
from apps.movimientos.formularios import FORMULARIOS, FormularioGasto
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento, valores_sugeridos


@requiere_hogar
def capturar(request, tipo):
    Formulario = FORMULARIOS.get(tipo)
    if Formulario is None:
        raise Http404("Tipo de movimiento desconocido")
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        movimiento = guardar_movimiento(formulario.save(commit=False), usuario=request.user)
        return _guardado(request, movimiento)
    return _formulario(request, formulario, tipo, Movimiento.Tipo.choices, "Registrar")


@requiere_hogar
def sugeridos(request):
    """Campos que precarga el concepto elegido (se pide al cambiar el concepto)."""
    valor = request.GET.get("concepto", "")
    iniciales = {}
    if valor.isdigit():
        concepto = get_object_or_404(Concepto.objects.del_hogar(request.hogar), pk=valor)
        iniciales = valores_sugeridos(concepto)
    formulario = FormularioGasto(hogar=request.hogar, initial=iniciales)
    return render(request, "movimientos/_campos_sugeridos.html", {"formulario": formulario})


def _formulario(request, formulario, tipo, tipos, titulo):
    contexto = {
        "formulario": formulario,
        "tipo": tipo,
        "tipos": tipos,
        "titulo": titulo,
        "accion": request.path,
    }
    plantilla = "movimientos/_captura.html" if es_htmx(request) else "movimientos/captura.html"
    return render(request, plantilla, contexto)


def _guardado(request, movimiento):
    if es_htmx(request):
        return datos_actualizados()
    messages.success(request, "Movimiento guardado.")
    return redirect("inicio")
```

`apps/movimientos/urls.py`:
```python
from django.urls import path

from apps.movimientos import vistas

app_name = "movimientos"

urlpatterns = [
    path("capturar/<str:tipo>/", vistas.capturar, name="capturar"),
    path("sugeridos/", vistas.sugeridos, name="sugeridos"),
]
```

En `finanzas/urls.py`, antes de `path("", include("apps.core.urls")),`:
```python
    path("movimientos/", include("apps.movimientos.urls")),
```

`templates/movimientos/_captura.html`:
```html
<div class="p-4">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="text-lg font-semibold">{{ titulo }}</h2>
    <button type="button" class="px-2 text-slate-500" data-cerrar-modal aria-label="Cerrar">✕</button>
  </div>
  {% if tipos %}
    <nav class="mb-4 grid grid-cols-2 gap-1 text-center text-sm sm:grid-cols-4">
      {% for valor, etiqueta in tipos %}
        <a href="{% url 'movimientos:capturar' valor %}" hx-get="{% url 'movimientos:capturar' valor %}" hx-target="#modal-contenido"
           class="rounded-lg px-2 py-1 {% if valor == tipo %}bg-emerald-600 text-white{% else %}bg-slate-100{% endif %}">{{ etiqueta }}</a>
      {% endfor %}
    </nav>
  {% endif %}
  <form method="post" action="{{ accion }}" hx-post="{{ accion }}" hx-target="#modal-contenido" class="space-y-3">
    {% csrf_token %}
    {% if formulario.non_field_errors %}<div class="rounded bg-red-50 p-2 text-sm text-red-700">{{ formulario.non_field_errors }}</div>{% endif %}
    {% for campo in formulario.principales %}{% include "componentes/campo.html" %}{% endfor %}
    {% if formulario.campos_sugeridos %}
      <fieldset id="campos-sugeridos" class="space-y-3 rounded-lg border border-slate-200 p-3">
        {% include "movimientos/_campos_sugeridos.html" %}
      </fieldset>
    {% endif %}
    <button type="submit" class="boton w-full">Guardar</button>
  </form>
</div>
```

`templates/movimientos/_campos_sugeridos.html`:
```html
<legend class="px-1 text-xs text-slate-500">Se precargan desde el concepto; puedes cambiarlos</legend>
{% for campo in formulario.sugeridos %}{% include "componentes/campo.html" %}{% endfor %}
```

`templates/movimientos/captura.html` (la misma captura como página completa, por si no hay JavaScript):
```html
{% extends "base.html" %}
{% block titulo %}{{ titulo }}{% endblock %}
{% block contenido %}<div class="tarjeta mx-auto max-w-md p-0">{% include "movimientos/_captura.html" %}</div>{% endblock %}
```

`templates/componentes/navegacion.html`: después del enlace "Inicio", agregar el botón **+**:
```html
  <button type="button" hx-get="{% url 'movimientos:capturar' 'gasto' %}" hx-target="#modal-contenido" aria-label="Registrar movimiento"
          class="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600 text-2xl text-white shadow md:h-auto md:w-full md:justify-start md:gap-2 md:rounded-lg md:px-2 md:py-1 md:text-base">+<span class="hidden md:inline">Registrar</span></button>
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_mov_captura.py` 13 passed; todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps finanzas/urls.py templates tests/movimientos/test_mov_captura.py
git commit -m "feat(movimientos): captura rapida de gastos, ingresos, transferencias y pagos con valores sugeridos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Consultas del mes: filtros y totales (MOV-04, MOV-06)

**Files:**
- Create: `apps/core/fechas.py`, `apps/movimientos/consultas.py`
- Modify: `apps/movimientos/formularios.py` (agregar `FormularioFiltros`)
- Test: `tests/core/test_core_fechas.py`, `tests/movimientos/test_mov_consultas.py`

**Interfaces:**
- Consumes: `Movimiento`, `MetodoPago` (Task 4); `guardar_movimiento` (Task 5).
- Produces:
  - `apps.core.fechas`: `validar_mes(anio, mes)` (lanza `ValueError` si el mes no está en 1–12 o el año no está en 2000–2100), `rango_del_mes(anio, mes) -> (date, date)`, `rango_del_anio(anio) -> (date, date)`, `mes_anterior(anio, mes) -> (int, int)`, `mes_siguiente(anio, mes) -> (int, int)`, `nombre_mes(anio, mes) -> "Octubre 2026"`.
  - `apps.movimientos.consultas`: `Filtros` (dataclass congelada: `tipo=""`, `categoria=None`, `persona=None`, `domicilio=None`, `cuenta=None`, `metodo_pago=""`, `texto=""`), `movimientos_entre(hogar, inicio, fin, filtros=Filtros()) -> QuerySet`, `movimientos_del_mes(hogar, anio, mes, filtros=Filtros()) -> QuerySet`, `Totales` (`ingresos`, `ingresos_extra`, `gastos`, `por_categoria: list[(Categoria, Decimal)]`, `por_metodo: list[(str, Decimal)]`, `por_cuenta: list[(str, Decimal)]`, propiedad `disponible`) y `totales(movimientos) -> Totales`.
  - `apps.movimientos.formularios.FormularioFiltros(data, hogar=)` con `filtros() -> Filtros`; ignora los valores inválidos (por ejemplo, ids de otro hogar).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/core/test_core_fechas.py`:
```python
from datetime import date

import pytest

from apps.core.fechas import (
    mes_anterior,
    mes_siguiente,
    nombre_mes,
    rango_del_anio,
    rango_del_mes,
    validar_mes,
)


def test_rango_del_mes_incluye_el_ultimo_dia():
    assert rango_del_mes(2026, 10) == (date(2026, 10, 1), date(2026, 10, 31))
    assert rango_del_mes(2028, 2) == (date(2028, 2, 1), date(2028, 2, 29))


def test_rango_del_anio():
    assert rango_del_anio(2026) == (date(2026, 1, 1), date(2026, 12, 31))


def test_navegacion_entre_anios():
    assert mes_anterior(2026, 1) == (2025, 12)
    assert mes_siguiente(2026, 12) == (2027, 1)
    assert mes_siguiente(2026, 10) == (2026, 11)


def test_nombre_del_mes():
    assert nombre_mes(2026, 10) == "Octubre 2026"


@pytest.mark.parametrize(("anio", "mes"), [(2026, 0), (2026, 13), (1999, 5), (2101, 1)])
def test_mes_fuera_de_rango(anio, mes):
    with pytest.raises(ValueError):
        validar_mes(anio, mes)
```

`tests/movimientos/test_mov_consultas.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria, Persona
from apps.movimientos.consultas import Filtros, movimientos_del_mes, totales
from apps.movimientos.formularios import FormularioFiltros
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db


def registrar(hogar, **campos):
    campos.setdefault("fecha", date(2026, 10, 10))
    campos["monto"] = D(campos["monto"])
    return guardar_movimiento(Movimiento(hogar=hogar, **campos))


def gasto(catalogo, monto, **campos):
    campos.setdefault("concepto", catalogo.gasolina)
    return registrar(catalogo.gasolina.hogar, tipo=Movimiento.Tipo.GASTO, monto=monto, **campos)


def test_solo_movimientos_del_mes_y_del_hogar(catalogo, otro_hogar):
    for dia, monto in [(date(2026, 9, 30), "100"), (date(2026, 10, 1), "200"),
                       (date(2026, 10, 31), "300"), (date(2026, 11, 1), "400")]:  # fmt: skip
        gasto(catalogo, monto, fecha=dia)
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    registrar(otro_hogar, tipo=Movimiento.Tipo.GASTO, monto="999", categoria=ajena)

    montos = sorted(m.monto for m in movimientos_del_mes(catalogo.gasolina.hogar, 2026, 10))

    assert montos == [D("200"), D("300")]


def test_filtros_por_persona_domicilio_cuenta_metodo_y_tipo(catalogo):
    hogar = catalogo.gasolina.hogar
    de_monze = gasto(catalogo, "10", persona=catalogo.monze)
    en_fidel = gasto(catalogo, "20", domicilio=catalogo.fidel, cuenta=catalogo.efectivo)
    con_tarjeta = gasto(catalogo, "30", metodo_pago=MetodoPago.TARJETA_CREDITO)
    pago = registrar(
        hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto="40",
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.tarjeta,
        metodo_pago=MetodoPago.TRANSFERENCIA,
    )

    def filtrar(**campos):
        return list(movimientos_del_mes(hogar, 2026, 10, Filtros(**campos)))

    assert filtrar(persona=catalogo.monze) == [de_monze]
    assert filtrar(domicilio=catalogo.fidel) == [en_fidel]
    assert filtrar(cuenta=catalogo.tarjeta) == [pago]
    assert filtrar(metodo_pago=MetodoPago.TARJETA_CREDITO) == [con_tarjeta]
    assert filtrar(tipo=Movimiento.Tipo.PAGO_DEUDA) == [pago]


def test_busqueda_por_texto_sin_distinguir_mayusculas(catalogo):
    pemex = gasto(catalogo, "10", descripcion="Carga Pemex")
    recarga = gasto(catalogo, "20", concepto=catalogo.recarga, descripcion="Telcel")
    hogar = catalogo.gasolina.hogar

    assert list(movimientos_del_mes(hogar, 2026, 10, Filtros(texto="pemex"))) == [pemex]
    assert list(movimientos_del_mes(hogar, 2026, 10, Filtros(texto="RECARGA"))) == [recarga]


def test_totales_separan_ingresos_extra_y_excluyen_transferencias_y_pagos(catalogo):
    hogar = catalogo.gasolina.hogar
    gasto(catalogo, "1500", cuenta=catalogo.efectivo)
    gasto(
        catalogo,
        "450",
        concepto=catalogo.luz_fidel,
        cuenta=catalogo.nomina,
        metodo_pago=MetodoPago.TARJETA_DEBITO,
    )
    ingreso = {"tipo": Movimiento.Tipo.INGRESO, "metodo_pago": MetodoPago.TRANSFERENCIA}
    registrar(hogar, monto="15000", tipo_ingreso=TipoIngreso.SALARIO, **ingreso)
    registrar(
        hogar, monto="20000", tipo_ingreso=TipoIngreso.AGUINALDO, es_extraordinario=True, **ingreso
    )
    registrar(
        hogar,
        tipo=Movimiento.Tipo.TRANSFERENCIA,
        monto="3000",
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.efectivo,
    )
    registrar(
        hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto="1000",
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.tarjeta,
    )

    t = totales(movimientos_del_mes(hogar, 2026, 10))

    assert t.ingresos == D("35000")
    assert t.ingresos_extra == D("20000")
    assert t.gastos == D("1950")
    assert t.disponible == D("33050")
    assert t.por_categoria == [
        (catalogo.categorias["Casa"], D("450")),
        (catalogo.categorias["Transporte"], D("1500")),
    ]
    assert t.por_metodo == [("Efectivo", D("1500")), ("Tarjeta de débito", D("450"))]
    assert t.por_cuenta == [("Efectivo", D("1500")), ("Nómina", D("450"))]


def test_totales_de_un_mes_vacio(hogar):
    t = totales(Movimiento.objects.none())

    assert (t.ingresos, t.ingresos_extra, t.gastos, t.disponible) == (0, 0, 0, 0)
    assert t.por_categoria == t.por_metodo == t.por_cuenta == []


def test_filtros_ignoran_ids_de_otro_hogar(catalogo, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    formulario = FormularioFiltros(
        {"persona": ajena.pk, "texto": "luz"}, hogar=catalogo.monze.hogar
    )

    assert formulario.filtros() == Filtros(texto="luz")


def test_filtros_sin_datos(catalogo):
    assert FormularioFiltros(None, hogar=catalogo.monze.hogar).filtros() == Filtros()
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/core/test_core_fechas.py tests/movimientos/test_mov_consultas.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.core.fechas'` (y `apps.movimientos.consultas`).

- [ ] **Step 3: Implementar**

`apps/core/fechas.py`:
```python
"""Meses del calendario: rangos, navegación y nombres (el mes financiero es el calendario)."""

import calendar
from datetime import date

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]  # fmt: skip
ANIO_MINIMO, ANIO_MAXIMO = 2000, 2100


def validar_mes(anio, mes):
    if not (1 <= mes <= 12 and ANIO_MINIMO <= anio <= ANIO_MAXIMO):
        raise ValueError(f"Mes fuera de rango: {anio}-{mes}")


def rango_del_mes(anio, mes):
    validar_mes(anio, mes)
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def rango_del_anio(anio):
    validar_mes(anio, 1)
    return date(anio, 1, 1), date(anio, 12, 31)


def mes_anterior(anio, mes):
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def mes_siguiente(anio, mes):
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def nombre_mes(anio, mes):
    return f"{MESES[mes - 1].capitalize()} {anio}"
```

`apps/movimientos/consultas.py`:
```python
"""Consultas de lectura de movimientos: filtros (RF-MOV-04) y totales (RF-MOV-06)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q, Sum

from apps.calculos.comun import CERO
from apps.catalogos.models import Categoria, Cuenta, Domicilio, Persona
from apps.core.fechas import rango_del_mes
from apps.movimientos.models import MetodoPago, Movimiento


@dataclass(frozen=True)
class Filtros:
    tipo: str = ""
    categoria: Categoria | None = None
    persona: Persona | None = None
    domicilio: Domicilio | None = None
    cuenta: Cuenta | None = None
    metodo_pago: str = ""
    texto: str = ""


@dataclass(frozen=True)
class Totales:
    ingresos: Decimal
    ingresos_extra: Decimal
    gastos: Decimal
    por_categoria: list
    por_metodo: list
    por_cuenta: list

    @property
    def disponible(self):
        """RN-15: ingresos reales (con extraordinarios) − gastos reales."""
        return self.ingresos - self.gastos


def movimientos_entre(hogar, inicio, fin, filtros=Filtros()):
    consulta = (
        Movimiento.objects.del_hogar(hogar)
        .filter(fecha__range=(inicio, fin))
        .select_related(
            "categoria", "concepto", "cuenta", "cuenta_destino", "persona", "domicilio"
        )
    )
    for campo in ("tipo", "categoria", "persona", "domicilio", "metodo_pago"):
        valor = getattr(filtros, campo)
        if valor:
            consulta = consulta.filter(**{campo: valor})
    if filtros.cuenta:
        consulta = consulta.filter(Q(cuenta=filtros.cuenta) | Q(cuenta_destino=filtros.cuenta))
    if filtros.texto:
        texto = filtros.texto
        consulta = consulta.filter(
            Q(descripcion__icontains=texto)
            | Q(notas__icontains=texto)
            | Q(concepto__nombre__icontains=texto)
        )
    return consulta


def movimientos_del_mes(hogar, anio, mes, filtros=Filtros()):
    inicio, fin = rango_del_mes(anio, mes)
    return movimientos_entre(hogar, inicio, fin, filtros)


def totales(movimientos):
    """Totales del mes; transferencias y pagos de deuda son neutrales (RN-14)."""
    gastos = movimientos.filter(tipo=Movimiento.Tipo.GASTO).order_by()
    ingresos = movimientos.filter(tipo=Movimiento.Tipo.INGRESO).order_by()
    por_categoria = _agrupar(gastos, "categoria")
    categorias = Categoria.objects.in_bulk([i for i in por_categoria if i is not None])
    por_cuenta = _agrupar(gastos, "cuenta")
    cuentas = Cuenta.objects.in_bulk([i for i in por_cuenta if i is not None])
    return Totales(
        ingresos=_suma(ingresos),
        ingresos_extra=_suma(ingresos.filter(es_extraordinario=True)),
        gastos=_suma(gastos),
        por_categoria=sorted(
            ((categorias[i], total) for i, total in por_categoria.items() if i is not None),
            key=lambda par: (par[0].orden, par[0].nombre),
        ),
        por_metodo=_ordenar(
            (MetodoPago(metodo).label, total)
            for metodo, total in _agrupar(gastos, "metodo_pago").items()
        ),
        por_cuenta=_ordenar(
            (cuentas[i].nombre if i else "Sin cuenta", total) for i, total in por_cuenta.items()
        ),
    )


def _suma(consulta):
    return consulta.aggregate(total=Sum("monto"))["total"] or CERO


def _agrupar(consulta, campo):
    filas = consulta.values(campo).annotate(total=Sum("monto"))
    return {fila[campo]: fila["total"] for fila in filas}


def _ordenar(pares):
    return sorted(pares, key=lambda par: (-par[1], par[0]))
```

En `apps/movimientos/formularios.py`, agregar a los imports:
```python
from apps.catalogos.models import Categoria, Cuenta, Domicilio, Persona
from apps.movimientos.consultas import Filtros
```
y al final:
```python
class FormularioFiltros(forms.Form):
    texto = forms.CharField(label="Buscar", required=False)
    tipo = forms.ChoiceField(choices=[("", "Todos"), *Movimiento.Tipo.choices], required=False)
    categoria = forms.ModelChoiceField(Categoria.objects.none(), required=False, label="Categoría")
    persona = forms.ModelChoiceField(Persona.objects.none(), required=False)
    domicilio = forms.ModelChoiceField(Domicilio.objects.none(), required=False)
    cuenta = forms.ModelChoiceField(Cuenta.objects.none(), required=False)
    metodo_pago = forms.ChoiceField(
        choices=[("", "Todos"), *MetodoPago.choices], required=False, label="Método de pago"
    )

    def __init__(self, *args, hogar, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, modelo in [("categoria", Categoria), ("persona", Persona),
                               ("domicilio", Domicilio), ("cuenta", Cuenta)]:  # fmt: skip
            self.fields[nombre].queryset = modelo.objects.del_hogar(hogar)

    def filtros(self):
        """Filtros válidos; los inválidos (p. ej. ids de otro hogar) se ignoran."""
        if not self.is_bound:
            return Filtros()
        self.is_valid()
        return Filtros(**self.cleaned_data)
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_core_fechas.py` 8 passed, `test_mov_consultas.py` 7 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/core/fechas.py apps/movimientos tests/core/test_core_fechas.py tests/movimientos/test_mov_consultas.py
git commit -m "feat(movimientos): filtros, busqueda y totales del mes por categoria, metodo y cuenta" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Lista de movimientos (P4): filtros, totales, edición, borrado y CSV

**Files:**
- Modify: `apps/movimientos/vistas.py`, `apps/movimientos/urls.py`, `templates/componentes/navegacion.html`
- Create: `templates/movimientos/lista.html`
- Test: `tests/movimientos/test_mov_lista.py`

**Interfaces:**
- Consumes: `FORMULARIOS`, `FormularioFiltros`, `_formulario`, `_guardado` (Tasks 6–7); `movimientos_entre`, `totales` (Task 7); `guardar_movimiento`, `eliminar_movimiento` (Task 5); `apps.core.fechas` (Task 7).
- Produces: rutas `movimientos:inicio` (`/movimientos/` → mes actual), `movimientos:lista` (`/movimientos/<anio>/<mes>/`), `movimientos:editar` (`/movimientos/<pk>/editar/`), `movimientos:eliminar` (`/movimientos/<pk>/eliminar/`, solo POST), `movimientos:csv_mes` (`/movimientos/<anio>/<mes>/csv/`), `movimientos:csv_anio` (`/movimientos/<anio>/csv/`). Tras guardar sin HTMX se vuelve a la lista del mes del movimiento.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/movimientos/test_mov_lista.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.catalogos.models import Categoria
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def registrar(hogar, **campos):
    campos.setdefault("fecha", date(2026, 10, 5))
    campos["monto"] = D(campos["monto"])
    return guardar_movimiento(Movimiento(hogar=hogar, **campos))


def gasto(catalogo, monto="650", **campos):
    campos.setdefault("concepto", catalogo.gasolina)
    return registrar(catalogo.gasolina.hogar, tipo=Movimiento.Tipo.GASTO, monto=monto, **campos)


def pago(catalogo, monto="1000"):
    return registrar(
        catalogo.tarjeta.hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto=monto,
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.tarjeta,
        metodo_pago=MetodoPago.TRANSFERENCIA,
    )


def test_lista_del_mes_con_totales(cliente, catalogo):
    gasto(catalogo)
    registrar(
        catalogo.nomina.hogar,
        tipo=Movimiento.Tipo.INGRESO,
        tipo_ingreso=TipoIngreso.SALARIO,
        monto="15000",
        fecha=date(2026, 10, 15),
    )
    gasto(catalogo, "999", fecha=date(2026, 9, 30))

    respuesta = cliente.get("/movimientos/2026/10/")

    contenido = respuesta.content.decode()
    assert "Octubre 2026" in contenido
    assert "$650.00" in contenido
    assert "$15,000.00" in contenido
    assert "$999.00" not in contenido
    assert respuesta.context["totales"].gastos == D("650")


def test_lista_aplica_los_filtros(cliente, catalogo):
    de_monze = gasto(catalogo, "10", persona=catalogo.monze)
    gasto(catalogo, "20")

    respuesta = cliente.get("/movimientos/2026/10/", {"persona": catalogo.monze.pk})

    assert list(respuesta.context["movimientos"]) == [de_monze]


def test_movimientos_redirige_al_mes_actual(cliente):
    hoy = timezone.localdate()

    respuesta = cliente.get("/movimientos/")

    assert respuesta.url == f"/movimientos/{hoy.year}/{hoy.month}/"


def test_mes_invalido_da_404(cliente):
    assert cliente.get("/movimientos/2026/13/").status_code == 404


def test_navegacion_de_diciembre_a_enero(cliente):
    contenido = cliente.get("/movimientos/2026/12/").content.decode()

    assert "/movimientos/2027/1/" in contenido
    assert "/movimientos/2026/11/" in contenido


def test_formulario_de_edicion_muestra_los_datos(cliente, catalogo):
    movimiento = gasto(catalogo)

    respuesta = cliente.get(f"/movimientos/{movimiento.pk}/editar/", headers=HTMX)

    assert respuesta.status_code == 200
    assert 'value="650.00"' in respuesta.content.decode()


def test_editar_un_gasto(cliente, catalogo):
    movimiento = gasto(catalogo)

    respuesta = cliente.post(
        f"/movimientos/{movimiento.pk}/editar/",
        {
            "monto": "700",
            "concepto": catalogo.gasolina.pk,
            "fecha": "2026-10-05",
            "metodo_pago": "efectivo",
        },
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    movimiento.refresh_from_db()
    assert movimiento.monto == D("700")


def test_editar_un_pago_de_deuda_ajusta_el_saldo(cliente, catalogo):
    movimiento = pago(catalogo)

    cliente.post(
        f"/movimientos/{movimiento.pk}/editar/",
        {
            "monto": "1200",
            "fecha": "2026-10-05",
            "cuenta": catalogo.nomina.pk,
            "cuenta_destino": catalogo.tarjeta.pk,
            "metodo_pago": "transferencia",
        },
        headers=HTMX,
    )

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("5639.01")


def test_eliminar_un_pago_de_deuda_devuelve_el_saldo(cliente, catalogo):
    movimiento = pago(catalogo)

    respuesta = cliente.post(f"/movimientos/{movimiento.pk}/eliminar/", headers=HTMX)

    assert respuesta.status_code == 204
    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")
    assert not Movimiento.objects.exists()


def test_eliminar_requiere_post(cliente, catalogo):
    movimiento = gasto(catalogo)

    assert cliente.get(f"/movimientos/{movimiento.pk}/eliminar/").status_code == 405


def test_movimiento_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    ajeno = registrar(otro_hogar, tipo=Movimiento.Tipo.GASTO, monto="10", categoria=ajena)

    assert cliente.get(f"/movimientos/{ajeno.pk}/editar/").status_code == 404
    assert cliente.post(f"/movimientos/{ajeno.pk}/eliminar/").status_code == 404
    assert Movimiento.objects.filter(pk=ajeno.pk).exists()


def test_exportar_csv_del_mes(cliente, catalogo):
    gasto(catalogo)

    respuesta = cliente.get("/movimientos/2026/10/csv/")

    assert respuesta["Content-Type"].startswith("text/csv")
    assert "movimientos-2026-10.csv" in respuesta["Content-Disposition"]
    lineas = respuesta.content.decode("utf-8-sig").splitlines()
    assert lineas[0].startswith("fecha,tipo,descripción")
    assert "Gasolina" in lineas[1]
    assert "650.00" in lineas[1]


def test_exportar_csv_del_anio(cliente, catalogo):
    gasto(catalogo, fecha=date(2026, 3, 1))
    gasto(catalogo, fecha=date(2026, 10, 1))
    gasto(catalogo, fecha=date(2025, 12, 31))

    respuesta = cliente.get("/movimientos/2026/csv/")

    assert len(respuesta.content.decode("utf-8-sig").splitlines()) == 3
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/movimientos/test_mov_lista.py -v`
Expected: FAIL con 404 en las rutas nuevas.

- [ ] **Step 3: Vistas y URLs**

En `apps/movimientos/vistas.py`, agregar a los imports:
```python
import csv

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.fechas import mes_anterior, mes_siguiente, nombre_mes, rango_del_anio, rango_del_mes
from apps.movimientos.consultas import movimientos_entre, totales
from apps.movimientos.formularios import FormularioFiltros
from apps.movimientos.servicios import eliminar_movimiento
```
en `_guardado`, reemplazar `return redirect("inicio")` por:
```python
    return redirect("movimientos:lista", movimiento.fecha.year, movimiento.fecha.month)
```
y agregar al final:
```python
ENCABEZADOS_CSV = [
    "fecha", "tipo", "descripción", "categoría", "concepto", "monto", "método de pago",
    "cuenta", "cuenta destino", "persona", "domicilio", "hormiga", "extraordinario",
    "tipo de ingreso",
]  # fmt: skip


@requiere_hogar
def inicio(request):
    hoy = timezone.localdate()
    return redirect("movimientos:lista", hoy.year, hoy.month)


@requiere_hogar
def lista(request, anio, mes):
    try:
        inicio_mes, fin_mes = rango_del_mes(anio, mes)
    except ValueError as error:
        raise Http404 from error
    filtros = FormularioFiltros(request.GET or None, hogar=request.hogar)
    movimientos = movimientos_entre(request.hogar, inicio_mes, fin_mes, filtros.filtros())
    resumen = totales(movimientos)
    contexto = {
        "anio": anio,
        "mes": mes,
        "titulo": nombre_mes(anio, mes),
        "anterior": mes_anterior(anio, mes),
        "siguiente": mes_siguiente(anio, mes),
        "consulta": request.GET.urlencode(),
        "filtros": filtros,
        "movimientos": movimientos,
        "totales": resumen,
        "tablas": [
            ("Gastos por categoría", [(str(c), t) for c, t in resumen.por_categoria]),
            ("Por método de pago", resumen.por_metodo),
            ("Por cuenta", resumen.por_cuenta),
        ],
    }
    return render(request, "movimientos/lista.html", contexto)


@requiere_hogar
def editar(request, pk):
    movimiento = get_object_or_404(Movimiento.objects.del_hogar(request.hogar), pk=pk)
    Formulario = FORMULARIOS[movimiento.tipo]
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, instance=movimiento, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        return _guardado(request, guardar_movimiento(formulario.save(commit=False)))
    return _formulario(request, formulario, movimiento.tipo, None, "Editar movimiento")


@requiere_hogar
@require_POST
def eliminar(request, pk):
    movimiento = get_object_or_404(Movimiento.objects.del_hogar(request.hogar), pk=pk)
    eliminar_movimiento(movimiento)
    if es_htmx(request):
        return datos_actualizados()
    messages.success(request, "Movimiento eliminado.")
    return redirect("movimientos:lista", movimiento.fecha.year, movimiento.fecha.month)


@requiere_hogar
def exportar_csv(request, anio, mes=None):
    """RF-MOV-07: movimientos del mes o del año (con los filtros activos) en CSV."""
    try:
        inicio_rango, fin_rango = rango_del_mes(anio, mes) if mes else rango_del_anio(anio)
    except ValueError as error:
        raise Http404 from error
    filtros = FormularioFiltros(request.GET or None, hogar=request.hogar).filtros()
    movimientos = movimientos_entre(request.hogar, inicio_rango, fin_rango, filtros)
    nombre = f"movimientos-{anio}-{mes:02d}.csv" if mes else f"movimientos-{anio}.csv"
    respuesta = HttpResponse(
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
    respuesta.write("﻿")  # BOM: Excel abre los acentos correctamente
    escritor = csv.writer(respuesta)
    escritor.writerow(ENCABEZADOS_CSV)
    for m in movimientos.order_by("fecha", "id"):
        escritor.writerow(
            [
                m.fecha.isoformat(), m.get_tipo_display(), m.descripcion,
                m.categoria.nombre if m.categoria else "", m.concepto or "", m.monto,
                m.get_metodo_pago_display(), m.cuenta or "", m.cuenta_destino or "",
                m.persona or "", m.domicilio or "", "sí" if m.es_hormiga else "no",
                "sí" if m.es_extraordinario else "no", m.get_tipo_ingreso_display(),
            ]  # fmt: skip
        )
    return respuesta
```

`apps/movimientos/urls.py` (lista completa):
```python
urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path("capturar/<str:tipo>/", vistas.capturar, name="capturar"),
    path("sugeridos/", vistas.sugeridos, name="sugeridos"),
    path("<int:anio>/<int:mes>/", vistas.lista, name="lista"),
    path("<int:anio>/<int:mes>/csv/", vistas.exportar_csv, name="csv_mes"),
    path("<int:anio>/csv/", vistas.exportar_csv, name="csv_anio"),
    path("<int:pk>/editar/", vistas.editar, name="editar"),
    path("<int:pk>/eliminar/", vistas.eliminar, name="eliminar"),
]
```

- [ ] **Step 4: Plantilla y navegación**

`templates/movimientos/lista.html`:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Movimientos · {{ titulo }}{% endblock %}
{% block contenido %}
<header class="mb-4 flex items-center justify-between gap-2">
  <a class="boton-secundario" href="{% url 'movimientos:lista' anterior.0 anterior.1 %}?{{ consulta }}" aria-label="Mes anterior">‹</a>
  <h1 class="text-lg font-semibold">{{ titulo }}</h1>
  <a class="boton-secundario" href="{% url 'movimientos:lista' siguiente.0 siguiente.1 %}?{{ consulta }}" aria-label="Mes siguiente">›</a>
</header>

<details class="tarjeta mb-4" {% if consulta %}open{% endif %}>
  <summary class="cursor-pointer font-medium">Filtros y búsqueda</summary>
  <form method="get" class="mt-3 grid gap-3 sm:grid-cols-2">
    {% for campo in filtros %}{% include "componentes/campo.html" %}{% endfor %}
    <div class="flex gap-2 sm:col-span-2">
      <button class="boton">Aplicar</button>
      <a class="boton-secundario" href="{{ request.path }}">Limpiar</a>
    </div>
  </form>
</details>

<section class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Ingresos</p>
    <p class="font-semibold text-emerald-700">{{ totales.ingresos|dinero }}</p>
    {% if totales.ingresos_extra %}<p class="text-xs text-slate-500">incluye {{ totales.ingresos_extra|dinero }} extra</p>{% endif %}
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Gastos</p>
    <p class="font-semibold text-red-600">{{ totales.gastos|dinero }}</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Disponible</p>
    <p class="font-semibold">{{ totales.disponible|dinero }}</p>
  </div>
  <div class="tarjeta text-sm">
    <p class="text-xs text-slate-500">Exportar CSV</p>
    <a class="text-sky-700" href="{% url 'movimientos:csv_mes' anio mes %}?{{ consulta }}">del mes</a> ·
    <a class="text-sky-700" href="{% url 'movimientos:csv_anio' anio %}?{{ consulta }}">del año</a>
  </div>
</section>

<section class="space-y-2">
  {% for m in movimientos %}
    <article class="tarjeta flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="truncate font-medium">{{ m.descripcion }}</p>
        <p class="text-xs text-slate-500">{{ m.fecha|date:"d M" }} · {{ m.get_tipo_display }}{% if m.categoria %} · {{ m.categoria }}{% endif %}{% if m.persona %} · {{ m.persona }}{% endif %}{% if m.domicilio %} · {{ m.domicilio }}{% endif %}{% if m.es_hormiga %} · 🐜{% endif %}{% if m.es_extraordinario %} · extra{% endif %}</p>
        <p class="text-xs text-slate-500">{{ m.get_metodo_pago_display }}{% if m.cuenta %} · {{ m.cuenta }}{% endif %}{% if m.cuenta_destino %} → {{ m.cuenta_destino }}{% endif %}</p>
      </div>
      <div class="shrink-0 text-right">
        <p class="font-semibold {% if m.tipo == 'gasto' %}text-red-600{% elif m.tipo == 'ingreso' %}text-emerald-700{% else %}text-slate-500{% endif %}">{% if m.tipo == 'gasto' %}-{% elif m.tipo == 'ingreso' %}+{% endif %}{{ m.monto|dinero }}</p>
        <div class="mt-1 flex justify-end gap-3 text-xs">
          <button type="button" class="text-sky-700" hx-get="{% url 'movimientos:editar' m.pk %}" hx-target="#modal-contenido">Editar</button>
          <button type="button" class="text-red-600" hx-post="{% url 'movimientos:eliminar' m.pk %}" hx-confirm="¿Eliminar este movimiento?">Eliminar</button>
        </div>
      </div>
    </article>
  {% empty %}
    <p class="tarjeta text-slate-500">No hay movimientos en este mes.</p>
  {% endfor %}
</section>

<section class="mt-6 grid gap-3 md:grid-cols-3">
  {% for nombre_tabla, filas in tablas %}
    <div class="tarjeta">
      <h2 class="mb-2 font-medium">{{ nombre_tabla }}</h2>
      <table class="w-full text-sm">
        {% for etiqueta, total in filas %}
          <tr class="border-t border-slate-100"><td class="py-1">{{ etiqueta }}</td><td class="py-1 text-right">{{ total|dinero }}</td></tr>
        {% empty %}
          <tr><td class="text-slate-500">Sin gastos</td></tr>
        {% endfor %}
      </table>
    </div>
  {% endfor %}
</section>
{% endblock %}
```

`templates/componentes/navegacion.html`: entre el enlace "Inicio" y el botón **+**, agregar:
```html
  <a href="{% url 'movimientos:inicio' %}" class="flex flex-col items-center rounded-lg px-2 py-1 md:flex-row md:gap-2 hover:bg-slate-100"><span>📒</span><span>Movimientos</span></a>
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_mov_lista.py` 14 passed; `test_mov_captura.py` sigue verde (`test_sin_htmx_redirige_tras_guardar` ahora redirige a la lista del mes); todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/movimientos templates tests/movimientos/test_mov_lista.py
git commit -m "feat(movimientos): lista del mes con filtros, totales, edicion, borrado y exportacion CSV" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Presupuesto: modelos y servicios (PRE-02, PRE-03, PRE-04, PRE-05)

**Files:**
- Create: `apps/presupuesto/__init__.py` (vacío), `apps/presupuesto/apps.py`, `apps/presupuesto/models.py`, `apps/presupuesto/admin.py`, `apps/presupuesto/mensajes.py`, `apps/presupuesto/servicios.py`, `apps/presupuesto/migrations/__init__.py` (vacío), `apps/presupuesto/migrations/0001_initial.py` (generado)
- Modify: `finanzas/settings.py` (INSTALLED_APPS), `tests/conftest.py` (fixture `plantilla_excel`)
- Test: `tests/presupuesto/test_pre_servicios.py`

**Interfaces:**
- Consumes: `ModeloDeHogar`; `Concepto`, `Persona`, `DINERO`; `TipoIngreso` (Task 4); `apps.calculos.presupuesto` (`LineaIngreso`, `LineaGasto`, `resumir_presupuesto`, `ResumenPresupuesto`, `MENSUAL`, `ANUAL`); `redondear`; `validar_mes` (Task 7).
- Produces:
  - Modelos (todos con `hogar`): `PlantillaPresupuesto(porcentaje_ahorro)` (una por hogar), `PlantillaIngreso(plantilla, nombre, tipo_ingreso, es_fijo, monto, persona)`, `PlantillaGasto(plantilla, concepto, monto, periodicidad, es_fijo, con_tarjeta, es_hormiga)` con método `monto_mensual()`, `PresupuestoMes(anio, mes, porcentaje_ahorro, cerrado)`, `PresupuestoMesIngreso(presupuesto, nombre, tipo_ingreso, es_fijo, monto, persona)`, `PresupuestoMesGasto(presupuesto, concepto, monto_mensual, es_fijo, con_tarjeta, es_hormiga)`; `Periodicidad.MENSUAL|ANUAL`. Related names: `ingresos` y `gastos` en la plantilla y en el mes.
  - `apps.presupuesto.servicios`: `obtener_plantilla(hogar)`, `obtener_presupuesto_mes(hogar, anio, mes)` (crea el mes copiando la plantilla; `ValueError` si el mes es inválido), `resincronizar_mes(presupuesto)`, `resumen_plantilla(plantilla) -> ResumenPresupuesto`, `ingresos_del_mes(presupuesto, persona=None, domicilio=None)`, `gastos_del_mes(presupuesto, persona=None, domicilio=None)` (QuerySets), `resumen_mes(presupuesto, persona=None, domicilio=None) -> ResumenPresupuesto`.
  - `apps.presupuesto.mensajes`: `mensaje_ahorro(porcentaje) -> str`, `mensaje_disponible(disponible, meta) -> (nivel, texto)` con `BIEN|CUIDADO|ALERTA`, `mensaje_recorte(recorte_necesario) -> str` (textos del Excel).
  - Fixture `plantilla_excel` (en `tests/conftest.py`): plantilla del hogar con el ingreso de 32,977.52 y los 28 renglones de gasto del Excel en sus categorías (nombres ficticios "Casa 1", "Comida 2", …).

- [ ] **Step 1: Fixture del presupuesto del Excel**

En `tests/conftest.py`, agregar después de los imports:
```python
# Renglones del presupuesto del Excel 2026 del usuario (montos y marcas; nombres ficticios).
# Marcas: F = fijo, T = con tarjeta, H = hormiga.
RENGLONES_EXCEL = {
    "Casa": [("200", "F"), ("100", ""), ("1500", "F"), ("1100", "F"), ("500", "F"),
             ("500", "F"), ("100", "F")],
    "Comida": [("3000", "F"), ("3000", "F"), ("1600", "F"), ("2000", "F"), ("600", "H"),
               ("400", "H")],
    "Familia": [("4641", "F"), ("800", "F")],
    "Transporte": [("1400", "F"), ("1000", "F")],
    "Deudas": [("1500", "F"), ("2000", "F")],
    "Salud": [("1000", "F")],
    "Suscripciones": [("239", "TH"), ("10", "T"), ("49", "T"), ("196", "F")],
    "Entretenimiento": [("500", "H")],
    "Otros": [("300", "F"), ("500", "TH"), ("500", "TH")],
}  # fmt: skip
```
y al final:
```python
@pytest.fixture
def plantilla_excel(hogar):
    """Plantilla con los valores del Excel: ingresos 32,977.52 y gastos 29,235."""
    from apps.presupuesto.models import PlantillaGasto, PlantillaIngreso
    from apps.presupuesto.servicios import obtener_plantilla

    sembrar_catalogos(hogar)
    plantilla = obtener_plantilla(hogar)
    PlantillaIngreso.objects.create(
        hogar=hogar,
        plantilla=plantilla,
        nombre="Salario mensual (neto)",
        tipo_ingreso="salario",
        monto=D("32977.52"),
    )
    for nombre_categoria, renglones in RENGLONES_EXCEL.items():
        categoria = Categoria.objects.get(hogar=hogar, nombre=nombre_categoria)
        for numero, (monto, marcas) in enumerate(renglones, start=1):
            concepto = Concepto.objects.create(
                hogar=hogar, categoria=categoria, nombre=f"{nombre_categoria} {numero}"
            )
            PlantillaGasto.objects.create(
                hogar=hogar,
                plantilla=plantilla,
                concepto=concepto,
                monto=D(monto),
                es_fijo="F" in marcas,
                con_tarjeta="T" in marcas,
                es_hormiga="H" in marcas,
            )
    return plantilla
```

- [ ] **Step 2: Escribir las pruebas que fallan**

`tests/presupuesto/test_pre_servicios.py`:
```python
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.calculos.comun import redondear
from apps.catalogos.models import Categoria, Concepto
from apps.presupuesto.mensajes import (
    ALERTA,
    BIEN,
    CUIDADO,
    mensaje_ahorro,
    mensaje_disponible,
    mensaje_recorte,
)
from apps.presupuesto.models import (
    Periodicidad,
    PlantillaGasto,
    PlantillaIngreso,
    PresupuestoMes,
    PresupuestoMesGasto,
)
from apps.presupuesto.servicios import (
    gastos_del_mes,
    obtener_plantilla,
    obtener_presupuesto_mes,
    resincronizar_mes,
    resumen_mes,
    resumen_plantilla,
)

pytestmark = pytest.mark.django_db


def test_una_plantilla_por_hogar(hogar):
    plantilla = obtener_plantilla(hogar)

    assert obtener_plantilla(hogar) == plantilla
    assert plantilla.porcentaje_ahorro == D("0.05")


def test_resumen_de_la_plantilla_reproduce_el_excel(plantilla_excel):
    r = resumen_plantilla(plantilla_excel)

    assert r.ingresos_totales == D("32977.52")
    assert r.gastos_totales == D("29235")
    assert r.gastos_fijos == D("26337")
    assert r.gastos_variables == D("2898")
    assert r.disponible == D("3742.52")
    assert r.meta_ahorro == D("1648.876")
    assert r.presupuesto_hormiga == D("2739")
    assert redondear(r.maximo_diario_hormiga) == D("91.30")
    assert r.recorte_necesario is None
    assert r.gasto_con_tarjeta == D("1298")


def test_el_mes_se_crea_copiando_la_plantilla(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    assert octubre.gastos.count() == 28
    assert octubre.ingresos.count() == 1
    assert octubre.porcentaje_ahorro == D("0.05")
    assert resumen_mes(octubre) == resumen_plantilla(plantilla_excel)


def test_consultar_de_nuevo_no_duplica_ni_pisa_ajustes(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)
    renglon = octubre.gastos.first()
    renglon.monto_mensual = D("1")
    renglon.save()

    otra_vez = obtener_presupuesto_mes(hogar, 2026, 10)

    assert otra_vez.pk == octubre.pk
    assert otra_vez.gastos.count() == 28
    renglon.refresh_from_db()
    assert renglon.monto_mensual == D("1")


def test_ajustar_un_mes_no_afecta_la_plantilla_ni_otros_meses(plantilla_excel, hogar):
    obtener_presupuesto_mes(hogar, 2026, 10).gastos.update(monto_mensual=D("0"))

    noviembre = obtener_presupuesto_mes(hogar, 2026, 11)

    assert resumen_mes(noviembre).gastos_totales == D("29235")
    assert resumen_plantilla(plantilla_excel).gastos_totales == D("29235")


def test_cambios_en_la_plantilla_solo_aplican_a_meses_nuevos(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    plantilla_excel.gastos.update(monto=D("0"))

    assert resumen_mes(octubre).gastos_totales == D("29235")
    assert resumen_mes(obtener_presupuesto_mes(hogar, 2026, 11)).gastos_totales == D("0")


def test_resincronizar_reemplaza_el_mes(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)
    octubre.gastos.all().delete()
    octubre.porcentaje_ahorro = D("0.20")
    octubre.save()

    resincronizar_mes(octubre)

    octubre.refresh_from_db()
    assert octubre.gastos.count() == 28
    assert octubre.porcentaje_ahorro == D("0.05")


def test_gasto_anual_se_prorratea_en_el_mes(hogar, catalogo):
    plantilla = obtener_plantilla(hogar)
    seguro = Concepto.objects.create(
        hogar=hogar, categoria=catalogo.categorias["Gastos anuales"], nombre="Seguro del auto"
    )
    PlantillaGasto.objects.create(
        hogar=hogar,
        plantilla=plantilla,
        concepto=seguro,
        monto=D("1000"),
        periodicidad=Periodicidad.ANUAL,
    )

    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    assert octubre.gastos.get().monto_mensual == D("83.33")
    assert resumen_plantilla(plantilla).gastos_totales == D("1000") / 12


def test_mes_invalido(hogar):
    with pytest.raises(ValueError):
        obtener_presupuesto_mes(hogar, 2026, 13)


def test_concepto_de_otro_hogar_en_la_plantilla_es_invalido(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    concepto_ajeno = Concepto.objects.create(hogar=otro_hogar, categoria=ajena, nombre="Luz")
    renglon = PlantillaGasto(
        hogar=hogar, plantilla=obtener_plantilla(hogar), concepto=concepto_ajeno, monto=D("1")
    )

    with pytest.raises(ValidationError) as error:
        renglon.full_clean()

    assert "concepto" in error.value.message_dict


def test_filtros_por_domicilio_y_persona(hogar, catalogo):
    plantilla = obtener_plantilla(hogar)
    catalogo.gasolina.persona = catalogo.monze
    catalogo.gasolina.save()
    for concepto, monto in [(catalogo.luz_fidel, "500"), (catalogo.gasolina, "1400")]:
        PlantillaGasto.objects.create(
            hogar=hogar, plantilla=plantilla, concepto=concepto, monto=D(monto)
        )
    PlantillaIngreso.objects.create(hogar=hogar, plantilla=plantilla, nombre="Salario", monto=D("20000"))
    PlantillaIngreso.objects.create(
        hogar=hogar,
        plantilla=plantilla,
        nombre="Beca",
        tipo_ingreso="beca",
        monto=D("1000"),
        persona=catalogo.monze,
    )
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    en_fidel = resumen_mes(octubre, domicilio=catalogo.fidel)
    de_monze = resumen_mes(octubre, persona=catalogo.monze)

    assert (en_fidel.gastos_totales, en_fidel.ingresos_totales) == (D("500"), D("0"))
    assert (de_monze.gastos_totales, de_monze.ingresos_totales) == (D("1400"), D("1000"))
    conceptos = [g.concepto for g in gastos_del_mes(octubre, domicilio=catalogo.fidel)]
    assert conceptos == [catalogo.luz_fidel]


def test_mensajes_del_porcentaje_de_ahorro():
    assert mensaje_ahorro(D("0")).startswith("Podrías ahorrar más")
    assert mensaje_ahorro(D("0.05")).startswith("Podrías ahorrar más")
    assert mensaje_ahorro(D("0.12")).startswith("Este es un buen porcentaje")
    assert mensaje_ahorro(D("0.15")).startswith("¡Buena meta de ahorro!")
    assert mensaje_ahorro(D("0.20")).startswith("¡Muy bien")
    assert mensaje_ahorro(D("0.50")).startswith("¡Genial!")


def test_mensaje_del_disponible():
    assert mensaje_disponible(D("3742.52"), D("1648.876"))[0] == BIEN
    assert mensaje_disponible(D("1000"), D("1648.876"))[0] == CUIDADO
    assert mensaje_disponible(D("-5"), D("10"))[0] == ALERTA
    assert mensaje_disponible(D("0"), D("0"))[0] == BIEN


def test_mensaje_del_recorte():
    assert mensaje_recorte(None).startswith("👏¡Bien!")
    assert mensaje_recorte(D("10")).startswith("⚠️Considera recortar")


def test_borrar_el_hogar_borra_su_presupuesto(plantilla_excel, hogar):
    obtener_presupuesto_mes(hogar, 2026, 10)

    hogar.delete()

    assert not PresupuestoMes.objects.exists()
    assert not PresupuestoMesGasto.objects.exists()
```

- [ ] **Step 3: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/presupuesto/test_pre_servicios.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.presupuesto'`.

- [ ] **Step 4: Modelos y admin**

`apps/presupuesto/apps.py`:
```python
from django.apps import AppConfig


class PresupuestoConfig(AppConfig):
    name = "apps.presupuesto"
    verbose_name = "Presupuesto"
```

`apps/presupuesto/models.py`:
```python
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.calculos.presupuesto import ANUAL, MENSUAL, LineaGasto
from apps.catalogos.models import DINERO, Concepto, Persona
from apps.core.models import ModeloDeHogar
from apps.movimientos.models import TipoIngreso

NO_NEGATIVO = [MinValueValidator(Decimal("0"))]
PORCENTAJE = {
    "max_digits": 5,
    "decimal_places": 4,
    "validators": [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
}


class Periodicidad(models.TextChoices):
    MENSUAL = MENSUAL, "Mensual"
    ANUAL = ANUAL, "Anual"


class RenglonIngreso(ModeloDeHogar):
    nombre = models.CharField(max_length=80)
    tipo_ingreso = models.CharField(
        "tipo de ingreso", max_length=20, choices=TipoIngreso.choices, default=TipoIngreso.SALARIO
    )
    es_fijo = models.BooleanField("fijo", default=True)
    monto = models.DecimalField(validators=NO_NEGATIVO, **DINERO)
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True
        ordering = ["-monto", "nombre"]

    def __str__(self):
        return self.nombre


class RenglonGasto(ModeloDeHogar):
    concepto = models.ForeignKey(Concepto, on_delete=models.RESTRICT, related_name="+")
    es_fijo = models.BooleanField("fijo", default=False)
    con_tarjeta = models.BooleanField("con tarjeta", default=False)
    es_hormiga = models.BooleanField("hormiga 🐜", default=False)

    class Meta:
        abstract = True
        ordering = ["concepto__categoria__orden", "concepto__nombre"]

    def __str__(self):
        return str(self.concepto)


class PlantillaPresupuesto(ModeloDeHogar):
    porcentaje_ahorro = models.DecimalField(
        "% de ahorro", default=Decimal("0.05"), **PORCENTAJE
    )

    class Meta:
        verbose_name = "plantilla de presupuesto"
        verbose_name_plural = "plantillas de presupuesto"
        constraints = [models.UniqueConstraint(fields=["hogar"], name="plantilla_unica_por_hogar")]

    def __str__(self):
        return f"Plantilla de {self.hogar}"


class PlantillaIngreso(RenglonIngreso):
    plantilla = models.ForeignKey(
        PlantillaPresupuesto, on_delete=models.CASCADE, related_name="ingresos"
    )

    class Meta(RenglonIngreso.Meta):
        verbose_name = "ingreso de la plantilla"
        verbose_name_plural = "ingresos de la plantilla"


class PlantillaGasto(RenglonGasto):
    plantilla = models.ForeignKey(
        PlantillaPresupuesto, on_delete=models.CASCADE, related_name="gastos"
    )
    monto = models.DecimalField(validators=NO_NEGATIVO, **DINERO)
    periodicidad = models.CharField(
        max_length=7, choices=Periodicidad.choices, default=Periodicidad.MENSUAL
    )

    class Meta(RenglonGasto.Meta):
        verbose_name = "gasto de la plantilla"
        verbose_name_plural = "gastos de la plantilla"
        constraints = [
            models.UniqueConstraint(fields=["plantilla", "concepto"], name="plantilla_gasto_unico")
        ]

    def monto_mensual(self):
        """RN-03: anual → monto / 12."""
        return LineaGasto(monto=self.monto, periodicidad=self.periodicidad).monto_mensual()


class PresupuestoMes(ModeloDeHogar):
    anio = models.PositiveSmallIntegerField("año")
    mes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    porcentaje_ahorro = models.DecimalField("% de ahorro", **PORCENTAJE)
    cerrado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "presupuesto del mes"
        verbose_name_plural = "presupuestos del mes"
        ordering = ["-anio", "-mes"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "anio", "mes"], name="presupuesto_mes_unico")
        ]

    def __str__(self):
        return f"Presupuesto {self.mes:02d}/{self.anio}"


class PresupuestoMesIngreso(RenglonIngreso):
    presupuesto = models.ForeignKey(
        PresupuestoMes, on_delete=models.CASCADE, related_name="ingresos"
    )

    class Meta(RenglonIngreso.Meta):
        verbose_name = "ingreso del mes"
        verbose_name_plural = "ingresos del mes"


class PresupuestoMesGasto(RenglonGasto):
    presupuesto = models.ForeignKey(PresupuestoMes, on_delete=models.CASCADE, related_name="gastos")
    monto_mensual = models.DecimalField("monto mensual", validators=NO_NEGATIVO, **DINERO)

    class Meta(RenglonGasto.Meta):
        verbose_name = "gasto del mes"
        verbose_name_plural = "gastos del mes"
        constraints = [
            models.UniqueConstraint(
                fields=["presupuesto", "concepto"], name="presupuesto_mes_gasto_unico"
            )
        ]
```

`apps/presupuesto/admin.py`:
```python
from django.contrib import admin

from apps.presupuesto.models import (
    PlantillaGasto,
    PlantillaIngreso,
    PlantillaPresupuesto,
    PresupuestoMes,
    PresupuestoMesGasto,
    PresupuestoMesIngreso,
)


class PlantillaIngresoInline(admin.TabularInline):
    model = PlantillaIngreso
    extra = 0
    exclude = ("hogar",)


class PlantillaGastoInline(admin.TabularInline):
    model = PlantillaGasto
    extra = 0
    exclude = ("hogar",)


@admin.register(PlantillaPresupuesto)
class PlantillaPresupuestoAdmin(admin.ModelAdmin):
    list_display = ("hogar", "porcentaje_ahorro")
    inlines = [PlantillaIngresoInline, PlantillaGastoInline]

    def save_formset(self, request, form, formset, change):
        for renglon in formset.save(commit=False):
            renglon.hogar = form.instance.hogar
            renglon.save()
        for renglon in formset.deleted_objects:
            renglon.delete()


class PresupuestoMesIngresoInline(admin.TabularInline):
    model = PresupuestoMesIngreso
    extra = 0
    exclude = ("hogar",)


class PresupuestoMesGastoInline(admin.TabularInline):
    model = PresupuestoMesGasto
    extra = 0
    exclude = ("hogar",)


@admin.register(PresupuestoMes)
class PresupuestoMesAdmin(admin.ModelAdmin):
    list_display = ("hogar", "anio", "mes", "porcentaje_ahorro", "cerrado")
    list_filter = ("hogar", "anio")
    inlines = [PresupuestoMesIngresoInline, PresupuestoMesGastoInline]
    save_formset = PlantillaPresupuestoAdmin.save_formset
```

- [ ] **Step 5: Mensajes y servicios**

`apps/presupuesto/mensajes.py`:
```python
"""Mensajes del Excel (hojas Presupuesto y Mis Finanzas), con rangos para cualquier %."""

from decimal import Decimal

BIEN, CUIDADO, ALERTA = "bien", "cuidado", "alerta"

# (desde qué % aplica, mensaje); se evalúan de mayor a menor.
MENSAJES_AHORRO = [
    (
        Decimal("0.25"),
        "¡Genial! Ahora toca hacerlo crecer. Revisa las mejores oportunidades de inversión 📈",
    ),
    (Decimal("0.20"), "¡Muy bien, este es un ahorro ideal! 🎯"),
    (Decimal("0.15"), "¡Buena meta de ahorro! Tu yo del futuro te lo agradecerá 💰"),
    (Decimal("0.10"), "Este es un buen porcentaje. ¡Ten disciplina para lograrlo! ✏️"),
    (Decimal("0"), "Podrías ahorrar más, evalúa tus gastos y mejora tus finanzas. ¡Tú puedes! 💪"),
]


def mensaje_ahorro(porcentaje):
    for desde, mensaje in MENSAJES_AHORRO:
        if porcentaje >= desde:
            return mensaje
    return MENSAJES_AHORRO[-1][1]


def mensaje_disponible(disponible, meta):
    if disponible >= meta:
        return BIEN, (
            "👏¡Felicidades!, tu disponible al final del mes es suficiente para lograr "
            "tus metas de ahorro."
        )
    if disponible > 0:
        return CUIDADO, (
            "⚠️Cuidado, lo que te resta al final del mes no es suficiente para llegar a "
            "tu meta de ahorro mensual."
        )
    return ALERTA, (
        "⛔¡Tus gastos son mayores a tus ingresos! Es momento de evaluar qué gastos hay que evitar."
    )


def mensaje_recorte(recorte_necesario):
    if recorte_necesario is None:
        return "👏¡Bien! Puedes lograr tus metas de ahorro y hasta darte un gustito 🐜"
    return (
        "⚠️Considera recortar gastos para lograr tus metas de ahorro "
        "(tip: comienza con tus gastos hormiga)."
    )
```

`apps/presupuesto/servicios.py`:
```python
from django.db import transaction

from apps.calculos.comun import redondear
from apps.calculos.presupuesto import LineaGasto, LineaIngreso, resumir_presupuesto
from apps.core.fechas import validar_mes
from apps.presupuesto.models import (
    PlantillaPresupuesto,
    PresupuestoMes,
    PresupuestoMesGasto,
    PresupuestoMesIngreso,
)


def obtener_plantilla(hogar):
    plantilla, _ = PlantillaPresupuesto.objects.get_or_create(hogar=hogar)
    return plantilla


@transaction.atomic
def obtener_presupuesto_mes(hogar, anio, mes):
    """RF-PRE-03: la primera consulta de un mes lo crea copiando la plantilla."""
    validar_mes(anio, mes)
    plantilla = obtener_plantilla(hogar)
    presupuesto, creado = PresupuestoMes.objects.get_or_create(
        hogar=hogar,
        anio=anio,
        mes=mes,
        defaults={"porcentaje_ahorro": plantilla.porcentaje_ahorro},
    )
    if creado:
        _copiar_plantilla(plantilla, presupuesto)
    return presupuesto


@transaction.atomic
def resincronizar_mes(presupuesto):
    """RF-PRE-04: reemplaza el presupuesto del mes por la plantilla actual."""
    plantilla = obtener_plantilla(presupuesto.hogar)
    presupuesto.ingresos.all().delete()
    presupuesto.gastos.all().delete()
    presupuesto.porcentaje_ahorro = plantilla.porcentaje_ahorro
    presupuesto.save(update_fields=["porcentaje_ahorro", "actualizado_en"])
    _copiar_plantilla(plantilla, presupuesto)


def _copiar_plantilla(plantilla, presupuesto):
    hogar = presupuesto.hogar
    PresupuestoMesIngreso.objects.bulk_create(
        PresupuestoMesIngreso(
            hogar=hogar,
            presupuesto=presupuesto,
            nombre=i.nombre,
            tipo_ingreso=i.tipo_ingreso,
            es_fijo=i.es_fijo,
            monto=i.monto,
            persona_id=i.persona_id,
        )
        for i in plantilla.ingresos.all()
    )
    PresupuestoMesGasto.objects.bulk_create(
        PresupuestoMesGasto(
            hogar=hogar,
            presupuesto=presupuesto,
            concepto_id=g.concepto_id,
            monto_mensual=redondear(g.monto_mensual()),
            es_fijo=g.es_fijo,
            con_tarjeta=g.con_tarjeta,
            es_hormiga=g.es_hormiga,
        )
        for g in plantilla.gastos.all()
    )


def resumen_plantilla(plantilla):
    """RN-01 a RN-04 sobre la plantilla (con el prorrateo anual exacto)."""
    return resumir_presupuesto(
        [LineaIngreso(monto=i.monto, es_fijo=i.es_fijo) for i in plantilla.ingresos.all()],
        [
            LineaGasto(
                monto=g.monto,
                periodicidad=g.periodicidad,
                es_fijo=g.es_fijo,
                con_tarjeta=g.con_tarjeta,
                es_hormiga=g.es_hormiga,
            )
            for g in plantilla.gastos.all()
        ],
        plantilla.porcentaje_ahorro,
    )


def ingresos_del_mes(presupuesto, persona=None, domicilio=None):
    """Un domicilio no tiene ingresos; por persona, solo los suyos."""
    if domicilio is not None:
        return presupuesto.ingresos.none()
    ingresos = presupuesto.ingresos.all()
    return ingresos.filter(persona=persona) if persona is not None else ingresos


def gastos_del_mes(presupuesto, persona=None, domicilio=None):
    """Gastos presupuestados; persona y domicilio se toman del concepto."""
    gastos = presupuesto.gastos.select_related("concepto__categoria")
    if persona is not None:
        gastos = gastos.filter(concepto__persona=persona)
    if domicilio is not None:
        gastos = gastos.filter(concepto__domicilio=domicilio)
    return gastos


def resumen_mes(presupuesto, persona=None, domicilio=None):
    return resumir_presupuesto(
        [
            LineaIngreso(monto=i.monto, es_fijo=i.es_fijo)
            for i in ingresos_del_mes(presupuesto, persona, domicilio)
        ],
        [
            LineaGasto(
                monto=g.monto_mensual,
                es_fijo=g.es_fijo,
                con_tarjeta=g.con_tarjeta,
                es_hormiga=g.es_hormiga,
            )
            for g in gastos_del_mes(presupuesto, persona, domicilio)
        ],
        presupuesto.porcentaje_ahorro,
    )
```

En `finanzas/settings.py`, agregar `"apps.presupuesto",` después de `"apps.movimientos",` en `INSTALLED_APPS`.

- [ ] **Step 6: Generar la migración**

Run: `docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations presupuesto`
Expected: `apps/presupuesto/migrations/0001_initial.py` con `Create model` para `PlantillaPresupuesto`, `PlantillaIngreso`, `PlantillaGasto`, `PresupuestoMes`, `PresupuestoMesIngreso` y `PresupuestoMesGasto`.

- [ ] **Step 7: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_pre_servicios.py` 15 passed; todo verde.

- [ ] **Step 8: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/presupuesto finanzas/settings.py tests/conftest.py tests/presupuesto/test_pre_servicios.py
git commit -m "feat(presupuesto): plantilla, presupuesto mensual copiado de la plantilla, resumen y mensajes del Excel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Pantalla de presupuesto (P5)

**Files:**
- Create: `apps/presupuesto/formularios.py`, `apps/presupuesto/vistas.py`, `apps/presupuesto/urls.py`
- Create: `templates/presupuesto/pagina.html`, `templates/presupuesto/_resumen.html`, `templates/presupuesto/_acciones.html`, `templates/componentes/_formulario_modal.html`, `templates/componentes/pagina_formulario.html`
- Modify: `apps/core/htmx.py` (agregar `responder_formulario`), `finanzas/urls.py`, `templates/componentes/navegacion.html`
- Test: `tests/presupuesto/test_pre_vistas.py`

**Interfaces:**
- Consumes: servicios, modelos y mensajes de la Task 9; `FormularioDeHogar`, `requiere_hogar`, `datos_actualizados`, `es_htmx` (Tasks 2–3); `apps.core.fechas`; `Concepto.nombre_con_categoria` (Task 6).
- Produces:
  - `apps.core.htmx.responder_formulario(request, contexto) -> HttpResponse`: con HTMX dibuja `componentes/_formulario_modal.html` (para el modal); sin HTMX, `componentes/pagina_formulario.html` (página completa). El contexto lleva `formulario`, `titulo` y `accion`. Si el formulario tiene `secciones()`, las dibuja agrupadas (la Task 13 lo usa).
  - `apps.presupuesto.formularios`: `FormularioRenglon` (base: `contenedor_campo`, recibe `contenedor=`), `RENGLONES: dict[(ambito, clase), formulario]` con ámbitos `plantilla|mes` y clases `ingreso|gasto`, `FormularioPorcentaje` (0–100) con `fraccion()`.
  - Rutas `presupuesto:inicio` (`/presupuesto/` → mes actual), `presupuesto:plantilla`, `presupuesto:mes` (`/presupuesto/<anio>/<mes>/`), `presupuesto:nuevo_plantilla` (`/presupuesto/plantilla/<clase>/nuevo/`), `presupuesto:nuevo_mes` (`/presupuesto/<anio>/<mes>/<clase>/nuevo/`), `presupuesto:editar_renglon` (`/presupuesto/renglon/<ambito>/<clase>/<pk>/`), `presupuesto:eliminar_renglon` (`.../eliminar/`, POST), `presupuesto:porcentaje_plantilla`, `presupuesto:porcentaje_mes` (POST), `presupuesto:resincronizar` (POST).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/presupuesto/test_pre_vistas.py`:
```python
from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.presupuesto.models import PlantillaGasto, PlantillaIngreso
from apps.presupuesto.servicios import obtener_plantilla, obtener_presupuesto_mes, resumen_plantilla

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def gasto_de_plantilla(catalogo, monto="1400"):
    return {"concepto": catalogo.gasolina.pk, "monto": monto, "periodicidad": "mensual", "es_fijo": "on"}


def test_presupuesto_redirige_al_mes_actual(cliente):
    hoy = timezone.localdate()

    assert cliente.get("/presupuesto/").url == f"/presupuesto/{hoy.year}/{hoy.month}/"


def test_plantilla_muestra_el_resumen_del_excel(cliente, plantilla_excel):
    contenido = cliente.get("/presupuesto/plantilla/").content.decode()

    for valor in ("$32,977.52", "$29,235.00", "$3,742.52", "$1,648.88", "$2,739.00", "$91.30"):
        assert valor in contenido
    assert "Podrías ahorrar más" in contenido
    assert "¡Felicidades!" in contenido
    assert "N/A" in contenido


def test_mes_muestra_su_presupuesto(cliente, plantilla_excel):
    respuesta = cliente.get("/presupuesto/2026/10/")

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Octubre 2026" in contenido
    assert "$29,235.00" in contenido


def test_mes_invalido_da_404(cliente):
    assert cliente.get("/presupuesto/2026/13/").status_code == 404


def test_formulario_de_nuevo_renglon(cliente, catalogo):
    respuesta = cliente.get("/presupuesto/plantilla/ingreso/nuevo/", headers=HTMX)

    assert respuesta.status_code == 200
    assert 'name="nombre"' in respuesta.content.decode()


def test_agregar_gasto_a_la_plantilla(cliente, catalogo, hogar):
    respuesta = cliente.post(
        "/presupuesto/plantilla/gasto/nuevo/", gasto_de_plantilla(catalogo), headers=HTMX
    )

    assert respuesta.status_code == 204
    renglon = PlantillaGasto.objects.get()
    assert renglon.plantilla == obtener_plantilla(hogar)
    assert renglon.hogar == hogar
    assert renglon.es_fijo


def test_concepto_repetido_en_la_plantilla_es_error(cliente, catalogo):
    url = "/presupuesto/plantilla/gasto/nuevo/"
    cliente.post(url, gasto_de_plantilla(catalogo), headers=HTMX)

    respuesta = cliente.post(url, gasto_de_plantilla(catalogo, "1"), headers=HTMX)

    assert respuesta.status_code == 200
    assert "__all__" in respuesta.context["formulario"].errors
    assert PlantillaGasto.objects.count() == 1


def test_editar_renglon_del_mes_no_cambia_la_plantilla(cliente, plantilla_excel, hogar):
    renglon = obtener_presupuesto_mes(hogar, 2026, 10).gastos.first()

    respuesta = cliente.post(
        f"/presupuesto/renglon/mes/gasto/{renglon.pk}/",
        {"concepto": renglon.concepto_id, "monto_mensual": "1"},
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    renglon.refresh_from_db()
    assert renglon.monto_mensual == D("1")
    assert resumen_plantilla(plantilla_excel).gastos_totales == D("29235")


def test_eliminar_renglon(cliente, catalogo, hogar):
    renglon = PlantillaGasto.objects.create(
        hogar=hogar, plantilla=obtener_plantilla(hogar), concepto=catalogo.gasolina, monto=D("1")
    )

    respuesta = cliente.post(
        f"/presupuesto/renglon/plantilla/gasto/{renglon.pk}/eliminar/", headers=HTMX
    )

    assert respuesta.status_code == 204
    assert not PlantillaGasto.objects.exists()


def test_renglon_de_otro_hogar_da_404(cliente, otro_hogar):
    ajeno = PlantillaIngreso.objects.create(
        hogar=otro_hogar, plantilla=obtener_plantilla(otro_hogar), nombre="Ajeno", monto=D("1")
    )

    assert cliente.get(f"/presupuesto/renglon/plantilla/ingreso/{ajeno.pk}/").status_code == 404
    url_eliminar = f"/presupuesto/renglon/plantilla/ingreso/{ajeno.pk}/eliminar/"
    assert cliente.post(url_eliminar).status_code == 404
    assert PlantillaIngreso.objects.filter(pk=ajeno.pk).exists()


def test_clase_desconocida_da_404(cliente):
    assert cliente.get("/presupuesto/plantilla/otro/nuevo/").status_code == 404


def test_cambiar_el_porcentaje_de_ahorro(cliente, hogar):
    respuesta = cliente.post("/presupuesto/plantilla/porcentaje/", {"porcentaje": "10"})

    assert respuesta.status_code == 302
    assert obtener_plantilla(hogar).porcentaje_ahorro == D("0.10")


def test_porcentaje_fuera_de_rango_no_se_guarda(cliente, hogar):
    cliente.post("/presupuesto/plantilla/porcentaje/", {"porcentaje": "150"})

    assert obtener_plantilla(hogar).porcentaje_ahorro == D("0.05")


def test_porcentaje_del_mes_no_cambia_la_plantilla(cliente, hogar):
    cliente.post("/presupuesto/2026/10/porcentaje/", {"porcentaje": "20"})

    assert obtener_presupuesto_mes(hogar, 2026, 10).porcentaje_ahorro == D("0.20")
    assert obtener_plantilla(hogar).porcentaje_ahorro == D("0.05")


def test_resincronizar_el_mes(cliente, plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)
    octubre.gastos.all().delete()

    respuesta = cliente.post("/presupuesto/2026/10/resincronizar/")

    assert respuesta.status_code == 302
    assert octubre.gastos.count() == 28
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/presupuesto/test_pre_vistas.py -v`
Expected: FAIL con 404 en `/presupuesto/...`.

- [ ] **Step 3: Respuesta de formularios genérica**

En `apps/core/htmx.py`, agregar `from django.shortcuts import render` a los imports y al final:
```python
def responder_formulario(request, contexto):
    """Formulario dentro del modal (HTMX) o como página completa (sin JavaScript)."""
    plantilla = (
        "componentes/_formulario_modal.html"
        if es_htmx(request)
        else "componentes/pagina_formulario.html"
    )
    return render(request, plantilla, contexto)
```

`templates/componentes/_formulario_modal.html`:
```html
<div class="p-4">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="text-lg font-semibold">{{ titulo }}</h2>
    <button type="button" class="px-2 text-slate-500" data-cerrar-modal aria-label="Cerrar">✕</button>
  </div>
  <form method="post" action="{{ accion }}" hx-post="{{ accion }}" hx-target="#modal-contenido" class="space-y-3">
    {% csrf_token %}
    {% if formulario.non_field_errors %}<div class="rounded bg-red-50 p-2 text-sm text-red-700">{{ formulario.non_field_errors }}</div>{% endif %}
    {% if formulario.secciones %}
      {% for titulo_seccion, descripcion, campos in formulario.secciones %}
        <fieldset class="space-y-3 {% if titulo_seccion %}rounded-lg border border-slate-200 p-3{% endif %}">
          {% if titulo_seccion %}<legend class="px-1 text-sm font-medium">{{ titulo_seccion }}</legend>{% endif %}
          {% if descripcion %}<p class="text-xs text-slate-500">{{ descripcion }}</p>{% endif %}
          {% for campo in campos %}{% include "componentes/campo.html" %}{% endfor %}
        </fieldset>
      {% endfor %}
    {% else %}
      {% for campo in formulario %}{% include "componentes/campo.html" %}{% endfor %}
    {% endif %}
    <button type="submit" class="boton w-full">Guardar</button>
  </form>
</div>
```

`templates/componentes/pagina_formulario.html`:
```html
{% extends "base.html" %}
{% block titulo %}{{ titulo }}{% endblock %}
{% block contenido %}<div class="tarjeta mx-auto max-w-md p-0">{% include "componentes/_formulario_modal.html" %}</div>{% endblock %}
```

- [ ] **Step 4: Formularios del presupuesto**

`apps/presupuesto/formularios.py`:
```python
from django import forms

from apps.core.formularios import FormularioDeHogar
from apps.presupuesto.models import (
    PlantillaGasto,
    PlantillaIngreso,
    PresupuestoMesGasto,
    PresupuestoMesIngreso,
)

CAMPOS_INGRESO = ["nombre", "tipo_ingreso", "es_fijo", "monto", "persona"]
MARCAS_GASTO = ["es_fijo", "con_tarjeta", "es_hormiga"]


class FormularioRenglon(FormularioDeHogar):
    """Renglón de ingreso o gasto; `contenedor` es la plantilla o el presupuesto del mes."""

    contenedor_campo = ""

    def __init__(self, *args, contenedor, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self.instance, self.contenedor_campo, contenedor)
        if "concepto" in self.fields:
            concepto = self.fields["concepto"]
            concepto.queryset = concepto.queryset.select_related("categoria")
            concepto.label_from_instance = lambda c: c.nombre_con_categoria

    @property
    def campos_fijos(self):
        return ("hogar", self.contenedor_campo)


class FormularioIngresoPlantilla(FormularioRenglon):
    contenedor_campo = "plantilla"

    class Meta:
        model = PlantillaIngreso
        fields = CAMPOS_INGRESO


class FormularioGastoPlantilla(FormularioRenglon):
    contenedor_campo = "plantilla"

    class Meta:
        model = PlantillaGasto
        fields = ["concepto", "monto", "periodicidad", *MARCAS_GASTO]


class FormularioIngresoMes(FormularioRenglon):
    contenedor_campo = "presupuesto"

    class Meta:
        model = PresupuestoMesIngreso
        fields = CAMPOS_INGRESO


class FormularioGastoMes(FormularioRenglon):
    contenedor_campo = "presupuesto"

    class Meta:
        model = PresupuestoMesGasto
        fields = ["concepto", "monto_mensual", *MARCAS_GASTO]


RENGLONES = {
    ("plantilla", "ingreso"): FormularioIngresoPlantilla,
    ("plantilla", "gasto"): FormularioGastoPlantilla,
    ("mes", "ingreso"): FormularioIngresoMes,
    ("mes", "gasto"): FormularioGastoMes,
}


class FormularioPorcentaje(forms.Form):
    porcentaje = forms.DecimalField(
        label="% de ahorro",
        min_value=0,
        max_value=100,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"list": "sugerencias-ahorro", "step": "0.01"}),
    )

    def fraccion(self):
        return self.cleaned_data["porcentaje"] / 100
```

- [ ] **Step 5: Vistas y URLs**

`apps/presupuesto/vistas.py`:
```python
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.calculos.comun import redondear
from apps.core.acceso import requiere_hogar
from apps.core.fechas import mes_anterior, mes_siguiente, nombre_mes
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.presupuesto import mensajes
from apps.presupuesto.formularios import RENGLONES, FormularioPorcentaje
from apps.presupuesto.models import PresupuestoMes
from apps.presupuesto.servicios import (
    obtener_plantilla,
    obtener_presupuesto_mes,
    resincronizar_mes,
    resumen_mes,
    resumen_plantilla,
)


@requiere_hogar
def inicio(request):
    hoy = timezone.localdate()
    return redirect("presupuesto:mes", hoy.year, hoy.month)


@requiere_hogar
def plantilla(request):
    contenedor = obtener_plantilla(request.hogar)
    contexto = _contexto(contenedor, resumen_plantilla(contenedor), "plantilla", "Plantilla")
    contexto["urls"] = {
        "porcentaje": reverse("presupuesto:porcentaje_plantilla"),
        "nuevo_ingreso": reverse("presupuesto:nuevo_plantilla", args=["ingreso"]),
        "nuevo_gasto": reverse("presupuesto:nuevo_plantilla", args=["gasto"]),
    }
    return render(request, "presupuesto/pagina.html", contexto)


@requiere_hogar
def del_mes(request, anio, mes):
    contenedor = _presupuesto_mes(request, anio, mes)
    contexto = _contexto(contenedor, resumen_mes(contenedor), "mes", nombre_mes(anio, mes))
    contexto["anterior"] = mes_anterior(anio, mes)
    contexto["siguiente"] = mes_siguiente(anio, mes)
    contexto["urls"] = {
        "porcentaje": reverse("presupuesto:porcentaje_mes", args=[anio, mes]),
        "nuevo_ingreso": reverse("presupuesto:nuevo_mes", args=[anio, mes, "ingreso"]),
        "nuevo_gasto": reverse("presupuesto:nuevo_mes", args=[anio, mes, "gasto"]),
        "resincronizar": reverse("presupuesto:resincronizar", args=[anio, mes]),
    }
    return render(request, "presupuesto/pagina.html", contexto)


@requiere_hogar
def renglon_nuevo(request, ambito, clase, anio=None, mes=None):
    Formulario = _formulario_de(ambito, clase)
    return _editar_renglon(request, Formulario, _contenedor(request, ambito, anio, mes), None)


@requiere_hogar
def renglon_editar(request, ambito, clase, pk):
    Formulario = _formulario_de(ambito, clase)
    renglon = get_object_or_404(Formulario._meta.model.objects.del_hogar(request.hogar), pk=pk)
    contenedor = getattr(renglon, Formulario.contenedor_campo)
    return _editar_renglon(request, Formulario, contenedor, renglon)


@requiere_hogar
@require_POST
def renglon_eliminar(request, ambito, clase, pk):
    Formulario = _formulario_de(ambito, clase)
    renglon = get_object_or_404(Formulario._meta.model.objects.del_hogar(request.hogar), pk=pk)
    destino = _url_de(getattr(renglon, Formulario.contenedor_campo))
    renglon.delete()
    return datos_actualizados() if es_htmx(request) else redirect(destino)


@requiere_hogar
@require_POST
def porcentaje(request, ambito, anio=None, mes=None):
    contenedor = _contenedor(request, ambito, anio, mes)
    formulario = FormularioPorcentaje(request.POST)
    if formulario.is_valid():
        contenedor.porcentaje_ahorro = formulario.fraccion()
        contenedor.save(update_fields=["porcentaje_ahorro", "actualizado_en"])
        messages.success(request, "Porcentaje de ahorro actualizado.")
    else:
        messages.error(request, "El porcentaje de ahorro debe estar entre 0 y 100.")
    return redirect(_url_de(contenedor))


@requiere_hogar
@require_POST
def resincronizar(request, anio, mes):
    resincronizar_mes(_presupuesto_mes(request, anio, mes))
    messages.success(request, "El presupuesto del mes se re-sincronizó con la plantilla.")
    return redirect("presupuesto:mes", anio, mes)


def _presupuesto_mes(request, anio, mes):
    try:
        return obtener_presupuesto_mes(request.hogar, anio, mes)
    except ValueError as error:
        raise Http404 from error


def _contenedor(request, ambito, anio, mes):
    if ambito == "plantilla":
        return obtener_plantilla(request.hogar)
    return _presupuesto_mes(request, anio, mes)


def _url_de(contenedor):
    if isinstance(contenedor, PresupuestoMes):
        return reverse("presupuesto:mes", args=[contenedor.anio, contenedor.mes])
    return reverse("presupuesto:plantilla")


def _formulario_de(ambito, clase):
    Formulario = RENGLONES.get((ambito, clase))
    if Formulario is None:
        raise Http404("Renglón desconocido")
    return Formulario


def _editar_renglon(request, Formulario, contenedor, renglon):
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, instance=renglon, contenedor=contenedor, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        formulario.save()
        return datos_actualizados() if es_htmx(request) else redirect(_url_de(contenedor))
    accion = "Editar" if renglon else "Agregar"
    titulo = f"{accion} {Formulario._meta.model._meta.verbose_name}"
    return responder_formulario(
        request, {"formulario": formulario, "titulo": titulo, "accion": request.path}
    )


def _contexto(contenedor, resumen, ambito, titulo):
    return {
        "ambito": ambito,
        "titulo": titulo,
        "resumen": resumen,
        "ingresos": contenedor.ingresos.select_related("persona"),
        "gastos": contenedor.gastos.select_related("concepto__categoria", "concepto__domicilio"),
        "mensajes": {
            "ahorro": mensajes.mensaje_ahorro(contenedor.porcentaje_ahorro),
            "disponible": mensajes.mensaje_disponible(resumen.disponible, resumen.meta_ahorro),
            "recorte": mensajes.mensaje_recorte(resumen.recorte_necesario),
        },
        "formulario_porcentaje": FormularioPorcentaje(
            initial={"porcentaje": redondear(contenedor.porcentaje_ahorro * 100)}
        ),
    }
```

`apps/presupuesto/urls.py`:
```python
from django.urls import path

from apps.presupuesto import vistas

app_name = "presupuesto"

PLANTILLA = {"ambito": "plantilla"}
MES = {"ambito": "mes"}

urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path("plantilla/", vistas.plantilla, name="plantilla"),
    path("plantilla/porcentaje/", vistas.porcentaje, PLANTILLA, name="porcentaje_plantilla"),
    path("plantilla/<str:clase>/nuevo/", vistas.renglon_nuevo, PLANTILLA, name="nuevo_plantilla"),
    path("<int:anio>/<int:mes>/", vistas.del_mes, name="mes"),
    path("<int:anio>/<int:mes>/porcentaje/", vistas.porcentaje, MES, name="porcentaje_mes"),
    path("<int:anio>/<int:mes>/resincronizar/", vistas.resincronizar, name="resincronizar"),
    path("<int:anio>/<int:mes>/<str:clase>/nuevo/", vistas.renglon_nuevo, MES, name="nuevo_mes"),
    path(
        "renglon/<str:ambito>/<str:clase>/<int:pk>/", vistas.renglon_editar, name="editar_renglon"
    ),
    path(
        "renglon/<str:ambito>/<str:clase>/<int:pk>/eliminar/",
        vistas.renglon_eliminar,
        name="eliminar_renglon",
    ),
]
```

En `finanzas/urls.py`, antes de `path("", include("apps.core.urls")),`:
```python
    path("presupuesto/", include("apps.presupuesto.urls")),
```

- [ ] **Step 6: Plantillas y navegación**

`templates/presupuesto/_resumen.html`:
```html
{% load formato %}
<section class="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Ingresos</p>
    <p class="font-semibold">{{ resumen.ingresos_totales|dinero }}</p>
    <p class="text-xs text-slate-500">fijos {{ resumen.ingresos_fijos|dinero }} · variables {{ resumen.ingresos_variables|dinero }}</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Gastos</p>
    <p class="font-semibold">{{ resumen.gastos_totales|dinero }}</p>
    <p class="text-xs text-slate-500">fijos {{ resumen.gastos_fijos|dinero }} · variables {{ resumen.gastos_variables|dinero }}</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Disponible</p>
    <p class="font-semibold">{{ resumen.disponible|dinero }}</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Meta de ahorro</p>
    <p class="font-semibold">{{ resumen.meta_ahorro|dinero }}</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Presupuesto hormiga 🐜</p>
    <p class="font-semibold">{{ resumen.presupuesto_hormiga|dinero }}</p>
    <p class="text-xs text-slate-500">máximo {{ resumen.maximo_diario_hormiga|dinero }} al día</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Gasto con tarjeta</p>
    <p class="font-semibold">{{ resumen.gasto_con_tarjeta|dinero }}</p>
  </div>
  <div class="tarjeta col-span-2">
    <p class="text-xs text-slate-500">Recorte necesario para la meta</p>
    <p class="font-semibold">{% if resumen.recorte_necesario is None %}N/A{% else %}{{ resumen.recorte_necesario|dinero }}{% endif %}</p>
    <p class="text-xs text-slate-600">{{ mensajes.recorte }}</p>
  </div>
</section>
<p class="mb-4 rounded-lg px-3 py-2 text-sm {% if mensajes.disponible.0 == 'bien' %}bg-emerald-50 text-emerald-800{% elif mensajes.disponible.0 == 'cuidado' %}bg-amber-50 text-amber-800{% else %}bg-red-50 text-red-700{% endif %}">{{ mensajes.disponible.1 }}</p>
```

`templates/presupuesto/_acciones.html`:
```html
<button type="button" class="text-sky-700" hx-get="{% url 'presupuesto:editar_renglon' ambito clase renglon.pk %}" hx-target="#modal-contenido">Editar</button>
<button type="button" class="ml-2 text-red-600" hx-post="{% url 'presupuesto:eliminar_renglon' ambito clase renglon.pk %}" hx-confirm="¿Quitar este renglón?">Quitar</button>
```

`templates/presupuesto/pagina.html`:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Presupuesto · {{ titulo }}{% endblock %}
{% block contenido %}
<nav class="mb-4 flex gap-2 text-sm">
  <a href="{% url 'presupuesto:plantilla' %}" class="rounded-lg px-3 py-1 {% if ambito == 'plantilla' %}bg-emerald-600 text-white{% else %}bg-white{% endif %}">Plantilla</a>
  <a href="{% url 'presupuesto:inicio' %}" class="rounded-lg px-3 py-1 {% if ambito == 'mes' %}bg-emerald-600 text-white{% else %}bg-white{% endif %}">Mes</a>
</nav>
<header class="mb-4 flex items-center justify-between gap-2">
  {% if ambito == "mes" %}<a class="boton-secundario" href="{% url 'presupuesto:mes' anterior.0 anterior.1 %}" aria-label="Mes anterior">‹</a>{% endif %}
  <h1 class="text-lg font-semibold">{{ titulo }}</h1>
  {% if ambito == "mes" %}<a class="boton-secundario" href="{% url 'presupuesto:mes' siguiente.0 siguiente.1 %}" aria-label="Mes siguiente">›</a>{% endif %}
</header>

{% include "presupuesto/_resumen.html" %}

<form method="post" action="{{ urls.porcentaje }}" class="tarjeta mb-4 flex flex-wrap items-end gap-3">
  {% csrf_token %}
  <div class="w-36">{% include "componentes/campo.html" with campo=formulario_porcentaje.porcentaje %}</div>
  <datalist id="sugerencias-ahorro"><option value="5"></option><option value="10"></option><option value="15"></option><option value="20"></option><option value="25"></option></datalist>
  <button class="boton">Guardar %</button>
  <p class="basis-full text-sm text-slate-600">{{ mensajes.ahorro }}</p>
</form>

{% if ambito == "mes" %}
  <form method="post" action="{{ urls.resincronizar }}" class="mb-4 text-right" onsubmit="return confirm('¿Reemplazar el presupuesto de este mes por la plantilla?')">
    {% csrf_token %}<button class="text-sm text-sky-700">Re-sincronizar con la plantilla</button>
  </form>
{% endif %}

<section class="tarjeta mb-4">
  <div class="mb-2 flex items-center justify-between">
    <h2 class="font-medium">Ingresos</h2>
    <button type="button" class="boton-secundario text-sm" hx-get="{{ urls.nuevo_ingreso }}" hx-target="#modal-contenido">+ Ingreso</button>
  </div>
  <table class="w-full text-sm">
    {% for renglon in ingresos %}
      <tr class="border-t border-slate-100">
        <td class="py-1">{{ renglon.nombre }} <span class="text-xs text-slate-500">· {{ renglon.get_tipo_ingreso_display }}{% if not renglon.es_fijo %} · variable{% endif %}{% if renglon.persona %} · {{ renglon.persona }}{% endif %}</span></td>
        <td class="py-1 text-right">{{ renglon.monto|dinero }}</td>
        <td class="py-1 text-right text-xs">{% include "presupuesto/_acciones.html" with clase="ingreso" %}</td>
      </tr>
    {% empty %}
      <tr><td class="text-slate-500">Sin ingresos</td></tr>
    {% endfor %}
  </table>
</section>

<section class="tarjeta">
  <div class="mb-2 flex items-center justify-between">
    <h2 class="font-medium">Gastos</h2>
    <button type="button" class="boton-secundario text-sm" hx-get="{{ urls.nuevo_gasto }}" hx-target="#modal-contenido">+ Gasto</button>
  </div>
  {% regroup gastos by concepto.categoria as grupos %}
  {% for grupo in grupos %}
    <h3 class="mt-3 text-sm font-semibold">{{ grupo.grouper }}</h3>
    <table class="w-full text-sm">
      {% for renglon in grupo.list %}
        <tr class="border-t border-slate-100">
          <td class="py-1">{{ renglon.concepto.nombre }}{% if renglon.concepto.domicilio %} <span class="text-xs text-slate-500">({{ renglon.concepto.domicilio }})</span>{% endif %}<span class="text-xs text-slate-500">{% if renglon.es_fijo %} · fijo{% endif %}{% if renglon.con_tarjeta %} · 💳{% endif %}{% if renglon.es_hormiga %} · 🐜{% endif %}{% if renglon.periodicidad == "anual" %} · anual {{ renglon.monto|dinero }}{% endif %}</span></td>
          <td class="py-1 text-right">{{ renglon.monto_mensual|dinero }}</td>
          <td class="py-1 text-right text-xs">{% include "presupuesto/_acciones.html" with clase="gasto" %}</td>
        </tr>
      {% endfor %}
    </table>
  {% empty %}
    <p class="text-sm text-slate-500">Sin gastos presupuestados.</p>
  {% endfor %}
</section>
{% endblock %}
```

(`renglon.monto_mensual` funciona en ambos ámbitos: en la plantilla es un método sin argumentos y en el mes es un campo.)

`templates/componentes/navegacion.html`: después del botón **+**, agregar:
```html
  <a href="{% url 'presupuesto:inicio' %}" class="flex flex-col items-center rounded-lg px-2 py-1 md:flex-row md:gap-2 hover:bg-slate-100"><span>🧮</span><span>Presupuesto</span></a>
```

- [ ] **Step 7: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_pre_vistas.py` 15 passed; todo verde.

- [ ] **Step 8: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps finanzas/urls.py templates tests/presupuesto/test_pre_vistas.py
git commit -m "feat(presupuesto): pantalla de plantilla y mes con resumen, renglones, % de ahorro y re-sincronizacion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Cálculos y servicio del tablero (TAB-01..04, TAB-05 deudas, TAB-06)

**Files:**
- Create: `apps/calculos/tablero.py`, `apps/tablero/__init__.py` (vacío), `apps/tablero/apps.py`, `apps/tablero/servicios.py`
- Modify: `apps/catalogos/servicios.py` (agregar `ResumenDeudas` y `resumir_deudas`), `finanzas/settings.py` (INSTALLED_APPS)
- Test: `tests/calculos/test_calc_tablero.py`, `tests/catalogos/test_catalogos_servicios.py`, `tests/tablero/test_tablero_servicio.py`

**Interfaces:**
- Consumes: `apps.calculos.deudas` (`TarjetaCredito`, `uso_de_credito`, `nivel_de_uso`, `NIVEL_CUIDADO`, `NIVEL_RIESGO`); `obtener_presupuesto_mes`, `resumen_mes`, `gastos_del_mes`, `mensaje_disponible` (Task 9); `movimientos_del_mes`, `totales`, `Filtros`, `Totales` (Task 7); filtros `dinero`, `porcentaje` como funciones (Task 2).
- Produces:
  - `apps.calculos.tablero`: `VERDE, AMBAR, ROJO`; `avance(gastado, presupuesto) -> Decimal | None`; `semaforo(gastado, presupuesto) -> str` (verde < 80 %, ámbar 80–100 %, rojo > 100 % o gasto sin presupuesto); `distribucion(montos: dict) -> dict` (fracción de cada monto sobre el total).
  - `apps.catalogos.servicios.ResumenDeudas(total_tarjetas, total_creditos, mensualidades, uso, nivel, tarjetas_con_intereses)` y `resumir_deudas(hogar) -> ResumenDeudas` (solo cuentas activas; un saldo a favor no es deuda).
  - `apps.tablero.servicios`: `FilaCategoria(categoria, presupuesto, gastado, restante, avance, color, participacion)`, `Alerta(nivel, mensaje)`, `Tablero(anio, mes, filtrado, resumen, reales, categorias, gasto_anual_estimado, deudas, mensaje_disponible, alertas)` y `armar_tablero(hogar, anio, mes, persona=None, domicilio=None) -> Tablero` (`ValueError` si el mes es inválido).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/calculos/test_calc_tablero.py`:
```python
from decimal import Decimal as D

import pytest

from apps.calculos.comun import CERO, redondear
from apps.calculos.tablero import AMBAR, ROJO, VERDE, avance, distribucion, semaforo


def test_avance():
    assert avance(D("1200"), D("2400")) == D("0.5")
    assert avance(D("10"), D("0")) is None


@pytest.mark.parametrize(
    ("gastado", "color"), [("1919", VERDE), ("1920", AMBAR), ("2400", AMBAR), ("2400.01", ROJO)]
)
def test_semaforo_con_presupuesto_de_2400(gastado, color):
    assert semaforo(D(gastado), D("2400")) == color


def test_semaforo_sin_presupuesto():
    assert semaforo(D("10"), D("0")) == ROJO
    assert semaforo(D("0"), D("0")) == VERDE


def test_distribucion_sobre_el_total():
    resultado = distribucion({"Comida": D("10600"), "Resto": D("18635")})

    assert redondear(resultado["Comida"], 4) == D("0.3626")
    assert redondear(sum(resultado.values()), 10) == D("1")


def test_distribucion_sin_total():
    assert distribucion({"Comida": CERO}) == {"Comida": CERO}
```

`tests/catalogos/test_catalogos_servicios.py`:
```python
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.catalogos.servicios import resumir_deudas

pytestmark = pytest.mark.django_db


def test_resumen_de_deudas(catalogo):
    r = resumir_deudas(catalogo.tarjeta.hogar)

    assert r.total_tarjetas == D("6839.01")
    assert r.total_creditos == D("38679.72")
    assert r.mensualidades == D("1500")
    assert redondear(r.uso, 4) == D("0.9632")
    assert r.nivel == "riesgo"
    assert r.tarjetas_con_intereses == ["Tarjeta Oro"]


def test_sin_tarjetas_no_hay_uso(hogar):
    r = resumir_deudas(hogar)

    assert (r.uso, r.nivel, r.total_tarjetas) == (None, None, 0)


def test_cuentas_inactivas_no_cuentan(catalogo):
    catalogo.tarjeta.activo = False
    catalogo.tarjeta.save()

    r = resumir_deudas(catalogo.tarjeta.hogar)

    assert r.total_tarjetas == 0
    assert r.tarjetas_con_intereses == []
```

`tests/tablero/test_tablero_servicio.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.catalogos.models import Categoria
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import guardar_movimiento
from apps.presupuesto.models import PlantillaGasto, PlantillaIngreso
from apps.presupuesto.servicios import obtener_plantilla
from apps.tablero.servicios import armar_tablero

pytestmark = pytest.mark.django_db


def registrar(hogar, **campos):
    campos.setdefault("fecha", date(2026, 10, 5))
    campos["monto"] = D(campos["monto"])
    return guardar_movimiento(Movimiento(hogar=hogar, **campos))


def gasto(hogar, monto, **campos):
    return registrar(hogar, tipo=Movimiento.Tipo.GASTO, monto=monto, **campos)


def ingreso(hogar, monto, tipo_ingreso, **campos):
    return registrar(
        hogar,
        tipo=Movimiento.Tipo.INGRESO,
        monto=monto,
        tipo_ingreso=tipo_ingreso,
        metodo_pago=MetodoPago.TRANSFERENCIA,
        **campos,
    )


def filas(tablero):
    return {fila.categoria.nombre: fila for fila in tablero.categorias}


def mensajes(tablero):
    return " | ".join(alerta.mensaje for alerta in tablero.alertas)


def test_tablero_con_el_presupuesto_del_excel(plantilla_excel, hogar):
    t = armar_tablero(hogar, 2026, 10)

    assert t.resumen.ingresos_totales == D("32977.52")
    assert t.resumen.gastos_totales == D("29235")
    assert t.gasto_anual_estimado == D("350820")
    assert t.mensaje_disponible[0] == "bien"
    assert len(t.categorias) == 12
    assert filas(t)["Comida"].presupuesto == D("10600")
    assert redondear(filas(t)["Comida"].participacion, 4) == D("0.3626")


def test_ingresos_reales_incluyen_extraordinarios_sin_cambiar_la_meta(plantilla_excel, hogar):
    ingreso(hogar, "15000", TipoIngreso.SALARIO)
    ingreso(hogar, "20000", TipoIngreso.AGUINALDO, es_extraordinario=True)

    t = armar_tablero(hogar, 2026, 10)

    assert t.reales.ingresos == D("35000")
    assert t.reales.ingresos_extra == D("20000")
    assert t.resumen.meta_ahorro == D("1648.876")


def test_avance_y_color_por_categoria(plantilla_excel, catalogo, hogar):
    gasto(hogar, "1920", concepto=catalogo.gasolina)
    gasto(hogar, "100", categoria=catalogo.categorias["Viajes"])

    t = armar_tablero(hogar, 2026, 10)

    transporte = filas(t)["Transporte"]
    assert (transporte.presupuesto, transporte.gastado, transporte.restante) == (
        D("2400"),
        D("1920"),
        D("480"),
    )
    assert transporte.avance == D("0.8")
    assert transporte.color == "ambar"
    assert filas(t)["Viajes"].color == "rojo"


def test_filtro_por_domicilio(plantilla_excel, catalogo, hogar):
    PlantillaGasto.objects.create(
        hogar=hogar, plantilla=plantilla_excel, concepto=catalogo.luz_fidel, monto=D("500")
    )
    gasto(hogar, "450", concepto=catalogo.luz_fidel, domicilio=catalogo.fidel)
    gasto(hogar, "650", concepto=catalogo.gasolina)

    t = armar_tablero(hogar, 2026, 10, domicilio=catalogo.fidel)

    assert t.filtrado
    assert (t.resumen.gastos_totales, t.resumen.ingresos_totales) == (D("500"), D("0"))
    assert t.reales.gastos == D("450")
    assert (filas(t)["Casa"].presupuesto, filas(t)["Casa"].gastado) == (D("500"), D("450"))
    assert t.mensaje_disponible is None
    assert "meta de ahorro" not in mensajes(t)
    assert "más de gastos que de ingresos" not in mensajes(t)


def test_alertas_de_tarjetas(catalogo, hogar):
    t = armar_tablero(hogar, 2026, 10)

    assert "96.32%" in mensajes(t)
    assert "intereses en Tarjeta Oro" in mensajes(t)


def test_alerta_de_gastos_mayores_a_ingresos(catalogo, hogar):
    gasto(hogar, "650", concepto=catalogo.gasolina)

    assert "$650.00 más de gastos que de ingresos" in mensajes(armar_tablero(hogar, 2026, 10))


def test_alerta_de_meta_no_alcanzable(catalogo, hogar):
    plantilla = obtener_plantilla(hogar)
    PlantillaIngreso.objects.create(hogar=hogar, plantilla=plantilla, nombre="Salario", monto=D("1000"))
    PlantillaGasto.objects.create(
        hogar=hogar, plantilla=plantilla, concepto=catalogo.gasolina, monto=D("990")
    )

    t = armar_tablero(hogar, 2026, 10)

    assert "te faltan $40.00 al mes" in mensajes(t)


def test_datos_de_otro_hogar_no_aparecen(plantilla_excel, hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    gasto(otro_hogar, "999", categoria=ajena)

    assert armar_tablero(hogar, 2026, 10).reales.gastos == 0


def test_mes_invalido(hogar):
    with pytest.raises(ValueError):
        armar_tablero(hogar, 2026, 13)
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/calculos/test_calc_tablero.py tests/catalogos/test_catalogos_servicios.py tests/tablero -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.calculos.tablero'` (y `ImportError` de `resumir_deudas`, `apps.tablero`).

- [ ] **Step 3: Cálculos puros**

`apps/calculos/tablero.py`:
```python
"""RF-TAB-02 y RF-TAB-03: avance por categoría, semáforo y distribución del gasto."""

from decimal import Decimal

from apps.calculos.comun import CERO

VERDE, AMBAR, ROJO = "verde", "ambar", "rojo"
LIMITE_VERDE = Decimal("0.80")


def avance(gastado, presupuesto):
    """Fracción gastada del presupuesto; None si no hay presupuesto."""
    if presupuesto <= 0:
        return None
    return gastado / presupuesto


def semaforo(gastado, presupuesto):
    """Verde < 80 %; ámbar 80–100 %; rojo > 100 % o gasto sin presupuesto."""
    fraccion = avance(gastado, presupuesto)
    if fraccion is None:
        return ROJO if gastado > 0 else VERDE
    if fraccion < LIMITE_VERDE:
        return VERDE
    if fraccion <= 1:
        return AMBAR
    return ROJO


def distribucion(montos):
    """Participación de cada monto en el total (0 si el total es 0)."""
    total = sum(montos.values(), CERO)
    if total <= 0:
        return {clave: CERO for clave in montos}
    return {clave: monto / total for clave, monto in montos.items()}
```

- [ ] **Step 4: Resumen de deudas**

En `apps/catalogos/servicios.py`, reemplazar los imports por:
```python
from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO
from apps.calculos.deudas import TarjetaCredito, nivel_de_uso, uso_de_credito
from apps.catalogos.models import Categoria, Cuenta
```
y agregar al final:
```python
@dataclass(frozen=True)
class ResumenDeudas:
    total_tarjetas: Decimal
    total_creditos: Decimal
    mensualidades: Decimal
    uso: Decimal | None
    nivel: str | None
    tarjetas_con_intereses: list


def resumir_deudas(hogar):
    """RF-DEU-03, RN-08 y RN-09 con las cuentas activas del hogar."""
    cuentas = Cuenta.objects.del_hogar(hogar).filter(activo=True)
    tarjetas = list(cuentas.filter(tipo=Cuenta.Tipo.CREDITO))
    creditos = list(cuentas.filter(tipo=Cuenta.Tipo.PRESTAMO))
    uso = uso_de_credito(
        TarjetaCredito(saldo=t.saldo_actual, linea=t.linea_credito or CERO) for t in tarjetas
    )
    return ResumenDeudas(
        total_tarjetas=sum((max(CERO, t.saldo_actual) for t in tarjetas), CERO),
        total_creditos=sum((max(CERO, c.saldo_actual) for c in creditos), CERO),
        mensualidades=sum((c.mensualidad or CERO for c in creditos), CERO),
        uso=uso,
        nivel=None if uso is None else nivel_de_uso(uso),
        tarjetas_con_intereses=[t.nombre for t in tarjetas if t.paga_total_mensual is False],
    )
```

- [ ] **Step 5: Servicio del tablero**

`apps/tablero/apps.py`:
```python
from django.apps import AppConfig


class TableroConfig(AppConfig):
    name = "apps.tablero"
    verbose_name = "Tablero"
```

`apps/tablero/servicios.py`:
```python
"""Composición del tablero del mes (P2). No tiene modelos propios."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from apps.calculos.comun import CERO
from apps.calculos.deudas import NIVEL_CUIDADO, NIVEL_RIESGO
from apps.calculos.presupuesto import ResumenPresupuesto
from apps.calculos.tablero import avance, distribucion, semaforo
from apps.catalogos.models import Categoria
from apps.catalogos.servicios import ResumenDeudas, resumir_deudas
from apps.core.templatetags.formato import dinero, porcentaje
from apps.movimientos.consultas import Filtros, Totales, movimientos_del_mes, totales
from apps.presupuesto.mensajes import mensaje_disponible
from apps.presupuesto.servicios import gastos_del_mes, obtener_presupuesto_mes, resumen_mes


@dataclass(frozen=True)
class FilaCategoria:
    categoria: Categoria
    presupuesto: Decimal
    gastado: Decimal
    restante: Decimal
    avance: Decimal | None
    color: str
    participacion: Decimal


@dataclass(frozen=True)
class Alerta:
    nivel: str
    mensaje: str


@dataclass(frozen=True)
class Tablero:
    anio: int
    mes: int
    filtrado: bool
    resumen: ResumenPresupuesto
    reales: Totales
    categorias: list
    gasto_anual_estimado: Decimal
    deudas: ResumenDeudas
    mensaje_disponible: tuple | None
    alertas: list


def armar_tablero(hogar, anio, mes, persona=None, domicilio=None):
    """RF-TAB-01..06. Con persona o domicilio, solo se filtran gastos (e ingresos por persona)."""
    presupuesto = obtener_presupuesto_mes(hogar, anio, mes)
    resumen = resumen_mes(presupuesto, persona=persona, domicilio=domicilio)
    filtros = Filtros(persona=persona, domicilio=domicilio)
    reales = totales(movimientos_del_mes(hogar, anio, mes, filtros))
    filtrado = persona is not None or domicilio is not None
    deudas = resumir_deudas(hogar)
    return Tablero(
        anio=anio,
        mes=mes,
        filtrado=filtrado,
        resumen=resumen,
        reales=reales,
        categorias=_filas_por_categoria(
            hogar, gastos_del_mes(presupuesto, persona, domicilio), reales
        ),
        gasto_anual_estimado=resumen.gastos_totales * 12,
        deudas=deudas,
        mensaje_disponible=(
            None if filtrado else mensaje_disponible(resumen.disponible, resumen.meta_ahorro)
        ),
        alertas=_alertas(resumen, reales, deudas, filtrado),
    )


def _filas_por_categoria(hogar, gastos_presupuestados, reales):
    presupuestado = defaultdict(lambda: CERO)
    for renglon in gastos_presupuestados:
        presupuestado[renglon.concepto.categoria_id] += renglon.monto_mensual
    gastado = {categoria.pk: total for categoria, total in reales.por_categoria}
    con_datos = set(presupuestado) | set(gastado)
    categorias = list(
        Categoria.objects.del_hogar(hogar).filter(Q(activo=True) | Q(pk__in=con_datos))
    )
    participacion = distribucion({c.pk: presupuestado[c.pk] for c in categorias})
    filas = []
    for categoria in categorias:
        monto_presupuesto = presupuestado[categoria.pk]
        monto_gastado = gastado.get(categoria.pk, CERO)
        filas.append(
            FilaCategoria(
                categoria=categoria,
                presupuesto=monto_presupuesto,
                gastado=monto_gastado,
                restante=monto_presupuesto - monto_gastado,
                avance=avance(monto_gastado, monto_presupuesto),
                color=semaforo(monto_gastado, monto_presupuesto),
                participacion=participacion[categoria.pk],
            )
        )
    return filas


def _alertas(resumen, reales, deudas, filtrado):
    """RF-TAB-06: RN-08, RN-09, disponible negativo y meta de ahorro no alcanzable."""
    alertas = []
    if deudas.nivel in (NIVEL_CUIDADO, NIVEL_RIESGO):
        alertas.append(
            Alerta(
                deudas.nivel,
                f"Uso de tus tarjetas de crédito: {porcentaje(deudas.uso)} ({deudas.nivel}). "
                "Lo sano es menos de 30%.",
            )
        )
    for nombre in deudas.tarjetas_con_intereses:
        alertas.append(
            Alerta(NIVEL_CUIDADO, f"Estás pagando intereses en {nombre}: no pagas el total.")
        )
    if filtrado:
        return alertas
    if reales.disponible < 0:
        alertas.append(
            Alerta(
                NIVEL_RIESGO,
                f"Este mes llevas {dinero(-reales.disponible)} más de gastos que de ingresos.",
            )
        )
    if resumen.recorte_necesario is not None:
        alertas.append(
            Alerta(
                NIVEL_CUIDADO,
                "Con este presupuesto no alcanzas tu meta de ahorro: "
                f"te faltan {dinero(resumen.recorte_necesario)} al mes.",
            )
        )
    return alertas
```

En `finanzas/settings.py`, agregar `"apps.tablero",` después de `"apps.presupuesto",` en `INSTALLED_APPS`.

- [ ] **Step 6: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_calc_tablero.py` 8 passed, `test_catalogos_servicios.py` 3 passed, `test_tablero_servicio.py` 9 passed; todo verde.

- [ ] **Step 7: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps finanzas/settings.py tests/calculos/test_calc_tablero.py tests/catalogos/test_catalogos_servicios.py tests/tablero
git commit -m "feat(tablero): avance por categoria, semaforo, resumen de deudas y alertas del mes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Pantalla del tablero (P2) e inicio

**Files:**
- Create: `apps/tablero/formularios.py`, `apps/tablero/vistas.py`, `apps/tablero/urls.py`, `templates/tablero/mes.html`
- Modify: `apps/core/vistas.py` (inicio → tablero del mes), `finanzas/urls.py`, `tests/core/test_core_acceso.py`
- Delete: `templates/core/inicio.html`
- Test: `tests/tablero/test_tablero_vistas.py`

**Interfaces:**
- Consumes: `armar_tablero`, `Tablero` (Task 11); `apps.core.fechas`; filtros `dinero`, `porcentaje`, `ancho_barra`.
- Produces: ruta `tablero:mes` (`/tablero/<anio>/<mes>/?persona=&domicilio=`); `/` redirige al tablero del mes actual; `apps.tablero.formularios.FormularioFiltrosTablero(data, hogar=)` con `elegidos() -> {"persona": ..., "domicilio": ...}` (ignora ids ajenos).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/tablero/test_tablero_vistas.py`:
```python
import pytest
from django.utils import timezone

from apps.catalogos.models import Persona

pytestmark = pytest.mark.django_db


def test_inicio_lleva_al_tablero_del_mes_actual(cliente):
    hoy = timezone.localdate()

    assert cliente.get("/").url == f"/tablero/{hoy.year}/{hoy.month}/"


def test_tablero_muestra_resumen_y_categorias(cliente, plantilla_excel):
    contenido = cliente.get("/tablero/2026/10/").content.decode()

    for texto in ("Octubre 2026", "$32,977.52", "$29,235.00", "$350,820.00", "Comida", "¡Felicidades!"):
        assert texto in contenido


def test_tablero_muestra_alertas_de_tarjetas(cliente, catalogo):
    assert "96.32%" in cliente.get("/tablero/2026/10/").content.decode()


def test_filtro_por_domicilio(cliente, catalogo):
    respuesta = cliente.get("/tablero/2026/10/", {"domicilio": catalogo.fidel.pk})

    assert respuesta.context["tablero"].filtrado


def test_filtro_con_id_de_otro_hogar_se_ignora(cliente, catalogo, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    respuesta = cliente.get("/tablero/2026/10/", {"persona": ajena.pk})

    assert respuesta.status_code == 200
    assert not respuesta.context["tablero"].filtrado


def test_mes_invalido_da_404(cliente):
    assert cliente.get("/tablero/2026/0/").status_code == 404


def test_tablero_requiere_sesion(client):
    assert client.get("/tablero/2026/10/").status_code == 302
```

En `tests/core/test_core_acceso.py`, reemplazar `test_inicio_muestra_la_navegacion` por:
```python
def test_la_navegacion_aparece_con_sesion(cliente):
    respuesta = cliente.get("/movimientos/2026/10/")

    assert "Salir" in respuesta.content.decode()
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/tablero/test_tablero_vistas.py -v`
Expected: FAIL (`/` responde 200 en lugar de redirigir; `/tablero/...` da 404).

- [ ] **Step 3: Implementar**

`apps/tablero/formularios.py`:
```python
from django import forms

from apps.catalogos.models import Domicilio, Persona


class FormularioFiltrosTablero(forms.Form):
    persona = forms.ModelChoiceField(Persona.objects.none(), required=False, empty_label="Todas")
    domicilio = forms.ModelChoiceField(
        Domicilio.objects.none(), required=False, empty_label="Todos"
    )

    def __init__(self, *args, hogar, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["persona"].queryset = Persona.objects.del_hogar(hogar)
        self.fields["domicilio"].queryset = Domicilio.objects.del_hogar(hogar)

    def elegidos(self):
        """Persona y domicilio válidos; un id inválido o ajeno se ignora."""
        if not self.is_bound:
            return {"persona": None, "domicilio": None}
        self.is_valid()
        return {
            "persona": self.cleaned_data.get("persona"),
            "domicilio": self.cleaned_data.get("domicilio"),
        }
```

`apps/tablero/vistas.py`:
```python
from django.http import Http404
from django.shortcuts import render

from apps.core.acceso import requiere_hogar
from apps.core.fechas import mes_anterior, mes_siguiente, nombre_mes, validar_mes
from apps.tablero.formularios import FormularioFiltrosTablero
from apps.tablero.servicios import armar_tablero


@requiere_hogar
def del_mes(request, anio, mes):
    try:
        validar_mes(anio, mes)
    except ValueError as error:
        raise Http404 from error
    filtros = FormularioFiltrosTablero(request.GET or None, hogar=request.hogar)
    contexto = {
        "tablero": armar_tablero(request.hogar, anio, mes, **filtros.elegidos()),
        "filtros": filtros,
        "titulo": nombre_mes(anio, mes),
        "anterior": mes_anterior(anio, mes),
        "siguiente": mes_siguiente(anio, mes),
        "consulta": request.GET.urlencode(),
    }
    return render(request, "tablero/mes.html", contexto)
```

`apps/tablero/urls.py`:
```python
from django.urls import path

from apps.tablero import vistas

app_name = "tablero"

urlpatterns = [
    path("<int:anio>/<int:mes>/", vistas.del_mes, name="mes"),
]
```

En `finanzas/urls.py`, antes de `path("", include("apps.core.urls")),`:
```python
    path("tablero/", include("apps.tablero.urls")),
```

`apps/core/vistas.py` completo:
```python
from django.shortcuts import redirect
from django.utils import timezone

from apps.core.acceso import requiere_hogar


@requiere_hogar
def inicio(request):
    hoy = timezone.localdate()
    return redirect("tablero:mes", hoy.year, hoy.month)
```

Borrar `templates/core/inicio.html`:
```powershell
git rm templates/core/inicio.html
```

`templates/tablero/mes.html`:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}{{ titulo }}{% endblock %}
{% block contenido %}
<header class="mb-4 flex items-center justify-between gap-2">
  <a class="boton-secundario" href="{% url 'tablero:mes' anterior.0 anterior.1 %}?{{ consulta }}" aria-label="Mes anterior">‹</a>
  <h1 class="text-lg font-semibold">{{ titulo }}</h1>
  <a class="boton-secundario" href="{% url 'tablero:mes' siguiente.0 siguiente.1 %}?{{ consulta }}" aria-label="Mes siguiente">›</a>
</header>

<details class="tarjeta mb-4" {% if tablero.filtrado %}open{% endif %}>
  <summary class="cursor-pointer font-medium">Ver por persona o domicilio</summary>
  <form method="get" class="mt-3 grid gap-3 sm:grid-cols-3">
    {% for campo in filtros %}{% include "componentes/campo.html" %}{% endfor %}
    <div class="flex items-end gap-2"><button class="boton">Ver</button><a class="boton-secundario" href="{{ request.path }}">Todo</a></div>
  </form>
</details>

{% for alerta in tablero.alertas %}
  <p class="mb-2 rounded-lg px-3 py-2 text-sm {% if alerta.nivel == 'riesgo' %}bg-red-50 text-red-700{% else %}bg-amber-50 text-amber-800{% endif %}">{{ alerta.mensaje }}</p>
{% endfor %}

<section class="my-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Ingresos del mes</p>
    <p class="text-lg font-semibold text-emerald-700">{{ tablero.reales.ingresos|dinero }}</p>
    <p class="text-xs text-slate-500">esperados {{ tablero.resumen.ingresos_totales|dinero }}{% if tablero.reales.ingresos_extra %} · extra {{ tablero.reales.ingresos_extra|dinero }}{% endif %}</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Gastos del mes</p>
    <p class="text-lg font-semibold text-red-600">{{ tablero.reales.gastos|dinero }}</p>
    <p class="text-xs text-slate-500">presupuesto {{ tablero.resumen.gastos_totales|dinero }}</p>
  </div>
  <div class="tarjeta">
    <p class="text-xs text-slate-500">Disponible del mes</p>
    <p class="text-lg font-semibold">{{ tablero.reales.disponible|dinero }}</p>
    <p class="text-xs text-slate-500">según presupuesto {{ tablero.resumen.disponible|dinero }} · meta de ahorro {{ tablero.resumen.meta_ahorro|dinero }}</p>
  </div>
</section>

{% if tablero.mensaje_disponible %}
  <p class="mb-4 rounded-lg px-3 py-2 text-sm {% if tablero.mensaje_disponible.0 == 'bien' %}bg-emerald-50 text-emerald-800{% elif tablero.mensaje_disponible.0 == 'cuidado' %}bg-amber-50 text-amber-800{% else %}bg-red-50 text-red-700{% endif %}">{{ tablero.mensaje_disponible.1 }}</p>
{% endif %}

<section class="tarjeta mb-4">
  <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
    <h2 class="font-medium">Por categoría</h2>
    <p class="text-xs text-slate-500">Gasto anual estimado {{ tablero.gasto_anual_estimado|dinero }}</p>
  </div>
  <ul class="space-y-3">
    {% for fila in tablero.categorias %}
      <li>
        <div class="flex justify-between gap-2 text-sm">
          <span>{{ fila.categoria }} <span class="text-xs text-slate-500">{{ fila.participacion|porcentaje:0 }}</span></span>
          <span>{{ fila.gastado|dinero }} / {{ fila.presupuesto|dinero }}</span>
        </div>
        <div class="mt-1 h-2 rounded-full bg-slate-100">
          <div class="h-2 rounded-full {% if fila.color == 'rojo' %}bg-red-500{% elif fila.color == 'ambar' %}bg-amber-400{% else %}bg-emerald-500{% endif %}" style="width: {{ fila.avance|ancho_barra }}%"></div>
        </div>
        <p class="text-xs text-slate-500">restante {{ fila.restante|dinero }}{% if fila.avance is not None %} · {{ fila.avance|porcentaje:0 }} usado{% endif %}</p>
      </li>
    {% endfor %}
  </ul>
</section>

<section class="tarjeta">
  <h2 class="mb-2 font-medium">Deudas</h2>
  <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
    <dt>Tarjetas de crédito</dt><dd class="text-right">{{ tablero.deudas.total_tarjetas|dinero }}</dd>
    <dt>Uso de tarjetas</dt><dd class="text-right">{{ tablero.deudas.uso|porcentaje }}</dd>
    <dt>Créditos</dt><dd class="text-right">{{ tablero.deudas.total_creditos|dinero }}</dd>
    <dt>Mensualidades</dt><dd class="text-right">{{ tablero.deudas.mensualidades|dinero }}</dd>
  </dl>
  <p class="mt-2 text-xs text-slate-500">Metas de ahorro y patrimonio se agregan en el plan 3.</p>
</section>
{% endblock %}
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_tablero_vistas.py` 7 passed; `test_core_acceso.py` 7 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps finanzas/urls.py templates tests/tablero/test_tablero_vistas.py tests/core/test_core_acceso.py
git commit -m "feat(tablero): tablero del mes con resumen, categorias, deudas, alertas y filtros por persona o domicilio" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Catálogos en la interfaz (P12)

**Files:**
- Create: `apps/catalogos/formularios.py`, `apps/catalogos/vistas.py`, `apps/catalogos/urls.py`, `templates/catalogos/indice.html`, `templates/catalogos/lista.html`
- Modify: `apps/catalogos/servicios.py` (agregar `tasa_sugerida`), `finanzas/urls.py`, `templates/componentes/navegacion.html`
- Test: `tests/catalogos/test_catalogos_vistas.py`, `tests/catalogos/test_catalogos_servicios.py`

**Interfaces:**
- Consumes: `FormularioDeHogar`, `responder_formulario`, `datos_actualizados`, `es_htmx`, `requiere_hogar`; `AYUDA_SUGERIDO` y etiquetas "por defecto" (Task 1); filtros `dinero` y `porcentaje` como funciones.
- Produces:
  - `apps.catalogos.servicios.tasa_sugerida(cuenta) -> Decimal | None` (RF-CAT-04: la tasa capturada o, en tarjetas sin tasa, la de `TasaMercado` con la misma institución y producto, sin distinguir mayúsculas).
  - `apps.catalogos.formularios.FormularioCatalogo` (base, con `grupos` y `secciones()`), `FormularioPersona`, `FormularioDomicilio`, `FormularioCategoria`, `FormularioConcepto` (sección "Valores sugeridos (opcional)"), `FormularioCuenta`.
  - Rutas `catalogos:indice` (`/catalogos/`, pantalla "Más"), `catalogos:lista` (`/catalogos/<catalogo>/`), `catalogos:nuevo`, `catalogos:editar` (`/catalogos/<catalogo>/<pk>/`), `catalogos:eliminar` (POST; desactiva si tiene registros asociados). `<catalogo>` ∈ `personas, domicilios, categorias, conceptos, cuentas`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/catalogos/test_catalogos_vistas.py`:
```python
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Concepto, Cuenta, Domicilio, Persona, TasaMercado
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento
from apps.presupuesto.models import PlantillaGasto
from apps.presupuesto.servicios import obtener_plantilla

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def test_indice_lista_los_catalogos(cliente):
    contenido = cliente.get("/catalogos/").content.decode()

    for titulo in ("Personas", "Domicilios", "Categorías", "Conceptos", "Cuentas"):
        assert titulo in contenido


def test_lista_solo_muestra_registros_del_hogar(cliente, catalogo, otro_hogar):
    Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    contenido = cliente.get("/catalogos/personas/").content.decode()

    assert "Monze" in contenido
    assert "Ajena" not in contenido


def test_crear_persona(cliente, hogar):
    respuesta = cliente.post(
        "/catalogos/personas/nuevo/", {"nombre": "Fidel", "activo": "on"}, headers=HTMX
    )

    assert respuesta.status_code == 204
    assert Persona.objects.get(nombre="Fidel").hogar == hogar


def test_nombre_repetido_es_error_del_formulario(cliente, catalogo):
    respuesta = cliente.post(
        "/catalogos/personas/nuevo/", {"nombre": "Monze", "activo": "on"}, headers=HTMX
    )

    assert respuesta.status_code == 200
    assert "__all__" in respuesta.context["formulario"].errors


def test_editar_domicilio(cliente, catalogo):
    respuesta = cliente.post(
        f"/catalogos/domicilios/{catalogo.fidel.pk}/",
        {"alias": "Casa Fidel", "direccion": "Calle Ficticia 1", "activo": "on"},
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    assert Domicilio.objects.get(pk=catalogo.fidel.pk).direccion == "Calle Ficticia 1"


def test_formulario_de_concepto_agrupa_valores_sugeridos(cliente, catalogo):
    contenido = cliente.get("/catalogos/conceptos/nuevo/", headers=HTMX).content.decode()

    assert "Valores sugeridos (opcional)" in contenido
    assert "Persona por defecto" in contenido


def test_crear_concepto_sin_valores_sugeridos(cliente, catalogo):
    respuesta = cliente.post(
        "/catalogos/conceptos/nuevo/",
        {"categoria": catalogo.categorias["Transporte"].pk, "nombre": "Casetas", "activo": "on"},
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    casetas = Concepto.objects.get(nombre="Casetas")
    assert (casetas.persona, casetas.cuenta, casetas.domicilio) == (None, None, None)


def test_eliminar_sin_uso_borra(cliente, hogar):
    temporal = Persona.objects.create(hogar=hogar, nombre="Temporal")

    respuesta = cliente.post(f"/catalogos/personas/{temporal.pk}/eliminar/", headers=HTMX)

    assert respuesta.status_code == 204
    assert not Persona.objects.filter(pk=temporal.pk).exists()


def test_eliminar_cuenta_con_movimientos_la_desactiva(cliente, catalogo):
    guardar_movimiento(
        Movimiento(
            hogar=catalogo.efectivo.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("10"),
            concepto=catalogo.gasolina,
            cuenta=catalogo.efectivo,
        )
    )

    cliente.post(f"/catalogos/cuentas/{catalogo.efectivo.pk}/eliminar/", headers=HTMX)

    catalogo.efectivo.refresh_from_db()
    assert catalogo.efectivo.activo is False


def test_eliminar_concepto_del_presupuesto_lo_desactiva(cliente, catalogo, hogar):
    PlantillaGasto.objects.create(
        hogar=hogar, plantilla=obtener_plantilla(hogar), concepto=catalogo.gasolina, monto=D("1")
    )

    cliente.post(f"/catalogos/conceptos/{catalogo.gasolina.pk}/eliminar/", headers=HTMX)

    catalogo.gasolina.refresh_from_db()
    assert catalogo.gasolina.activo is False


def test_registro_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    assert cliente.get(f"/catalogos/personas/{ajena.pk}/").status_code == 404
    assert cliente.post(f"/catalogos/personas/{ajena.pk}/eliminar/").status_code == 404
    assert Persona.objects.filter(pk=ajena.pk).exists()


def test_catalogo_desconocido_da_404(cliente):
    assert cliente.get("/catalogos/otro/").status_code == 404


def test_cuentas_muestran_la_tasa_de_mercado(cliente, hogar):
    TasaMercado.objects.create(
        institucion="Banco Demo", producto="Clásica", tasa_promedio=D("0.4500")
    )
    Cuenta.objects.create(
        hogar=hogar,
        nombre="Demo",
        tipo=Cuenta.Tipo.CREDITO,
        institucion="banco demo",
        producto="clásica",
    )

    contenido = cliente.get("/catalogos/cuentas/").content.decode()

    assert "45.00% (promedio del mercado)" in contenido
```

En `tests/catalogos/test_catalogos_servicios.py`, agregar `from apps.catalogos.models import Cuenta, TasaMercado` y `from apps.catalogos.servicios import tasa_sugerida` a los imports, y al final:
```python
def test_tasa_sugerida(hogar):
    TasaMercado.objects.create(institucion="Banco Demo", producto="Clásica", tasa_promedio=D("0.45"))
    credito = Cuenta.Tipo.CREDITO

    capturada = Cuenta(hogar=hogar, nombre="A", tipo=credito, tasa_anual=D("0.30"))
    sin_tasa = Cuenta(
        hogar=hogar, nombre="B", tipo=credito, institucion="BANCO DEMO", producto="clásica"
    )
    debito = Cuenta(
        hogar=hogar,
        nombre="C",
        tipo=Cuenta.Tipo.DEBITO,
        institucion="Banco Demo",
        producto="Clásica",
    )
    desconocida = Cuenta(hogar=hogar, nombre="D", tipo=credito, institucion="Otro")

    assert tasa_sugerida(capturada) == D("0.30")
    assert tasa_sugerida(sin_tasa) == D("0.45")
    assert tasa_sugerida(debito) is None
    assert tasa_sugerida(desconocida) is None
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/catalogos -v`
Expected: FAIL con 404 en `/catalogos/...` e `ImportError` de `tasa_sugerida`.

- [ ] **Step 3: Tasa sugerida y formularios**

En `apps/catalogos/servicios.py`, cambiar el import de modelos a `from apps.catalogos.models import Categoria, Cuenta, TasaMercado` y agregar al final:
```python
def tasa_sugerida(cuenta):
    """RF-CAT-04: tasa capturada o, en tarjetas sin tasa, el promedio del mercado."""
    if cuenta.tasa_anual is not None:
        return cuenta.tasa_anual
    if cuenta.tipo != Cuenta.Tipo.CREDITO or not cuenta.institucion:
        return None
    tasa = TasaMercado.objects.filter(
        institucion__iexact=cuenta.institucion, producto__iexact=cuenta.producto
    ).first()
    return tasa.tasa_promedio if tasa else None
```

`apps/catalogos/formularios.py`:
```python
from django import forms

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.core.formularios import FormularioDeHogar


class FormularioCatalogo(FormularioDeHogar):
    """`grupos` = [(título, ayuda, [campos])]; sin grupos, los campos van en orden."""

    grupos = None

    def secciones(self):
        if not self.grupos:
            return []
        return [(titulo, ayuda, [self[c] for c in campos]) for titulo, ayuda, campos in self.grupos]


class FormularioPersona(FormularioCatalogo):
    class Meta:
        model = Persona
        fields = ["nombre", "parentesco", "activo"]


class FormularioDomicilio(FormularioCatalogo):
    class Meta:
        model = Domicilio
        fields = ["alias", "direccion", "activo"]


class FormularioCategoria(FormularioCatalogo):
    class Meta:
        model = Categoria
        fields = ["nombre", "icono", "orden", "activo"]


class FormularioConcepto(FormularioCatalogo):
    grupos = [
        (None, None, ["categoria", "nombre", "es_fijo", "es_hormiga", "activo"]),
        (
            "Valores sugeridos (opcional)",
            "Se precargan al registrar un movimiento; puedes cambiarlos en cada gasto.",
            ["persona", "cuenta", "domicilio"],
        ),
    ]

    class Meta:
        model = Concepto
        fields = [
            "categoria", "nombre", "es_fijo", "es_hormiga", "activo",
            "persona", "cuenta", "domicilio",
        ]  # fmt: skip


class FormularioCuenta(FormularioCatalogo):
    grupos = [
        (None, None, ["nombre", "tipo", "institucion", "producto", "titular", "ultimos_digitos",
                      "activo"]),
        (
            "Tarjeta de crédito",
            "Solo para tarjetas. Si no capturas la tasa, se usa el promedio del mercado.",
            ["linea_credito", "tasa_anual", "paga_total_mensual", "dia_corte", "dia_pago"],
        ),
        ("Préstamo", None, ["monto_inicial", "mensualidad"]),
        (
            "Saldo",
            "Positivo = lo que tienes (débito, efectivo) o lo que debes (crédito, préstamo).",
            ["saldo_actual", "fecha_saldo"],
        ),
    ]  # fmt: skip

    class Meta:
        model = Cuenta
        fields = [
            "nombre", "tipo", "institucion", "producto", "titular", "ultimos_digitos", "activo",
            "linea_credito", "tasa_anual", "paga_total_mensual", "dia_corte", "dia_pago",
            "monto_inicial", "mensualidad", "saldo_actual", "fecha_saldo",
        ]  # fmt: skip
        widgets = {"fecha_saldo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
```

- [ ] **Step 4: Vistas, URLs y plantillas**

`apps/catalogos/vistas.py`:
```python
from collections.abc import Callable
from dataclasses import dataclass

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalogos.formularios import (
    FormularioCategoria,
    FormularioConcepto,
    FormularioCuenta,
    FormularioDomicilio,
    FormularioPersona,
)
from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.catalogos.servicios import tasa_sugerida
from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.core.templatetags.formato import dinero, porcentaje


@dataclass(frozen=True)
class Catalogo:
    titulo: str
    singular: str
    modelo: type
    formulario: type
    columnas: tuple[tuple[str, Callable], ...]


def _sugeridos(concepto):
    valores = [concepto.persona, concepto.cuenta, concepto.domicilio]
    return " · ".join(str(valor) for valor in valores if valor) or "—"


def _tasa(cuenta):
    tasa = tasa_sugerida(cuenta)
    if tasa is None:
        return "—"
    return porcentaje(tasa) if cuenta.tasa_anual is not None else f"{porcentaje(tasa)} (promedio del mercado)"


CATALOGOS = {
    "personas": Catalogo(
        "Personas", "persona", Persona, FormularioPersona, (("Parentesco", lambda o: o.parentesco),)
    ),
    "domicilios": Catalogo(
        "Domicilios", "domicilio", Domicilio, FormularioDomicilio, (("Dirección", lambda o: o.direccion),)
    ),
    "categorias": Catalogo(
        "Categorías", "categoría", Categoria, FormularioCategoria, (("Orden", lambda o: o.orden),)
    ),
    "conceptos": Catalogo(
        "Conceptos",
        "concepto",
        Concepto,
        FormularioConcepto,
        (("Categoría", lambda o: o.categoria), ("Sugeridos", _sugeridos)),
    ),
    "cuentas": Catalogo(
        "Cuentas",
        "cuenta",
        Cuenta,
        FormularioCuenta,
        (
            ("Tipo", lambda o: o.get_tipo_display()),
            ("Saldo", lambda o: dinero(o.saldo_actual)),
            ("Tasa", _tasa),
        ),
    ),
}


def _catalogo(nombre):
    catalogo = CATALOGOS.get(nombre)
    if catalogo is None:
        raise Http404("Catálogo desconocido")
    return catalogo


@requiere_hogar
def indice(request):
    return render(request, "catalogos/indice.html", {"catalogos": CATALOGOS})


@requiere_hogar
def lista(request, catalogo):
    datos = _catalogo(catalogo)
    objetos = datos.modelo.objects.del_hogar(request.hogar)
    if datos.modelo is Concepto:
        objetos = objetos.select_related("categoria", "persona", "cuenta", "domicilio")
    filas = [
        (objeto, [(encabezado, funcion(objeto)) for encabezado, funcion in datos.columnas])
        for objeto in objetos
    ]
    contexto = {"catalogo": datos, "nombre": catalogo, "filas": filas}
    return render(request, "catalogos/lista.html", contexto)


@requiere_hogar
def nuevo(request, catalogo):
    return _editar(request, catalogo, None)


@requiere_hogar
def editar(request, catalogo, pk):
    datos = _catalogo(catalogo)
    objeto = get_object_or_404(datos.modelo.objects.del_hogar(request.hogar), pk=pk)
    return _editar(request, catalogo, objeto)


@requiere_hogar
@require_POST
def eliminar(request, catalogo, pk):
    """RF-CAT-05: lo que tiene registros asociados no se borra, se desactiva."""
    datos = _catalogo(catalogo)
    objeto = get_object_or_404(datos.modelo.objects.del_hogar(request.hogar), pk=pk)
    try:
        with transaction.atomic():
            objeto.delete()
        messages.success(request, f"Se eliminó {objeto}.")
    except (RestrictedError, ProtectedError):
        objeto.activo = False
        objeto.save(update_fields=["activo", "actualizado_en"])
        messages.info(request, f"{objeto} tiene registros asociados: se desactivó en lugar de borrarse.")
    return datos_actualizados() if es_htmx(request) else redirect("catalogos:lista", catalogo)


def _editar(request, catalogo, objeto):
    datos = _catalogo(catalogo)
    post = request.POST if request.method == "POST" else None
    formulario = datos.formulario(post, instance=objeto, hogar=request.hogar)
    if post is not None and formulario.is_valid():
        formulario.save()
        return datos_actualizados() if es_htmx(request) else redirect("catalogos:lista", catalogo)
    titulo = f"{'Editar' if objeto else 'Agregar'} {datos.singular}"
    return responder_formulario(
        request, {"formulario": formulario, "titulo": titulo, "accion": request.path}
    )
```

`apps/catalogos/urls.py`:
```python
from django.urls import path

from apps.catalogos import vistas

app_name = "catalogos"

urlpatterns = [
    path("", vistas.indice, name="indice"),
    path("<str:catalogo>/", vistas.lista, name="lista"),
    path("<str:catalogo>/nuevo/", vistas.nuevo, name="nuevo"),
    path("<str:catalogo>/<int:pk>/", vistas.editar, name="editar"),
    path("<str:catalogo>/<int:pk>/eliminar/", vistas.eliminar, name="eliminar"),
]
```

En `finanzas/urls.py`, antes de `path("", include("apps.core.urls")),`:
```python
    path("catalogos/", include("apps.catalogos.urls")),
```

`templates/catalogos/indice.html`:
```html
{% extends "base.html" %}
{% block titulo %}Más{% endblock %}
{% block contenido %}
<h1 class="mb-4 text-lg font-semibold">Más</h1>
<section class="tarjeta mb-4">
  <h2 class="mb-2 font-medium">Catálogos</h2>
  <ul class="divide-y divide-slate-100">
    {% for nombre, datos in catalogos.items %}
      <li><a class="block py-2 text-sky-700" href="{% url 'catalogos:lista' nombre %}">{{ datos.titulo }}</a></li>
    {% endfor %}
  </ul>
</section>
<section class="tarjeta space-y-2">
  <a class="block text-sky-700" href="{% url 'presupuesto:plantilla' %}">Plantilla de presupuesto</a>
  {% if user.is_staff %}<a class="block text-sky-700" href="{% url 'admin:index' %}">Administración avanzada</a>{% endif %}
  <form method="post" action="{% url 'logout' %}">{% csrf_token %}<button class="text-red-600">Salir</button></form>
</section>
{% endblock %}
```

`templates/catalogos/lista.html`:
```html
{% extends "base.html" %}
{% block titulo %}{{ catalogo.titulo }}{% endblock %}
{% block contenido %}
<header class="mb-4 flex items-center justify-between gap-2">
  <h1 class="text-lg font-semibold"><a class="text-slate-400" href="{% url 'catalogos:indice' %}">Más ›</a> {{ catalogo.titulo }}</h1>
  <button type="button" class="boton" hx-get="{% url 'catalogos:nuevo' nombre %}" hx-target="#modal-contenido">+ Agregar</button>
</header>
<section class="space-y-2">
  {% for objeto, valores in filas %}
    <article class="tarjeta flex items-start justify-between gap-3 {% if not objeto.activo %}opacity-60{% endif %}">
      <div class="min-w-0">
        <p class="font-medium">{{ objeto }}{% if not objeto.activo %} <span class="text-xs text-slate-500">(inactivo)</span>{% endif %}</p>
        <p class="text-xs text-slate-500">{% for encabezado, valor in valores %}{{ encabezado }}: {{ valor|default:"—" }}{% if not forloop.last %} · {% endif %}{% endfor %}</p>
      </div>
      <div class="flex shrink-0 gap-3 text-xs">
        <button type="button" class="text-sky-700" hx-get="{% url 'catalogos:editar' nombre objeto.pk %}" hx-target="#modal-contenido">Editar</button>
        <button type="button" class="text-red-600" hx-post="{% url 'catalogos:eliminar' nombre objeto.pk %}" hx-confirm="¿Eliminar? Si tiene registros asociados, se desactivará.">Eliminar</button>
      </div>
    </article>
  {% empty %}
    <p class="tarjeta text-slate-500">Todavía no hay registros.</p>
  {% endfor %}
</section>
{% endblock %}
```

`templates/componentes/navegacion.html`: después del enlace "Presupuesto", agregar:
```html
  <a href="{% url 'catalogos:indice' %}" class="flex flex-col items-center rounded-lg px-2 py-1 md:flex-row md:gap-2 hover:bg-slate-100"><span>☰</span><span>Más</span></a>
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_catalogos_vistas.py` 13 passed, `test_catalogos_servicios.py` 4 passed; todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps finanzas/urls.py templates tests/catalogos
git commit -m "feat(catalogos): personas, domicilios, categorias, conceptos y cuentas en la interfaz; desactivar en vez de borrar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Cierre: documentación, verificación completa y prueba de humo

**Files:**
- Modify: `README.md`
- Modify (fuera del repo): `..\CLAUDE.md` (estado del proyecto)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: README con el uso diario; suite, lint, imagen y humo verificados.

- [ ] **Step 1: README**

En `README.md`, reemplazar la última línea de "Primer uso" (`Luego entra a http://localhost:8000/admin/ ...`) por:
```markdown
Luego entra a http://localhost:8000 con tu email y contraseña:

- **Inicio**: tablero del mes (ingresos y gastos reales contra el presupuesto, categorías, deudas y alertas).
- **+**: registra un gasto, ingreso (aguinaldo, PTU…), transferencia o pago de deuda.
- **Movimientos**: lista del mes con filtros, totales y exportación a CSV.
- **Presupuesto**: plantilla base y ajustes de cada mes.
- **Más**: personas, domicilios, categorías, conceptos y cuentas.

Desde el celular en la misma red: `http://<IP-de-tu-PC>:8000` (agrega la IP a `DJANGO_ALLOWED_HOSTS` en `.env`).
```

- [ ] **Step 2: Verificación completa**

```powershell
docker compose build
docker compose run --rm css
docker compose run --rm web pytest --cov=apps --cov-report=term-missing
docker compose run --rm web ruff check .
docker compose run --rm web ruff format --check .
docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations --check --dry-run
sh tests/verificar_imagen.sh
```
Expected: `0 failed`; cobertura de `apps/calculos` 100 % y total ≥ 90 %; ruff sin errores ni archivos por formatear; `No changes detected`; `OK: ningún archivo sensible entró a la imagen`.

- [ ] **Step 3: Prueba de humo contra el servidor real**

Con `docker compose up -d` corriendo, guardar este script **fuera del repo** (por ejemplo en `$env:TEMP\humo.py`) y ejecutarlo. Crea una cuenta temporal, recorre las pantallas, registra un gasto y borra todo al final:
```python
from django.contrib.auth import get_user_model
from django.test import Client

from apps.catalogos.models import Categoria, Concepto
from apps.catalogos.servicios import sembrar_catalogos
from apps.core.servicios import crear_hogar

Usuario = get_user_model()
usuario = Usuario.objects.create_user(email="humo@example.com", password="humo-12345-x")
hogar = crear_hogar("Hogar de humo", usuario)
try:
    sembrar_catalogos(hogar)
    transporte = Categoria.objects.get(hogar=hogar, nombre="Transporte")
    gasolina = Concepto.objects.create(hogar=hogar, categoria=transporte, nombre="Gasolina")
    c = Client(HTTP_HOST="localhost")
    assert c.post("/entrar/", {"username": "HUMO@example.com", "password": "humo-12345-x"}).status_code == 302
    for url in ["/", "/tablero/2026/10/", "/movimientos/2026/10/", "/presupuesto/plantilla/",
                "/presupuesto/2026/10/", "/catalogos/", "/catalogos/conceptos/"]:
        r = c.get(url, follow=True)
        assert r.status_code == 200, (url, r.status_code)
    r = c.post("/movimientos/capturar/gasto/", {"monto": "650", "concepto": gasolina.pk,
               "fecha": "2026-10-09", "metodo_pago": "efectivo"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert "$650.00" in c.get("/tablero/2026/10/").content.decode()
    print("HUMO OK")
finally:
    hogar.delete()
    usuario.delete()
```
Run:
```powershell
Get-Content $env:TEMP\humo.py | docker compose exec -T web python manage.py shell
docker compose exec web python manage.py shell -c "from apps.core.models import Hogar; print(Hogar.objects.filter(nombre='Hogar de humo').count())"
```
Expected: `HUMO OK` y luego `0` (no quedan datos de prueba).

- [ ] **Step 4: Revisión visual en el celular (la hace el usuario)**

Abrir `http://localhost:8000` en la PC y, con la IP de la PC en `DJANGO_ALLOWED_HOSTS`, en el celular:
1. Entrar con su email.
2. Botón **+** → Gasto → monto + concepto → Guardar (≤ 3 toques tras abrir; el tablero se actualiza).
3. Ingreso tipo Aguinaldo → la casilla "extraordinario" se marca sola.
4. Presupuesto → agregar un gasto a la plantilla y ver el resumen.
5. Más → Conceptos → la sección "Valores sugeridos (opcional)".

- [ ] **Step 5: Commit y memoria del proyecto**

```powershell
git add README.md
git commit -m "docs: uso diario de la app en el README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

En `..\CLAUDE.md` (fuera del repo), sección "Estado / siguiente paso": marcar el plan 2 como completado y poner como siguiente el plan 3 (metas, deudas, patrimonio y simulador).
