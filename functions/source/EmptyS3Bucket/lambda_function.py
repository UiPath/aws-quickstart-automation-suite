import boto3
import json
import cfnresponse
import threading


def create(properties, physical_id):
    bucket_names = properties['BucketNames']
    print(f'Creating buckets {bucket_names} ...')
    return_attribute = dict(Action='CREATE')
    return cfnresponse.SUCCESS, physical_id, return_attribute


def update(properties, physical_id):
    bucket_names = physical_id
    print(f'Updating bucket {bucket_names} ...')
    return_attribute = dict(Action='UPDATE')
    return cfnresponse.SUCCESS, physical_id, return_attribute


def delete(properties, physical_id):
    bucket_names = properties['BucketNames']
    print(f'Deleting objects in buckets: {bucket_names} ...')
    print(properties)
    s3 = boto3.resource('s3')
    for bucket_name in bucket_names:
        bucket = s3.Bucket(bucket_name)
        bucket.object_versions.delete()
        print(f'Bucket {bucket_name} emptied.')
    return_attribute = dict(Action='DELETE')
    return cfnresponse.SUCCESS, physical_id, return_attribute


def timeout(event, context):
    print('Execution is about to time out, sending failure response to CloudFormation')
    cfnresponse.send(event, context, cfnresponse.FAILED, {}, None)


def handler(event, context):
    # make sure we send a failure to CloudFormation if the function is going to timeout
    timer = threading.Timer((context.get_remaining_time_in_millis() / 1000.00) - 0.5, timeout, args=[event, context])
    timer.start()
    print('Received event: ' + json.dumps(event))
    status = cfnresponse.FAILED
    new_physical_id = None
    return_attribute = {}
    try:
        properties = event.get('ResourceProperties')
        physical_id = event.get('PhysicalResourceId')
        status, new_physical_id, return_attribute = {
            'Create': create,
            'Update': update,
            'Delete': delete
        }.get(event['RequestType'], lambda x, y: (cfnresponse.FAILED, None))(properties, physical_id)
    except Exception as e:
        print('Exception: ' + str(e))
        status = cfnresponse.FAILED
    finally:
        cfnresponse.send(event, context, status, return_attribute, new_physical_id)