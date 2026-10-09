# Proyecto: App de Finanzas Familiares

Memoria del proyecto. Registra contexto, decisiones y estado. Actualizar cuando cambie algo.

## Origen
- Base: `2026/documentos/Financial Planner template.xlsx` (plantilla Digitt, pensada para Google Sheets, personalizada por el usuario).
- Objetivo: reemplazar el Excel con una app web y luego escalarla a producto.

## Estructura de carpetas (datos personales, NO son código)
- `2026/documentos/`: el Excel base.
- `2026/bancos/{coppel, hey banco, plata, stori}/`: estados de cuenta en PDF (plata y stori vacías).
- `2026/nomina/`: recibos de nómina quincenales de Coppel (`90280004-AAAA-MM-DD.pdf`, mayo–septiembre 2026).
- `2026/recibos/{agua, luz, internet}/`: recibos de servicios. Internet viene en .zip (dentro, PDF de estado de cuenta y factura).
- Todos los PDFs tienen texto extraíble (no requieren OCR).
- ⚠️ Contienen datos sensibles (RFC, CURP, NSS, cuentas). Nunca se suben a git ni se usan como fixtures sin anonimizar.

## Cómo funciona el Excel (lo que hay que igualar)
- **Presupuesto** (centro): ingresos fijos/variables, % de ahorro (5–25%), 12 categorías (Casa, Comida, Familia, Transporte, Viajes, Deudas, Salud, Suscripciones, Gastos anuales [÷12], Cuidado personal, Entretenimiento, Otros). Marcas por concepto: ¿fijo?, ¿con tarjeta?, ¿hormiga? Calcula el presupuesto hormiga, el máximo diario (÷30) y cuánto recortar para cumplir la meta.
- **Mis Finanzas**: tablero de ingresos vs. gastos esperados, disponible a fin de mes, % por categoría, resumen de ahorros y deudas.
- **Metas de Ahorro**: 4 metas; aporte mensual = ((meta − actual·(1+i/12)^n)·(i/12)) / ((1+i/12)^n − 1), mínimo 0.
- **Deudas**: tarjetas (tasa promedio del mercado desde un catálogo oculto, saldo, línea, % de uso con alertas <30% / 30–50% / >50%) y créditos (inicial, actual, mensualidad, % pagado).
- **Patrimonio**: activos − (créditos + saldos de tarjetas).
- **Hojas 01–12**: registro de gastos (concepto=categoría, monto, método de pago, tarjeta) → presupuesto vs. gastado vs. restante. Todas están vacías; octubre tiene ingresos extra.
- **Simulador de Créditos**: amortización con tasa efectiva mensual ((1+anual)^(1/12)−1), comisión de apertura sumada al capital, PMT y pagos anticipados.
- Defectos conocidos que la app corrige: gastos anuales ÷12 inconsistentes, métodos de pago distintos según el mes, presupuesto único para todo el año, sin histórico.

## Decisiones tomadas (2026-10-09)
- **Alcance**: primero uso personal/familiar, pero diseñada multi-hogar (tenant = Hogar) para volverse producto.
- **v1**: paridad con el Excel + importación básica de PDFs (bancos, nómina, recibos) con revisión manual antes de guardar.
- **Uso familiar**: en la v1 solo el usuario tiene login. Los movimientos se etiquetan por **Persona** (hijos, Fidel, titulares de recibos) y por **Domicilio** (varios domicilios).
- **Ingresos adicionales por mes**: efectivo o transferencia; tipos salario, aguinaldo, utilidades (PTU), bono, beca, préstamo recibido, otros; fijo vs. extraordinario.
- **Plataforma**: web responsive / PWA.
- **Stack**: Django + HTMX + PostgreSQL (enfoque A). Importación con Claude API (texto del PDF → movimientos propuestos), con parsers fijos por banco como optimización futura.
- **Entorno**: Docker local disponible (Docker 29.8, Compose v5); git 2.51; `gh` no instalado.
- **Despliegue**: por ahora solo en la PC del usuario con Docker Compose (Django + Postgres). Acceso desde el celular por la red local o Tailscale. CI con GitHub Actions (pruebas en cada push) desde el inicio; el despliegue continuo a un VPS con Docker Compose vía SSH queda para después, cuando haya servidor.
- **Repositorio de código**: la raíz del repo es esta carpeta `Finanzas/` (decisión del usuario, 2026-10-09). `2026/` y cualquier carpeta de año quedan en `.gitignore`. Mitigaciones de OneDrive: datos de Postgres y media solo en volúmenes Docker con nombre; nada de `.venv/` dentro del repo; push frecuente a GitHub (ver ADR-08).

## Modelo de datos (sección 1, aprobada)
Hogar, Usuario · Persona, Domicilio, Categoría (+subconceptos), Cuenta (débito/crédito/efectivo/préstamo: banco, tasa, línea, saldo, día de corte y de pago) · Movimiento (gasto/ingreso/transferencia/pago de deuda; método de pago, cuenta, persona, domicilio, hormiga, tipo de ingreso, origen manual/importado) · Plantilla de presupuesto (periodicidad mensual/anual) → Presupuesto mensual (copia ajustable) · Meta de ahorro (sin límite de 4) · Activo · Simulación de crédito · Documento → Movimiento propuesto.

## Fases
1. v1: paridad con el Excel + personas/domicilios + ingresos extra + importación con revisión.
2. v2: histórico año contra año, alertas y recordatorios de pago (CFE, agua, tarjetas), conciliación de nómina.
3. v3: producto (multiusuario con roles, onboarding, planes de pago).

## Documentos del proyecto (`docs/`)
- `docs/ARQUITECTURA.md`: contexto, contenedores Docker, componentes Django, flujo de importación, despliegue, CI, stack, seguridad, ADRs (diagramas Mermaid).
- `docs/modelo-datos.dbml`: modelo de BD completo (22 tablas, validado con @dbml/core → PostgreSQL). Ver en dbdiagram.io.
- `docs/DEF.md`: Documento de Especificación Funcional (RF por módulo, reglas de negocio RN-01..15 con valores del Excel como pruebas, pantallas, RNF, criterios de aceptación).
- v1.0 aprobados por el usuario el 2026-10-09.

## Decisiones técnicas adicionales (aprobadas en los docs)
- Django 5.2 LTS, HTMX 2, Tailwind CLI standalone, Chart.js, Django-Q2 (broker ORM, sin Redis), pypdf, uv, ruff, pytest.
- Contenedores: web + worker (misma imagen) + db (Postgres 17) + backup opcional.
- IA: `claude-opus-5-5`, effort low, `messages.parse` con Pydantic, solo texto (no PDF), fallbacks default. Costo estimado ≈ 1–2 USD/mes.
- RN-08 (confirmado): % de uso de tarjetas = saldo / línea. El cálculo del Excel (gasto mensual / línea) se descarta como indicador.

## Estado / siguiente paso
- 2026-10-09: docs v1.0 aprobados; repo git inicializado en `Finanzas/`.
- Siguiente: plan de implementación en `docs/superpowers/plans/` → ejecución por fases.
- Idioma de trabajo con el usuario: español.
