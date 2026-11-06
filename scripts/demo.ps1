# Prepara y arranca la demostración de ComParte en Windows (PowerShell).
#
#   .\scripts\demo.ps1                  # hora de demo 16:00, datos recién cargados, puerto 8000
#   .\scripts\demo.ps1 -Hora 15:30 -Puerto 8080 -SinHistorial
#
# Qué hace: crea el entorno virtual si no existe, instala las dependencias, borra y recarga los datos de
# prueba, fija la hora de la aplicación (así el video no depende de la hora real) y arranca el servidor.
# Si tu carpeta está en OneDrive, define $env:COMPARTE_VENV con una ruta fuera de OneDrive para no
# sincronizar miles de archivos del entorno virtual.

param(
    [string]$Hora = "16:00",
    [int]$Puerto = 8000,
    [switch]$SinHistorial
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$venv = if ($env:COMPARTE_VENV) { $env:COMPARTE_VENV } else { ".venv" }
if (-not (Test-Path $venv)) {
    Write-Host "Creando el entorno virtual en $venv ..."
    python -m venv $venv
}
$python = Join-Path $venv "Scripts\python.exe"

Write-Host "Instalando dependencias ..."
& $python -m pip install --quiet -r requirements.txt

$argumentos = @("-m", "comparte", "servir", "--puerto", $Puerto, "--hora-demo", $Hora, "--reiniciar")
if ($SinHistorial) { $argumentos += "--sin-historial" }

Write-Host "Abre http://127.0.0.1:$Puerto  (Ctrl+C para detener)"
& $python @argumentos
