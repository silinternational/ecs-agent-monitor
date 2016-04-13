import boto3

def main(event, context):
  ecs_client = boto3.client(u'ecs')

  inspect_clusters = [u'staging1']

  for cluster in inspect_clusters:
    resp = ecs_client.list_container_instances(
      cluster=cluster
    )

    instances = resp[u'containerInstanceArns']

    try:
      nxt_tok = resp[u'nextToken']

      while True:
        resp = ecs_client.list_container_instances(
          cluster=cluster,
          nextToken=nxt_tok
        )

        instances += resp[u'containerInstanceArns']
        nxt_tok = resp[u'nextToken']
    except KeyError:
      pass

    resp = ecs_client.describe_container_instances(
      cluster=cluster,
      containerInstances=instances
    )

    ec2 = boto3.resource('ec2')
    autoscale_client = boto3.client('autoscaling')

    terminated = []

    for inst in resp[u'containerInstances']:
      if not inst['agentConnected']:
        I = ec2.Instance(id=inst[u'ec2InstanceId'])

        autoscalegroup = filter(lambda k: k['Key'] == u'aws:autoscaling:groupName', I.tags)[0]['Value']

        # Danger! Detaching Instance from autoscaling group
        autoscale_client.detach_instances(
          InstanceIds=[I.id],
          AutoScalingGroupName=autoscalegroup,
          ShouldDecrementDesiredCapacity=False
        )

        # Danger! Terminating Instance
        I.terminate()

        terminated.append(I.id)
        print u'Detaching and Terminating: ', I.id, u' in autoscale group ', autoscalegroup

    # Send summary to an SNS topic
    sns = boto3.resource("sns")
    topic = sns.Topic("arn")

    topic.publish(
        Subject="AWS Lambda: ECS-Agent-Monitor",
        Message=\
"""
The ecs-agent-monitor function running in AWS Lambda has detected %i EC2
instances whose ECS `ecs-agent' process has died.

The following Instances were detached from their autoscaling groups and
terminated:

%s
""" % (len(terminated), "\n".join(terminated))
    )
