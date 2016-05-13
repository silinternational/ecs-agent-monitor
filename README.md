# ecs-agent-monitor

AWS Lambda function to terminate ECS instances with stopped agents.

## The problem
Amazon EC2 Container Service runs an agent as a Docker container on each EC2
instance registered in an ECS cluster. Unfortunately, far too often this agent
crashes which cases the other services running on the instance to not be
accessible. This doesn't have to be a big deal though, in a micro-services
world we expect and plans for failure.

## The solution
This Lambda function can be scheduled to check all instances in a given ECS
cluster and verify the agent connection status. If (when) it finds the
connection status to be false it will de-register the EC2 instance from its
auto-scaling group and either Stop or Terminate the EC2 instance.
De-registering from the auto-scaling group will cause it to be replaced with a
new healthy instance and either Stop the instance for further troubleshooting
or just Terminate it to move on.

## IAM Policy
You will need to create an new IAM role for this lambda function to assume.

See `sample_policy.json` for a sample IAM permissions policy that should be
applied to this role.

See `sample_trust.json` for a sample IAM trust policy that should also be
applied to this role.

## Cloudwatch Alarm

## How to use
TBD - we're still developing this thing.

## Contributing
We welcome contributions in the form of issues opened or pull requests.

This repository uses [git-flow](http://nvie.com/posts/a-successful-git-branching-model/).
So, if you want to use a stable version of the script, just check-out the latest
tag on the `master` branch.

## CI/CD
[ ![Codeship Status for silinternational/ecs-agent-monitor](https://codeship.com/projects/97556e30-e3dc-0133-e2f1-2ef0590de381/status?branch=master)](https://codeship.com/projects/146170)

We are using Codeship to build and deploy this script to AWS Lambda. You can
download the AWS Lambda zipped deployment package of the most recent tag on the
`master` branch [here](https://s3.amazonaws.com/gtis-public-web/ecs-agent-monitor.zip).
