#! /usr/bin/python

import copy
import json
import sys

MAXRANGE = (2**127)

global_data = {}
global_data['offsets'] = {}

def calculate_tokens():
    tokens = {}
    for dc in range(len(global_data['datacenters'])):
        tokens[dc] = {}
        for i in range(int(global_data['datacenters'][dc])):
            tokens[dc][i] = (i * MAXRANGE / int(global_data['datacenters'][dc]))

    global_data['tokens'] = tokens

def two_closest_tokens(this_dc, this_token):
    tokens = get_offset_tokens()
    lower_bound = 0
    upper_bound = MAXRANGE

    for that_dc in tokens:
        if this_dc == that_dc:
            continue

        that_dc = tokens[that_dc]

        for that_node in that_dc:
            that_token = that_dc[that_node]

            if that_token <= this_token and that_token > lower_bound:
                lower_bound = that_token
            if that_token > this_token and that_token < upper_bound:
                upper_bound = that_token

    return lower_bound, upper_bound

def get_offset_tokens():
    offset_tokens = copy.deepcopy(global_data['tokens'])
    for dc in offset_tokens:
        if dc == 0:
            continue
        for node in offset_tokens[dc]:
            offset = global_data['offsets'][dc] if dc in global_data['offsets'] else 0
            offset_tokens[dc][node] = (offset_tokens[dc][node] + offset) % MAXRANGE
    return offset_tokens

def calculate_offsets():
    exit_loop = False
    while not exit_loop:
        exit_loop = True

        tokens = get_offset_tokens()
        for this_dc in range(len(tokens)):
            if this_dc == 0:
                continue

            tokens = get_offset_tokens()
            global_data['offsets'][this_dc] = global_data['offsets'][this_dc] if this_dc in global_data['offsets'] else 0
            previous_offset = global_data['offsets'][this_dc]
            running_offset = []

            for this_node in range(len(tokens[this_dc])):
                this_token = tokens[this_dc][this_node]
                lower_bound, upper_bound = two_closest_tokens(this_dc, this_token)
                perfect_spot = (upper_bound - lower_bound) / 2 + lower_bound
                this_offset = perfect_spot - this_token
                running_offset.append(this_offset)

            global_data['offsets'][this_dc] += sum(running_offset) / len(running_offset)
            if global_data['offsets'][this_dc] - previous_offset > 0:
                exit_loop = False


def print_tokens():
    print 'Offsets: ', global_data['offsets']
    print json.dumps(get_offset_tokens(), sort_keys=True, indent=4)

def run(datacenters):
    global_data['datacenters'] = datacenters
    calculate_tokens()
    calculate_offsets()
    return get_offset_tokens()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        datacenters = sys.argv[1:]
    else:
        print "Usage: ./tokentoolv2.py <nodes_in_dc> [<nodes_in_dc>]..."
        sys.exit(0)
    run(datacenters)
    print_tokens()
