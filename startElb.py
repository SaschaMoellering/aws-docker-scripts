import boto.ec2

from boto.ec2.elb import ELBConnection
from boto.ec2.elb import HealthCheck

from boto.ec2.autoscale import AutoScaleConnection
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy

import sys, getopt, os

REGION = 'eu-west-1'
AMI_ID = 'ami-892fe1fe'
EC2_KEY_HANDLE = 'jenkins'
INSTANCE_TYPE = 't2.micro'
SECURITY_GROUPS = ['']

AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY']
AWS_SECRET_KEY = os.environ['AWS_SECRET_KEY']

elastic_load_balancer = {
    'health_check_target': 'HTTP:8080/index.html',#Location to perform health checks
    'connection_forwarding': [(80, 8080, 'http'), (443, 8443, 'tcp')],#[Load Balancer Port, EC2 Instance Port, Protocol]
    'timeout': 3, #Number of seconds to wait for a response from a ping
    'interval': 20 #Number of seconds between health checks
}

autoscaling_group = {
    'min_size': 2,#Minimum number of instances that should be running at all times
    'max_size': 3 #Maximum number of instances that should be running at all times
}

#=================AMI to launch======================================================
as_ami = {
    'id': AMI_ID, #The AMI ID of the instance your Auto Scaling group will launch
    'access_key': EC2_KEY_HANDLE, #The key the EC2 instance will be configured with
    'security_groups': SECURITY_GROUPS, #The security group(s) your instances will belong to
    'instance_type': INSTANCE_TYPE, #The size of instance that will be launched
    'instance_monitoring': True #Indicated whether the instances will be launched with detailed monitoring enabled. Needed to enable CloudWatch
}


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hr:i:t:", ["registry=", "image=", "tag="])
    except getopt.GetoptError:
        print 'startElb.py -r <registry> -i <image> -t <tag>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'startElb.py -r <registry> -i <image> -t <tag>'
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

    payload = create_payload(registry=registry, image=image, tag=tag)
    print 'User-Data: ', payload
    startElb(tag=tag, payload=payload)

    return 0


def create_payload(registry, image, tag):

    fully_qualified_image = registry + "/" + image + ":" + tag

    payload = '#!/bin/bash\n'
    payload += 'yum update -y\n'
    payload += 'yum install docker -y\n'
    payload += 'service docker start\n'
    payload += 'su -c "docker pull ' + fully_qualified_image + '"\n'
    payload += 'su -c "docker run ' + fully_qualified_image + '"'

    return payload


def addInstancesToLb(tag, lb):
    ec2conn = boto.ec2.connect_to_region(region_name=REGION)

    reservations = ec2conn.get_all_instances(filters={"tag:application": tag});
    instances = [i for r in reservations for i in r.instances]

    for inst in instances:
        lb.register_instance(inst.id)


def startElb(tag, payload):
    conn_reg = boto.ec2.connect_to_region(region_name=REGION)
    #=================Construct a list of all availability zones for your region=========
    zones = conn_reg.get_all_zones()

    zoneStrings = []
    for zone in zones:
        zoneStrings.append(zone.name)

    conn_elb = ELBConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY)
    conn_as = AutoScaleConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY)

    #=================Create a Load Balancer=============================================
    #For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#module-boto.ec2.elb.healthcheck
    hc = HealthCheck('healthCheck',
                 interval=elastic_load_balancer['interval'],
                 target=elastic_load_balancer['health_check_target'],
                 timeout=elastic_load_balancer['timeout'])

    #For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.elb.ELBConnection.create_load_balancer
    lb = conn_elb.create_load_balancer(tag + '_elb',
                                   zoneStrings,
                                   elastic_load_balancer['connection_forwarding'])

    addInstancesToLb(tag, lb)

    lb.configure_health_check(hc)

    #DNS name for your new load balancer
    print "Map the CNAME of your website to: %s" % (lb.dns_name)

    #=================Create a Auto Scaling Group and a Launch Configuration=============================================
    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.launchconfig.LaunchConfiguration
    lc = LaunchConfiguration(name=tag + "_lc", image_id=as_ami['id'],
                         key_name=as_ami['access_key'],
                         security_groups=as_ami['security_groups'],
                         instance_type=as_ami['instance_type'],
                         instance_monitoring=as_ami['instance_monitoring'],
                         user_data=payload)
    conn_as.create_launch_configuration(lc)

    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.group.AutoScalingGroup
    ag = AutoScalingGroup(group_name=tag + "_sg", load_balancers=[elastic_load_balancer['name']],
                      availability_zones=zoneStrings,
                      launch_config=lc, min_size=autoscaling_group['min_size'], max_size=autoscaling_group['max_size'])
    conn_as.create_auto_scaling_group(ag)


    #=================Create Scaling Policies=============================================
    # Policy for scaling the number of servers up and down
    # For a complete list of options see
    # http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.policy.ScalingPolicy
    scalingUpPolicy = ScalingPolicy(name='webserverScaleUpPolicy',
                                          adjustment_type='ChangeInCapacity',
                                          as_name=ag.name,
                                          scaling_adjustment=2,
                                          cooldown=180)

    scalingDownPolicy = ScalingPolicy(name='webserverScaleDownPolicy',
                                          adjustment_type='ChangeInCapacity',
                                          as_name=ag.name,
                                          scaling_adjustment=-1,
                                          cooldown=180)

    conn_as.create_scaling_policy(scalingUpPolicy)
    conn_as.create_scaling_policy(scalingDownPolicy)



if __name__ == "__main__":
    main(sys.argv[1:])