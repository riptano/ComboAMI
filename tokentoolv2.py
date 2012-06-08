#! /usr/bin/python

import copy
import json
import sys

global_data = {}
global_data['MAXRANGE'] = (2**127)

def calculate_tokens():
    """Sets the default tokens that each datacenter has to be spaced with."""

    tokens = {}
    for dc in range(len(global_data['datacenters'])):
        tokens[dc] = {}

        for i in range(int(global_data['datacenters'][dc])):
            tokens[dc][i] = (i * global_data['MAXRANGE'] / int(global_data['datacenters'][dc]))

    global_data['tokens'] = tokens

def two_closest_tokens(this_dc, this_token):
    """Returns the two closests tokens to this token within the entire cluster."""

    tokens = get_offset_tokens()
    lower_bound = 0
    upper_bound = global_data['MAXRANGE']

    for that_dc in tokens:
        if this_dc == that_dc:
            # Don't take the current datacenter's nodes into consideration
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
    """Calculates what the tokens are with their calculated offsets."""

    offset_tokens = copy.deepcopy(global_data['tokens'])
    for dc in offset_tokens:
        if dc == 0:
            # Never offset the first datacenter
            continue

        # Apply all offsets
        for node in offset_tokens[dc]:
            offset = global_data['offsets'][dc] if dc in global_data['offsets'] else 0
            offset_tokens[dc][node] = (offset_tokens[dc][node] + offset) % global_data['MAXRANGE']
    return offset_tokens

def calculate_offsets():
    """Find what the offsets should be for each datacenter."""

    exit_loop = False
    while not exit_loop:
        exit_loop = True

        tokens = get_offset_tokens()
        for this_dc in range(len(tokens)):
            if this_dc == 0:
                # Never offset the first datacenter
                continue

            tokens = get_offset_tokens()
            global_data['offsets'][this_dc] = global_data['offsets'][this_dc] if this_dc in global_data['offsets'] else 0
            previous_offset = global_data['offsets'][this_dc]
            running_offset = []

            # Get all the offsets, per token, that place each token in the ideal spot
            # away from all other tokens in the cluster
            for this_node in range(len(tokens[this_dc])):
                this_token = tokens[this_dc][this_node]
                lower_bound, upper_bound = two_closest_tokens(this_dc, this_token)
                perfect_spot = (upper_bound - lower_bound) / 2 + lower_bound
                this_offset = perfect_spot - this_token
                running_offset.append(this_offset)

            # Set this datacenters offset to be an average of all the running offsets
            if len(running_offset):
                global_data['offsets'][this_dc] += sum(running_offset) / len(running_offset)

            # Vote on exiting the loop if this datacenter did not change it's offset
            if global_data['offsets'][this_dc] - previous_offset > 0:
                exit_loop = False

# ===========================
# Main Starters

def print_tokens(tokens=False):
    if not tokens:
        tokens = get_offset_tokens()
    # print 'Offsets: ', global_data['offsets']
    print json.dumps(tokens, sort_keys=True, indent=4)

    if 'test' in global_data:
        calc_tests(tokens)

def run(datacenters):
    global_data['offsets'] = {}

    # Calculate the amount of datacenters in the beginning
    # of the list that have no nodes
    # Because the first DC remains stable
    leading_blank_centers = 0
    for datacenter in datacenters:
        if not datacenter:
            leading_blank_centers += 1
        else:
            break
    datacenters = datacenters[leading_blank_centers:]

    global_data['datacenters'] = datacenters
    calculate_tokens()
    calculate_offsets()
    returning_tokens = get_offset_tokens()

    # Add the preceding blank datacenters back in
    if leading_blank_centers:
        translated_tokens = {}
        for i in range(leading_blank_centers):
            translated_tokens[i] = {}
        i += 1
        for j in range(len(returning_tokens.keys())):
            translated_tokens[i] = returning_tokens[j]
            i += 1
        returning_tokens = translated_tokens

    # print returning_tokens
    return returning_tokens

# ===========================

# ===========================
# Tests

def calc_tests(tokens):
    import math
    these_calcs = {}

    for this_dc in range(len(tokens)):
        these_calcs[this_dc] = []
        for node in range(len(tokens[this_dc])):
            degrees = ((tokens[this_dc][node]) * 360 / global_data['MAXRANGE']) + 180
            radians = degrees * math.pi / 180

            center = global_data['graph_size'];
            x2 = center + global_data['length_of_line'] * math.sin(radians);
            y2 = center + global_data['length_of_line'] * math.cos(radians);
            these_calcs[this_dc].append((x2, y2))

    global_data['coordinates'].append(these_calcs)

def write_html():
    html = """<!DOCTYPE html>
<html>
<body>

%s

</body>
</html>

"""
    default_chart = """
    <canvas id="{0}" width="{2}" height="{2}" style="border:1px solid #c3c3c3;">
        Your browser does not support the canvas element.
    </canvas>
    <script type="text/javascript">
        var c=document.getElementById("{0}");
        var ctx=c.getContext("2d");\n%s
    </script>
    """
    default_chart_piece = """
        ctx.beginPath();
        ctx.strokeStyle = "%s";
        ctx.moveTo({1},{1});
        ctx.lineTo(%s,%s);
        ctx.stroke();
        ctx.closePath();
    """
    all_charts = ''
    for chart_set in range(len(global_data['coordinates'])):
        chart_index = chart_set
        chart_set = global_data['coordinates'][chart_set]
        chart_piece = ''
        for dc in range(len(chart_set)):
            for coordinates in chart_set[dc]:
                chart_piece += default_chart_piece % (global_data['colors'][dc], coordinates[0], coordinates[1])
        this_chart = default_chart % chart_piece
        all_charts += this_chart.format(chart_index, global_data['graph_size'], global_data['graph_size'] * 2)
    with open('tokentool.html', 'w') as f:
        f.write(html % all_charts)

def run_tests():
    global_data['test'] = True
    global_data['coordinates'] = []
    global_data['graph_size'] = 100
    global_data['length_of_line'] = 80
    global_data['colors'] = ['#000', '#00F', '#0F0', '#F00', '#0FF', '#FF0', '#F0F']
    global_data['MAXRANGE'] = 1000

    tests = [
        [1],
        [1, 1],
        [2, 2],
        [1, 2, 2],
        [2, 2, 2],
        [2, 0, 0],
        [0, 2, 0],
        [0, 0, 2],
        [2, 2, 0],
        [2, 0, 2],
        [0, 2, 2],
        [0, 0, 1, 1, 0, 1, 1],
        [6],
        [3, 3, 3],
        [9],
        [1,1,1,1],
        [4],
        [3,3,6,4,2]
    ]
    for test in tests:
        print_tokens(run(test))
    write_html()

# ===========================

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            run_tests()
            sys.exit(0)
        datacenters = sys.argv[1:]
    else:
        print "Usage: ./tokentoolv2.py <nodes_in_dc> [<nodes_in_dc>]..."
        sys.exit(0)
    run(datacenters)
    print_tokens()
