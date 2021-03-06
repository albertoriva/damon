# An actor that includes a SampleCollection, to process
# multiple samples possibly having multiple replicates each.

import os.path
from Actor import Actor
from Logger import Logger

# Main class

class MultiSampleActor(Actor):
    sc = None                   # SampleCollection
    libpath = "/apps/dibig_tools/1.0/lib/" # *** This should be configurable!

    def __init__(self):
        self._addFile(self.libpath + "js/jquery.tablescroll.js")
        self._addFile(self.libpath + "css/jquery.tablescroll.css")

    def initFiles(self):
        self.log.setLogfile(self.getConf("logfile"))
        self.log.setEcho('stdout')
        self.log.logStart(self.title)

        ## Ensure we don't have old files lying around
        self.shell("rm -f *.done tmp-* .files")

        ## Initialize .files
        self._addToInclude("*.html", "*.png", "*.pdf", "*.xlsx", "*.csv", "*.css", "*.js", "*.bed", "*.vcf", "*.bedGraph", "*.conf")

    def cleanup(self):
        self.log.logEnd()
        self.log.close()

    def addToZipFile(self, path): # *** This is the same as _addToInclude
        with open(".files", "a") as out:
            out.write(path + "\n")

