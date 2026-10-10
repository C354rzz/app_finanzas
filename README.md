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
