# RoleplayAI-PWA-LM-Studio 🎲📱

Application PWA mobile et serveur FastAPI permettant de contrôler à distance une instance locale de **LM Studio** pour jouer à des jeux de rôle textuels (RPG) et récits interactifs propulsés par LLM local.

---

## 🌟 Fonctionnalités

### 🖥️ Serveur & Backend (`pc_server`)
- **Contrôle de LM Studio à distance** : Démarrage et arrêt du serveur LM Studio (`lms server start` / `lms server stop`) directement depuis le client web/mobile.
- **Gestion des Modèles & Paramètres** : Détection dynamique des modèles chargés, réglage de la température et de la fenêtre de contexte (`max_tokens`).
- **Persistance des Histoires** : Sauvegarde JSON par session dans `pc_server/conversations/`.
- **Mémoire Long-Terme & Compression Intelligente (Fenêtre glissante)** :
  - Résumé automatique des blocs de conversations (tous les 8 tours / 16 messages).
  - Compression récursive en *Super-Blocs* pour les longues sessions afin de ne jamais saturer le contexte du modèle tout en préservant la continuité narrative.
- **Suivi d'état & Inventaire en Arrière-plan (Trackers)** :
  - Extraction automatique des changements d'état (inventaire, PV, quêtes, réputation) via un appel LLM asynchrone en tâche de fond (`BackgroundTasks`).
  - Injection automatique de l'état formatté (`<internal_game_state>`) dans le prompt système.
- **Gestion Avancée des Tours** : Possibilité d'annuler le dernier tour (*Undo*) avec réajustement des index de compression.
- **Directives Narratives Personnalisables** : Modification du `system_prompt` par conversation depuis l'interface.

### 📱 Client Mobile / PWA (`mobile_client`)
- **Interface Dark Mode épurée & réactive** conçue pour les smartphones (PWA installable sur l'écran d'accueil).
- **Mode Plein Écran** pour une immersion totale dans l'histoire.
- **Éditeur de Trackers & Directives** : Modales dédiées pour gérer l'inventaire et les instructions de l'IA.
- **Notifications Toast** : Alertes visuelles quand les trackers sont mis à jour en arrière-plan par l'IA.
- **Historique des Conversations** : Sélection, renommage et bascule rapide entre différentes parties.

---

## 🏗️ Architecture du Projet

```text
RoleplayAI-PWA-LM-Studio/
├── mobile_client/              # Frontend PWA (Vanilla HTML/CSS/JS)
│   ├── app.js                  # Logique client, requêtes API et gestion de l'état UI
│   ├── index.css               # Feuille de style responsive et dark mode
│   ├── index.html              # Structure de l'application PWA
│   ├── manifest.json           # Manifest PWA pour l'installation sur smartphone
│   └── README.md
│
├── pc_server/                  # Backend FastAPI
│   ├── main.py                 # Serveur FastAPI, proxy LM Studio, logique de compression & trackers
│   ├── requirements.txt        # Dépendances Python
│   └── conversations/          # Dossier de persistance des conversations (JSON)
│
└── README.md
```

---

## 🚀 Installation et Lancement

### Prérequis
1. **[LM Studio](https://lmstudio.ai/)** installé avec le CLI `lms` configuré dans votre `PATH`.
2. **Python 3.10+** installé sur votre machine hôte.

### 1. Installation des dépendances

```bash
cd pc_server
pip install -r requirements.txt
```

### 2. Démarrage du serveur

```bash
python main.py
```

Le serveur démarrera sur `http://0.0.0.0:8000`.

### 3. Accès depuis votre smartphone

1. Assurez-vous que votre téléphone est connecté au **même réseau Wi-Fi** que votre PC.
2. Trouvez l'adresse IP locale de votre PC (ex: `192.168.1.XX`).
3. Ouvrez le navigateur de votre smartphone et rendez-vous sur :
   ```text
   http://192.168.1.XX:8000
   ```
4. *(Optionnel)* Cliquez sur **"Ajouter à l'écran d'accueil"** dans votre navigateur pour installer la PWA.

---

## 📡 API Endpoints Principaux

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/start` | Démarre LM Studio via le CLI (`lms server start`) |
| `POST` | `/api/stop` | Arrête le serveur LM Studio |
| `GET` | `/api/models` | Récupère la liste des modèles disponibles |
| `GET` | `/api/conversations` | Liste l'ensemble des conversations sauvegardées |
| `POST` | `/api/conversations/new` | Initialise une nouvelle conversation |
| `GET` / `PUT` | `/api/conversations/{id}/system` | Consulte ou modifie les directives système |
| `GET` / `PUT` | `/api/conversations/{id}/trackers` | Consulte ou met à jour les trackers (inventaire, état) |
| `DELETE` | `/api/conversations/{id}/last_turn` | Annule le dernier tour de jeu |
| `POST` | `/api/chat` | Envoie un message au LLM (avec compression et background tracking) |

---

## 📝 Licence

Projet open-source disponible pour un usage personnel et communautaire.
