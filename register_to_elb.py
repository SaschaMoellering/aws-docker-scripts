import sys
import getopt
import boto
import boto.ec2.elb

import aws_library

__author__ = 'sascha.moellering'

def main(argv):
    image = ''
    tag = ''
    elb_name = ''
    stage = ''

    try:
        opts, args = getopt.getopt(argv, "hi:t:e:s:g:",
                                   ["image=", "tag=", "elb=", "stage=", "region="])
    except getopt.GetoptError:
        print 'register_to_elb.py -i <image> -t <tag> -e <elb> -s <stage> -g <region>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'register_to_elb.py -i <image> -t <tag>  -e <elb> -s <stage> -g <region>'
            sys.exit()
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-e", "--elb"):
            elb_name = arg
        elif opt in ("-s", "--stage"):
            stage = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-g", "--region"):
            region = arg

    print 'Using image {0}'.format(image)
    print 'Using tag {0}'.format(tag)
    print 'Using elb {0}'.format(elb_name)
    print 'Using stage {0}'.format(stage)
    print 'Using region {0}'.format(region)

    register_to_elb(region=region, image=image, tag=tag, elb=elb_name)

    sys.exit(0)


def register_to_elb(region, image, tag, elb):

    ec2_tag = image + "_" + tag

    conn_elb = boto.ec2.elb.connect_to_region(region_name=region)
    lb_list = conn_elb.get_all_load_balancers([elb])

    if len(lb_list) == 0:
        print "No ELB {0} found".format(elb)
        sys.exit(1)

    lb = lb_list[0]

    aws_library.add_instances_to_lb(ec2_tag, lb, region)

if __name__ == "__main__":
    main(sys.argv[1:])