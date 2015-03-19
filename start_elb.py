import sys
import getopt

import boto.ec2
import boto.ec2.cloudwatch
from boto.ec2.elb import HealthCheck
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy
from boto.ec2.cloudwatch import MetricAlarm

import configuration
import aws_library


autoscaling_group = {
    'min_size': 6,  # Minimum number of instances that should be running at all times
    'max_size': 12  # Maximum number of instances that should be running at all times
}


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hr:i:t:s:d:g:a:c:g:", ["registry=", "image=", "tag=", "stage=", "docker_run=",
                                                              "region=", "auto_register=", "health_check="])
    except getopt.GetoptError:
        print 'start_elb.py -r <registry> -i <image> -t <tag> -s <stage> -d <docker_run> -g <region> -a <auto_register>' \
              ' -c <health_check>'
        sys.exit(2)

    registry = ''
    image = ''
    tag = ''
    stage = ''
    docker_run = ''
    region = ''
    auto_register = False
    health_check = ''

    for opt, arg in opts:
        if opt == '-h':
            print 'start_elb.py -r <registry> -i <image> -t <tag> -s <stage> -d <docker_run> -a <auto_register>' \
                  ' -c <health_check> -g <region>'
            sys.exit()
        elif opt in ("-r", "--registry"):
            registry = arg
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-s", "--stage"):
            stage = arg
        elif opt in ("-d", "--docker_run"):
            docker_run = arg
        elif opt in ("-g", "--region"):
            region = arg
        elif opt in ("-a", "--autoregister"):
            auto_register = aws_library.str_to_bool(arg)
        elif opt in ("-c", "--health_check"):
            health_check = arg

    print 'Using registry ', registry
    print 'Using image ', image
    print 'Using tag ', tag
    print 'Using stage ', stage
    print 'Using region ', region
    print 'Using docker_run ', docker_run
    print 'Using auto_register {0}'.format(auto_register)
    print 'Using health check path {0}'.format(health_check)

    config_dict = configuration.Environment.aws_config[region][stage]
    ami_id = aws_library.get_latest_ami(region, config_dict["ami_id"])
    print "Using AMI {0}".format(ami_id)
    ec2_key_handle = config_dict["ec2_key_handle"]
    instance_type = config_dict["instance_type"]
    security_groups = config_dict["security_groups"]
    subnet_id = config_dict["subnet_id"]
    public_ip_address = config_dict["public_ip_address"]
    iam_role = config_dict["iam_role"]
    zone_strings = config_dict["availability_zones"]

    as_ami = {
        'id': ami_id,  # The AMI ID of the instance your Auto Scaling group will launch
        'access_key': ec2_key_handle,  # The key the EC2 instance will be configured with
        'security_groups': security_groups,  # The security group(s) your instances will belong to
        'instance_type': instance_type,  # The size of instance that will be launched
        'instance_monitoring': True  # Indicated whether the instances will be launched with detailed monitoring enabled.
    }

    elastic_load_balancer = {
        'health_check_target': 'HTTP:8080/{0}'.format(health_check),  # Location to perform health checks
        'connection_forwarding': [(80, 8080, 'http'), (443, 8443, 'tcp')],
        # [Load Balancer Port, EC2 Instance Port, Protocol]
        'timeout': 3,  # Number of seconds to wait for a response from a ping
        'interval': 20  # Number of seconds between health checks
    }

    images_list = aws_library.search_images_in_registry(registry=registry, image_name=image)

    dockerrun_dict = aws_library.convert_to_dict(dockerrun=docker_run, image_name=image)
    user_data = configuration.create_user_data(registry=registry, images=images_list, tag=tag, stage=stage,
                                               dockerrun=dockerrun_dict)

    print 'User-Data: \n', user_data
    start_elb(tag=image + "_" + tag, user_data=user_data, region=region, auto_register=auto_register, as_ami=as_ami,
              subnet_id=subnet_id, security_groups=security_groups, public_ip_address=public_ip_address,
              iam_role=iam_role, zone_strings=zone_strings, elastic_load_balancer=elastic_load_balancer)

    sys.exit(0)


def start_elb(tag, user_data, region, auto_register, as_ami, subnet_id, security_groups, public_ip_address, iam_role,
              zone_strings, elastic_load_balancer):
    print "Using tag \"" + tag + "\""
    conn_reg = boto.ec2.connect_to_region(region_name=region)
    # =================Construct a list of all availability zones for your region=========

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

    print "ELB name: \"" + elb_tag + "\""

    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.elb.ELBConnection.create_load_balancer
    lb = conn_elb.create_load_balancer(name=elb_tag + 'Elb',
                                       zones=None,
                                       subnets=subnet_id,
                                       security_groups=security_groups,
                                       listeners=elastic_load_balancer['connection_forwarding'])

    if auto_register:
        aws_library.add_instances_to_lb(tag=tag, lb=lb, region=region)

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
                          vpc_zone_identifier=subnet_id)
    conn_as.create_auto_scaling_group(ag)

    # =================Create Scaling Policies=============================================
    # Policy for scaling the number of servers up and down
    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.policy.ScalingPolicy
    scaling_up_policy = ScalingPolicy(name=elb_tag + "webserverScaleUpPolicy",
                                      adjustment_type='ChangeInCapacity',
                                      as_name=ag.name,
                                      scaling_adjustment=1,
                                      cooldown=60)

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