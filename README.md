# Finanzas familiares

App web (Django + HTMX + PostgreSQL) que reemplaza el planeador en Excel.
Documentación: `docs/ARQUITECTURA.md`, `docs/DEF.md`, `docs/modelo-datos.dbml`.

## Desarrollo (PowerShell, en `Finanzas\app_finanzas\`)

| Acción | Comando |
|---|---|
| Primera vez | `Copy-Item .env.example .env` y `docker compose build` |
| Levantar | `docker compose up -d` → http://localhost:8000 |
| Recompilar estilos (cambié clases en plantillas) | `docker compose run --rm css` |
| Reiniciar el worker (cambié código de importación) | `docker compose restart worker` |
| Pruebas | `docker compose run --rm web pytest` |
| Lint | `docker compose run --rm web ruff check .` |
| Formato | `docker compose run --rm web ruff format .` |
| Migraciones | `docker compose run --rm web python manage.py makemigrations` |
| Shell Django | `docker compose run --rm web python manage.py shell` |
| Cambié dependencias | `docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock` y `docker compose build` |
| Detener | `docker compose down` (con `-v` **borra la base de datos**) |

⚠️ Los datos personales viven fuera de esta carpeta (`..\2026\`). Nunca copies PDFs ni el Excel aquí.

## Primer uso

```powershell
docker compose up -d
docker compose exec web python manage.py createsuperuser --email tu@email.com
docker compose exec web python manage.py crear_hogar --nombre "Mi Familia" --email tu@email.com
```

Luego entra a http://localhost:8000 con tu email y contraseña:

- **Inicio**: tablero del mes (ingresos y gastos reales contra el presupuesto, categorías, deudas y alertas).
- **+**: registra un gasto, ingreso (aguinaldo, PTU…), transferencia o pago de deuda.
- **Movimientos**: lista del mes con filtros, totales y exportación a CSV.
- **Presupuesto**: plantilla base y ajustes de cada mes.
- **Más**: catálogos (personas, domicilios, categorías, conceptos y cuentas) y planeación: metas de ahorro, deudas (con «Registrar pago»), patrimonio y simulador de créditos.

Desde el celular en la misma red: `http://<IP-de-tu-PC>:8000` (agrega la IP a `DJANGO_ALLOWED_HOSTS` en `.env`).

## Uso diario y acceso desde el celular

**Modo de uso diario** (gunicorn, sin depuración). En `.env`: `DJANGO_DEBUG=0` y una `DJANGO_SECRET_KEY` larga y aleatoria. Luego:

```powershell
docker compose -f docker-compose.yml up -d --build
```

Para volver al modo desarrollo: `docker compose up -d`. Después de actualizar el código (`git pull`), repite el comando de uso diario.

**Fuera de casa con Tailscale** (HTTPS sin abrir puertos del router):

1. Instala Tailscale en la PC y en el celular con la misma cuenta.
2. En https://login.tailscale.com/admin/dns activa **MagicDNS** y **HTTPS Certificates**.
3. En la PC (PowerShell): `tailscale serve --bg 8000`. Muestra tu dirección, por ejemplo `https://mi-pc.tail1234.ts.net`.
4. En `.env` agrega el nombre a `DJANGO_ALLOWED_HOSTS` (`localhost,127.0.0.1,mi-pc.tail1234.ts.net`) y la dirección completa a `DJANGO_CSRF_TRUSTED_ORIGINS` (`https://mi-pc.tail1234.ts.net`). Reinicia con el comando de uso diario.
5. En el celular abre esa dirección e instala la app: en Android, menú ⋮ → **Instalar app**; en iPhone (Safari), Compartir → **Agregar a inicio**.

La app solo responde mientras la PC está encendida. Sin conexión verás el aviso «Sin conexión», nunca datos guardados.

## Importar documentos con IA

1. Crea una clave en https://platform.claude.com y ponla en `.env`: `ANTHROPIC_API_KEY=sk-ant-...`.
2. Reinicia los servicios para que la lean: `docker compose up -d --force-recreate web worker`.
3. En la app: **Importar** → sube PDFs (o un ZIP) → espera a que el estado diga «Por revisar» → **Revisar** → acepta, edita o descarta cada propuesta.

- Solo se envía a la IA el **texto** del documento, con RFC, CURP y números de cuenta ocultos (quedan los últimos 4 dígitos).
- Un estado de cuenta típico cuesta unos centavos de dólar; el costo del mes aparece en la pantalla Importar.
- El contenedor `worker` procesa los documentos. Si cambias código de importación: `docker compose restart worker`.
- Un PDF escaneado (sin texto) queda en error: la v1 no tiene OCR.

## Respaldos

Cada respaldo es un ZIP con la base de datos y los PDFs importados. Contiene tus datos personales: guárdalo en una carpeta privada.

1. En `.env`, elige la carpeta (de preferencia dentro de OneDrive y fuera de este repositorio), por ejemplo `CARPETA_RESPALDOS=C:/Users/tu-usuario/OneDrive/Respaldos/finanzas`, y reinicia: `docker compose up -d` (o el comando de uso diario).
2. Respaldo manual: `powershell -ExecutionPolicy Bypass -File scripts\respaldar.ps1`. El resultado queda en `respaldos.log`.
3. Respaldo diario automático (una sola vez): `powershell -ExecutionPolicy Bypass -File scripts\programar_respaldo.ps1 -Hora 21:00`. Se conservan los 30 más recientes.
4. Restaurar: `powershell -ExecutionPolicy Bypass -File scripts\restaurar.ps1 finanzas-AAAAMMDD-HHMMSS.zip` (pide escribir `RESTAURAR`). Antes de reemplazar, guarda un respaldo `finanzas-antes-de-restaurar-…` de los datos actuales. Si el respaldo está dañado o es de una versión más nueva de la app, no cambia nada.

En una PC nueva: instala Docker, clona el repositorio, crea `.env`, levanta la app y restaura el último respaldo (no hace falta `crear_hogar`).
