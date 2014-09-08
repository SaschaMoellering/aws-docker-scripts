import sys
import getopt

import boto.ec2
import boto.ec2.cloudwatch
from boto.ec2.elb import HealthCheck
from boto.ec2.autoscale import ScalingPolicy

import configuration


config_dict = configuration.Environment.aws_config["test"]
ami_id = config_dict["ami_id"]
ec2_key_handle = config_dict["ec2_key_handle"]
instance_type = config_dict["instance_type"]
security_groups = config_dict["security_groups"]
region = config_dict["region"]


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hi:t:", ["image=", "tag="])
    except getopt.GetoptError:
        print 'delete_elb.py -i <image> -t <tag>'
        sys.exit(2)

    image = ''
    tag = ''

    for opt, arg in opts:
        if opt == '-h':
            print 'delete_elb.py -i <image> -t <tag>'
            sys.exit()
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg

    print 'Using image ', image
    print 'Using tag ', tag

    delete_elb(image, tag)

    sys.exit(0)


def delete_elb(image, tag):
    elb_tag = image + tag
    elb_tag = elb_tag.replace("_", "")
    elb_tag = elb_tag.replace("-", "")
    elb_tag = elb_tag.replace(".", "")

    print "Using " + elb_tag

    remove_metrics(elb_tag)
    remove_autoscaling(elb_tag)

    conn_elb = boto.ec2.elb.connect_to_region(region_name=region)
    lb_list = conn_elb.get_all_load_balancers(load_balancer_names=[elb_tag + 'Elb'])

    lb = lb_list[0]
    delete_instances_from_lb(image + "_" + tag, lb)

    lb.delete()


def delete_instances_from_lb(tag, lb):
    ec2conn = boto.ec2.connect_to_region(region_name=region)

    reservations = ec2conn.get_all_instances(filters={"tag:application": tag})
    instances = [i for r in reservations for i in r.instances]
    instance_ids = []
    for instance in instances:
        if instance.state == 'running':
            instance_ids.append(instance.id)

    lb.deregister_instances(instance_ids)


def remove_autoscaling(elb_tag):
    conn_as = boto.ec2.autoscale.connect_to_region(region_name=region)

    conn_as.delete_policy(elb_tag + "webserverScaleDownPolicy", elb_tag + "Sg")
    conn_as.delete_policy(elb_tag + "webserverScaleUpPolicy", elb_tag + "Sg")

    conn_as.delete_auto_scaling_group(elb_tag + "Sg")

    conn_as.delete_launch_configuration(elb_tag + "Lc")


def remove_metrics(elb_tag):
    cloudwatch = boto.ec2.cloudwatch.connect_to_region(region_name=region)
    scale_up_alarm = elb_tag + 'scale_up_on_cpu'
    scale_down_alarm = elb_tag + 'scale_down_on_cpu'

    cloudwatch.delete_alarms([scale_up_alarm, scale_down_alarm])


if __name__ == "__main__":
    main(sys.argv[1:])