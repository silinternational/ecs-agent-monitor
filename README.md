# ecs-agent-monitor
AWS Lambda function to terminate ECS instances with stopped agents.

## The problem
Amazon EC2 Container Service runs an agent as a Docker container on each EC2 instance registered in an ECS cluster. 
Unfortunately far too often this agent crashes which cases the other services running on the instance to not be accessible. 
This doesn't have to be a big deal though, in a micro-services world we expect and plans for failure.

## The solution
This Lambda function can be scheduled to check all instances in a given ECS cluster and verify the agent connection status.
If (when) it finds the connection status to be false it will de-register the EC2 instance from its auto-scaling group and either
Stop or Terminate the EC2 instance. De-refistering from the auto-scaling group will cause it to be replaced with a new healthy instance
and either Stop the instance for further troubleshooting or just Terminate it to move on. 

## IAM Policy
You will need to create an new IAM role for this lambda function to assume.

See `sample_iam.json` for a sample IAM policy that should be applied to this role.

## Cloudwatch Alarm

## How to use
TBD - we're still developing this thing.

## Contributing
We welcome contributions in the form of issues opened or pull requests. 
