document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('articleForm');
    const generateBtn = document.getElementById('generateBtn');
    const btnText = generateBtn.querySelector('.btn-text');
    const loader = generateBtn.querySelector('.loader');
    const resultsSection = document.getElementById('resultsSection');
    const articleContent = document.getElementById('articleContent');
    
    // Debug elements
    const debugPlan = document.getElementById('debugPlan');
    const debugDraft = document.getElementById('debugDraft');
    const debugCritique = document.getElementById('debugCritique');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset UI
        resultsSection.style.display = 'none';
        generateBtn.disabled = true;
        btnText.textContent = 'Generando... (Esto tomará unos minutos)';
        loader.style.display = 'inline-block';

        const formData = {
            topic: document.getElementById('topic').value,
            title: document.getElementById('title').value
        };

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error('Error en la generación del artículo');
            }

            const data = await response.json();

            // Display Results
            resultsSection.style.display = 'block';
            articleContent.innerHTML = data.final_article;

            // Fill Debug Info
            debugPlan.textContent = data.plan;
            debugDraft.innerHTML = data.draft;
            debugCritique.textContent = data.critique;

            // Scroll to results
            resultsSection.scrollIntoView({ behavior: 'smooth' });

        } catch (error) {
            alert('Hubo un error: ' + error.message);
        } finally {
            generateBtn.disabled = false;
            btnText.textContent = 'Generar Artículo';
            loader.style.display = 'none';
        }
    });
});
