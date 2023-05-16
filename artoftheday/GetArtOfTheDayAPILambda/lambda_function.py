import base64
import boto3
import json
import os

s3 = boto3.client('s3')


def lambda_handler(event, context):
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

    bucket_name = os.environ['ART_OF_THE_DAY_BUCKET_NAME']
    image_key = f'{date}.png'  # The image key is the date with the ".png" extension
    text_key = f'{date}-prompt.txt'  # The text key is the date with the ".txt" extension

    try:
        image_data = s3.get_object(Bucket=bucket_name, Key=image_key)['Body'].read()
        text_data = s3.get_object(Bucket=bucket_name, Key=text_key)['Body'].read().decode('utf-8')

        # Base64-encode the image data
        encoded_image_data = base64.b64encode(image_data)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'image': encoded_image_data.decode('utf-8'),
                'prompt': text_data
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
            'body': str(e),
            'headers': {
                'Access-Control-Allow-Origin': '*',
            }
        }
