class Environment():
    aws_config = {}
    live_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                   "ec2_key_handle": "", "instance_type": "t2.micro",
                   "security_groups": ['']}

    quality_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                      "ec2_key_handle": "", "instance_type": "t2.micro",
                      "security_groups": ['']}

    staging_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                      "ec2_key_handle": "", "instance_type": "t2.micro",
                      "security_groups": ['']}

    test_config = {"region": "eu-west-1", "ami_id": "ami-892fe1fe",
                   "ec2_key_handle": "", "instance_type": "t2.micro",
                   "security_groups": ['']}

    aws_config['live'] = live_config
    aws_config['quality'] = quality_config
    aws_config['staging'] = staging_config
    aws_config['test'] = test_config


def create_user_data(registry, image, tag):
    fully_qualified_image = registry + "/" + image + ":" + tag

    user_data = '#!/bin/bash\n'
    user_data += 'yum update -y\n'
    user_data += 'yum install docker -y\n'
    user_data += 'service docker start\n'
    user_data += 'su -c "docker pull ' + fully_qualified_image + '"\n'
    user_data += 'su -c "docker run -p 8080:8080 -d ' + fully_qualified_image + '"'

    return user_data


