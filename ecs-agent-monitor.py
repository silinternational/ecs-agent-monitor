import boto3

def main(event, context):
    warn_only = False
    
    warn_only_config = event.get("warn_only")
    if warn_only_config and str(warn_only_config).lower() == "true":
        warn_only = True
        

    if not u'cluster' in event:
        raise Exception(
          "Key u'cluster' not found in the event object! Which cluster should I scan?!"
        )

    ecs_client = boto3.client("ecs")

    resp = ecs_client.list_container_instances(
      cluster=event[u'cluster']
    )

    instances = resp[u'containerInstanceArns']

    try:
        nxt_tok = resp[u'nextToken']

        while True:
            resp = ecs_client.list_container_instances(
              cluster=event[u'cluster'],
              nextToken=nxt_tok
            )

            instances += resp[u'containerInstanceArns']
            nxt_tok = resp[u'nextToken']
    except KeyError:
        pass
  
    resp = ecs_client.describe_container_instances(
      cluster=event[u'cluster'],
      containerInstances=instances
    )

    ec2 = boto3.resource("ec2")
    autoscale_client = boto3.client("autoscaling")

    terminated = []

    for inst in resp[u'containerInstances']:
        if not inst[u'agentConnected']:
            bad_inst = ec2.Instance(id=inst[u'ec2InstanceId'])
            
            autoscalegroup = [x[u'Value'] for x in bad_inst.tags 
                              if x[u'Key'] == u'aws:autoscaling:groupName'][0]

            if not warn_only:
                # Danger! Detaching Instance from autoscaling group
                autoscale_client.detach_instances(
                    InstanceIds=[bad_inst.id],
                    AutoScalingGroupName=autoscalegroup,
                    ShouldDecrementDesiredCapacity=False
                )

                # Danger! Terminating Instance
                bad_inst.terminate()
                print "Detaching and Terminating: %s in autoscale group %s" \
                  % (bad_inst.id, autoscalegroup)

            terminated.append(bad_inst.id)

    # If instances were found for termination and we have an SNS topic ARN,
    # send an informative message.
    if len(terminated) != 0 and u'snsLogArn' in event:
        sns = boto3.resource("sns")
        topic = sns.Topic(event[u'snsLogArn'])

        message = """\
The ecs-agent-monitor function running in AWS Lambda has detected %i EC2
Instances in the `%s' ECS cluster whose `ecs-agent' process has died.

These are:
%s

""" % (len(terminated), event[u'cluster'], "\n".join(terminated))
        
        if not warn_only:
            message = ("%sThese instances have been detached from their "
                       "autoscaling groups and terminated."  % message)
        
        topic.publish(
            Subject="AWS Lambda: ECS-Agent-Monitor",
            Message=message
        )
    

    # Warn if logging is impossible
    if u'snsLogArn' not in event:
        print "Warn: key u'snsLogArn' not found in the event object, so logging is disabled."
