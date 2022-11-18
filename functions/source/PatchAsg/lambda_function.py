import boto3
import json
import cfnresponse
import threading


def create(properties, physical_id):
    asg_name = properties['AutoScalingGroupName']
    region = properties['RegionName']

    client = boto3.client('autoscaling', region_name=region)
    response = client.suspend_processes(
        AutoScalingGroupName=asg_name,
        ScalingProcesses=['Terminate', 'Launch']
    )
    print(json.dumps(response, indent=2))

    return_attribute = dict()

    return_attribute['Action'] = 'CREATE'
    return cfnresponse.SUCCESS, asg_name, return_attribute


def update(properties, physical_id):
    asg_name = properties['AutoScalingGroupName']
    region = properties['RegionName']

    client = boto3.client('autoscaling', region_name=region)
    response = client.suspend_processes(
        AutoScalingGroupName=asg_name,
        ScalingProcesses=['Terminate', 'Launch']
    )
    print(json.dumps(response, indent=2))

    return_attribute = dict()

    return_attribute['Action'] = 'UPDATE'
    return cfnresponse.SUCCESS, physical_id, return_attribute


def delete(properties, physical_id):
    asg_name = properties['AutoScalingGroupName']
    region = properties['RegionName']

    client = boto3.client('autoscaling', region_name=region)
    response = client.resume_processes(
        AutoScalingGroupName=asg_name,
        ScalingProcesses=['Terminate', 'Launch']
    )
    print(json.dumps(response, indent=2))

    return_attribute = dict()

    return_attribute['Action'] = 'DELETE'
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
    returnAttribute = {}
    try:
        properties = event.get('ResourceProperties')
        physical_id = event.get('PhysicalResourceId')
        status, new_physical_id, returnAttribute = {
            'Create': create,
            'Update': update,
            'Delete': delete
        }.get(event['RequestType'], lambda x, y: (cfnresponse.FAILED, None))(properties, physical_id)
    except Exception as e:
        print('Exception: ' + str(e))
        status = cfnresponse.FAILED
    finally:
        timer.cancel()
        cfnresponse.send(event, context, status, returnAttribute, new_physical_id)
