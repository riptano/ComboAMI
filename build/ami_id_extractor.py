import sys
import json

# Parses the packer's machine-readable output in order to extract the
# the information required to build the ami_id.json file.
#
# Sample input line:
# 1439600749,us-west-1-1204-hvm,artifact,0,id,us-west-1:ami-0f78864b


# Extract the fields we care about from the packer output
amis = []
for line in sys.stdin:
    artifact_fields = line.strip().split(",")

    builder_string = artifact_fields[1]  # ie us-west-1-1204-hvm
    builder_fields = builder_string.split("-")
    release = builder_fields[-2]
    virt_type = builder_fields[-1]

    ami_string = artifact_fields[-1]
    ami_fields = ami_string.split(":")
    region = ami_fields[0]
    ami_id = ami_fields[1]

    # Store them in a dict for easy conversion to json later
    ami_dict = {
        "id": ami_id,
        "Distributor ID": "Ubuntu",
        "Release": release,
        "virtualization type": virt_type,
        "region": region
    }

    # Pack them up in a list for easy sorting and filtering
    amis.append(ami_dict)


# Construct a map in the shape of our ami_ids.json file:
# {
#     {"us-east-1": [ami1, ami2, ami3, ami4]}
#     {"us-west-1": [ami1, ami2, ami3, ami4]}
#     {...}
# }
ami_map = {}
# List all regions we built an ami in, deduplicated by converting to a set()
regions = set([ami["region"] for ami in amis])
# Generate a top-level key per region, containing a list of that region's amis
for region in regions:
    amis_for_region = [ami for ami in amis if ami["region"] == region]
    ami_map[region] = amis_for_region

# I want to get rid of the region key from each ami before final output, it was
# only there to facilitate sorting and filtering.
# I take advantage of the fact that python doesn't copy its mutable maps to
# just iterate through the list mutating the maps and through the magic of
# spooky action at a distance the keys will disappear from the members of
# ami_map as well
for ami in amis:
    del ami["region"]

# Dump out map in json format.
# sort_keys will keep our git diffs readable over time
# indent will pretty-print and make it human-readable
print json.dumps(ami_map, sort_keys=True, indent=4)
