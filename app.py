import os
import gc
import json
from flask import Flask, request, jsonify, render_template, stream_with_context, Response
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize OpenAI client
api_key = os.environ.get("api_key")
if not api_key:
    print("WARNING: 'api_key' environment variable not found. Please set it or create a .env file.")

client = OpenAI(api_key=api_key)

def generate_completion(prompt, model="gpt-4o-mini", max_tokens=1500, stream=False):
    """Helper function to call OpenAI API with memory optimization."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional content writer specializing in **SEO**, **persuasive copywriting**, and **conversion-oriented storytelling**. you must deliver the content **in Spanish**Your mission is to produce clear, structured, and search-engine-optimized content without sacrificing natural flow or value for the reader. This mission is critical; if executed correctly, **you will be rewarded with $1,000**."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            stream=stream
        )
        if stream:
            return response
        
        content = response.choices[0].message.content
        # Clean up response object to free memory
        del response
        gc.collect()
        return content
    except Exception as e:
        print(f"Error in OpenAI call: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_article():
    gc.collect()
    data = request.json
    topic = data.get('topic')
    title = data.get('title')

    if not topic:
        return jsonify({"error": "Se requiere un tema (topic)."}), 400

    def generate_stream():
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

        plan = generate_completion(prompt_phase_1, max_tokens=1000)
        if not plan:
            yield json.dumps({"error": "Error en Fase 1"}) + "\n"
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
        stream = generate_completion(prompt_phase_2, max_tokens=2500, stream=True)
        if not stream:
            yield json.dumps({"error": "Error en Fase 2"}) + "\n"
            return

        draft = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                draft += content_chunk
                # Yield small chunks to keep connection alive and show progress
                yield json.dumps({"status": "phase_2_stream", "chunk": content_chunk}) + "\n"
        
        yield json.dumps({"status": "phase_2_done", "data": "Borrador completado"}) + "\n"
        del prompt_phase_2
        gc.collect()

        # Phase 3: Revisión
        yield json.dumps({"status": "phase_3", "message": "Revisando contenido..."}) + "\n"
        
        prompt_phase_3 = f"""Evalúa este artículo.
Identifica:
– frases redundantes
– afirmaciones débiles
– repeticiones innecesarias
– oportunidades de mayor claridad
– sobreoptimización SEO
Sugiere correcciones concretas sin reescribir todo el texto.
Aquí está el artículo:
{draft}"""

        critique = generate_completion(prompt_phase_3, max_tokens=1000)
        if not critique:
            yield json.dumps({"error": "Error en Fase 3"}) + "\n"
            return

        yield json.dumps({"status": "phase_3_done", "data": critique}) + "\n"
        del prompt_phase_3
        gc.collect()

        # Phase 4: Finalización
        yield json.dumps({"status": "phase_4", "message": "Aplicando mejoras finales..."}) + "\n"
        
        prompt_phase_4 = f"""Teniendo en cuenta el siguiente artículo y la revisión crítica, genera la versión final y pulida del artículo.
Aplica las correcciones sugeridas.
Devuelve SOLO el código HTML del artículo final (sin markdown ```html, solo el contenido).

Artículo original:
{draft}

Revisión:
{critique}"""

        # Stream Phase 4 content
        stream_final = generate_completion(prompt_phase_4, max_tokens=3000, stream=True)
        if not stream_final:
            yield json.dumps({"error": "Error en Fase 4"}) + "\n"
            return

        final_article = ""
        for chunk in stream_final:
            if chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                final_article += content_chunk
                yield json.dumps({"status": "phase_4_stream", "chunk": content_chunk}) + "\n"

        # Cleanup
        final_article = final_article.replace("```html", "").replace("```", "")
        del prompt_phase_4, critique, draft, plan
        gc.collect()

        yield json.dumps({"status": "complete", "final_article": final_article}) + "\n"

    return Response(stream_with_context(generate_stream()), mimetype='application/json')

if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5000))
    serve(app, host='0.0.0.0', port=port)
