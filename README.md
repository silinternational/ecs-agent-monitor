# ecs-agent-monitor
AWS Lambda function to terminate ECS instances with stopped agents.

## The Problem
Amazon EC2 Container Service runs an agent as a Docker container on each EC2
instance registered in an ECS cluster. Unfortunately, on occasion this agent
crashes, and this causes other services running on the instance to be
inaccessible.

This doesn't have to be a big deal, though. In the world of micro-services we
expect and plans for failure.

## The Solution
This AWS Lambda function can be scheduled to check all instances in a given ECS
cluster and verify their agent connection statuses. Any instance whose
connection status is `false` will be deregistered from its AWS Autoscaling Group
and then terminated.

AWS will automatically replace each instance deregistering from its Autoscaling
Group with an identical new healthy instance.


# How to use
[ ![Codeship Status for silinternational/ecs-agent-monitor](https://codeship.com/projects/97556e30-e3dc-0133-e2f1-2ef0590de381/status?branch=master)](https://codeship.com/projects/146170)

We use Codeship to build AWS Lambda deployment packages; you can download the
latest stable version [here](https://s3.amazonaws.com/gtis-public-web/ecs-agent-monitor.zip).

You will need to create a new Lambda function. Configuration parameters, both
recommended and *required*:
  - Name: ecs-agent-monitor
  - Runtime: *Python 2.7*
  - Handler: *ecs-agent-monitor.main*
  - Role: (see below)
  - Description: Terminate ECS Instances with stopped agents
  - Memory (MB): 128
  - Timeout: 20 sec

Load the function code, either directly from the zipped deployment package, by
pasting in the S3 URL to that package, or by [building your own package](http://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html).

## IAM Policy
You will need to create an new IAM role for this Lambda function to assume,
in order that it may have the necessary permission to access ECS clusters,
and deregister and terminate instances. See `sample_policy.json` for a sample
IAM permissions policy that could be applied to this role.

It is also necessary to configure this IAM role's trust relationships, in order
to allow the Lambda function to assume this role. See `sample_trust.json` for an
IAM trust policy that should be applied to enable this.

Once you have created this role, configure the Lambda function to assume it (see
above).

## Invoking by Events
This function is controlled by the JSON event variable passed when invoked. For
example:

    {
      "cluster":"default",
      "snsLogArn":"arn:aws:sns:region:account-id:topicname"
    }

The function this JSON for two keys:
  - `cluster`: the ECS cluster to scan for stopped agents
  - `snsLogArn`: (optional) ARN of a AWS SNS Topic

If `snsLogArn` is available, the function will send a formatted information
message to that SNS Topic whenever it terminates EC2 Instances.

## Cloudwatch Event
You can invoke this function manually from the AWS Web Console, or the `aws`
command-line tool (by passing in the necessary JSON event), but for regular
cluster scanning it is better to configure a Cloudwatch Rule to invoke the
function on a regular basis.

# Contributing
We welcome contributions in the form of issues opened or pull requests.

This repository uses [git-flow](http://nvie.com/posts/a-successful-git-branching-model/).
So, if you want to use a stable version of the script, just check-out the latest
tag on the `master` branch.

The zipped deployment package is automatically built from the latest tag on `master`.
