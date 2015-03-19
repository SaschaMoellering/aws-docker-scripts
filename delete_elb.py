import sys
import getopt

import aws_library
import boto.ec2
import boto.ec2.cloudwatch
from boto.ec2.elb import HealthCheck
from boto.ec2.autoscale import ScalingPolicy


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hi:t:g:", ["image=", "tag=", "region="])
    except getopt.GetoptError:
        print 'delete_elb.py -i <image> -t <tag> -g <region>'
        sys.exit(2)

    image = ''
    tag = ''

    for opt, arg in opts:
        if opt == '-h':
            print 'delete_elb.py -i <image> -t <tag> -g <region>'
            sys.exit()
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-g", "--region"):
            region = arg

    print 'Using image ', image
    print 'Using tag ', tag
    print 'Using region ', region

    delete_elb(image, tag, region)

    sys.exit(0)


def delete_elb(image, tag, region):
    elb_tag = image + tag
    elb_tag = elb_tag.replace("_", "")
    elb_tag = elb_tag.replace("-", "")
    elb_tag = elb_tag.replace(".", "")

    print "Using " + elb_tag

    # Removes metrics and autoscaling

    remove_metrics(region=region, elb_tag=elb_tag)
    remove_autoscaling(region=region, elb_tag=elb_tag)

    conn_elb = boto.ec2.elb.connect_to_region(region_name=region)
    lb_list = conn_elb.get_all_load_balancers(load_balancer_names=[elb_tag + 'Elb'])

    lb = lb_list[0]

    # Deletes instances from ELB

    aws_library.delete_instances_from_lb(image, tag, lb, region, 'normal')

    # Deletes ELB

    lb.delete()


def remove_autoscaling(elb_tag, region):
    conn_as = boto.ec2.autoscale.connect_to_region(region_name=region)

    conn_as.delete_policy(elb_tag + "webserverScaleDownPolicy", elb_tag + "Sg")
    conn_as.delete_policy(elb_tag + "webserverScaleUpPolicy", elb_tag + "Sg")

    conn_as.delete_auto_scaling_group(elb_tag + "Sg")

    conn_as.delete_launch_configuration(elb_tag + "Lc")


def remove_metrics(elb_tag, region):
    cloudwatch = boto.ec2.cloudwatch.connect_to_region(region_name=region)
    scale_up_alarm = elb_tag + 'scale_up_on_cpu'
    scale_down_alarm = elb_tag + 'scale_down_on_cpu'

    cloudwatch.delete_alarms([scale_up_alarm, scale_down_alarm])


if __name__ == "__main__":
    main(sys.argv[1:])