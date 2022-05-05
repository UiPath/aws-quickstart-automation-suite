import boto3
import json
import cfnresponse


def create(properties, physical_id):
    region = properties["RegionName"]
    image_name = properties["ImageName"]
    architecture = properties["Architecture"]
    virtualization_type = properties["VirtualizationType"]
    owners = properties["Owners"]
    image_id = ""
    ec2 = boto3.client("ec2", region)
    images = ec2.describe_images(
        ExecutableUsers=["all"],
        Filters=[
            {"Name": "name", "Values": [image_name]},
            {"Name": "state", "Values": ["available"]},
            {"Name": "architecture", "Values": [architecture]},
            {"Name": "virtualization-type", "Values": [virtualization_type]}
        ],
        Owners=[owners]
    )["Images"]
    if len(images) > 0:
        image_id = images[0]["ImageId"]
    print(region, image_id)
    return_attribute = {}
    return_attribute["ImageId"] = image_id
    return_attribute["Action"] = "CREATE"
    return cfnresponse.SUCCESS, image_id, return_attribute


def update(properties, physical_id):
    image_id = physical_id
    return_attribute = {}
    return_attribute["ImageId"] = image_id
    return_attribute["Action"] = "UPDATE"
    return cfnresponse.SUCCESS, image_id, return_attribute


def delete(properties, physical_id):
    image_id = physical_id
    return_attribute = {}
    return_attribute["ImageId"] = image_id
    return_attribute["Action"] = "DELETE"
    return cfnresponse.SUCCESS, image_id, return_attribute


def handler(event, context):
    print("Received event: " + json.dumps(event))
    status = cfnresponse.FAILED
    new_physical_id = None
    return_attribute = {}
    try:
        properties = event.get("ResourceProperties")
        physical_id = event.get("PhysicalResourceId")
        status, new_physical_id, return_attribute = {
            "Create": create,
            "Update": update,
            "Delete": delete
        }.get(event["RequestType"], lambda x, y: (cfnresponse.FAILED, None))(properties, physical_id)
    except Exception as e:
        print("Exception: " + str(e))
        status = cfnresponse.FAILED
    finally:
        cfnresponse.send(event, context, status, return_attribute, new_physical_id)
