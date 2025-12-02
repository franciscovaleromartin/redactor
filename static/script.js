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
        btnText.textContent = 'Iniciando...';
        loader.style.display = 'inline-block';

        // Clear previous results
        articleContent.innerHTML = '';
        debugPlan.textContent = '';
        debugDraft.innerHTML = '';
        debugCritique.textContent = '';

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
                throw new Error('Error en la conexión con el servidor');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            resultsSection.style.display = 'block';
            resultsSection.scrollIntoView({ behavior: 'smooth' });

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep the last incomplete line in buffer

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        const data = JSON.parse(line);

                        if (data.error) {
                            throw new Error(data.error);
                        }

                        if (data.status === 'phase_1') {
                            btnText.textContent = 'Fase 1: Planificando...';
                        } else if (data.status === 'phase_1_done') {
                            debugPlan.textContent = data.data;
                        } else if (data.status === 'phase_2') {
                            btnText.textContent = 'Fase 2: Redactando...';
                        } else if (data.status === 'phase_2_done') {
                            debugDraft.innerHTML = '<p><em>Borrador generado internamente...</em></p>';
                        } else if (data.status === 'phase_3') {
                            btnText.textContent = 'Fase 3: Revisando...';
                        } else if (data.status === 'phase_3_done') {
                            debugCritique.textContent = data.data;
                        } else if (data.status === 'phase_4') {
                            btnText.textContent = 'Fase 4: Finalizando...';
                        } else if (data.status === 'complete') {
                            articleContent.innerHTML = data.final_article;
                            btnText.textContent = '¡Completado!';
                        }

                    } catch (parseError) {
                        console.error('Error parsing JSON chunk:', parseError);
                    }
                }
            }

        } catch (error) {
            alert('Hubo un error: ' + error.message);
            btnText.textContent = 'Error';
        } finally {
            generateBtn.disabled = false;
            if (btnText.textContent !== 'Error') {
                btnText.textContent = 'Generar Otro Artículo';
            }
            loader.style.display = 'none';
        }
    });
});
