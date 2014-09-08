import sys
import getopt
import os

import boto.ec2
import boto.ec2.cloudwatch
from boto.ec2.elb import HealthCheck
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy
from boto.ec2.cloudwatch import MetricAlarm

import configuration
import docker_library


config_dict = configuration.Environment.aws_config["test"]
ami_id = config_dict["ami_id"]
ec2_key_handle = config_dict["ec2_key_handle"]
instance_type = config_dict["instance_type"]
security_groups = config_dict["security_groups"]
region = config_dict["region"]
subnet_id = config_dict["subnet_id"]
public_ip_address = config_dict["public_ip_address"]
iam_role = config_dict["iam_role"]

AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY']
AWS_SECRET_KEY = os.environ['AWS_SECRET_KEY']

elastic_load_balancer = {
    'health_check_target': 'HTTP:8080/index.html',  # Location to perform health checks
    'connection_forwarding': [(80, 8080, 'http'), (443, 8443, 'tcp')],
    # [Load Balancer Port, EC2 Instance Port, Protocol]
    'timeout': 3,  # Number of seconds to wait for a response from a ping
    'interval': 20  # Number of seconds between health checks
}

autoscaling_group = {
    'min_size': 2,  # Minimum number of instances that should be running at all times
    'max_size': 3  # Maximum number of instances that should be running at all times
}

# =================AMI to launch======================================================
as_ami = {
    'id': ami_id,  # The AMI ID of the instance your Auto Scaling group will launch
    'access_key': ec2_key_handle,  # The key the EC2 instance will be configured with
    'security_groups': security_groups,  # The security group(s) your instances will belong to
    'instance_type': instance_type,  # The size of instance that will be launched
    'instance_monitoring': True  # Indicated whether the instances will be launched with detailed monitoring enabled.
    # Needed to enable CloudWatch
}


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hr:i:t:", ["registry=", "image=", "tag="])
    except getopt.GetoptError:
        print 'start_elb.py -r <registry> -i <image> -t <tag>'
        sys.exit(2)

    registry = ''
    image = ''
    tag = ''

    for opt, arg in opts:
        if opt == '-h':
            print 'start_elb.py -r <registry> -i <image> -t <tag>'
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

    images_list = docker_library.search_images_in_registry(registry=registry, image_name=image)

    user_data = configuration.create_user_data(registry=registry, images=images_list, tag=tag)

    print 'User-Data: \n', user_data
    start_elb(tag=image + "_" + tag, user_data=user_data)

    return 0


def add_instances_to_lb(tag, lb):
    ec2conn = boto.ec2.connect_to_region(region_name=region)

    print "Filtering instances for tag application => " + tag

    reservations = ec2conn.get_all_instances(filters={"tag:application": tag})
    instance_ids = [i.id for r in reservations for i in r.instances]

    lb.register_instances(instance_ids)


def start_elb(tag, user_data):
    print "Using tag \"" + tag + "\""
    conn_reg = boto.ec2.connect_to_region(region_name=region)
    # =================Construct a list of all availability zones for your region=========
    zones = conn_reg.get_all_zones()

    zone_strings = []
    for zone in zones:
        print "Zone: " + zone.name
        zone_strings.append(zone.name)

    conn_elb = boto.ec2.elb.connect_to_region(region_name=region)
    conn_as = boto.ec2.autoscale.connect_to_region(region_name=region)

    # =================Create a Load Balancer=============================================
    # For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#module-boto.ec2.elb.healthcheck
    hc = HealthCheck('healthCheck',
                     interval=elastic_load_balancer['interval'],
                     target=elastic_load_balancer['health_check_target'],
                     timeout=elastic_load_balancer['timeout'])

    # ELB does not accept any special characters
    elb_tag = tag
    elb_tag = elb_tag.replace("_", "")
    elb_tag = elb_tag.replace("-", "")
    elb_tag = elb_tag.replace(".", "")

    print "ELB tag: \"" + elb_tag + "\""

    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.elb.ELBConnection.create_load_balancer
    lb = conn_elb.create_load_balancer(name=elb_tag + 'Elb',
                                       zones=zone_strings,
                                       listeners=elastic_load_balancer['connection_forwarding'])

    add_instances_to_lb(tag, lb)

    lb.configure_health_check(hc)

    # DNS name for your new load balancer
    print "Map the CNAME of your website to: %s" % lb.dns_name

    # =================Create a Auto Scaling Group and a Launch Configuration============================================
    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.launchconfig.LaunchConfiguration
    lc = LaunchConfiguration(name=elb_tag + "Lc", image_id=as_ami['id'],
                             key_name=as_ami['access_key'],
                             security_groups=as_ami['security_groups'],
                             instance_type=as_ami['instance_type'],
                             instance_monitoring=as_ami['instance_monitoring'],
                             instance_profile_name=iam_role,
                             user_data=user_data)
    conn_as.create_launch_configuration(lc)

    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.group.AutoScalingGroup

    ag = AutoScalingGroup(group_name=elb_tag + "Sg",
                          load_balancers=[elb_tag],
                          availability_zones=zone_strings,
                          launch_config=lc, min_size=autoscaling_group['min_size'],
                          max_size=autoscaling_group['max_size'],
                          associate_public_ip_address=public_ip_address,
                          vpc_zone_identifier=[subnet_id])
    conn_as.create_auto_scaling_group(ag)

    # =================Create Scaling Policies=============================================
    # Policy for scaling the number of servers up and down
    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.policy.ScalingPolicy
    scaling_up_policy = ScalingPolicy(name=elb_tag + "webserverScaleUpPolicy",
                                      adjustment_type='ChangeInCapacity',
                                      as_name=ag.name,
                                      scaling_adjustment=1,
                                      cooldown=180)

    scaling_down_policy = ScalingPolicy(name=elb_tag + "webserverScaleDownPolicy",
                                        adjustment_type='ChangeInCapacity',
                                        as_name=ag.name,
                                        scaling_adjustment=-1,
                                        cooldown=180)

    conn_as.create_scaling_policy(scaling_up_policy)
    conn_as.create_scaling_policy(scaling_down_policy)

    scaling_up_policy = conn_as.get_all_policies(
        as_group=elb_tag + "Sg",
        policy_names=[elb_tag + "webserverScaleUpPolicy"])[0]
    scaling_down_policy = conn_as.get_all_policies(
        as_group=elb_tag + "Sg",
        policy_names=[elb_tag + "webserverScaleDownPolicy"])[0]

    cloudwatch = boto.ec2.cloudwatch.connect_to_region(region)
    alarm_dimensions = {"AutoScalingGroupName": 'my_group'}

    scale_up_alarm = MetricAlarm(name=elb_tag + 'scale_up_on_cpu',
                                 namespace='AWS/EC2',
                                 metric='CPUUtilization',
                                 statistic='Average',
                                 comparison='>',
                                 threshold='70',
                                 period='60',
                                 evaluation_periods=2,
                                 alarm_actions=[scaling_up_policy.policy_arn],
                                 dimensions=alarm_dimensions)

    scale_down_alarm = MetricAlarm(name=elb_tag + 'scale_down_on_cpu',
                                   namespace='AWS/EC2',
                                   metric='CPUUtilization',
                                   statistic='Average',
                                   comparison='<',
                                   threshold='40',
                                   period='60',
                                   evaluation_periods=2,
                                   alarm_actions=[scaling_down_policy.policy_arn],
                                   dimensions=alarm_dimensions)

    cloudwatch.create_alarm(scale_down_alarm)
    cloudwatch.create_alarm(scale_up_alarm)


if __name__ == "__main__":
    main(sys.argv[1:])