from google import genai

client = genai.Client(api_key="AIzaSyBwpalZCFOtYRKLN7bctSUf1PAp4Y01B6g")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Say hello in one sentence."
)
print(response.text)