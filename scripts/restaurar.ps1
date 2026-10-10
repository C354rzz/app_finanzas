# Restaura un respaldo (RF-DAT-02). REEMPLAZA todos los datos actuales.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\restaurar.ps1 finanzas-20261009-210000.zip
# El ZIP debe estar en la carpeta de respaldos (CARPETA_RESPALDOS del .env).
param([Parameter(Mandatory = $true)][string]$Archivo)
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$nombre = Split-Path -Leaf $Archivo
$respuesta = Read-Host "Esto reemplaza TODOS los datos actuales por los de $nombre. Escribe RESTAURAR para continuar"
if ($respuesta -cne "RESTAURAR") {
    Write-Host "Cancelado: no se cambió nada."
    exit 1
}
docker compose stop worker
docker compose exec -T web python manage.py restaurar $nombre --confirmar
$codigo = $LASTEXITCODE
docker compose start worker
exit $codigo
