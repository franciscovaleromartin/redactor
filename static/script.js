document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('articleForm');
    const generateBtn = document.getElementById('generateBtn');
    const btnText = generateBtn.querySelector('.btn-text');
    const loader = generateBtn.querySelector('.loader');
    const resultsSection = document.getElementById('resultsSection');
    const articleContent = document.getElementById('articleContent');

    // Drive connection elements
    const connectDriveBtn = document.getElementById('connectDriveBtn');
    const connectedIndicator = document.getElementById('connectedIndicator');
    const sendToDriveBtn = document.getElementById('sendToDriveBtn');

    // Debug elements
    const debugPlan = document.getElementById('debugPlan');
    const debugDraft = document.getElementById('debugDraft');
    const debugCritique = document.getElementById('debugCritique');

    // Check authentication status on page load
    async function checkAuthStatus() {
        try {
            const response = await fetch('/auth-status');
            const data = await response.json();

            if (data.authenticated) {
                // User is connected
                connectDriveBtn.style.display = 'none';
                connectedIndicator.style.display = 'block';
            } else {
                // User is not connected
                connectDriveBtn.style.display = 'block';
                connectedIndicator.style.display = 'none';
            }
        } catch (error) {
            console.error('Error checking auth status:', error);
            connectDriveBtn.style.display = 'block';
            connectedIndicator.style.display = 'none';
        }
    }

    // Call on page load
    checkAuthStatus();

    // Handle connect button click
    connectDriveBtn.addEventListener('click', () => {
        window.location.href = '/authorize';
    });

    // Handle disconnect button click
    const disconnectDriveBtn = document.getElementById('disconnectDriveBtn');
    disconnectDriveBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/disconnect-drive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const result = await response.json();

            if (result.success) {
                // Update UI to show disconnected state
                connectDriveBtn.style.display = 'block';
                connectedIndicator.style.display = 'none';

                // Disable send to drive button if visible
                if (sendToDriveBtn) {
                    sendToDriveBtn.disabled = true;
                }

                alert('Desconectado de Google Drive exitosamente');
            } else {
                alert('Error al desconectar: ' + result.message);
            }
        } catch (error) {
            console.error('Error disconnecting:', error);
            alert('Error al desconectar de Google Drive');
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Reset UI
        resultsSection.style.display = 'block'; // Show immediately to see progress
        generateBtn.disabled = true;
        btnText.textContent = 'Iniciando...';
        loader.style.display = 'inline-block';

        // Clear previous results
        articleContent.innerHTML = '';
        debugPlan.textContent = '';
        debugDraft.innerHTML = '';
        debugCritique.textContent = '';

        // Reset step indicators
        document.querySelectorAll('.step').forEach(step => {
            step.classList.remove('active', 'completed');
        });

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

                        // Get step elements
                        const step1 = document.getElementById('step1');
                        const step2 = document.getElementById('step2');
                        const step3 = document.getElementById('step3');
                        const step4 = document.getElementById('step4');

                        // Update UI based on status
                        if (data.status === 'phase_1') {
                            btnText.textContent = 'Fase 1: Planificando...';
                            step1.classList.add('active');
                        } else if (data.status === 'phase_1_done') {
                            debugPlan.textContent = data.data;
                            step1.classList.remove('active');
                            step1.classList.add('completed');
                        } else if (data.status === 'phase_1_truncated') {
                            debugPlan.textContent = data.data;
                            step1.classList.remove('active');
                            step1.classList.add('truncated');
                            step1.textContent = '1. Planificación (Truncado)';
                        } else if (data.status === 'phase_2') {
                            btnText.textContent = 'Fase 2: Redactando...';
                            debugDraft.innerHTML = ''; // Clear previous
                            step2.classList.add('active');
                        } else if (data.status === 'phase_2_stream') {
                            // Append streaming content to draft debug view
                            debugDraft.innerHTML += data.chunk.replace(/\n/g, '<br>');
                        } else if (data.status === 'phase_2_done') {
                            // Phase 2 complete
                            step2.classList.remove('active');
                            step2.classList.add('completed');
                        } else if (data.status === 'phase_2_truncated') {
                            step2.classList.remove('active');
                            step2.classList.add('truncated');
                            step2.textContent = '2. Redacción (Truncado)';
                        } else if (data.status === 'phase_3') {
                            btnText.textContent = 'Fase 3: Revisando...';
                            step3.classList.add('active');
                        } else if (data.status === 'phase_3_done') {
                            debugCritique.textContent = data.data;
                            step3.classList.remove('active');
                            step3.classList.add('completed');
                        } else if (data.status === 'phase_3_truncated') {
                            debugCritique.textContent = data.data;
                            step3.classList.remove('active');
                            step3.classList.add('truncated');
                            step3.textContent = '3. Revisión (Truncado)';
                        } else if (data.status === 'phase_4') {
                            btnText.textContent = 'Fase 4: Finalizando...';
                            articleContent.innerHTML = ''; // Clear previous
                            step4.classList.add('active');
                        } else if (data.status === 'phase_4_stream') {
                            // Append streaming content to final article view
                            articleContent.innerHTML += data.chunk;
                        } else if (data.status === 'phase_4_done') {
                            step4.classList.remove('active');
                            step4.classList.add('completed');
                        } else if (data.status === 'phase_4_truncated') {
                            step4.classList.remove('active');
                            step4.classList.add('truncated');
                            step4.textContent = '4. Finalización (Truncado)';
                        } else if (data.status === 'complete') {
                            // Ensure final clean version is set
                            articleContent.innerHTML = data.final_article;
                            btnText.textContent = '¡Completado!';
                            // Don't modify step4 here - it's already been set by phase_4_done or phase_4_truncated
                            resultsSection.style.display = 'block';
                            document.getElementById('sendToDriveBtn').disabled = false;

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

    // Google Drive upload handler
    const driveStatus = document.getElementById('driveStatus');

    sendToDriveBtn.addEventListener('click', async () => {
        // Check if user is authenticated first
        const authCheck = await fetch('/auth-status');
        const authData = await authCheck.json();

        if (!authData.authenticated) {
            driveStatus.innerHTML = '❌ Primero debes <a href="/authorize" style="color: #3b82f6; text-decoration: underline;">conectar Google Drive</a>';
            return;
        }

        const content = articleContent.innerHTML;
        // Extract title from the generated article's H1 tag
        let title = '';
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = content;
        const h1Element = tempDiv.querySelector('h1');

        if (h1Element) {
            title = h1Element.textContent.trim();
        }

        // Fallback to form title or topic if no H1 found
        if (!title) {
            title = document.getElementById('title').value;
        }
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
                driveStatus.innerHTML = `✅ Guardado en tu Google Drive (carpeta "redactor"): <a href="${result.link}" target="_blank">Ver documento</a>`;
                sendToDriveBtn.textContent = "Enviado";
            } else {
                throw new Error(result.error || "Error desconocido");
            }

        } catch (error) {
            const errorMsg = error.message;
            if (errorMsg.includes('Not authenticated')) {
                driveStatus.innerHTML = '❌ Sesión expirada. <a href="/authorize" style="color: #3b82f6; text-decoration: underline;">Reconectar Google Drive</a>';
            } else {
                driveStatus.textContent = "❌ Error al guardar: " + errorMsg;
            }
            sendToDriveBtn.disabled = false;
            sendToDriveBtn.textContent = "Enviar a Google Drive";
        }
    });
});
