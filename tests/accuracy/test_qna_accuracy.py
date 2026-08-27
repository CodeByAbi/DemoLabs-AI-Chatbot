import sys
import os
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

# DeepEval
try:
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    from deepeval.models.base_model import DeepEvalBaseLLM
except:
    print("CRITICAL: pip install deepeval dulu!")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Config
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
CHATBOT_API_URL = "http://localhost:8000/v1/chat_outgoing" # <-- PASTIKAN BENAR

# Azure Wrapper DeepEval
class AzureOpenAI(DeepEvalBaseLLM):
    def __init__(self): self.model_name = "gpt-4o-mini"
    def load_model(self): return self.model_name
    def generate(self, prompt: str) -> str: return self._call(prompt)
    async def a_generate(self, prompt: str) -> str: return self._call(prompt)
    def get_model_name(self): return self.model_name
    def _call(self, prompt):
        url = f"{ENDPOINT.rstrip('/')}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}"
        headers = {"Content-Type": "application/json", "api-key": API_KEY}
        payload = {"messages": [{"role": "user", "content": prompt}], "temperature": 0}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=30)
            return res.json()["choices"][0]["message"]["content"]
        except: return "Error"

# Metrik
correctness_metric = GEval(
    name="Correctness",
    criteria="Is the actual output factually consistent with the expected output?",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    model=AzureOpenAI(),
    threshold=0.7
)

def get_bot_response(question, persona_id, dataset_id):
    payload = {
        "user_id": "eval-user", "message": question, "session_id": "eval-sess",
        "conversation_id": "eval-conv", "persona_id": persona_id, "dataset_id": dataset_id,
        "timestamp": datetime.now().isoformat(), "locale": "en_US", "channel": "web", "metadata": {}
    }
    try:
        res = requests.post(CHATBOT_API_URL, json=payload, timeout=30)
        if res.status_code == 200:
            d = res.json()
            if "data" in d and "answer" in d["data"]: return d["data"]["answer"]
            return str(d)
    except: pass
    return "Error Connection"

def run_tests(persona_id, dataset_id, test_file, output_file):
    with open(test_file, 'r') as f: cases = json.load(f)
    results, scores, times = [], [], []
    
    print(f"\nRUNNING DEEPEVAL ({len(cases)} Cases)")
    print("-" * 60)

    for i, case in enumerate(cases):
        start = datetime.now()
        actual = get_bot_response(case['question'], persona_id, dataset_id)
        
        score = 0.0
        if "Error" not in actual:
            test_case = LLMTestCase(input=case['question'], actual_output=actual, expected_output=case['expected_answer'])
            try:
                correctness_metric.measure(test_case)
                score = correctness_metric.score
            except: score = 0.0
        
        duration = (datetime.now() - start).total_seconds()
        scores.append(score)
        times.append(duration)
        
        print(f"[{i+1}] {case['difficulty'].upper()} | Score: {score:.2f} | Time: {duration:.1f}s")
        
        results.append({
            "test_case": case,
            "response": {"generated_answer": actual},
            "metrics": {
                "semantic_similarity": float(score), 
                "response_time_seconds": duration,
                "retrieval_correct": True if score > 0.7 else False
            },
            "status": "success"
        })

    final = {
        "test_type": "qna_deepeval", "dataset_id": dataset_id, "persona_id": persona_id,
        "timestamp": datetime.now().isoformat(),
        "summary": {"total_tests": len(cases), "successful_tests": len(results)},
        "aggregate_metrics": {
            "semantic_similarity": {"mean": sum(scores)/len(scores) if scores else 0},
            "performance": {"avg_response_time_seconds": sum(times)/len(times) if times else 0}
        },
        "test_results": results
    }
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f: json.dump(final, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona-id"); parser.add_argument("--dataset-id")
    parser.add_argument("--test-file"); parser.add_argument("--output")
    args = parser.parse_args()
    run_tests(args.persona_id, args.dataset_id, args.test_file, args.output)