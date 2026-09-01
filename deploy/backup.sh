#!/bin/bash
# Respaldo diario cifrado de la base de datos y el .env a Google Drive.
# Se ejecuta automaticamente via systemd timer (ver sistema-nutricion-backup.timer).

set -e

DIR="/opt/sistema-nutricion"
FECHA=$(date +%Y-%m-%d_%H%M)
TMP_TAR="/tmp/respaldo_${FECHA}.tar.gz"
TMP_GPG="/tmp/respaldo_${FECHA}.tar.gz.gpg"
CARPETA_DRIVE_ID="1AexbrpkVhn-F67SyeFx7y145Tua4q4kt"

echo "[$(date)] Iniciando respaldo..."

# 1. Empaquetar base de datos y .env
tar -czf "$TMP_TAR" -C "$DIR" sistema_nutricion.db .env

# 2. Cifrar con GPG (simetrico, con la frase guardada en .backup_passphrase)
gpg --batch --yes --passphrase-file "$DIR/.backup_passphrase" \
    --symmetric --cipher-algo AES256 \
    -o "$TMP_GPG" "$TMP_TAR"

# 3. Subir a Google Drive
rclone copy "$TMP_GPG" gdrive-marifer: --drive-root-folder-id "$CARPETA_DRIVE_ID"

# 4. Limpiar archivos temporales locales
rm -f "$TMP_TAR" "$TMP_GPG"

# 5. Rotacion: borrar de Drive los respaldos con mas de 30 dias
rclone delete gdrive-marifer: --drive-root-folder-id "$CARPETA_DRIVE_ID" --min-age 30d

echo "[$(date)] Respaldo completado: respaldo_${FECHA}.tar.gz.gpg"
