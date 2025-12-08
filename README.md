# Redactor

**Redactor** es una herramienta avanzada de automatización de contenidos que utiliza Inteligencia Artificial (Google Gemini) para generar artículos optimizados para SEO de alta calidad.

Diseñada para flujos de trabajo profesionales, permite generar contenido desde una interfaz web o directamente desde **Google Sheets**, guardando los resultados automáticamente en **Google Drive**.

## ¿Por qué Redactor?

Generar contenido de calidad para SEO requiere tiempo y estructura. Esta herramienta automatiza el proceso emulando el flujo de trabajo de un redactor experto:

1.  **Planificación**: Analiza la intención de búsqueda y crea un esquema (H1, H2, H3).
2.  **Redacción**: Escribe el contenido completo siguiendo el esquema.
3.  **Revisión**: Una "segunda opinión" de la IA critica el borrador buscando mejoras.
4.  **Finalización**: Aplica las correcciones para entregar un texto pulido.

Todo esto sucede en segundos, permitiéndote escalar tu estrategia de contenidos sin sacrificar calidad.

## ¿Cómo funciona?

### 1. Entrada de Datos (Input)
Tienes dos formas de usar la herramienta:

*   **Desde la Web**: Ingresa un tema y un título sugerido en la interfaz visual.
*   **Desde Google Sheets**: Conecta tu hoja de cálculo. La herramienta detectará automáticamente las nuevas filas con "Palabra clave" y "Título" y las procesará en segundo plano (individualmente o por lotes).

### 2. Procesamiento Inteligente
El sistema utiliza los modelos más recientes de **Google Gemini** para ejecutar el ciclo de 4 fases (Planificar -> Redactar -> Revisar -> Pulir), asegurando que el contenido sea coherente, útil y optimizado.

### 3. Salida Automática (Output)
Olvídate de copiar y pegar.
*   **Google Drive**: Cada artículo generado se convierte automáticamente en un documento de Google Docs y se guarda en una carpeta específica ("redactor") en tu unidad de Drive conectada.
*   **Visualización Web**: También puedes ver y copiar el resultado HTML directamente desde la aplicación.

## Características Clave

*   **Integración Total**: Google Sheets → Redactor → Google Drive.
*   **Persistencia de Sesión**: Tu conexión con Google Drive se mantiene entre sesiones para que no tengas que loguearte cada vez.
*   **Modo Batch**: Procesa docenas de temas a la vez desde tu hoja de cálculo.
*   **Calidad SEO**: Prompts diseñados por expertos para cumplir con los principios E-E-A-T.

## Configuración Rápida

1.  **Requisitos**: Python 3.8+ y una API Key de Google Gemini.
2.  **Instalación**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Variables de Entorno**: Crea un archivo `.env` con:
    ```
    api_key=TU_API_KEY_DE_GEMINI
    SECRET_KEY=una_clave_segura
    DRIVE_FOLDER_ID=tu_id_de_carpeta_de_drive (opcional)
    ```
    **Nota**: El `DRIVE_FOLDER_ID` es opcional. Si lo configuras, los artículos se guardarán en esa carpeta específica de Google Drive en lugar de buscar/crear una carpeta llamada "redactor". Para obtener el ID de tu carpeta, copia el ID de la URL de Drive (ej: `https://drive.google.com/drive/folders/ID_AQUI`).
4.  **Ejecución**:
    ```bash
    python app.py
    ```

¡Empieza a escalar tu producción de contenidos hoy mismo!
