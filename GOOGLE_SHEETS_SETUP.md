# Configuración del Script de Google Sheets

## Paso 1: Generar tu Token de API

1. Ve a https://redactor-e1sp.onrender.com/
2. Haz clic en **"🔗 Conectar Google Drive"** y autoriza la aplicación
3. Una vez conectado, verás la sección **"🔑 Token de API para Google Sheets"**
4. Haz clic en **"Generar Nuevo Token"**
5. **IMPORTANTE**: Copia el token inmediatamente (solo se muestra una vez)

## Paso 2: Actualizar tu Script de Google Sheets

Reemplaza tu script actual con el siguiente código actualizado:

```javascript
// ============================================
// CONFIGURACIÓN - PEGA TU TOKEN AQUÍ
// ============================================
const API_TOKEN = "PEGA_TU_TOKEN_AQUI"; // 👈 Reemplaza esto con tu token real
// ============================================

function onOpen() {
  SpreadsheetApp.getUi()
      .createMenu("Enviar")
      .addItem("Generar articulo de FILA SELECCIONADA automaticamente", "enviarFilaSeleccionada")
      .addItem("Generar articulos de TODAS LAS FILAS automaticamente", "enviarTodasLasFilas")
      .addToUi();
}

/**
 * Función para manejar la respuesta 401 específica de autenticación de Drive.
 * Muestra una alerta específica si el error es 401 y contiene el mensaje de Drive.
 * @param {GoogleAppsScript.URL_Fetch.HTTPResponse} response - La respuesta de UrlFetchApp.
 * @returns {boolean} - true si el error 401 fue manejado y se mostró la alerta, false en caso contrario.
 */
function manejarErrorAutenticacion(response) {
  const ui = SpreadsheetApp.getUi();
  const urlConexion = "https://redactor-e1sp.onrender.com/";

  if (response.getResponseCode() === 401) {
    try {
      const responseText = response.getContentText();
      const responseJson = JSON.parse(responseText);

      // Comprueba si el mensaje de error es el específico de autenticación
      if (responseJson.status === "error" &&
          (responseJson.message.includes("No estás autenticado") ||
           responseJson.message.includes("Invalid or expired API token"))) {
        ui.alert(
          "🚨 Error de Autenticación",
          `Tu token de API es inválido o expiró. Por favor:\n\n` +
          `1. Ve a ${urlConexion}\n` +
          `2. Conéctate con Google Drive\n` +
          `3. Genera un nuevo token\n` +
          `4. Actualiza el token en este script`,
          ui.ButtonSet.OK
        );
        return true; // Se manejó el error y la función principal DEBE detenerse.
      }
    } catch (e) {
      // Si falla el parseo, se logea, pero el script seguirá al manejo genérico.
      Logger.log("Error al parsear la respuesta 401: " + e.message);
    }
  }
  return false; // El error no fue un 401 de autenticación
}

/**
 * Envía la palabra clave y el título de la fila seleccionada a la URL de la API.
 */
function enviarFilaSeleccionada() {
  const url = "https://redactor-e1sp.onrender.com/";
  const hoja = SpreadsheetApp.getActiveSheet();
  const rango = hoja.getActiveRange();
  const fila = rango.getRow();
  const ui = SpreadsheetApp.getUi();

  // Verificar que el token esté configurado
  if (!API_TOKEN || API_TOKEN === "PEGA_TU_TOKEN_AQUI") {
    ui.alert(
      "⚠️ Token No Configurado",
      "Por favor configura tu token de API en la parte superior del script.\n\n" +
      "1. Ve a https://redactor-e1sp.onrender.com/\n" +
      "2. Genera un token\n" +
      "3. Pégalo en la variable API_TOKEN",
      ui.ButtonSet.OK
    );
    return;
  }

  if (fila === 1) {
    ui.alert("Selecciona una fila con datos.");
    return;
  }

  const palabra = hoja.getRange(fila, 1).getValue();
  const titulo = hoja.getRange(fila, 2).getValue();

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      headers: {
        "X-API-Token": API_TOKEN  // 👈 Enviamos el token en el header
      },
      payload: JSON.stringify({
        palabra_clave: palabra,
        titulo_sugerido: titulo
      }),
      muteHttpExceptions: true
    });

    // 🛑 Si el error es 401 de autenticación, se muestra la alerta y la función se detiene aquí.
    if (manejarErrorAutenticacion(response)) {
      return;
    }

    // Si la respuesta es 200 (OK)
    if (response.getResponseCode() >= 200 && response.getResponseCode() < 300) {
       ui.alert("Fila enviada correctamente.");
    } else {
       // Manejo de otros errores HTTP (400, 404, 500, etc.)
       let errorDetails = `Código: ${response.getResponseCode()}`;
       try {
           const responseJson = JSON.parse(response.getContentText());
           if (responseJson.message) {
               errorDetails = responseJson.message;
           }
       } catch (e) {
           // Si no se puede parsear, usamos el código
       }
       ui.alert(`Error al enviar la fila: ${errorDetails}`);
    }

  } catch (error) {
    // Esto captura errores de red o errores de Google Apps Script (NO errores HTTP)
    ui.alert(`Error de red o desconocido: ${error.message}`);
  }
}

/**
 * Envía los datos de todas las filas a la URL de la API en una sola petición.
 */
function enviarTodasLasFilas() {
  const url = "https://redactor-e1sp.onrender.com/";
  const hoja = SpreadsheetApp.getActiveSheet();
  const ultimaFila = hoja.getLastRow();
  const ui = SpreadsheetApp.getUi();

  // Verificar que el token esté configurado
  if (!API_TOKEN || API_TOKEN === "PEGA_TU_TOKEN_AQUI") {
    ui.alert(
      "⚠️ Token No Configurado",
      "Por favor configura tu token de API en la parte superior del script.\n\n" +
      "1. Ve a https://redactor-e1sp.onrender.com/\n" +
      "2. Genera un token\n" +
      "3. Pégalo en la variable API_TOKEN",
      ui.ButtonSet.OK
    );
    return;
  }

  if (ultimaFila <= 1) {
    ui.alert("No hay datos para enviar.");
    return;
  }

  // Confirmación antes de enviar todas las filas
  const respuesta = ui.alert(
    "Confirmar envío",
    `¿Deseas enviar ${ultimaFila - 1} fila(s) a Redactor?`,
    ui.ButtonSet.YES_NO
  );
  if (respuesta !== ui.Button.YES) {
    return;
  }

  // Array para almacenar todas las filas
  const filas = [];
  // Recorrer desde la fila 2 (saltando la cabecera) hasta la última fila
  for (let i = 2; i <= ultimaFila; i++) {
    const palabra = hoja.getRange(i, 1).getValue();
    const titulo = hoja.getRange(i, 2).getValue();
    // Verificar que la fila tenga datos
    if (palabra && titulo) {
      filas.push({
        palabra_clave: palabra,
        titulo_sugerido: titulo
      });
    }
  }

  if (filas.length === 0) {
    ui.alert("No hay filas válidas para enviar.");
    return;
  }

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      headers: {
        "X-API-Token": API_TOKEN  // 👈 Enviamos el token en el header
      },
      payload: JSON.stringify({
        filas: filas
      }),
      muteHttpExceptions: true
    });

    // 🛑 Si el error es 401 de autenticación, se muestra la alerta y la función se detiene aquí.
    if (manejarErrorAutenticacion(response)) {
      return;
    }

    // Si la respuesta es 200 (OK)
    if (response.getResponseCode() >= 200 && response.getResponseCode() < 300) {
       ui.alert(`${filas.length} fila(s) enviada(s) correctamente.`);
    } else {
       // Manejo de otros errores HTTP (400, 404, 500, etc.)
       let errorDetails = `Código: ${response.getResponseCode()}`;
       try {
           const responseJson = JSON.parse(response.getContentText());
           if (responseJson.message) {
               errorDetails = responseJson.message;
           }
       } catch (e) {
           // Si no se puede parsear, usamos el código
       }
       ui.alert(`Error al enviar las filas: ${errorDetails}`);
    }

  } catch (error) {
    // Esto captura errores de red o errores de Google Apps Script (NO errores HTTP)
    ui.alert(`Error de red o desconocido: ${error.message}`);
  }
}
```

## Paso 3: Guardar y Probar

1. Pega el script actualizado en tu Google Sheet (Extensiones → Apps Script)
2. **IMPORTANTE**: Reemplaza `"PEGA_TU_TOKEN_AQUI"` con tu token real
3. Guarda el script
4. Recarga tu Google Sheet
5. Prueba enviando una fila o todas las filas

## Seguridad

- ⚠️ **NO compartas tu token con nadie**
- ⚠️ Si crees que tu token fue comprometido, genera uno nuevo desde la web
- Cada usuario debe tener su propio token personal
- Los tokens están vinculados a tu cuenta de Google Drive

## Solución de Problemas

### Error: "Invalid or expired API token"
- Tu token expiró o es inválido
- Genera un nuevo token desde la web

### Error: "Token No Configurado"
- No has pegado tu token en el script
- Asegúrate de reemplazar `"PEGA_TU_TOKEN_AQUI"` con tu token real

### Los artículos no aparecen en mi Drive
- Verifica que estés conectado a la web con la misma cuenta de Google
- El token está vinculado a tu cuenta específica

## Ventajas del Sistema de Tokens

✅ Cada usuario tiene sus propias credenciales aisladas
✅ Los artículos se guardan en el Drive personal de cada usuario
✅ Más seguro que compartir sesiones
✅ Puedes revocar tokens en cualquier momento
