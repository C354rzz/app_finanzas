# DEF — Documento de Especificación Funcional
## App de Finanzas Familiares · v1

| Campo | Valor |
|---|---|
| Versión | 1.0 — aprobado |
| Fecha | 2026-10-09 |
| Fuente | `2026/documentos/Financial Planner template.xlsx` + decisiones de diseño (ver `CLAUDE.md`) |
| Documentos relacionados | `ARQUITECTURA.md`, `modelo-datos.dbml` |

---

## 1. Propósito y alcance

### 1.1 Propósito
Reemplazar el planeador financiero en Excel con una aplicación web (PWA) de uso familiar que:
1. Ofrezca **todas** las funciones del Excel (paridad).
2. Reduzca la captura manual con la **importación de PDFs** (estados de cuenta, nómina, recibos) y su revisión antes de guardar.
3. Permita analizar el gasto por **persona** y por **domicilio**.
4. Quede lista para convertirse en producto (multi-hogar).

### 1.2 Dentro del alcance (v1)
Presupuesto (plantilla + mensual), registro de movimientos (gastos, ingresos fijos y extraordinarios, transferencias, pagos de deuda), tablero, metas de ahorro, deudas (tarjetas y créditos), patrimonio, simulador de crédito, catálogos (personas, domicilios, categorías/conceptos, cuentas), importación de documentos con IA, respaldo de datos.

### 1.3 Fuera del alcance (v1)
- Varios usuarios por hogar, roles e invitaciones (v3).
- Alertas por correo/push y recordatorios de fecha de pago (v2).
- Comparativos año contra año e histórico multianual (v2).
- Conexión directa con bancos (open banking).
- Facturación, planes de pago y onboarding público (v3).
- App móvil nativa.
- Varias monedas (la moneda es fija por hogar: MXN).

### 1.4 Glosario
| Término | Significado |
|---|---|
| Hogar | Unidad de datos (tenant). Todo pertenece a un hogar. |
| Persona | Miembro de la familia o tercero al que se atribuye un movimiento (no necesita login). |
| Domicilio | Inmueble al que se atribuye un gasto (ej. Casa Cedro, Casa Fidel). |
| Categoría | Agrupación principal de gasto (las 12 del Excel). |
| Concepto | Renglón dentro de una categoría (ej. Luz, Costco, Netflix). |
| Cuenta | Origen o destino del dinero: efectivo, débito, crédito, préstamo, ahorro, inversión. |
| Gasto hormiga 🐜 | Gasto pequeño y frecuente que el usuario quiere vigilar. |
| Ingreso extraordinario | Ingreso no recurrente (aguinaldo, PTU, bono, beca, préstamo recibido). |
| Plantilla | Presupuesto base del que se genera cada mes. |
| Propuesta | Movimiento extraído de un documento que espera confirmación. |

## 2. Actores

| Actor | Descripción v1 |
|---|---|
| **Administrador del hogar** | Único usuario con login. Captura, importa, configura y consulta todo. |
| **Servicio de extracción (Claude API)** | Sistema externo que convierte el texto de un documento en movimientos estructurados. |
| **Worker** | Proceso en segundo plano que ejecuta la importación. |

## 3. Requisitos funcionales

Prioridad: **M** = obligatorio para v1 · **D** = deseable en v1.

### 3.1 Acceso y configuración (ACC)
| ID | Requisito | Prior. |
|---|---|---|
| RF-ACC-01 | El usuario inicia sesión con email y contraseña. Toda pantalla, salvo el login, requiere sesión. | M |
| RF-ACC-02 | Al crear el hogar se siembran las 12 categorías del Excel con sus iconos, los conceptos del Excel del usuario y el catálogo de tasas de mercado. *(Los conceptos y el catálogo de tasas se cargan con la importación del Excel, RF-ACC-04: no se guardan datos de la plantilla en el repositorio.)* | M |
| RF-ACC-03 | Un usuario solo ve y modifica datos de su hogar. | M |
| RF-ACC-04 | Importación inicial única desde el Excel: plantilla de presupuesto, cuentas/deudas, metas y activos. | D |

### 3.2 Catálogos (CAT)
| ID | Requisito | Prior. |
|---|---|---|
| RF-CAT-01 | CRUD de **Personas** (nombre, parentesco, activo). | M |
| RF-CAT-02 | CRUD de **Domicilios** (alias, dirección, activo). | M |
| RF-CAT-03 | CRUD de **Categorías** (nombre, icono, orden) y **Conceptos** (categoría, nombre, fijo/hormiga y persona/domicilio/cuenta por defecto). | M |
| RF-CAT-04 | CRUD de **Cuentas** con campos según su tipo (ver modelo). En tarjetas de crédito sin tasa capturada se sugiere la tasa promedio del catálogo según institución y producto. | M |
| RF-CAT-05 | Los elementos con movimientos asociados no se borran; se desactivan. | M |

### 3.3 Movimientos (MOV)
| ID | Requisito | Prior. |
|---|---|---|
| RF-MOV-01 | **Captura rápida** de gasto: monto, descripción, categoría/concepto, método de pago y fecha (hoy por defecto). Cuenta, persona, domicilio y marca hormiga se precargan desde el concepto. | M |
| RF-MOV-02 | **Captura de ingreso**: monto, descripción, tipo de ingreso (salario, aguinaldo, PTU, bono, beca, préstamo recibido, reembolso, venta, otro), método (efectivo, transferencia…), cuenta destino, persona y la marca *extraordinario* (activada por defecto en aguinaldo, PTU, bono, beca y préstamo recibido). | M |
| RF-MOV-03 | **Transferencia** entre cuentas propias y **pago de deuda** (cuenta origen → tarjeta/préstamo). No cuentan como gasto ni como ingreso. | M |
| RF-MOV-04 | Lista de movimientos por mes con filtros por tipo, categoría, persona, domicilio, cuenta y método de pago, y búsqueda por texto. | M |
| RF-MOV-05 | Edición en línea y eliminación de movimientos (con confirmación). | M |
| RF-MOV-06 | Totales del mes por categoría, por método de pago y por cuenta (equivalente a las tablas de las hojas 01–12). | M |
| RF-MOV-07 | Exportar los movimientos del mes o del año a CSV/Excel. | D |

### 3.4 Presupuesto (PRE)
| ID | Requisito | Prior. |
|---|---|---|
| RF-PRE-01 | Editar la **plantilla**: ingresos esperados (nombre, tipo, fijo/variable, monto, persona) y gastos por concepto (monto, periodicidad mensual/anual, fijo, con tarjeta, hormiga). | M |
| RF-PRE-02 | Definir el **% de ahorro** deseado (0–100%; sugerencias 5/10/15/20/25%) con el mensaje motivacional del Excel según el valor. | M |
| RF-PRE-03 | La primera vez que se consulta un mes se crea su **presupuesto mensual** copiando la plantilla. Ese presupuesto se puede ajustar sin afectar la plantilla ni otros meses. | M |
| RF-PRE-04 | Opción "re-sincronizar mes con la plantilla" (reemplaza el presupuesto del mes, previa confirmación). | D |
| RF-PRE-05 | Mostrar el resumen: ingresos fijos/variables/total, gastos fijos/variables/total, disponible promedio, meta de ahorro mensual, presupuesto hormiga, máximo diario hormiga y recorte necesario (RN-01 a RN-04). | M |

### 3.5 Tablero (TAB)
| ID | Requisito | Prior. |
|---|---|---|
| RF-TAB-01 | Tablero del mes seleccionado: ingresos esperados vs. reales, gasto presupuestado vs. real, disponible del mes. | M |
| RF-TAB-02 | Por categoría: presupuesto, gastado, restante y % de avance, con color (verde < 80%, ámbar 80–100%, rojo > 100%). | M |
| RF-TAB-03 | Distribución del gasto por categoría (% del total) y gasto anual estimado (total mensual × 12). | M |
| RF-TAB-04 | Filtros por persona y domicilio (ej. "costo mensual de Casa Fidel"). | M |
| RF-TAB-05 | Resumen de metas de ahorro, de deudas y del patrimonio neto. | M |
| RF-TAB-06 | Alertas de RN-08 (uso de tarjetas), RN-09 (pago de intereses), disponible negativo y meta de ahorro no alcanzable. | M |

### 3.6 Metas de ahorro (MET)
| ID | Requisito | Prior. |
|---|---|---|
| RF-MET-01 | CRUD de metas sin límite de cantidad: tipo, nombre, ahorro actual, meses, tasa anual, monto objetivo y cuenta (opcional). | M |
| RF-MET-02 | Calcular el **ahorro mensual necesario** por meta (RN-05) y el total mensual de metas, junto con su % sobre los ingresos. | M |
| RF-MET-03 | Alertar si el total de metas supera el disponible del mes. | M |

### 3.7 Deudas (DEU)
| ID | Requisito | Prior. |
|---|---|---|
| RF-DEU-01 | Vista de tarjetas de crédito: institución, producto, tasa (capturada o promedio de mercado), saldo, línea, % de uso y si paga el total. | M |
| RF-DEU-02 | Vista de créditos: tipo, deuda inicial, deuda actual, mensualidad y % completado (RN-06). | M |
| RF-DEU-03 | Totales: deuda total en tarjetas, deuda total en créditos y suma de mensualidades. | M |
| RF-DEU-04 | Gasto promedio con tarjeta según el presupuesto (suma de los conceptos "con tarjeta") y gasto real del mes con tarjeta de crédito. | M |
| RF-DEU-05 | Registrar un pago de deuda desde esta vista (crea un movimiento `pago_deuda`). | D |

### 3.8 Patrimonio (PAT)
| ID | Requisito | Prior. |
|---|---|---|
| RF-PAT-01 | CRUD de activos: tipo, nombre, valor actual, fecha de valuación y domicilio/cuenta (opcional). | M |
| RF-PAT-02 | Calcular el patrimonio neto (RN-10). | M |

### 3.9 Simulador de crédito (SIM)
| ID | Requisito | Prior. |
|---|---|---|
| RF-SIM-01 | Entradas: monto, tasa anual, meses, comisión por apertura y pagos anticipados por mes. | M |
| RF-SIM-02 | Salidas: tasa efectiva mensual, mensualidad, total de intereses y tabla de amortización (mes, mensualidad, intereses, capital, saldo final, capital acumulado, pago anticipado) según RN-07. | M |
| RF-SIM-03 | Guardar y nombrar simulaciones (opcional). | D |

### 3.10 Importación de documentos (IMP)
| ID | Requisito | Prior. |
|---|---|---|
| RF-IMP-01 | Subir uno o varios archivos PDF o ZIP (se extraen los PDF que contenga), de hasta 20 MB cada uno. | M |
| RF-IMP-02 | Rechazar un archivo ya importado (mismo SHA-256) e indicar cuándo se importó. | M |
| RF-IMP-03 | Procesar en segundo plano. La pantalla muestra el estado (subido → procesando → por revisar / error) y se actualiza sola. | M |
| RF-IMP-04 | Extraer el texto del PDF localmente. Si no hay texto (PDF escaneado), marcar error "requiere OCR" (OCR fuera de alcance v1). | M |
| RF-IMP-05 | Clasificar el documento (estado de cuenta, nómina, recibo de servicio), identificar emisor, periodo y cuenta, y extraer los movimientos con fecha, descripción original, monto, tipo y categoría/persona/domicilio sugeridos con un nivel de confianza. | M |
| RF-IMP-06 | Aplicar las **reglas de clasificación** del hogar antes que la sugerencia de la IA (RN-12). | M |
| RF-IMP-07 | Marcar **posibles duplicados** contra movimientos existentes (RN-11). | M |
| RF-IMP-08 | Pantalla de revisión: tabla editable de propuestas. Por fila: aceptar, editar o descartar. Acciones masivas: aceptar todo lo no duplicado, descartar todo. | M |
| RF-IMP-09 | Al aceptar una propuesta se crea el movimiento con `origen = importado` y el enlace al documento. Opción "recordar esta clasificación", que crea una regla. | M |
| RF-IMP-10 | **Nómina**: crear una propuesta de ingreso `salario` por el neto del recibo, con el periodo en la descripción. Las percepciones extraordinarias del recibo (aguinaldo, PTU, bono) se proponen como ingresos aparte. | M |
| RF-IMP-11 | **Recibo de servicio**: se identifica (emisor y periodo) pero **no genera propuesta de gasto**, porque un recibo no prueba el pago; el gasto entra cuando aparece el cargo en el estado de cuenta o se captura a mano. *(Cambio aprobado por el usuario el 2026-10-09; la conciliación recibo ↔ pago queda para la v2.)* | M |
| RF-IMP-12 | **Estado de cuenta**: actualizar el saldo de la cuenta (`saldo_actual`, `fecha_saldo`) con el saldo al corte, previa confirmación. | D |
| RF-IMP-13 | Registrar por documento el modelo usado, los tokens y el costo estimado. Mostrar el costo acumulado del mes. | M |
| RF-IMP-14 | Ver el documento original desde la propuesta o el movimiento. | D |

### 3.11 Datos y respaldo (DAT)
| ID | Requisito | Prior. |
|---|---|---|
| RF-DAT-01 | Comando de respaldo de la base de datos y de los archivos subidos hacia una carpeta configurable. | M |
| RF-DAT-02 | Comando de restauración documentado y probado. | M |

## 4. Reglas de negocio (cálculos)

Todas las cantidades monetarias usan `Decimal` y se redondean a 2 decimales **solo al mostrar**. Los valores de verificación ("✔") salen del Excel actual del usuario y sirven como pruebas de aceptación.

| ID | Regla | Verificación |
|---|---|---|
| **RN-01** Totales de presupuesto | Ingresos totales = Σ ingresos del mes. Gastos totales = Σ `monto_mensual` de los gastos. Disponible = ingresos − gastos. Gastos fijos = Σ gastos con `es_fijo`; variables = total − fijos. | ✔ Ingresos 32,977.52 · Gastos 29,235.00 · Disponible 3,742.52 · Fijos 26,337 · Variables 2,898 |
| **RN-02** Meta de ahorro mensual | meta = ingresos totales × % ahorro. | ✔ 32,977.52 × 5% = 1,648.876 |
| **RN-03** Prorrateo anual | Gasto `anual` → monto mensual = monto / 12, aplicado **igual** en presupuesto, tablero y meses. (Corrige la inconsistencia del Excel, que solo dividía en algunos lugares.) | — |
| **RN-04** Gastos hormiga | Presupuesto hormiga = Σ gastos con `es_hormiga`. Máximo diario = presupuesto hormiga / 30. Recorte necesario = si (disponible − meta) ≥ 0 → "N/A"; si no, mostrar \|disponible − meta\|. | ✔ 2,739 · 91.30/día · N/A |
| **RN-05** Ahorro mensual por meta | i = tasa/12, n = meses, A = ahorro actual, M = meta. Aporte = max(0, (M − A·(1+i)^n)·i / ((1+i)^n − 1)). Si i = 0: max(0, (M − A)/n). | ✔ Regalo (20,000; 12 m; 10%) = 1,591.65 · Vacaciones (45,000) = 3,581.21 · Total 5,172.87 = 15.69% del ingreso |
| **RN-06** % completado de crédito | 1 − deuda actual / deuda inicial (o "—" si la deuda inicial es 0). | ✔ 1 − 38,679.72/41,130 = 5.96% |
| **RN-07** Amortización | Tasa efectiva mensual r = (1 + tasa anual)^(1/12) − 1. Capital inicial C₀ = monto × (1 + comisión). Mes k: pago = PMT(r, n − (k−1), saldo_{k−1}) + anticipado_k; interés = saldo_{k−1}·r; capital = pago − interés; saldo_k = saldo_{k−1} − capital. Total intereses = Σ interés. | ✔ 30,000; 25%; 12 m; 1.5% → C₀ = 30,450 · r = 1.8769% · mensualidad 2,857.62 · intereses 3,841.45 |
| **RN-08** Uso de tarjetas (utilización de crédito) | % uso = Σ saldo de tarjetas / Σ línea de crédito; se calcula también por tarjeta. < 30% "buen nivel"; 30–50% "cuidado"; > 50% "riesgo". **Corrige el Excel**, que dividía el gasto mensual con tarjeta entre la línea. Ese cálculo no se usa como indicador; el gasto con tarjeta se muestra solo como dato informativo (RF-DEU-04). | ✔ 6,839.01 / 7,100 = 96.32% → "riesgo" |
| **RN-09** Intereses | Si una tarjeta tiene `paga_total_mensual = No` → alerta "estás pagando intereses". | — |
| **RN-10** Patrimonio neto | Σ activos − Σ saldos de préstamos − Σ saldos de tarjetas. | ✔ 2,593,519.94 − 38,679.72 − 6,839.01 = 2,548,001.21 |
| **RN-11** Posible duplicado | Una propuesta es posible duplicado si existe un movimiento del hogar con el mismo monto, la misma cuenta (o sin cuenta) y fecha a ±2 días. | — |
| **RN-12** Prioridad de clasificación | Regla del hogar (por prioridad, coincidencia de patrón sin acentos ni mayúsculas) > sugerencia de la IA > sin clasificar. | — |
| **RN-13** Ingresos extraordinarios | Cuentan en el ingreso **real** del mes en que llegan, pero **no** en el "ingreso promedio mensual" del presupuesto ni en el cálculo de la meta de ahorro. Se muestran como "ingresos extra del mes". | — |
| **RN-14** Signo de movimientos | Gasto resta, ingreso suma, transferencia y pago de deuda son neutrales en el balance gasto/ingreso. El pago de deuda reduce el saldo de la cuenta de crédito destino. | — |
| **RN-15** Disponible del mes (real) | Ingresos reales del mes (incluye extraordinarios) − gastos reales del mes. | — |

## 5. Pantallas

| # | Pantalla | Contenido principal | RF |
|---|---|---|---|
| P1 | Login | Email y contraseña | ACC-01 |
| P2 | Inicio / Tablero | Selector de mes, tarjetas resumen, barras por categoría, alertas, filtros por persona/domicilio | TAB-* |
| P3 | Captura rápida (modal, botón "+") | Selector Gasto/Ingreso/Transferencia/Pago, campos mínimos, valores por defecto | MOV-01..03 |
| P4 | Movimientos | Lista filtrable, edición en línea, totales por método y cuenta | MOV-04..07 |
| P5 | Presupuesto | Pestañas Plantilla / Mes actual; resumen y alertas | PRE-* |
| P6 | Metas | Tarjetas por meta con aporte mensual | MET-* |
| P7 | Deudas | Tablas de tarjetas y créditos, indicadores | DEU-* |
| P8 | Patrimonio | Lista de activos y patrimonio neto | PAT-* |
| P9 | Simulador | Formulario y tabla de amortización | SIM-* |
| P10 | Importar | Zona de carga, lista de documentos con estado y costo | IMP-01..04, 13 |
| P11 | Revisar documento | Tabla editable de propuestas, acciones masivas | IMP-05..12 |
| P12 | Catálogos | Personas, domicilios, categorías/conceptos, cuentas | CAT-* |

Navegación móvil: barra inferior (Inicio · Movimientos · **+** · Importar · Más). Escritorio: barra lateral.

## 6. Flujos principales

**F1 — Inicio de mes:** abrir el tablero de un mes nuevo → se crea el presupuesto del mes desde la plantilla (RF-PRE-03) → el usuario ajusta si es necesario.

**F2 — Gasto diario:** "+" → monto, concepto → guardar (≤ 3 toques tras abrir). El tablero refleja el cambio de inmediato.

**F3 — Importar un estado de cuenta:** subir el PDF → se verifica el hash → el worker extrae el texto y llama a la IA → aplica las reglas → marca duplicados → estado "por revisar" → el usuario revisa, acepta o edita → se crean los movimientos → el documento queda "confirmado".

**F4 — Aguinaldo:** registrar un ingreso tipo `aguinaldo` (o aceptarlo desde la nómina importada) → suma al ingreso real de diciembre como extraordinario, sin alterar el promedio mensual (RN-13).

## 7. Requisitos no funcionales

| ID | Requisito |
|---|---|
| RNF-01 Usabilidad | Diseño mobile-first, PWA instalable; la captura rápida funciona en pantallas de 360 px. |
| RNF-02 Rendimiento | Pantallas de lectura < 500 ms con 10,000 movimientos en la PC local. Importación de un estado de cuenta de 10 páginas < 2 min. |
| RNF-03 Privacidad | Los datos viven en la PC del usuario. A la Claude API solo se envía el **texto** del documento, sin el archivo, y únicamente durante la importación. Las claves van en `.env`, fuera de git. |
| RNF-04 Seguridad | Sesión obligatoria; aislamiento por hogar en cada consulta; CSRF activo; HTTPS para el acceso remoto (Tailscale). |
| RNF-05 Exactitud | Todos los cálculos en `Decimal`; las RN con "✔" son pruebas automatizadas. |
| RNF-06 Respaldo | Respaldo automatizable (diario recomendado) con restauración probada. |
| RNF-07 Costo | Costo de IA estimado < 5 USD/mes con ~10 documentos al mes. |
| RNF-08 Idioma/región | Español (México), formato de moneda `$1,234.56`, zona horaria America/Monterrey. |
| RNF-09 Mantenibilidad | Python 3.12, cobertura de pruebas ≥ 80% en cálculos e importación, CI en cada push. |

## 8. Criterios de aceptación de la v1
1. Con los datos del Excel cargados, la app reproduce todos los valores "✔" de la sección 4.
2. Los 5 recibos de agua, 4 de luz, 3 de internet, 10 de nómina y 8 estados de cuenta de 2026 se importan con propuestas correctas, y en la revisión se corrigen menos del 20% de los campos.
3. Reimportar un archivo existente se rechaza.
4. Se puede registrar un gasto desde el celular en menos de 15 segundos.
5. Un respaldo se restaura en una instalación limpia sin pérdida de datos.

## 9. Supuestos y preguntas abiertas
- **Confirmado (2026-10-09):** DEF = Documento de Especificación Funcional. Documentos revisados y aprobados por el usuario.
- **Confirmado (2026-10-09):** RN-08 usa saldo / línea de crédito (el indicador estándar).
- **Supuesto:** la tasa promedio de mercado del Excel (hoja "No borrar") es suficiente; no se actualiza en línea.
- **Supuesto:** el "mes" financiero es el mes calendario (la nómina es quincenal, 15/30).
