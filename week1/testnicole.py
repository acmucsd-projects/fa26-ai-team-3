import ollama

# 1. Define your prompt and system instructions
system_instruction = "You are a helpful, concise coding assistant."
user_prompt = "Write a quick Python function to reverse a string."

print("🧠 Sending prompt to Ollama...\n")

try:
    # 2. Call the model (using your downloaded qwen3)
    response = ollama.chat(
        model='qwen3', 
        messages=[
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': user_prompt}
        ]
    )
    
    # 3. Print the result
    print("🤖 Response:")
    print(response['message']['content'])

except Exception as e:
    print(f"❌ Error connecting to Ollama: {e}")
    print("Make sure the Ollama application is running in the background!")
