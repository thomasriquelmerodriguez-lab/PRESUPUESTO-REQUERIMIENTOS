@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>&1
if errorlevel 1 (
  echo Debe instalar e iniciar Docker Desktop antes de ejecutar la aplicacion.
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop esta instalado, pero el motor no esta funcionando.
  echo Abra Docker Desktop y espere hasta que aparezca Engine running.
  pause
  exit /b 1
)

echo Construyendo e iniciando el Sistema de Requerimientos...
docker compose up --build -d
if errorlevel 1 (
  echo.
  echo No fue posible iniciar la aplicacion.
  echo Ejecute: docker compose logs --tail=100
  pause
  exit /b 1
)

echo Esperando que el servidor inicie...
timeout /t 10 /nobreak >nul
start "" http://localhost:8000
echo.
echo Aplicacion iniciada en http://localhost:8000
pause
