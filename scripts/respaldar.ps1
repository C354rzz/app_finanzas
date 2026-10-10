# Respaldo de Finanzas (RF-DAT-01). Lo ejecuta a diario el Programador de tareas de Windows.
# Uso manual: powershell -ExecutionPolicy Bypass -File scripts\respaldar.ps1
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$bitacora = Join-Path $raiz "respaldos.log"
$salida = & docker compose exec -T web python manage.py respaldar --conservar 30 2>&1 | ForEach-Object { "$_" }
$codigo = $LASTEXITCODE
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') codigo=$codigo $($salida -join ' ')" | Add-Content -Encoding UTF8 $bitacora
exit $codigo
