import string
import boto
import boto.ec2
import requests

# Library for common AWS tasks


def search_images_in_registry(registry, image_name):

    # Search for images in Docker registry
    # Returns a list of images with the prefix 'image_name'

    query = "http://{0}/v1/search?q={1}".format(registry, image_name)
    print "Using query: " + query
    resp = requests.get(query)

    image_list = []
    json_resp = resp.json()
    for result in json_resp['results']:
        name = result['name'].replace("library/", "")
        image_list.append(name)

    return image_list


def convert_to_dict(dockerrun, image_name):
    docker_dict = {}
    docker_array = string.split(dockerrun, ";")
    for line in docker_array:
        if "=" in line:
            line_array = string.split(line, "=")
            key = image_name + "-" + line_array[0]
            value = line_array[1]
        else:
            key = image_name
            value = line

        docker_dict[key] = value

    return docker_dict


def str_to_bool(s):
    if s == 'True':
        return True
    elif s == 'False':
        return False
    else:
        raise ValueError


def get_latest_ami(region, image):

    # Returns the lastest AMI version for the custom zanox AMI

    ec2conn = boto.ec2.connect_to_region(region)
    images = ec2conn.get_all_images(filters={"tag:ami-name": image})
    ami_ids = []
    for i in images:
        print "Found AMI {0} - {1}".format(i.id, i.name)
        ami_ids.append(i.id)

    image_id = ''
    if len(ami_ids) > 0:
        image_id = (sorted(ami_ids, reverse=True))[0]

    return image_id


def add_instances_to_lb(tag, lb, region):

    # Adds running EC2 instances to a specific ELB

    ec2conn = boto.ec2.connect_to_region(region_name=region)

    print "Filtering running instances for tag application => " + tag

    reservations = ec2conn.get_all_instances(filters={"tag:application": tag})
    instances = [i for r in reservations for i in r.instances]
    instance_ids = []
    for instance in instances:
        if instance.state == 'running':
            print "Adding instance {0}".format(instance.id)
            instance_ids.append(instance.id)

    if len(instance_ids) > 0:
        lb.register_instances(instance_ids)


def delete_instances_from_lb(image, tag, lb, region, mode):

    # Removes running EC2 instances from an ELB

    ec2conn = boto.ec2.connect_to_region(region_name=region)

    application_tag = image + "_" + tag
    instances = []

    if mode == 'normal':
        reservations = ec2conn.get_all_instances(filters={"tag:application": application_tag})
        instances = [i for r in reservations for i in r.instances]
    elif mode == 'inverse':
        all_reservations = ec2conn.get_all_instances(filters={"tag:Name": image})
        for r in all_reservations:
            for i in r.instances:
                tags = i.tags
                if 'application_version' in tags:
                    if i.tags['application_version'] == tag:
                        print "Added instance {0} to removal list".format(i.id)
                        instances.append(i)

    instance_ids = []
    for instance in instances:
        if instance.state == 'running':
            print "Removing instance {0}".format(instance.id)
            instance_ids.append(instance.id)

    if len(instance_ids) > 0:
        lb.deregister_instances(instance_ids)





