import json
import os

import boto3


tagging = boto3.client("resourcegroupstaggingapi")
sns = boto3.client("sns")

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")


def lambda_handler(event, context):

    print("===== AUTO TAGGER STARTED =====")

    print("Received event:")
    print(json.dumps(event, indent=2))

    # Get CloudTrail event details
    detail = event.get("detail", {})

    # Ignore failed API calls and DryRun operations
    error_code = detail.get("errorCode")

    if error_code:
        print(f"API call was not successful: {error_code}")
        print("Ignoring event.")

        return {
            "statusCode": 200,
            "message": f"Ignored unsuccessful API call: {error_code}"
        }

    # Safely get responseElements
    response_elements = detail.get("responseElements") or {}

    instances_set = response_elements.get("instancesSet") or {}

    items = instances_set.get("items") or []

    print(f"Found EC2 instances: {items}")

    if not items:

        print("No EC2 instances found.")

        return {
            "statusCode": 200,
            "message": "No EC2 instances found"
        }

    region = event["region"]
    account_id = event["account"]

    instance_arns = []

    for instance in items:

        instance_id = instance.get("instanceId")

        if not instance_id:
            continue

        arn = (
            f"arn:aws:ec2:{region}:{account_id}"
            f":instance/{instance_id}"
        )

        instance_arns.append(arn)

    print(f"Instance ARNs: {instance_arns}")

    if not instance_arns:

        print("No valid instance ARNs found.")

        return {
            "statusCode": 200,
            "message": "No valid instances found"
        }

    # Standard tags
    tags = {
        "Environment": "dev",
        "Owner": "devops",
        "Project": "auto-tagging",
        "ManagedBy": "lambda"
    }

    print(f"Applying tags: {tags}")

    try:

        response = tagging.tag_resources(
            ResourceARNList=instance_arns,
            Tags=tags
        )

        print("Tagging response:")
        print(json.dumps(response, default=str))

        # Send SNS notification if configured
        if SNS_TOPIC_ARN:

            message = {
                "resources": instance_arns,
                "tags": tags,
                "failed": response.get(
                    "FailedResourcesMap",
                    {}
                )
            }

            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject="AWS Auto Tagger Result",
                Message=json.dumps(
                    message,
                    indent=2
                )
            )

            print("SNS notification sent.")

        else:

            print("SNS_TOPIC_ARN is not configured.")

        return {
            "statusCode": 200,
            "tagged_resources": instance_arns
        }

    except Exception as e:

        print(f"ERROR while tagging resources: {str(e)}")

        raise
