# Plan 3 — Planeación: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar las hojas de planeación del Excel a la app: metas de ahorro, deudas (tarjetas y créditos), patrimonio neto y simulador de créditos, y mostrar metas y patrimonio en el tablero.

**Architecture:** Nueva app `apps/planeacion` con los modelos `MetaAhorro`, `Activo` y `SimulacionCredito`. Sus servicios (`servicios.py`) componen los cálculos puros que ya existen en `apps/calculos` (RN-05, RN-06, RN-07, RN-08, RN-10) con las cuentas del hogar. Las pantallas siguen el patrón del plan 2: vistas Django + HTMX, formularios en el modal (`responder_formulario`) y recarga tras guardar (`datos_actualizados`).

**Tech Stack:** Django 5.2, HTMX 2.0.11, Tailwind v4, PostgreSQL 17, pytest-django.

**Spec:** `docs/DEF.md`, `docs/ARQUITECTURA.md`, `docs/modelo-datos.dbml` (v1.0, aprobados 2026-10-09).

### Hoja de ruta (este es el plan 3 de 5)
| Plan | Contenido |
|---|---|
| 1 — Fundación ✅ | Docker, CI, usuario, hogar, catálogos (admin), motor de cálculos |
| 2 — Operación diaria ✅ | Login y UI, movimientos, presupuesto, tablero, catálogos en UI |
| **3 — Planeación (este)** | Metas, deudas, patrimonio, simulador; metas y patrimonio en el tablero |
| 4 — Importación IA | Django-Q2, worker, pypdf, Claude API, reglas, duplicados, revisión |
| 5 — Operación | PWA, Tailscale, respaldo, importación inicial desde Excel (incluye tasas de mercado y conceptos) |

Requisitos del DEF que cubre: MET-01..03, DEU-01..05, PAT-01..02, SIM-01..03, TAB-05 completo y la alerta de metas de TAB-06; reglas RN-05, RN-06, RN-07, RN-08 (por tarjeta), RN-09 y RN-10 en pantalla.

### Decisiones de este plan (para revisión del usuario)
1. **Las pantallas de planeación viven en "Más"** (sección "Planeación"): la barra inferior del celular ya tiene 5 botones.
2. **Las metas usan el presupuesto del mes actual** para el disponible y el % sobre ingresos, como la hoja "Metas de Ahorro" del Excel, que toma el disponible de "Mis Finanzas".
3. **El aporte mensual usa los meses que capturas** (igual que el Excel). La fecha de inicio solo sirve para mostrar cuándo termina la meta; no recalcula con los meses que faltan.
4. **Las tasas se capturan en %** (10 = 10 %) en metas y simulador; se guardan como fracción (0.10), igual que en el resto de la app.
5. **El valor de un activo se captura a mano**, aunque esté ligado a una cuenta; la liga es informativa.
6. **"Deudas" es una vista** sobre las cuentas de tipo tarjeta y préstamo (se editan en Más → Cuentas). Agrega el botón **Registrar pago** (RF-DEU-05), que abre la captura de pago de deuda con esa cuenta ya elegida.
7. **Simulador:** los pagos anticipados se escriben uno por renglón como `mes=monto` (ej. `3=5000`). El plazo máximo es 600 meses (50 años).
8. **Mensajes del Excel tal cual**, corrigiendo la errata "trajetas" → "tarjetas". El mensaje de metas usa la comparación estricta del Excel: si el disponible es exactamente igual al total de metas, muestra "no es suficiente".
9. **Alerta nueva en el tablero (RF-MET-03):** si el total mensual de las metas activas supera el disponible del presupuesto. Con filtro por persona o domicilio no se muestran metas ni esta alerta.
10. **Fuera de este plan:** el enlace "¿Quieres transferir tu deuda de tarjetas?" del simulador del Excel y la simulación de crecimiento del ahorro mes a mes.

## Global Constraints

- Python **3.12**; Django **>=5.2,<5.3**; PostgreSQL **17**.
- Dinero: `Decimal`, `DecimalField(max_digits=12, decimal_places=2)` (`valor_actual` de activos: `max_digits=14`). **Nunca `float`.** Tasas: fracción, `DecimalField(max_digits=7, decimal_places=4)`.
- Redondeo a 2 decimales **solo al mostrar** (`apps.calculos.comun.redondear`, filtros `dinero` y `porcentaje`).
- Nombres de dominio en **español**. Mensajes en español.
- `apps/calculos/` **no importa nada de Django**; este plan no lo modifica.
- Todo modelo de negocio hereda de `apps.core.models.ModeloDeHogar`. Toda consulta filtra por `request.hogar`. Id de otro hogar en la URL → **404**; en un formulario → **error de validación**.
- Toda vista usa `apps.core.acceso.requiere_hogar`. Todo formulario de un dato del hogar hereda de `apps.core.formularios.FormularioDeHogar`.
- Formularios en el modal con `apps.core.htmx.responder_formulario`; tras guardar o borrar con HTMX, `datos_actualizados()`.
- **Ningún dato personal en el repo**: ejemplos y fixtures ficticios (los montos de verificación del DEF sí se usan).
- Comandos desde PowerShell en `Finanzas\app_finanzas\`, dentro de Docker (`docker compose run --rm web ...`).
- Antes de cada commit: `ruff format apps tests` y `ruff check .` sin errores (sin caché si hay dudas: `ruff check --no-cache .`).
- Cada commit termina con la línea: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Entradas degeneradas en metas** (meses 0, objetivo 0, tasa negativa, ahorro actual mayor al objetivo) → error de formulario o aporte 0, nunca un 500. *Pruebas en Task 1 y Task 4.*
2. **Texto mal escrito en el simulador** (pagos anticipados ilegibles, mes fuera del plazo, monto 0, plazo de 10,000 meses) → mensaje de error en el formulario; nunca un 500 ni una tabla gigante. *Pruebas en Task 7.*
3. **Ids de otro hogar** (meta, activo, simulación guardada, cuenta o domicilio en un formulario, `cuenta_destino` en la URL de captura) → 404 o error de formulario. *Pruebas en Task 4, Task 5, Task 6 y Task 7.*
4. **Tarjeta sin línea, con saldo a favor o crédito sin monto inicial** → el % se muestra como "—" y nada truena. *Pruebas en Task 3 y Task 5.*
5. **Hogar vacío** (sin metas, activos ni deudas) → todas las pantallas y el tablero cargan con mensajes razonables. *Pruebas en Task 2, Task 5, Task 6 y Task 8.*

---

## Estructura de archivos

```
app_finanzas\
├── finanzas\settings.py                 (T1) INSTALLED_APPS += apps.planeacion
├── finanzas\urls.py                     (T4) planeacion/
├── apps\core\fechas.py                  (T2) sumar_meses
├── apps\core\formularios.py             (T4) CampoPorcentaje
├── apps\planeacion\
│   ├── __init__.py apps.py              (T1)
│   ├── models.py admin.py migrations\   (T1) MetaAhorro, Activo, SimulacionCredito
│   ├── mensajes.py                      (T2) textos del Excel (metas, uso de tarjetas, intereses)
│   ├── servicios.py                     (T2 metas; T3 deudas y patrimonio; T7 simulaciones)
│   ├── formularios.py                   (T4 meta; T6 activo; T7 simulador)
│   ├── vistas.py urls.py                (T4, T5, T6, T7)
├── apps\movimientos\vistas.py           (T5) captura con cuenta_destino precargada
├── apps\tablero\servicios.py            (T8) metas, patrimonio y alerta RF-MET-03
├── templates\
│   ├── planeacion\ metas.html (T4) deudas.html (T5) patrimonio.html (T6) simulador.html (T7)
│   ├── catalogos\indice.html            (T4–T7) sección "Planeación"
│   └── tablero\mes.html                 (T8)
└── tests\
    ├── core\ test_core_fechas.py (T2) test_core_formularios.py (T4)
    ├── planeacion\ test_plan_modelos.py (T1) test_plan_metas.py (T2) test_plan_deudas.py (T3)
    │              test_plan_vistas_metas.py (T4) test_plan_vistas_deudas.py (T5)
    │              test_plan_vistas_patrimonio.py (T6) test_plan_simulador.py (T7)
    └── tablero\test_tablero_planeacion.py (T8)
```

Los nombres de archivo de prueba son únicos a propósito (pytest con `--import-mode=importlib`, sin `__init__.py` en `tests/`). Las fixtures `hogar`, `otro_hogar`, `usuario`, `cliente`, `catalogo` y `plantilla_excel` ya existen en `tests/conftest.py` (planes 1 y 2).

---

### Task 1: Modelos de planeación

**Files:**
- Create: `apps/planeacion/__init__.py` (vacío), `apps/planeacion/apps.py`, `apps/planeacion/models.py`, `apps/planeacion/admin.py`, `apps/planeacion/migrations/__init__.py` (vacío), `apps/planeacion/migrations/0001_initial.py` (generado)
- Modify: `finanzas/settings.py` (INSTALLED_APPS)
- Test: `tests/planeacion/test_plan_modelos.py`

**Interfaces:**
- Consumes: `ModeloDeHogar`; `Cuenta`, `Domicilio`, `DINERO`, `TASA` (`apps.catalogos.models`); `aporte_mensual_meta` (`apps.calculos.metas`); `amortizar`, `Amortizacion` (`apps.calculos.credito`).
- Produces:
  - `apps.planeacion.models.MESES_MAXIMOS = 600`.
  - `MetaAhorro(hogar, tipo, nombre, monto_objetivo, ahorro_actual, meses, tasa_anual, fecha_inicio, cuenta, activa)` con `MetaAhorro.Tipo` (`auto, casa, compra_importante, educacion, fondo_emergencia, regalo, remodelacion, vacaciones, otro`) y método `aporte_mensual() -> Decimal` (RN-05).
  - `Activo(hogar, tipo, nombre, valor_actual, fecha_valuacion, domicilio, cuenta, activo)` con `Activo.Tipo` (`acciones, auto, inmueble, cuenta_ahorro, cuenta_inversion, afore, stock_options, terreno, otro`).
  - `SimulacionCredito(hogar, nombre, monto, tasa_anual, meses, comision_apertura, pagos_anticipados)` (JSON `{"<mes>": "<monto>"}`) con `anticipados() -> dict[int, Decimal]` y `amortizacion() -> Amortizacion` (RN-07); `clean()` rechaza combinaciones que `amortizar` no acepta.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/planeacion/test_plan_modelos.py`:
```python
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.calculos.comun import redondear
from apps.catalogos.models import Cuenta, Domicilio
from apps.planeacion.models import Activo, MetaAhorro, SimulacionCredito

pytestmark = pytest.mark.django_db


def meta(hogar, **campos):
    datos = {"hogar": hogar, "nombre": "Regalo", "monto_objetivo": D("20000")}
    datos.update(campos)
    return MetaAhorro(**datos)


def errores(objeto):
    with pytest.raises(ValidationError) as error:
        objeto.full_clean()
    return error.value.message_dict


def test_aporte_mensual_de_la_meta_del_excel(hogar):
    regalo = meta(hogar)

    regalo.full_clean()

    assert (regalo.meses, regalo.tasa_anual, regalo.ahorro_actual) == (12, D("0.10"), 0)
    assert redondear(regalo.aporte_mensual()) == D("1591.65")


def test_meta_ya_alcanzada_requiere_cero(hogar):
    assert meta(hogar, ahorro_actual=D("25000")).aporte_mensual() == 0


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("meses", 0), ("meses", 601), ("monto_objetivo", D("0")), ("tasa_anual", D("-0.01")),
     ("ahorro_actual", D("-1"))],
)  # fmt: skip
def test_meta_con_datos_invalidos(hogar, campo, valor):
    assert campo in errores(meta(hogar, **{campo: valor}))


def test_meta_con_cuenta_de_otro_hogar_es_invalida(hogar, otro_hogar):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.AHORRO)

    assert "cuenta" in errores(meta(hogar, cuenta=ajena))


def test_activo_con_valor_negativo_o_domicilio_ajeno(hogar, otro_hogar):
    ajeno = Domicilio.objects.create(hogar=otro_hogar, alias="Ajeno")

    assert "valor_actual" in errores(Activo(hogar=hogar, nombre="Auto", valor_actual=D("-1")))
    assert "domicilio" in errores(
        Activo(hogar=hogar, nombre="Casa", valor_actual=D("1"), domicilio=ajeno)
    )


def test_simulacion_reproduce_el_simulador_del_excel(hogar):
    simulacion = SimulacionCredito(
        hogar=hogar,
        nombre="Préstamo personal",
        monto=D("30000"),
        tasa_anual=D("0.25"),
        meses=12,
        comision_apertura=D("0.015"),
    )

    simulacion.full_clean()
    tabla = simulacion.amortizacion()

    assert tabla.capital_inicial == D("30450")
    assert redondear(tabla.mensualidad) == D("2857.62")
    assert redondear(tabla.total_intereses) == D("3841.45")


def test_simulacion_lee_los_pagos_anticipados(hogar):
    simulacion = SimulacionCredito(
        hogar=hogar,
        nombre="Con abono",
        monto=D("30000"),
        tasa_anual=D("0.25"),
        meses=12,
        pagos_anticipados={"3": "5000.00"},
    )

    assert simulacion.anticipados() == {3: D("5000.00")}
    assert simulacion.amortizacion().filas[2].pago_anticipado == D("5000.00")


@pytest.mark.parametrize(
    "pagos", [{"13": "100"}, {"tres": "100"}, {"2": "mucho"}, {"2": "-5"}]
)
def test_simulacion_con_pagos_anticipados_invalidos(hogar, pagos):
    simulacion = SimulacionCredito(
        hogar=hogar, nombre="X", monto=D("1000"), tasa_anual=D("0.1"), meses=12,
        pagos_anticipados=pagos,
    )  # fmt: skip

    assert "__all__" in errores(simulacion)


def test_simulacion_con_plazo_excesivo(hogar):
    simulacion = SimulacionCredito(
        hogar=hogar, nombre="X", monto=D("1000"), tasa_anual=D("0.1"), meses=601
    )

    assert "meses" in errores(simulacion)


def test_borrar_el_hogar_borra_su_planeacion(hogar):
    meta(hogar).save()
    Activo.objects.create(hogar=hogar, nombre="Auto", valor_actual=D("150000"))
    SimulacionCredito.objects.create(
        hogar=hogar, nombre="X", monto=D("1000"), tasa_anual=D("0.1"), meses=12
    )

    hogar.delete()

    assert not MetaAhorro.objects.exists()
    assert not Activo.objects.exists()
    assert not SimulacionCredito.objects.exists()


def test_borrar_la_cuenta_de_una_meta_conserva_la_meta(hogar):
    ahorro = Cuenta.objects.create(hogar=hogar, nombre="Ahorro", tipo=Cuenta.Tipo.AHORRO)
    regalo = meta(hogar, cuenta=ahorro)
    regalo.save()

    ahorro.delete()

    regalo.refresh_from_db()
    assert regalo.cuenta is None
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/planeacion/test_plan_modelos.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'apps.planeacion'`.

- [ ] **Step 3: Implementar**

`apps/planeacion/apps.py`:
```python
from django.apps import AppConfig


class PlaneacionConfig(AppConfig):
    name = "apps.planeacion"
    verbose_name = "Planeación"
```

`apps/planeacion/models.py`:
```python
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.calculos.credito import amortizar
from apps.calculos.metas import aporte_mensual_meta
from apps.catalogos.models import DINERO, TASA, Cuenta, Domicilio
from apps.core.models import ModeloDeHogar

MESES_MAXIMOS = 600
NO_NEGATIVO = [MinValueValidator(Decimal("0"))]
POSITIVO = [MinValueValidator(Decimal("0.01"))]
PLAZO = [MinValueValidator(1), MaxValueValidator(MESES_MAXIMOS)]


class MetaAhorro(ModeloDeHogar):
    class Tipo(models.TextChoices):
        AUTO = "auto", "🚗 Auto"
        CASA = "casa", "🏡 Casa"
        COMPRA_IMPORTANTE = "compra_importante", "🛍️ Compra importante"
        EDUCACION = "educacion", "🎓 Educación"
        FONDO_EMERGENCIA = "fondo_emergencia", "🛟 Fondo de emergencia"
        REGALO = "regalo", "🎁 Regalo"
        REMODELACION = "remodelacion", "🔨 Remodelación"
        VACACIONES = "vacaciones", "🏖️ Vacaciones"
        OTRO = "otro", "🎲 Otro"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OTRO)
    nombre = models.CharField(max_length=80)
    monto_objetivo = models.DecimalField("meta de ahorro total", validators=POSITIVO, **DINERO)
    ahorro_actual = models.DecimalField(
        "ahorro actual", default=Decimal("0"), validators=NO_NEGATIVO, **DINERO
    )
    meses = models.PositiveSmallIntegerField("meses para ahorrar", default=12, validators=PLAZO)
    tasa_anual = models.DecimalField(
        "tasa de interés anual", default=Decimal("0.10"), validators=NO_NEGATIVO, **TASA
    )
    fecha_inicio = models.DateField("fecha de inicio", default=timezone.localdate)
    cuenta = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Opcional: la cuenta donde guardas este ahorro.",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "meta de ahorro"
        verbose_name_plural = "metas de ahorro"
        ordering = ["-activa", "nombre"]

    def __str__(self):
        return self.nombre

    def aporte_mensual(self):
        """RN-05: ahorro mensual necesario para llegar a la meta."""
        return aporte_mensual_meta(self.monto_objetivo, self.ahorro_actual, self.meses, self.tasa_anual)


class Activo(ModeloDeHogar):
    class Tipo(models.TextChoices):
        ACCIONES = "acciones", "📈 Acciones"
        AUTO = "auto", "🚗 Auto"
        INMUEBLE = "inmueble", "🏡 Casa o departamento"
        CUENTA_AHORRO = "cuenta_ahorro", "💰 Cuenta de ahorro"
        CUENTA_INVERSION = "cuenta_inversion", "📊 Cuenta de inversión"
        AFORE = "afore", "👵 Afore"
        STOCK_OPTIONS = "stock_options", "🧾 Stock options"
        TERRENO = "terreno", "🌄 Terreno"
        OTRO = "otro", "🎲 Otro"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OTRO)
    nombre = models.CharField(max_length=120)
    valor_actual = models.DecimalField(
        "valor actual", max_digits=14, decimal_places=2, validators=NO_NEGATIVO
    )
    fecha_valuacion = models.DateField("fecha de valuación", default=timezone.localdate)
    domicilio = models.ForeignKey(
        Domicilio,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Opcional: si el activo es un inmueble.",
    )
    cuenta = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Opcional: si el valor viene de una cuenta (ahorro, inversión, afore).",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "activo"
        verbose_name_plural = "activos"
        ordering = ["-activo", "-valor_actual", "nombre"]

    def __str__(self):
        return self.nombre


class SimulacionCredito(ModeloDeHogar):
    nombre = models.CharField(max_length=80)
    monto = models.DecimalField("crédito total", validators=POSITIVO, **DINERO)
    tasa_anual = models.DecimalField("tasa de interés anual", validators=NO_NEGATIVO, **TASA)
    meses = models.PositiveSmallIntegerField("duración en meses", validators=PLAZO)
    comision_apertura = models.DecimalField(
        "comisión por apertura", default=Decimal("0"), validators=NO_NEGATIVO, **TASA
    )
    pagos_anticipados = models.JSONField(
        "pagos anticipados", default=dict, blank=True, help_text='{"<mes>": "<monto>"}'
    )

    class Meta:
        verbose_name = "simulación de crédito"
        verbose_name_plural = "simulaciones de crédito"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def anticipados(self):
        return {int(mes): Decimal(str(monto)) for mes, monto in self.pagos_anticipados.items()}

    def amortizacion(self):
        """RN-07: tabla de amortización con comisión y pagos anticipados."""
        return amortizar(
            self.monto, self.tasa_anual, self.meses, self.comision_apertura, self.anticipados()
        )

    def clean(self):
        super().clean()
        if None in (self.monto, self.tasa_anual, self.meses, self.comision_apertura):
            return
        if not 1 <= self.meses <= MESES_MAXIMOS:
            return
        try:
            self.amortizacion()
        except (ValueError, TypeError, InvalidOperation) as error:
            raise ValidationError(str(error)) from error
```

`apps/planeacion/admin.py`:
```python
from django.contrib import admin

from apps.planeacion.models import Activo, MetaAhorro, SimulacionCredito


@admin.register(MetaAhorro)
class MetaAhorroAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "monto_objetivo", "ahorro_actual", "meses", "activa", "hogar")
    list_filter = ("hogar", "tipo", "activa")


@admin.register(Activo)
class ActivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "valor_actual", "fecha_valuacion", "activo", "hogar")
    list_filter = ("hogar", "tipo", "activo")


@admin.register(SimulacionCredito)
class SimulacionCreditoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "monto", "tasa_anual", "meses", "hogar")
    list_filter = ("hogar",)
```

En `finanzas/settings.py`, agregar `"apps.planeacion",` después de `"apps.presupuesto",` en `INSTALLED_APPS`.

- [ ] **Step 4: Generar la migración**

Run: `docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations planeacion`
Expected: `apps/planeacion/migrations/0001_initial.py` con `Create model Activo`, `Create model MetaAhorro` y `Create model SimulacionCredito`.

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_plan_modelos.py` 18 passed; todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/planeacion finanzas/settings.py tests/planeacion/test_plan_modelos.py
git commit -m "feat(planeacion): metas de ahorro, activos y simulaciones de credito" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Servicio de metas (MET-02, MET-03) y mensajes del Excel

**Files:**
- Modify: `apps/core/fechas.py` (agregar `sumar_meses`)
- Create: `apps/planeacion/mensajes.py`, `apps/planeacion/servicios.py`
- Test: `tests/core/test_core_fechas.py` (agregar), `tests/planeacion/test_plan_metas.py`

**Interfaces:**
- Consumes: `MetaAhorro` (Task 1); `ResumenPresupuesto`, `resumir_presupuesto`, `LineaIngreso`, `LineaGasto` (`apps.calculos.presupuesto`); `BIEN, CUIDADO, ALERTA` (`apps.presupuesto.mensajes`); `NIVEL_BUENO, NIVEL_CUIDADO, NIVEL_RIESGO` (`apps.calculos.deudas`); fixture `plantilla_excel`; `resumen_plantilla` (`apps.presupuesto.servicios`).
- Produces:
  - `apps.core.fechas.sumar_meses(fecha: date, meses: int) -> date` (el día se recorta al último día del mes destino).
  - `apps.planeacion.mensajes`: `mensaje_metas(disponible, total_metas) -> (nivel, texto)`, `mensaje_uso(nivel_de_uso | None) -> str`, `mensaje_tarjeta(paga_total_mensual: bool | None) -> str`.
  - `apps.planeacion.servicios`: `FilaMeta(meta, aporte, fecha_fin)`, `ResumenMetas(filas, total_mensual, porcentaje_ingresos, nivel, mensaje)` y `resumir_metas(hogar, resumen: ResumenPresupuesto) -> ResumenMetas` (solo metas activas; `porcentaje_ingresos` es `None` si no hay ingresos).

- [ ] **Step 1: Escribir las pruebas que fallan**

En `tests/core/test_core_fechas.py`, agregar `sumar_meses` al import de `apps.core.fechas` y al final:
```python
def test_sumar_meses():
    assert sumar_meses(date(2026, 10, 9), 12) == date(2027, 10, 9)
    assert sumar_meses(date(2026, 11, 15), 3) == date(2027, 2, 15)
    assert sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert sumar_meses(date(2026, 3, 1), 0) == date(2026, 3, 1)
```

`tests/planeacion/test_plan_metas.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.calculos.presupuesto import LineaGasto, LineaIngreso, resumir_presupuesto
from apps.planeacion.mensajes import mensaje_metas, mensaje_tarjeta, mensaje_uso
from apps.planeacion.models import MetaAhorro
from apps.planeacion.servicios import resumir_metas
from apps.presupuesto.mensajes import ALERTA, BIEN, CUIDADO
from apps.presupuesto.servicios import resumen_plantilla

pytestmark = pytest.mark.django_db


def resumen(ingresos, gastos):
    return resumir_presupuesto(
        [LineaIngreso(monto=D(ingresos))], [LineaGasto(monto=D(gastos))], D("0.05")
    )


def metas_del_excel(hogar):
    for nombre, monto in [("Regalo", "20000"), ("Vacaciones", "45000")]:
        MetaAhorro.objects.create(
            hogar=hogar,
            nombre=nombre,
            monto_objetivo=D(monto),
            fecha_inicio=date(2026, 10, 1),
        )


def test_metas_del_excel(plantilla_excel, hogar):
    metas_del_excel(hogar)

    r = resumir_metas(hogar, resumen_plantilla(plantilla_excel))

    assert [redondear(f.aporte) for f in r.filas] == [D("1591.65"), D("3581.21")]
    assert redondear(r.total_mensual) == D("5172.87")
    assert redondear(r.porcentaje_ingresos, 4) == D("0.1569")
    assert r.nivel == CUIDADO
    assert r.filas[0].fecha_fin == date(2027, 10, 1)


def test_metas_inactivas_y_de_otro_hogar_no_cuentan(hogar, otro_hogar):
    metas_del_excel(hogar)
    MetaAhorro.objects.filter(nombre="Vacaciones").update(activa=False)
    MetaAhorro.objects.create(hogar=otro_hogar, nombre="Ajena", monto_objetivo=D("99999"))

    r = resumir_metas(hogar, resumen("32977.52", "29235"))

    assert [f.meta.nombre for f in r.filas] == ["Regalo"]


def test_sin_metas_ni_ingresos(hogar):
    r = resumir_metas(hogar, resumen("0", "0"))

    assert (r.filas, r.total_mensual, r.porcentaje_ingresos) == ([], 0, None)


def test_mensajes_de_metas():
    assert mensaje_metas(D("6000"), D("5172.87"))[0] == BIEN
    assert mensaje_metas(D("5172.87"), D("5172.87"))[0] == CUIDADO
    assert mensaje_metas(D("-1"), D("0"))[0] == ALERTA
    assert mensaje_metas(D("-1"), D("0"))[1].startswith("⛔ ¡Tus gastos son mayores")


def test_mensajes_de_tarjetas():
    assert mensaje_uso("bueno").startswith("👏¡Buen nivel")
    assert mensaje_uso("cuidado").startswith("⚠️ Cuidado con el uso")
    assert mensaje_uso("riesgo") == "⛔ Usas demasiado tus tarjetas, considera disminuir tus gastos."
    assert mensaje_uso(None) == ""
    assert mensaje_tarjeta(False).startswith("⚠️ Cuidado, estás perdiendo dinero en intereses")
    assert mensaje_tarjeta(True).startswith("👏¡Bien!")
    assert mensaje_tarjeta(None) == ""
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/core/test_core_fechas.py tests/planeacion/test_plan_metas.py -v`
Expected: ERROR con `ImportError: cannot import name 'sumar_meses'` y `ModuleNotFoundError: No module named 'apps.planeacion.mensajes'`.

- [ ] **Step 3: Implementar**

En `apps/core/fechas.py`, al final:
```python
def sumar_meses(fecha, meses):
    """Misma fecha `meses` después; el día se ajusta al último del mes si no existe."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))
```

`apps/planeacion/mensajes.py`:
```python
"""Mensajes de las hojas "Metas de Ahorro" y "Deudas" del Excel."""

from apps.calculos.deudas import NIVEL_BUENO, NIVEL_CUIDADO, NIVEL_RIESGO
from apps.presupuesto.mensajes import ALERTA, BIEN, CUIDADO


def mensaje_metas(disponible, total_metas):
    if disponible < 0:
        return ALERTA, (
            "⛔ ¡Tus gastos son mayores a tus ingresos! Recorta gastos para retomar tus metas "
            "de ahorro."
        )
    if disponible > total_metas:
        return BIEN, (
            "👏 ¡Felicidades! Tienes suficiente al final de mes para lograr tus metas de ahorro."
        )
    return CUIDADO, (
        "⚠️ Parece que lo disponible del mes no es suficiente para lograr tus metas de ahorro."
    )


MENSAJES_USO = {
    NIVEL_BUENO: "👏¡Buen nivel de uso de tus tarjetas!",
    NIVEL_CUIDADO: (
        "⚠️ Cuidado con el uso de tus tarjetas. Puede ser buena idea que adelantes pagos de "
        "tus mensualidades."
    ),
    NIVEL_RIESGO: "⛔ Usas demasiado tus tarjetas, considera disminuir tus gastos.",
}


def mensaje_uso(nivel):
    return MENSAJES_USO.get(nivel, "")


def mensaje_tarjeta(paga_total_mensual):
    if paga_total_mensual is None:
        return ""
    if paga_total_mensual:
        return "👏¡Bien! Esa es la mejor manera de usar tus tarjetas."
    return "⚠️ Cuidado, estás perdiendo dinero en intereses. Considera refinanciar tu tarjeta."
```

`apps/planeacion/servicios.py`:
```python
"""Servicios de planeación: metas, deudas, patrimonio y simulaciones."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.calculos.comun import CERO
from apps.core.fechas import sumar_meses
from apps.planeacion.mensajes import mensaje_metas
from apps.planeacion.models import MetaAhorro


@dataclass(frozen=True)
class FilaMeta:
    meta: MetaAhorro
    aporte: Decimal
    fecha_fin: date


@dataclass(frozen=True)
class ResumenMetas:
    filas: list
    total_mensual: Decimal
    porcentaje_ingresos: Decimal | None
    nivel: str
    mensaje: str


def resumir_metas(hogar, resumen):
    """RF-MET-02 y RF-MET-03 con el disponible e ingresos de un resumen de presupuesto."""
    metas = MetaAhorro.objects.del_hogar(hogar).filter(activa=True).select_related("cuenta")
    filas = [
        FilaMeta(
            meta=meta,
            aporte=meta.aporte_mensual(),
            fecha_fin=sumar_meses(meta.fecha_inicio, meta.meses),
        )
        for meta in metas
    ]
    total = sum((fila.aporte for fila in filas), CERO)
    ingresos = resumen.ingresos_totales
    nivel, mensaje = mensaje_metas(resumen.disponible, total)
    return ResumenMetas(
        filas=filas,
        total_mensual=total,
        porcentaje_ingresos=total / ingresos if ingresos > 0 else None,
        nivel=nivel,
        mensaje=mensaje,
    )
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_core_fechas.py` 9 passed, `test_plan_metas.py` 5 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/core/fechas.py apps/planeacion tests/core/test_core_fechas.py tests/planeacion/test_plan_metas.py
git commit -m "feat(planeacion): resumen de metas de ahorro con aporte mensual y mensajes del Excel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Servicios de deudas y patrimonio (DEU-01..04, PAT-02)

**Files:**
- Modify: `apps/planeacion/servicios.py`
- Test: `tests/planeacion/test_plan_deudas.py`

**Interfaces:**
- Consumes: `Activo` (Task 1); `mensaje_uso`, `mensaje_tarjeta` (Task 2); `Cuenta`, `TasaMercado`; `resumir_deudas`, `ResumenDeudas`, `tasa_sugerida` (`apps.catalogos.servicios`); `TarjetaCredito`, `uso_de_credito`, `nivel_de_uso`, `porcentaje_completado`, `patrimonio_neto` (`apps.calculos.deudas`); `obtener_presupuesto_mes`, `resumen_mes` (presupuesto); `movimientos_del_mes`, `totales`, `Filtros` (movimientos); fixtures `catalogo` (tarjeta línea 7,100 saldo 6,839.01 sin pago total; préstamo inicial 41,130 saldo 38,679.72 mensualidad 1,500) y `plantilla_excel`.
- Produces:
  - `FilaTarjeta(cuenta, tasa, tasa_de_mercado, uso, nivel, mensaje)`, `FilaCredito(cuenta, completado)`, `VistaDeudas(tarjetas, creditos, resumen, mensaje_uso, gasto_tarjeta_presupuesto, gasto_tarjeta_real)` y `vista_deudas(hogar, anio, mes) -> VistaDeudas`.
  - `Patrimonio(activos, total_activos, deuda_creditos, deuda_tarjetas, neto)` y `calcular_patrimonio(hogar) -> Patrimonio` (RN-10; solo activos y cuentas activos).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/planeacion/test_plan_deudas.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.catalogos.models import Cuenta, TasaMercado
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento
from apps.planeacion.models import Activo
from apps.planeacion.servicios import calcular_patrimonio, vista_deudas

pytestmark = pytest.mark.django_db


def test_tarjetas_y_creditos_del_hogar(catalogo):
    v = vista_deudas(catalogo.tarjeta.hogar, 2026, 10)

    (tarjeta,) = v.tarjetas
    assert tarjeta.cuenta == catalogo.tarjeta
    assert redondear(tarjeta.uso, 4) == D("0.9632")
    assert tarjeta.nivel == "riesgo"
    assert tarjeta.mensaje.startswith("⚠️ Cuidado, estás perdiendo dinero")
    assert (tarjeta.tasa, tarjeta.tasa_de_mercado) == (None, False)
    (credito,) = v.creditos
    assert redondear(credito.completado, 4) == D("0.0596")
    assert v.resumen.total_tarjetas + v.resumen.total_creditos == D("45518.73")
    assert v.mensaje_uso.startswith("⛔ Usas demasiado")


def test_tasa_promedio_del_mercado(hogar):
    TasaMercado.objects.create(institucion="Banco Demo", producto="Clásica", tasa_promedio=D("0.45"))
    Cuenta.objects.create(
        hogar=hogar,
        nombre="Demo",
        tipo=Cuenta.Tipo.CREDITO,
        institucion="Banco Demo",
        producto="Clásica",
        linea_credito=D("10000"),
    )

    (tarjeta,) = vista_deudas(hogar, 2026, 10).tarjetas

    assert (tarjeta.tasa, tarjeta.tasa_de_mercado) == (D("0.45"), True)


def test_sin_linea_ni_monto_inicial_no_truena(hogar):
    Cuenta.objects.create(
        hogar=hogar, nombre="Sin línea", tipo=Cuenta.Tipo.CREDITO, saldo_actual=D("-50")
    )
    Cuenta.objects.create(hogar=hogar, nombre="Sin inicial", tipo=Cuenta.Tipo.PRESTAMO)

    v = vista_deudas(hogar, 2026, 10)

    assert (v.tarjetas[0].uso, v.tarjetas[0].nivel) == (None, None)
    assert v.creditos[0].completado is None
    assert v.resumen.total_tarjetas == 0


def test_gasto_con_tarjeta_presupuestado_y_real(plantilla_excel, catalogo, hogar):
    for monto, metodo in [("300", MetodoPago.TARJETA_CREDITO), ("100", MetodoPago.EFECTIVO)]:
        guardar_movimiento(
            Movimiento(
                hogar=hogar,
                tipo=Movimiento.Tipo.GASTO,
                monto=D(monto),
                concepto=catalogo.gasolina,
                metodo_pago=metodo,
                fecha=date(2026, 10, 5),
            )
        )

    v = vista_deudas(hogar, 2026, 10)

    assert v.gasto_tarjeta_presupuesto == D("1298")
    assert v.gasto_tarjeta_real == D("300")


def test_hogar_sin_deudas(hogar):
    v = vista_deudas(hogar, 2026, 10)

    assert (v.tarjetas, v.creditos, v.mensaje_uso) == ([], [], "")


def test_patrimonio_neto_del_excel(catalogo, hogar, otro_hogar):
    for nombre, valor in [("Casa", "2400000"), ("Auto", "150000"), ("Ahorro", "43519.94")]:
        Activo.objects.create(hogar=hogar, nombre=nombre, valor_actual=D(valor))
    Activo.objects.create(hogar=hogar, nombre="Vendido", valor_actual=D("1"), activo=False)
    Activo.objects.create(hogar=otro_hogar, nombre="Ajeno", valor_actual=D("999"))

    p = calcular_patrimonio(hogar)

    assert p.total_activos == D("2593519.94")
    assert (p.deuda_creditos, p.deuda_tarjetas) == (D("38679.72"), D("6839.01"))
    assert p.neto == D("2548001.21")
    assert len(p.activos) == 3


def test_patrimonio_de_un_hogar_vacio(hogar):
    p = calcular_patrimonio(hogar)

    assert (p.activos, p.total_activos, p.neto) == ([], 0, 0)
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/planeacion/test_plan_deudas.py -v`
Expected: ERROR con `ImportError: cannot import name 'calcular_patrimonio'`.

- [ ] **Step 3: Implementar**

En `apps/planeacion/servicios.py`, reemplazar los imports por:
```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.calculos.comun import CERO
from apps.calculos.deudas import (
    TarjetaCredito,
    nivel_de_uso,
    patrimonio_neto,
    porcentaje_completado,
    uso_de_credito,
)
from apps.catalogos.models import Cuenta
from apps.catalogos.servicios import ResumenDeudas, resumir_deudas, tasa_sugerida
from apps.core.fechas import sumar_meses
from apps.movimientos.consultas import Filtros, movimientos_del_mes, totales
from apps.movimientos.models import MetodoPago, Movimiento
from apps.planeacion.mensajes import mensaje_metas, mensaje_tarjeta, mensaje_uso
from apps.planeacion.models import Activo, MetaAhorro
from apps.presupuesto.servicios import obtener_presupuesto_mes, resumen_mes
```
y agregar al final:
```python
@dataclass(frozen=True)
class FilaTarjeta:
    cuenta: Cuenta
    tasa: Decimal | None
    tasa_de_mercado: bool
    uso: Decimal | None
    nivel: str | None
    mensaje: str


@dataclass(frozen=True)
class FilaCredito:
    cuenta: Cuenta
    completado: Decimal | None


@dataclass(frozen=True)
class VistaDeudas:
    tarjetas: list
    creditos: list
    resumen: ResumenDeudas
    mensaje_uso: str
    gasto_tarjeta_presupuesto: Decimal
    gasto_tarjeta_real: Decimal


def vista_deudas(hogar, anio, mes):
    """RF-DEU-01..04 con las cuentas activas y el presupuesto y gastos del mes."""
    cuentas = Cuenta.objects.del_hogar(hogar).filter(activo=True)
    tarjetas = []
    for tarjeta in cuentas.filter(tipo=Cuenta.Tipo.CREDITO):
        tasa = tasa_sugerida(tarjeta)
        uso = uso_de_credito(
            [TarjetaCredito(saldo=tarjeta.saldo_actual, linea=tarjeta.linea_credito or CERO)]
        )
        tarjetas.append(
            FilaTarjeta(
                cuenta=tarjeta,
                tasa=tasa,
                tasa_de_mercado=tarjeta.tasa_anual is None and tasa is not None,
                uso=uso,
                nivel=None if uso is None else nivel_de_uso(uso),
                mensaje=mensaje_tarjeta(tarjeta.paga_total_mensual),
            )
        )
    creditos = [
        FilaCredito(
            cuenta=credito,
            completado=porcentaje_completado(credito.monto_inicial or CERO, credito.saldo_actual),
        )
        for credito in cuentas.filter(tipo=Cuenta.Tipo.PRESTAMO)
    ]
    resumen = resumir_deudas(hogar)
    filtros = Filtros(tipo=Movimiento.Tipo.GASTO, metodo_pago=MetodoPago.TARJETA_CREDITO)
    return VistaDeudas(
        tarjetas=tarjetas,
        creditos=creditos,
        resumen=resumen,
        mensaje_uso=mensaje_uso(resumen.nivel),
        gasto_tarjeta_presupuesto=resumen_mes(
            obtener_presupuesto_mes(hogar, anio, mes)
        ).gasto_con_tarjeta,
        gasto_tarjeta_real=totales(movimientos_del_mes(hogar, anio, mes, filtros)).gastos,
    )


@dataclass(frozen=True)
class Patrimonio:
    activos: list
    total_activos: Decimal
    deuda_creditos: Decimal
    deuda_tarjetas: Decimal
    neto: Decimal


def calcular_patrimonio(hogar):
    """RN-10: Σ activos − Σ saldos de préstamos − Σ saldos de tarjetas."""
    activos = list(
        Activo.objects.del_hogar(hogar).filter(activo=True).select_related("domicilio", "cuenta")
    )
    deudas = resumir_deudas(hogar)
    total = sum((activo.valor_actual for activo in activos), CERO)
    return Patrimonio(
        activos=activos,
        total_activos=total,
        deuda_creditos=deudas.total_creditos,
        deuda_tarjetas=deudas.total_tarjetas,
        neto=patrimonio_neto([total], [deudas.total_creditos], [deudas.total_tarjetas]),
    )
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_plan_deudas.py` 7 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/planeacion tests/planeacion/test_plan_deudas.py
git commit -m "feat(planeacion): vista de deudas por tarjeta y credito, y patrimonio neto" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Pantalla de metas de ahorro (P6) y campo de porcentaje

**Files:**
- Modify: `apps/core/formularios.py` (agregar `CampoPorcentaje`), `finanzas/urls.py`, `templates/catalogos/indice.html`
- Create: `apps/planeacion/formularios.py`, `apps/planeacion/vistas.py`, `apps/planeacion/urls.py`, `templates/planeacion/metas.html`
- Test: `tests/core/test_core_formularios.py` (agregar), `tests/planeacion/test_plan_vistas_metas.py`

**Interfaces:**
- Consumes: `MetaAhorro` (Task 1); `resumir_metas` (Task 2); `FormularioDeHogar`, `requiere_hogar`, `responder_formulario`, `datos_actualizados`, `es_htmx` (plan 2); `obtener_presupuesto_mes`, `resumen_mes` (presupuesto).
- Produces:
  - `apps.core.formularios.CampoPorcentaje(maximo=Decimal("100"), **kwargs)`: campo decimal que se captura y muestra en % y entrega la fracción (`"10"` → `Decimal("0.1")`; muestra `Decimal("0.25")` como `25.00`).
  - `apps.planeacion.formularios.FormularioMeta`.
  - Helpers en `apps.planeacion.vistas`: `_editar(request, Formulario, instancia, destino, titulo)`, `_eliminar(request, modelo, pk, destino)`, `_mes_actual(hogar) -> ResumenPresupuesto`. Las Tasks 6 y 7 los reutilizan.
  - Rutas (app `planeacion`, prefijo `/planeacion/`): `planeacion:metas`, `planeacion:meta_nueva`, `planeacion:meta_editar` (`metas/<pk>/`), `planeacion:meta_eliminar` (POST).
  - Sección "Planeación" en `templates/catalogos/indice.html` con el marcador `<!-- planeación: Tasks 5, 6, 7 -->`.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `tests/core/test_core_formularios.py`, agregar a los imports:
```python
from decimal import Decimal as D

from django.core.exceptions import ValidationError

from apps.core.formularios import CampoPorcentaje
```
y al final:
```python
def test_campo_porcentaje_entrega_la_fraccion():
    campo = CampoPorcentaje(required=False)

    assert campo.clean("10") == D("0.1")
    assert campo.clean("1.5") == D("0.015")
    assert campo.clean("") is None
    assert campo.prepare_value(D("0.2500")) == D("25.00")
    assert campo.prepare_value("abc") == "abc"


def test_campo_porcentaje_valida_en_porcentaje():
    with pytest.raises(ValidationError):
        CampoPorcentaje().clean("150")
    with pytest.raises(ValidationError):
        CampoPorcentaje().clean("-1")
    assert CampoPorcentaje(maximo=D("1000")).clean("150") == D("1.5")
```

`tests/planeacion/test_plan_vistas_metas.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Cuenta
from apps.planeacion.models import MetaAhorro

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def datos_meta(**campos):
    datos = {
        "tipo": "regalo",
        "nombre": "Regalo",
        "monto_objetivo": "20000",
        "ahorro_actual": "0",
        "meses": "12",
        "tasa_anual": "10",
        "fecha_inicio": "2026-10-01",
        "activa": "on",
    }
    datos.update(campos)
    return datos


def crear_meta(hogar, nombre="Regalo", monto="20000"):
    return MetaAhorro.objects.create(
        hogar=hogar, nombre=nombre, monto_objetivo=D(monto), fecha_inicio=date(2026, 10, 1)
    )


def test_pantalla_de_metas_con_los_valores_del_excel(cliente, plantilla_excel, hogar):
    crear_meta(hogar)
    crear_meta(hogar, "Vacaciones", "45000")

    contenido = cliente.get("/planeacion/metas/").content.decode()

    for texto in ("$1,591.65", "$3,581.21", "$5,172.87", "15.69%", "⚠️ Parece que lo disponible"):
        assert texto in contenido


def test_pantalla_sin_metas(cliente):
    assert "Aún no tienes metas de ahorro" in cliente.get("/planeacion/metas/").content.decode()


def test_crear_meta(cliente, hogar):
    respuesta = cliente.post("/planeacion/metas/nueva/", datos_meta(), headers=HTMX)

    assert respuesta.status_code == 204
    meta = MetaAhorro.objects.get()
    assert (meta.hogar, meta.tasa_anual, meta.meses) == (hogar, D("0.10"), 12)


def test_editar_muestra_la_tasa_en_porcentaje(cliente, hogar):
    meta = crear_meta(hogar)

    respuesta = cliente.get(f"/planeacion/metas/{meta.pk}/", headers=HTMX)

    assert 'value="10.00"' in respuesta.content.decode()


def test_meses_cero_es_error(cliente, hogar):
    respuesta = cliente.post("/planeacion/metas/nueva/", datos_meta(meses="0"), headers=HTMX)

    assert respuesta.status_code == 200
    assert "meses" in respuesta.context["formulario"].errors
    assert not MetaAhorro.objects.exists()


def test_cuenta_de_otro_hogar_es_error(cliente, otro_hogar):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.AHORRO)

    respuesta = cliente.post(
        "/planeacion/metas/nueva/", datos_meta(cuenta=ajena.pk), headers=HTMX
    )

    assert "cuenta" in respuesta.context["formulario"].errors


def test_eliminar_meta(cliente, hogar):
    meta = crear_meta(hogar)

    respuesta = cliente.post(f"/planeacion/metas/{meta.pk}/eliminar/", headers=HTMX)

    assert respuesta.status_code == 204
    assert not MetaAhorro.objects.exists()


def test_meta_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = crear_meta(otro_hogar)

    assert cliente.get(f"/planeacion/metas/{ajena.pk}/").status_code == 404
    assert cliente.post(f"/planeacion/metas/{ajena.pk}/eliminar/").status_code == 404
    assert MetaAhorro.objects.filter(pk=ajena.pk).exists()


def test_mas_enlaza_a_las_metas(cliente):
    assert "/planeacion/metas/" in cliente.get("/catalogos/").content.decode()
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/core/test_core_formularios.py tests/planeacion/test_plan_vistas_metas.py -v`
Expected: ERROR con `ImportError: cannot import name 'CampoPorcentaje'`; las vistas dan 404.

- [ ] **Step 3: `CampoPorcentaje`**

En `apps/core/formularios.py`, agregar a los imports:
```python
from decimal import Decimal

from apps.calculos.comun import redondear
```
y al final:
```python
class CampoPorcentaje(forms.DecimalField):
    """Se captura y muestra en % (10 = 10 %); entrega la fracción (0.10)."""

    def __init__(self, *, maximo=Decimal("100"), **kwargs):
        kwargs.setdefault("decimal_places", 2)
        super().__init__(min_value=Decimal("0"), max_value=maximo, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, Decimal):
            return redondear(value * 100)
        return value

    def clean(self, value):
        porcentaje = super().clean(value)
        return None if porcentaje is None else porcentaje / 100
```

- [ ] **Step 4: Formulario, vistas, URLs y plantilla**

`apps/planeacion/formularios.py`:
```python
from django import forms

from apps.core.formularios import CampoPorcentaje, FormularioDeHogar
from apps.planeacion.models import MetaAhorro

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class FormularioMeta(FormularioDeHogar):
    tasa_anual = CampoPorcentaje(
        label="Tasa de interés anual (%)", help_text="¿A qué tasa sueles invertir? 10 = 10 %."
    )

    class Meta:
        model = MetaAhorro
        fields = [
            "tipo", "nombre", "monto_objetivo", "ahorro_actual", "meses", "tasa_anual",
            "fecha_inicio", "cuenta", "activa",
        ]  # fmt: skip
        widgets = {"fecha_inicio": FECHA}
```

`apps/planeacion/vistas.py`:
```python
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.planeacion.formularios import FormularioMeta
from apps.planeacion.models import MetaAhorro
from apps.planeacion.servicios import resumir_metas
from apps.presupuesto.servicios import obtener_presupuesto_mes, resumen_mes


def _mes_actual(hogar):
    hoy = timezone.localdate()
    return resumen_mes(obtener_presupuesto_mes(hogar, hoy.year, hoy.month))


def _editar(request, Formulario, instancia, destino, titulo):
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, instance=instancia, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        formulario.save()
        return datos_actualizados() if es_htmx(request) else redirect(destino)
    contexto = {"formulario": formulario, "titulo": titulo, "accion": request.path}
    return responder_formulario(request, contexto)


def _eliminar(request, modelo, pk, destino):
    get_object_or_404(modelo.objects.del_hogar(request.hogar), pk=pk).delete()
    return datos_actualizados() if es_htmx(request) else redirect(destino)


@requiere_hogar
def metas(request):
    resumen = _mes_actual(request.hogar)
    contexto = {
        "metas": resumir_metas(request.hogar, resumen),
        "resumen": resumen,
        "pausadas": MetaAhorro.objects.del_hogar(request.hogar).filter(activa=False),
    }
    return render(request, "planeacion/metas.html", contexto)


@requiere_hogar
def meta_nueva(request):
    return _editar(request, FormularioMeta, None, "planeacion:metas", "Nueva meta de ahorro")


@requiere_hogar
def meta_editar(request, pk):
    meta = get_object_or_404(MetaAhorro.objects.del_hogar(request.hogar), pk=pk)
    return _editar(request, FormularioMeta, meta, "planeacion:metas", "Editar meta de ahorro")


@requiere_hogar
@require_POST
def meta_eliminar(request, pk):
    return _eliminar(request, MetaAhorro, pk, "planeacion:metas")
```

`apps/planeacion/urls.py`:
```python
from django.urls import path

from apps.planeacion import vistas

app_name = "planeacion"

urlpatterns = [
    path("metas/", vistas.metas, name="metas"),
    path("metas/nueva/", vistas.meta_nueva, name="meta_nueva"),
    path("metas/<int:pk>/", vistas.meta_editar, name="meta_editar"),
    path("metas/<int:pk>/eliminar/", vistas.meta_eliminar, name="meta_eliminar"),
]
```

En `finanzas/urls.py`, antes de `path("", include("apps.core.urls")),`:
```python
    path("planeacion/", include("apps.planeacion.urls")),
```

`templates/planeacion/metas.html`:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Metas de ahorro{% endblock %}
{% block contenido %}
<header class="mb-4 flex items-center justify-between gap-2">
  <h1 class="text-lg font-semibold"><a class="text-slate-400" href="{% url 'catalogos:indice' %}">Más ›</a> Metas de ahorro</h1>
  <button type="button" class="boton" hx-get="{% url 'planeacion:meta_nueva' %}" hx-target="#modal-contenido">+ Meta</button>
</header>

<section class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
  <div class="tarjeta"><p class="text-xs text-slate-500">Total de objetivos de ahorro al mes</p><p class="text-lg font-semibold">{{ metas.total_mensual|dinero }}</p></div>
  <div class="tarjeta"><p class="text-xs text-slate-500">% de tus ingresos</p><p class="text-lg font-semibold">{{ metas.porcentaje_ingresos|porcentaje }}</p></div>
  <div class="tarjeta"><p class="text-xs text-slate-500">Disponible al final del mes (presupuesto)</p><p class="text-lg font-semibold">{{ resumen.disponible|dinero }}</p></div>
</section>
<p class="mb-4 rounded-lg px-3 py-2 text-sm {% if metas.nivel == 'bien' %}bg-emerald-50 text-emerald-800{% elif metas.nivel == 'cuidado' %}bg-amber-50 text-amber-800{% else %}bg-red-50 text-red-700{% endif %}">{{ metas.mensaje }}</p>

<section class="grid gap-3 sm:grid-cols-2">
  {% for fila in metas.filas %}
    <article class="tarjeta">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="text-xs text-slate-500">{{ fila.meta.get_tipo_display }}</p>
          <h2 class="font-medium">{{ fila.meta.nombre }}</h2>
        </div>
        <div class="flex gap-3 text-xs">
          <button type="button" class="text-sky-700" hx-get="{% url 'planeacion:meta_editar' fila.meta.pk %}" hx-target="#modal-contenido">Editar</button>
          <button type="button" class="text-red-600" hx-post="{% url 'planeacion:meta_eliminar' fila.meta.pk %}" hx-confirm="¿Eliminar esta meta?">Eliminar</button>
        </div>
      </div>
      <p class="mt-2 text-2xl font-semibold text-emerald-700">{{ fila.aporte|dinero }} <span class="text-sm font-normal text-slate-500">al mes</span></p>
      <p class="text-xs text-slate-500">Meta {{ fila.meta.monto_objetivo|dinero }} · ahorro actual {{ fila.meta.ahorro_actual|dinero }} · {{ fila.meta.meses }} meses al {{ fila.meta.tasa_anual|porcentaje }} · termina en {{ fila.fecha_fin|date:"F Y" }}{% if fila.meta.cuenta %} · en {{ fila.meta.cuenta }}{% endif %}</p>
    </article>
  {% empty %}
    <p class="tarjeta text-slate-500 sm:col-span-2">Aún no tienes metas de ahorro. Agrega la primera con «+ Meta».</p>
  {% endfor %}
</section>

{% if pausadas %}
  <section class="tarjeta mt-4">
    <h2 class="mb-2 text-sm font-medium text-slate-500">Metas pausadas</h2>
    <ul class="divide-y divide-slate-100 text-sm">
      {% for meta in pausadas %}
        <li class="flex justify-between py-1"><span>{{ meta }}</span><button type="button" class="text-xs text-sky-700" hx-get="{% url 'planeacion:meta_editar' meta.pk %}" hx-target="#modal-contenido">Editar</button></li>
      {% endfor %}
    </ul>
  </section>
{% endif %}
{% endblock %}
```

En `templates/catalogos/indice.html`, entre la sección "Catálogos" y la última sección, agregar:
```html
<section class="tarjeta mb-4">
  <h2 class="mb-2 font-medium">Planeación</h2>
  <ul class="divide-y divide-slate-100">
    <li><a class="block py-2 text-sky-700" href="{% url 'planeacion:metas' %}">🎯 Metas de ahorro</a></li>
    <!-- planeación: Tasks 5, 6, 7 -->
  </ul>
</section>
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_core_formularios.py` 8 passed, `test_plan_vistas_metas.py` 9 passed; todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps finanzas/urls.py templates tests/core/test_core_formularios.py tests/planeacion/test_plan_vistas_metas.py
git commit -m "feat(planeacion): pantalla de metas de ahorro con aporte mensual y % de ingresos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Pantalla de deudas (P7) y "Registrar pago" (DEU-05)

**Files:**
- Modify: `apps/planeacion/vistas.py`, `apps/planeacion/urls.py`, `apps/movimientos/vistas.py`, `templates/catalogos/indice.html`
- Create: `templates/planeacion/deudas.html`
- Test: `tests/planeacion/test_plan_vistas_deudas.py`

**Interfaces:**
- Consumes: `vista_deudas`, `VistaDeudas` (Task 3); `movimientos:capturar` (plan 2).
- Produces: ruta `planeacion:deudas` (`/planeacion/deudas/`); `GET /movimientos/capturar/pago_deuda/?cuenta_destino=<pk>` abre la captura con esa cuenta elegida si es una tarjeta o préstamo del hogar (si no, la ignora).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/planeacion/test_plan_vistas_deudas.py`:
```python
import pytest

from apps.catalogos.models import Cuenta

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}
CAPTURA = "/movimientos/capturar/pago_deuda/"


def test_pantalla_de_deudas(cliente, catalogo):
    contenido = cliente.get("/planeacion/deudas/").content.decode()

    for texto in ("Tarjeta Oro", "96.32%", "⚠️ Cuidado, estás perdiendo dinero", "Préstamo auto",
                  "5.96%", "$45,518.73", "Registrar pago"):  # fmt: skip
        assert texto in contenido
    assert f"cuenta_destino={catalogo.tarjeta.pk}" in contenido


def test_pantalla_sin_deudas(cliente):
    contenido = cliente.get("/planeacion/deudas/").content.decode()

    assert "No tienes tarjetas de crédito registradas." in contenido
    assert "No tienes créditos registrados." in contenido


def test_registrar_pago_precarga_la_tarjeta(cliente, catalogo):
    respuesta = cliente.get(CAPTURA, {"cuenta_destino": catalogo.tarjeta.pk}, headers=HTMX)

    assert respuesta.context["formulario"]["cuenta_destino"].value() == catalogo.tarjeta.pk


def test_cuenta_destino_ajena_o_invalida_se_ignora(cliente, catalogo, otro_hogar):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.CREDITO)

    for valor in (ajena.pk, catalogo.efectivo.pk, "abc"):
        respuesta = cliente.get(CAPTURA, {"cuenta_destino": valor}, headers=HTMX)
        assert respuesta.context["formulario"]["cuenta_destino"].value() is None


def test_mas_enlaza_a_deudas(cliente):
    assert "/planeacion/deudas/" in cliente.get("/catalogos/").content.decode()
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/planeacion/test_plan_vistas_deudas.py -v`
Expected: FAIL (404 en `/planeacion/deudas/`; la cuenta no viene precargada).

- [ ] **Step 3: Implementar**

En `apps/movimientos/vistas.py`, en `capturar`, después de `formulario = Formulario(datos, hogar=request.hogar)`:
```python
    if datos is None:
        _precargar_destino(formulario, request.GET.get("cuenta_destino", ""))
```
y agregar al final del archivo:
```python
def _precargar_destino(formulario, valor):
    """RF-DEU-05: abrir el pago de deuda con la tarjeta o préstamo ya elegido."""
    campo = formulario.fields.get("cuenta_destino")
    if campo is not None and valor.isdigit() and campo.queryset.filter(pk=valor).exists():
        formulario.initial["cuenta_destino"] = int(valor)
```

En `apps/planeacion/vistas.py`, agregar `vista_deudas` al import de `apps.planeacion.servicios` y al final:
```python
@requiere_hogar
def deudas(request):
    hoy = timezone.localdate()
    vista = vista_deudas(request.hogar, hoy.year, hoy.month)
    contexto = {
        "deudas": vista,
        "total_deudas": vista.resumen.total_tarjetas + vista.resumen.total_creditos,
    }
    return render(request, "planeacion/deudas.html", contexto)
```

En `apps/planeacion/urls.py`, agregar a `urlpatterns`:
```python
    path("deudas/", vistas.deudas, name="deudas"),
```

`templates/planeacion/deudas.html`:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Deudas{% endblock %}
{% block contenido %}
<header class="mb-4 flex items-center justify-between gap-2">
  <h1 class="text-lg font-semibold"><a class="text-slate-400" href="{% url 'catalogos:indice' %}">Más ›</a> Deudas</h1>
  <a class="boton-secundario text-sm" href="{% url 'catalogos:lista' 'cuentas' %}">Editar cuentas</a>
</header>

<section class="tarjeta mb-4">
  <h2 class="mb-2 font-medium">💳 Tarjetas de crédito</h2>
  {% for fila in deudas.tarjetas %}
    <article class="border-t border-slate-100 py-3 first:border-t-0">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="font-medium">{{ fila.cuenta }}</p>
          <p class="text-xs text-slate-500">{{ fila.cuenta.institucion|default:"—" }} · {{ fila.cuenta.producto|default:"—" }} · tasa {{ fila.tasa|porcentaje }}{% if fila.tasa_de_mercado %}*{% endif %}</p>
        </div>
        <button type="button" class="boton-secundario text-xs" hx-get="{% url 'movimientos:capturar' 'pago_deuda' %}?cuenta_destino={{ fila.cuenta.pk }}" hx-target="#modal-contenido">Registrar pago</button>
      </div>
      <p class="mt-1 text-sm">Saldo {{ fila.cuenta.saldo_actual|dinero }} de {{ fila.cuenta.linea_credito|dinero }} · uso <span class="font-semibold {% if fila.nivel == 'riesgo' %}text-red-600{% elif fila.nivel == 'cuidado' %}text-amber-600{% else %}text-emerald-700{% endif %}">{{ fila.uso|porcentaje }}</span></p>
      {% if fila.mensaje %}<p class="text-xs text-slate-600">{{ fila.mensaje }}</p>{% endif %}
    </article>
  {% empty %}
    <p class="text-sm text-slate-500">No tienes tarjetas de crédito registradas.</p>
  {% endfor %}
  {% if deudas.tarjetas %}
    <dl class="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-slate-200 pt-3 text-sm">
      <dt>Saldo total</dt><dd class="text-right">{{ deudas.resumen.total_tarjetas|dinero }}</dd>
      <dt>% de uso de tu línea de crédito</dt><dd class="text-right">{{ deudas.resumen.uso|porcentaje }}</dd>
      <dt>Gasto con tarjeta según tu presupuesto</dt><dd class="text-right">{{ deudas.gasto_tarjeta_presupuesto|dinero }}</dd>
      <dt>Gasto real con tarjeta este mes</dt><dd class="text-right">{{ deudas.gasto_tarjeta_real|dinero }}</dd>
    </dl>
    {% if deudas.mensaje_uso %}<p class="mt-2 text-sm">{{ deudas.mensaje_uso }}</p>{% endif %}
    <p class="mt-2 text-xs text-slate-500">* Tasa promedio del mercado para esa tarjeta; la tuya puede variar.</p>
  {% endif %}
</section>

<section class="tarjeta mb-4">
  <h2 class="mb-2 font-medium">🏦 Créditos</h2>
  {% for fila in deudas.creditos %}
    <article class="border-t border-slate-100 py-3 first:border-t-0">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="font-medium">{{ fila.cuenta }}</p>
          <p class="text-xs text-slate-500">Deuda inicial {{ fila.cuenta.monto_inicial|dinero }} · actual {{ fila.cuenta.saldo_actual|dinero }} · mensualidad {{ fila.cuenta.mensualidad|dinero }}</p>
        </div>
        <button type="button" class="boton-secundario text-xs" hx-get="{% url 'movimientos:capturar' 'pago_deuda' %}?cuenta_destino={{ fila.cuenta.pk }}" hx-target="#modal-contenido">Registrar pago</button>
      </div>
      <div class="mt-2 h-2 rounded-full bg-slate-100"><div class="h-2 rounded-full bg-emerald-500" style="width: {{ fila.completado|ancho_barra }}%"></div></div>
      <p class="text-xs text-slate-500">{{ fila.completado|porcentaje }} completado</p>
    </article>
  {% empty %}
    <p class="text-sm text-slate-500">No tienes créditos registrados.</p>
  {% endfor %}
  {% if deudas.creditos %}
    <dl class="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-slate-200 pt-3 text-sm">
      <dt>Deuda total en créditos</dt><dd class="text-right">{{ deudas.resumen.total_creditos|dinero }}</dd>
      <dt>Suma de mensualidades</dt><dd class="text-right">{{ deudas.resumen.mensualidades|dinero }}</dd>
    </dl>
  {% endif %}
</section>

<p class="tarjeta text-sm">Total de tus deudas: <strong>{{ total_deudas|dinero }}</strong></p>
{% endblock %}
```

En `templates/catalogos/indice.html`, antes de `<!-- planeación: Tasks 5, 6, 7 -->`:
```html
    <li><a class="block py-2 text-sky-700" href="{% url 'planeacion:deudas' %}">💳 Deudas</a></li>
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_plan_vistas_deudas.py` 5 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps templates tests/planeacion/test_plan_vistas_deudas.py
git commit -m "feat(planeacion): pantalla de deudas con uso por tarjeta, avance de creditos y registrar pago" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Pantalla de patrimonio (P8)

**Files:**
- Modify: `apps/planeacion/formularios.py`, `apps/planeacion/vistas.py`, `apps/planeacion/urls.py`, `templates/catalogos/indice.html`
- Create: `templates/planeacion/patrimonio.html`
- Test: `tests/planeacion/test_plan_vistas_patrimonio.py`

**Interfaces:**
- Consumes: `Activo` (Task 1); `calcular_patrimonio`, `Patrimonio` (Task 3); `_editar`, `_eliminar`, `FECHA` (Task 4).
- Produces: `FormularioActivo`; rutas `planeacion:patrimonio`, `planeacion:activo_nuevo`, `planeacion:activo_editar` (`patrimonio/<pk>/`), `planeacion:activo_eliminar` (POST).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/planeacion/test_plan_vistas_patrimonio.py`:
```python
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Domicilio
from apps.planeacion.models import Activo

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def datos_activo(**campos):
    datos = {
        "tipo": "auto",
        "nombre": "Auto familiar",
        "valor_actual": "150000",
        "fecha_valuacion": "2026-10-01",
        "activo": "on",
    }
    datos.update(campos)
    return datos


def test_patrimonio_neto_del_excel(cliente, catalogo, hogar):
    for nombre, valor in [("Casa", "2400000"), ("Auto", "150000"), ("Ahorro", "43519.94")]:
        Activo.objects.create(hogar=hogar, nombre=nombre, valor_actual=D(valor))

    contenido = cliente.get("/planeacion/patrimonio/").content.decode()

    for texto in ("$2,593,519.94", "$38,679.72", "$6,839.01", "$2,548,001.21"):
        assert texto in contenido


def test_pantalla_sin_activos(cliente):
    assert "Aún no registras activos" in cliente.get("/planeacion/patrimonio/").content.decode()


def test_crear_activo(cliente, hogar):
    respuesta = cliente.post("/planeacion/patrimonio/nuevo/", datos_activo(), headers=HTMX)

    assert respuesta.status_code == 204
    assert Activo.objects.get().hogar == hogar


def test_valor_negativo_es_error(cliente, hogar):
    respuesta = cliente.post(
        "/planeacion/patrimonio/nuevo/", datos_activo(valor_actual="-1"), headers=HTMX
    )

    assert "valor_actual" in respuesta.context["formulario"].errors


def test_domicilio_de_otro_hogar_es_error(cliente, otro_hogar):
    ajeno = Domicilio.objects.create(hogar=otro_hogar, alias="Ajeno")

    respuesta = cliente.post(
        "/planeacion/patrimonio/nuevo/", datos_activo(domicilio=ajeno.pk), headers=HTMX
    )

    assert "domicilio" in respuesta.context["formulario"].errors


def test_editar_y_eliminar_activo(cliente, hogar):
    activo = Activo.objects.create(hogar=hogar, nombre="Auto", valor_actual=D("1"))

    cliente.post(f"/planeacion/patrimonio/{activo.pk}/", datos_activo(), headers=HTMX)
    activo.refresh_from_db()
    assert activo.valor_actual == D("150000")

    assert cliente.post(f"/planeacion/patrimonio/{activo.pk}/eliminar/", headers=HTMX).status_code == 204
    assert not Activo.objects.exists()


def test_activo_de_otro_hogar_da_404(cliente, otro_hogar):
    ajeno = Activo.objects.create(hogar=otro_hogar, nombre="Ajeno", valor_actual=D("1"))

    assert cliente.get(f"/planeacion/patrimonio/{ajeno.pk}/").status_code == 404
    assert cliente.post(f"/planeacion/patrimonio/{ajeno.pk}/eliminar/").status_code == 404


def test_mas_enlaza_al_patrimonio(cliente):
    assert "/planeacion/patrimonio/" in cliente.get("/catalogos/").content.decode()
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/planeacion/test_plan_vistas_patrimonio.py -v`
Expected: FAIL con 404 en `/planeacion/patrimonio/`.

- [ ] **Step 3: Implementar**

En `apps/planeacion/formularios.py`, cambiar el import de modelos a `from apps.planeacion.models import Activo, MetaAhorro` y agregar al final:
```python
class FormularioActivo(FormularioDeHogar):
    class Meta:
        model = Activo
        fields = ["tipo", "nombre", "valor_actual", "fecha_valuacion", "domicilio", "cuenta", "activo"]
        widgets = {"fecha_valuacion": FECHA}
        labels = {"activo": "Vigente (cuenta en el patrimonio)"}
```

En `apps/planeacion/vistas.py`, cambiar los imports a:
```python
from apps.planeacion.formularios import FormularioActivo, FormularioMeta
from apps.planeacion.models import Activo, MetaAhorro
from apps.planeacion.servicios import calcular_patrimonio, resumir_metas, vista_deudas
```
y agregar al final:
```python
@requiere_hogar
def patrimonio(request):
    contexto = {
        "patrimonio": calcular_patrimonio(request.hogar),
        "no_vigentes": Activo.objects.del_hogar(request.hogar).filter(activo=False),
    }
    return render(request, "planeacion/patrimonio.html", contexto)


@requiere_hogar
def activo_nuevo(request):
    return _editar(request, FormularioActivo, None, "planeacion:patrimonio", "Nuevo activo")


@requiere_hogar
def activo_editar(request, pk):
    activo = get_object_or_404(Activo.objects.del_hogar(request.hogar), pk=pk)
    return _editar(request, FormularioActivo, activo, "planeacion:patrimonio", "Editar activo")


@requiere_hogar
@require_POST
def activo_eliminar(request, pk):
    return _eliminar(request, Activo, pk, "planeacion:patrimonio")
```

En `apps/planeacion/urls.py`, agregar a `urlpatterns`:
```python
    path("patrimonio/", vistas.patrimonio, name="patrimonio"),
    path("patrimonio/nuevo/", vistas.activo_nuevo, name="activo_nuevo"),
    path("patrimonio/<int:pk>/", vistas.activo_editar, name="activo_editar"),
    path("patrimonio/<int:pk>/eliminar/", vistas.activo_eliminar, name="activo_eliminar"),
```

`templates/planeacion/patrimonio.html`:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Patrimonio{% endblock %}
{% block contenido %}
<header class="mb-4 flex items-center justify-between gap-2">
  <h1 class="text-lg font-semibold"><a class="text-slate-400" href="{% url 'catalogos:indice' %}">Más ›</a> Patrimonio</h1>
  <button type="button" class="boton" hx-get="{% url 'planeacion:activo_nuevo' %}" hx-target="#modal-contenido">+ Activo</button>
</header>

<section class="tarjeta mb-4">
  <p class="text-xs text-slate-500">Valor de tu patrimonio total (net worth)</p>
  <p class="text-2xl font-semibold {% if patrimonio.neto < 0 %}text-red-600{% else %}text-emerald-700{% endif %}">{{ patrimonio.neto|dinero }}</p>
  <dl class="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
    <dt>Valor total de tus activos</dt><dd class="text-right">{{ patrimonio.total_activos|dinero }}</dd>
    <dt>Deuda en créditos</dt><dd class="text-right">-{{ patrimonio.deuda_creditos|dinero }}</dd>
    <dt>Deuda en tarjetas</dt><dd class="text-right">-{{ patrimonio.deuda_tarjetas|dinero }}</dd>
  </dl>
  <p class="mt-2 text-xs"><a class="text-sky-700" href="{% url 'planeacion:deudas' %}">Ver deudas</a></p>
</section>

<section class="space-y-2">
  {% for activo in patrimonio.activos %}
    <article class="tarjeta flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-xs text-slate-500">{{ activo.get_tipo_display }}</p>
        <p class="font-medium">{{ activo.nombre }}</p>
        <p class="text-xs text-slate-500">valuado el {{ activo.fecha_valuacion|date:"d M Y" }}{% if activo.domicilio %} · {{ activo.domicilio }}{% endif %}{% if activo.cuenta %} · {{ activo.cuenta }}{% endif %}</p>
      </div>
      <div class="shrink-0 text-right">
        <p class="font-semibold">{{ activo.valor_actual|dinero }}</p>
        <div class="mt-1 flex justify-end gap-3 text-xs">
          <button type="button" class="text-sky-700" hx-get="{% url 'planeacion:activo_editar' activo.pk %}" hx-target="#modal-contenido">Editar</button>
          <button type="button" class="text-red-600" hx-post="{% url 'planeacion:activo_eliminar' activo.pk %}" hx-confirm="¿Eliminar este activo?">Eliminar</button>
        </div>
      </div>
    </article>
  {% empty %}
    <p class="tarjeta text-slate-500">Aún no registras activos (casa, auto, ahorros, afore…). Agrega el primero con «+ Activo».</p>
  {% endfor %}
</section>

{% if no_vigentes %}
  <section class="tarjeta mt-4">
    <h2 class="mb-2 text-sm font-medium text-slate-500">No vigentes (no cuentan en el patrimonio)</h2>
    <ul class="divide-y divide-slate-100 text-sm">
      {% for activo in no_vigentes %}
        <li class="flex justify-between py-1"><span>{{ activo }}</span><button type="button" class="text-xs text-sky-700" hx-get="{% url 'planeacion:activo_editar' activo.pk %}" hx-target="#modal-contenido">Editar</button></li>
      {% endfor %}
    </ul>
  </section>
{% endif %}
{% endblock %}
```

En `templates/catalogos/indice.html`, antes de `<!-- planeación: Tasks 5, 6, 7 -->`:
```html
    <li><a class="block py-2 text-sky-700" href="{% url 'planeacion:patrimonio' %}">🏛️ Patrimonio</a></li>
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_plan_vistas_patrimonio.py` 8 passed; todo verde.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps templates tests/planeacion/test_plan_vistas_patrimonio.py
git commit -m "feat(planeacion): pantalla de patrimonio con activos y patrimonio neto" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Simulador de créditos (P9, SIM-01..03)

**Files:**
- Modify: `apps/planeacion/formularios.py`, `apps/planeacion/servicios.py`, `apps/planeacion/vistas.py`, `apps/planeacion/urls.py`, `templates/catalogos/indice.html`
- Create: `templates/planeacion/simulador.html`
- Test: `tests/planeacion/test_plan_simulador.py`

**Interfaces:**
- Consumes: `SimulacionCredito`, `MESES_MAXIMOS` (Task 1); `CampoPorcentaje` (Task 4); `amortizar` (`apps.calculos.credito`); `redondear`, `CERO`.
- Produces:
  - `apps.planeacion.formularios.FormularioSimulador` (campos `monto`, `tasa_anual` (%), `meses`, `comision_apertura` (%), `pagos_anticipados` (texto `mes=monto` por renglón → `dict[int, Decimal]`), `nombre`); tras `is_valid()` deja la tabla en `formulario.amortizacion`.
  - `apps.planeacion.servicios.guardar_simulacion(hogar, formulario) -> SimulacionCredito` y `datos_de_simulacion(simulacion) -> dict` (datos para volver a abrirla en el formulario).
  - Rutas `planeacion:simulador` (`/planeacion/simulador/`, GET con los datos en la URL o `?simulacion=<pk>`), `planeacion:simulacion_guardar` (POST), `planeacion:simulacion_eliminar` (`simulador/<pk>/eliminar/`, POST).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/planeacion/test_plan_simulador.py`:
```python
from decimal import Decimal as D

import pytest

from apps.planeacion.models import SimulacionCredito

pytestmark = pytest.mark.django_db
URL = "/planeacion/simulador/"
EXCEL = {"monto": "30000", "tasa_anual": "25", "meses": "12", "comision_apertura": "1.5"}


def test_simulador_reproduce_el_excel(cliente):
    respuesta = cliente.get(URL, EXCEL)

    contenido = respuesta.content.decode()
    for texto in ("$30,450.00", "1.88%", "$2,857.62", "$3,841.45"):
        assert texto in contenido
    assert len(respuesta.context["amortizacion"].filas) == 12


def test_simulador_sin_datos(cliente):
    respuesta = cliente.get(URL)

    assert respuesta.status_code == 200
    assert respuesta.context["amortizacion"] is None


def test_pagos_anticipados(cliente):
    respuesta = cliente.get(URL, {**EXCEL, "pagos_anticipados": "3=5000\n6: 1,000"})

    filas = respuesta.context["amortizacion"].filas
    assert (filas[2].pago_anticipado, filas[5].pago_anticipado) == (D("5000"), D("1000"))


@pytest.mark.parametrize(
    ("campos", "campo", "texto"),
    [
        ({"pagos_anticipados": "tres mil"}, "pagos_anticipados", "No entiendo"),
        ({"pagos_anticipados": "13=100"}, "__all__", "fuera del plazo"),
        ({"meses": "10000"}, "meses", ""),
        ({"monto": "0"}, "monto", ""),
        ({"tasa_anual": "abc"}, "tasa_anual", ""),
    ],
)
def test_datos_invalidos_muestran_error(cliente, campos, campo, texto):
    respuesta = cliente.get(URL, {**EXCEL, **campos})

    errores = respuesta.context["formulario"].errors
    assert respuesta.status_code == 200
    assert respuesta.context["amortizacion"] is None
    assert campo in errores
    assert texto in str(errores[campo])


def test_guardar_y_abrir_una_simulacion(cliente, hogar):
    respuesta = cliente.post(URL + "guardar/", {**EXCEL, "nombre": "Préstamo personal"})

    simulacion = SimulacionCredito.objects.get()
    assert simulacion.hogar == hogar
    assert (simulacion.tasa_anual, simulacion.comision_apertura) == (D("0.25"), D("0.015"))
    assert respuesta.url == f"{URL}?simulacion={simulacion.pk}"
    contenido = cliente.get(respuesta.url).content.decode()
    assert "$2,857.62" in contenido
    assert "Préstamo personal" in contenido


def test_guardar_con_pagos_anticipados(cliente):
    respuesta = cliente.post(
        URL + "guardar/", {**EXCEL, "nombre": "Con abono", "pagos_anticipados": "3=5000"}
    )

    simulacion = SimulacionCredito.objects.get()
    assert simulacion.pagos_anticipados == {"3": "5000"}
    filas = cliente.get(respuesta.url).context["amortizacion"].filas
    assert filas[2].pago_anticipado == D("5000")


def test_guardar_sin_nombre_no_guarda(cliente):
    respuesta = cliente.post(URL + "guardar/", EXCEL)

    assert respuesta.status_code == 302
    assert not SimulacionCredito.objects.exists()


def test_simulacion_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = SimulacionCredito.objects.create(
        hogar=otro_hogar, nombre="Ajena", monto=D("1000"), tasa_anual=D("0.1"), meses=12
    )

    assert cliente.get(URL, {"simulacion": ajena.pk}).status_code == 404
    assert cliente.post(f"{URL}{ajena.pk}/eliminar/").status_code == 404
    assert SimulacionCredito.objects.filter(pk=ajena.pk).exists()


def test_eliminar_simulacion(cliente, hogar):
    simulacion = SimulacionCredito.objects.create(
        hogar=hogar, nombre="Vieja", monto=D("1000"), tasa_anual=D("0.1"), meses=12
    )

    assert cliente.post(f"{URL}{simulacion.pk}/eliminar/").status_code == 302
    assert not SimulacionCredito.objects.exists()


def test_mas_enlaza_al_simulador(cliente):
    assert URL in cliente.get("/catalogos/").content.decode()
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/planeacion/test_plan_simulador.py -v`
Expected: FAIL con 404 en `/planeacion/simulador/`.

- [ ] **Step 3: Formulario del simulador**

En `apps/planeacion/formularios.py`, reemplazar los imports y la constante `FECHA` (todo lo que está antes de `class FormularioMeta`) por:
```python
import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.calculos.comun import CERO
from apps.calculos.credito import amortizar
from apps.core.formularios import CampoPorcentaje, FormularioDeHogar
from apps.planeacion.models import MESES_MAXIMOS, Activo, MetaAhorro

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
PAGO_ANTICIPADO = re.compile(r"^\s*(\d+)\s*[=:]\s*(\d[\d,]*(?:\.\d+)?)\s*$")
```
y agregar al final:
```python
class FormularioSimulador(forms.Form):
    """RF-SIM-01: datos del crédito. Tras is_valid() deja la tabla en `amortizacion`."""

    monto = forms.DecimalField(
        label="Crédito total", min_value=Decimal("0.01"), max_digits=12, decimal_places=2
    )
    tasa_anual = CampoPorcentaje(label="Tasa de interés anual (%)", maximo=Decimal("1000"))
    meses = forms.IntegerField(label="Duración en meses", min_value=1, max_value=MESES_MAXIMOS)
    comision_apertura = CampoPorcentaje(
        label="Comisión por apertura (%)", required=False, initial=Decimal("0")
    )
    pagos_anticipados = forms.CharField(
        label="Pagos anticipados",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "3=5000"}),
        help_text="Uno por renglón: mes=monto (ej. 3=5000).",
    )
    nombre = forms.CharField(label="Nombre de la simulación", max_length=80, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.amortizacion = None

    def clean_pagos_anticipados(self):
        pagos = {}
        for renglon in re.split(r"[\n;]+", self.cleaned_data["pagos_anticipados"]):
            if not renglon.strip():
                continue
            coincide = PAGO_ANTICIPADO.match(renglon)
            if not coincide:
                raise ValidationError(
                    f"No entiendo «{renglon.strip()}». Escribe mes=monto, por ejemplo 3=5000."
                )
            mes, monto = int(coincide[1]), Decimal(coincide[2].replace(",", ""))
            pagos[mes] = pagos.get(mes, CERO) + monto
        return pagos

    def clean(self):
        datos = super().clean()
        if not self.errors:
            try:
                self.amortizacion = amortizar(**self.argumentos())
            except ValueError as error:
                raise ValidationError(str(error)) from error
        return datos

    def argumentos(self):
        datos = self.cleaned_data
        return {
            "monto": datos["monto"],
            "tasa_anual": datos["tasa_anual"],
            "meses": datos["meses"],
            "comision_apertura": datos["comision_apertura"] or CERO,
            "pagos_anticipados": datos["pagos_anticipados"],
        }
```

- [ ] **Step 4: Servicios, vistas, URLs y plantilla**

En `apps/planeacion/servicios.py`, agregar `from apps.calculos.comun import CERO, redondear` (en lugar de importar solo `CERO`), agregar `SimulacionCredito` al import de `apps.planeacion.models` y al final:
```python
def guardar_simulacion(hogar, formulario):
    """RF-SIM-03: guarda los datos de un FormularioSimulador válido."""
    datos = formulario.cleaned_data
    simulacion = SimulacionCredito(
        hogar=hogar,
        nombre=datos["nombre"],
        monto=datos["monto"],
        tasa_anual=datos["tasa_anual"],
        meses=datos["meses"],
        comision_apertura=datos["comision_apertura"] or CERO,
        pagos_anticipados={str(mes): str(monto) for mes, monto in datos["pagos_anticipados"].items()},
    )
    simulacion.full_clean()
    simulacion.save()
    return simulacion


def datos_de_simulacion(simulacion):
    """Datos para volver a abrir una simulación guardada en el formulario."""
    return {
        "nombre": simulacion.nombre,
        "monto": str(simulacion.monto),
        "tasa_anual": str(redondear(simulacion.tasa_anual * 100)),
        "meses": str(simulacion.meses),
        "comision_apertura": str(redondear(simulacion.comision_apertura * 100)),
        "pagos_anticipados": "\n".join(
            f"{mes}={monto}" for mes, monto in sorted(simulacion.anticipados().items())
        ),
    }
```

En `apps/planeacion/vistas.py`, cambiar los imports a:
```python
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.planeacion.formularios import FormularioActivo, FormularioMeta, FormularioSimulador
from apps.planeacion.models import Activo, MetaAhorro, SimulacionCredito
from apps.planeacion.servicios import (
    calcular_patrimonio,
    datos_de_simulacion,
    guardar_simulacion,
    resumir_metas,
    vista_deudas,
)
from apps.presupuesto.servicios import obtener_presupuesto_mes, resumen_mes
```
y agregar al final:
```python
@requiere_hogar
def simulador(request):
    simulacion = None
    valor = request.GET.get("simulacion", "")
    if valor.isdigit():
        simulacion = get_object_or_404(
            SimulacionCredito.objects.del_hogar(request.hogar), pk=valor
        )
        formulario = FormularioSimulador(datos_de_simulacion(simulacion))
    else:
        formulario = FormularioSimulador(request.GET or None)
    valido = formulario.is_bound and formulario.is_valid()
    contexto = {
        "formulario": formulario,
        "amortizacion": formulario.amortizacion if valido else None,
        "simulacion": simulacion,
        "guardadas": SimulacionCredito.objects.del_hogar(request.hogar),
    }
    return render(request, "planeacion/simulador.html", contexto)


@requiere_hogar
@require_POST
def simulacion_guardar(request):
    formulario = FormularioSimulador(request.POST)
    if formulario.is_valid() and formulario.cleaned_data["nombre"]:
        simulacion = guardar_simulacion(request.hogar, formulario)
        messages.success(request, f"Se guardó la simulación «{simulacion}».")
        return redirect(f"{reverse('planeacion:simulador')}?simulacion={simulacion.pk}")
    messages.error(request, "Para guardar la simulación escribe un nombre y revisa los datos.")
    consulta = request.POST.copy()
    consulta.pop("csrfmiddlewaretoken", None)
    return redirect(f"{reverse('planeacion:simulador')}?{consulta.urlencode()}")


@requiere_hogar
@require_POST
def simulacion_eliminar(request, pk):
    get_object_or_404(SimulacionCredito.objects.del_hogar(request.hogar), pk=pk).delete()
    messages.success(request, "Se eliminó la simulación.")
    return redirect("planeacion:simulador")
```

En `apps/planeacion/urls.py`, agregar a `urlpatterns`:
```python
    path("simulador/", vistas.simulador, name="simulador"),
    path("simulador/guardar/", vistas.simulacion_guardar, name="simulacion_guardar"),
    path("simulador/<int:pk>/eliminar/", vistas.simulacion_eliminar, name="simulacion_eliminar"),
```

`templates/planeacion/simulador.html`:
```html
{% extends "base.html" %}
{% load formato %}
{% block titulo %}Simulador de créditos{% endblock %}
{% block contenido %}
<h1 class="mb-1 text-lg font-semibold"><a class="text-slate-400" href="{% url 'catalogos:indice' %}">Más ›</a> Simulador de créditos</h1>
<p class="mb-4 text-sm text-slate-600">¿Quieres saber si un crédito te conviene? Pruébalo antes de tomar una decisión.</p>

<form method="get" action="{% url 'planeacion:simulador' %}" class="tarjeta mb-4 grid gap-3 sm:grid-cols-2">
  {% if formulario.non_field_errors %}<div class="rounded bg-red-50 p-2 text-sm text-red-700 sm:col-span-2">{{ formulario.non_field_errors }}</div>{% endif %}
  {% for campo in formulario %}
    {% if campo.name != "nombre" %}
      <div {% if campo.name == "pagos_anticipados" %}class="sm:col-span-2"{% endif %}>{% include "componentes/campo.html" %}</div>
    {% endif %}
  {% endfor %}
  <div class="sm:col-span-2"><button class="boton">Calcular</button></div>
</form>

{% if amortizacion %}
  <section class="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
    <div class="tarjeta"><p class="text-xs text-slate-500">Crédito con comisión</p><p class="font-semibold">{{ amortizacion.capital_inicial|dinero }}</p></div>
    <div class="tarjeta"><p class="text-xs text-slate-500">Tasa efectiva mensual</p><p class="font-semibold">{{ amortizacion.tasa_mensual|porcentaje }}</p></div>
    <div class="tarjeta"><p class="text-xs text-slate-500">Mensualidad a pagar</p><p class="font-semibold">{{ amortizacion.mensualidad|dinero }}</p></div>
    <div class="tarjeta"><p class="text-xs text-slate-500">Total de intereses</p><p class="font-semibold text-red-600">{{ amortizacion.total_intereses|dinero }}</p></div>
  </section>

  <form method="post" action="{% url 'planeacion:simulacion_guardar' %}" class="tarjeta mb-4 flex flex-wrap items-end gap-3">
    {% csrf_token %}
    {% for campo in formulario %}
      {% if campo.name == "pagos_anticipados" %}
        <textarea name="pagos_anticipados" hidden>{{ campo.value|default_if_none:"" }}</textarea>
      {% elif campo.name != "nombre" %}
        <input type="hidden" name="{{ campo.name }}" value="{{ campo.value|default_if_none:'' }}">
      {% endif %}
    {% endfor %}
    <div class="min-w-48 grow">{% include "componentes/campo.html" with campo=formulario.nombre %}</div>
    <button class="boton-secundario">Guardar simulación</button>
  </form>

  <section class="tarjeta overflow-x-auto">
    <table class="w-full min-w-[640px] text-right text-sm">
      <thead class="text-xs text-slate-500">
        <tr><th class="text-left">Mes</th><th>Mensualidad</th><th>Intereses</th><th>Capital</th><th>Saldo final</th><th>Capital acumulado</th><th>Pago anticipado</th></tr>
      </thead>
      <tbody>
        {% for fila in amortizacion.filas %}
          <tr class="border-t border-slate-100">
            <td class="text-left">{{ fila.mes }}</td>
            <td>{{ fila.mensualidad|dinero }}</td>
            <td>{{ fila.intereses|dinero }}</td>
            <td>{{ fila.capital|dinero }}</td>
            <td>{{ fila.saldo_final|dinero }}</td>
            <td>{{ fila.capital_acumulado|dinero }}</td>
            <td>{% if fila.pago_anticipado %}{{ fila.pago_anticipado|dinero }}{% endif %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </section>
{% endif %}

<section class="tarjeta mt-4">
  <h2 class="mb-2 font-medium">Simulaciones guardadas</h2>
  <ul class="divide-y divide-slate-100 text-sm">
    {% for guardada in guardadas %}
      <li class="flex items-center justify-between py-2">
        <a class="text-sky-700 {% if guardada == simulacion %}font-semibold{% endif %}" href="{% url 'planeacion:simulador' %}?simulacion={{ guardada.pk }}">{{ guardada.nombre }}</a>
        <form method="post" action="{% url 'planeacion:simulacion_eliminar' guardada.pk %}" onsubmit="return confirm('¿Eliminar esta simulación?')">{% csrf_token %}<button class="text-xs text-red-600">Eliminar</button></form>
      </li>
    {% empty %}
      <li class="py-2 text-slate-500">Aún no guardas simulaciones.</li>
    {% endfor %}
  </ul>
</section>
{% endblock %}
```

En `templates/catalogos/indice.html`, antes de `<!-- planeación: Tasks 5, 6, 7 -->`:
```html
    <li><a class="block py-2 text-sky-700" href="{% url 'planeacion:simulador' %}">🧾 Simulador de créditos</a></li>
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_plan_simulador.py` 14 passed; todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps templates tests/planeacion/test_plan_simulador.py
git commit -m "feat(planeacion): simulador de creditos con pagos anticipados y simulaciones guardadas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Metas y patrimonio en el tablero (TAB-05) y alerta de metas (MET-03)

**Files:**
- Modify: `apps/tablero/servicios.py`, `templates/tablero/mes.html`
- Test: `tests/tablero/test_tablero_planeacion.py`

**Interfaces:**
- Consumes: `resumir_metas`, `ResumenMetas`, `calcular_patrimonio`, `Patrimonio` (Tasks 2–3); `armar_tablero`, `Tablero`, `Alerta`, `_alertas` (plan 2).
- Produces: `Tablero.metas: ResumenMetas | None` (`None` con filtro de persona o domicilio) y `Tablero.patrimonio: Patrimonio`; alerta "Tus metas de ahorro piden … al mes y el disponible de tu presupuesto es …" cuando el total de metas activas supera el disponible del presupuesto (sin filtro).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/tablero/test_tablero_planeacion.py`:
```python
from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.planeacion.models import Activo, MetaAhorro
from apps.tablero.servicios import armar_tablero

pytestmark = pytest.mark.django_db


def metas_del_excel(hogar):
    for nombre, monto in [("Regalo", "20000"), ("Vacaciones", "45000")]:
        MetaAhorro.objects.create(
            hogar=hogar, nombre=nombre, monto_objetivo=D(monto), fecha_inicio=date(2026, 10, 1)
        )


def mensajes(tablero):
    return " | ".join(alerta.mensaje for alerta in tablero.alertas)


def test_tablero_incluye_metas_y_alerta_si_no_alcanzan(plantilla_excel, hogar):
    metas_del_excel(hogar)

    t = armar_tablero(hogar, 2026, 10)

    assert redondear(t.metas.total_mensual) == D("5172.87")
    assert "Tus metas de ahorro piden $5,172.87 al mes" in mensajes(t)
    assert "$3,742.52" in mensajes(t)


def test_sin_metas_no_hay_alerta(plantilla_excel, hogar):
    t = armar_tablero(hogar, 2026, 10)

    assert t.metas.filas == []
    assert "metas de ahorro piden" not in mensajes(t)


def test_con_filtro_no_se_muestran_metas(plantilla_excel, catalogo, hogar):
    metas_del_excel(hogar)

    t = armar_tablero(hogar, 2026, 10, domicilio=catalogo.fidel)

    assert t.metas is None
    assert "metas de ahorro piden" not in mensajes(t)


def test_tablero_incluye_patrimonio(catalogo, hogar):
    Activo.objects.create(hogar=hogar, nombre="Auto", valor_actual=D("100000"))

    assert armar_tablero(hogar, 2026, 10).patrimonio.neto == D("54481.27")


def test_pantalla_del_tablero_con_metas_y_patrimonio(cliente, plantilla_excel, hogar):
    metas_del_excel(hogar)

    contenido = cliente.get("/tablero/2026/10/").content.decode()

    assert "Necesitas ahorrar" in contenido
    assert "$5,172.87" in contenido
    assert "Patrimonio neto" in contenido


def test_pantalla_del_tablero_sin_metas(cliente):
    contenido = cliente.get("/tablero/2026/10/").content.decode()

    assert "Aún no tienes metas de ahorro." in contenido
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/tablero/test_tablero_planeacion.py -v`
Expected: FAIL con `AttributeError: 'Tablero' object has no attribute 'metas'`.

- [ ] **Step 3: Servicio del tablero**

En `apps/tablero/servicios.py`:

1. Agregar a los imports:
```python
from apps.planeacion.servicios import (
    Patrimonio,
    ResumenMetas,
    calcular_patrimonio,
    resumir_metas,
)
```
2. En `Tablero`, después de `alertas: list`, agregar:
```python
    metas: ResumenMetas | None
    patrimonio: Patrimonio
```
3. En `armar_tablero`, después de `deudas = resumir_deudas(hogar)`:
```python
    metas = None if filtrado else resumir_metas(hogar, resumen)
```
reemplazar `alertas=_alertas(resumen, reales, deudas, filtrado),` por:
```python
        alertas=_alertas(resumen, reales, deudas, filtrado, metas),
        metas=metas,
        patrimonio=calcular_patrimonio(hogar),
```
4. Cambiar la firma `def _alertas(resumen, reales, deudas, filtrado):` por `def _alertas(resumen, reales, deudas, filtrado, metas=None):` y, justo antes del `return alertas` final, agregar:
```python
    if metas is not None and metas.filas and metas.total_mensual > resumen.disponible:
        alertas.append(
            Alerta(
                NIVEL_CUIDADO,
                f"Tus metas de ahorro piden {dinero(metas.total_mensual)} al mes y el disponible "
                f"de tu presupuesto es {dinero(resumen.disponible)}.",
            )
        )
```

- [ ] **Step 4: Plantilla del tablero**

En `templates/tablero/mes.html`, antes de la sección de deudas (`<section class="tarjeta">` que contiene `<h2 class="mb-2 font-medium">Deudas</h2>`), agregar:
```html
{% if tablero.metas %}
  <section class="tarjeta mb-4">
    <div class="mb-2 flex items-baseline justify-between">
      <h2 class="font-medium">Metas de ahorro</h2>
      <a class="text-xs text-sky-700" href="{% url 'planeacion:metas' %}">Ver metas</a>
    </div>
    {% if tablero.metas.filas %}
      <p class="text-sm">Necesitas ahorrar <strong>{{ tablero.metas.total_mensual|dinero }}</strong> al mes ({{ tablero.metas.porcentaje_ingresos|porcentaje }} de tus ingresos).</p>
      <p class="text-xs text-slate-600">{{ tablero.metas.mensaje }}</p>
    {% else %}
      <p class="text-sm text-slate-500">Aún no tienes metas de ahorro.</p>
    {% endif %}
  </section>
{% endif %}
```
y reemplazar `<p class="mt-2 text-xs text-slate-500">Metas de ahorro y patrimonio se agregan en el plan 3.</p>` por:
```html
  <dl class="mt-2 grid grid-cols-2 gap-x-4 border-t border-slate-100 pt-2 text-sm font-semibold">
    <dt>Patrimonio neto</dt><dd class="text-right">{{ tablero.patrimonio.neto|dinero }}</dd>
  </dl>
  <p class="mt-2 text-xs"><a class="text-sky-700" href="{% url 'planeacion:deudas' %}">Ver deudas</a> · <a class="text-sky-700" href="{% url 'planeacion:patrimonio' %}">Ver patrimonio</a></p>
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `test_tablero_planeacion.py` 6 passed; las pruebas del tablero del plan 2 siguen verdes; todo verde.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/tablero templates/tablero tests/tablero/test_tablero_planeacion.py
git commit -m "feat(tablero): metas de ahorro, patrimonio neto y alerta de metas no alcanzables" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Cierre: documentación, verificación completa y prueba de humo

**Files:**
- Modify: `README.md`
- Modify (fuera del repo): `..\CLAUDE.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: README actualizado; suite, lint, migraciones, imagen y humo verificados.

- [ ] **Step 1: README**

En `README.md`, reemplazar la línea `- **Más**: personas, domicilios, categorías, conceptos y cuentas.` por:
```markdown
- **Más**: catálogos (personas, domicilios, categorías, conceptos y cuentas) y planeación: metas de ahorro, deudas (con «Registrar pago»), patrimonio y simulador de créditos.
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

- [ ] **Step 3: Prueba de humo contra el servidor real**

Con `docker compose up -d` corriendo, guardar este script **fuera del repo** (por ejemplo en `$env:TEMP\humo3.py`) y ejecutarlo:
```python
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import Client

from apps.catalogos.models import Cuenta
from apps.core.servicios import crear_hogar
from apps.planeacion.models import Activo, MetaAhorro

Usuario = get_user_model()
usuario = Usuario.objects.create_user(email="humo3@example.com", password="humo-12345-x")
hogar = crear_hogar("Hogar de humo 3", usuario)
try:
    Cuenta.objects.create(hogar=hogar, nombre="Tarjeta", tipo=Cuenta.Tipo.CREDITO,
                          linea_credito=D("7100"), saldo_actual=D("6839.01"))
    MetaAhorro.objects.create(hogar=hogar, nombre="Regalo", monto_objetivo=D("20000"))
    Activo.objects.create(hogar=hogar, nombre="Auto", valor_actual=D("150000"))
    c = Client(HTTP_HOST="localhost")
    c.force_login(usuario)
    for url in ["/planeacion/metas/", "/planeacion/deudas/", "/planeacion/patrimonio/",
                "/planeacion/simulador/", "/catalogos/", "/"]:
        r = c.get(url, follow=True)
        assert r.status_code == 200, (url, r.status_code)
    r = c.get("/planeacion/simulador/", {"monto": "30000", "tasa_anual": "25", "meses": "12",
                                         "comision_apertura": "1.5"})
    assert "$2,857.62" in r.content.decode()
    assert "$1,591.65" in c.get("/planeacion/metas/").content.decode()
    assert "$143,160.99" in c.get("/planeacion/patrimonio/").content.decode()
    print("HUMO 3 OK")
finally:
    hogar.delete()
    usuario.delete()
```
Run:
```powershell
Get-Content $env:TEMP\humo3.py | docker compose exec -T web python manage.py shell
docker compose exec web python manage.py shell -c "from apps.core.models import Hogar; print(Hogar.objects.filter(nombre='Hogar de humo 3').count())"
```
Expected: `HUMO 3 OK` y luego `0`.

- [ ] **Step 4: Commit y memoria del proyecto**

```powershell
git add README.md
git commit -m "docs: planeacion en el README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

En `..\CLAUDE.md` (fuera del repo), sección "Estado / siguiente paso": marcar el plan 3 como completado y poner como siguiente el plan 4 (importación de PDFs con IA).
