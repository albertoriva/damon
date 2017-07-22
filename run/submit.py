#!/usr/bin/env python

# (c) 2013, A. Riva, University of Florida
# $Id: submit.py,v 1.6 2013/12/07 03:54:43 alb Exp $

import os, os.path
import sys
import fcntl
import string
import getpass
from datetime import datetime

trueArgs = []
afterArgs = []
doneFile = False
confFile = ".qsubrc"

scriptLibrary = os.path.dirname(__file__) + "/../lib/scripts/"
logFile       = os.path.dirname(__file__) + "/../lib/submit.log"

def writeLogEntry(script):
    now = datetime.now()
    with open(logFile, "a") as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:
            f.write(now.isoformat('\t') + '\t' + getpass.getuser() + '\t' + script + '\n')
        finally:
            fcntl.flock(f,fcntl.LOCK_UN)

def parseArgs():
    nextIsAfter = False
    nextIsDone = False
    nextIsConf = False
    global doneFile

    for a in sys.argv[1:]:
        if nextIsAfter:
            afterArgs.append(a)
            nextIsAfter = False
        elif nextIsDone:
            doneFile = a
            nextIsDone = False
        elif nextIsConf:
            confFile = a
            nextIsConf = False
        elif a == "-after":
            nextIsAfter = True
        elif a == "-done":
            nextIsDone = True
        elif a == "-conf":
            nextIsConf = True
        else:
            trueArgs.append(a)

def usage():
    print """
usage: submit.py [-after jobid] [-done name] scriptName [arguments...]

  Submits script "scriptName" using qsub, passing the values
  of "arguments" to the script as $arg1, $arg2, $arg3, etc. 

  If "-after" is specified, the script will run after the job 
  indicated by "jobid" has terminated successfully. Multiple 
  "-after" arguments may be specified.

  If "-done" is specified, the script will create a file called "name"
  when it terminates. This can be used to detect that execution of the
  script has finished.

  Additional qsub options can be read from a file (by default, \".qsubrc\"
  in your home directory). You can change the name of this file with the
  \"-conf\" argument. The path is relative to your home directory, so for
  example \"-conf confs/largejob.txt\" will read configuration options from
  the largejob.txt file in the confs/ subdirectory of your home. Set this
  argument to a non-existent file to disable option loading.

  This command returns the id of the submitted job, which is suitable
  as the -after argument for a subsequent job. For example:

  STEP1=`submit.py step1.sh`
  STEP2=`submit.py -after $STEP1 step2.sh`

Copyright (c) 2014, Alberto Riva (ariva@ufl.edu), University of Florida
"""

def set_vars(values):
    idx = 1
    names = ["args"]
    os.putenv("args", " ".join(values))

    for v in values:
        name = "arg" + str(idx)
        os.putenv(name, v)
        names.append(name)
        idx = idx + 1

    return names

def readOptions(optfile):
    optpath = os.path.expanduser("~/" + optfile)
    if os.path.isfile(optpath):
        with open(optpath, 'r') as f:
            opts = f.read()
        opts = opts.replace('\n', ' ')
        return opts
    else:
        return ""

def decorateScript(infile, outfile):
    inHeader = True
    out = open(outfile, "w")
    inf = open(infile, "r")
    for row in inf:
        if inHeader:
            srow = row.strip()
            if len(srow) == 0:
                pass
            elif srow.find("#!") == 0:
                pass
            elif srow.find("#PBS") == 0:
                pass
            else:
                inHeader = False
                out.write("\necho Commandline: " + string.join(sys.argv[1:]) + "\n")
                out.write("echo Started: `date`\n\n")
        out.write(row)
    out.write("echo Terminated: `date`\n")
    if doneFile:
        p = doneFile.find("@")
        if p >= 0:
            newDone = doneFile[0:p] + "${PBS_JOBID}" + doneFile[p+1:]
            out.write("touch " + newDone + "\n");
        else:
            out.write("/apps/dibig_tools/1.0/bin/touch-done " + doneFile + "\n")
    inf.close()
    out.close()

# Main
sys.stderr.write("Script library: " + scriptLibrary + "\n")

if __name__ == "__main__":

    if len(sys.argv) < 2:
        usage()
        exit(1)

    parseArgs()
    scriptName = trueArgs[0]
    scriptPath = scriptLibrary + scriptName
    # *** todo: check that the script exists.
    newScriptName = scriptName + ".IN"
    decorateScript(scriptPath, newScriptName)
    varList = set_vars(trueArgs[1:])
    varNames = string.join(varList, ",")
    opts = readOptions(confFile)

    cmdline = "qsub -d `pwd` " + opts

    if varNames != '':
        cmdline = cmdline + "-v " + varNames

    if len(afterArgs) > 0:
        afterArgs = [ "afterok:" + a for a in afterArgs]
        afterCmd = " -W depend=" + string.join(afterArgs, ",")
        cmdline = cmdline + afterCmd

    cmdline = cmdline + " " + newScriptName
    sys.stderr.write("Executing: " + cmdline + "\n")
    os.system(cmdline)
    writeLogEntry(scriptName)
