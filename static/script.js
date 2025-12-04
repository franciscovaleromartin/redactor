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
                throw new Error('Error en la generación del artículo');
            }

            // Read streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        const data = JSON.parse(line);

                        // Handle errors
                        if (data.error) {
                            throw new Error(data.error);
                        }

                        // Update UI based on status
                        if (data.status === 'phase_1') {
                            btnText.textContent = 'Fase 1: Planificando...';
                        } else if (data.status === 'phase_1_done') {
                            debugPlan.textContent = data.data;
                        } else if (data.status === 'phase_2') {
                            btnText.textContent = 'Fase 2: Redactando...';
                            debugDraft.innerHTML = ''; // Clear previous
                        } else if (data.status === 'phase_2_stream') {
                            // Append streaming content to draft debug view
                            debugDraft.innerHTML += data.chunk.replace(/\n/g, '<br>');
                        } else if (data.status === 'phase_2_done') {
                            // Phase 2 complete
                        } else if (data.status === 'phase_3') {
                            btnText.textContent = 'Fase 3: Revisando...';
                        } else if (data.status === 'phase_3_done') {
                            debugCritique.textContent = data.data;
                        } else if (data.status === 'phase_4') {
                            btnText.textContent = 'Fase 4: Finalizando...';
                            articleContent.innerHTML = ''; // Clear previous
                        } else if (data.status === 'phase_4_stream') {
                            // Append streaming content to final article view
                            articleContent.innerHTML += data.chunk;
                        } else if (data.status === 'complete') {
                            // Ensure final clean version is set
                            articleContent.innerHTML = data.final_article;
                            btnText.textContent = '¡Completado!';
                            resultsSection.style.display = 'block';
                            document.getElementById('sendToDriveBtn').style.display = 'inline-block';
                            resultsSection.scrollIntoView({ behavior: 'smooth' });
                        }
                    } catch (parseError) {
                        console.error('Error parsing JSON chunk:', parseError);
                        console.error('Line:', line);
                    }
                }
            }

        } catch (error) {
            alert('Hubo un error: ' + error.message);
        } finally {
            generateBtn.disabled = false;
            btnText.textContent = 'Generar Artículo';
            loader.style.display = 'none';
        }
    });
    const sendToDriveBtn = document.getElementById('sendToDriveBtn');
    const driveStatus = document.getElementById('driveStatus');

    sendToDriveBtn.addEventListener('click', async () => {
        const content = articleContent.innerHTML;
        // Use the suggested title or a default one
        let title = document.getElementById('title').value;
        if (!title) {
            title = "Articulo - " + document.getElementById('topic').value;
        }

        sendToDriveBtn.disabled = true;
        sendToDriveBtn.textContent = "Enviando...";
        driveStatus.textContent = "";

        try {
            const response = await fetch('/upload-to-drive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content, title })
            });

            const result = await response.json();

            if (result.success) {
                driveStatus.innerHTML = `✅ Guardado en Drive: <a href="${result.link}" target="_blank">Ver documento</a>`;
                sendToDriveBtn.textContent = "Enviado";
            } else {
                throw new Error(result.error || "Error desconocido");
            }

        } catch (error) {
            driveStatus.textContent = "❌ Error al guardar: " + error.message;
            sendToDriveBtn.disabled = false;
            sendToDriveBtn.textContent = "Enviar a Google Drive";
        }
    });
});
