import sys
import getopt
import time
import copy

import boto.ec2

import configuration


config_dict = configuration.Environment.aws_config["test"]
region = config_dict["region"]


def main(argv):
    registry = ''
    image = ''
    tag = ''

    try:
        opts, args = getopt.getopt(argv, "hr:i:t:", ["registry=", "image=", "tag="])
    except getopt.GetoptError:
        print 'delete_docker_instance.py -r <registry> -i <image> -t <tag>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'start_docker_instance.py -r <registry> -i <image> -t <tag>'
            sys.exit()
        elif opt in ("-r", "--registry"):
            registry = arg
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg

    print 'Using registry ', registry
    print 'Using image ', image
    print 'Using tag ', tag

    delete_instances(tag, image)

    return 0


def delete_instances(tag, image):
    ec2conn = boto.ec2.connect_to_region(region_name=region)

    reservations = ec2conn.get_all_instances(filters={"tag:application": image + "_" + tag})
    instance_ids = [i.id for r in reservations for i in r.instances]

    ec2conn.terminate_instances(instance_ids)
    wait_for_instances_to_stop(ec2conn, instance_ids, copy.deepcopy(instance_ids))


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