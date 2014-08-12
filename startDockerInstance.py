import boto.ec2
import sys, getopt, time, copy

REGION = 'eu-west-1'
AMI_ID = 'ami-892fe1fe'
EC2_KEY_HANDLE = 'jenkins'
INSTANCE_TYPE = 't2.micro'

def main(argv):

    registry = ''
    image = ''
    tag = ''
    quantity = 1

    try:
        opts, args = getopt.getopt(argv, "hr:i:t:q:", ["registry=", "image=", "tag=", "quantity="])
    except getopt.GetoptError:
        print 'startDockerInstance.py -r <registry> -i <image> -t <tag> -q <quantity>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'startDockerInstance.py -r <registry> -i <image> -t <tag> -q <quantity>'
            sys.exit()
        elif opt in ("-r", "--registry"):
            registry = arg
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-q", "--quantity"):
            quantity = int(arg)
    print 'Using registry ', registry
    print 'Using image ', image
    print 'Using tag ', tag
    print 'Using quantity ', quantity

    payload = create_payload(registry=registry, image=image, tag=tag)
    print 'User-Data: ', payload

    start_ec2_instance(payload, quantity, tag, image)


def create_payload(registry, image, tag):

    fully_qualified_image = registry + "/" + image + ":" + tag

    payload = '#!/bin/bash\n'
    payload += 'yum update -y\n'
    payload += 'yum install docker -y\n'
    payload += 'service docker start\n'
    payload += 'su -c "docker pull ' + fully_qualified_image + '"\n'
    payload += 'su -c "docker run ' + fully_qualified_image + '"'

    return payload


def start_ec2_instance(payload, quantity, tag, image):
    conn = boto.ec2.connect_to_region(REGION)

    # Create a block device mapping

    dev_xvda = boto.ec2.blockdevicemapping.EBSBlockDeviceType()
    dev_xvda.size = 8  # size in Gigabytes
    bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    bdm['/dev/xvda'] = dev_xvda

    reservation = conn.run_instances(min_count=quantity,
                       max_count=quantity,
                       image_id=AMI_ID,
                        key_name=EC2_KEY_HANDLE,
                        instance_type=INSTANCE_TYPE,
                        security_groups = ['vertx'],
                        block_device_map = bdm,
                        user_data=payload,
                        ebs_optimized=False)

    instance_ids = []
    for instance in reservation.instances:
        instance.add_tag('application', image + '_' + tag)
        print "Tagging ip %s with tag %s" % (instance.__dict__['ip_address'], (image + '_' + tag))
        instance_ids.append(instance.id)

    wait_for_instances_to_start(conn, instance_ids, copy.deepcopy(instance_ids))

    return 0


def wait_for_instances_to_start(conn, instance_ids, pending_ids):
    """Loop through all pending instace ids waiting for them to start.
        If an instance is running, remove it from pending_ids.
        If there are still pending requests, sleep and check again in 10 seconds.
        Only return when all instances are running."""
    reservations = conn.get_all_instances(instance_ids=pending_ids)
    for reservation in reservations:
        for instance in reservation.instances:
            if instance.state == 'running':
                print "instance `{}` running!".format(instance.id)
                pending_ids.pop(pending_ids.index(instance.id))
            else:
                print "instance `{}` starting...".format(instance.id)
    if len(pending_ids) == 0:
        print "all instances started!"
    else:
        time.sleep(10)
        wait_for_instances_to_start(conn, instance_ids, pending_ids)


if __name__ == "__main__":
    main(sys.argv[1:])