document.addEventListener('DOMContentLoaded', () => {
    // Éléments du DOM
    const temperature = document.getElementById('temperature');
    const tempValue = document.getElementById('tempValue');
    const maxTokens = document.getElementById('maxTokens');
    const tokensValue = document.getElementById('tokensValue');
    const btnStart = document.getElementById('btnStart');
    const btnStop = document.getElementById('btnStop');
    const modelSelect = document.getElementById('modelSelect');
    
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const btnSend = document.getElementById('btnSend');
    const btnNewChat = document.getElementById('btnNewChat');
    const btnUndo = document.getElementById('btnUndo');
    const btnRename = document.getElementById('btnRename');
    const btnTrackers = document.getElementById('btnTrackers');
    const btnSystem = document.getElementById('btnSystem');
    const btnFullscreen = document.getElementById('btnFullscreen');
    const chatPanel = document.querySelector('.chat-panel');
    const chatTitle = document.getElementById('chatTitle');
    const conversationList = document.getElementById('conversationList');

    // Trackers Modal
    const trackersModal = document.getElementById('trackersModal');
    const btnCloseTrackers = document.getElementById('btnCloseTrackers');
    const trackersList = document.getElementById('trackersList');
    const btnAddTracker = document.getElementById('btnAddTracker');
    const btnSaveTrackers = document.getElementById('btnSaveTrackers');
    const toastNotification = document.getElementById('toastNotification');
    const toastMessage = document.getElementById('toastMessage');

    // System Modal
    const systemModal = document.getElementById('systemModal');
    const btnCloseSystem = document.getElementById('btnCloseSystem');
    const btnSaveSystem = document.getElementById('btnSaveSystem');
    const systemPromptInput = document.getElementById('systemPromptInput');

    let currentConversationId = null;
    let currentConversationName = "Nouvelle conversation";
    let lastTrackerUpdate = 0;
    let pollingInterval = null;

    // Met à jour la visibilité du bouton Undo et Renommer
    function updateChatActionsVisibility() {
        btnSystem.style.display = 'inline-block';
        btnTrackers.style.display = 'inline-block';
        
        if (currentConversationId) {
            btnRename.style.display = 'inline-block';
        } else {
            btnRename.style.display = 'none';
        }
        
        if (currentConversationId && chatMessages.querySelectorAll('.message.user').length > 0) {
            btnUndo.style.display = 'inline-block';
        } else {
            btnUndo.style.display = 'none';
        }
    }
    
    async function ensureConversationExists() {
        if (!currentConversationId) {
            try {
                const res = await fetch('/api/conversations/new', { method: 'POST' });
                if (res.ok) {
                    const data = await res.json();
                    currentConversationId = data.id;
                    updateChatActionsVisibility();
                    loadConversations();
                }
            } catch (e) {
                console.error(e);
            }
        }
    }

    function showToast(message) {
        toastMessage.textContent = message;
        toastNotification.style.display = 'block';
        setTimeout(() => toastNotification.classList.add('show'), 10);
        
        setTimeout(() => {
            toastNotification.classList.remove('show');
            setTimeout(() => toastNotification.style.display = 'none', 300);
        }, 4000);
    }

    // Commandes Serveur
    btnStart.addEventListener('click', async () => {
        btnStart.textContent = 'Démarrage...';
        btnStart.disabled = true;
        btnStart.style.opacity = '0.7';
        try {
            const res = await fetch('/api/start', { method: 'POST' });
            if (res.ok) {
                btnStart.textContent = 'Démarré';
                btnStart.style.backgroundColor = 'var(--success)';
                // On ne remet plus le bouton à son état initial ici, loadModels s'en chargera
                setTimeout(loadModels, 3000); // Recharger les données car le serveur devrait être up
            }
        } catch(e) {
            btnStart.textContent = 'Erreur';
            setTimeout(() => {
                btnStart.textContent = 'Démarrer';
                btnStart.disabled = false;
                btnStart.style.opacity = '1';
                btnStart.style.backgroundColor = '';
            }, 2000);
        }
    });

    btnStop.addEventListener('click', async () => {
        btnStop.textContent = 'Arrêt...';
        btnStop.disabled = true;
        btnStop.style.opacity = '0.7';
        try {
            const res = await fetch('/api/stop', { method: 'POST' });
            if (res.ok) {
                btnStop.textContent = 'Arrêté';
                document.getElementById('statusDot').className = 'dot offline';
                document.getElementById('statusText').textContent = 'Hors ligne';
                setTimeout(loadModels, 1000); // Mettre à jour l'interface
            }
        } catch(e) {
            btnStop.textContent = 'Erreur';
            setTimeout(() => {
                btnStop.textContent = 'Arrêter';
                btnStop.disabled = false;
                btnStop.style.opacity = '1';
            }, 2000);
        }
    });

    // Paramètres
    temperature.addEventListener('input', (e) => tempValue.textContent = e.target.value);
    maxTokens.addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        tokensValue.textContent = val === -1 ? '-1 (Infini)' : val;
    });

    // Fonction pour ajouter un message au DOM
    function appendMessage(role, content) {
        const div = document.createElement('div');
        div.className = `message ${role === 'user' ? 'user' : 'ai'}`;
        div.textContent = content;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        updateChatActionsVisibility();
    }

    // Chat
    btnNewChat.addEventListener('click', async () => {
        currentConversationId = null;
        currentConversationName = "Nouvelle conversation";
        chatTitle.textContent = "Chat";
        chatMessages.innerHTML = '<div class="message system">Nouvelle conversation.</div>';
        lastCompressedIndex = 0;
        messagesCount = 0;
        updateChatActionsVisibility();
        stopPolling();
    });

    btnRename.addEventListener('click', async () => {
        if (!currentConversationId) return;
        const newName = prompt("Nouveau nom de la conversation :", currentConversationName);
        if (newName && newName.trim() !== "") {
            try {
                const res = await fetch(`/api/conversations/${currentConversationId}/name`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: newName })
                });
                if (res.ok) {
                    const data = await res.json();
                    currentConversationName = data.name;
                    chatTitle.textContent = currentConversationName;
                    loadConversations(); // Recharger la liste
                }
            } catch (e) {
                console.error(e);
            }
        }
    });

    btnUndo.addEventListener('click', async () => {
        if (!currentConversationId) return;
        btnUndo.disabled = true;
        try {
            const res = await fetch(`/api/conversations/${currentConversationId}/last_turn`, { method: 'DELETE' });
            if (res.ok) {
                const data = await res.json();
                
                // Remettre le texte dans l'input
                if (data.last_user_message) {
                    chatInput.value = data.last_user_message;
                    chatInput.focus();
                }
                
                // Recharger l'affichage avec l'historique mis à jour
                chatMessages.innerHTML = '';
                if (data.history.length === 0) {
                    chatMessages.innerHTML = '<div class="message system">Nouvelle conversation.</div>';
                } else {
                    data.history.forEach(msg => {
                        appendMessage(msg.role, msg.content);
                    });
                }
                
                messagesCount = data.history.length;
                if (data.last_compressed_index !== undefined) {
                    lastCompressedIndex = data.last_compressed_index;
                }
            }
        } catch (e) {
            console.error(e);
        }
        btnUndo.disabled = false;
        updateChatActionsVisibility();
    });

    btnSend.addEventListener('click', async () => {
        const text = chatInput.value.trim();
        if (!text) return;

        // Ajouter message user
        appendMessage('user', text);
        chatInput.value = '';
        
        // Vérifier si une compression aura lieu (le backend vérifie: messagesCount - lastCompressedIndex >= 16)
        const isCompressing = (messagesCount - lastCompressedIndex) >= 16;
        const loadingText = isCompressing 
            ? 'Compression de la mémoire en cours... (cela prend environ 1 à 2 minutes)' 
            : 'L\'IA réfléchit...';
        
        // Ajouter un indicateur de chargement
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message system';
        loadingDiv.id = 'loadingIndicator';
        loadingDiv.textContent = loadingText;
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        const settings = {
            temperature: parseFloat(temperature.value),
            max_tokens: parseInt(maxTokens.value),
            model: modelSelect.value
        };

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: currentConversationId,
                    message: text,
                    settings: settings
                })
            });

            const data = await response.json();
            document.getElementById('loadingIndicator')?.remove();

            if (response.ok) {
                currentConversationId = data.conversation_id;
                currentConversationName = data.history[0]?.name || chatTitle.textContent;
                appendMessage('ai', data.message.content);
                
                messagesCount = data.history.length;
                if (data.last_compressed_index !== undefined) {
                    lastCompressedIndex = data.last_compressed_index;
                }
                
                loadConversations(); // Mettre à jour la liste
                
                // L'IA vient de répondre, on lance une écoute temporaire
                // pour voir si la tâche de fond met à jour les trackers
                startSmartPolling();
            } else {
                appendMessage('system', 'Erreur: ' + data.detail);
            }
        } catch (error) {
            document.getElementById('loadingIndicator')?.remove();
            appendMessage('system', 'Erreur réseau.');
        }
    });

    // Chargement d'une conversation spécifique
    async function openConversation(convId) {
        try {
            const res = await fetch(`/api/conversations/${convId}`);
            if (res.ok) {
                const data = await res.json();
                currentConversationId = convId;
                currentConversationName = data.name || "Conversation";
                chatTitle.textContent = currentConversationName;
                chatMessages.innerHTML = '';
                data.messages.forEach(msg => {
                    appendMessage(msg.role, msg.content);
                });
                updateChatActionsVisibility();
                
                messagesCount = data.messages ? data.messages.length : 0;
                lastCompressedIndex = data.last_compressed_index || 0;
                
                // On ne démarre plus de polling infini ici.
                // Le check se fera uniquement après avoir envoyé un message.
            }
        } catch (e) {
            console.error(e);
        }
    }

    // --- LOGIQUE TRACKERS ---
    
    function createTrackerDOM(name = "", data = {}) {
        const div = document.createElement('div');
        div.className = 'tracker-item';
        
        let desc = "";
        let items = {};
        if (data && typeof data === 'object') {
            if ('items' in data && typeof data.items === 'object') {
                desc = data.description || "";
                items = data.items || {};
            } else {
                desc = data.description || data._description || "";
                items = { ...data };
                delete items.description;
                delete items._description;
            }
        }
        
        const header = document.createElement('div');
        header.className = 'tracker-header';
        header.innerHTML = `
            <input type="text" class="tracker-name" value="${name}" placeholder="Nom du Tracker (ex: inventaire)">
            <div class="tracker-header-actions">
                <button class="btn-init-tracker" title="Détecter les éléments via l'IA d'après les derniers messages">🪄 Initialiser</button>
                <button class="btn-remove-tracker" title="Supprimer catégorie">❌</button>
            </div>
        `;

        const descContainer = document.createElement('div');
        descContainer.className = 'tracker-desc-container';
        descContainer.innerHTML = `
            <label class="tracker-field-label">📝 Description / Règle pour l'IA :</label>
            <textarea class="tracker-desc" rows="2" placeholder="Ex: Les armes, armures possédées par le joueur et objets de quêtes">${desc}</textarea>
        `;

        const itemsHeader = document.createElement('div');
        itemsHeader.className = 'tracker-field-label';
        itemsHeader.style.marginTop = '10px';
        itemsHeader.textContent = "📦 Éléments suivis :";
        
        const rowsContainer = document.createElement('div');
        rowsContainer.className = 'tracker-rows';
        
        function addRow(k = "", v = "") {
            const row = document.createElement('div');
            row.className = 'tracker-row';
            row.innerHTML = `
                <input type="text" class="tracker-key" value="${k}" placeholder="Objet / Stat">
                <span>:</span>
                <input type="text" class="tracker-val" value="${v}" placeholder="Quantité / État">
                <button class="btn-remove-row" title="Supprimer ligne">✖</button>
            `;
            row.querySelector('.btn-remove-row').onclick = () => row.remove();
            rowsContainer.appendChild(row);
        }
        
        if (Object.keys(items).length === 0) {
            addRow(); 
        } else {
            for (const [k, v] of Object.entries(items)) {
                addRow(k, v);
            }
        }
        
        const btnAddRow = document.createElement('button');
        btnAddRow.className = 'btn-add-row';
        btnAddRow.textContent = "+ Ajouter un élément";
        btnAddRow.onclick = () => addRow();
        
        div.appendChild(header);
        div.appendChild(descContainer);
        div.appendChild(itemsHeader);
        div.appendChild(rowsContainer);
        div.appendChild(btnAddRow);
        
        header.querySelector('.btn-remove-tracker').onclick = () => div.remove();

        const btnInit = header.querySelector('.btn-init-tracker');
        btnInit.onclick = async () => {
            const currentName = div.querySelector('.tracker-name').value.trim();
            const currentDesc = div.querySelector('.tracker-desc').value.trim();
            
            if (!currentName) {
                showToast("Veuillez d'abord donner un nom à ce tracker !");
                div.querySelector('.tracker-name').focus();
                return;
            }
            
            if (!currentConversationId) {
                showToast("Aucune conversation active.");
                return;
            }
            
            btnInit.textContent = "🪄 Analyse...";
            btnInit.disabled = true;
            btnInit.style.opacity = "0.7";
            
            try {
                const res = await fetch(`/api/conversations/${currentConversationId}/trackers/initialize`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        category_name: currentName,
                        description: currentDesc,
                        model: modelSelect.value
                    })
                });
                
                if (res.ok) {
                    const data = await res.json();
                    const detectedItems = data.items || {};
                    const keys = Object.keys(detectedItems);
                    
                    if (keys.length === 0) {
                        showToast("L'IA n'a trouvé aucun élément correspondant dans l'histoire récente.");
                    } else {
                        // Vider les lignes existantes et injecter les nouveaux éléments détectés
                        rowsContainer.innerHTML = '';
                        for (const [k, v] of Object.entries(detectedItems)) {
                            addRow(k, v);
                        }
                        showToast(`✨ ${keys.length} élément(s) détecté(s) par l'IA !`);
                    }
                } else {
                    const err = await res.json().catch(() => ({ detail: 'Erreur' }));
                    showToast(`Erreur IA : ${err.detail || 'Impossible d\'initialiser'}`);
                }
            } catch (e) {
                console.error(e);
                showToast("Erreur réseau lors de l'initialisation.");
            } finally {
                btnInit.textContent = "🪄 Initialiser";
                btnInit.disabled = false;
                btnInit.style.opacity = "1";
            }
        };
        
        trackersList.appendChild(div);
    }
    
    btnTrackers.addEventListener('click', async () => {
        await ensureConversationExists();
        if (!currentConversationId) return;
        trackersList.innerHTML = 'Chargement...';
        trackersModal.style.display = 'flex';
        
        try {
            const res = await fetch(`/api/conversations/${currentConversationId}/trackers`);
            if (res.ok) {
                const data = await res.json();
                trackersList.innerHTML = '';
                const trackers = data.trackers || {};
                
                if (Object.keys(trackers).length === 0) {
                    trackersList.innerHTML = '<div class="empty-state">Aucun tracker actif. Ajoutez-en un pour suivre l\'inventaire, la santé, etc.</div>';
                } else {
                    for (const [name, val] of Object.entries(trackers)) {
                        createTrackerDOM(name, val);
                    }
                }
            }
        } catch (e) {
            trackersList.innerHTML = 'Erreur réseau.';
        }
    });
    
    btnCloseTrackers.addEventListener('click', () => {
        trackersModal.style.display = 'none';
    });
    
    btnAddTracker.addEventListener('click', () => {
        createTrackerDOM('', {});
    });
    
    btnSaveTrackers.addEventListener('click', async () => {
        if (!currentConversationId) return;
        
        const newTrackers = {};
        document.querySelectorAll('.tracker-item').forEach(item => {
            const nameInput = item.querySelector('.tracker-name').value.trim();
            const descInput = item.querySelector('.tracker-desc')?.value.trim() || "";
            if (nameInput) {
                const itemsObj = {};
                item.querySelectorAll('.tracker-row').forEach(row => {
                    const k = row.querySelector('.tracker-key').value.trim();
                    const v = row.querySelector('.tracker-val').value.trim();
                    if (k) {
                        itemsObj[k] = v;
                    }
                });
                newTrackers[nameInput] = {
                    description: descInput,
                    items: itemsObj
                };
            }
        });
        
        btnSaveTrackers.textContent = "Sauvegarde...";
        try {
            const res = await fetch(`/api/conversations/${currentConversationId}/trackers`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ trackers: newTrackers })
            });
            if (res.ok) {
                btnSaveTrackers.textContent = "Sauvegardé !";
                setTimeout(() => {
                    btnSaveTrackers.textContent = "Sauvegarder";
                    trackersModal.style.display = 'none';
                }, 1000);
                
                // Mettre à jour notre timestamp local pour éviter de se notifier soi-même
                const data = await fetch(`/api/conversations/${currentConversationId}/trackers`).then(r => r.json());
                lastTrackerUpdate = data.last_tracker_update;
            }
        } catch (e) {
            btnSaveTrackers.textContent = "Erreur";
            setTimeout(() => btnSaveTrackers.textContent = "Sauvegarder", 2000);
        }
    });
    
    // --- VÉRIFICATION DES TRACKERS (APRES UN MESSAGE) ---
    
    async function checkTrackersOnce() {
        if (!currentConversationId) return;
        try {
            const res = await fetch(`/api/conversations/${currentConversationId}/trackers`);
            if (res.ok) {
                const data = await res.json();
                if (data.last_tracker_update > lastTrackerUpdate) {
                    lastTrackerUpdate = data.last_tracker_update;
                    
                    // Si des trackers existent
                    if (Object.keys(data.trackers).length > 0) {
                        showToast("L'IA a mis à jour vos trackers en arrière-plan ! 📋");
                        
                        if (trackersModal.style.display === 'flex') {
                            trackersList.innerHTML = '';
                            for (const [name, val] of Object.entries(data.trackers)) {
                                createTrackerDOM(name, val);
                            }
                        }
                    }
                    return true; // Un changement a été détecté
                }
            }
        } catch (e) {}
        return false;
    }

    function startSmartPolling() {
        stopPolling();
        let attempts = 0;
        // On va vérifier 4 fois (à 5s, 10s, 15s, et 20s après le message)
        pollingInterval = setInterval(async () => {
            attempts++;
            const changed = await checkTrackersOnce();
            if (changed || attempts >= 4) {
                stopPolling();
            }
        }, 5000);
    }
    
    function stopPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
    }

    // --- LOGIQUE SYSTEM PROMPT ---
    
    btnSystem.addEventListener('click', async () => {
        await ensureConversationExists();
        if (!currentConversationId) return;
        systemPromptInput.value = "Chargement...";
        systemModal.style.display = 'flex';
        
        try {
            const res = await fetch(`/api/conversations/${currentConversationId}/system`);
            if (res.ok) {
                const data = await res.json();
                systemPromptInput.value = data.system_prompt;
            }
        } catch (e) {
            systemPromptInput.value = "Erreur réseau.";
        }
    });
    
    btnCloseSystem.addEventListener('click', () => {
        systemModal.style.display = 'none';
    });
    
    btnSaveSystem.addEventListener('click', async () => {
        if (!currentConversationId) return;
        
        btnSaveSystem.textContent = "Sauvegarde...";
        try {
            const res = await fetch(`/api/conversations/${currentConversationId}/system`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ system_prompt: systemPromptInput.value.trim() })
            });
            if (res.ok) {
                btnSaveSystem.textContent = "Sauvegardé !";
                setTimeout(() => {
                    btnSaveSystem.textContent = "Sauvegarder";
                    systemModal.style.display = 'none';
                }, 1000);
            }
        } catch (e) {
            btnSaveSystem.textContent = "Erreur";
            setTimeout(() => btnSaveSystem.textContent = "Sauvegarder", 2000);
        }
    });

    // --- PLEIN ÉCRAN ---
    function getFullscreenElement() {
        return document.fullscreenElement || document.webkitFullscreenElement;
    }

    function toggleChatFullscreen() {
        if (getFullscreenElement()) {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            }
        } else {
            if (chatPanel.requestFullscreen) {
                chatPanel.requestFullscreen().catch(err => console.error('[Fullscreen] Erreur :', err));
            } else if (chatPanel.webkitRequestFullscreen) {
                chatPanel.webkitRequestFullscreen();
            }
        }
    }

    function updateFullscreenButton() {
        btnFullscreen.textContent = getFullscreenElement() ? '✕' : '⛶';
        btnFullscreen.title = getFullscreenElement() ? 'Quitter le plein écran' : 'Plein écran';
    }

    btnFullscreen.addEventListener('click', toggleChatFullscreen);
    document.addEventListener('fullscreenchange', updateFullscreenButton);
    document.addEventListener('webkitfullscreenchange', updateFullscreenButton);

    // Charger les conversations
    async function loadConversations() {
        try {
            const res = await fetch('/api/conversations');
            if (res.ok) {
                const data = await res.json();
                if (data.conversations && data.conversations.length > 0) {
                    conversationList.innerHTML = '';
                    data.conversations.forEach(conv => {
                        const li = document.createElement('li');
                        li.className = 'conversation-item';
                        li.textContent = conv.name;
                        li.addEventListener('click', () => openConversation(conv.id));
                        conversationList.appendChild(li);
                    });
                } else {
                    conversationList.innerHTML = '<li class="empty-state">Aucune conversation</li>';
                }
            }
        } catch (e) {}
    }

    // Charger les modèles
    async function loadModels() {
        try {
            const res = await fetch('/api/models');
            if (res.ok) {
                // LM Studio est en ligne
                document.getElementById('statusDot').className = 'dot online';
                document.getElementById('statusText').textContent = 'En ligne';
                
                // Mettre à jour les boutons
                btnStart.disabled = true;
                btnStart.style.backgroundColor = 'var(--bg-color)';
                btnStart.style.color = 'var(--text-secondary)';
                btnStart.style.opacity = '0.5';
                btnStart.textContent = 'En ligne';
                
                btnStop.disabled = false;
                btnStop.style.opacity = '1';
                btnStop.textContent = 'Arrêter';
                
                const data = await res.json();
                if (data.data && data.data.length > 0) {
                    modelSelect.innerHTML = '';
                    data.data.forEach(model => {
                        const opt = document.createElement('option');
                        opt.value = model.id;
                        opt.textContent = model.id;
                        modelSelect.appendChild(opt);
                    });
                } else {
                    modelSelect.innerHTML = '<option value="">Aucun modèle chargé dans LM Studio</option>';
                }
            } else {
                // Erreur HTTP
                setOfflineState();
            }
        } catch (e) {
            setOfflineState();
        }
    }
    
    function setOfflineState() {
        document.getElementById('statusDot').className = 'dot offline';
        document.getElementById('statusText').textContent = 'Hors ligne';
        modelSelect.innerHTML = '<option value="">Erreur de connexion</option>';
        
        // Mettre à jour les boutons
        btnStart.disabled = false;
        btnStart.style.backgroundColor = '';
        btnStart.style.color = '';
        btnStart.style.opacity = '1';
        btnStart.textContent = 'Démarrer';
        
        btnStop.disabled = true;
        btnStop.style.opacity = '0.5';
        btnStop.textContent = 'Arrêter';
    }

    // Initialisation
    loadModels();
    loadConversations();
});
