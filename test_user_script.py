import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Use the path we know exists
MODEL = r'C:\Users\wyrms\.cache\huggingface\hub\models--Qwen--Qwen2.5-Coder-7B-Instruct\snapshots\c03e6d358207e414f1eca0bb1891e29f1db0e242'

print(f'Loading model from {MODEL}...')

try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    print('Tokenizer loaded.')

    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        device_map='auto',
        torch_dtype=torch.float16,
        load_in_4bit=True,
        low_cpu_mem_usage=True
    )
    print('Model loaded successfully!')

    messages = [
        {'role': 'system', 'content': 'You are a precise coding assistant.'},
        {'role': 'user', 'content': 'Say pong.'},
    ]

    print('Generating...')
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors='pt').to(model.device)

    out = model.generate(**inputs, max_new_tokens=20, temperature=0.2)
    print(tokenizer.decode(out[0], skip_special_tokens=True))
    
except Exception as e:
    print(f'CRASHED: {e}')

