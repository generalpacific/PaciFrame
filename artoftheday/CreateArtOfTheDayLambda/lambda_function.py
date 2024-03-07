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

openai.api_key = os.environ["OPENAI_API_KEY"]


def generate_prompt(style, medium, colors, objects, theme):
    return '''Generate a {} {} painting that depicts {}. 
    The color palette of the painting is {} and the painting explores {} themes.'''.format(style, medium, objects,
                                                                                           colors, theme)


def generate_image(prompt, idx):
    # Set the model parameters
    num_images = 1
    size = "1792x1024"
    response_format = "url"

    # Call the DALL-E API
    response = openai.Image.create(
        model="dall-e-3",
        prompt=prompt,
        n=num_images,
        size=size,
        response_format=response_format
    )

    # Get the URL of the generated image
    image_url = response['data'][0]['url']

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

    num_images = os.environ['MAX_IMAGES_PER_DAY']
    date_str = ""
    for i in range(num_images):
        prompt = generate_prompt(style=random.choice(metadata_dict["style"]),
                                 medium=random.choice(metadata_dict["medium"]),
                                 colors=random.choice(metadata_dict["color palette"]),
                                 objects=random.choice(metadata_dict["objects"]),
                                 theme=random.choice(metadata_dict["theme"])
                                 )
        print(f"Generated for idx: {i} prompt: {prompt}")
        print(f"Generating image for idx {i}...")
        date_str = generate_image(prompt, idx=i)
    return {
        'statusCode': 200,
        'body': json.dumps('Image saved. Date: ' + date_str)
    }
