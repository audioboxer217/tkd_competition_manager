import argparse
import json
import os

import boto3
from dotenv import load_dotenv


def main(env: str, debug: bool = False):
    # Fetch variables
    load_dotenv(f"{env}.env")
    USER = os.getenv("user")
    PASSWORD = os.getenv("password")
    HOST = os.getenv("host")
    PORT = os.getenv("port")
    DBNAME = os.getenv("dbname")

    # Your JSON data as a Python dictionary or list
    data = {"user": USER, "password": PASSWORD, "host": HOST, "port": PORT, "dbname": DBNAME}

    # Convert the Python object to a JSON formatted string
    json_string = json.dumps(data)

    # S3 bucket and object details
    bucket_name = f"zappa-tkd-competition-manager-{env}"
    object_key = "secrets.json"

    # Create an S3 client
    # Boto3 will automatically use credentials configured in your environment
    s3_client = boto3.client("s3")

    try:
        # Upload the JSON string directly to S3
        response = s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=json_string,
            ContentType="application/json",  # Set the content type
        )
        print(f"Successfully uploaded JSON object to s3://{bucket_name}/{object_key}")
        if debug:
            print(f"Response: {response}")

    except Exception as e:
        print(f"Error uploading object: {e}")


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "-e",
        "--env",
        choices=["dev", "prod"],
        default="dev",
        help="Environment to upload to",
    )
    argparser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        required=False,
        help="Enable debug mode",
    )
    args = argparser.parse_args()

    main(args.env, args.debug)
