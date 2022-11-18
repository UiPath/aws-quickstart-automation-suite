import boto3
import json
import cfnresponse
import threading
import math

# Platform is counted in the default value callculations
SERVICES_REQUIRMENTS_MAP = {
    "single_node": {
        'platform': {
            'cpu': 0,
            'ram': 0
        },
        'action_center': {
            'cpu': 0.7,
            'ram': 2.1
        },
        'aicenter': {
            'cpu': 2.0,
            'ram': 6.5,
        },
        'apps': {
            'cpu': 2.8,
            'ram': 7.2
        },
        'automation_hub': {
            'cpu': 0.5,
            'ram': 1.4
        },
        'automation_ops': {
            'cpu': 0.2,
            'ram': 0.7
        },
        'asrobots': {
            'cpu': 0.5,
            'ram': 0.7
        },
        'dataservice': {
            'cpu': 0.2,
            'ram': 0.5
        },
        'documentunderstanding': {
            'cpu': 3.2,
            'ram': 4.0
        },
        'insights': {
            'cpu': 0.3,
            'ram': 1.7
        },
        'orchestrator': {
            'cpu': 1.0,
            'ram': 2.6
        },
        'processmining': {
            'cpu': 2.2,
            'ram': 12.0
        },
        'task_mining': {
            'cpu': 4.0,
            'ram': 5.0
        },
        'test_manager': {
            'cpu': 0.5,
            'ram': 1.0
        }
    },
    "multi_node": {
        'platform': {
            'cpu': 0,
            'ram': 0
        },
        'action_center': {
            'cpu': 2.0,
            'ram': 4.7
        },
        'aicenter': {
            'cpu': 5.5,
            'ram': 14.0,
        },
        'apps': {
            'cpu': 7.25,
            'ram': 18.5
        },
        'automation_hub': {
            'cpu': 2.0,
            'ram': 3.5
        },
        'automation_ops': {
            'cpu': 1.0,
            'ram': 1.7
        },
        'asrobots': {
            'cpu': 1.0,
            'ram': 1.5
        },
        'dataservice': {
            'cpu': 0.5,
            'ram': 1.0
        },
        'documentunderstanding': {
            'cpu': 6.7,
            'ram': 8.6
        },
        'insights': {
            'cpu': 1.5,
            'ram': 5.0
        },
        'orchestrator': {
            'cpu': 3.5,
            'ram': 7.2
        },
        'processmining': {
            'cpu': 5.1,
            'ram': 24.0
        },
        'task_mining': {
            'cpu': 8.4,
            'ram': 10.0
        },
        'test_manager': {
            'cpu': 1.0,
            'ram': 2.0
        }
    }
}


def get_enabled_services_map(properties):
    enabled_services_map = {
        'platform' : True,
        'processmining': False,
        'orchestrator' : properties['Orchestrator'].lower() == "true",
        'action_center' : properties['ActionCenter'].lower() == "true",
        'test_manager' : properties['TestManager'].lower() == "true",
        'insights' : properties['Insights'].lower() == "true",
        'dataservice' : properties['DataService'].lower() == "true",
        'automation_hub' : properties['AutomationHub'].lower() == "true",
        'automation_ops' : properties['AutomationOps'].lower() == "true",
        'task_mining' : properties['TaskMining'].lower() == "true",
        'aicenter' : properties['AiCenter'].lower() == "true",
        'documentunderstanding' : properties['DocumentUnderstanding'].lower() == "true",
        'apps' : properties['BusinessApps'].lower() == "true",
        'asrobots' : properties['ASRobots'].lower() == "true"
    }
    print("Enabled services:")
    for service, status in enabled_services_map.items():
        print(f'{service} is enabled? {status}')
    return enabled_services_map

def get_cluster_requirments(is_multi_node: bool, enabled_services_map: dict):
    total_cpu = 40.0 if is_multi_node else 9.5
    total_ram = 47.6 if is_multi_node else 16.4
    services_requirments = SERVICES_REQUIRMENTS_MAP['multi_node'] if is_multi_node else SERVICES_REQUIRMENTS_MAP['single_node']

    for service, is_enabled in enabled_services_map.items():
        if is_enabled:
            print(f"For service {service} adding CPU { services_requirments[service]['cpu'] } to total {total_cpu}")
            print(f"For service {service} adding RAM { services_requirments[service]['ram'] } to total {total_ram}")
            total_cpu += services_requirments[service]['cpu']
            total_ram += services_requirments[service]['ram']
    return total_cpu, total_ram

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
    gpu = properties['AddGpu']
    return_attribute = dict()

    # datadisk size
    return_attribute["ServerDiskSize"] = 512
    if multi_node.lower() == 'multi node':
        is_multi_node = True
    else:
        is_multi_node = False

    core_multi_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m4.4xlarge"]
    ext_multi_node_types = ["c5a.8xlarge", "c5.9xlarge", "m5.8xlarge", "m5a.8xlarge"]
    core_single_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m5a.4xlarge"]
    ext_single_node_types = ["c5a.8xlarge", "c5.9xlarge", "m5.8xlarge"]
    tm_node_types = ["c5a.8xlarge", "c5.9xlarge", "c4.8xlarge"]
    asrobots_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m5a.4xlarge"]
    gpu_node_types = ["p3.2xlarge", "g4dn.4xlarge", "p2.xlarge", "g5.4xlarge"]
    
    enabled_services_map = get_enabled_services_map(properties)
    total_cpu, total_ram = get_cluster_requirments(is_multi_node, enabled_services_map)
    # Add a 20% procent buffer for the selection
    total_cpu *= 1.2
    total_ram *= 1.2
    min_cpu_per_node = 8
    min_ram_per_node = 16

    min_cpu_tm_node = 20
    min_ram_tm_node = 60

    min_cpu_asrobots_node = 16
    min_ram_asrobots_node = 32

    min_cpu_gpu_node = 8
    min_ram_gpu_node = 52
    min_gpu_ram_gpu_node = 11

    if is_multi_node:
        print("Getting instance types for multinode installation")
        if total_cpu <= 48:
            instance_obj = get_instance_from_list(types_list=core_multi_node_types, region=region)
        else:
            instance_obj = get_instance_from_list(types_list=ext_multi_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_per_node or instance_cpu < min_cpu_per_node:
            raise Exception("Minimum Instance HW requirements are not met")
        # There must be at least 3 servers in a multi-node deployment. As a result the # of nodes is >= 3
        initial_instance_count = max(int(math.ceil(total_cpu / instance_cpu)), int(math.ceil(total_ram / instance_ram)), 3)
        return_attribute["ServerInstanceCount"] = 3
        return_attribute["AgentInstanceCount"] = initial_instance_count - 3
        return_attribute["InstanceType"] = instance_obj['InstanceType']
    else:
        print("single node")
        if total_cpu <= 16:
            print("small vm needed")
            instance_obj = get_instance_from_list(types_list=core_single_node_types, region=region)
        else:
            print("big vm needed")
            instance_obj = get_instance_from_list(types_list=ext_single_node_types, region=region)
        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < total_ram or instance_cpu < total_cpu:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["ServerInstanceCount"] = 1
        return_attribute["AgentInstanceCount"] = 0
        return_attribute["InstanceType"] = instance_obj['InstanceType']

    if properties['TaskMining'].lower() == 'true':
        print("Adding Task Mining node")
        instance_obj = get_instance_from_list(types_list=tm_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_tm_node or instance_cpu < min_cpu_tm_node:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["TmInstanceType"] = instance_obj['InstanceType']
    else:
        return_attribute["TmInstanceType"] = ""

    print("Adding AS Robots node config")
    instance_obj = get_instance_from_list(types_list=asrobots_node_types, region=region)

    instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
    instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
    if instance_ram < min_ram_asrobots_node or instance_cpu < min_cpu_asrobots_node:
        raise Exception("Minimum Instance HW requirements are not met")
    return_attribute["ASRobotsInstanceType"] = instance_obj['InstanceType']

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
    gpu = properties['AddGpu']
    return_attribute = dict()

    # datadisk size
    return_attribute["ServerDiskSize"] = 512
    if multi_node.lower() == 'multi node':
        is_multi_node = True
    else:
        is_multi_node = False

    core_multi_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m4.4xlarge"]
    ext_multi_node_types = ["c5a.8xlarge", "c5.9xlarge", "m5.8xlarge", "m5a.8xlarge"]
    core_single_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m5a.4xlarge"]
    ext_single_node_types = ["c5a.8xlarge", "c5.9xlarge", "m5.8xlarge"]
    tm_node_types = ["c5a.8xlarge", "c5.9xlarge", "c4.8xlarge"]
    asrobots_node_types = ["c5.4xlarge", "c5a.4xlarge", "m5.4xlarge", "m5a.4xlarge"]
    gpu_node_types = ["p3.2xlarge", "g4dn.4xlarge", "p2.xlarge", "g5.4xlarge"]
    
    enabled_services_map = get_enabled_services_map(properties)
    total_cpu, total_ram = get_cluster_requirments(is_multi_node, enabled_services_map)
    # Add a 20% procent buffer for the selection
    total_cpu *= 1.2
    total_ram *= 1.2
    min_cpu_per_node = 8
    min_ram_per_node = 16

    min_cpu_tm_node = 20
    min_ram_tm_node = 60

    min_cpu_asrobots_node = 16
    min_ram_asrobots_node = 32

    min_cpu_gpu_node = 8
    min_ram_gpu_node = 52
    min_gpu_ram_gpu_node = 11

    if is_multi_node:
        print("Getting instance types for multinode installation")
        if total_cpu <= 48:
            instance_obj = get_instance_from_list(types_list=core_multi_node_types, region=region)
        else:
            instance_obj = get_instance_from_list(types_list=ext_multi_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_per_node or instance_cpu < min_cpu_per_node:
            raise Exception("Minimum Instance HW requirements are not met")
        # There must be at least 3 servers in a multi-node deployment. As a result the # of nodes is >= 3
        initial_instance_count = max(int(math.ceil(total_cpu / instance_cpu)), int(math.ceil(total_ram / instance_ram)), 3)
        return_attribute["ServerInstanceCount"] = 3
        return_attribute["AgentInstanceCount"] = initial_instance_count - 3
        return_attribute["InstanceType"] = instance_obj['InstanceType']
    else:
        print("single node")
        if total_cpu <= 16:
            print("small vm needed")
            instance_obj = get_instance_from_list(types_list=core_single_node_types, region=region)
        else:
            print("big vm needed")
            instance_obj = get_instance_from_list(types_list=ext_single_node_types, region=region)
        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < total_ram or instance_cpu < total_cpu:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["ServerInstanceCount"] = 1
        return_attribute["AgentInstanceCount"] = 0
        return_attribute["InstanceType"] = instance_obj['InstanceType']

    if properties['TaskMining'].lower() == 'true':
        print("Adding Task Mining node")
        instance_obj = get_instance_from_list(types_list=tm_node_types, region=region)

        instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
        instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
        if instance_ram < min_ram_tm_node or instance_cpu < min_cpu_tm_node:
            raise Exception("Minimum Instance HW requirements are not met")
        return_attribute["TmInstanceType"] = instance_obj['InstanceType']
    else:
        return_attribute["TmInstanceType"] = ""

    print("Adding AS Robots node config")
    instance_obj = get_instance_from_list(types_list=asrobots_node_types, region=region)

    instance_cpu = instance_obj["VCpuInfo"]['DefaultVCpus']
    instance_ram = instance_obj["MemoryInfo"]['SizeInMiB'] // 1024
    if instance_ram < min_ram_asrobots_node or instance_cpu < min_cpu_asrobots_node:
        raise Exception("Minimum Instance HW requirements are not met")
    return_attribute["ASRobotsInstanceType"] = instance_obj['InstanceType']

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
        timer.cancel()
        cfnresponse.send(event, context, status, returnAttribute, new_physical_id)
