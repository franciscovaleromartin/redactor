# Redactor SIDN

Aplicación web para generar artículos optimizados para SEO usando un proceso de 4 fases con GPT.

## Despliegue en Render

### Pasos para desplegar:

1. **Sube el código a GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin <tu-repositorio-url>
   git push -u origin main
   ```

2. **Configura en Render:**
   - Ve a [Render Dashboard](https://dashboard.render.com/)
   - Click en "New +" → "Web Service"
   - Conecta tu repositorio de GitHub
   - Render detectará automáticamente el `render.yaml`
   
3. **Configura la variable de entorno:**
   - En el dashboard de Render, ve a "Environment"
   - Añade la variable: `api_key` con tu **Google API Key** (de Google AI Studio)
   
4. **Despliega:**
   - Render desplegará automáticamente tu aplicación
   - Recibirás una URL como: `https://redactor-sidn.onrender.com`

## Variables de entorno necesarias

- `api_key`: Tu Google API Key (consíguela en [Google AI Studio](https://aistudio.google.com/))

## Desarrollo local

1. Crea un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Crea un archivo `.env` con tu API key:
   ```
   api_key=tu-google-api-key-aqui
   ```

4. Ejecuta la aplicación:
   ```bash
   python app.py
   ```

5. Abre tu navegador en: `http://localhost:5000`
