$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$file = "presupuesto_local_$stamp.dump"
Write-Host "Creando respaldo de la base local en $file ..."
docker compose exec -T db pg_dump -U presupuesto -d presupuesto -Fc | Set-Content -Encoding Byte $file
Write-Host "Si PowerShell muestra un error con la salida binaria, use el comando alternativo documentado en GUIA_PUBLICACION_WEB.md."
