# Configuración de OAuth en Render (Producción)

## ⚠️ IMPORTANTE: Seguridad

**NUNCA subas `oauth_credentials.json` a GitHub**, aunque el repositorio sea privado. Ya está protegido en `.gitignore`.

## Cómo configurar en Render

### Paso 1: Obtener el contenido del archivo

En tu terminal local (donde tienes `oauth_credentials.json`):

```bash
cat oauth_credentials.json
```

Copia TODO el contenido (es un JSON que empieza con `{"installed":` o `{"web":`).

### Paso 2: Crear variable de entorno en Render

1. Ve a tu dashboard de Render: https://dashboard.render.com/
2. Selecciona tu aplicación web "redactor"
3. Ve a **Environment** en el menú lateral
4. Click en **Add Environment Variable**
5. Configura:
   - **Key**: `OAUTH_CREDENTIALS_JSON`
   - **Value**: Pega TODO el contenido del JSON que copiaste
6. Click **Save Changes**

### Paso 3: Redeploy (si es necesario)

Render debería hacer auto-deploy. Si no, haz un manual deploy.

---

## ⚠️ Problema con OAuth en Render (Sin Navegador)

**IMPORTANTE**: El flujo OAuth estándar requiere abrir un navegador para autorizar. Render no tiene navegador porque es un servidor.

### Solución Recomendada: Autorizar Localmente Primero

1. **Localmente**: 
   - Ejecuta la app en tu computadora
   - Haz clic en "Enviar a Google Drive"
   - Autoriza en el navegador
   - Esto creará `token.json`

2. **Subir token a Render**:
   - Opción A: Añade `token.json` como variable de entorno `OAUTH_TOKEN` (más seguro)
   - Opción B: Usa un volumen persistente en Render para guardar `token.json`

### Alternativa: Web Flow (Más Complejo)

Para producción en Render, deberías usar **Web Application OAuth** en lugar de Desktop App:

1. En Google Cloud Console, crea un nuevo OAuth Client ID
2. Tipo: **Web application**
3. Authorized redirect URIs: `https://tu-app.onrender.com/oauth2callback`
4. Esto permite que los usuarios autoricen desde el navegador directamente en Render

---

## Diferencia entre Desarrollo y Producción

| Aspecto | Desarrollo Local | Producción (Render) |
|---------|------------------|---------------------|
| Credenciales | Archivo `oauth_credentials.json` | Variable `OAUTH_CREDENTIALS_JSON` |
| Tipo OAuth | Desktop App | Web Application (recomendado) |
| Tokens | `token.json` guardado localmente | Variable de entorno o volumen persistente |
| Flujo OAuth | Abre navegador automáticamente | Requiere configuración especial |

---

## Recomendación Final

Para tu caso (aplicación personal), lo más sencillo es:

1. **Desarrollo**: Usa `oauth_credentials.json` localmente
2. **Producción**: 
   - Considera si realmente necesitas OAuth en Render
   - Si solo tú usarás la app, autoriza localmente y sube el `token.json` como variable de entorno
   - Si otros usuarios la usarán, necesitas migrar a Web Application OAuth

¿Quieres que te ayude a implementar alguna de estas opciones?
