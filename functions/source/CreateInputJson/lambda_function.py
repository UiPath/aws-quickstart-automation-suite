import boto3
import json
import cfnresponse
import threading
import uuid
import random
import string


def create(properties, physical_id):
    region = properties["RegionName"]
    secret_arn = properties["TargetSecretArn"]
    db_password_secret_arn = properties["RDSPasswordSecretArn"]
    platform_secret_arn = properties['PlatformSecretArn']
    org_secret_arn = properties['OrgSecretArn']
    argocd_secret_arn = properties['ArgoCdSecretArn']
    argocd_user_secret_arn = properties['ArgoCdUserSecretArn']
    fqdn = properties["Fqdn"]
    db_endpoint = properties["RDSDBInstanceEndpointAddress"]
    multi_node = properties["MultiNode"]
    internal_load_balancer_dns = properties["KubeLoadBalancerDns"]
    action_center = properties['ActionCenter']
    test_manager = properties['TestManager']
    insights = properties['Insights']
    data_service = properties['DataService']
    automation_hub = properties['AutomationHub']
    automation_ops = properties['AutomationOps']
    task_mining = properties['TaskMining']
    ai_center = properties['AiCenter']
    du = properties['DocumentUnderstanding']
    apps = properties['BusinessApps']
    add_gpu = properties['AddGpu']
    server_instance_count = int(properties['ServerInstanceCount'])
    agent_instance_count = int(properties['AgentInstanceCount'])
    private_subnet_ids = properties['PrivateSubnetIDs']
    extra_dict_keys = properties['ExtraConfigKeys']
    self_signed_cert_validity = properties['SelfSignedCertificateValidity']

    initial_number_of_instances = server_instance_count + agent_instance_count

    ret = {"fqdn": fqdn, "rke_token": str(uuid.uuid4())}
    ret['cloud_template_vendor'] = 'AWS'
    ret['cloud_template_source'] = 'Quickstart'

    ret['fixed_rke_address'] = internal_load_balancer_dns
    if multi_node.lower() == 'multi node':
        ret['profile'] = 'ha'
        subnet_list = private_subnet_ids.split(',')
        if len(subnet_list) >= 3:
            ret['zone_resilience'] = True
        else:
            ret['zone_resilience'] = False
    else:
        ret['profile'] = 'default'

    if add_gpu.lower() == 'true':
        initial_number_of_instances += 1

    sm = boto3.client('secretsmanager', region_name=region)

    print("Getting Platform secret")
    db_secret = sm.get_secret_value(
        SecretId=platform_secret_arn
    )
    secret = json.loads(db_secret['SecretString'])
    print("Adding Platform username and password to JSON")
    ret["admin_username"] = secret['username']
    ret["admin_password"] = secret['password']

    print("Adding the org secret")
    sm.put_secret_value(
        SecretId=org_secret_arn,
        SecretString=json.dumps({"username": "orgadmin", "password": secret['password']})
    )

    print("Getting ArgoCD secret")
    argocd_secret = sm.get_secret_value(
        SecretId=argocd_secret_arn
    )
    secret = json.loads(argocd_secret['SecretString'])
    print("Adding ArgoCD username and password to JSON")
    ret['fabric'] = {"argocd_admin_password": secret['password']}

    print("Getting ArgoCD readonly User secret")
    argocd_user_secret = sm.get_secret_value(
        SecretId=argocd_user_secret_arn
    )
    secret = json.loads(argocd_user_secret['SecretString'])
    print("Adding ArgoCD readonly user's password to JSON")
    ret['fabric']["argocd_user_password"] = secret['password']

    # fix issue with non existing server certificates file
    ret["server_certificate"] = {}
    ret["server_certificate"]["ca_cert_file"] = "/root/rootCA.crt"
    ret["server_certificate"]["tls_cert_file"] = "/root/server.crt"
    ret["server_certificate"]["tls_key_file"] = "/root/server.key"

    ret["identity_certificate"] = {}
    ret["identity_certificate"]["token_signing_cert_file"] = "/root/token_signing_certificate.pfx"
    ret["identity_certificate"]["token_signing_cert_pass"] = ''.join(random.choice(string.ascii_letters) for i in range(20))
    ret["identity_certificate"]["ldap_cert_authority_file"] = ""

    ret['self_signed_cert_validity'] = self_signed_cert_validity

    if extra_dict_keys:
        try:
            extra_dict_json = json.loads(extra_dict_keys)
            print(json.dumps(extra_dict_json))
        except Exception as e:
            print("Failed to load the extra configuration dictionary")
            raise e

        if extra_dict_json:
            ret.update(extra_dict_json)

    print("Getting RDS secret")
    db_secret = sm.get_secret_value(
        SecretId=db_password_secret_arn
    )
    secret = json.loads(db_secret['SecretString'])
    ret["sql"] = {}
    ret["sql"]["create_db"] = True

    dot_net_escaped_password = secret['password'].replace("'", "''")
    odbc_escaped_password = secret['password'].replace("}", "}}")

    print("Adding SQL connection strings to JSON")
    ret["sql_connection_string_template"] = f"Server=tcp:{db_endpoint},1433;Initial Catalog=DB_NAME_PLACEHOLDER;Persist Security Info=False;User Id={secret['username']};Password='{dot_net_escaped_password}';MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=True;Connection Timeout=30;Max Pool Size=100;"
    ret["sql_connection_string_template_jdbc"] = f"jdbc:sqlserver://{db_endpoint};database=DB_NAME_PLACEHOLDER;user={secret['username']};password={{{odbc_escaped_password}}}"
    ret["sql_connection_string_template_odbc"] = f"SERVER={db_endpoint};DATABASE=DB_NAME_PLACEHOLDER;DRIVER={{ODBC Driver 17 for SQL Server}};UID={secret['username']};PWD={{{odbc_escaped_password}}}"

    ret['orchestrator'] = {}
    ret['orchestrator']['testautomation'] = {"enabled": True}
    ret['orchestrator']['updateserver'] = {"enabled": True}

    if automation_hub.lower() == "true":
        ret['automation_hub'] = {"enabled": True}
    else:
        ret['automation_hub'] = {"enabled": False}

    if automation_ops.lower() == "true":
        ret['automation_ops'] = {"enabled": True}
    else:
        ret['automation_ops'] = {"enabled": False}

    if action_center.lower() == "true":
        ret['action_center'] = {"enabled": True}
    else:
        ret['action_center'] = {"enabled": False}

    if data_service.lower() == "true":
        ret['dataservice'] = {"enabled": True}
    else:
        ret['dataservice'] = {"enabled": False}

    if test_manager.lower() == "true":
        ret['test_manager'] = {"enabled": True}
    else:
        ret['test_manager'] = {"enabled": False}

    if insights.lower() == "true":
        ret['insights'] = {"enabled": True}
    else:
        ret['insights'] = {"enabled": False}

    if apps.lower() == "true":
        ret['apps'] = {"enabled": True}
    else:
        ret['apps'] = {"enabled": False}

    if task_mining.lower() == "true":
        ret['task_mining'] = {"enabled": True}
        initial_number_of_instances += 1
    else:
        ret['task_mining'] = {
            "enabled": False
        }

    if ai_center.lower() == "true":
        ret['aicenter'] = {
            "enabled": True
        }
    else:
        ret['aicenter'] = {"enabled": False}

    if du.lower() == "true":
        ret['documentunderstanding'] = {
            "enabled": True,
            "handwriting": {
                "enabled": "true",
                "max_cpu_per_pod": 2
            }
        }
    else:
        ret['documentunderstanding'] = {"enabled": False}

    ret["initial_number_of_instances"] = initial_number_of_instances

    sm.put_secret_value(
        SecretId=secret_arn,
        SecretString=json.dumps(ret)
    )
    return_attribute = dict()
    return_attribute['Action'] = 'CREATE'
    return cfnresponse.SUCCESS, secret_arn, return_attribute


def update(properties, physical_id):
    region = properties["RegionName"]
    secret_arn = properties["TargetSecretArn"]
    db_password_secret_arn = properties["RDSPasswordSecretArn"]
    platform_secret_arn = properties['PlatformSecretArn']
    org_secret_arn = properties['OrgSecretArn']
    argocd_secret_arn = properties['ArgoCdSecretArn']
    argocd_user_secret_arn = properties['ArgoCdUserSecretArn']
    fqdn = properties["Fqdn"]
    db_endpoint = properties["RDSDBInstanceEndpointAddress"]
    multi_node = properties["MultiNode"]
    internal_load_balancer_dns = properties["KubeLoadBalancerDns"]
    action_center = properties['ActionCenter']
    data_service = properties['DataService']
    test_manager = properties['TestManager']
    insights = properties['Insights']
    automation_hub = properties['AutomationHub']
    automation_ops = properties['AutomationOps']
    task_mining = properties['TaskMining']
    ai_center = properties['AiCenter']
    du = properties['DocumentUnderstanding']
    apps = properties['BusinessApps']
    add_gpu = properties['AddGpu']
    server_instance_count = int(properties['ServerInstanceCount'])
    agent_instance_count = int(properties['AgentInstanceCount'])
    private_subnet_ids = properties['PrivateSubnetIDs']
    extra_dict_keys = properties['ExtraConfigKeys']
    self_signed_cert_validity = properties['SelfSignedCertificateValidity']

    initial_number_of_instances = server_instance_count + agent_instance_count

    ret = {"fqdn": fqdn, "rke_token": str(uuid.uuid4())}
    ret['cloud_template_vendor'] = 'AWS'
    ret['cloud_template_source'] = 'Quickstart'

    ret['fixed_rke_address'] = internal_load_balancer_dns
    if multi_node.lower() == 'multi node':
        ret['profile'] = 'ha'
        subnet_list = private_subnet_ids.split(',')
        if len(subnet_list) >= 3:
            ret['zone_resilience'] = True
        else:
            ret['zone_resilience'] = False
    else:
        ret['profile'] = 'default'

    if add_gpu.lower() == 'true':
        initial_number_of_instances += 1

    sm = boto3.client('secretsmanager', region_name=region)

    print("Getting Platform secret")
    db_secret = sm.get_secret_value(
        SecretId=platform_secret_arn
    )
    secret = json.loads(db_secret['SecretString'])
    print("Adding Platform username and password to JSON")
    ret["admin_username"] = secret['username']
    ret["admin_password"] = secret['password']

    print("Adding the org secret")
    sm.put_secret_value(
        SecretId=org_secret_arn,
        SecretString=json.dumps({"username": "orgadmin", "password": secret['password']})
    )

    print("Getting ArgoCD secret")
    argocd_secret = sm.get_secret_value(
        SecretId=argocd_secret_arn
    )
    secret = json.loads(argocd_secret['SecretString'])
    print("Adding ArgoCD username and password to JSON")
    ret['fabric'] = {"argocd_admin_password": secret['password']}

    print("Getting ArgoCD readonly User secret")
    argocd_user_secret = sm.get_secret_value(
        SecretId=argocd_user_secret_arn
    )
    secret = json.loads(argocd_user_secret['SecretString'])
    print("Adding ArgoCD readonly user's password to JSON")
    ret['fabric']["argocd_user_password"] = secret['password']

    # fix issue with non existing server certificates file
    ret["server_certificate"] = {}
    ret["server_certificate"]["ca_cert_file"] = "/root/rootCA.crt"
    ret["server_certificate"]["tls_cert_file"] = "/root/server.crt"
    ret["server_certificate"]["tls_key_file"] = "/root/server.key"

    ret["identity_certificate"] = {}
    ret["identity_certificate"]["token_signing_cert_file"] = "/root/token_signing_certificate.pfx"
    ret["identity_certificate"]["token_signing_cert_pass"] = ''.join(random.choice(string.ascii_letters) for i in range(20))
    ret["identity_certificate"]["ldap_cert_authority_file"] = ""

    ret['self_signed_cert_validity'] = self_signed_cert_validity

    if extra_dict_keys:
        try:
            extra_dict_json = json.loads(extra_dict_keys)
            print(json.dumps(extra_dict_json))
        except Exception as e:
            print("Failed to load the extra configuration dictionary")
            raise e

        if extra_dict_json:
            ret.update(extra_dict_json)

    print("Getting RDS secret")
    db_secret = sm.get_secret_value(
        SecretId=db_password_secret_arn
    )
    secret = json.loads(db_secret['SecretString'])
    ret["sql"] = {}
    ret["sql"]["create_db"] = True

    dot_net_escaped_password = secret['password'].replace("'", "''")
    odbc_escaped_password = secret['password'].replace("}", "}}")

    print("Adding SQL connection strings to JSON")
    ret["sql_connection_string_template"] = f"Server=tcp:{db_endpoint},1433;Initial Catalog=DB_NAME_PLACEHOLDER;Persist Security Info=False;User Id={secret['username']};Password='{dot_net_escaped_password}';MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=True;Connection Timeout=30;Max Pool Size=100;"
    ret["sql_connection_string_template_jdbc"] = f"jdbc:sqlserver://{db_endpoint};database=DB_NAME_PLACEHOLDER;user={secret['username']};password={{{odbc_escaped_password}}}"
    ret["sql_connection_string_template_odbc"] = f"SERVER={db_endpoint};DATABASE=DB_NAME_PLACEHOLDER;DRIVER={{ODBC Driver 17 for SQL Server}};UID={secret['username']};PWD={{{odbc_escaped_password}}}"

    ret['orchestrator'] = {}
    ret['orchestrator']['testautomation'] = {"enabled": True}
    ret['orchestrator']['updateserver'] = {"enabled": True}

    if automation_hub.lower() == "true":
        ret['automation_hub'] = {"enabled": True}
    else:
        ret['automation_hub'] = {"enabled": False}

    if automation_ops.lower() == "true":
        ret['automation_ops'] = {"enabled": True}
    else:
        ret['automation_ops'] = {"enabled": False}

    if action_center.lower() == "true":
        ret['action_center'] = {"enabled": True}
    else:
        ret['action_center'] = {"enabled": False}

    if data_service.lower() == "true":
        ret['dataservice'] = {"enabled": True}
    else:
        ret['dataservice'] = {"enabled": False}

    if test_manager.lower() == "true":
        ret['test_manager'] = {"enabled": True}
    else:
        ret['test_manager'] = {"enabled": False}

    if insights.lower() == "true":
        ret['insights'] = {"enabled": True}
    else:
        ret['insights'] = {"enabled": False}

    if apps.lower() == "true":
        ret['apps'] = {"enabled": True}
    else:
        ret['apps'] = {"enabled": False}

    if task_mining.lower() == "true":
        ret['task_mining'] = {"enabled": True}
        initial_number_of_instances += 1
    else:
        ret['task_mining'] = {
            "enabled": False
        }

    if ai_center.lower() == "true":
        ret['aicenter'] = {
            "enabled": True
        }
    else:
        ret['aicenter'] = {"enabled": False}

    if du.lower() == "true":
        ret['documentunderstanding'] = {
            "enabled": True,
            "handwriting": {
                "enabled": "true",
                "max_cpu_per_pod": 2
            }
        }
    else:
        ret['documentunderstanding'] = {"enabled": False}

    ret["initial_number_of_instances"] = initial_number_of_instances

    sm.put_secret_value(
        SecretId=secret_arn,
        SecretString=json.dumps(ret)
    )
    return_attribute = dict()
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
