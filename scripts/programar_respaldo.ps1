# Registra (una sola vez) la tarea diaria de respaldo en el Programador de tareas de Windows.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\programar_respaldo.ps1 [-Hora 21:00]
param([string]$Hora = "21:00")
$script = Join-Path $PSScriptRoot "respaldar.ps1"
$accion = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$disparador = New-ScheduledTaskTrigger -Daily -At $Hora
# Si la PC estaba apagada a esa hora, corre en cuanto se pueda.
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "Finanzas - respaldo diario" -Action $accion -Trigger $disparador -Settings $ajustes -Description "Respalda la base de datos y los PDFs de la app Finanzas." -Force | Out-Null
Write-Host "Tarea registrada: respaldo diario a las $Hora. Bitácora: $(Join-Path (Split-Path -Parent $PSScriptRoot) 'respaldos.log')"
