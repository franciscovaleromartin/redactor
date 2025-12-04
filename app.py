import os
import gc
import json
from flask import Flask, request, jsonify, render_template, stream_with_context, Response
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import pickle
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Gemini
api_key = os.environ.get("api_key")
if not api_key:
    print("WARNING: 'api_key' environment variable not found. Please set it or create a .env file.")

if api_key:
    genai.configure(api_key=api_key)
    try:
        print("Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

# Try models in order of preference until one works
AVAILABLE_MODELS = [
    "models/gemini-2.0-flash",      # New stable
    "models/gemini-2.0-flash-exp",  # Experimental
    "models/gemini-2.5-flash",      # Latest
    "models/gemini-2.0-pro-exp",    # Pro Experimental
]

def get_working_model():
    """Find the first working model from the available list."""
    import time
    for model_name in AVAILABLE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            # Test with a simple prompt
            test_response = model.generate_content("Hi", generation_config=genai.types.GenerationConfig(max_output_tokens=10))
            print(f"✓ Using model: {model_name}")
            return model_name
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                print(f"⚠ Model {model_name} rate limited, trying next...")
            elif "404" in error_str:
                print(f"✗ Model {model_name} not found")
            else:
                print(f"✗ Model {model_name} error: {e}")
            continue
    raise Exception("No working Gemini models found. Please check your API key or wait for rate limits to reset.")

# Determine working model at startup
WORKING_MODEL = None
if api_key:
    try:
        WORKING_MODEL = get_working_model()
    except Exception as e:
        print(f"ERROR: {e}")

def generate_completion(prompt, model_name=None, max_tokens=None, stream=False):
    """Helper function to call Google Gemini API."""
    if model_name is None:
        model_name = WORKING_MODEL
    
    if not model_name:
        raise Exception("No working Gemini model available")
    
    model = genai.GenerativeModel(model_name)
    
    # Configure generation config
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=0.7
    )

    # System instruction prepended to prompt
    system_instruction = "Eres un redactor profesional especializado en SEO y copywriting. Escribe contenido claro, estructurado y optimizado para buscadores en español.\n\n"
    
    full_prompt = system_instruction + prompt

    # Configure safety settings to avoid blocking content
    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE"
        },
    ]

    response = model.generate_content(
        full_prompt,
        generation_config=generation_config,
        safety_settings=safety_settings,
        stream=stream
    )
    
    if stream:
        return response
    
    # Check if response was blocked or incomplete
    if not response.candidates:
        raise Exception("No candidates returned by the model.")

    candidate = response.candidates[0]
    finish_reason = candidate.finish_reason
    
    # Debug logging
    print(f"Generation finish_reason: {finish_reason}")
    
    if not candidate.content.parts:
        # If no content parts, it's a hard failure
        if finish_reason == 3: # SAFETY
            raise Exception(f"Content blocked by safety filters. Reason: {finish_reason}")
        elif finish_reason == 2: # MAX_TOKENS
             raise Exception(f"Content truncated (Max Tokens) and empty. Reason: {finish_reason}")
        else:
            raise Exception(f"Generation failed with no content. Reason: {finish_reason}")

    content = response.text
    
    # If MAX_TOKENS (2) but we have content, we might want to warn but proceed
    if finish_reason == 2:
        print("WARNING: Generation truncated due to max tokens.")

    # Clean up response object to free memory
    del response
    gc.collect()
    return content

# OAuth 2.0 Configuration
SCOPES = ['https://www.googleapis.com/auth/drive.file']
OAUTH_CREDENTIALS_FILE = 'oauth_credentials.json'
TOKEN_FILE = 'token.json'

def get_drive_service():
    """Get authenticated Google Drive service using OAuth 2.0."""
    creds = None
    
    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh the token
            creds.refresh(Request())
        else:
            # Start OAuth flow
            # Try to load from file first, then from environment variable
            if os.path.exists(OAUTH_CREDENTIALS_FILE):
                flow = InstalledAppFlow.from_client_secrets_file(
                    OAUTH_CREDENTIALS_FILE, SCOPES)
            elif os.environ.get('OAUTH_CREDENTIALS_JSON'):
                # Load from environment variable (for Render/production)
                import json
                creds_info = json.loads(os.environ.get('OAUTH_CREDENTIALS_JSON'))
                flow = InstalledAppFlow.from_client_config(creds_info, SCOPES)
            else:
                raise Exception(f"OAuth credentials not found. Please provide '{OAUTH_CREDENTIALS_FILE}' file or set OAUTH_CREDENTIALS_JSON environment variable.")
            
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    service = build('drive', 'v3', credentials=creds)
    return service

@app.route('/', methods=['GET', 'POST'])
def index():
    topic = ""
    title = ""
    
    if request.method == 'POST':
        if request.is_json:
            data = request.json
            topic = data.get('palabra_clave', '')
            title = data.get('titulo_sugerido', '')
    
    return render_template('index.html', topic=topic, title=title)

@app.route('/upload-to-drive', methods=['POST'])
def upload_to_drive():
    try:
        data = request.json
        content = data.get('content')
        title = data.get('title', 'Articulo Generado')
        folder_id = data.get('folder_id', None)  # Optional: specify target folder
        
        if not content:
            return jsonify({"error": "No content provided"}), 400

        # Get authenticated Drive service with OAuth 2.0
        service = get_drive_service()
        
        # Create file metadata
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'  # Convert to Google Doc
        }
        
        # Add parent folder if specified
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # Create media
        # Wrap the HTML content in a basic HTML structure for Drive to convert it properly
        full_html = f"<html><body>{content}</body></html>"
        media = MediaIoBaseUpload(io.BytesIO(full_html.encode('utf-8')),
                                  mimetype='text/html',
                                  resumable=True)
        
        # Upload file
        file = service.files().create(body=file_metadata,
                                      media_body=media,
                                      fields='id, webViewLink').execute()
                                      
        return jsonify({
            "success": True, 
            "fileId": file.get('id'), 
            "link": file.get('webViewLink')
        })
        
    except Exception as e:
        print(f"Drive Upload Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/debug-drive', methods=['GET'])
def debug_drive():
    try:
        # Get authenticated Drive service with OAuth 2.0
        service = get_drive_service()
        
        # Check Quota and User Info
        about = service.about().get(fields="storageQuota,user").execute()
        
        # Check if token file exists
        token_status = "Token exists" if os.path.exists(TOKEN_FILE) else "No token found"
        oauth_creds_status = "OAuth credentials exist" if os.path.exists(OAUTH_CREDENTIALS_FILE) else "OAuth credentials not found"

        return jsonify({
            "user": about.get('user'),
            "quota": about.get('storageQuota'),
            "token_status": token_status,
            "oauth_credentials_status": oauth_creds_status
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate_article():
    gc.collect()
    data = request.json
    topic = data.get('topic')
    title = data.get('title')

    if not topic:
        return jsonify({"error": "Se requiere un tema (topic)."}), 400

    def generate_stream():
        try:
            # Phase 1: Planificación
            yield json.dumps({"status": "phase_1", "message": "Generando esquema SEO..."}) + "\n"
            
            prompt_phase_1 = f"""Genera un esquema detallado para un artículo optimizado para SEO sobre: {topic}.
Título sugerido: {title}
Incluye:
– Intención de búsqueda.
– Palabras clave principales y secundarias.
– Estructura H1/H2/H3 muy específica.
– Puntos clave que deben cubrirse en cada sección.
– Ejemplos concretos para mejorar calidad.
No escribas el contenido. Solo el plan."""

            plan = generate_completion(prompt_phase_1, max_tokens=800)
            if not plan:
                yield json.dumps({"error": "Error en Fase 1: No se pudo generar el plan"}) + "\n"
                return
                
            yield json.dumps({"status": "phase_1_done", "data": plan}) + "\n"
            del prompt_phase_1
            gc.collect()

            # Phase 2: Redacción
            yield json.dumps({"status": "phase_2", "message": "Redactando borrador..."}) + "\n"
            
            prompt_phase_2 = f"""Usa exclusivamente el siguiente esquema para redactar el artículo.
No añadas nuevas secciones.
Mantén claridad, precisión y evita relleno.
Incluye datos verificables o neutrales cuando proceda.
Aplica densidad de palabra clave moderada.
No repitas ideas con sinónimos.
Aquí tienes el esquema:
{plan}

Escribe el artículo completo en formato HTML (usa etiquetas h1, h2, p, ul, li, etc. pero sin html/body tags)."""

            # Stream Phase 2 content
            stream = generate_completion(prompt_phase_2, max_tokens=1200, stream=True)
            if not stream:
                yield json.dumps({"error": "Error en Fase 2: No se pudo iniciar la redacción"}) + "\n"
                return

            draft = ""
            for chunk in stream:
                # Check if chunk has valid content
                if hasattr(chunk, 'text') and chunk.text:
                    content_chunk = chunk.text
                    draft += content_chunk
                    yield json.dumps({"status": "phase_2_stream", "chunk": content_chunk}) + "\n"
            
            if not draft:
                yield json.dumps({"error": "Error en Fase 2: Borrador vacío"}) + "\n"
                return

            yield json.dumps({"status": "phase_2_done", "data": "Borrador completado"}) + "\n"
            del prompt_phase_2
            
            # Keep-alive during GC
            yield json.dumps({"status": "keep_alive", "message": "Procesando..."}) + "\n"
            gc.collect()

            # Phase 3: Revisión
            yield json.dumps({"status": "phase_3", "message": "Revisando contenido..."}) + "\n"
            print("Iniciando Fase 3...") # Debug log
            
            # Truncate draft to avoid token limits (approx 12000 chars ~ 3000 tokens)
            truncated_draft = draft[:12000] 
            if len(draft) > 12000:
                print("Aviso: Borrador truncado para Fase 3")
            
            prompt_phase_3 = f"""Evalúa este artículo.
Identifica:
– frases redundantes
– afirmaciones débiles
– repeticiones innecesarias
– oportunidades de mayor claridad
– sobreoptimización SEO
Sugiere correcciones concretas sin reescribir todo el texto.
Aquí está el artículo:
{truncated_draft}"""

            critique = generate_completion(prompt_phase_3, max_tokens=800)
            if not critique:
                print("Fallo en Fase 3: Crítica vacía") # Debug log
                yield json.dumps({"error": "Error en Fase 3: No se pudo generar la crítica"}) + "\n"
                return

            yield json.dumps({"status": "phase_3_done", "data": critique}) + "\n"
            del prompt_phase_3
            
            # Keep-alive during GC
            yield json.dumps({"status": "keep_alive", "message": "Procesando..."}) + "\n"
            gc.collect()

            # Phase 4: Finalización
            yield json.dumps({"status": "phase_4", "message": "Aplicando mejoras finales..."}) + "\n"
            print("Iniciando Fase 4...") # Debug log
            
            prompt_phase_4 = f"""Teniendo en cuenta el siguiente artículo y la revisión crítica, genera la versión final y pulida del artículo.
Aplica las correcciones sugeridas.
Devuelve SOLO el código HTML del artículo final (sin markdown ```html, solo el contenido).

Artículo original:
{truncated_draft}

Revisión:
{critique}"""

            # Stream Phase 4 content
            # Stream Phase 4 content
            stream_final = generate_completion(prompt_phase_4, max_tokens=1500, stream=True)
            if not stream_final:
                yield json.dumps({"error": "Error en Fase 4: No se pudo iniciar la versión final"}) + "\n"
                return

            final_article = ""
            for chunk in stream_final:
                # Check if chunk has valid content
                if hasattr(chunk, 'text') and chunk.text:
                    content_chunk = chunk.text
                    final_article += content_chunk
                    yield json.dumps({"status": "phase_4_stream", "chunk": content_chunk}) + "\n"

            if not final_article:
                 yield json.dumps({"error": "Error en Fase 4: El artículo final se generó vacío."}) + "\n"
                 return

            # Cleanup
            final_article = final_article.replace("```html", "").replace("```", "")
            del prompt_phase_4, critique, draft, plan, truncated_draft
            gc.collect()

            yield json.dumps({"status": "complete", "final_article": final_article}) + "\n"
            
        except Exception as e:
            print(f"Excepción general en generate_stream: {e}")
            yield json.dumps({"error": f"Error inesperado: {str(e)}"}) + "\n"

    return Response(stream_with_context(generate_stream()), mimetype='application/json')

if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5000))
    serve(app, host='0.0.0.0', port=port)
