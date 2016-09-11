###################################################
#
# (c) 2016, Alberto Riva, ariva@ufl.edu
# DiBiG, ICBR Bioinformatics, University of Florida
#
# See the LICENSE file for license information.
###################################################

from datetime import date, datetime
from tempfile import mkstemp
import os
import os.path
import sys
import csv
import glob
import time
import shutil
import subprocess
import ConfigParser

# Globals

actCopyright = "&copy; " + str(date.today().year) + ", <A href='mailto:ariva@ufl.edu'>A. Riva</A>, University of Florida."
#submitCmd = "submit.py"
submitCmd = "submit"
excludeFile = ".exclude"

# Utils

def message(string, *args):
    # Write `string' to standard error. `args' are 
    # inserted into `string' with format.
    sys.stderr.write(string.format(*args))
    sys.stderr.write("\n")

def fullname(pathname):
    # Returns the filename part of `pathname'
    # *** This is the same as os.path.basename()
    return os.path.split(pathname)[1]

def fileDetails(pathname):
    # Returns a tuple containing file extension and size of the
    # file pointed to by `pathname'
    ext = os.path.splitext(pathname)[1]
    ext = ext[1:]
    return (ext, os.path.getsize(pathname))

def printBytes(b):
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

def timeStamp():
    dt = datetime.now()
    return "{}-{}-{}@{}:{:0>2}".format(dt.month, dt.day, dt.year, dt.hour, dt.minute)

def dateAndTime():
    dt = datetime.now()
    return "{}/{}/{} {}:{:0>2}:{:0>2}".format(dt.month, dt.day, dt.year, dt.hour, dt.minute, dt.second)

def subprocOutput(command):
    # Execute `command', return the command's output.
    # `command' can be a string or a list in which the first
    # element is the command name and remaining elements are arguments.
    # The end-of-line character at the end of the last line of output
    # is removed automatically.
    # NOTE: signals an error if the command returns a non-zero return code.
    return subprocess.check_output(command.split(" ")).rstrip("\n")

# Support for tables

def decodeAlign(align, i):
    """Decodes the character at position `i' in an align string `align' into the corresponding CSS style (for tables). If `align' is None, assume L at each position."""
    al = {'L': 'aleft', 'R': 'aright', 'C': 'acenter', 'H': 'aheader'}
    if align == None:
        return al['L']
    else:
        return al[align[i]];
    
def decodeAlignNew(align, i):
    al = {'L': "<TD class='{} aleft'>{}</TD>",
          'R': "<TD class='{} aright'>{}</TD>",
          'C': "<TD class='{} acenter'>{}</TD>",
          'H': "<TD class='{} aheder'>{}</TD>",
          'N': "<TD class='{} aright'>{:,}</TD>",
          'F': "<TD class='{} aright'>{:.3f}</TD>"}
    if align == None:
        return al['L']
    else:
        return al[align[i]]

# Helper classes for the wait() command
# Each waiter has a success() method that returns True
# when the event it's waiting for happens

class Waiter():
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
    wanted = 0

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

    def __init__(self, filename, wanted):
        self.filename = filename
        self.wanted = wanted

    def str(self):
        return "<{} files matching {}>".format(self.wanted, self.filename)

    def success(self):
        """A GlobWaiter is successful if the number of existing files matching
the pattern in `filename' is greater than or equal to `wanted'."""
        return (len(glob.glob(self.filename)) >= self.wanted)
        
    def delete(self):
        for f in glob.glob(self.filename):
            os.remove(f)

# Script class

class Script:
    Name = "run"
    Title = "Script"
    Project = "(no name)"
    Copyright = actCopyright
    Fields = {}
    Arguments = []
    Include = []                 # List of additional files to be copied in run directory
    # Runtime
    source = ""                  # Name of file containing script
    tempfiles = []               # List of temporary files
    dir = ""                     # Output directory
    out = False                  # Output stream
    inScene = False              # Are we inside a scene?
    previousDir = ""             # Directory before starting execution
    conf = None                  # ConfigParser object

    # Internal methods (not meant to be called by user)

    def __init__(self):
        self.Fields = {}
        self.Arguments = []
        self.tempfiles = []
        self.previousDir = ""
        self.Include = ['/apps/dibig_tools/1.0/lib/img/UF-ICBR-logo.png']

    def _cleanup(self):

        # Finish HTML file and close it
        if self.out and not self.out.closed:
            self.postamble(self.out)
            self.out.close()

        # Remove temporary files
        for fdata in self.tempfiles:
            os.remove(fdata[1])

        # Return to parent directory
        if self.previousDir != "":
            os.chdir(self.previousDir)
            message("Current directory now: {}", os.getcwd())

    def _addToExclude(self, filename):
        global excludeFile
        with open(excludeFile, "a") as out:
            out.write("{}/{}\n".format(self.Name, filename))
        return filename

    def loadConfiguration(self, filename):
        if os.path.isfile(filename):
            self.conf = ConfigParser.ConfigParser()
            self.conf.read(filename)
            return self.conf
        else:
            print "Error: configuration file {} not found or not readable.".format(filename)
            exit(1)

    def getConf(self, entry, section="General"):
        try:
            return self.conf.get(section, entry)
        except ConfigParser.NoOptionError:
            return None

    # Actor definitions (should normally NOT be overwritten)

    def name(self, name):
        """Declare the name of this script to be `name'. This value is used as the name of the directory created by the script."""
        self.Name = name

    def title(self, title):
        """Declare the title of this script to be `title'. The title is printed at the top of the HTML report."""
        self.Title = title

    def project(self, project):
        """Declare the name of the project that this script belongs to. The project is printed in the header of the HTML report."""
        self.Project = project

    def script(self, name, title, project):
        """Declare the name, title, and project for this script."""
        self.Name = name
        self.Title = title
        self.Project = project

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
        fdata = mkstemp(dir=".")
        f = os.fdopen(fdata[0], "w")
        self.tempfiles.append([fdata[0], fdata[1], f])
        return f
    
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
        """Wait until all the files in the `wanted' list get created. Returns when all specified files exist. This can be used to check for the completion of a background script. If `delete' is True, the files are deleted before returning."""

        # If a single filename was passed, turn it into a list
        if type(wanted).__name__ != 'list':
            wanted = [wanted]

        wanted = [ self._parseWait(w) for w in wanted ]
        message("Waiting for: " + ", ".join([ w.str() for w in wanted]))
        while wanted != []:
            for w in wanted:
                success = w.success()
                if success:
                    if delete:
                        w.delete()
                    wanted.remove(w)
                    message("Waiting for: " + ", ".join([ w.str() for w in wanted]))
            time.sleep(1)

    def copy(self, filename, dest="", exclude=False):
        """Copy `filename' to the current directory. The filename is preserved unless `dest' is specified, in which case it is used as the new filename."""
        if dest == "":
            dest = fullname(filename)
        message("Copying `{}' to `{}'", filename, dest)
        shutil.copyfile(filename, dest)
        if exclude:
            self._addToExclude(filename)

        return dest

    def setFileExt(self, pathname, extension, remove=False):
        """Change the extension of `pathname' to `extension'."""
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

    def missingOrStale(self, filename, other=False, warn=False):
        """Returns true if `filename' is missing or (when `other' is specified) older than `other'."""
        if not os.path.isfile(filename):
            if warn:
                sys.stderr.write("File `{}' does not exist or is not readable.\n".format(filename))
            return True             # missing
        elif other and os.path.isfile(other):
            this = os.path.getmtime(filename)
            that = os.path.getmtime(other)
            if this < that:
                if warn:
                    sys.stderr.write("File `{}' is older than file `{}'.\n".format(filename, other))
                return True
            else:
                return False
        else:
            return False

    def delete(self, pattern):
        """Delete files matching `pattern' in the current directory."""
        message("Deleting: {}", pattern)
        subprocess.call("rm " + pattern, shell=True)

    def begin(self, timestamp=True, copyScript=True, html="index.html"):
        """Start execution of the script. Creates a directory where result files will be written, and chdirs to it. If `timestamp' is True, the directory name contains the current timestamp. If `copyScript' is True, the script is copied to the results directory. The report is written to the HTML file specified by `html'."""

        if timestamp:
            ts = timeStamp()
            dirPath = "{}-{}/".format(self.Name, ts)
        else:
            dirPath = self.Name + "/"

        message("Creating output directory: {}", dirPath)
        if not os.path.exists(dirPath):
            os.makedirs(dirPath)

        self.dir = dirPath

        filePath = dirPath + "/" + html
        scriptPath = dirPath + "/" + fullname(self.source)
        
        self.out = open(filePath, "w")

        if copyScript:
            shutil.copyfile(self.source, scriptPath)
        self.previousDir = os.getcwd()
        os.chdir(dirPath)
        message("Current directory now: {}", dirPath)
        for inc in self.Include:
            shutil.copy(inc, ".")
        self.preamble(self.out)

    def scene(self, idx, title, timestamp=False):
        """Open a new scene with index `idx' and title `title'."""
        self.new_scene(self.out, idx, title, timestamp)

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
                s.write("<TD class='{} {}'>{}</TD>".format(className, decodeAlign(align, idx), str(v)))
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
                fd = fileDetails(filename)
                s.write("<br>({} format, {})\n".format(fd[0], printBytes(fd[1])))
            if description:
                s.write("<br><i>{}</i>\n".format(description))
            s.write("</TD></TR></TABLE></CENTER><BR>\n")
        
    def file(self, filename, description=False):
        """Insert a box to download file `filename'. `description' is optional text describing the file. File details (format and size) are added automatically."""
        if os.path.isfile(filename):
            s = self.out
            fd = fileDetails(filename)
            s.write("<CENTER><TABLE class='figure'><TR><TD class='figure'>\n")
            s.write("<b>File:</b> <A href='{}' target='external'>{}</A>\n".format(filename, filename))
            s.write("<br><b>Size:</b> {}\n".format(printBytes(fd[1])))
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
        message("Executing: {}", cmd)
        return subprocOutput(cmd)

    def executef(self, command, *args):
        """Like execute(), but the command line is created by applying `args' to `command' using format()."""
        cmd = command.format(*args)
        message("Executing: {}", cmd)
        return subprocOutput(cmd)

    def shell(self, command, *args):
        """Like executef(), but allows multiple commands, redirection, piping, etc (runs a subshell).
Returns the command's output without the trailing \n."""
        cmd = command.format(*args)
        message("Executing: {}", cmd)
        try:
            return subprocess.check_output(cmd, shell=True).rstrip("\n")
        except subprocess.CalledProcessError as cpe:
            return cpe.output.rstrip("\n")

    def submit(self, scriptAndArgs, after=False, done=False):
        """Submit a script to the SGE queue with the submit command. `scriptAndArgs' is a string containing the qsub script that should be submitted and its arguments. If `after' is specified, schedule this job to run after the one whose jobid is the value of `after'. If `done' is a filename, the script will create an empty file with that name when done (use this in conjunction with the wait() method). Returns the jobid of the submitted job."""
        cmdline = submitCmd
        if after:
            cmdline = cmdline + " -after " + after
        if done:
            cmdline = cmdline + " -done " + done
        cmdline = cmdline + " " + scriptAndArgs
        return self.execute(cmdline)

    # DNA sequences printing

    def DNA_header(self, s, width):
        s.write("{:8}1".format(""))
        for i in range(2, width+1):
            if i % 10 == 0:
                s.write(str(i))
            elif (i + 1) % 10 == 0:
                pass
            else:
                s.write(" ")
        s.write("\n{:8}|".format(""))
        for i in range(2, width+1):
            if i % 10 == 0:
                s.write("|")
            else:
                s.write(" ")
        s.write("\n")

    def DNA_complement(self, b):
        base_complements = {"A": "T", "C": "G", "G": "C", "T": "A", "a": "t", "c": "g", "g": "c", "t": "a"}
        if b in base_complements:
            return base_complements[b]
        else:
            return b

    def DNA(self, seq, name=False, description=False, rc=False, offset=1, width=60):
        """Print DNA sequence `seq' to the report in FASTA format. Sequences are formatted to `width' characters per line, and numbered starting at `offset'. `name' and `description' are printed before the sequence, if specified. If `rc' is True, prints the complement sequence under each line."""
        s = self.out
        pos = offset

        s.write("<CENTER><TABLE class='figure'><TR><TD class='figure'>\n")
        if name:
            s.write("<b>Name:</b> {}<br>\n".format(name))
        s.write("<b>Length:</b> {}bp<br>\n".format(len(seq)))
        s.write("<pre>\n")
        self.DNA_header(s, width)
        s.write("{:>7} ".format(pos))
        for i in range(len(seq)):
            # highlighting not implemented yet...
            s.write(seq[i])
            pos = pos + 1
            if ((i + 1) % width) == 0:
                if rc:
                    rcpos = pos - width
                    s.write("{:>8}".format(""))
                    for j in range(i-width, i):
                        s.write(base_complement(seq[j]))
                    s.write("\n")
                s.write("\n{:>7} ".format(pos))
        s.write("</pre></TD></TR></TABLE></CENTER>\n")

# Style methods (can be overridden in subclasses)

    def css(self):
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
"""

    def preamble(self, out):
        src = fullname(self.source)
        out.write("""
<!DOCTYPE html>
<html>
  <head>
    <title>{}</title>
    <style type='text/css'>
{}
    </style>
  </head>
  <body>
{}
    <center>
      <h1>{}</h1>
      <table class='main'>
        <tr>
          <td class='main'>
            <b>Script:</b> {}<br>
            <b>Project:</b> {}<br>
            <b>Started on:</b> {}<br>
            <b>Hostname:</b> {}<br>
            <b>Run directory:</b> {}<br>
            <b>Source:</b> <A href='{}' target='_blank'>{}</A>
          </td>
        </tr>
""".format(self.Title, self.css(), self.header(), self.Title, self.Name, self.Project, dateAndTime(), subprocOutput("hostname"), os.getcwd(), src, src))

    def header(self):
        return """<table class='hdr'>
      <tr><td align='left'><A href='http://biotech.ufl.edu/'><img src='UF-ICBR-logo.png' border='0'></A></td><td align='right'><A class='dibig' href='http://dibig.biotech.ufl.edu'>DiBiG</A></td></tr>
      <tr><th class='hdr' align='left'>ICBR Bioinformatics</th><th class='hdr' align='right'><i>Powered by Actor, v1.0</i><tr>
    </table>"""

    def postamble(self, out):
        if self.inScene:
            out.write("<BR><BR>Completed: <b>{}</b>".format(timeStamp()))
            out.write("</TD></TR>\n")
        out.write("\n<TR><TD class='main'><small>{}</small></TD></TR>\n".format(self.Copyright))
        out.write("\n    </table>\n  </body>\n</html>\n")

    def new_scene(self, out, idx, title, timestamp):
        if self.inScene:
            if timestamp:
                out.write("<BR><BR>Completed: <b>{}</b>".format(timeStamp()))
            out.write("</TD></TR>\n")
        self.inScene = True
        out.write("\n<TR><TD class='main'><big>{}. {}</big><BR>\n".format(idx, title))
