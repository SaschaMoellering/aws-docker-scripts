import sys
import getopt
import time
import copy

import boto.ec2

import configuration


def main(argv):
    registry = ''
    image = ''
    tag = ''
    region = ''

    try:
        opts, args = getopt.getopt(argv, "hr:i:t:g:", ["registry=", "image=", "tag=", "region="])
    except getopt.GetoptError:
        print 'delete_docker_instance.py -r <registry> -i <image> -t <tag> -g <region>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'start_docker_instance.py -r <registry> -i <image> -t <tag> -g <region>'
            sys.exit()
        elif opt in ("-r", "--registry"):
            registry = arg
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-g", "--region"):
            region = arg

    print 'Using registry ', registry
    print 'Using image ', image
    print 'Using tag ', tag
    print 'Using region ', region

    instance_ids = delete_instances(tag, image, region)

    sys.stdout.write(''.join(instance_ids))
    sys.exit(0)


def delete_instances(tag, image, region):

    # Searching for EC2 instances using tags

    ec2conn = boto.ec2.connect_to_region(region_name=region)

    reservations = ec2conn.get_all_instances(filters={"tag:application": image + "_" + tag})
    instances = [i for r in reservations for i in r.instances]
    instance_ids = []
    for instance in instances:
        if instance.state == 'running':
            instance_ids.append(instance.id)

    # Terminates running instances

    if len(instance_ids) > 0:
        ec2conn.terminate_instances(instance_ids)
        wait_for_instances_to_stop(ec2conn, instance_ids, copy.deepcopy(instance_ids))
    else:
        print "No instances found for tag:application with value:" + (image + "_" + tag)

    return instance_ids


def wait_for_instances_to_stop(conn, instance_ids, pending_ids):
    """Loop through all pending instace ids waiting for them to start.
        If an instance is running, remove it from pending_ids.
        If there are still pending requests, sleep and check again in 10 seconds.
        Only return when all instances are running."""
    reservations = conn.get_all_instances(instance_ids=pending_ids)
    for reservation in reservations:
        for instance in reservation.instances:
            print "State: " + instance.state
            if instance.state == 'terminated':
                print "instance `{" + instance.id + "}` terminated!"
                pending_ids.pop(pending_ids.index(instance.id))
            else:
                print "instance `{" + instance.id + "}` stopping..."
    if len(pending_ids) == 0:
        print "all instances terminated!"
    else:
        time.sleep(10)
        wait_for_instances_to_stop(conn, instance_ids, pending_ids)


if __name__ == "__main__":
    main(sys.argv[1:])