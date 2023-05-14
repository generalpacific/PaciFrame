import csv
import openai
import os
import random
import requests
from PIL import Image

openai.api_key = os.environ["OPENAI_API_KEY"]


def generate_prompt(style, medium, colors, objects, theme):
    return '''Generate a {} {} painting that depicts {}. 
    The color palette of the painting is {} and the painting explores {} themes.'''.format(style, medium, objects,
                                                                                           colors, theme)


def generate_image(prompt):
    # Set the model parameters
    model = "image-alpha-001"
    num_images = 1
    size = "1024x1024"
    response_format = "url"

    # Call the DALL-E API
    response = openai.Image.create(
        prompt=prompt,
        model=model,
        n=num_images,
        size=size,
        response_format=response_format
    )

    # Get the URL of the generated image
    image_url = response['data'][0]['url']

    # Download the image from the URL
    image_data = requests.get(image_url).content

    # Save the image to a file
    with open("dalle_image.png", "wb") as f:
        f.write(image_data)

    # Open the image file using PIL
    image = Image.open("dalle_image.png")

    # Show the image
    image.show()


def read_from_csv():
    metadata_dict = {}

    with open('metadata.csv', 'r') as file:
        reader = csv.reader(file)
        header = next(reader)  # read the first row as header
        for row in reader:
            for i, value in enumerate(row):
                key = header[i]
                if key not in metadata_dict:
                    metadata_dict[key] = []
                metadata_dict[key].append(value)

    return metadata_dict


def main():
    metadata_dict = read_from_csv()
    prompt = generate_prompt(style=random.choice(metadata_dict["style"]),
                             medium=random.choice(metadata_dict["medium"]),
                             colors=random.choice(metadata_dict["color palette"]),
                             objects=random.choice(metadata_dict["objects"]),
                             theme=random.choice(metadata_dict["theme"])
                             )
    print("Generated prompt: " + prompt)
    print("Generating image...")
    generate_image(prompt)


if __name__ == '__main__':
    main()
