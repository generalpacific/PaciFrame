import boto3
import csv
import json
import openai
import os
import pytz
import random
import requests
import tempfile
from datetime import datetime
from enum import Enum

openai.api_key = os.environ["OPENAI_API_KEY"]


class ArtMode(Enum):
    MIX_AND_MATCH = 1
    NEW_OBJECT = 2


ART_MODE = ArtMode.NEW_OBJECT

SUPPORTED_OBJECTS = ["an android statue", "Torres del paine", "Istanbul skyline", "a Raspberry pi",
                     "a runner running on a trail", "a grand piano", "a visualization languages", "a japanese garden",
                     "a man meditating under a tree in a valley", "a home library with famous books",
                     "a formula one car", "pyramids of Giza along with Sphinx", "view of the Alhambra"]


def generate_prompt_for_mix_and_match(style, medium, colors, objects, theme):
    return '''Generate a {} {} painting that depicts {}. 
    The color palette of the painting is {} and the painting explores {} themes.'''.format(style, medium, objects,
                                                                                           colors, theme)


def generate_prompt_for_new_object(new_object, style, medium, theme, artist):
    return '''Generate a {} {} painting that depicts {}. 
    The painting explores {} themes.
    Paint it like {} would paint it.'''.format(style, medium, new_object, theme, artist, artist)


def generate_image(prompt, idx):
    # Set the model parameters
    num_images = 1
    size = "1792x1024"
    response_format = "url"

    # Call the DALL-E API
    response = openai.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=num_images,
        size=size,
        response_format=response_format
    )

    # Get the URL of the generated image
    print(response)
    image_url = response.data[0].url

    # Download the image from the URL
    image_data = requests.get(image_url).content

    tz = pytz.timezone('US/Pacific')
    now = datetime.now(tz)
    # Generate the S3 key with today's date
    date_str = now.strftime("%Y-%m-%d")
    s3_key = f"{date_str}-{idx}.png"
    if idx == 0:
        s3_key = f"{date_str}.png"

    # Upload the prompt to S3
    s3 = boto3.client('s3')
    s3_key_prompt = f"{date_str}-prompt.txt"
    if idx != 0:
        s3_key_prompt = f"{date_str}-{idx}-prompt.txt"
    s3.put_object(Body=prompt, Bucket=os.environ['ARTOFTHEDAY_S3_BUCKET'], Key=s3_key_prompt)

    # Upload the image data to S3
    with tempfile.TemporaryFile() as temp_file:
        temp_file.write(image_data)
        temp_file.seek(0)
        s3.upload_fileobj(temp_file, os.environ['ARTOFTHEDAY_S3_BUCKET'], s3_key)
    return date_str


def read_from_csv():
    s3 = boto3.client('s3')

    bucket_name = os.environ['METADATA_S3_BUCKET']
    file_name = os.environ['METADATA_S3_FILENAME']

    # download file from S3 to local disk
    s3.download_file(bucket_name, file_name, '/tmp/metadata_dict.csv')

    metadata_dict = {}

    with open('/tmp/metadata_dict.csv', 'r') as file:
        reader = csv.reader(file)
        header = next(reader)  # read the first row as header
        for row in reader:
            for i, value in enumerate(row):
                key = header[i]
                if key not in metadata_dict:
                    metadata_dict[key] = []
                metadata_dict[key].append(value)

    return metadata_dict


def lambda_handler(event, context):
    metadata_dict = read_from_csv()

    num_images = int(os.environ['MAX_IMAGES_PER_DAY'])
    date_str = ""
    new_object = random.choice(SUPPORTED_OBJECTS)
    for i in range(num_images):
        prompt = ""
        print(f"Current ArtMode: {ART_MODE}")
        if ART_MODE == ArtMode.MIX_AND_MATCH:
            prompt = generate_prompt_for_mix_and_match(style=random.choice(metadata_dict["style"]),
                                                       medium=random.choice(metadata_dict["medium"]),
                                                       colors=random.choice(metadata_dict["colors"]),
                                                       objects=random.choice(metadata_dict["objects"]),
                                                       theme=random.choice(metadata_dict["theme"])
                                                       )
        else:
            painting_idx = random.randint(0, len(metadata_dict["style"]) - 1)
            prompt = generate_prompt_for_new_object(new_object, metadata_dict["style"][painting_idx],
                                                    metadata_dict["medium"][painting_idx],
                                                    metadata_dict["theme"][painting_idx],
                                                    metadata_dict["artist"][painting_idx])
        print(f"Generated for idx: {i} prompt: {prompt}")
        print(f"Generating image for idx {i}...")
        date_str = generate_image(prompt, idx=i)
    return {
        'statusCode': 200,
        'body': json.dumps('Image saved. Date: ' + date_str)
    }

