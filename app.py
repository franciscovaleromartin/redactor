import os
import gc
import json
import threading
import time
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
    "models/gemini-3.0-pro",        # 3.0 Pro Para produccion - PRIMERA PREFERENCIA
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

# Determine working model at startup (MOVED TO LAZY LOAD)
WORKING_MODEL = None
# We no longer check strictly at startup to avoid "Time Out" during Render deploy
# if api_key:
#     try:
#         WORKING_MODEL = get_working_model()
#     except Exception as e:
#         print(f"ERROR: {e}")

def generate_completion(prompt, model_name=None, max_tokens=None, stream=False):
    """Helper function to call Google Gemini API."""
    global WORKING_MODEL
    
    if model_name is None:
        if not WORKING_MODEL:
            try:
                print("Lazy loading: Checking for working model...")
                WORKING_MODEL = get_working_model()
            except Exception as e:
                print(f"Error initializing model: {e}")
                
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
TOKEN_FILE = 'token.json'  # File to store user credentials

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

def get_drive_service(creds_dict=None):
    """Get authenticated Google Drive service using OAuth 2.0.
    
    Args:
        creds_dict (dict, optional): Credentials dictionary. If None, tries to get from session or file.
    """
    if creds_dict is None:
        if 'credentials' in session:
            creds_dict = session['credentials']
        elif os.path.exists(TOKEN_FILE):
            # Fallback to local token file
            try:
                with open(TOKEN_FILE, 'r') as f:
                    creds_dict = json.load(f)
            except Exception as e:
                print(f"Error reading token file: {e}")
                
        if not creds_dict:
            raise Exception("Not authenticated. Please authorize first by visiting /authorize")
    
    # Load credentials
    creds = Credentials(**creds_dict)
    
    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Update storage with refreshed token
            new_creds_dict = credentials_to_dict(creds)
            
            # Update session if available
            if request and hasattr(session, 'update'): 
                # Check if we are in a request context
                try:
                    session['credentials'] = new_creds_dict
                except RuntimeError:
                    pass # Not in request context

            # Update file
            with open(TOKEN_FILE, 'w') as f:
                json.dump(new_creds_dict, f)
                
            creds_dict = new_creds_dict
        except Exception as e:
            print(f"Error refreshing token: {e}")
            raise Exception("Authentication expired. Please re-login.")
    
    service = build('drive', 'v3', credentials=creds)
    return service

def find_or_create_folder(service, folder_name='redactor'):
    """Find or create a folder in Google Drive by name."""
    # Search for folder by name (case-insensitive-ish: check for 'redactor' and 'Redactor')
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

def save_article_to_drive(title, content, service=None, folder_name='redactor'):
    """
    Saves an article content to Google Drive.
    
    Args:
        title (str): Title of the article
        content (str): HTML content of the article
        service: Google Drive service instance (optional, creates one if None)
        folder_name (str): Target folder name
        
    Returns:
        dict: File metadata (id, link)
    """
    if not service:
        service = get_drive_service()
        
    # Find or create folder
    folder_id = find_or_create_folder(service, folder_name)
    
    # Create file metadata
    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.document',  # Convert to Google Doc
        'parents': [folder_id]
    }
    
    # Create media
    full_html = f"<html><body>{content}</body></html>"
    media = MediaIoBaseUpload(io.BytesIO(full_html.encode('utf-8')),
                                mimetype='text/html',
                                resumable=True)
    
    # Upload file
    file = service.files().create(body=file_metadata,
                                    media_body=media,
                                    fields='id, webViewLink').execute()
    return file

def generate_article_logic(topic, title, yield_json=True):
    """
    Core generation logic.
    
    Args:
        topic (str): Topic to write about.
        title (str): Suggested title.
        yield_json (bool): If True, yields JSON strings for SSE. If False, yields plain updates and finally the HTML.
        
    Yields:
        str: JSON strings or internal status/content.
    """
    try:
        # Phase 1: Planificación
        if yield_json: yield json.dumps({"status": "phase_1", "message": "Generando esquema SEO..."}) + "\n"
        
        prompt_phase_1 = f"""Generate a detailed and SEO-optimized outline for an article about: **{topic}**
Suggested title: **{title}**

Your output must include:

- **Search intent** of the user.
- **Primary and secondary keywords**.
- A highly specific **H1 / H2 / H3 structure**.
- **Key points** to be covered in every section.
- **Concrete examples** that enhance clarity and depth.

Do *not* write the article.
Produce only the complete outline."""

        plan = generate_completion(prompt_phase_1, max_tokens=800)
        if not plan:
            if yield_json: yield json.dumps({"error": "Error en Fase 1: No se pudo generar el plan"}) + "\n"
            return
            
        if yield_json: yield json.dumps({"status": "phase_1_done", "data": plan}) + "\n"
        del prompt_phase_1
        gc.collect()

        # Phase 2: Redacción
        if yield_json: yield json.dumps({"status": "phase_2", "message": "Redactando borrador..."}) + "\n"
        
        prompt_phase_2 = f"""Write the full article **exclusively following this outline**:

{plan}

Requirements:

- Do not add new sections.
- Maintain clarity, precision, and zero filler content.
- Include verifiable or neutral data when relevant.
- Apply **moderate** keyword density.
- Avoid repeating ideas using synonyms.
- Output the article in clean **HTML format** using semantic tags (h1, h2, h3, p, ul, li…), but **do not include** `<html>` or `<body>` tags.
- At the end of the article, include a **final closing paragraph**, but do **not** label it as a conclusion and do **not** use the words "conclusion", "summary", "resumen", or any synonym. It must simply function as the natural final paragraph of the article.

Write the full article now."""

        # Stream Phase 2 content
        stream = generate_completion(prompt_phase_2, max_tokens=1200, stream=True)
        if not stream:
            if yield_json: yield json.dumps({"error": "Error en Fase 2: No se pudo iniciar la redacción"}) + "\n"
            return

        draft = ""
        for chunk in stream:
            if hasattr(chunk, 'text') and chunk.text:
                content_chunk = chunk.text
                draft += content_chunk
                if yield_json: yield json.dumps({"status": "phase_2_stream", "chunk": content_chunk}) + "\n"
        
        if not draft:
            if yield_json: yield json.dumps({"error": "Error en Fase 2: Borrador vacío"}) + "\n"
            return

        if yield_json: yield json.dumps({"status": "phase_2_done", "data": "Borrador completado"}) + "\n"
        del prompt_phase_2
        gc.collect()

        # Phase 3: Revisión
        if yield_json: yield json.dumps({"status": "phase_3", "message": "Revisando contenido..."}) + "\n"
        
        # Truncate to avoid excessive tokens
        truncated_draft = draft[:12000] 
        
        prompt_phase_3 = f"""Evaluate and critique the following article with the goal of boosting SEO performance:

{truncated_draft}

Identify and list:

- Redundant or repetitive phrases
- Weak, vague, or unsupported statements
- Unnecessary repetitions of ideas
- Opportunities to increase clarity or precision
- Cases of keyword over-optimization

Provide **specific, actionable corrections** without rewriting the entire article."""

        critique = generate_completion(prompt_phase_3, max_tokens=800)
        if not critique:
            if yield_json: yield json.dumps({"error": "Error en Fase 3: No se pudo generar la crítica"}) + "\n"
            return

        if yield_json: yield json.dumps({"status": "phase_3_done", "data": critique}) + "\n"
        del prompt_phase_3
        gc.collect()

        # Phase 4: Finalización
        if yield_json: yield json.dumps({"status": "phase_4", "message": "Aplicando mejoras finales..."}) + "\n"
        
        prompt_phase_4 = f"""Using the following article and its critique:

**Original Article:**
{truncated_draft}

**Review:**
{critique}

Produce the **final, polished version** of the article.

Apply all suggested corrections and enhancements.

Return **only the HTML article code**, with no Markdown, no explanations, and no `<html>` or `<body>` tags.
Do not include images."""

        # Stream Phase 4 content
        stream_final = generate_completion(prompt_phase_4, max_tokens=1500, stream=True)
        if not stream_final:
            if yield_json: yield json.dumps({"error": "Error en Fase 4: No se pudo iniciar la versión final"}) + "\n"
            return

        final_article = ""
        for chunk in stream_final:
            if hasattr(chunk, 'text') and chunk.text:
                content_chunk = chunk.text
                final_article += content_chunk
                if yield_json: yield json.dumps({"status": "phase_4_stream", "chunk": content_chunk}) + "\n"

        if not final_article:
             if yield_json: yield json.dumps({"error": "Error en Fase 4: El artículo final se generó vacío."}) + "\n"
             return

        # Cleanup
        final_article = final_article.replace("```html", "").replace("```", "")
        del prompt_phase_4, critique, draft, plan, truncated_draft
        gc.collect()

        if yield_json:
            yield json.dumps({"status": "complete", "final_article": final_article}) + "\n"
        else:
            yield final_article

    except Exception as e:
        print(f"Generate Exception: {e}")
        error_msg = f"Error inesperado: {str(e)}"
        if yield_json:
            yield json.dumps({"error": error_msg}) + "\n"
        else:
            raise e

def process_batch(rows, credentials_dict=None):
    """
    Process a batch of articles in the background.
    Iterates through rows, generates content, and uploads to Drive.
    """
    print(f"Starting batch processing of {len(rows)} items...")

    # Authenticate service once if possible, or per request if needed.
    # Since this runs in a thread, we can't access 'session' directly easily if it expires.
    # We pass the credentials dictionary explicitly, or let get_drive_service load from file.
    try:
        service = get_drive_service(creds_dict=credentials_dict)
    except Exception as e:
        print(f"Batch Error: Could not authenticate Drive: {str(e)}")
        # Try one more time forcing file load if creds_dict was None
        if not credentials_dict:
             try:
                 print("Attempting to load credentials from file for batch...")
                 service = get_drive_service() # Will try file
             except Exception as e2:
                 print(f"Batch Error (Fallback): {str(e2)}")
                 return
        else:
             return

    for i, row in enumerate(rows):
        topic = row.get('palabra_clave')
        suggested_title = row.get('titulo_sugerido', '')
        
        if not topic:
            continue
            
        print(f"[{i+1}/{len(rows)}] Processing: {topic}")
        
        try:
            # Generate Article
            # Iterate through the generator until the end to get the final result
            final_content = None
            generator = generate_article_logic(topic, suggested_title, yield_json=False)
            
            for result in generator:
                # The last yielded value from generate_article_logic(yield_json=False) is the final HTML
                final_content = result
            
            if final_content:
                # Use suggested title or topic if not provided
                doc_title = suggested_title if suggested_title else f"Articulo: {topic}"
                
                # Upload to Drive
                print(f"Uploading '{doc_title}' to Drive...")
                save_article_to_drive(doc_title, final_content, service=service)
                print(f"✓ Uploaded: {doc_title}")
            else:
                print(f"✗ Failed to generate content for {topic}")
                
        except Exception as e:
            print(f"✗ Error processing {topic}: {e}")
            
        # Heavy cleanup after each item
        gc.collect()
        # Small pause to be nice to APIs
        time.sleep(2)
        
    print("Batch processing complete.")

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
        
        # Store credentials in session AND file
        credentials = flow.credentials
        creds_dict = credentials_to_dict(credentials)
        session['credentials'] = creds_dict
        
        # Persist to file
        with open(TOKEN_FILE, 'w') as f:
            json.dump(creds_dict, f)
        
        # Redirect back to home page
        return redirect('/')
        
    except Exception as e:
        return jsonify({"error": f"Callback error: {str(e)}"}), 500

@app.route('/auth-status')
def auth_status():
    """Check if user is authenticated with Google Drive."""
    try:
        # Check session or file
        if 'credentials' in session:
            creds_dict = session['credentials']
        elif os.path.exists(TOKEN_FILE):
             with open(TOKEN_FILE, 'r') as f:
                creds_dict = json.load(f)
        else:
             return jsonify({"authenticated": False})
        
        # Check if credentials are valid
        creds = Credentials(**creds_dict)
        
        # Try to refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                new_creds_dict = credentials_to_dict(creds)
                
                # Update session
                if 'credentials' in session:
                     session['credentials'] = new_creds_dict
                
                # Update file
                with open(TOKEN_FILE, 'w') as f:
                    json.dump(new_creds_dict, f)
            except:
                # Refresh failed, need to re-authorize
                if 'credentials' in session: session.pop('credentials', None)
                if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)
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
        
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            
        return jsonify({"success": True, "message": "Disconnected from Google Drive"})
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
                
                # CHECK FOR BATCH INPUT ("filas")
                if 'filas' in data and isinstance(data['filas'], list):
                    rows = data['filas']
                # Handle single item inputs (Sheets single row or direct JSON)
                # Sheets sends 'palabra_clave' and 'titulo_sugerido'
                elif 'palabra_clave' in data:
                    rows = [{
                        'palabra_clave': data.get('palabra_clave'),
                        'titulo_sugerido': data.get('titulo_sugerido', '')
                    }]
                else: 
                     return jsonify({"status": "error", "message": "JSON must contain 'filas' list or 'palabra_clave'"}), 400

                # Process whatever rows we have (1 or many)
                
                # Try to get credentials from session or file
                creds_dict = session.get('credentials')
                if not creds_dict and os.path.exists(TOKEN_FILE):
                    try:
                        with open(TOKEN_FILE, 'r') as f:
                            creds_dict = json.load(f)
                    except:
                        pass
                
                if not creds_dict:
                        return jsonify({"status": "error", "message": "No estás autenticado en Google Drive. Por favor visita la web y conecta Drive primero."}), 401
                
                # Start background thread
                thread = threading.Thread(target=process_batch, args=(rows, creds_dict))
                thread.daemon = True # Daemon thread so it doesn't block app shutdown
                thread.start()
                
                return jsonify({
                    "status": "processing_started",
                    "message": f"Se ha iniciado el procesamiento de {len(rows)} artículo(s) en segundo plano."
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        return jsonify({"status": "error", "message": "JSON required"}), 400
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

        # Use helper function
        # Get authenticated Drive service with current session
        service = get_drive_service()
        file = save_article_to_drive(title, content, service=service)
                                      
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
        
        # Check if token file exists (Variable TOKEN_FILE seems unused previously but we check OAUTH_CREDENTIALS_FILE)
        oauth_creds_status = "OAuth credentials exist" if os.path.exists(OAUTH_CREDENTIALS_FILE) else "OAuth credentials not found"

        return jsonify({
            "user": about.get('user'),
            "quota": about.get('storageQuota'),
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
         # Re-use logic in JSON yielding mode
         for msg in generate_article_logic(topic, title, yield_json=True):
             yield msg

    return Response(stream_with_context(generate_stream()), mimetype='application/json')

if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5000))
    serve(app, host='0.0.0.0', port=port)
