# (c) 2015, A. Riva, DiBiG, ICBR Bioinformatics
# University of Florida

import sys
import importlib
from inspect import getmro

class Director():
    """This class coordinates the execution of the pipeline."""

    actor = None
    steplist = []               # Names of steps
    steps = []                  # Actual step objects
    registry = {}
    stopAt = ""

    def __init__(self, actor, library="Library"):
        self.actor = actor
        self.steplist = []
        self.steps = []

        if type(library).__name__ == 'str':
            library = [library]
        for libname in library:
            lib = importlib.import_module(libname)
            libdict = self.makeLibraryDict(lib)
            sys.stdout.write("{} Lines loaded from library {}\n".format(len(libdict), libname))
            #self.registry.update(lib.REGISTRY)
            self.registry.update(libdict)

    def makeLibraryDict(self, lib):
        """Collect all classes that are a subclass of Line in `lib'. Returns
a dictionary with the tag attribute of each class as the key."""
        libdict = {}
        lc = lib.Line
        for cname in dir(lib):
            x = getattr(lib, cname)
            if x == lc:
                continue
            if type(x).__name__ == 'classobj' and lc in getmro(x):
                    #print "{} {}".format(x, x.name)
                libdict[x.tag] = x
        return libdict

    def setSteps(self, steplist):
        """Set the list of steps to be performed by this director to `steplist'. Steplist
can be either a list of strings or a string containing comma-separated step names (e.g.
"step1, step2, step3". Use the step() method to know if a step should be executed."""
        if type(steplist).__name__ == 'str':
            steplist = [ i.strip(" ") for i in steplist.split(",") ]
        self.steplist = steplist
        self.notifiedSteps = []

    def stepPresent(self, step):
        return (step in self.steplist) or ("-"+step in self.steplist) or ("no"+step in self.steplist)

    def stepDry(self, step):
        return ("-"+step in self.steplist) or ("no"+step in self.steplist)

    # def step(self, wanted):
    #     if wanted in self.steplist:
    #         if not wanted in self.notifiedSteps: # should we notify?
    #             print "Performing step `{}'.".format(wanted)
    #             self.notifiedSteps.append(wanted)
    #         return True
    #     else:
    #         if not wanted in self.notifiedSteps:
    #             print "Skipping step `{}'.".format(wanted)
    #             self.notifiedSteps.append(wanted)
    #         return False

    def step(self, key, **properties):
        if self.stepPresent(key):
            self.add(key, dry=self.stepDry(key), **properties)
        else:
            print "[Unused step: " + key + "]"

    def add(self, key, **properties):
        line = None
        dkey = key
        p = key.find(".")
        if p > -1:
            dkey = key[:p]

        if dkey in self.registry:
            cls = self.registry[dkey]
            line = cls(self.actor, key=key, properties=properties)
            self.steps.append(line)
        else:
            sys.stderr.write("Warning: no Line with key `{}'.\n".format(dkey))
        return line

    def dryRun(self):
        """Set all steps in this pipeline to dry."""
        for s in self.steps:
            s.dry = True

    def startAt(self, startkey):
        """Set all steps in this pipeline to dry, until `startkey' is reached. All steps
from `startkey' onwards will be set to not-dry."""
        if startkey:
            print "Starting at {}".format(startkey)
            dry = True
            for s in self.steps:
                if s.key == startkey:
                    dry = False
                s.dry = dry

    def stopAt(self, stopkey):
        """Stop the pipeline after executing step `stopkey'."""
        self.stopAt = stopkey

    def showSteps(self):
        print "Ready to run the following steps:"
        for s in self.steps:
            print "{} {}".format("-" if s.dry else "+", s.name)
        if self.actor.ask:
            print "Press Enter to start execution."
            try:
                raw_input()
                return True
            except KeyboardInterrupt:
                print "\nExecution cancelled."
                return False
        else:
            return True

    def run(self, ACT, title):
        """Top-level method to run the pipeline."""

        self.startAt(ACT.getConf("startAt"))
        self.stopAt(ACT.getConf("stopAt"))

        if ACT.dry:
            self.dryRun()

        if self.showSteps():
            ACT.script(ACT.title, title)
            if ACT.begin(timestamp=False):
                ACT.initFiles()
                self.RunScript()
                ACT.cleanup()
                return True
        return False

    def PerformAll(self, method, immediatestop=False):
        good = True
        doit = True
        for l in self.steps:
            if doit:
                self.actor.log.log("Director: performing {} on `{}'.", method, l.name)
                m = getattr(l, method)
                f = m()
                if not f:
                    self.actor.log.log("Error in {}: {}: {}".format(method, l.name, l.status))
                    if immediatestop:
                        return False
                    else:
                        good = False
                if l.key == self.stopAt:
                    self.actor.log.log("Stop requested at step {}.".format(l.key))
                    doit = False
        return good

    def VerifyAll(self):
        return self.PerformAll('Verify')

    def PreExecuteAll(self):
        return self.PerformAll('PreExecute')

    def ExecuteAll(self):
        return self.PerformAll('Execute', immediatestop=True)

    def PostExecuteAll(self):
        return self.PerformAll('PostExecute')

    def ReportAll(self):
        return self.PerformAll('Report')

    def RunScript(self):
        if not self.VerifyAll():
            return False
        if not self.PreExecuteAll():
            return False
        if not self.ExecuteAll():
            return False
        if not self.PostExecuteAll():
            return False
        if not self.ReportAll():
            return False
        self.actor.complete = True
