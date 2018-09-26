###################################################
#
# (c) 2016, Alberto Riva, ariva@ufl.edu
# DiBiG, ICBR Bioinformatics, University of Florida
#
# See the LICENSE file for license information.
###################################################

import os
import os.path
import sys
import csv
import glob
import time
import shutil
import subprocess
from datetime import date, datetime
from tempfile import mkstemp

import ConfigParser
import imageslider
from Logger import Logger

# Globals

actCopyright = "&copy; " + str(date.today().year) + ", <A href='mailto:ariva@ufl.edu'>A. Riva</A>, University of Florida."
submitCmd = "submit"

# Internal utilities (not really meant for users)

# Helper classes for the wait() command
# Each waiter has a success() method that returns True
# when the event it's waiting for happens

class Waiter():
    wanted = 0
    filename = ""

    def __init__(self, filename):
        self.filename = filename

    def str(self):
        return "<File {}>".format(self.filename)

    def success(self):
        """A base Waiter is successful when its target file exists."""
        return os.path.exists(self.filename)

    def delete(self):
        os.remove(self.filename)

class CounterWaiter(Waiter):

    def __init__(self, filename, wanted):
        self.filename = filename
        self.wanted = wanted

    def str(self):
        return "<Value {} in {}>".format(self.wanted, self.filename)

    def success(self):
        """A CounterWaiter is successful when the target file exists and 
contains a value greater than or equal to `wanted'."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    current = int(f.readline())
                return (current >= self.wanted)
            except:
                return False
        else:
            return False

class GlobWaiter(CounterWaiter):
    found = 0

    def __init__(self, filename, wanted):
        self.filename = filename
        self.wanted = wanted
        
    def str(self):
        return "<{}/{} files matching {}>".format(self.wanted-self.found, self.wanted, self.filename)

    def success(self):
        """A GlobWaiter is successful if the number of existing files matching
the pattern in `filename' is greater than or equal to `wanted'."""
        self.found = len(glob.glob(self.filename))
        return (self.found >= self.wanted)
        
    def delete(self):
        for f in glob.glob(self.filename):
            os.remove(f)

class ActorError(Exception):
    step = False

class FileError(ActorError):
    filename = ""
    
    def __init__(self, filename, step=False):
        self.filename = filename
        self.step = step

    def __str__(self):
        if self.step:
            return "Error in step {}: file {} does not exist or is not readable.".format(self.step, self.filename)
        else:
            return "Error file {} does not exist or is not readable.".format(self.filename)

class FileTooSmall(FileError):
    filename = ""
    megs = 1

    def __init__(self, filename, megs, step=False):
        self.filename = filename
        self.megs = megs
        self.step = step

    def __str__(self):
        msg = "Error: something went wrong"
        if self.step:
            msg = msg + " in step " + self.step
        return msg + " - file `{}' is smaller than {} Mb.".format(self.filename, self.megs)

class FileTooShort(FileError):
    filename = ""
    lines = 1

    def __init__(self, filename, lines, step=False):
        self.filename = filename
        self.lines = lines
        self.step = step

    def __str__(self):
        msg = "Error: something went wrong"
        if self.step:
            msg = msg + " in step " + self.step
        return msg + " - file `{}' is shorter than {} lines.".format(self.filename, self.lines)

# Main class

class Actor():
    Name = "run"
    title = "Script"
    Project = "(no name)"
    Copyright = actCopyright
    Fields = {}
    Arguments = []
    Include = []                 # List of additional files to be copied in run directory
    Conf = None                  # ConfigParser object
    Steps = []                   # Steps the user wants to run
    Prefix = None                # Prefix for submit jobs
    log = Logger(None)           # To avoid errors in scripts that don't explicitly create one

    # Runtime
    ask = True                   # If False, run in unattendend mode
    source = ""                  # Name of file containing script
    configFile = None            # Name of configuration file
    includeFile = ".files"       # Include list for Zip file
    excludeFile = ".exclude"     # Exclude list for Zip file
    tempfiles = []               # List of temporary files
    dir = ""                     # Output directory
    out = False                  # Output stream
    toc = False                  # Stream for table of contents
    sceneIdx = 0                 # Number of current scene
    inScene = False              # Are we inside a scene?
    previousDir = ""             # Directory before starting execution
    notifiedSteps = []
    methods = []                 # List of strings for methods section
    references = []              # List of references for methods section
    nreferences = 0              # Number of references
    complete = False             # Set to true for successful completion
    error = None                 # Set to an error message in case of errors

    # Internal methods (not meant to be called by user)

    def __init__(self):
        self.Fields = {}
        self.Arguments = []
        self.Include = []
        self.tempfiles = []
        self.previousDir = ""

    def _cleanup(self):

        # Finish HTML file and close it
        if self.out and not self.out.closed:
            self.postamble(self.out)
            self.out.close()

        if self.toc and not self.toc.closed:
            self.toc.write("</TD></TR></OL>\n")
            self.toc.close()

        # Remove temporary files
        for fdata in self.tempfiles:
            os.remove(fdata[1])

        # Return to parent directory
        if self.previousDir != "":
            os.chdir(self.previousDir)
            self.message("Current directory now: {}", os.getcwd())

    def _addToExclude(self, filename):
        with open(self.excludeFile, "a") as out:
            out.write("{}/{}\n".format(self.Name, filename))
        return filename

    def _addToInclude(self, *filenames):
        with open(self.includeFile, "a") as out:
            for f in filenames:
                out.write("{}/{}\n".format(self.Name, f))
        return filenames

    def _addFile(self, filename):
        """Add `filename' to the list of files that get copied to the script directory "as is" (e.g.
stylesheets, logos)."""
        self.Include.append(filename)
        return filename

    def _subprocOutput(self, command):
        # Execute `command', return the command's output.
        # `command' can be a string or a list in which the first
        # element is the command name and remaining elements are arguments.
        # The end-of-line character at the end of the last line of output
        # is removed automatically.
        # NOTE: signals an error if the command returns a non-zero return code.
        return subprocess.check_output(command.split(" ")).rstrip("\n")

    def _decodeAlign(self, align, i):
        """Decodes the character at position `i' in an align string `align' into the corresponding CSS style (for tables). If `align' is None, assume L at each position."""
        al = {'L': "<TD class='{} aleft'>{}</TD>",
              'R': "<TD class='{} aright'>{}</TD>",
              'C': "<TD class='{} acenter'>{}</TD>",
              'H': "<TD class='{} aheader'>{}</TD>",
              'N': "<TD class='{} aright'>{:,}</TD>",
              'F': "<TD class='{} aright'>{:.3f}</TD>"}
        if align == None:
            return al['L']
        else:
            return al[align[i]]

# Utils
    def message(self, string, *args):
        # Write `string' to standard error. `args' are 
        # inserted into `string' with format.
        sys.stderr.write(string.format(*args))
        sys.stderr.write("\n")

    def messagelf(self, string, *args):
        """Like `message', but moves the cursor at the beginning of the line first, clears to end of line, and does not output a \n at the end."""
        sys.stderr.write(chr(13) + string.format(*args) + "\033[K")

    def fullname(self, pathname):
        # Returns the filename part of `pathname'
        # *** This is the same as os.path.basename()
        return os.path.split(pathname)[1]

    def fileLink(self, filename, label):
        if os.path.isfile(filename):
            return "<B>{}</B> <A href='{}' target='_blank'>{}</A>".format(label, filename, self.fullname(filename))
        else:
            return ""

    def fileDetails(self, pathname):
        # Returns a tuple containing file extension and size of the
        # file pointed to by `pathname'
        ext = os.path.splitext(pathname)[1]
        ext = ext[1:]
        return (ext, os.path.getsize(pathname))

    def printBytes(self, b):
        # Return a string containing the number b formatted as a number of 
        # bytes, or kilobytes, or megabytes, or gigabytes, as appropriate.
        if b < 1024:
            return "{} bytes".format(b)
        b = b / 1024.0
        if b < 1024:
            return "{:.2f} kB".format(b)
        b = b / 1024.0
        if b < 1024:
            return "{:.2f} MB".format(b)
        b = b / 1024.0
        return "{:.2f} GB".format(b)

    def timeStamp(self):
        dt = datetime.now()
        return "{}-{}-{}@{}:{:0>2}".format(dt.month, dt.day, dt.year, dt.hour, dt.minute)

    def dateAndTime(self):
        dt = datetime.now()
        return "{}/{}/{} {}:{:0>2}:{:0>2}".format(dt.month, dt.day, dt.year, dt.hour, dt.minute, dt.second)

### Support for files and pathnames

    def linkify(self, url, name=False, target=False):
        if not name:
            name = url
        if target:
            tg = " target='{}'".format(target)
        else:
            tg = ""
        return "<A href='{}'{}>{}</A>".format(url, tg, name)

    def fixPath(self, path):
        """Add ../ in front of `path' unless it is absolute."""
        if path[0] == "/":
            return path
        else:
            return "../" + path

    def checkPath(self, p, step=False):
        """Checks that the file indicated by pathname p exists and is readable.
Returns fixPath(p) if successful, signals an error otherwise."""
        if p == None:
            return p
        elif os.path.isfile(p) or os.path.islink(p):
            return self.fixPath(p)
        else:
            raise FileError(p)

    def checkFile(self, p, step=False):
        """Checks that the file indicated by pathname p exists and is readable.
Returns True if successful, signals an error otherwise."""
        if os.path.isfile(p):
            return True
        else:
            raise FileError(p, step)

    def fileLines(self, filename, skipchar=None):
        """Returns the number of lines in `filename' (as a string). If `skipchar' is specified,
only counts lines that do NOT start with that charachter."""
        if skipchar:
            r = self.shell("grep -v ^{} {} | wc -l -".format(skipchar, filename))
        else:
            r = self.shell("wc -l " + filename)
        p = r.find(" ")
        if p > 0:
            return r[:p]
        else:
            return None

    def checkFileSize(self, p, megs=1, step=False):
        """Checks that the file indicated by pathname `p' exists and is larger than `megs' 
megabytes (defaulting to 1). Returns True if successful, signals an error otherwise."""
        if not os.path.isfile(p):
            raise FileError(p, step)
        fs = os.path.getsize(p)
        if fs < megs * 1048576:
            raise FileTooSmall(p, megs, step)
        return True

    def checkFileLength(self, p, lines=1, skipchar=None, step=False):
        """Checks that the file indicated by pathname `p' exists and contains more than 
`lines' lines (defaulting to 1). Returns True if successful, signals an error otherwise."""
        if not os.path.isfile(p):
            raise FileError(p, step)
        if self.fileLines(p, skipchar=skipchar) >= lines:
            return True
        else:
            raise FileTooShort(p, lines, step)

# Support for configuration files

    def loadConfiguration(self, filename):
        """Load configuration file `filename'."""
        if os.path.isfile(filename):
            self.configFile = filename
            self.Conf = ConfigParser.ConfigParser()
            self.Conf.optionxform = str
            self.Conf.read(filename)

            if self.Conf.has_section("Include"):
                for (label, incfile) in self.Conf.items("Include"):
                    if os.path.isfile(incfile):
                        sys.stderr.write("  (including conf file {})\n".format(incfile))
                        self.Conf.read(incfile)

            # Set standard attributes
            self.title = self.getConf("title")
            self.project = self.getConf("project")
            self.prefix = self.getConf("label")

            return self.Conf
        else:
            print "Error: configuration file {} not found or not readable.".format(filename)
            exit(1)

    def getConf(self, entry, section="General", default=None):
        """Return the value for `entry' in `section', if present, or the
value of default (None if unspecified). `section' defaults to General."""
        try:
            if self.Conf.has_section(section):
                return self.Conf.get(section, entry)
            else:
                return default
        except ConfigParser.NoOptionError:
            return default
    
    def getConfInt(self, entry, section="General", default=None):
        try:
            return int(self.Conf.get(section, entry))
        except ConfigParser.NoOptionError:
            return default
        except ValueError:
            return default

    def getConfFloat(self, entry, section="General", default=None):
        try:
            return float(self.Conf.get(section, entry))
        except ConfigParser.NoOptionError:
            return default
        except ValueError:
            return default

    def getConfBoolean(self, entry, section="General", default=None):
        """Return the boolean value for `entry' in `section', if present, or the
value of default (None if unspecified). `section' defaults to General."""
        try:
            return self.Conf.getboolean(section, entry)
        except ConfigParser.NoOptionError:
            return default

    def getConfList(self, entry, section="General", default=[]):
        """Return the value for `entry' in `section' as a comma-delimited list.
`section' defaults to General."""
        try:
            a = self.Conf.get(section, entry)
            return [ w.strip(" ") for w in a.split(",") ]
        except ConfigParser.NoOptionError:
            return default

    def getConfAll(self, section):
        """Returns all (key, value) pairs for the options in `section'."""
        if self.Conf.has_section(section):
            return self.Conf.items(section)
        else:
            return []

# Support for enabling/disabling steps

    def setSteps(self, steplist):
        """Set the list of steps to be performed by this actor to `steplist'. Steplist
can be either a list of strings or a string containing comma-separated step names (e.g.
"step1, step2, step3". Use the step() method to know if a step should be executed."""
        if type(steplist).__name__ == 'str':
            steplist = [ i.strip(" ") for i in steplist.split(",") ]
        self.Steps = steplist
        self.notifiedSteps = []

    def stepPresent(self, step):
        return (step in self.Steps) or ("-"+step in self.Steps) or ("no"+step in self.Steps)

    def stepDry(self, step):
        return ("-"+step in self.Steps) or ("no"+step in self.Steps)

    def step(self, wanted):
        if wanted in self.Steps:
            if not wanted in self.notifiedSteps: # should we notify?
                print "Performing step `{}'.".format(wanted)
                self.notifiedSteps.append(wanted)
            return True
        else:
            if not wanted in self.notifiedSteps:
                print "Skipping step `{}'.".format(wanted)
                self.notifiedSteps.append(wanted)
            return False

    # Actor definitions (should normally NOT be overwritten)

    def name(self, name):
        """Declare the name of this script to be `name'. This value is used as the name of the directory created by the script."""
        self.Name = name

    def title(self, title):
        """Declare the title of this script to be `title'. The title is printed at the top of the HTML report."""
        self.title = title

    def project(self, project):
        """Declare the name of the project that this script belongs to. The project is printed in the header of the HTML report."""
        self.Project = project

    def script(self, name, title, project=None):
        """Declare the name, title, and project for this script."""
        self.Name = name
        self.title = title
        if project:
            self.project = project

    def info(self, namesVals):
        """Adds the key, value pairs in dictionary `namesVals' to the list of additional info fields for this script. Info fields are printed in the header of the HTML report."""
        self.Fields.update(namesVals)

    def field(self, namesVals):
        """Alias for info()."""
        self.info(namesVals)

    def fields(self, namesVals):
        """Alias for info()."""
        self.info(namesVals)

    def arguments(self, idx=False):
        """Returns the list of arguments passed to this script. If `idx' is specified, only returns the argument with that index."""
        if idx:
            return self.Arguments[idx]
        else:
            return self.Arguments

    def exclude(self, filename):
        """Add `filename' to the list of files excluded from the zip file created when the script ends."""
        return self._addToExclude(filename)

    def tempfile(self):
        """Create and open a temporary file in the current directory. Returns the open file handle. The file is automatically deleted when execution of the script terminates."""
        fdata = mkstemp(prefix='tmp', dir=".")
        f = os.fdopen(fdata[0], "w")
        self.tempfiles.append([fdata[0], fdata[1], f])
        return f

    def missingOrStale(self, filename, other=[], warn=False):
        """Returns true if `filename' is missing or (when `other' is specified) older than `other'.
`Other' can be a list of filenames, in which case all of them are tested."""
        if isinstance(other, type("str")):
            other = [other]
        if not os.path.isfile(filename):
            if warn:
                sys.stderr.write("File `{}' does not exist or is not readable.".format(filename))
            return True             # missing                                                                                                                            
        this = os.path.getmtime(filename)
        for o in other:
            if os.path.isfile(o):
                that = os.path.getmtime(o)
                if this < that:
                    if warn:
                        sys.stderr.write("File `{}' is older than file `{}'.".format(filename, o))
                    return True
        return False
    
    def mkdir(self, name):
        if not os.path.exists(name):
            os.makedirs(name)

    # The following few methods deal with waiting for things to happen...

    def _parseWait(self, w):
        if type(w).__name__ == 'str':
            return Waiter(w)
        else:
            filename = w[0]
            cnt = w[1]
            p = filename.find("@")
            if p >= 0:
                newFile = filename[0:p] + "*" + filename[p+1:]
                return GlobWaiter(newFile, cnt)
            else:
                return CounterWaiter(filename, cnt)

    def wait(self, wanted, delete=True):
        """Wait until all the files in the `wanted' list get created. Returns True when all specified files exist. This can be used to check for the completion of a background script. If `delete' is True, the files are deleted before returning."""

        # If a single filename was passed, turn it into a list
        if type(wanted).__name__ != 'list':
            wanted = [wanted]

        wanted = [ self._parseWait(w) for w in wanted ]
        nwanted = sum(w.wanted for w in wanted)
        wmsg   = ", ".join([ w.str() for w in wanted])
        self.messagelf("\nWaiting for: " + wmsg)
        while wanted != []:
            newmsg = ", ".join([ w.str() for w in wanted])
            if newmsg != wmsg:
                wmsg = newmsg
                self.messagelf("Waiting for: " + wmsg)
            for w in wanted:
                success = w.success()
                if success:
                    if delete:
                        w.delete()
                    wanted.remove(w)
            if wanted != []:
                time.sleep(5)
        self.messagelf("{} jobs completed.".format(nwanted))
        self.message("\n")
        return True

    def copy(self, filename, dest="", exclude=False):
        """Copy `filename' to the current directory. The filename is preserved unless `dest' is specified, in which case it is used as the new filename."""
        if dest == "":
            dest = self.fullname(filename)
        self.message("Copying `{}' to `{}'", filename, dest)
        shutil.copyfile(filename, dest)
        if exclude:
            self._addToExclude(filename)

        return dest

    def setFileExt(self, pathname, extension, remove=False):
        """Change the extension of `pathname' to `extension'. If `remove' is specified, removes all extensions that are contained in that list."""
        if remove:
            while True:
                if pathname.find(".") == -1:
                    return pathname + extension
                else:
                    (root, ext) = os.path.splitext(pathname)
                    if ext in remove:
                        pathname = root
                    else:
                        return pathname + extension
        else:
            (root, ext) = os.path.splitext(pathname)
            return root + extension

    def delete(self, pattern):
        """Delete files matching `pattern' in the current directory."""
        self.message("Deleting: {}", pattern)
        subprocess.call("rm " + pattern, shell=True)

    def begin(self, timestamp=False, copyScript=False, copyConf=True, html="index.html"):
        """Start execution of the script. Creates a directory where result files will be written, and chdirs to it. If `timestamp' is True, the directory name contains the current timestamp. If `copyScript' is True, the script is copied to the results directory. If copyConf is True, the configuration file is copied to the results directory. The report is written to the HTML file specified by `html'."""

        if timestamp:
            ts = self.timeStamp()
            dirPath = "{}-{}/".format(self.Name, ts)
        else:
            dirPath = self.Name + "/"

        if os.path.exists(dirPath):
            if self.ask:
                a = raw_input("The output directory already exists. Proceed anyway? (Y/n) ")
                if a not in ['Y', 'y', '']:
                    return False
        else:
            self.message("Creating output directory: {}", dirPath)
            os.makedirs(dirPath)

        self.dir = dirPath

        filePath = dirPath + "/" + html
        scriptPath = dirPath + "/" + self.fullname(self.source)
        tocPath = dirPath + "/toc.html"

        self.out = open(filePath, "w")
        self.toc = open(tocPath, "w")
        self.toc.write("<TR><TD class='main'><b>Table of contents:</b><OL>\n")

        if copyScript:
            self.message("Copying script source {} to {}", self.source, scriptPath)
            shutil.copyfile(self.source, scriptPath)
        if copyConf and self.configFile:
            self.message("Copying config file {} to {}", self.configFile, dirPath + "/" + self.fullname(self.configFile))
            shutil.copyfile(self.configFile, dirPath + "/" + self.fullname(self.configFile))
        self.previousDir = os.getcwd()
        os.chdir(dirPath)
        self.message("Current directory now: {}", dirPath)
        for inc in self.Include:
            shutil.copy(inc, ".")
        self.preamble(self.out)
        return True

    def scene(self, title, timestamp=False):
        """Open a new scene with title `title'."""
        self.sceneIdx += 1
        self.new_scene(self.out, self.sceneIdx, title, timestamp)
        if self.toc:
            self.toc.write("<LI><A href='#sc{}'>{}</A></LI>\n".format(self.sceneIdx, title))

    def reportf(self, text, *args):
        """Add `text' to the current scene in the report. The arguments `args', if present, are inserted into `text' using format."""
        self.out.write(text.format(*args))
        self.out.write("\n")

    def report(self, *words):
        """Add `words' to the current scene in the report, separated by spaces."""
        self.out.write(" ".join([str(f) for f in words]))
        self.out.write("\n")

    def table(self, data, header=False, className="content", align=None, caption=None, delim='\t'):
        """Create a table containing the values in `data' (a list of lists). If `data' is a string, it is assumed to be the name of a delimited file, containing the values for the table. The delimiter defaults to the tab character, but can be changed with the `delimiter' argument. If `header' is specified, it should be a list containing table headers, or the value True, in which case the first row of the data is used as the header. `align' is a string containing one of the following characters for each table column: L (align left), R (align right), C (center), H (use TH instead of TD). `caption' is a caption added at the top of the table."""
        s = self.out
        f = None                # in case we need to open `data' as a file
        rows = None             # iterator for data rows
        odd = True              # first row is odd

        s.write("<CENTER>\n<TABLE class='{}'>\n".format(className))

        # Print caption, if present
        if caption:
            s.write("<CAPTION class='{}'>{}</CAPTION>\n".format(className, caption))

        # If data is a filename, turn it into a csv reader
        if type(data) == type(str()): # is `data' a string?
            if os.path.isfile(data):  # check if it's a file
                f = open(data, 'r')
                rows = csv.reader(f, delimiter=delim)
            else:
                raise Exception('File ' + data + ' does not exist or is not readable.')
        else:
            rows = iter(data)

        # Print header, if present
        if header:
            if header == True:
                header = rows.next()
            s.write("<TR>")
            for h in header:
                s.write("<TH class='{}'>{}</TH>".format(className, h))
            s.write("</TR>\n")

        # Now print all table rows
        for row in rows:
            s.write("<TR class='{}'>".format('odd' if odd else 'even'))
            idx = 0
            for v in row:
                cell = self._decodeAlign(align, idx).format(className, str(v))
                s.write(cell)
                idx = idx + 1
            s.write("</TR>\n")
        s.write("</TABLE>\n</CENTER><BR>\n")
        if f != None:
            f.close()

    def img(self, filename, description=False, thumbnail=False, thumbsize=50, details=True):
        """Insert the image in `filename' in the report. `description' is the image caption. If `thumbnail' is specified, it should be a small version of the image; in this case the thumbnail is inserted in the report as a link to the original image. In either case, the inline image is scaled to a width of `thumbsize' pixels. If `details' is True, adds the format and size of the image to the box."""
        if os.path.isfile(filename):
            s = self.out
            src = filename
            if thumbnail and os.path.isfile(thumbnail):
                src = thumbnail

            s.write("<CENTER><TABLE class='figure'><TR><TD class='figure' align='center'>\n")
            s.write("<A href='{}' target='external'><IMG src='{}' height='{}' border='1'></A>\n".format(filename, src, thumbsize))
            if details:
                fd = self.fileDetails(filename)
                s.write("<br>({} format, {})\n".format(fd[0], self.printBytes(fd[1])))
            if description:
                s.write("<br><i>{}</i>\n".format(description))
            s.write("</TD></TR></TABLE></CENTER><BR>\n")
        
    def file(self, filename, description=False):
        """Insert a box to download file `filename'. `description' is optional text describing the file. File details (format and size) are added automatically."""
        if os.path.isfile(filename):
            s = self.out
            fd = self.fileDetails(filename)
            s.write("<CENTER><TABLE class='figure'><TR><TD class='figure'>\n")
            s.write("<b>File:</b> <A href='{}' target='external'>{}</A>\n".format(filename, filename))
            s.write("<br><b>Size:</b> {}\n".format(self.printBytes(fd[1])))
            if description:
                s.write("<br><b>Description:</b> <i>{}</i>\n".format(description))
            s.write("</TD></TR></TABLE></CENTER><BR>\n")

    def include(self, filename):
        """Include the contents of a text file `filename' in a box."""
        if os.path.isfile(filename):
            s = self.out
            s.write("<CENTER><TABLE class='figure'><TR><TD class='figure'><PRE>\n")
            with open(filename, "r") as f:
                s.write(f.read())
            s.write("</PRE></TD></TR></TABLE></CENTER><BR>\n")

    def execute(self, *strings):
        """Execute the command line represented by `strings', returning the output of the command."""
        cmd = " ".join([str(f) for f in strings])
        if self.log:
            self.log.log("Executing: {}", cmd)
        return self._subprocOutput(cmd)

    def executef(self, command, *args):
        """Like execute(), but the command line is created by applying `args' to `command' using format()."""
        cmd = command.format(*args)
        if self.log:
            self.log.log("Executing: {}", cmd)
        return self._subprocOutput(cmd)

    def shell(self, command, *args):
        """Like executef(), but allows multiple commands, redirection, piping, etc (runs a subshell).
Returns the command's output without the trailing \n."""
        cmd = command.format(*args)
        if self.log:
            self.log.log("Executing: {}", cmd)
        try:
            return subprocess.check_output(cmd, shell=True).rstrip("\n")
        except subprocess.CalledProcessError as cpe:
            return cpe.output.rstrip("\n")

    def query(self, database, query, *args):
        """Executes `query' on sqlite3 database `database'; returns results as a list of lists."""
        q = query.format(*args)
        result = self.shell("""sqlite3 {} "{}" """.format(database, q))
        return [row.split("|") for row in result.split("\n")]

    def queryToDict(self, database, fields, query, *args):
        """Executes `query' on sqlite3 database `database'; returns results as a list of 
dictionaries, using the elements of `fields' as keys."""
        result = []
        q = query.format(*args)
        rows = self.shell("""sqlite3 {} "{}" """.format(database, q)).split("\n")
        for row in rows:
            d = {}
            for (k, v) in zip(fields, row.split("|")):
                d[k] = v
            result.append(d)
        return result

    def submit(self, scriptAndArgs, after=False, done=False, prefix=None, options=None):
        """Submit a script to the SGE queue with the submit command. `scriptAndArgs' is a string containing the qsub script that should be submitted and its arguments. If `after' is specified, schedule this job to run after the one whose jobid is the value of `after'. If `done' is a filename, the script will create an empty file with that name when done (use this in conjunction with the wait() method). Returns the jobid of the submitted job."""
        cmdline = submitCmd
        if after:
            cmdline = cmdline + " -after " + after
        if done:
            cmdline = cmdline + " -done " + done
        if options:
            cmdline = cmdline + " -o " + options
        if prefix == None:
            prefix = self.prefix
        if prefix != None:
            cmdline = cmdline + " -p " + prefix
        cmdline = cmdline + " " + scriptAndArgs
        return self.execute(cmdline)

# Methods section

    def addMethods(self, text):
        text = self.parseReferences(text)
        self.methods.append(text)

    def processRef(self, text):
        pieces = text.split("|")
        ref = pieces[0].strip()
        for piece in pieces:
            piece = piece.strip()
            if piece.startswith("doi:"):
                doi = piece[4:]
                ref += " | doi: <A href='http://dx.doi.org/{}'>{}</A>".format(doi, doi)
            elif piece.startswith("pmid:"):
                pmid = piece[5:]
                ref += " | PubMed: <A href='http://www.ncbi.nlm.nih.gov/pubmed/?term={}'>{}</A>".format(pmid, pmid)
        return ref

    def parseReferences(self, text):
        newtext = ""
        beg = 0
        while True:
            p = text.find("[", beg)
            if p == -1:
                newtext += text[beg:]
                break
            p2 = text.find("]", p)
            if p2 == -1:
                newtext += text[beg:]
                break
            frag = text[beg:p]
            ref = text[p+1:p2]
            self.references.append(self.processRef(ref))
            self.nreferences += 1
            newtext += "{} [{}]".format(frag, self.nreferences)
            beg = p2+1
        return newtext

# Support for conversion to excel

    def toExcel(self, filenames, outfile=False, force=False):
        """Convert the supplied `filenames' (a list) to Excel. If `outfile' is provided,
all files are combined into a single Excel file, one sheet per file. Otherwise, each
file is converted to Excel format separately. If `force' is True, the Excel file is
always generated, otherwise it's only generated when it is stale. Returns the list of 
Excel files written."""
        converted = []
        cmd = "module load dibig_tools; "
        if outfile:
            if force or self.missingOrStale(outfile, other=filenames):
                converted = [outfile]
                cmd += "csvtoxls.py {} -q {}".format(outfile, " ".join(filenames))
            else:
                return outfile
        else:
            for f in filenames:
                x = os.path.splitext(f)[0] + ".xlsx"
                if force or self.missingOrStale(x, other=f):
                    converted.append(x)
                    cmd += "csvtoxls.py {} -q {};".format(x, f)
        self.shell(cmd)
        return converted

# Support for image sliders

    def imgSlider(self, slides, mode='v'):
        """Create an image slider for the specified `slides', which should be a list
of tuples (name, url). `mode' can be 'v', for a vertical slider (default) or 'h' for
a horizontal one."""
        s = self.out
        if mode == 'v':
            ims = imageslider.VerticalSlider(slides)
        else:
            ims = imageslider.HorizontalSlider(slides)
        ims.generate(s)

# Style methods (can be overridden in subclasses)

    def css(self):
        """Returns the CSS for the output page."""
        return """BODY {
  background: lightgrey;
  font-family: arial;
  font-size: 11pt;
  line-height: 150%;
  margin: 0px;
}
TABLE.main {
  width: 90%;
  border-collapse: separate;
  border-spacing: 10px;
}
TD.main {
  background: white;
  border: 2px solid #444444;
  border-radius: 4px;
  padding: 4px;
  page-break-after: always;
}
TABLE.content {
  border-collapse: collapse;
  border-bottom: 1px solid black; /* 1px solid #3366FF; */
}
TH.content {
  border-top: 1px solid black;
  border-bottom: 2px solid black;
  padding: 4px;
}
TD.content {
  /* border: 1px solid #3366FF; */
  padding: 4px;
}
CAPTION.content {
  /* caption-side: bottom; */
  border-bottom-style: 1px solid black;
  font-style: italic;
}
TR.odd {
  background: white;
}
TR.even {
  background: #EEEEEE;
}
TABLE.figure {
  width: 80%;
  border-collapse: collapse;
  border: 1px solid blue;
}
TD.figure {
  padding: 20px;
  background: #EEEEEE;
}
.aleft {
  text-align: left;
}
.aright {
  text-align: right;
}
.acenter {
  text-align: center;
}
.aheader {
  text-align: left;
  font-weight: bold;
  padding-right: 8px;
}

TABLE.hdr {
  width: 100%;
  border: 0px;
  padding: 0px;
  background: white;
  border-collapse: collapse;
}

TH.hdr {
  color: white;
  background: #10337A;
  padding-left: 12px;
  padding-right: 12px;
}

.dibig {
    color: #10337A;
    font-size: 28pt;
    font-weight: bold;
    font-family: Georgia,"Palatino Linotype",Palatino,"Book Antiqua",serif;
    text-decoration: none;
    padding-right: 12px;
}

H2 {
  color: #10337A;
  font-size: 24pt;
}
.upreg {
  color: red;
}
.dnreg {
  color: green;
}

TABLE.legend {
  border: 1px solid black;
  border-collapse: collapse;
  background: white;
}
TABLE.legend TR:hover TD {
  background: yellow;
  cursor: pointer;
}
TH.legend {
  padding: 2px;
  border-bottom: 2px solid black;
  background: lightgrey;
  font-size: 10pt;
  font-weight: bold;
}
TD.legend {
  padding: 2px;
  border-bottom: 1px solid black;
  background: white;
  font-size: 10pt;
}
IMG.bordered {
  border: 1px solid black;
}

"""

    def formatProject(self, proj):
        """Formats project string `proj' according to the following rules:
- If it contains a |, treat as href|text and create a link
- It it starts with http, convert to link
- Otherwise, leave as is.
"""
        if proj == None:
            return "(none)"
        f = proj.find("|")
        if f > 0:
            parts = proj.split("|")
            return "<A href='{}' target=_blank>{}</A>".format(parts[0], parts[1])
        elif proj.startswith("http"):
            return "<A href='{}' target=_blank>{}</A>".format(proj, proj)
        else: 
            return proj
    
    def preamble(self, out):
        "Writes the top part of the HTML output page (from beginning to end of the first box) to output stream `out'."""
        src = self.fileLink(self.source, "Script")
        conf = self.fileLink(self.configFile, "Configuration")
        out.write("""
<!DOCTYPE html>
<html>
  <head>
    <title>{}</title>
    <style type='text/css'>
{}
    </style>
{}
  </head>
  <body>
{}
    <center>
      <h1>{}</h1>
      <table class='main'>
        <tr>
          <td class='main'>
            <b>Title:</b> {}<br>
            <b>Project:</b> {}<br>
            <b>Started on:</b> {}<br>
            <b>Hostname:</b> {}<br>
            <b>Run directory:</b> {}<br>
{}
          </td>
       </tr>
        <!--#config errmsg="" -->
        <!--#include file="toc.html" -->
""".format(self.title, self.css(), self.headExtra(), self.header(), self.title, self.Name, 
           self.formatProject(self.project), self.dateAndTime(), self._subprocOutput("hostname"), os.getcwd(), conf))

    def headExtra(self):
        """Returns additional tags for the <HEAD> section."""
        return ""

    def header(self):
        """Returns the header part of the HTML report (called by preamble)."""
        return ""

    def new_scene(self, out, idx, title, timestamp=False):
        """Writes code to open a new scene to output stream `out'."""
        if self.inScene:
            if timestamp:
                out.write("<BR><BR>Completed: <b>{}</b>".format(self.timeStamp()))
            out.write("</TD></TR>\n")
        self.inScene = True
        out.write("\n<TR><TD class='main'><big><A name='sc{}'>{}. {}</A></big><BR>\n".format(idx, idx, title))

    def postamble(self, out):
        """Writes the final part of the HTML report to output stream `out'."""
        if self.inScene:
            out.write("<BR><BR>Completed: <b>{}</b>".format(self.timeStamp()))
            out.write("</TD></TR>\n")
        out.write("""<!--#config errmsg="" -->\n""")
        out.write("""<!--#include file="additional/index.html" -->\n""")
        out.write("\n<TR><TD class='main'><small>{}</small></TD></TR>\n".format(self.Copyright))
        out.write("\n    </table>\n  </body>\n</html>\n")

