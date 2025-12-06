import os
import gc
import json
from flask import Flask, request, jsonify, render_template, stream_with_context, Response, session, redirect, url_for
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Allow OAuth scope to change (e.g. adding metadata access) without crashing
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


app = Flask(__name__)

# Configure Flask session
app.secret_key = os.environ.get('SECRET_KEY', 'redactor_dev_secret_key_static_fallback')

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
''' "models/gemini-3.0-pro",        # 3.0 Pro Para produccion '''
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

    ''' Para produccion: Este prompt configura la "personalidad" de la IA. Usamos mayúsculas para directrices inquebrantables.
# ROLE
You are an Elite SEO Content Strategist and Senior Copywriter specialized in the Spanish market. Your writing style is authoritative, engaging, and indistinguishable from a human expert.

# CORE DIRECTIVES
1. **E-E-A-T PRINCIPLE**: Demonstrate Experience, Expertise, Authoritativeness, and Trustworthiness in every output.
2. **LANGUAGE**: All content generated must be in **Native European Spanish** (unless specified otherwise).
3. **USER-CENTRIC**: Prioritize the user's search intent over keyword stuffing. The content must solve problems.
4. **FORMAT**: You are a master of HTML structure. Your code is clean, semantic, and accessible.
    '''
    
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
SCOPES = ['https://www.googleapis.com/auth/drive']
OAUTH_CREDENTIALS_FILE = 'oauth_credentials.json'

def get_oauth_config():
    """Load OAuth configuration from file or environment variable."""
    if os.path.exists(OAUTH_CREDENTIALS_FILE):
        with open(OAUTH_CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    elif os.environ.get('OAUTH_CREDENTIALS_JSON'):
        return json.loads(os.environ.get('OAUTH_CREDENTIALS_JSON'))
    else:
        raise Exception("OAuth credentials not found. Please provide 'oauth_credentials.json' file or set OAUTH_CREDENTIALS_JSON environment variable.")

def credentials_to_dict(credentials):
    """Convert credentials to a dictionary for session storage."""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_drive_service():
    """Get authenticated Google Drive service using OAuth 2.0 from session."""
    if 'credentials' not in session:
        raise Exception("Not authenticated. Please authorize first by visiting /authorize")
    
    # Load credentials from session
    creds = Credentials(**session['credentials'])
    
    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session['credentials'] = credentials_to_dict(creds)
    
    service = build('drive', 'v3', credentials=creds)
    return service

def find_or_create_folder(service, folder_name='redactor'):
    """Find or create a folder in Google Drive by name."""
    # Search for folder by name (case-insensitive-ish: check for 'redactor' and 'Redactor')
    # Removed 'root' in parents to search the entire drive, not just root
    query = f"(name='{folder_name}' or name='{folder_name.capitalize()}') and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = results.get('files', [])
    
    if folders:
        # Folder exists, return the first match
        print(f"Found existing folder: {folders[0]['name']} (ID: {folders[0]['id']})")
        return folders[0]['id']
    else:
        # Create the folder
        print(f"Creating new folder: {folder_name}")
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

@app.route('/authorize')
def authorize():
    """Initiate OAuth 2.0 authorization flow."""
    try:
        # Get OAuth config
        oauth_config = get_oauth_config()
        
        # Determine redirect URI based on environment
        if request.host.startswith('localhost') or request.host.startswith('127.0.0.1'):
            redirect_uri = url_for('oauth2callback', _external=True, _scheme='http')
        else:
            redirect_uri = url_for('oauth2callback', _external=True, _scheme='https')
        
        # Create flow instance
        flow = Flow.from_client_config(
            oauth_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force to show consent screen to get refresh token
        )
        
        # Store state in session for CSRF protection
        session['state'] = state
        
        return redirect(authorization_url)
        
    except Exception as e:
        return jsonify({"error": f"Authorization error: {str(e)}"}), 500

@app.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth 2.0 callback from Google."""
    try:
        # Verify state to prevent CSRF
        state = session.get('state')
        if not state:
            return jsonify({"error": "State not found in session"}), 400
        
        # Get OAuth config
        oauth_config = get_oauth_config()
        
        # Determine redirect URI (must match the one used in /authorize)
        if request.host.startswith('localhost') or request.host.startswith('127.0.0.1'):
            redirect_uri = url_for('oauth2callback', _external=True, _scheme='http')
        else:
            redirect_uri = url_for('oauth2callback', _external=True, _scheme='https')
        
        # Create flow instance
        flow = Flow.from_client_config(
            oauth_config,
            scopes=SCOPES,
            state=state,
            redirect_uri=redirect_uri
        )
        
        # Exchange authorization code for tokens
        flow.fetch_token(authorization_response=request.url)
        
        # Store credentials in session
        credentials = flow.credentials
        session['credentials'] = credentials_to_dict(credentials)
        
        # Redirect back to home page
        return redirect('/')
        
    except Exception as e:
        return jsonify({"error": f"Callback error: {str(e)}"}), 500

@app.route('/auth-status')
def auth_status():
    """Check if user is authenticated with Google Drive."""
    try:
        if 'credentials' not in session:
            return jsonify({"authenticated": False})
        
        # Check if credentials are valid
        creds = Credentials(**session['credentials'])
        
        # Try to refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                session['credentials'] = credentials_to_dict(creds)
            except:
                # Refresh failed, need to re-authorize
                session.pop('credentials', None)
                return jsonify({"authenticated": False})
        
        return jsonify({"authenticated": True})
        
    except Exception as e:
        return jsonify({"authenticated": False, "error": str(e)})

@app.route('/disconnect-drive', methods=['POST'])
def disconnect_drive():
    """Disconnect user from Google Drive by clearing session credentials."""
    try:
        if 'credentials' in session:
            session.pop('credentials', None)
            return jsonify({"success": True, "message": "Disconnected from Google Drive"})
        else:
            return jsonify({"success": False, "message": "Not connected"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

DRAFT_FILE = 'latest_draft.json'

@app.route('/', methods=['GET', 'POST'])
def index():
    topic = ""
    title = ""
    
    if request.method == 'POST':
        # Handle data from Google Sheets or external sources
        if request.is_json:
            try:
                data = request.json
                # Extract and map fields (Sheets sends 'palabra_clave' and 'titulo_sugerido')
                draft_data = {
                    'topic': data.get('palabra_clave', ''),
                    'title': data.get('titulo_sugerido', '')
                }
                
                # Save to file for persistence
                with open(DRAFT_FILE, 'w') as f:
                    json.dump(draft_data, f)
                
                return jsonify({"status": "received", "message": "Datos guardados correctamente"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        return jsonify({"status": "error", "message": "JSON required"}), 400
            
    # GET request: Load the latest draft if it exists
    if os.path.exists(DRAFT_FILE):
        try:
            with open(DRAFT_FILE, 'r') as f:
                draft_data = json.load(f)
                topic = draft_data.get('topic', '')
                title = draft_data.get('title', '')
        except Exception as e:
            print(f"Error reading draft file: {e}")
    
    return render_template('index.html', topic=topic, title=title)

@app.route('/upload-to-drive', methods=['POST'])
def upload_to_drive():
    try:
        data = request.json
        content = data.get('content')
        title = data.get('title', 'Articulo Generado')
        
        if not content:
            return jsonify({"error": "No content provided"}), 400

        # Get authenticated Drive service with OAuth 2.0
        service = get_drive_service()
        
        # Find or create 'redactor' folder
        folder_id = find_or_create_folder(service, 'redactor')
        
        # Create file metadata
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document',  # Convert to Google Doc
            'parents': [folder_id]  # Always save to 'redactor' folder
        }
        
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

            ''' Para produccion: Aquí usamos etiquetas como <topic> para encapsular las variables. Esto reduce alucinaciones.
# TASK
Create a high-level **SEO Content Brief and Outline**. Do NOT write the article yet. Focus on structure and strategy.

# INPUT DATA
<topic>
{topic}
</topic>

<suggested_title>
{title}
</suggested_title>

# REQUIREMENTS
1. **Search Intent Analysis**: Define if the user wants to Buy, Know, or Go.
2. **Semantic Entities**: List 5-10 LSI keywords and entities related to the topic (not just synonyms, but contextual concepts).
3. **SERP Feature Targeting**: Identify one section designed to capture a "Featured Snippet" (e.g., a direct definition or list).
4. **Structural Hierarchy**:
   - Create a deep structure using H2 and H3 tags.
   - Under each heading, provide 3 bullet points on EXACTLY what to discuss.
   - Include specific examples or analogies to be used.

# OUTPUT FORMAT
Return the plan in Markdown. Ensure the H1 matches the suggested title.
            
            '''


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

            ''' Pra produccion: Instrucciones tecnicas precisas para evitar el "bloque de texto". Se enfatiza la legibilidad visual.
# TASK
Write the full comprehensive article based STRICTLY on the provided outline.

# INPUT CONTEXT
<outline>
{plan}
</outline>

# WRITING GUIDELINES
- **Voice & Tone**: Professional yet conversational. Avoid passive voice. Use rhetorical questions to engage.
- **Visual Rhythm**:
  - Max 3 lines per paragraph.
  - Use `<strong>` tags to highlight key insights (scannability).
  - Use `<ul>` or `<ol>` lists every 300 words approximately.
- **Semantic SEO**: Naturally weave in the entities defined in the outline.

# TECHNICAL CONSTRAINTS
- Output format: **HTML Body only**.
- Use tags: `<h1>`, `<h2>`, `<h3>`, `<p>`, `<ul>`, `<li>`, `<strong>`, `<blockquote>`.
- **FORBIDDEN**: Do NOT use `<html>`, `<head>`, or `<body>` tags. Do NOT use Markdown formatting for the content, use real HTML tags.
- **Language**: Spanish.

# EXECUTE
Write the high-quality draft now.
            '''

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

            ''' Para produccion: Aqui cambiamos la "temperatura" del prompt. Le pedimos que sea crítico, no amable. Usamos listas para estructurar la crítica.
# ROLE
Act as a Ruthless Editor-in-Chief. Your job is to destroy low-quality content and elevate it to premium standards.

# TASK
Audit the following draft for weaknesses.

<draft>
{truncated_draft}
</draft>

# AUDIT CRITERIA
Analyze the text based on these 4 pillars:
1. **FLUFF REMOVAL**: Identify sentences that add zero value or are repetitive.
2. **AUTHORITY CHECK**: Flag vague claims (e.g., "many people say") that need data or specific examples.
3. **FLOW & ENGAGEMENT**: Point out robotic transitions or boring introductions.
4. **HTML INTEGRITY**: Check if the HTML structure is logical (hierarchy).

# OUTPUT
Provide a bulleted list of SPECIFIC instructions on how to fix these issues. Do not rewrite the text yet. Be direct and critical.
            '''

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
No incluyas imágenes.

Artículo original:
{truncated_draft}

Revisión:
{critique}"""

            ''' Para produccion: El objetivo aqui es la limpieza tecnica absoluta. Instruimos al modelo para que devuelva "Raw String" para que tu software no se rompa con bloques de código markdown.
# TASK
Synthesize the final, polished version of the article by applying the Editor's critique to the Original Draft.

# INPUTS
<original_draft>
{truncated_draft}
</original_draft>

<critique_notes>
{critique}
</critique_notes>

# FINAL POLISHING RULES
1. **Apply Changes**: Rewrite weak sections based on the critique.
2. **Refine HTML**: Ensure all tags are properly closed and nested.
3. **Check Tone**: Ensure the final Spanish sounds native and fluent, not translated.
4. **Final Check**: Remove any concluding remarks like "In conclusion" if they feel generic.

# OUTPUT FORMAT
- Return **ONLY the raw HTML string**.
- **CRITICAL**: Do NOT enclose the output in markdown code blocks (like ```html ... ```).
- Start directly with the `<h1>` tag and end with the final tag.
            '''


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
