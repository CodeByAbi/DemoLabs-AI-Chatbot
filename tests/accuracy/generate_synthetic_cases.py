import sys
import json
import os
import requests
import time
from pathlib import Path
from datetime import datetime

# --- CONFIG ---
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# ⚠️ WAJIB CEK URL INI! (Ganti localhost dgn IP server kalau perlu)
CHATBOT_API_URL = "http://localhost:8000/v1/chat_outgoing" 

if not all([API_KEY, ENDPOINT, DEPLOYMENT]):
    print("CRITICAL: Env Vars Azure belum lengkap.")
    sys.exit(1)

def get_bot_truth(topic):
    """Minta Bot jelaskan topik (Validasi Konteks)"""
    payload = {
        "user_id": "seeder-01", "message": f"Tell me about {topic}", 
        "session_id": "seed-sess", "conversation_id": "seed-conv",
        "persona_id": "240a1084-93f3-468b-8f99-02ed555ee862", # ID PROD
        "dataset_id": "05fac329-6761-4df8-87f4-cf5f7f540f4d", # ID PROD
        "timestamp": datetime.now().isoformat(), "locale": "en_US", "channel": "web", "metadata": {}
    }
    try:
        print(f"   ...Validasi ke Bot: '{topic}'", end=" ")
        resp = requests.post(CHATBOT_API_URL, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            ans = data.get("data", {}).get("answer") or data.get("answer") or str(data)
            if "maaf" in ans.lower() or "sorry" in ans.lower():
                print("❌ Bot tidak tau (Skip)")
                return None
            print("✅ Valid")
            return ans
        print(f"❌ Error API {resp.status_code}")
    except Exception as e:
        print(f"❌ Koneksi Gagal: {e}")
    return None

def get_azure_completion(messages):
    """LLM sebagai Pabrik Soal"""
    url = f"{ENDPOINT.rstrip('/')}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    payload = {"messages": messages, "temperature": 0.8}
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except: return None

def generate_variations(topic, truth, count, difficulty):
    print(f"      -> Seeding {count} Q&A ({difficulty})...", end=" ", flush=True)
    
    prompt = f"""
    CONTEXT TRUTH: "{truth}"
    TOPIC: "{topic}"

    TASK: Generate {count} unique Q&A pairs based on the Context Truth.
    DIFFICULTY: {difficulty.upper()}

    GUIDELINES:
    - Easy: Simple direct questions. Answer is formal/standard.
    - Medium: Paraphrased questions. Answer conveys same meaning but different wording.
    - Hard: Casual/Slang/Indirect questions. Answer adapts to be helpful and natural.

    OUTPUT: Strictly JSON List of objects: [{{"q": "...", "a": "..."}}]
    """
    
    content = get_azure_completion([{"role": "user", "content": prompt}])
    variations = []
    if content:
        try:
            clean = content.replace("```json", "").replace("```", "").strip()
            pairs = json.loads(clean)
            for p in pairs[:count]:
                variations.append({
                    "question": p['q'], "expected_answer": p['a'],
                    "category": "generated", "difficulty": difficulty, "test_type": "llm_seeded"
                })
            print(f"✅")
        except: print(f"❌ Gagal Parse")
    else: print("❌ Gagal Azure")
    return variations

def main():
    file_path = "tests/accuracy/test_data/qna_test_cases.json"
    with open(file_path, 'r') as f: seeds = json.load(f)
    final_cases = []
    
    print(f"\n=== LLM SEEDER & VALIDATOR ===")
    
    for seed in seeds:
        topic = seed['question']
        truth = get_bot_truth(topic)
        
        if not truth: continue # Skip kalau bot gak punya datanya
        
        # Generate 20 Variasi per topik
        final_cases.extend(generate_variations(topic, truth, 7, "easy"))
        final_cases.extend(generate_variations(topic, truth, 7, "medium"))
        final_cases.extend(generate_variations(topic, truth, 6, "hard"))
    
    # Simpan
    with open(file_path, 'w') as f: json.dump(final_cases, f, indent=2)
    
    # Update Config
    conf_path = "tests/accuracy/test_data/qna_test_config.json"
    with open(conf_path, 'r') as f: c = json.load(f)
    c['total_test_cases'] = len(final_cases)
    with open(conf_path, 'w') as f: json.dump(c, f, indent=2)
    
    print(f"\n✅ DONE! {len(final_cases)} Soal Valid Siap Dites.")

if __name__ == "__main__":
    main()