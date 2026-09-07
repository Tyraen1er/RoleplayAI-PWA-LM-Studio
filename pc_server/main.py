from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
import os
import subprocess
import requests
import json
import re
import uuid
import time
import logging

# Chemin absolu vers les dossiers
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOBILE_CLIENT_DIR = os.path.join(BASE_DIR, "mobile_client")
CONVERSATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversations")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lms_proxy.log")

import sys

# Configuration des logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Logique au démarrage (rien de spécial)
    yield
    # Logique à l'arrêt du script Python (ex: Ctrl+C)
    print("\nFermeture du serveur Python. Tentative d'arrêt de LM Studio...")
    try:
        subprocess.run(["lms", "server", "stop"], shell=True, check=False)
        print("LM Studio arrêté avec succès.")
    except Exception as e:
        print(f"Erreur lors de l'arrêt de LM Studio: {e}")

app = FastAPI(title="LM Studio Controller API", lifespan=lifespan)

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith((".js", ".css", ".html", "/")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Chemin absolu vers les dossiers
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOBILE_CLIENT_DIR = os.path.join(BASE_DIR, "mobile_client")
CONVERSATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversations")

# S'assurer que le dossier des conversations existe
os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

# URL de l'API locale de LM Studio
LM_STUDIO_API = "http://localhost:1234/v1"

# Modèles de données
class LMStudioSettings(BaseModel):
    temperature: float
    max_tokens: int
    model: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    conversation_id: str = None
    message: str
    settings: LMStudioSettings

class RenameRequest(BaseModel):
    name: str

class TrackersUpdate(BaseModel):
    trackers: Dict[str, Any]

class TrackerInitRequest(BaseModel):
    category_name: str
    description: Optional[str] = ""
    model: Optional[str] = ""

def parse_json_from_llm(text: str) -> dict:
    """Extrait et décode proprement un objet JSON retourné par le LLM."""
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
        
    # Tentative d'extraction par regex du premier bloc { ... }
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
            
    return {}

def format_trackers_for_prompt(trackers: Dict[str, Any]) -> str:
    """Formate les trackers de manière propre et universelle pour le contexte système."""
    if not trackers:
        return ""
    lines = [
        "<internal_game_state>",
        "IMPORTANT: The following data is internal memory for narrative consistency.",
        "Do NOT print, list, or format this state block in your story output."
    ]
    for category_name, category_content in trackers.items():
        lines.append(f"\n[Category: {category_name}]")
        if isinstance(category_content, dict):
            # Nouveau format {description, items}
            if "items" in category_content and isinstance(category_content["items"], dict):
                desc = category_content.get("description", "").strip()
                if desc:
                    lines.append(f"Description / Scope: {desc}")
                for k, v in category_content["items"].items():
                    lines.append(f"- {k}: {v}")
            else:
                # Format plat ou rétrocompatible
                desc = category_content.get("description", "").strip() if "description" in category_content else ""
                if desc:
                    lines.append(f"Description / Scope: {desc}")
                for k, v in category_content.items():
                    if k != "description":
                        if isinstance(v, list):
                            lines.append(f"- {k}: {', '.join(str(item) for item in v)}")
                        elif isinstance(v, dict):
                            inner_str = ", ".join(f"{ik}: {iv}" for ik, iv in v.items())
                            lines.append(f"- {k}: {inner_str}")
                        else:
                            lines.append(f"- {k}: {v}")
        elif isinstance(category_content, list):
            for item in category_content:
                lines.append(f"- {item}")
        else:
            lines.append(f"- {category_content}")
    lines.append("</internal_game_state>")
    return "\n".join(lines)

class SystemPromptUpdate(BaseModel):
    system_prompt: str

@app.post("/api/settings")
def update_settings(settings: LMStudioSettings):
    # Logique pour mettre à jour les paramètres de LM Studio ou de la conversation
    print(f"Nouveaux paramètres reçus depuis le mobile : {settings}")
    return {"status": "success", "settings": settings}

@app.post("/api/start")
def start_server():
    try:
        # Lancement de LM Studio via sa CLI (lms server start)
        # On utilise Popen pour ne pas bloquer le serveur Python
        subprocess.Popen(["lms", "server", "start"], shell=True)
        return {"status": "success", "message": "Démarrage demandé"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/stop")
def stop_server():
    try:
        # Arrêt de LM Studio via sa CLI (lms server stop)
        subprocess.run(["lms", "server", "stop"], shell=True, check=True)
        return {"status": "success", "message": "Arrêt demandé"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/models")
def get_models():
    try:
        response = requests.get(f"{LM_STUDIO_API}/models", timeout=2)
        if response.status_code == 200:
            return response.json()
        return {"data": []}
    except requests.exceptions.RequestException:
        # LM Studio n'est probablement pas démarré
        raise HTTPException(status_code=503, detail="LM Studio hors ligne")

@app.get("/api/conversations")
def list_conversations():
    conversations = []
    for filename in os.listdir(CONVERSATIONS_DIR):
        if filename.endswith(".json"):
            conv_id = filename.replace(".json", "")
            try:
                with open(os.path.join(CONVERSATIONS_DIR, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    conversations.append({
                        "id": conv_id,
                        "name": data.get("name", "New Conversation"),
                        "updated_at": os.path.getmtime(os.path.join(CONVERSATIONS_DIR, filename))
                    })
            except Exception:
                pass
    # Trier par date de mise à jour (plus récent d'abord)
    conversations.sort(key=lambda x: x["updated_at"], reverse=True)
    return {"conversations": conversations}

@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Conversation introuvable")

@app.post("/api/conversations/new")
def create_new_conversation():
    conv_id = str(uuid.uuid4())
    conv_data = {
        "name": "New Conversation",
        "messages": [],
        "summaries": [],
        "trackers": {},
        "system_prompt": "You are an expert narrator writing a story collaboratively. Always let the player make their own decisions without prompting them. Make detailed and long answers.",
        "last_compressed_index": 0
    }
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(conv_data, f, ensure_ascii=False, indent=2)
    return {"id": conv_id}

@app.delete("/api/conversations/{conv_id}/last_turn")
def delete_last_turn(conv_id: str):
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        conv_data = json.load(f)
        
    messages = conv_data.get("messages", [])
    if not messages:
        return {"status": "success", "message": "", "history": []}
        
    last_user_msg = ""
    # Si le dernier message est celui de l'IA, on le supprime ainsi que le message utilisateur précédent
    if messages[-1]["role"] != "user":
        messages.pop() # Enlève la réponse de l'IA
    
    if messages and messages[-1]["role"] == "user":
        last_user_msg = messages[-1]["content"]
        messages.pop() # Enlève le message de l'utilisateur
        
    conv_data["messages"] = messages
    
    # Sécurité si on a supprimé des messages qui avaient déjà été compressés
    if conv_data.get("last_compressed_index", 0) > len(messages):
        # Le joueur a annulé un message qui était déjà dans un bloc compressé.
        # On recule d'un bloc de 10 messages (5 tours) et on supprime le dernier résumé.
        while conv_data.get("last_compressed_index", 0) > len(messages):
            if "summaries" in conv_data and conv_data["summaries"]:
                conv_data["summaries"].pop()
            conv_data["last_compressed_index"] = max(0, conv_data.get("last_compressed_index", 0) - 10)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(conv_data, f, ensure_ascii=False, indent=2)
        
    return {
        "status": "success", 
        "last_user_message": last_user_msg, 
        "history": messages,
        "last_compressed_index": conv_data.get("last_compressed_index", 0)
    }

@app.put("/api/conversations/{conv_id}/name")
def rename_conversation(conv_id: str, request: RenameRequest):
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        conv_data = json.load(f)
        
    conv_data["name"] = request.name.strip()
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(conv_data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "name": conv_data["name"]}

@app.get("/api/conversations/{conv_id}/trackers")
def get_trackers(conv_id: str):
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        conv_data = json.load(f)
        
    return {
        "trackers": conv_data.get("trackers", {}),
        "last_tracker_update": conv_data.get("last_tracker_update", 0)
    }

@app.put("/api/conversations/{conv_id}/trackers")
def update_trackers_endpoint(conv_id: str, request: TrackersUpdate):
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        conv_data = json.load(f)
        
    conv_data["trackers"] = request.trackers
    conv_data["last_tracker_update"] = time.time()
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(conv_data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success"}

@app.post("/api/conversations/{conv_id}/trackers/initialize")
def initialize_tracker(conv_id: str, request: TrackerInitRequest):
    """Analyse les derniers messages non compressés pour déterminer les objets et valeurs du tracker."""
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        conv_data = json.load(f)
        
    messages = conv_data.get("messages", [])
    if not messages:
        return {"status": "success", "items": {}}
        
    # Extraire les messages non-compressés (à partir de last_compressed_index)
    start_idx = conv_data.get("last_compressed_index", 0)
    uncompressed_messages = messages[start_idx:] if start_idx < len(messages) else messages
    
    # Construire le texte de contexte narratif
    story_parts = []
    if conv_data.get("summaries"):
        story_parts.append("Past Story Summary:\n" + "\n".join(conv_data["summaries"]))
        
    story_parts.append("Recent Conversation Turns:")
    for msg in uncompressed_messages:
        role = "Player" if msg["role"] == "user" else "Narrator"
        story_parts.append(f"{role}: {msg['content']}")
        
    story_context = "\n\n".join(story_parts)
    
    prompt = (
        f"You are a state-tracking AI for a text adventure game.\n"
        f"Your task is to extract individual characteristics, items, stats, or elements belonging to the tracker category '{request.category_name}'.\n\n"
        f"Category Name: '{request.category_name}'\n"
        f"Category Description / Scope: '{request.description or 'Extract each individual element or attribute'}'\n\n"
        f"Narrative Context:\n{story_context}\n\n"
        f"Instructions:\n"
        f"1. Break down the category into individual, separate keys for each distinct feature, stat, or item.\n"
        f"2. Output a flat JSON object where each key is a single attribute/item and the value is its state/description string.\n"
        f"   Example (Inventory): {{\"Iron Sword\": \"1\", \"Healing Potion\": \"2\", \"Gold\": \"50\"}}\n"
        f"   Example (Physical Traits): {{\"Height\": \"1m73\", \"Age\": \"33 years\", \"Body Frame\": \"Toned and slender\", \"Eyes\": \"Blue\", \"Hair\": \"Long and brown\"}}\n"
        f"3. All keys and values MUST be strictly in English (e.g. use 'Height' not 'Taille', 'Age' not 'Âge', 'Body Frame' not 'Corpulence', 'Eyes' not 'Yeux', 'Hair' not 'Cheveux'). Do NOT use French.\n"
        f"4. If nothing in the story context fits this category, return an empty JSON object: {{}}\n"
        f"5. Output ONLY a flat raw JSON object with individual keys. Do NOT wrap in parent categories."
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": "You are a state extraction assistant that responds strictly in flat, valid raw JSON in English. All keys and values must be in English. No prose, no markdown wrappers."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "stream": False
    }
    if request.model:
        payload["model"] = request.model
        
    logging.info(f"--- INITIALISATION TRACKER: '{request.category_name}' ---")
    try:
        resp = requests.post(f"{LM_STUDIO_API}/chat/completions", json=payload, timeout=60)
        logging.info(f"LM Studio status: {resp.status_code}")
        if resp.status_code == 200:
            result_text = resp.json()["choices"][0]["message"]["content"].strip()
            logging.info(f"Résultat extraction LLM pour '{request.category_name}': {result_text}")
            
            parsed = parse_json_from_llm(result_text)
            if isinstance(parsed, dict):
                # Désimbrication si le modèle a créé un conteneur parent (ex: {"TYRAEN'S BODY APPEARANCE": {...}})
                if len(parsed) == 1 and isinstance(list(parsed.values())[0], dict):
                    raw_items = list(parsed.values())[0]
                elif request.category_name in parsed and isinstance(parsed[request.category_name], dict):
                    raw_items = parsed[request.category_name]
                else:
                    matched_k = next((k for k in parsed.keys() if k.lower() in [request.category_name.lower(), "items", "features", "attributes", "elements"]), None)
                    if matched_k and isinstance(parsed[matched_k], dict):
                        raw_items = parsed[matched_k]
                    else:
                        raw_items = parsed
                
                # Aplatir proprement chaque sous-clé
                items = {}
                for k, v in raw_items.items():
                    if str(k).lower() not in ["category", "description", "status", "has_changes"]:
                        if isinstance(v, dict):
                            for sub_k, sub_v in v.items():
                                items[str(sub_k)] = str(sub_v)
                        else:
                            items[str(k)] = str(v)
                return {"status": "success", "items": items}
            return {"status": "success", "items": {}}
        else:
            error_detail = resp.text
            try:
                err_json = resp.json()
                error_detail = err_json.get("error", {}).get("message", resp.text)
            except Exception:
                pass
            logging.error(f"Erreur LM Studio lors de l'init tracker: {resp.status_code} - {error_detail}")
            raise HTTPException(status_code=resp.status_code, detail=f"LM Studio: {error_detail}")
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        logging.error(f"LM Studio est inaccessible lors de l'init tracker: {e}")
        raise HTTPException(status_code=503, detail="LM Studio est hors ligne. Veuillez démarrer le serveur LM Studio sur le port 1234.")
    except Exception as e:
        logging.error(f"Exception lors de l'init tracker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations/{conv_id}/system")
def get_system_prompt(conv_id: str):
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        conv_data = json.load(f)
        
    return {
        "system_prompt": conv_data.get("system_prompt", "You are an expert interactive narrator conducting a text adventure. Always let the player make their own decisions.")
    }

@app.put("/api/conversations/{conv_id}/system")
def update_system_prompt(conv_id: str, request: SystemPromptUpdate):
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        conv_data = json.load(f)
        
    conv_data["system_prompt"] = request.system_prompt
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(conv_data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success"}

def update_trackers_background(conv_id: str, last_action: str, ai_response: str, model: str):
    """Tâche de fond qui demande à LM Studio de mettre à jour les trackers en un seul appel."""
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    if not os.path.exists(file_path):
        return
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            conv_data = json.load(f)
            
        trackers = conv_data.get("trackers", {})
        if not trackers:
            return  # Aucun tracking actif
            
        prompt = (
            "You are a state-tracking AI for a text adventure game. Your task is to update the player's tracking sheets based on the latest narrative event.\n\n"
            f"Current state across all categories (including category descriptions and items):\n{json.dumps(trackers, indent=2, ensure_ascii=False)}\n\n"
            f"Latest event:\nPlayer: {last_action}\nGame: {ai_response}\n\n"
            "Instructions:\n"
            "1. Analyze the event carefully using the description/scope of each category to determine which category is affected.\n"
            "2. If no state changes occurred in any category, return an empty JSON object: {}\n"
            "3. If any category changed, return a JSON object with category names as keys, and objects containing ONLY the modified or newly added item keys and their updated values.\n"
            "   Example: {\"inventory\": {\"Silver Sword\": \"1\", \"Healing Potion\": \"0\"}}\n"
            "   - NEVER delete an existing item key. If an item is lost, consumed, or depleted, set its value to '0' or 'None'.\n"
            "   - You can add new keys to categories if the player acquires something new matching that category's description.\n"
            "   - Do NOT modify or return the 'description' field, only output item keys and values.\n"
            "4. All keys and values MUST be strictly in English.\n"
            "5. Your output MUST be a valid JSON object matching this structure without markdown codeblocks."
        )
        
        payload = {
            "messages": [
                {"role": "system", "content": "You are a state-tracking assistant that responds strictly in valid raw JSON in English. All keys and values must be in English. No prose, no markdown."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,  # Faible température pour éviter les hallucinations
            "stream": False
        }
        if model:
            payload["model"] = model
            
        logging.info("--- TRACKING BACKGROUND: Vérification globale des trackers (appel unique batché) ---")
        resp = requests.post(f"{LM_STUDIO_API}/chat/completions", json=payload, timeout=45)
        if resp.status_code == 200:
            result_text = resp.json()["choices"][0]["message"]["content"].strip()
            logging.info(f"Résultat LLM global pour les trackers:\n{result_text}")
            
            parsed_json = parse_json_from_llm(result_text)
            if isinstance(parsed_json, dict) and parsed_json:
                # Gérer les formats où le LLM encapsule dans une clé
                updates_dict = parsed_json
                if "updates" in parsed_json and isinstance(parsed_json["updates"], dict):
                    updates_dict = parsed_json["updates"]
                elif "categories" in parsed_json and isinstance(parsed_json["categories"], dict):
                    updates_dict = parsed_json["categories"]
                    
                updated_any = False
                for cat_name, cat_updates in updates_dict.items():
                    if not isinstance(cat_updates, dict):
                        continue
                        
                    # Si cat_updates contient lui-même un sous-dict imbriqué unique
                    if len(cat_updates) == 1 and isinstance(list(cat_updates.values())[0], dict):
                        cat_updates = list(cat_updates.values())[0]
                        
                    flat_updates = {}
                    for k, v in cat_updates.items():
                        if k != "description":
                            if isinstance(v, dict):
                                for sub_k, sub_v in v.items():
                                    flat_updates[str(sub_k)] = str(sub_v)
                            else:
                                flat_updates[str(k)] = str(v)
                                
                    target_cat = cat_name if cat_name in trackers else next((c for c in trackers.keys() if c.lower() == cat_name.lower()), None)
                    
                    if target_cat:
                        if "items" in trackers[target_cat] and isinstance(trackers[target_cat]["items"], dict):
                            for k, v in flat_updates.items():
                                trackers[target_cat]["items"][k] = v
                                updated_any = True
                                logging.info(f"Tracker '{target_cat}' mis à jour : {k} -> {v}")
                        else:
                            for k, v in flat_updates.items():
                                trackers[target_cat][k] = v
                                updated_any = True
                                logging.info(f"Tracker '{target_cat}' mis à jour : {k} -> {v}")
                    elif isinstance(cat_updates, dict) and cat_name not in ["has_changes", "status"]:
                        trackers[cat_name] = {
                            "description": "",
                            "items": {k: str(v) for k, v in flat_updates.items()}
                        }
                        updated_any = True
                        logging.info(f"Nouvelle catégorie tracker '{cat_name}' créée : {flat_updates}")
                        
                # Sauvegarde finale si un changement a eu lieu
                if updated_any:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        fresh_data = json.load(f)
                    fresh_data["trackers"] = trackers
                    fresh_data["last_tracker_update"] = time.time()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(fresh_data, f, ensure_ascii=False, indent=2)
                    logging.info("Sauvegarde des trackers réussie.")
        else:
            logging.error(f"Erreur API lors du tracking global: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        logging.error(f"Erreur dans la tâche de fond de tracking: {e}")


@app.post("/api/chat")
def chat_with_lmstudio(request: ChatRequest, background_tasks: BackgroundTasks):
    conv_id = request.conversation_id or str(uuid.uuid4())
    file_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")
    
    # Charger l'historique
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            conv_data = json.load(f)
    else:
        # Extraire le nom à partir du premier message (max 30 chars)
        title = request.message[:30] + "..." if len(request.message) > 30 else request.message
        conv_data = {"id": conv_id, "name": title, "messages": []}
        
    # Migration si ancienne sauvegarde avec "summary" texte au lieu d'une liste
    if "summary" in conv_data and isinstance(conv_data["summary"], str):
        if conv_data["summary"]:
            conv_data["summaries"] = [conv_data["summary"]]
        del conv_data["summary"]
        
    if "summaries" not in conv_data:
        conv_data["summaries"] = []

    # S'assurer de ne pas avoir deux messages 'user' à la suite (ex: si le dernier message a planté)
    while conv_data["messages"] and conv_data["messages"][-1]["role"] == "user":
        conv_data["messages"].pop()
        
    # --- LOGIQUE DE COMPRESSION PAR BLOCS (Fenêtre Glissante) ---
    COMPRESSION_THRESHOLD = 16 # 8 tours
    BLOCK_SIZE = 10 # 5 tours compressés
    
    last_idx = conv_data.get("last_compressed_index", 0)
    messages_count = len(conv_data["messages"])
    
    if messages_count - last_idx >= COMPRESSION_THRESHOLD:
        # On extrait le bloc de 10 messages (5 tours)
        messages_to_compress = conv_data["messages"][last_idx:last_idx + BLOCK_SIZE]
        
        compression_prompt = "Summarize the events of the following 5 conversation turns into clear chronological narrative prose. Highlight the player's choices/actions, key plot beats, and character developments. Output only a clean narrative summary without bracketed tags, metadata headers, or bullet lists.\n\n"
        for msg in messages_to_compress:
            role = "Player" if msg["role"] == "user" else "AI Narrator"
            compression_prompt += f"{role}: {msg['content']}\n\n"
            
        compression_payload = {
            "messages": [
                {"role": "system", "content": "You are an expert at summarizing interactive fiction stories."},
                {"role": "user", "content": compression_prompt}
            ],
            "temperature": 0.5,
            "stream": False
        }
        if request.settings.model:
            compression_payload["model"] = request.settings.model
            
        try:
            logging.info("--- DÉBUT COMPRESSION DE BLOC ---")
            resp = requests.post(f"{LM_STUDIO_API}/chat/completions", json=compression_payload, timeout=120)
            resp.raise_for_status()
            summary = resp.json()["choices"][0]["message"]["content"]
            
            conv_data["summaries"].append(summary)
            conv_data["last_compressed_index"] = last_idx + BLOCK_SIZE
            logging.info(f"Compression terminée. Nouvel index: {conv_data['last_compressed_index']}")
            
            # --- LOGIQUE DE COMPRESSION RECURSIVE (SUPER-BLOC) ---
            if len(conv_data["summaries"]) >= 5:
                logging.info("--- DÉBUT COMPRESSION RECURSIVE (SUPER BLOC) ---")
                blocks_to_merge = conv_data["summaries"][:4] # Les 4 premiers blocs
                
                super_prompt = "Here are 4 chronologically ordered summaries of a story. Combine them into a single, cohesive narrative master summary. Preserve the player's key decisions, overarching plot, and atmosphere. Output only clean narrative prose without bracketed tags, section headers, or metadata labels.\n\n"
                for i, blk in enumerate(blocks_to_merge):
                    super_prompt += f"--- Part {i+1} ---\n{blk}\n\n"
                    
                super_payload = {
                    "messages": [
                        {"role": "system", "content": "You are an expert editor summarizing interactive fiction."},
                        {"role": "user", "content": super_prompt}
                    ],
                    "temperature": 0.5,
                    "stream": False,
                    "model": request.settings.model if request.settings.model else ""
                }
                
                resp_super = requests.post(f"{LM_STUDIO_API}/chat/completions", json=super_payload, timeout=180)
                resp_super.raise_for_status()
                super_summary = resp_super.json()["choices"][0]["message"]["content"]
                
                # Replace first 4 blocks with the Super-Block, keeping the 5th (recent) intact
                conv_data["summaries"] = [super_summary, conv_data["summaries"][-1]]
                logging.info("Super-Block created successfully.")
                
        except Exception as e:
            logging.error(f"Erreur lors de la compression: {e}")
            # Si échec, on ne bloque pas le jeu

    # Ajouter le nouveau message utilisateur
    user_msg = {"role": "user", "content": request.message}
    conv_data["messages"].append(user_msg)
    
    # --- PRÉPARATION DE LA PAYLOAD POUR LM STUDIO (ORDRE STRICT) ---
    payload_messages = []
    
    # 1. System Prompt (toujours en premier)
    system_content = conv_data.get("system_prompt", "You are an expert interactive narrator conducting a text adventure. Always let the player make their own decisions.")

    
    # Trackers / État du monde et du joueur
    if conv_data.get("trackers"):
        formatted_trackers = format_trackers_for_prompt(conv_data["trackers"])
        if formatted_trackers:
            system_content += "\n\n" + formatted_trackers
            
    # Résumé de l'histoire passée (injecté proprement dans le contexte système pour éviter l'imitation par l'IA)
    if conv_data.get("summaries"):
        master_summary = "\n\n".join(conv_data["summaries"])
        system_content += (
            f"\n\n<past_story_summary>\n"
            f"Chronological summary of previous events for context:\n"
            f"{master_summary}\n"
            f"</past_story_summary>"
        )
        
    payload_messages.append({
        "role": "system",
        "content": system_content
    })
    
    if conv_data.get("summaries"):
        # 2. Message d'origine (la première action du joueur)
        if len(conv_data["messages"]) > 0:
            payload_messages.append(conv_data["messages"][0])
            
        # 3. Message de reprise + Premier message non-compressé
        start_idx = conv_data.get("last_compressed_index", 0)
        if start_idx > 0 and start_idx < len(conv_data["messages"]):
            first_uncompressed = conv_data["messages"][start_idx]
            payload_messages.append({
                "role": "user",
                "content": f"(The story continues from the previous events)\n\n{first_uncompressed['content']}"
            })
            
            # 4. Ajouter le reste de l'historique non-compressé (jusqu'à l'avant-dernier inclus)
            for msg in conv_data["messages"][start_idx + 1 : -1]:
                payload_messages.append(msg)
                
        # 5. Ajouter le tout dernier message
        if len(conv_data["messages"]) > 1:
            payload_messages.append(conv_data["messages"][-1])
    else:
        # Aucun sommaire formé, on ajoute tout l'historique brut après le system prompt
        for msg in conv_data["messages"]:
            payload_messages.append(msg)
    
    # Préparer la requête pour LM Studio
    payload = {
        "messages": payload_messages,
        "temperature": request.settings.temperature,
        "stream": False
    }
    # Ne pas envoyer max_tokens s'il est à -1 (infini), sinon LM Studio renvoie une erreur 400
    if request.settings.max_tokens > 0:
        payload["max_tokens"] = request.settings.max_tokens
        
    if request.settings.model:
        payload["model"] = request.settings.model
        
    logging.info(f"--- NOUVELLE REQUETE DE CHAT ---")
    logging.info(f"Conversation: {conv_id}")
    logging.info(f"Payload envoyé à LM Studio: {json.dumps(payload, ensure_ascii=False)}")
        
    try:
        # Appel à LM Studio
        response = requests.post(f"{LM_STUDIO_API}/chat/completions", json=payload, timeout=60)
        logging.info(f"Statut HTTP LM Studio: {response.status_code}")
        logging.info(f"Réponse brute LM Studio: {response.text}")
        
        response.raise_for_status()
        
        result = response.json()
        ai_message = result["choices"][0]["message"]
        
        # Sauvegarder la réponse de l'IA
        conv_data["messages"].append({"role": ai_message["role"], "content": ai_message["content"]})
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conv_data, f, ensure_ascii=False, indent=2)
            
        # Lancement de la tâche de fond pour mettre à jour les trackers
        background_tasks.add_task(update_trackers_background, conv_id, request.message, ai_message["content"], request.settings.model)
            
        return {
            "status": "success",
            "conversation_id": conv_id,
            "message": ai_message,
            "history": conv_data["messages"],
            "last_compressed_index": conv_data.get("last_compressed_index", 0)
        }
    except requests.exceptions.HTTPError as e:
        # Tenter d'extraire le message d'erreur précis de LM Studio
        error_detail = str(e)
        if e.response is not None:
            try:
                err_data = e.response.json()
                error_detail = err_data.get("error", {}).get("message", e.response.text)
            except:
                error_detail = e.response.text
                
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conv_data, f, ensure_ascii=False, indent=2)
        raise HTTPException(status_code=500, detail=f"Erreur LM Studio: {error_detail}")
    except Exception as e:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conv_data, f, ensure_ascii=False, indent=2)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

# Servir l'application mobile PWA à la racine
@app.get("/")
def read_root():
    return FileResponse(os.path.join(MOBILE_CLIENT_DIR, "index.html"))

app.mount("/", StaticFiles(directory=MOBILE_CLIENT_DIR), name="mobile_client")

if __name__ == "__main__":
    # Lancement du serveur sur toutes les interfaces pour que le mobile puisse s'y connecter
    uvicorn.run(app, host="0.0.0.0", port=8000)
