#!/bin/sh
# Verifica que archivos sensibles colocados en subcarpetas NO entren a la imagen Docker.
# Uso (desde app_finanzas/): sh tests/verificar_imagen.sh
set -e
SENUELOS="docs/senuelo.pdf apps/senuelo.xlsx apps/senuelo.xls finanzas/senuelo.xml tests/senuelo.zip tests/senuelo.csv apps/.env"
for f in $SENUELOS; do echo "dato sensible" > "$f"; done
trap 'for f in $SENUELOS; do rm -f "$f"; done' EXIT
docker build -q --build-arg PYTHON_IMAGE="${PYTHON_IMAGE:-python:3.12-slim}" -f docker/Dockerfile -t finanzas:verificar-imagen . > /dev/null
encontrados=$(docker run --rm --entrypoint sh finanzas:verificar-imagen -c "find /app -name 'senuelo*' -o -path '/app/apps/.env'")
if [ -n "$encontrados" ]; then
    echo "FALLA: archivos sensibles dentro de la imagen:"; echo "$encontrados"; exit 1
fi
echo "OK: ningún archivo sensible entró a la imagen"
