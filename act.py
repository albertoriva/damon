#!/usr/bin/env python

###################################################
#
# (c) 2016, Alberto Riva, ariva@ufl.edu
# DiBiG, ICBR Bioinformatics, University of Florida
#
# See the LICENSE file for license information.
###################################################

import sys
import os.path
import subprocess
import traceback

# Utils

def getScriptClass(filename):
    with open(filename, "r") as f:
        line = f.readline().strip("\r\n\t ")
    if line[0:2] == "# ":
        return line[2:]
    else:
        return "Actor"

def show(msg, *args):
    sys.stdout.write(msg.format(*args))

# Main

class Args():
    script = None
    arguments = []
    zipfile = False
    debug = False
    ask = True
    dry = False

    def parse(self, args):
        next = ""
        for a in args:
            if next == "-z":
                self.zipfile = a
                next = ""
            elif a == "-z":
                next = a
            elif a == "-Z":
                self.zipfile = True
            elif a == "-d":
                self.debug = True
            elif a == "-y":
                self.ask = False
            elif a == "-r":
                self.dry = True
            elif self.script == None:
                self.script = a
            else:
                self.arguments.append(a)
        if self.script == None:
            return False
        if not os.path.isfile(self.script):
            show("Script file `{}' not found.", self.script)
            return False
        return True

# Top-level functions

    def act(self):
        filename = self.script
        className = getScriptClass(filename)
        # print "Importing {}".format(className)
        module = __import__(className, globals(), locals())
        # print "Imported from {}".format(module.__file__)
        actor = module
        classObj = getattr(module, className)
        exFile = ".exclude" # *** hack, this should go away
        inFile = ".files"
        ACT = classObj()
        ACT.source = os.path.abspath(filename)
        ACT.Arguments = self.arguments
        ACT.ask = self.ask
        ACT.dry = self.dry
        # print ACT.ask
        good = True

        if self.debug:
            try:
                execfile(filename, globals(), locals())
                ACT._cleanup()
            except Exception as e:
                bt = traceback.format_exc()
                ACT.log.log(bt)
                good = False
                raise e
        else:
            try:
                execfile(filename, globals(), locals())
            except Exception as e:
                msg = "*** Script terminated with the following error:\n*** {}\n".format(e)
                show(msg)
                ACT.log.log(msg)
                good = False
            finally:
                ACT._cleanup()

        if not good:
            sys.exit(2)
        # We're back to top-level directory, let's see
        # if user wants to zip the package
        if ACT.complete and self.zipfile:
            if self.zipfile == True:
                self.zipfile = ACT.Name + ".zip"
            exclFile = ACT.dir + "/" + exFile
            inclFile = ACT.dir + "/" + inFile
            zipcmd = ["-x", "*.IN.*", "-r", self.zipfile, ACT.dir]
            if os.path.isfile(inclFile):
                zipcmd = ["-i@" + inclFile] + zipcmd
            if os.path.isfile(exclFile):
                zipcmd = ["-x@" + exclFile, "-x", exclFile] + zipcmd
            zipcmd = ["zip"] + zipcmd
            #print zipcmd
            show("Creating ZIP file {}...\n", self.zipfile)
            subprocess.call(zipcmd)
            show("ZIP file {} created.\n", self.zipfile)

def usage():
    show("""
Usage: {} [-d] [-y] [-z zipFile] [-Z] scriptName [arguments...]

Executes Actor script "scriptName" with the specified arguments. Options:

  -z zipFile | After execution, compress the "useful" files in the output
               directory to a ZIP file with the specified name. Useful
               files are those matching patterns listed in the .files file.
  -Z         | Like -z, but uses script name as basename of the zip file.
  -d         | Debug mode: script will print backtrace in case of errors
               (by default all errors are caught and only the error message 
               is printed). Also disables -z.
  -y         | Answer "yes" to all questions (unattended mode).
  -r         | Dry mode: set all steps to dry run. A.k.a. "report-only" mode.

The script returns error code 0 if everything was OK; 1 if this help message
was printed, and 2 in case of any error. 

Copyright (c) 2015-2018, A. Riva (ariva@ufl.edu)
University of Florida
""", os.path.split(sys.argv[0])[1])

if __name__ == "__main__":
    
    A = Args()
    if A.parse(sys.argv[1:]):
        A.act()
        sys.exit(0)
    else:
        usage()
        sys.exit(1)
