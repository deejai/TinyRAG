from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

def ask_gpt(prompt, chat_history=None):
    if chat_history == None:
        chat_history = []
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=chat_history + [{"role": "user", "content": prompt}]
    )

    response = completion.choices[0].message.content
    print(">> RESPONSE!!")
    print(response)
    return response
