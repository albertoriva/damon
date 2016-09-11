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

# Top-level functions

def act(filename, arguments, zipfile=False, debug=False):
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
    ACT.Arguments = arguments
    good = True

    if debug:
        execfile(filename, globals(), locals())
        ACT._cleanup()
    else:
        try:
            execfile(filename, globals(), locals())
        except Exception as e:
            print "*** Script terminated with error: {}".format(e)
            good = False
        finally:
            ACT._cleanup()

    # We're back to top-level directory, let's see
    # if user wants to zip the package
    if good and zipfile:
        if zipfile == True:
            zipfile = ACT.Name + ".zip"
        exclFile = ACT.dir + "/" + exFile
        inclFile = ACT.dir + "/" + inFile
        zipcmd = ["-x", "*.IN.*", "-r", zipfile, ACT.dir]
        if os.path.isfile(inclFile):
            zipcmd = ["-i@" + inclFile] + zipcmd
        elif os.path.isfile(exclFile):
            zipcmd = ["-x@" + exclFile, "-x", exclFile] + zipcmd
        zipcmd = ["zip"] + zipcmd
        #print zipcmd
        print "Creating ZIP file {}...".format(zipfile)
        subprocess.call(zipcmd)
        print "ZIP file {} created.".format(zipfile)

# Main

class Args():
    script = None
    arguments = []
    zipfile = False
    debug = False

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

def usage():
    print """
usage: actor.py [-d] [-z zipFile] [-Z] scriptName [arguments...]

  Executes script "scriptName" with the specified arguments. 
  If "-z"  is specified, the output directory will be compressed
  to a zip file with the specified name. If -Z is specified, 
  the output directory will be compressed to a file having
  as its name the script name followed by .zip. "-d" enables
  debugging, ie the script will stop with a python error message
  in case of errors, instead of trapping and reporting errors.

Copyright (c) 2015, A. Riva (ariva@ufl.edu)
University of Florida
"""

if __name__ == "__main__":
    
    A = Args()
    if A.parse(sys.argv[1:]):
        act(A.script, A.arguments, zipfile=A.zipfile, debug=A.debug)
    else:
        usage()

