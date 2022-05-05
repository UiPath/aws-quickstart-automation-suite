# Deployment

## Entrypoints

There are 3 entrypoints into the deployment:

- Deploying into a new VPC - basic config
- Deploying into a new VPC - extended config options
- Deploying into an existing VPC

### Deploying using the CLI

To deploy from the command line, use the [aws cli](https://aws.amazon.com/cli/) to create a stack. In the [examples folder](../examples) there are parameter files for some very common scenarios.

#### Single node default deployment

The simplest deployment scenario, with the minimum number of parameters updated.

```shell
aws cloudformation create-stack --stack-name uipath-single-node --template-url https://uipath-s3-quickstart.s3.amazonaws.com/aws-quickstart-sf-v2021-10-0/templates/main.template.yaml --parameters file://single-node-default.json --region us-east-1 --capabilities CAPABILITY_NAMED_IAM
```

#### Single node deployment into a new VPC, internal load balancer

Deploys the Automation Suite into an existing VPC. This is a multi-node deployment, which skips the installation of `ActionCenter`, `AutomationHub` and `TaskMining`. All other parameters are set to their default values, which includes the provisioning of a bastion in the public subnet, as well as installing all other UiPath services.

```shell
aws cloudformation create-stack --stack-name uipath-single-node --template-url https://uipath-s3-quickstart.s3.amazonaws.com/aws-quickstart-sf-v2021-10-0/templates/uipath-sf.template.yaml --parameters file://multi-node-existing-vpc.json --region us-east-1 --capabilities CAPABILITY_NAMED_IAM
```

#### Multi node deployment in an existing VPC

For this deployment scenario, some information needs to be provided, describing the exiting infrastructure. These include:
- `VPCCIDR` for the VPC where the installation is performed
- `VPCID` the ID of the VPC
- `PrivateSubnetIDs` and `PublicSubnetIDs` comma separated values indicating the subnets of the VPC

Deploys the Automation Suite into an existing VPC. This is a multi-node deployment, which skips the installation of `ActionCenter`, `AutomationHub` and `TaskMining`. All other parameters are set to their default values, which includes the provisioning of a bastion in the public subnet, as well as installing all other UiPath services.

```shell
aws cloudformation create-stack --stack-name uipath-single-node --template-url https://uipath-s3-quickstart.s3.amazonaws.com/aws-quickstart-sf-v2021-10-0/templates/uipath-sf.template.yaml --parameters file://multi-node-existing-vpc.json --region us-east-1 --capabilities CAPABILITY_NAMED_IAM
```

#### Private hosted zone deployment

This scenario involves the deployment using an internal load balancer, in an existing VPC which has a private hosted zone attached. This scenario requires extra prerequisites:
- an existing VPC
- a private hosted zone, attached to the VPC. this means that DNS queries to the domain name can be answered inside the VPC
- a valid certificate in Azure Certificate Management

```shell
aws cloudformation create-stack --stack-name uipath-single-node --template-url https://uipath-s3-quickstart.s3.amazonaws.com/aws-quickstart-sf-v2021-10-0/templates/uipath-sf.template.yaml --parameters file://private-hosted-zone.json --region us-east-1 --capabilities CAPABILITY_NAMED_IAM
```

#### Backup disabled, customer managed key for SQL database encryption

Switch the backup flag to false and provide a customer managed KMS key to use for the encryption of the RDS instance.

```shell
aws cloudformation create-stack --stack-name uipath-single-node --template-url https://uipath-s3-quickstart.s3.amazonaws.com/aws-quickstart-sf-v2021-10-0/templates/uipath-detailed.template.yaml --parameters file://kms.json --region us-east-1 --capabilities CAPABILITY_NAMED_IAM
```


## Parameters

### New VPC - basic config

<!-- NEW_VPC_BASIC_CONFIG -->
| Parameter name | Default value | Description |
| --- | --- | --- |
| AvailabilityZones | Requires Input | Choose up to three Availability Zones to use for the VPC subnets. |
| NumberOfAZs | 2 | Choose the number of Availability Zones to use in the VPC. This must match the number of AZs selected in the *Availability Zones* parameter. |
| KeyPairName | Requires Input | Existing key pair to connect to virtual machine (VM) instances. |
| MultiNode | Single Node | Install Automation Suite on a Single Node (recommended for evaluation/dev purposes) or Multi-node (recommended for production purposes) |
| UseLevel7LoadBalancer | ALB | Select either an Application Load Balancer (ALB) or a Network Load Balancer (NLB) |
| UiPathVersion | 2022.4.0-rc.12 | UiPath version to install |
| ServiceProfile | Default platform | Choose Default platform to install Orchestrator, Action Center, Test Manager, Insights, Automation Hub, Automation Ops, Data Service. Choose Entire platform to additionally install Apps, AI Center, Task Mining, Document Understanding. |
| AddGpu | false | Choose true to add a GPU enabled VM to the deployment. |
| HostedZoneID | Requires Input | ID of Route 53 hosted zone. |
| UiPathFQDN | Requires Input | Fully qualified domain name (FQDN) for Automation Suite. This must be either a subdomain, or root domain, of the of ID of Route 53 hosted zone parameter. |
| QSS3BucketName | uipath-s3-quickstart | Name of the S3 bucket for your copy of the Quick Start assets. Do not modify. |
| QSS3BucketRegion | us-east-1 | AWS Region where the Quick Start S3 bucket (QSS3BucketName) is hosted. Do not modify. |
| QSS3KeyPrefix | aws-quickstart-sf/ | S3 key prefix that is used to simulate a directory for your copy of the Quick Start assets. Do not modify. |
| AcceptLicenseAgreement | Requires Input | Use of paid UiPath products and services is subject to the licensing agreement executed between you and UiPath. Unless otherwise indicated by UiPath, use of free UiPath products is subject to the associated licensing agreement available here: https://www.uipath.com/legal/trust-and-security/legal-terms (or successor website). Type true in the text input field to confirm that you agree to the applicable licensing agreement. |
<!-- NEW_VPC_BASIC_CONFIG -->

### New VPC - extended config options


<!-- NEW_VPC_EXTENDED_CONFIG -->
| Parameter name | Default value | Description |
| --- | --- | --- |
| AvailabilityZones | Requires Input | Choose up to three Availability Zones to use for the VPC subnets. |
| NumberOfAZs | 2 | Choose the number of Availability Zones to use in the VPC. This must match the number of AZs selected in the *Availability Zones* parameter. |
| KeyPairName | Requires Input | Existing key pair to connect to virtual machine (VM) instances. |
| AmiId | Empty | Enter the AMI Id to be used for the creation of the EC2 instances of the cluster.Leave empty to determine automatically the AMI to use. |
| GpuAmiId | Empty | Enter the AMI Id to be used for the creation of the GPU enabled EC2 instance.Leave empty to determine automatically the AMI to use. |
| IamRoleArn | Empty | ARN of a pre-deployed IAM Role with sufficient permissions for the deployment. Leave empty to create the role |
| IamRoleName | Empty | Name of a pre-deployed IAM Role with sufficient permissions for the deployment. Leave empty to create the role |
| MultiNode | Single Node | Install Automation Suite on a Single Node (recommended for evaluation/dev purposes) or Multi-node (recommended for production purposes) |
| EnableBackup | true | Choose false to disable cluster backup. |
| UseLevel7LoadBalancer | ALB | Select either an Application Load Balancer (ALB) or a Network Load Balancer (NLB) |
| UiPathVersion | 2022.4.0-rc.12 | UiPath version to install |
| InstallerDownloadUrl | Empty | Custom URL for installer download. Leave empty to use the UiPathVersion, provide an URL to override the download location. |
| ExtraConfigKeys | Empty | Extra configuration keys to add to the cluster config. Leave empty to use default config. |
| ActionCenter | true | Choose false to disable Action Center installation. |
| Insights | true | Choose false to disable Insights installation. |
| AutomationHub | true | Choose false to disable Automation Hub installation. |
| AutomationOps | true | Choose false to disable Automation Ops installation. |
| TestManager | true | Choose false to disable Test Manager installation. |
| DataService | true | Choose false to disable Data Service installation. |
| AiCenter | true | Choose false to disable AI Center installation. |
| BusinessApps | true | Choose false to disable Apps installation. |
| DocumentUnderstanding | true | Choose false to disable Document Understanding installation. |
| TaskMining | true | Choose false to disable Task Mining installation. |
| AddGpu | false | Choose true to add a GPU enabled VM to the deployment. |
| HostedZoneID | Requires Input | ID of Route 53 hosted zone. |
| UiPathFQDN | Requires Input | Fully qualified domain name (FQDN) for Automation Suite. This must be either a subdomain, or root domain, of the of ID of Route 53 hosted zone parameter. |
| AcmCertificateArn | Empty | ARN of certificate present in the ACM (Amazon Certificate Manager) to use with the ALB.Leave empty to create the public certificate during deployment. |
| UseInternalLoadBalancer | false | Deploy Internal Load Balancer |
| DeployBastion | true | Deploy a bastion host inside the public subnet.Choose false to skip deploying the Bastion. |
| RDSEngine | sqlserver-se | RDS MS SQL engine |
| RDSVersion | 15.00 | RDS MS SQL version |
| DatabaseKmsKeyId | Empty | KMS Key Id to use for the encryption of the RDS storage. Leave empty to not encrypt the RDS storage |
| QSS3BucketName | uipath-s3-quickstart | Name of the S3 bucket for your copy of the Quick Start assets. Do not modify. |
| QSS3BucketRegion | us-east-1 | AWS Region where the Quick Start S3 bucket (QSS3BucketName) is hosted. Do not modify. |
| QSS3KeyPrefix | aws-quickstart-sf/ | S3 key prefix that is used to simulate a directory for your copy of the Quick Start assets. Do not modify. |
| AcceptLicenseAgreement | Requires Input | Use of paid UiPath products and services is subject to the licensing agreement executed between you and UiPath. Unless otherwise indicated by UiPath, use of free UiPath products is subject to the associated licensing agreement available here: https://www.uipath.com/legal/trust-and-security/legal-terms (or successor website). Type true in the text input field to confirm that you agree to the applicable licensing agreement. |
<!-- NEW_VPC_EXTENDED_CONFIG -->

### Existing VPC

<!-- EXISTING_VPC -->
| Parameter name | Default value | Description |
| --- | --- | --- |
| VPCCIDR | 10.0.0.0/16 | VPC CIDR block, in format x.x.0.0/16. |
| VPCID | Requires Input | VPC ID |
| PublicSubnetIDs | Empty | List of public subnet IDs to deploy the internet-facing Load Balancer and the Bastion host.Leave empty to deploy internal Load Balancer and skip the deployment of the Bastion host. |
| PrivateSubnetIDs | Requires Input | List of private subnet IDs. |
| NumberOfAZs | 2 | Choose the number of Availability Zones to use in the VPC. This must match the number of AZs selected in the *Availability Zones* parameter. |
| KeyPairName | Requires Input | Existing key pair to connect to virtual machine (VM) instances. |
| AmiId | Empty | Enter the AMI Id to be used for the creation of the EC2 instances of the cluster.Leave empty to determine automatically the AMI to use. |
| GpuAmiId | Empty | Enter the AMI Id to be used for the creation of the GPU enabled EC2 instance.Leave empty to determine automatically the AMI to use. |
| IamRoleArn | Empty | ARN of a pre-deployed IAM Role with sufficient permissions for the deployment. Leave empty to create the role |
| IamRoleName | Empty | Name of a pre-deployed IAM Role with sufficient permissions for the deployment. Leave empty to create the role |
| MultiNode | Single Node | Install Automation Suite on a Single Node (recommended for evaluation/dev purposes) or Multi-node (recommended for production purposes) |
| EnableBackup | true | Choose false to disable cluster backup. |
| UseLevel7LoadBalancer | ALB | Select either an Application Load Balancer (ALB) or a Network Load Balancer (NLB) |
| PerformInstallation | true | Perform the Automation Suite installation.Choose false to perform only infrastructure provisioning and configuration. |
| UiPathVersion | 2022.4.0-rc.12 | UiPath version to install |
| InstallerDownloadUrl | Empty | Custom URL for installer download. Leave empty to use the UiPathVersion, provide an URL to override the version. |
| ExtraConfigKeys | Empty | Extra configuration keys to add to the cluster config. Leave empty to use default config. |
| ActionCenter | true | Choose false to disable Action Center installation. |
| Insights | true | Choose false to disable Insights installation. |
| AutomationHub | true | Choose false to disable Automation Hub installation. |
| AutomationOps | true | Choose false to disable Automation Ops installation. |
| TestManager | true | Choose false to disable Test Manager installation. |
| DataService | true | Choose false to disable Data Service installation. |
| AiCenter | true | Choose false to disable AI Center installation. |
| BusinessApps | true | Choose false to disable Apps installation. |
| DocumentUnderstanding | true | Choose false to disable Document Understanding installation. |
| TaskMining | true | Choose false to disable Task Mining installation. |
| AddGpu | false | Choose true to add a GPU enabled VM to the deployment. |
| HostedZoneID | Requires Input | ID of Route 53 hosted zone. |
| UiPathFQDN | Requires Input | Fully qualified domain name (FQDN) for Automation Suite. This must be either a subdomain, or root domain, of the of ID of Route 53 hosted zone parameter. |
| AcmCertificateArn | Empty | ARN of certificate present in the ACM (Amazon Certificate Manager) to use with the ALB.Leave empty to create the public certificate during deployment. |
| UseInternalLoadBalancer | false | Deploy Internal Load Balancer |
| DeployBastion | true | Deploy a bastion host inside the public subnet.Choose false to skip deploying the Bastion. |
| RDSEngine | sqlserver-se | RDS MS SQL engine |
| RDSVersion | 15.00 | RDS MS SQL version |
| DatabaseKmsKeyId | Empty | KMS Key Id to use for the encryption of the RDS storage. Leave empty to not encrypt the RDS storage |
| QSS3BucketName | uipath-s3-quickstart | Name of the S3 bucket for your copy of the Quick Start assets. Do not modify. |
| QSS3BucketRegion | us-east-1 | AWS Region where the Quick Start S3 bucket (QSS3BucketName) is hosted. Do not modify. |
| QSS3KeyPrefix | aws-quickstart-sf/ | S3 key prefix that is used to simulate a directory for your copy of the Quick Start assets. Do not modify. |
| AcceptLicenseAgreement | Requires Input | Use of paid UiPath products and services is subject to the licensing agreement executed between you and UiPath. Unless otherwise indicated by UiPath, use of free UiPath products is subject to the associated licensing agreement available here: https://www.uipath.com/legal/trust-and-security/legal-terms (or successor website). Type true in the text input field to confirm that you agree to the applicable licensing agreement. |
<!-- EXISTING_VPC -->

