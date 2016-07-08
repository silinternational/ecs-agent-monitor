# ecs-agent-monitor
AWS Lambda function to terminate ECS instances with stopped/failed agents.

## The Problem
The Amazon EC2 Container Service runs an agent as a Docker container on each EC2
instance registered in an ECS cluster. Unfortunately, on occasion this agent
crashes, and this causes other services running on that instance to be
inaccessible.

This doesn't have to be a big deal, though. In the world of micro-services we
ought to expect failure and plan for automatically dealing with it.

## The Solution
This AWS Lambda function can be run to check all instances in a given ECS
cluster and verify their agent connection statuses. Any instance whose
connection status is `false` will be deregistered from its AWS Autoscaling group
and then terminated.

AWS will automatically replace each instance deregistering from its Autoscaling
group with an identical new healthy instance.


# Usage
[ ![Codeship Status for silinternational/ecs-agent-monitor](https://codeship.com/projects/97556e30-e3dc-0133-e2f1-2ef0590de381/status?branch=master)](https://codeship.com/projects/146170)

We use Codeship to build AWS Lambda deployment packages; you can download the
latest stable version [here](https://s3.amazonaws.com/gtis-public-web/ecs-agent-monitor.zip).

You will need to create a new Lambda function. Configuration parameters, both
recommended and **required**:
  - Name: ecs-agent-monitor
  - Runtime: **Python 2.7**
  - Handler: **ecs-agent-monitor.main**
  - Role: (see below)
  - Description: Terminate ECS Instances with stopped agents
  - Memory (MB): 128
  - Timeout: 20 sec

Load the function code, either directly from the zipped deployment package, by
pasting in the S3 URL to that package, or by [building your own package](http://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html)
from the source.

Make sure the package contains redis. Use `pip install -r requirements.txt path/to/package`

## IAM Policy
You will need to create an new IAM role for this Lambda function to assume,
in order that it may have the necessary permission to access ECS clusters,
and deregister and terminate instances. See `sample_policy.json` for an
IAM permissions policy that could be applied to this role.

It is also necessary to configure the role's trust relationships, in order to
allow the Lambda function to assume it when run. See `sample_trust.json` for an
IAM trust policy that should be applied to enable this.

In order for the Lambda function to access Elasticache, when creating the Lambda function, provide the following:
- subnet IDs in the Amazon VPC
- a VPC security group to allow the Lambda function to access resources in the VPC

Additionally, assign to the Lambda function a role ARN created from an IAM role with the following:
- AWS service role: AWS Lambda
- Access Permissions Policy: AWSLambdaVPCAccessExecutionRole  

Once you have created this role, configure the Lambda function to assume it (see
above).

## Runtime Configuration
This function is controlled by the JSON event variable passed when it is
invoked. It expects something like this:

    {
      "cluster": "default",
      "snsLogArn": "arn:aws:sns:region:account-id:topicname",
      "elasticache_config_endpoint": "clusterName.xxxxxx.0001.region.cache.amazonaws.com",
      "elasticache_port": 6379
      "fail_after": 2
    }

It looks in the event for five keys:
  - `cluster`: the ECS cluster to scan for stopped agents
  - `snsLogArn`: (optional) ARN of an AWS SNS Topic
  - `elasticache_config_endpoint`: the redis elasticache endpoint
  - `elasticache_port`: the redis elasticache port
  - `fail_after`: the number of failures needed to terminate an instance

If `snsLogArn` is available, the function will send a formatted information
message to that SNS topic whenever it terminates EC2 instances. You can then
add subscriptions to that topic to generate email or text notifications.

## Cloudwatch Event
You can invoke this function manually from the AWS Web Console or the `aws`
command-line tool (by passing in the necessary JSON event), but for regular
cluster scanning it is better to configure a Cloudwatch Rule to invoke it 
on a scheduled basis. Be sure to configure the rule to pass the correct JSON
event to the function.

# Contributing
We welcome contributions in the form of opened issues or pull requests.

This repository uses [git-flow](http://nvie.com/posts/a-successful-git-branching-model/)
for its VCS commit model. So, if you want to use the most recent stable version
of the function, just checkout the latest tag on the `master` branch.

The zipped deployment package is automatically built from the latest tag on `master`.
