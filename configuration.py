class Environment():
    aws_config = {}
    live_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                   "ec2_key_handle": "", "instance_type": "t2.micro",
                   "security_groups": ['sg-'], "subnet_id": ['subnet-', 'subnet-'],
                   "public_ip_address": False, "iam_role": "",
                   "availability_zones": ['eu-west-1a', 'eu-west-1b']}

    quality_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                      "ec2_key_handle": "", "instance_type": "t2.micro",
                      "security_groups": ['sg-'], "subnet_id": ['subnet-', 'subnet-'],
                      "public_ip_address": False, "iam_role": "",
                      "availability_zones": ['eu-west-1a', 'eu-west-1b']}

    staging_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                   "ec2_key_handle": "", "instance_type": "t2.micro",
                   "security_groups": ['sg-'], "subnet_id": ['subnet-', 'subnet-'],
                   "public_ip_address": False, "iam_role": "",
                   "availability_zones": ['eu-west-1a', 'eu-west-1b']}

    test_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                   "ec2_key_handle": "", "instance_type": "t2.micro",
                   "security_groups": ['sg-'], "subnet_id": ['subnet-', 'subnet-'],
                   "public_ip_address": False, "iam_role": "",
                   "availability_zones": ['eu-west-1a', 'eu-west-1b']}

    aws_config['live'] = live_config
    aws_config['quality'] = quality_config
    aws_config['staging'] = staging_config
    aws_config['test'] = test_config


def create_user_data(registry, images, tag, stage, dockerrun):
    user_data = '#!/bin/bash\n'
    user_data += 'yum update -y\n'
    user_data += 'yum install docker -y\n'
    user_data += 'service docker start\n'

    for image in images:
        fully_qualified_image = registry + "/" + image + ":" + tag
        user_data += 'su -c "docker run --env stage=' + stage + ' ' + dockerrun + ' ' + fully_qualified_image + '"\n'

    return user_data



