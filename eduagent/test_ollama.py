import ollama

client = ollama.Client(host="http://127.0.0.1:11434")

response = client.chat(
    model="llama3:latest",   # or the exact model from `ollama list`
    messages=[
        {
            "role": "user",
            "content": "What is Python?"
        }
    ]
)

print(response)