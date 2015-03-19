class Environment():
    aws_config = {}
    eu_west_live_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                   "ec2_key_handle": "", "instance_type": "t2.micro",
                   "security_groups": ['sg-'], "subnet_id": ['subnet-', 'subnet-'],
                   "public_ip_address": True, "iam_role": "",
                   "availability_zones": ['eu-west-1a', 'eu-west-1b']}

    eu_west_staging_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                   "ec2_key_handle": "", "instance_type": "t2.micro",
                   "security_groups": ['sg-'], "subnet_id": ['subnet-', 'subnet-'],
                   "public_ip_address": True, "iam_role": "",
                   "availability_zones": ['eu-west-1a', 'eu-west-1b']}

    eu_west_config = {'live': eu_west_live_config, 'staging': eu_west_staging_config}
    aws_config['eu-west-1'] = eu_west_config


def create_user_data(registry, images, tag, stage, dockerrun):
    user_data = '#!/bin/bash\n'
    user_data += 'yum update -y\n'
    user_data += 'yum install docker -y\n'
    user_data += 'echo "OPTIONS=\\"-H 0.0.0.0:2375 -H unix:///var/run/docker.sock --insecure-registry {0}\\"" >' \
                 ' /etc/sysconfig/docker\n'.format(registry)

    user_data += 'service docker start\n'

    for image in images:
        if image in dockerrun:
            fully_qualified_image = "{0}/{1}:{2}".format(registry, image, tag)

            user_data += 'su -c "docker run --restart=always --env stage={0} {1} {2}"\n' \
                .format(stage, dockerrun[image], fully_qualified_image)

            print user_data

    return user_data



