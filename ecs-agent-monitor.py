import pyrebase
import boto3

def main(event, context):

    config = {
      "apiKey": event.get("apiKey"),
      "authDomain": event.get("authDomain"),
      "databaseURL": event.get("databaseURL"),
      "storageBucket": event.get("storageBucket"),
    }
    firebase = pyrebase.initialize_app(config)
    auth = firebase.auth()
    user = auth.sign_in_with_email_and_password(event.get("firebaseEmail"), event.get("firebasePassword"))
    db = firebase.database()

    warn_only = False

    print user
    print db

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
    trackedInFirebase = []

    # set amount of failures instances can have, default is 2
    fail_after = 2
    if event.get("fail_after"):
        fail_after = event.get("fail_after")

    print "about to check instances"

    for inst in resp[u'containerInstances']:

        ec2instanceId = str(inst[u'ec2InstanceId'])
        authToken = user['idToken']
        instanceIdExists = db.child(ec2instanceId).get(authToken).val() != None

        # check if agent is connected
        if inst[u'agentConnected']:
            if instanceIdExists:
                db.child(ec2instanceId).remove(authToken)

        # check if agent is not connected
        if not inst[u'agentConnected']:

            numberOfFailures = db.child(ec2instanceId).get(authToken).val()[ec2instanceId]

            # if instance id does not exist in firebase, then add it to firebase
            if not instanceIdExists:
                data = { ec2instanceId : 1 }
                db.child(ec2instanceId).set(data, authToken)
                trackedInFirebase.append((ec2instanceId, 1))

            # if instance id exists but has not reached fail_after, then increment number of fails
            elif instanceIdExists and numberOfFailures < fail_after:
                data = { ec2instanceId : numberOfFailures + 1 }
                db.child(ec2instanceId).set(data, authToken)
                trackedInFirebase.append((ec2instanceId, numberOfFailures+1))

            # if instance id exists in firebase and instance has reached fail_after, then terminate
            else:

                # delete instance id key from firebase
                db.child(ec2instanceId).remove(authToken)

                bad_inst = ec2.Instance(id=ec2instanceId)

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

    # If instances were found for tracking in firebase and we have an SNS topic ARN,
    # send an informative message.
    if len(trackedInFirebase) != 0 and u'snsLogArn' in event:
        sns = boto3.resource("sns")
        topic = sns.Topic(event[u'snsLogArn'])

        message = "ecs-agent-monitor function running in AWS Lambda has detected the following: "

        for (instanceId, failures) in trackedInFirebase:
            msg = """"\
The instance `%s' failed. It has failed %i times. It will be terminated if it fails %i times." 
""" % (instanceId, failures, fail_after)
            message += msg    

        topic.publish(
            Subject="AWS Lambda: ECS-Agent-Monitor",
            Message=message
        )
        

    print "finished publishing message concerning instances tracked in firebase"

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