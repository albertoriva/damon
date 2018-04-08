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

# Utils

def getScriptClass(filename):
    with open(filename, "r") as f:
        line = f.readline().strip("\r\n\t ")
    if line[0:2] == "# ":
        return line[2:]
    else:
        return "Actor"

# Main

class Args():
    script = None
    arguments = []
    zipfile = False
    debug = False
    ask = True

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
            elif self.script == None:
                self.script = a
            else:
                self.arguments.append(a)
        if self.script == None:
            return False
        if not os.path.isfile(self.script):
            print "Script file `{}' not found.".format(self.script)
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
        # print ACT.ask
        good = True

        if self.debug:
            execfile(filename, globals(), locals())
            ACT._cleanup()
        else:
            try:
                execfile(filename, globals(), locals())
            except Exception as e:
                msg = "*** Script terminated with error: {}".format(e)
                ACT.log.log(msg)
                good = False
            finally:
                ACT._cleanup()

        # We're back to top-level directory, let's see
        # if user wants to zip the package
        if ACT.complete and good and self.zipfile:
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
            print zipcmd
            print "Creating ZIP file {}...".format(self.zipfile)
            subprocess.call(zipcmd)
            print "ZIP file {} created.".format(self.zipfile)

def usage():
    print """
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

Copyright (c) 2015-2017, A. Riva (ariva@ufl.edu)
University of Florida
""".format(os.path.split(sys.argv[0])[1])

if __name__ == "__main__":
    
    A = Args()
    if A.parse(sys.argv[1:]):
        A.act()
    else:
        usage()

