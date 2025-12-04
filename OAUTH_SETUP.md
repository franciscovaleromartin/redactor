# Configuración OAuth 2.0 para Google Drive

## Paso 1: Obtener Credenciales OAuth 2.0

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto: **gen-lang-client-0644096793**
3. En el menú lateral, ve a **APIs & Services** → **Credentials**
4. Click en **+ CREATE CREDENTIALS** → **OAuth 2.0 Client ID**
5. Si es la primera vez, te pedirá configurar la pantalla de consentimiento:
   - Click en **CONFIGURE CONSENT SCREEN**
   - Selecciona **External** (o Internal si tienes Google Workspace)
   - Rellena los campos obligatorios:
     - App name: `Redactor SIDN`
     - User support email: tu email
     - Developer contact: tu email
   - Click **SAVE AND CONTINUE** hasta completar
6. Ahora crea el OAuth Client ID:
   - Application type: **Desktop app**
   - Name: `Redactor Desktop Client`
   - Click **CREATE**
7. Descarga el archivo JSON de credenciales
8. Renombra el archivo a `oauth_credentials.json` 
9. **Mueve el archivo a la raíz del proyecto** (junto a `app.py`)

## Paso 2: Probar la Aplicación

Una vez tengas `oauth_credentials.json` en la raíz del proyecto:

1. Reinicia el servidor Flask
2. Genera un artículo
3. Click en **"Enviar a Google Drive"**
4. Se abrirá automáticamente una ventana del navegador pidiendo autorización
5. Inicia sesión con tu cuenta de Google
6. Autoriza la aplicación
7. El archivo se guardará en tu Google Drive personal (en la raíz)

## Notas Importantes

- Los tokens de acceso se guardan en `token.json` y se renuevan automáticamente
- Solo necesitas autorizar una vez; las siguientes veces usará el token guardado
- Los archivos se guardan en la raíz de tu Drive personal (no en una carpeta específica)
- Si quieres guardar en una carpeta específica, puedes modificar el código en `script.js` para enviar un `folder_id`

## Troubleshooting

**Error: "OAuth credentials file not found"**
- Asegúrate de que `oauth_credentials.json` está en la raíz del proyecto

**Error: "The user's Drive storage quota has been exceeded"**
- Ya no debería pasar porque ahora usa tu cuenta personal, no la service account

**El navegador no se abre para autorizar**
- Comprueba que el servidor Flask está corriendo en `http://localhost:5000`
- Revisa la consola, debería aparecer una URL para autorizar manualmente
