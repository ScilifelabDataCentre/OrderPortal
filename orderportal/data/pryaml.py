"Read YAML file and print."

import sys
import pprint
import yaml

data = yaml.safe_load(open(sys.argv[1]))
pprint.pprint(data)
