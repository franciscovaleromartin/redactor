# Configuración Web OAuth 2.0 para Producción

## 🔴 IMPORTANTE: Cambio Necesario en Google Cloud Console

El código ahora usa **Web Application OAuth** en lugar de Desktop App. Necesitas crear **nuevas credenciales**.

## Paso 1: Crear OAuth Web Application

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto: **gen-lang-client-0644096793**
3. En el menú lateral, ve a **APIs & Services** → **Credentials**
4. Click en **+ CREATE CREDENTIALS** → **OAuth 2.0 Client ID**
5. Si es la primera vez, configura la pantalla de consentimiento (como indicaste antes)
6. **Application type:** Selecciona **Web application**
7. **Name:** `Redactor Web Client`
8. **Authorized redirect URIs**: Añade **ambas** URLs:
   - **Local**: `http://localhost:5000/oauth2callback`
   - **Render**: `https://tu-app-nombre.onrender.com/oauth2callback`
     - ⚠️ Reemplaza `tu-app-nombre` con el nombre real de tu app en Render
9. Click **CREATE**
10. Descarga el archivo JSON de credenciales

## Paso 2: Configurar Localmente

1. Abre el archivo JSON descargado
2. Debería verse así:
   ```json
   {
     "web": {
       "client_id": "...",
       "client_secret": "...",
       "redirect_uris": ["..."],
       ...
     }
   }
   ```
   ✅ Nota: Ahora dice `"web"` en lugar de `"installed"`

3. Guárdalo como `oauth_credentials.json` en la raíz del proyecto

## Paso 3: Configurar en Render

### Opción A: Variable de Entorno (Recomendado)

1. Copia TODO el contenido del archivo `oauth_credentials.json`
2. Ve a Render Dashboard → Tu App → **Environment**
3. Añade estas variables:
   - **Key**: `OAUTH_CREDENTIALS_JSON`
   - **Value**: Pega el JSON completo
   - **Key**: `SECRET_KEY`
   - **Value**: Genera una clave secreta (puede ser cualquier string aleatorio largo)
     ```bash
     # Ejemplo para generar una clave:
     python3 -c "import os; print(os.urandom(24).hex())"
     ```
4. Guarda cambios y redeploy

### Opción B: Archivo (Solo para testing local)

Si solo quieres probar localmente, puedes dejar el archivo `oauth_credentials.json` en el proyecto, pero asegúrate de que está en `.gitignore`.

## Paso 4: Probar el Flujo

### En Local (http://localhost:5000)

1. Reinicia el servidor Flask (Ctrl+C y luego vuelve a ejecutar)
2. Abre el navegador en `http://localhost:5000`
3. Deberías ver el botón **"🔗 Conectar Google Drive"** en la esquina superior derecha
4. Click en el botón
5. Te redirige a Google para autorizar
6. Autoriza la aplicación
7. Te redirige de vuelta a localhost
8. El botón cambia a **"✓ Google Drive Conectado"**
9. Genera un artículo
10. Click en "Enviar a Google Drive"
11. Verifica que se guarda en tu Drive

### En Render (https://tu-app.onrender.com)

1. Asegúrate de haber configurado las variables de entorno
2. Deploy la app
3. Abre `https://tu-app.onrender.com`
4. Repite los pasos 3-11 de arriba

## Diferencias con Desktop OAuth

| Aspecto | Desktop OAuth (Anterior) | Web OAuth (Actual) |
|---------|-------------------------|-------------------|
| Tipo de Credencial | Desktop app | Web application |
| Redirect URI | `http://localhost:*` automático | URIs específicas configuradas |
| Almacenamiento | Archivo `token.json` | Sesión Flask |
| Multi-usuario | No (todos usan el mismo token) | Sí (cada usuario tiene su sesión) |
| Funciona en Render | ❌ No (no hay navegador) | ✅ Sí |

## Troubleshooting

**Error: "redirect_uri_mismatch"**
- Solución: Verifica que las redirect URIs en Google Cloud Console coincidan exactamente con las de tu app:
  - Local: `http://localhost:5000/oauth2callback`
  - Render: `https://TU-APP.onrender.com/oauth2callback`

**Error: "State not found in session"**
- Solución: Asegúrate de que `SECRET_KEY` está configurado en las variables de entorno

**El botón "Conectar" no aparece**
- Solución: Abre la consola del navegador (F12) y verifica si hay errores en JavaScript

**La sesión se pierde cada vez**
- Solución: En producción (Render), asegúrate de que `SECRET_KEY` es una variable de entorno permanente (no cambia entre deploys)
