import openai
import os

openai.api_key = os.environ["OPENAI_API_KEY"]


def generate_text(prompt, model):
    completion = openai.ChatCompletion.create(model=model, messages=[{"role": "user", "content": prompt}])

    print(completion)
    answer = completion.choices[0].message.content
    return answer


def main():
    prompt = input("Enter a prompt: ")
    model = "gpt-3.5-turbo"
    answer = generate_text(prompt, model)
    print(answer)


if __name__ == '__main__':
    main()
