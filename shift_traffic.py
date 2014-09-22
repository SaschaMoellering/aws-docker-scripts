import sys
import getopt
import os

#AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY']
#AWS_SECRET_KEY = os.environ['AWS_SECRET_KEY']


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hr:i:t:", ["registry=", "image=", "tag="])
    except getopt.GetoptError:
        print 'shift_traffic.py -r <registry> -i <image> -t <tag>'
        sys.exit(2)

    return 0


if __name__ == "__main__":
    main(sys.argv[1:])