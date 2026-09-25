@echo off
setlocal
for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set D=%%d%%b%%c
for /f "tokens=1-3 delims=:,. " %%a in ("%time%") do set T=%%a%%b%%c
set OUT=presupuesto_local_%D%_%T%.dump
for /f "delims=" %%i in ('docker compose ps -q db') do set DBID=%%i
if "%DBID%"=="" (
  echo No se encontro el contenedor db. Ejecute este archivo desde la carpeta de la aplicacion local.
  pause
  exit /b 1
)
docker exec %DBID% sh -c "pg_dump -U presupuesto -d presupuesto -Fc -f /tmp/presupuesto.dump"
docker cp %DBID%:/tmp/presupuesto.dump "%OUT%"
docker exec %DBID% rm -f /tmp/presupuesto.dump
echo Respaldo creado: %OUT%
pause
