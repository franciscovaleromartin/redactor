import os
from flask import Flask, request, jsonify, render_template
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

def generate_completion(prompt, model="gpt-4o"):
    """Helper function to call OpenAI API."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un experto redactor SEO y copywriter."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in OpenAI call: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_article():
    data = request.json
    topic = data.get('topic')
    title = data.get('title')

    if not topic:
        return jsonify({"error": "Se requiere un tema (topic)."}), 400

    # Phase 1: Planificación SEO
    prompt_phase_1 = f"""Genera un esquema detallado para un artículo optimizado para SEO sobre: {topic}.
Título sugerido: {title}
Incluye:
– Intención de búsqueda.
– Palabras clave principales y secundarias.
– Estructura H1/H2/H3 muy específica.
– Puntos clave que deben cubrirse en cada sección.
– Ejemplos concretos para mejorar calidad.
No escribas el contenido. Solo el plan."""
    
    plan = generate_completion(prompt_phase_1)
    if not plan:
        return jsonify({"error": "Error en Fase 1: Planificación"}), 500

    # Phase 2: Redacción controlada
    prompt_phase_2 = f"""Usa exclusivamente el siguiente esquema para redactar el artículo.
No añadas nuevas secciones.
Mantén claridad, precisión y evita relleno.
Incluye datos verificables o neutrales cuando proceda.
Aplica densidad de palabra clave moderada.
No repitas ideas con sinónimos.
Aquí tienes el esquema:
{plan}

Escribe el artículo completo en formato HTML (usa etiquetas h1, h2, p, ul, li, etc. pero sin html/body tags)."""

    draft = generate_completion(prompt_phase_2)
    if not draft:
        return jsonify({"error": "Error en Fase 2: Redacción"}), 500

    # Phase 3: Revisión automática
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

    critique = generate_completion(prompt_phase_3)
    if not critique:
        return jsonify({"error": "Error en Fase 3: Revisión"}), 500

    # Phase 4: Aplicación de mejoras
    prompt_phase_4 = f"""Teniendo en cuenta el siguiente artículo y la revisión crítica, genera la versión final y pulida del artículo.
Aplica las correcciones sugeridas.
Devuelve SOLO el código HTML del artículo final (sin markdown ```html, solo el contenido).

Artículo original:
{draft}

Revisión:
{critique}"""

    final_article = generate_completion(prompt_phase_4)
    if not final_article:
        return jsonify({"error": "Error en Fase 4: Mejoras"}), 500

    # Clean up potential markdown code blocks if GPT adds them despite instructions
    final_article = final_article.replace("```html", "").replace("```", "")

    return jsonify({
        "plan": plan,
        "draft": draft,
        "critique": critique,
        "final_article": final_article
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
