import boto3
import json
import cfnresponse
import threading
import uuid
import random
import string
import base64
from urllib.parse import quote

AICENTER_EXTERNAL_IDENTITY_CERT_PATH = "/root/installer/identity.cer"
AICENTER_EXTERNAL_ORCH_CERT_PATH = "/root/installer/orchestrator.cer"

def get_enabled_services_map(properties):
    enabled_services_map = {
        'platform' : True,
        'processmining': properties['ProcessMining'].lower() == "true",
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


def check_certificate(service, base64_encoded_cert):
    if not base64_encoded_cert:
        print(f"{service} certificate not provided.")
        raise Exception("Certificate missing")
    try:
        base64.b64decode(base64_encoded_cert, validate=True)
    except Exception as e:
        print("Failed to decode base64 certificate provided")
        raise e

def check_ai_center_external_certificates(properties: dict):
    check_certificate("Orchestrator", properties['OrchestratorCertificate'])
    check_certificate("Identity", properties['IdentityCertificate'])


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
    pm_db_endpoint = properties["PMRDSDBInstanceEndpointAddress"]
    multi_node = properties["MultiNode"]
    internal_load_balancer_dns = properties["KubeLoadBalancerDns"]
    add_gpu = properties['AddGpu']
    server_instance_count = int(properties['ServerInstanceCount'])
    agent_instance_count = int(properties['AgentInstanceCount'])
    private_subnet_ids = properties['PrivateSubnetIDs']
    extra_dict_keys = properties['ExtraConfigKeys']
    self_signed_cert_validity = properties['SelfSignedCertificateValidity']
    use_external_orchestrator = properties['UseExternalOrchestrator']
    orchestrator_url = properties['OrchestratorURL']
    identity_url = properties['IdentityURL']
    initial_number_of_instances = server_instance_count + agent_instance_count

    enabled_services_map = get_enabled_services_map(properties)
    if use_external_orchestrator.lower() == "true":
        check_ai_center_external_certificates(properties)

    ret = {"fqdn": fqdn, "rke_token": str(uuid.uuid4())}
    ret['cloud_template_vendor'] = 'AWS'
    ret['cloud_template_source'] = 'Quickstart'

    ret['external_object_storage'] = {
        'enabled': False,
    }

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
    urlencoded_pyodbc_username = quote(secret['username'], safe='')
    urlencoded_pyodbc_password = quote(secret['password'], safe='')

    print("Adding SQL connection strings to JSON")
    ret["sql_connection_string_template"] = f"Server=tcp:{db_endpoint},1433;Initial Catalog=DB_NAME_PLACEHOLDER;Persist Security Info=False;User Id={secret['username']};Password='{dot_net_escaped_password}';MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=True;Connection Timeout=30;Max Pool Size=100;"
    ret["sql_connection_string_template_jdbc"] = f"jdbc:sqlserver://{db_endpoint}:1433;database=DB_NAME_PLACEHOLDER;user={secret['username']};password={{{odbc_escaped_password}}};encrypt=true;trustServerCertificate=true;Connection Timeout=30;"
    ret["sql_connection_string_template_odbc"] = f"SERVER={db_endpoint},1433;DATABASE=DB_NAME_PLACEHOLDER;DRIVER={{ODBC Driver 17 for SQL Server}};UID={secret['username']};PWD={{{odbc_escaped_password}}};MultipleActiveResultSets=False;Encrypt=YES;TrustServerCertificate=YES;Connection Timeout=30;"
    ret["sql_connection_string_template_sqlalchemy_pyodbc"] = f"mssql+pyodbc://{urlencoded_pyodbc_username}:{urlencoded_pyodbc_password}@{db_endpoint}:1433/DB_NAME_PLACEHOLDER?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=YES&Encrypt=YES"

    ret['platform'] = {}
    ret['platform']['enabled'] = enabled_services_map['platform']

    ret['orchestrator'] = {}
    ret['orchestrator']['enabled'] = enabled_services_map['orchestrator']
    ret['orchestrator']['testautomation'] = {"enabled": enabled_services_map['orchestrator']}
    ret['orchestrator']['updateserver'] = {"enabled": enabled_services_map['orchestrator']}

    ret['automation_hub'] = {"enabled": enabled_services_map['automation_hub']}

    ret['automation_ops'] = {"enabled": enabled_services_map['automation_ops']}

    ret['action_center'] =  {"enabled":enabled_services_map['action_center']}

    ret['dataservice'] = {"enabled": enabled_services_map['dataservice']}

    ret['test_manager'] = {"enabled": enabled_services_map['test_manager']}

    ret['insights'] = {"enabled": enabled_services_map['test_manager']}

    ret['apps'] = {"enabled": enabled_services_map['apps']}

    ret['task_mining'] = {"enabled": enabled_services_map['task_mining']}
    if enabled_services_map['task_mining']:
        initial_number_of_instances += 1

    ret['processmining'] = {"enabled": enabled_services_map['processmining']}
    if enabled_services_map['processmining']:
        if pm_db_endpoint:
            ret['processmining']["warehouse"] = {
                "sql_connection_str": f"Server=tcp:{pm_db_endpoint},1433;Initial Catalog=DB_NAME_PLACEHOLDER;Persist Security Info=False;User Id={secret['username']};Password='{dot_net_escaped_password}';MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=True;Connection Timeout=30;Max Pool Size=100;",
                "sqlalchemy_pyodbc_sql_connection_str": f"mssql+pyodbc://{urlencoded_pyodbc_username}:{urlencoded_pyodbc_password}@{pm_db_endpoint}:1433/DB_NAME_PLACEHOLDER?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=YES&Encrypt=YES"
            }

    ret['aicenter'] = {"enabled": enabled_services_map['aicenter']}
    if enabled_services_map['aicenter']:
        if use_external_orchestrator.lower() == "true":
            ret['aicenter']["orchestrator_url"] = orchestrator_url
            ret['aicenter']["identity_server_url"] = identity_url
            ret['aicenter']["orchestrator_cert_file_path"] = AICENTER_EXTERNAL_ORCH_CERT_PATH
            ret['aicenter']["identity_cert_file_path"] = AICENTER_EXTERNAL_IDENTITY_CERT_PATH
            ret['aicenter']["metering_api_key"] = "PLACEHOLDER"

    ret['documentunderstanding'] = {}
    ret['documentunderstanding']['enabled'] = enabled_services_map['documentunderstanding']
    if enabled_services_map['documentunderstanding']:
        ret['documentunderstanding']['handwriting'] = {
            "enabled": True,
            "max_cpu_per_pod": 2
        }

    ret['asrobots'] = {'enabled': enabled_services_map['asrobots']}
    if enabled_services_map['asrobots']:
        ret['asrobots']["packagecaching"] = True
        if multi_node.lower() == 'multi node':
            initial_number_of_instances += 1

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
    pm_db_endpoint = properties["PMRDSDBInstanceEndpointAddress"]
    multi_node = properties["MultiNode"]
    internal_load_balancer_dns = properties["KubeLoadBalancerDns"]
    add_gpu = properties['AddGpu']
    server_instance_count = int(properties['ServerInstanceCount'])
    agent_instance_count = int(properties['AgentInstanceCount'])
    private_subnet_ids = properties['PrivateSubnetIDs']
    extra_dict_keys = properties['ExtraConfigKeys']
    self_signed_cert_validity = properties['SelfSignedCertificateValidity']
    use_external_orchestrator = properties['UseExternalOrchestrator']
    orchestrator_url = properties['OrchestratorURL']
    identity_url = properties['IdentityURL']
    initial_number_of_instances = server_instance_count + agent_instance_count

    enabled_services_map = get_enabled_services_map(properties)
    if use_external_orchestrator.lower() == "true":
        check_ai_center_external_certificates(properties)

    ret = {"fqdn": fqdn, "rke_token": str(uuid.uuid4())}
    ret['cloud_template_vendor'] = 'AWS'
    ret['cloud_template_source'] = 'Quickstart'

    ret['external_object_storage'] = {
        'enabled': False,
    }
    
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
    urlencoded_pyodbc_username = quote(secret['username'], safe='')
    urlencoded_pyodbc_password = quote(secret['password'], safe='')

    print("Adding SQL connection strings to JSON")
    ret["sql_connection_string_template"] = f"Server=tcp:{db_endpoint},1433;Initial Catalog=DB_NAME_PLACEHOLDER;Persist Security Info=False;User Id={secret['username']};Password='{dot_net_escaped_password}';MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=True;Connection Timeout=30;Max Pool Size=100;"
    ret["sql_connection_string_template_jdbc"] = f"jdbc:sqlserver://{db_endpoint}:1433;database=DB_NAME_PLACEHOLDER;user={secret['username']};password={{{odbc_escaped_password}}};encrypt=true;trustServerCertificate=true;Connection Timeout=30;"
    ret["sql_connection_string_template_odbc"] = f"SERVER={db_endpoint},1433;DATABASE=DB_NAME_PLACEHOLDER;DRIVER={{ODBC Driver 17 for SQL Server}};UID={secret['username']};PWD={{{odbc_escaped_password}}};MultipleActiveResultSets=False;Encrypt=YES;TrustServerCertificate=YES;Connection Timeout=30;"
    ret["sql_connection_string_template_sqlalchemy_pyodbc"] = f"mssql+pyodbc://{urlencoded_pyodbc_username}:{urlencoded_pyodbc_password}@{db_endpoint}:1433/DB_NAME_PLACEHOLDER?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=YES&Encrypt=YES"

    ret['platform'] = {}
    ret['platform']['enabled'] = enabled_services_map['platform']

    ret['orchestrator'] = {}
    ret['orchestrator']['enabled'] = enabled_services_map['orchestrator']
    ret['orchestrator']['testautomation'] = {"enabled": enabled_services_map['orchestrator']}
    ret['orchestrator']['updateserver'] = {"enabled": enabled_services_map['orchestrator']}

    ret['automation_hub'] = {"enabled": enabled_services_map['automation_hub']}

    ret['automation_ops'] = {"enabled": enabled_services_map['automation_ops']}

    ret['action_center'] =  {"enabled":enabled_services_map['action_center']}

    ret['dataservice'] = {"enabled": enabled_services_map['dataservice']}

    ret['test_manager'] = {"enabled": enabled_services_map['test_manager']}

    ret['insights'] = {"enabled": enabled_services_map['test_manager']}

    ret['apps'] = {"enabled": enabled_services_map['apps']}

    ret['task_mining'] = {"enabled": enabled_services_map['task_mining']}
    if enabled_services_map['task_mining']:
        initial_number_of_instances += 1

    ret['processmining'] = {"enabled": enabled_services_map['processmining']}

    ret['aicenter'] = {"enabled": enabled_services_map['aicenter']}
    if enabled_services_map['aicenter']:
        if use_external_orchestrator.lower() == "true":
            ret['aicenter']["orchestrator_url"] = orchestrator_url
            ret['aicenter']["identity_server_url"] = identity_url
            ret['aicenter']["orchestrator_cert_file_path"] = AICENTER_EXTERNAL_ORCH_CERT_PATH
            ret['aicenter']["identity_cert_file_path"] = AICENTER_EXTERNAL_IDENTITY_CERT_PATH
            ret['aicenter']["metering_api_key"] = "PLACEHOLDER"
    
    ret['documentunderstanding'] = {}
    ret['documentunderstanding']['enabled'] = enabled_services_map['documentunderstanding']
    if enabled_services_map['documentunderstanding']:
        ret['documentunderstanding']['handwriting'] = {
            "enabled": True,
            "max_cpu_per_pod": 2
        }
    
    ret['processmining'] = {"enabled": enabled_services_map['processmining']}
    if enabled_services_map['processmining']:
        if pm_db_endpoint:
            ret['processmining']["warehouse"] = {
                "sql_connection_str": f"Server=tcp:{pm_db_endpoint},1433;Initial Catalog=DB_NAME_PLACEHOLDER;Persist Security Info=False;User Id={secret['username']};Password='{dot_net_escaped_password}';MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=True;Connection Timeout=30;Max Pool Size=100;",
                "sqlalchemy_pyodbc_sql_connection_str": f"mssql+pyodbc://{urlencoded_pyodbc_username}:{urlencoded_pyodbc_password}@{pm_db_endpoint}:1433/DB_NAME_PLACEHOLDER?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=YES&Encrypt=YES"
            }

    ret['asrobots'] = {'enabled': enabled_services_map['asrobots']}
    if enabled_services_map['asrobots']:
        ret['asrobots']["packagecaching"] = True
        if multi_node.lower() == 'multi node':
            initial_number_of_instances += 1

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
        timer.cancel()
        cfnresponse.send(event, context, status, returnAttribute, new_physical_id)
