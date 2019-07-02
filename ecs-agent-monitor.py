import boto3
import decimal


def main(event, context):

    db_table_name = event.get("tableName")
    region = event.get("region")

    dynamodb = boto3.resource('dynamodb', region_name=region)
    db_table = dynamodb.Table(db_table_name)

    warn_only = False

    print db_table

    warn_only_config = event.get("warn_only")
    if warn_only_config and str(warn_only_config).lower() == "true":
        warn_only = True

    if u'cluster' not in event:
        raise Exception(
          "Key u'cluster' not found in the event object! Which cluster should I scan?!"
        )

    ecs_client = boto3.client("ecs")

    resp = ecs_client.list_container_instances(
      cluster=event[u'cluster']
    )

    instances = resp[u'containerInstanceArns']

    print instances

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
    tracked_in_dynamodb = []

    # set amount of failures instances can have, default is 2
    fail_after = 2
    if event.get("fail_after"):
        fail_after = event.get("fail_after")

    print "about to check instances"

    for inst in resp[u'containerInstances']:

        ec2_instance_id = str(inst[u'ec2InstanceId'])
        db_response = db_table.get_item(Key={'ec2InstanceId': ec2_instance_id})
        instance_id_exists = 'Item' in db_response

        # check if agent is connected
        if inst[u'agentConnected']:
            if instance_id_exists:
                db_table.delete_item(Key={'ec2InstanceId': ec2_instance_id})

        # check if agent is not connected
        if not inst[u'agentConnected']:

            number_of_failures = 0 if not instance_id_exists else db_response['Item']['numberOfFailures']

            # if instance id does not exist in dynamodb, then add it to dynamodb
            if not instance_id_exists:
                db_table.put_item(Item={'ec2InstanceId': ec2_instance_id, 'numberOfFailures': 1})
                tracked_in_dynamodb.append((ec2_instance_id, 1))

            # if instance id exists but has not reached fail_after, then increment number of fails
            elif instance_id_exists and number_of_failures < fail_after:
                db_table.update_item(
                    Key={
                        'ec2InstanceId': ec2_instance_id
                    },
                    UpdateExpression="set numberOfFailures = numberOfFailures + :val",
                    ExpressionAttributeValues={
                        ':val': decimal.Decimal(1)
                    },
                    ReturnValues="UPDATED_NEW"
                )
                tracked_in_dynamodb.append((ec2_instance_id, number_of_failures + 1))

            # if instance id exists in dynamodb and instance has reached fail_after, then terminate
            else:

                # delete instance id key from dynamodb
                db_table.delete_item(Key={'ec2InstanceId': ec2_instance_id})

                bad_inst = ec2.Instance(id=ec2_instance_id)

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

    print "finished checking instances"

    # If instances were found for tracking in dynamodb and we have an SNS topic ARN,
    # send an informative message.
    if len(tracked_in_dynamodb) != 0 and u'snsLogArn' in event:
        sns = boto3.resource("sns", region_name=region)
        topic = sns.Topic(event[u'snsLogArn'])

        message = "The ecs-agent-monitor function running in AWS Lambda has detected the following: "

        for (instanceId, failures) in tracked_in_dynamodb:
            msg = """"\
The instance `%s' in the `%s' ECS cluster failed. It has failed %i times. It will be terminated if it fails %i times."
""" % (instanceId, event[u'cluster'], failures, fail_after)
            message += msg

        topic.publish(
            Subject="AWS Lambda: ECS-Agent-Monitor",
            Message=message
        )

    print "finished publishing message concerning instances tracked in dynamodb"

    # If instances were found for termination and we have an SNS topic ARN,
    # send an informative message.
    if len(terminated) != 0 and u'snsLogArn' in event:
        sns = boto3.resource("sns", region_name=region)
        topic = sns.Topic(event[u'snsLogArn'])

        message = """\
The ecs-agent-monitor function running in AWS Lambda has detected %i EC2
Instances in the `%s' ECS cluster whose `ecs-agent' process has died.

These are:
%s

""" % (len(terminated), event[u'cluster'], "\n".join(terminated))

        if not warn_only:
            message = ("%sThese instances have been detached from their "
                       "autoscaling groups and terminated." % message)

        topic.publish(
            Subject="AWS Lambda: ECS-Agent-Monitor",
            Message=message
        )

    # Warn if logging is impossible
    if u'snsLogArn' not in event:
        print "Warn: key u'snsLogArn' not found in the event object, so logging is disabled."
