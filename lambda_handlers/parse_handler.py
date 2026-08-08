from scripts.parse import parse

def handler(event, context):
    result = parse()
    return {"statusCode": 200, **result}