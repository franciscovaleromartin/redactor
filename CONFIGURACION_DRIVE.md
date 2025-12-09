# Configuración de Google Drive

## Carpeta Compartida

Todos los artículos generados (tanto desde la web como desde Google Sheets) se guardan en esta carpeta compartida de Google Drive:

**📁 Carpeta:** https://drive.google.com/drive/folders/1FTAbii3OX4063iq-mx5rmBxYjdiZuO7l?usp=sharing

## Configuración en Producción (Render)

En Render, configura la variable de entorno:

```
DRIVE_FOLDER_ID=1FTAbii3OX4063iq-mx5rmBxYjdiZuO7l
```

## Funcionamiento

- ✅ Todos los usuarios guardan artículos en la misma carpeta compartida
- ✅ No es necesario que cada usuario se conecte a Drive
- ✅ El administrador conecta su cuenta de Drive una vez
- ✅ Todos los artículos se guardan con las credenciales del administrador

## Script de Google Sheets

Los usuarios pueden usar el script de Google Sheets sin necesidad de tokens. El script envía los datos a la web, y la web guarda los artículos usando las credenciales del administrador en la carpeta compartida.

## Notas Importantes

- El administrador debe conectar su cuenta de Drive desde la web
- Las credenciales se guardan en `token.json` en el servidor
- Todos los artículos se guardan en la carpeta compartida configurada
- Los usuarios de Google Sheets no necesitan autenticarse
