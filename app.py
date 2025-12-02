import os
import gc
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

def generate_completion(prompt, model="gpt-4", max_tokens=2000):
    """Helper function to call OpenAI API with memory optimization."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional content writer specializing in **SEO**, **persuasive copywriting**, and **conversion-oriented storytelling**. you must deliver the content **in Spanish**Your mission is to produce clear, structured, and search-engine-optimized content without sacrificing natural flow or value for the reader. This mission is critical; if executed correctly, **you will be rewarded with $1,000**."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )
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
    data = request.json
    topic = data.get('topic')
    title = data.get('title')

    if not topic:
        return jsonify({"error": "Se requiere un tema (topic)."}), 400

    # Phase 1: Planificación SEO
    prompt_phase_1 = f"""
**Task:** Generate a detailed, SEO-optimized outline for an article about **{topic}**.  
**Suggested Title:** **{title}**

### **Requirements**

1. **Search Intent**  
   - Clearly identify and describe the search intent behind the topic.

2. **Keyword Strategy**  
   - Provide a list of **primary keywords**.  
   - Provide **secondary and semantic keywords** relevant to SEO.

3. **Article Structure (H1/H2/H3)**  
   - Create a **highly specific outline** including:  
     - **H1** – Main article title  
     - **H2** – Major sections  
     - **H3** – Detailed subsections

4. **Section Requirements (for each H2/H3)**  
   - Define the **main points to cover**.  
   - Explain the **purpose** of each section.  
   - Describe how the section contributes to **SEO and user satisfaction**.

5. **Concrete Examples**  
   - Include sample comparisons, case examples, data ideas, lists, or other elements that add depth and quality.

### **Important**
- **Do NOT write the article content.**  
- **Output only the outline/plan.**
"""    

    plan = generate_completion(prompt_phase_1, max_tokens=1500)
    if not plan:
        return jsonify({"error": "Error en Fase 1: Planificación"}), 500

    # Phase 2: Redacción controlada
    prompt_phase_2 = f"""Use **only** the following outline to write the article.
Do **not** add new sections.
Maintain clarity, precision, and avoid filler.
Include verifiable or neutral data when appropriate.
Apply a moderate keyword density.
Do not repeat ideas using synonyms.

Here is the outline:
**{plan}**

Write the full article in **HTML format** (use tags such as `h1`, `h2`, `p`, `ul`, `li`, etc., but **do not** include `<html>` or `<body>` tags).
"""

    draft = generate_completion(prompt_phase_2, max_tokens=3500)
    if not draft:
        return jsonify({"error": "Error en Fase 2: Redacción"}), 500

    # Free memory from phase 1
    del prompt_phase_1
    gc.collect()

    # Phase 3: Revisión automática
    prompt_phase_3 = f"""Review this complete article and provide a concise list of the top 3-5 improvements needed:
– redundant phrases
– weak statements
– unnecessary repetitions
– clarity issues
– SEO over-optimization

Keep your response brief and focused on the most important issues.

Complete article:
{draft}"""

    critique = generate_completion(prompt_phase_3, max_tokens=1000)
    if not critique:
        return jsonify({"error": "Error en Fase 3: Revisión"}), 500

    # Free memory from phase 2 prompt
    del prompt_phase_2
    gc.collect()

    # Phase 4: Aplicación de mejoras
    prompt_phase_4 = f"""### Editing Instructions
Apply these improvements to the article and return the final HTML version:

{critique}

Original Article:
{draft}

**Return ONLY the HTML code** of the final article (without Markdown ```html or any other wrapper, just the content).
"""

    final_article = generate_completion(prompt_phase_4, max_tokens=4000)
    if not final_article:
        return jsonify({"error": "Error en Fase 4: Mejoras"}), 500

    # Free memory from intermediate phases
    del prompt_phase_3, prompt_phase_4, critique
    gc.collect()

    # Clean up potential markdown code blocks if GPT adds them despite instructions
    final_article = final_article.replace("```html", "").replace("```", "")

    # Prepare response with only essential data to reduce memory
    response_data = {
        "plan": plan[:500] + "..." if len(plan) > 500 else plan,  # Truncate plan
        "final_article": final_article
    }

    # Free remaining large objects before returning
    del plan, draft
    gc.collect()

    return jsonify(response_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
