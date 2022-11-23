#####################################################
#                                                   #
# (c) 2016, Alberto Riva, ariva@ufl.edu             #
# DiBiG, ICBR Bioinformatics, University of Florida #
#                                                   #
# See the LICENSE file for license information.     #
#####################################################

import sys

def cellify(s):
    tp = type(s).__name__
    if tp == 'str':
        return C(s)
    elif tp == 'int':
        return N(s)
    elif tp == 'float':
        return F(s)
    else:
        return s

class TableCell():
    cls = ""
    value = ""

    def __init__(self, v):
        self.value = v

    def printCell(self, v, cls):
        if cls:
            return "<TD class='{}'>{}</TD>".format(cls, v)
        else:
            return "<TD>{}</TD>".format(v)

    def toHTML(self, cls=""):
        return self.printCell(self.value, cls)

class C(TableCell):
    """Regular cell, printed as-is, left-aligned."""

    pass

class P(TableCell):
    """Percentage cell, printed as nn.dd%, right-aligned."""

    def __init__(self, v, div=None):
        if div:
            self.value = 1.0 * float(v) / float(div)
        else:
            self.value = float(v)

    def toHTML(self, cls=""):
        return self.printCell("{:.2f}%".format(100.0 * self.value), cls=cls + " aright")

class P3(TableCell):
    """Percentage cell, printed as nn.ddd%, right-aligned."""

    def __init__(self, v, div=None):
        if div:
            self.value = 1.0 * float(v) / float(div)
        else:
            self.value = float(v)

    def toHTML(self, cls=""):
        return self.printCell("{:.3f}%".format(100.0 * self.value), cls=cls + " aright")

class PP(TableCell):
    """Cell showing value and percentage of total, as 'xx (xx.xx%)', right-aligned."""

    def __init__(self, v, div):
        if div:
            pct = 100.0 * float(v) / float(div)
        else:
            pct = 0
        self.value = "{:,} ({:.3f}%)".format(int(v), pct)

    def toHTML(self, cls=""):
        return self.printCell(self.value, cls=cls + " aright")

class PP0(TableCell):
    """Cell showing value and percentage of total, as 'xx (xx%)', right-aligned."""

    def __init__(self, v, div):
        if div:
            pct = 100.0 * float(v) / float(div)
        else:
            pct = 0
        self.value = "{:,} ({}%)".format(int(v), int(pct))

    def toHTML(self, cls=""):
        return self.printCell(self.value, cls=cls + " aright")

class A(TableCell):
    """Anchor cell, printed as hyperlink, centered."""
    href = ""
    target = "_blank"

    def __init__(self, href, text=None, target='_blank'):
        self.href = href
        self.target = target
        if text:
            self.value = text
        else:
            self.value = href

    def toHTML(self, cls=""):
        return self.printCell("<A href='{}' target='{}'>{}</A>".format(self.href, self.target, self.value), cls=cls + " acenter")

class AD(TableCell):
    """Anchor cell, but includes number of rows in the file, printed as with D. Cell is right aligned."""
    href = ""
    target = "_blank"
    nrows = 0

    def __init__(self, href, nrows, text=None, target='_blank'):
        self.href = href
        self.target = target
        self.nrows = nrows
        if text:
            self.value = text
        else:
            self.value = href

    def toHTML(self, cls=""):
        return self.printCell("<A href='{}' target='{}'>{}</A> ({:,})".format(self.href, self.target, self.value, self.nrows), cls=cls + " aright")
    
class R(TableCell):
    """Text cell, printed as-is, right aligned."""

    def __init__(self, v, cls=None):
        self.value = v

    def toHTML(self, cls=""):
        return self.printCell(self.value, cls=cls + " aright")

class N(TableCell):
    """Numeric cell, printed as-is, right aligned."""

    def __init__(self, v):
        self.value = int(v)

    def toHTML(self, cls=""):
        return self.printCell(self.value, cls=cls + " aright")

class D(TableCell):
    """Fancy number cell, printed with thousands separator, right-aligned."""

    def __init__(self, v, cls=None, bold=False):
        self.value = int(v)
        self.bold = bold
        if cls:
            self.cls = cls

    def toHTML(self, cls=""):
        if self.bold:
            return self.printCell("<B>{:,}</B>".format(self.value), cls=self.cls + cls + " aright")
        else:
            return self.printCell("{:,}".format(self.value), cls=self.cls + cls + " aright")

class F(TableCell):
    """Floating point number, two decimals, right-aligned."""

    def __init__(self, v):
        self.value = float(v)

    def toHTML(self, cls=""):
        return self.printCell("{:.2f}".format(1.0 * self.value), cls=cls + " aright")

class F3(TableCell):
    """Floating point number, two decimals, right-aligned."""

    def __init__(self, v):
        self.value = float(v)

    def toHTML(self, cls=""):
        return self.printCell("{:.3f}".format(1.0 * self.value), cls=cls + " aright")

class TableRow():
    """Class that represents a table row. A row has a parent (the table), a list of cells (strings)
and optionally a row header (a string)."""
    parent = None
    cells = []
    rowClass = None
    cellClass = ""
    rowHeader = None
    rowHeaderClass = None
    rowHeaderSpan = None

    def __init__(self, parent, cells):
        self.parent = parent
        self.cells = cells

    def toHTML(self, align=None):
        r = "<TR"
        if self.rowClass:
            r += " class='{}'".format(self.rowClass)
        r += ">"
        if self.rowHeader:
            cls = " class='{}'".format(self.rowHeaderClass) if self.rowHeaderClass else ''
            r += "<TD rowspan={}{}>{}</TD>".format(self.rowHeaderSpan, cls, self.rowHeader)
        if False: #align:
            for c, a in zip(self.cells, align):
                r += "<TD"
                if self.cellClass:
                    r += " class='{}'".format(self.cellClass)
                r += " align='{}'>{}</TD>".format(a, c.toHTML())
        else:
            for c in self.cells:
                r += c.toHTML(cls=self.cellClass)
                #r += "<TD"
                #if self.cellClass:
                #    r += " class='{}'".format(self.cellClass)
                #r += ">{}</TD>".format(c.toHTML())
        r += "</TR>"
        return r

class SectionRow(TableRow):
    """A section row only has a single cell, taking up the entire width of the table."""

    def toHTML(self, align=None):
        r = "<TR"
        if self.rowClass:
            r += " class='{}'".format(self.rowClass)
        r += ">"
        r += "<TD colspan={}".format(self.parent.ncols + (1 if self.parent.hasRowHeader else 0))
        if self.cellClass:
            r += " class='{}'".format(self.cellClass)
        r += "><b><i>{}</i></b></TD>".format(self.cells[0])
        r += "</TR>"
        return r

class HeaderRow(TableRow):

    def toHTML(self, align=None):
        r = "<TR"
        if self.rowClass:
            r += " class='{}'".format(self.rowClass)
        r += ">"
        for c in self.cells:
            r += "<TD nowrawp"
            if self.cellClass:
                r += " class='{}'".format(self.cellClass)
            r += "><b>{}</b></TD>".format(c)
        r += "</TR>"
        return r

class Table():
    id = None
    headRows = []
    bodyRows = []
    footRows = []
    align = None
    highlight = None
    caption = None
    tableClass = None
    columnHeaderClass = None
    headerRowClass = None
    oddRowClass = None
    evenRowClass = None
    sectionRowClass = None
    headerCellClass = None
    bodyCellClass = None
    sectionCellClass = None
    filename = None

    # Internal
    tableNum = [1]              # Make this persistent
    rowIdx = 1
    ncols = 0
    adding = 'b'                # by default add to body
    tempRowHeader = None        # placeholder for a row header
    hasRowHeader = False
    attrNames = ['id', 'caption', 'highlight', 'align', 'tableClass', 'headerRowClass', 'oddRowClass', 'evenRowClass', 'sectionRowClass', 'filename']
    filestream = None

    def __init__(self, **attributes):
        self.headRows = []
        self.bodyRows = []
        self.footRows = []
        for a in self.attrNames:
            if a in attributes:
                setattr(self, a, attributes[a])
        if self.filename:
            self.filestream = open(self.filename, "w")

    def startHead(self):
        self.adding = 'h'

    def startBody(self):
        self.adding = 'b'

    def startFooter(self):
        self.adding = 'f'

    def addRowHeader(self, text, rowspan=1):
        """Add a cell representing a row header at the beginning of the current row."""
        self.tempRowHeader = ("<b>" + text + "</b>", rowspan)
        self.hasRowHeader = True
        if self.filestream:
            self.filestream.write(text)

    def _addRow(self, row):
        if self.adding == 'h':
            self.headRows.append(row)
        elif self.adding == 'b':
            self.bodyRows.append(row)
        elif self.adding == 'f':
            self.footRows.append(row)
        nc = len(row.cells) + (1 if row.rowHeader else 0)
        if nc > self.ncols:
            self.ncols = nc

    def addRow(self, cells, align=None):
        cells = [ cellify(c) for c in cells ]
        row = TableRow(self, cells)
        row.align = align or self.align
        row.rowClass = self.oddRowClass if (self.rowIdx % 2 == 1) else self.evenRowClass
        if self.tempRowHeader:
            row.rowHeader = self.tempRowHeader[0]
            row.rowHeaderSpan = self.tempRowHeader[1]
            self.tempRowHeader = None
        self._addRow(row)
        self.rowIdx += 1
        if self.filestream:
            self.filestream.write("\t".join([str(c.value) for c in cells]) + "\n")
        return row

    def addHeaderRow(self, titles):
        row = HeaderRow(self, titles)
        row.rowClass = self.headerRowClass
        self._addRow(row)
        self.rowIdx = 1
        if self.filestream:
            self.filestream.write("#" + "\t".join(titles) + "\n")
        return row

    def addSectionRow(self, title):
        row = SectionRow(self, [title])
        row.rowClass = self.sectionRowClass
        self._addRow(row)
        self.rowIdx = 1
        if self.filestream:
            self.filestream.write("##" + title + "\n")
        return row

    def blockToHTML(self, stream, tag, rows, addAlign=False):
        if addAlign:
            aln = self.parseAlign()
        else:
            aln = None
        if len(rows) > 0:
            stream.write("  <" + tag + ">\n")
            for row in rows:
                stream.write("    " + row.toHTML(aln) + "\n")
            stream.write("  </" + tag + ">\n")
            
    def parseAlign(self):
        aln = []
        done = 0
        current = None
        codes = {'L': 'left', 'l': 'left',
                 'R': 'right', 'r': 'right',
                 'C': 'center', 'c': 'center'}
        if self.align:
            for a in self.align:
                if a in codes:
                    current = codes[a]
                    aln.append(current)
                    done += 1
                elif a.isdigit():
                    n = int(a) - 1
                    for i in range(n):
                        aln.append(current)
                        done += 1
        while done < self.ncols:
            aln.append('left')
            done += 1
        return aln

    def addColgroup(self, stream):
        stream.write("  <COLGROUP>\n")
        for c in range(1, self.ncols + 1):
            if c in self.highlight:
                stream.write("    <COL style='background:lightyellow' />\n")
            else:
                stream.write("    <COL />\n")
        stream.write("  </COLGROUP>\n")

    def toHTML(self, stream):
        """Print this table to `stream'."""
        stream.write("<TABLE")
        if self.id:
            stream.write(" id='{}'".format(self.id))
        if self.tableClass:
            stream.write(" class='{}'".format(self.tableClass))
        stream.write(">\n")
        if self.caption:
            stream.write("<CAPTION>{}</CAPTION>\n".format(self.caption))
        if self.highlight and len(self.highlight) > 0:
            self.addColgroup(stream)
        self.blockToHTML(stream, "THEAD", self.headRows)        
        self.blockToHTML(stream, "TBODY", self.bodyRows, addAlign=True)
        self.blockToHTML(stream, "TFOOT", self.footRows)
        stream.write("</TABLE>\n")
        if self.filestream:
            self.filestream.close()

class ScrollingTable(Table):
    visibleRows = 15
    attrNames = ['id', 'caption', 'align', 'visibleRows', 'sectionRowClass', 'filename']

    def toHTML(self, stream):
        #stream.write("  <TABLE class='table table-hover table-bordered table-condensed' id='{}'>\n".format(self.id))
        stream.write("<BR><BR><CENTER>\n")
        stream.write("  <TABLE id='{}' cellspacing='0' width='90%'>\n".format(self.id))
        if self.highlight and len(self.highlight) > 0:
            self.addColgroup(stream)
        self.blockToHTML(stream, "THEAD", self.headRows)        
        self.blockToHTML(stream, "TBODY", self.bodyRows, addAlign=True)
        self.blockToHTML(stream, "TFOOT", self.footRows)
        stream.write("""  </TABLE>
""")
        if self.filestream:
            self.filestream.close()
        if self.caption:
            stream.write("<I><SMALL><b>Table {}.</b> {}</SMALL></I><BR><BR>\n".format(self.tableNum[0], self.caption))
            self.tableNum[0] += 1
        stream.write("""
  </CENTER>
<SCRIPT type="text/javascript">
jQuery(document).ready(function($)
{{
        $('#{}').tableScroll({{height:250}});
}});

</SCRIPT>
""".format(self.id))

def ptd(line):
    return line.rstrip("\r\n").split("\t")

def fileToTable(filename, tableId, stream=sys.stdout, visibleRows=20, header=False, headerFromFile=False, ignoreChar='#', maxrows=0):
    """Create a scrolling table with id `tableId' to display the contents of file `filename'."""
    ta = ScrollingTable(id=tableId, visibleRows=visibleRows)
    with open(filename, "r") as f:
        if header:
            ta.startHead()
            ta.addHeaderRow(header)
        elif headerFromFile:
            line = f.readline()
            if line[0] == ignoreChar:
                line = line[1:]
            ta.startHead()
            ta.addHeaderRow(ptd(line))
        ta.startBody()
        for line in f:
            if not ignoreChar or line[0] != ignoreChar:
                parsed = ptd(line)
                ta.addRow(parsed)
                maxrows -= 1
                if maxrows == 0:
                    break
    if stream:
        ta.toHTML(stream)
    return ta

def scrolltest():
    ta = ScrollingTable(id='t1', visibleRows=20)
    ta.startHead()
    ta.addHeaderRow(['h1', 'h2', 'h3'])
    ta.startBody()
    ta.addSectionRow('title')
    ta.addRow(['one', 'two', 'three'])
    ta.startFooter()
    ta.addRowHeader("Total")
    ta.addRow(['four', 'five', 'six'])
    ta.toHTML(sys.stdout)
        
def test():
    ta = Table(tableClass='c1')
    ta.startHead()
    ta.addHeaderRow(['h1', 'h2', 'h3'])
    ta.startBody()
    ta.addSectionRow('title')
    ta.addRow(['one', 'two', 'three'])
    ta.startFooter()
    ta.addRowHeader("Total")
    ta.addRow(['four', 'five', 'six'])
    ta.toHTML(sys.stdout)
    print(ta.ncols)
    print(ta.hasRowHeader)
