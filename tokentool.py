#! /usr/bin/python

import sys, random, time

MAXRANGE = (2**127)
DEBUG = False

# MAXRANGE = 100
DEBUG = False

originalTokens = {}
dcOffsets = {}

zoom = 2

def readInt(number, exitOnFail=False):
    returnVal = None
    try:
        returnVal = int(number)
    except:
        print "Please input a valid number."
        if exitOnFail:
            sys.exit(1)
    return returnVal

def splitRing(dc, numOfNodes):
    global originalTokens
    originalTokens[dc] = {}
    for i in range(0, numOfNodes):
        token = (i * MAXRANGE / numOfNodes) % MAXRANGE
        originalTokens[dc][i] = token

def findClosestMinAndMax(thisToken, thisRange):
    # Double the range for wrap around tokens
    doubleRange = [token + MAXRANGE for token in thisRange]
    thisRange = thisRange + doubleRange

    minimum = 0
    maximum = 0
    for token in thisRange:
        if token < thisToken:
            minimum = token
        if token >= thisToken:
            maximum = token
            break
    if not maximum:
        maximum = MAXRANGE
    return [minimum, thisToken, maximum]


def parseOptions():
    global originalTokens, dcOffsets

    # Parse Input
    if (len(sys.argv) == 1):
        print "Command line usage:"
        print "    tools/tokentool <# of nodes in DC1> [<# of nodes in DC2> <# of nodes in DC3> ...]"
        print
        sys.exit(0)
    elif (len(sys.argv) == 4):
        print "Sorry, more than 2 DC's are not yet supported."
        print
        sys.exit(0)
    else:
        # Gather then number of datacenters
        datacenters = readInt(len(sys.argv) - 1)

        # Gather the number of nodes in each datacenter
        sizeSet = []
        for i in range(0, datacenters):
            sizeSet.append(readInt(sys.argv[i + 1], True))
    
    return sizeSet

def initialRingSplit(sizeSet):

    # Calculate the inital tokens for each datacenter
    for i, node in enumerate(sizeSet):
        splitRing(i, node)
    
    # Find the initial DC offsets based on the first node soley
    dcs = originalTokens.keys()
    dcs.pop(0)
    dcOffsets[0] = 0
    for dc in dcs:
        if len(originalTokens[dc - 1]) > 1:
            dcOffsets[dc] = ((originalTokens[dc - 1][1] + dcOffsets[dc - 1]) - (originalTokens[dc - 1][0] + dcOffsets[dc - 1])) / 2
        else:
            dcOffsets[dc] = MAXRANGE / 2

def noDuplicateTokens(offsetdc=-1, offset=0):
    allkeys = []
    for dc in originalTokens.keys():
        for node in originalTokens[dc].keys():
            if dc == offsetdc:
                allkeys.append(originalTokens[dc][node] + offset)
            else:
                allkeys.append(originalTokens[dc][node])
    if len(allkeys) == len(set(allkeys)):
        return True
    else:
        return False


def sweepAndFind(dc, otherdc, iteration):
    global zoom, dcOffsets
    theseTokens = originalTokens[dc].values()
    otherTokens = originalTokens[otherdc].values()
    
    fuzzyRange = MAXRANGE / max(len(theseTokens), len(otherTokens))
    zoom *= 2
    steps = fuzzyRange / zoom

    if steps < 1:
        return True

    if DEBUG: 
        print "fuzzyRange", fuzzyRange
        print "zoom", zoom
        print "steps", steps
        print
    
    # Starting from the current spot, 
    # try to gain focus by spinning the ring
    # by the current fuzzy interval
    currentStep = -(steps * 2)
    closestToFocus = MAXRANGE
    frozenDCOffset = dcOffsets[dc]

    if not iteration:
        searchRange = fuzzyRange / (2 ** iteration)
    else:
        searchRange = steps * 2

    while currentStep <= searchRange:

        currentFocus = 0
        for thisToken in theseTokens:
            if False:
                print "thisToken", thisToken
                print "currentStep", currentStep
                print "frozenDCOffset", frozenDCOffset
            thisToken = (thisToken + currentStep + frozenDCOffset) % (2 * MAXRANGE)
            if False:
                print "thisToken", thisToken

            minThisMax = findClosestMinAndMax(thisToken, otherTokens)
            minimum = minThisMax[0]
            maximum = minThisMax[2]
            
            if minimum < maximum:
                thisTokenOffset = (maximum - minimum) / 2 + minimum - thisToken
            else:
                thisTokenOffset = (maximum + MAXRANGE - minimum) / 2 + minimum - thisToken
            if DEBUG: print minThisMax, thisTokenOffset
            
            currentFocus += thisTokenOffset
        
        if abs(currentFocus) < closestToFocus:
            if DEBUG:
                print "dcOffsets[dc]", dcOffsets[dc]
                print "currentStep", currentStep
            
            if noDuplicateTokens(dc, currentStep + frozenDCOffset):
                dcOffsets[dc] = currentStep + frozenDCOffset
                closestToFocus = abs(currentFocus)

        currentStep += steps

        if DEBUG: 
            print "currentFocus", currentFocus
            print "closestToFocus", closestToFocus
            print
    if DEBUG: 
        print "closestToFocus", closestToFocus

def focus():
    global originalTokens, dcOffsets, zoom
    iteration = 0
    doneZooming = False
    if len(originalTokens) == 1:
        doneZooming = True
    while not doneZooming:

        # TODO: Confirm no token conflicts

        # Loop over all dcs
        dcs = originalTokens.keys()
        dcs.reverse()
        for dc in dcs:                
            
            # Allow the first dc to stay in it's initial spot
            if dc == 0:
                continue

            for otherdc in dcs:

                # Don't compare the dc to itself
                if otherdc == dc:
                    continue
                
                doneZooming = sweepAndFind(dc, otherdc, iteration)

        iteration += 1

        if DEBUG: 
            time.sleep(1)
            print "dcOffsets", dcOffsets
            print '-------'

def calculateTokens():
    for dc in originalTokens.keys():
        sortedTokens = []
        for node in originalTokens[dc].keys():
            sortedTokens.append((originalTokens[dc][node] + dcOffsets[dc]) % MAXRANGE)

        sortedTokens.sort()

        for node in originalTokens[dc].keys():
            originalTokens[dc][node] = sortedTokens[node]
    return originalTokens

def printResults():
    # Calculate the shifted tokens
    calculateTokens()

    # Print
    for dc in originalTokens.keys():
        print "DC%d:" % (dc + 1)
        for i, token in enumerate(originalTokens[dc].values()):
            print "Node %d: %d" % (i, token)
        print

def run():
    global originalTokens, dcOffsets

    initialRingSplit(parseOptions())
    focus()
    printResults()

if __name__ == '__main__':
    run()
