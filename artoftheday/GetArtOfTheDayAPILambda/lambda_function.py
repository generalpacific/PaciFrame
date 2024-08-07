import base64
import boto3
import json
import os
import gzip


def lambda_handler(event, context):
    s3 = boto3.client('s3')
    print(type(event))
    print(event)
    print("Event json %s" % json.dumps(event))
    print("Context %s" % context)

    if 'queryStringParameters' not in event:
        print("No queryStringParameters in event")
        return {
            'statusCode': '400',
            'body': "No queryStringParameters in event",
            'headers': {
                'Access-Control-Allow-Origin': '*',
            }
        }

    if event['queryStringParameters'] is None:
        print("queryStringParameters in event is none")
        return {
            'statusCode': '400',
            'body': "queryStringParameters in event is none",
            'headers': {
                'Access-Control-Allow-Origin': '*',
            }
        }

    if 'date' not in event['queryStringParameters']:
        print("No date in event[queryStringParameters]")
        return {
            'statusCode': '400',
            'body': "No date in event[queryStringParameters]",
            'headers': {
                'Access-Control-Allow-Origin': '*',
            }
        }
    date = event["queryStringParameters"]["date"]

    max_images_per_day = int(os.environ['MAX_IMAGES_PER_DAY'])

    # check the index of image if requested
    index = 0
    if 'index' in event['queryStringParameters']:
        index_str = event['queryStringParameters']['index']
        try:
            index = int(index_str)
        except ValueError:
            print(f"ValueError: Cannot convert index: {index_str} to an integer due to inappropriate value.")
        except TypeError:
            print(f"TypeError: Cannot convert index: {index_str} to an integer due to inappropriate type.")
        if index >= max_images_per_day:
            return {
                'statusCode': '400',
                'body': f"Index cannot be greater than or equal to max: f{max_images_per_day}",
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                }
            }

    bucket_name = os.environ['ART_OF_THE_DAY_BUCKET_NAME']
    image_key = f'{date}.png'  # The image key is the date with the ".png" extension
    if index != 0:
        image_key = f'{date}-{index}.png'
    text_key = f'{date}-prompt.txt'  # The text key is the date with the ".txt" extension
    if index != 0:
        text_key = f'{date}-{index}-prompt.txt'

    print(f"Getting image for key: {image_key} and text_key: {text_key}")

    try:
        image_data = s3.get_object(Bucket=bucket_name, Key=image_key)['Body'].read()
        prompt_data = s3.get_object(Bucket=bucket_name, Key=text_key)['Body'].read().decode('utf-8')

        # Base64-encode the image data
        encoded_image_data = base64.b64encode(gzip.compress(image_data))

        return {
            'statusCode': 200,
            'body': json.dumps({
                'image': encoded_image_data.decode('utf-8'),
                'prompt': prompt_data
            }),
            'headers': {
                'Content-Type': 'image/png',
                'Access-Control-Allow-Origin': '*'
            }
        }
    except Exception as e:
        print(e)
        return {
            'statusCode': '500',
            'body': json.dumps({
                'error': str(e),
            }),
            'headers': {
                'Access-Control-Allow-Origin': '*',
            }
        }
