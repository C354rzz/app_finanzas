# Importación inicial desde el Excel del planeador (RF-ACC-04). Por omisión solo simula.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\importar_excel.ps1 -Archivo "..\2026\documentos\Financial Planner template.xlsx" [-Email tu@email.com] [-Aplicar]
param(
    [Parameter(Mandatory = $true)][string]$Archivo,
    [string]$Email,
    [switch]$Aplicar
)
$ruta = (Resolve-Path $Archivo).Path
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$destino = "/tmp/planner.xlsx"
docker compose cp "$ruta" "web:$destino"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$argumentos = @("compose", "exec", "-T", "web", "python", "manage.py", "importar_excel", $destino)
if ($Email) { $argumentos += @("--email", $Email) }
if ($Aplicar) { $argumentos += "--aplicar" }
try {
    & docker @argumentos
    $codigo = $LASTEXITCODE
}
finally {
    docker compose exec -T web rm -f $destino
}
exit $codigo
