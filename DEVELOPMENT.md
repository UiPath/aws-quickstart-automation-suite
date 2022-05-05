
## Deploying local changes

### Setting up environment

Install prerequisites:
- aws cli found [here](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- taskcat utility found [here](https://aws-ia.github.io/taskcat/docs/INSTALLATION/)
- taskcat requires docker running on the machine

Configuration files:
- configure aws authentication, instructions [here](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- add a configuration file for taskcat located at `~/.taskcat.yml`, with a content covering these keys: 
```yaml
general:
  s3_regional_buckets: true
  parameters:
    KeyPairName: my-key-pair
    AcceptLicenseAgreement: "true"
  tags:
    Owner: first.last@uipath.com
    Project: "Automation Suite"
```

### Deploying

The deployment has 2 steps, both of which are handled by `taskcat`:
1. Upload artifacts to S3 buckets
   1. Build lambda functions inside the `/functions` folder
   2. Upload all templates and resulting zip files
2. Start deployments for **all configurations** described in the `.taskcat.yml` file, under the `tests` key

To deploy a single environment using the local code changes:
- comment out the tests which are not relevant
- execute in the root of the project:

```shell
taskcat test run -k -n
```

### Deploying a different version

In the `.taskcat.yml` file there are multiple types of tests, among which one is pre-created to deploy older versions or release candidates.
Just replace:
- the `ExtraConfigKeys` key with the authentication information for docker registry where the images are located
- the `InstallerDownloadUrl` key with the url for the installer

```yaml
  multi-node-alb-dev-build:
    template: ./templates/uipath-detailed.template.yaml
    regions:
      - eu-central-1
    parameters:
      AvailabilityZones: "$[taskcat_getaz_2]"
      UiPathFQDN: "$[taskcat_random-string].uipathmarketplace.net"
      MultiNode: "Multi Node"
      UseLevel7LoadBalancer: 'ALB'
      ActionCenter: 'false'
      Insights: 'false'
      AutomationHub: 'false'
      AutomationOps: 'false'
      TestManager: 'false'
      AiCenter: 'false'
      BusinessApps: 'false'
      DocumentUnderstanding: 'false'
      TaskMining: 'false'
      UiPathVersion: "2022.4.0-rc.12"
      HostedZoneID: Z02863091ZH3OBSC7MS71
      ExtraConfigKeys: '##EXTRA_CONFIG_KEYS##'
      InstallerDownloadUrl: '##INSTALLER_DOWNLOAD_URL##'
```

You can execute just this deployment using:
```shell
taskcat test run -k -n -t multi-node-alb-dev-build
```
