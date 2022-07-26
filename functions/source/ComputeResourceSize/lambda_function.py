import boto3
import json
import cfnresponse
import threading
import math


def get_instance_from_list(types_list: list, region: str) -> dict:
    ec2 = boto3.client('ec2', region_name=region)
    type_offerings = ec2.describe_instance_type_offerings(
        LocationType='region',
        Filters=[
            {
                'Name': 'location',
                'Values': [region]
            },
            {
                'Name': 'instance-type',
                'Values': types_list
            }
        ]
    )
    print("Available instance types:")
    print(json.dumps(type_offerings))
    available_types = [crt_type['InstanceType'] for crt_type in type_offerings['InstanceTypeOfferings']]
    print("Available instance types, short list:")
    print(available_types)
    if not available_types:
        raise Exception("No offerings available in the region")
    types = ec2.describe_instance_types(
        InstanceTypes=available_types,
        Filters=[
            {
                'Name': 'supported-virtualization-type',
                'Values': ['hvm']
            }
        ]
    )
    print(json.dumps(types))
    if not types['InstanceTypes']:
        raise Exception("No types available in the region")

    for ret_type in types_list:
        if ret_type in available_types:
            return [crt_type for crt_type in types['InstanceTypes'] if crt_type["InstanceType"] == ret_type][0]


def create(properties, physical_id):
    region = properties["RegionName"]
    multi_node = properties["MultiNode"]
    action_center = properties['ActionCenter']
    test_manager = properties['TestManager']
    insights = properties['Insights']
    automation_hub = properties['AutomationHub']
    automation_ops = properties['AutomationOps']
    task_mining = properties['TaskMining']
    ai_center = properties['AiCenter']
    du = properties['DocumentUnderstanding']
    apps = properties['BusinessApps']
    gpu = properties['AddGpu']
    return_attribute = dict()

    # datadisk size
    if task_mining.lower() == "true" or du.lower() == "true" or \
            ai_center.lower() == "true" or apps.lower() == "true":
        return_attribute["ServerDiskSize"] = 2048
    else:
        return_attribute["ServerDiskSize"] = 512

    if apps.lower() == 'true' or ai_center.lower() == 'true' or \
            du.lower() == 'true' or task_mining.lower() == 'true':
        is_core_platform = False
    else:
        is_core_platform = True

    if multi_node.lower() == 'multi node':
        is_multi_node = True
    else:
        is_multi_node = False

    core_multi_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m4.4xlarge"]
    ext_multi_node_types = ["c5a.8xlarge", "c5.9xlarge", "m5.8xlarge", "m5a.8xlarge"]
    core_single_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m5a.4xlarge"]
    ext_single_node_types = ["c5a.8xlarge", "c5.9xlarge", "m5.8xlarge"]
    tm_node_types = ["c5a.8xlarge", "c5.9xlarge", "c4.8xlarge"]
    gpu_node_types = ["p3.2xlarge", "g4dn.4xlarge", "p2.xlarge", "g5.4xlarge"]

    if is_multi_node:
        if is_core_platform:
            total_cpu = 48
            total_ram = 96
            min_cpu_per_node = 16
            min_ram_per_node = 32
        else:
            total_cpu = 96
            total_ram = 192
            min_cpu_per_node = 16
            min_ram_per_node = 32
    else:
        if is_core_platform:
            total_cpu = 16
            total_ram = 32
            min_cpu_per_node = 16
            min_ram_per_node = 32
        else:
            total_cpu = 32
            total_ram = 64
            min_cpu_per_node = 32
            min_ram_per_node = 64

    min_cpu_tm_node = 20
    min_ram_tm_node = 60

    min_cpu_gpu_node = 8
    min_ram_gpu_node = 52
    min_gpu_ram_gpu_node = 11

    if is_multi_node:
        print("Getting instance types for multi node installation")
        if is_core_platform:
            print("core platform")
            instance_obj = get_instance_from_list(types_list=core_multi_node_types, region=region)
        else:
            print("extended platform")
            instance_obj = get_instance_from_list(types_list=ext_multi_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_per_node or instance_cpu < min_cpu_per_node:
            raise Exception("Minimum Instance HW requirements are not met")
        initial_instance_count = max(int(math.ceil(total_cpu / instance_cpu)), int(math.ceil(total_ram / instance_ram)))
        return_attribute["ServerInstanceCount"] = 3
        return_attribute["AgentInstanceCount"] = initial_instance_count - 3
        return_attribute["InstanceType"] = instance_obj['InstanceType']
    else:
        print("Getting instance types for single node installation")
        if is_core_platform:
            print("core platform")
            instance_obj = get_instance_from_list(types_list=core_single_node_types, region=region)
        else:
            print("extended platform")
            instance_obj = get_instance_from_list(types_list=ext_single_node_types, region=region)
        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024

        if instance_ram < total_ram or instance_cpu < total_cpu:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["ServerInstanceCount"] = 1
        return_attribute["AgentInstanceCount"] = 0
        return_attribute["InstanceType"] = instance_obj['InstanceType']

    if task_mining.lower() == 'true':
        print("Adding Task Mining node")
        instance_obj = get_instance_from_list(types_list=tm_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_tm_node or instance_cpu < min_cpu_tm_node:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["TmInstanceType"] = instance_obj['InstanceType']
    else:
        return_attribute["TmInstanceType"] = ""

    if gpu.lower() == 'true':
        print("Adding Gpu node")
        instance_obj = get_instance_from_list(types_list=gpu_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        instance_gpu_ram = instance_obj["GpuInfo"]['Gpus'][0]['MemoryInfo']['SizeInMiB'] // 1024
        if instance_ram < min_ram_gpu_node or instance_cpu < min_cpu_gpu_node or instance_gpu_ram < min_gpu_ram_gpu_node:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["GpuInstanceType"] = instance_obj['InstanceType']
    else:
        return_attribute["GpuInstanceType"] = ""

    return_attribute['Action'] = 'CREATE'
    return cfnresponse.SUCCESS, physical_id, return_attribute


def update(properties, physical_id):
    region = properties["RegionName"]
    multi_node = properties["MultiNode"]
    action_center = properties['ActionCenter']
    test_manager = properties['TestManager']
    insights = properties['Insights']
    automation_hub = properties['AutomationHub']
    automation_ops = properties['AutomationOps']
    task_mining = properties['TaskMining']
    ai_center = properties['AiCenter']
    du = properties['DocumentUnderstanding']
    apps = properties['BusinessApps']
    gpu = properties['AddGpu']
    return_attribute = dict()

    # datadisk size
    if task_mining.lower() == "true" or du.lower() == "true" or \
            ai_center.lower() == "true" or apps.lower() == "true":
        return_attribute["ServerDiskSize"] = 2048
    else:
        return_attribute["ServerDiskSize"] = 512

    if apps.lower() == 'true' or ai_center.lower() == 'true' or \
            du.lower() == 'true' or task_mining.lower() == 'true':
        is_core_platform = False
    else:
        is_core_platform = True

    if multi_node.lower() == 'multi node':
        is_multi_node = True
    else:
        is_multi_node = False

    core_multi_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m4.4xlarge"]
    ext_multi_node_types = ["c5a.8xlarge", "c5.9xlarge", "m5.8xlarge", "m5a.8xlarge"]
    core_single_node_types = ["m5.4xlarge", "m5a.4xlarge", "r5.4xlarge", "r5a.4xlarge"]
    ext_single_node_types = ["c5.12xlarge", "c5a.12xlarge", "m5.12xlarge"]
    tm_node_types = ["c5a.8xlarge", "c5.9xlarge", "c4.8xlarge"]
    gpu_node_types = ["p3.2xlarge"]

    if is_multi_node:
        if is_core_platform:
            total_cpu = 48
            total_ram = 96
            min_cpu_per_node = 16
            min_ram_per_node = 32
        else:
            total_cpu = 100
            total_ram = 224
            min_cpu_per_node = 16
            min_ram_per_node = 32
    else:
        if is_core_platform:
            total_cpu = 16
            total_ram = 32
            min_cpu_per_node = 16
            min_ram_per_node = 32
        else:
            total_cpu = 36
            total_ram = 96
            min_cpu_per_node = 36
            min_ram_per_node = 96

    min_cpu_tm_node = 20
    min_ram_tm_node = 60

    min_cpu_gpu_node = 8
    min_ram_gpu_node = 52
    min_gpu_ram_gpu_node = 11

    if is_multi_node:
        print("Getting instance types for multinode installation")
        if is_core_platform:
            instance_obj = get_instance_from_list(types_list=core_multi_node_types, region=region)
        else:
            instance_obj = get_instance_from_list(types_list=ext_multi_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_per_node or instance_cpu < min_cpu_per_node:
            raise Exception("Minimum Instance HW requirements are not met")
        initial_instance_count = max(int(math.ceil(total_cpu / instance_cpu)), int(math.ceil(total_ram / instance_ram)))
        return_attribute["ServerInstanceCount"] = 3
        return_attribute["AgentInstanceCount"] = initial_instance_count - 3
        return_attribute["InstanceType"] = instance_obj['InstanceType']
    else:
        print("single node")
        if is_core_platform:
            print("core platform")
            instance_obj = get_instance_from_list(types_list=core_single_node_types, region=region)
        else:
            print("extended platform")
            instance_obj = get_instance_from_list(types_list=ext_single_node_types, region=region)
        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024

        if instance_ram < total_ram or instance_cpu < total_cpu:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["ServerInstanceCount"] = 1
        return_attribute["AgentInstanceCount"] = 0
        return_attribute["InstanceType"] = instance_obj['InstanceType']

    if task_mining.lower() == 'true':
        print("Adding Task Mining node")
        instance_obj = get_instance_from_list(types_list=tm_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_tm_node or instance_cpu < min_cpu_tm_node:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["TmInstanceType"] = instance_obj['InstanceType']
    else:
        return_attribute["TmInstanceType"] = ""

    if gpu.lower() == 'true':
        print("Adding Gpu node")
        instance_obj = get_instance_from_list(types_list=gpu_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        instance_gpu_ram = instance_obj["GpuInfo"]['Gpus'][0]['MemoryInfo']['SizeInMiB'] // 1024
        if instance_ram < min_ram_gpu_node or instance_cpu < min_cpu_gpu_node or instance_gpu_ram < min_gpu_ram_gpu_node:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["GpuInstanceType"] = instance_obj['InstanceType']
    else:
        return_attribute["GpuInstanceType"] = ""

    return_attribute['Action'] = 'UPDATE'
    return cfnresponse.SUCCESS, physical_id, return_attribute


def delete(properties, physical_id):
    return_attribute = {'Action': 'DELETE'}
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
        cfnresponse.send(event, context, status, returnAttribute, new_physical_id)
