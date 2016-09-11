import Actor

class DibigActor(Actor.Actor):
    dibigpath = '/apps/dibig_tools/1.0/lib/'

    def __init__(self):
        self.Include = [self.dibigpath + 'img/UF-ICBR-logo.png',
                        #self.dibigpath + 'js/jquery-1.10.2.min.js',
                        #self.dibigpath + 'js/jquery.scrollTableBody-1.0.0.js',
                        #self.dibigpath + 'css/bootstrap.min.css',
                        self.dibigpath + 'js/jquery.tablescroll.js',
                        self.dibigpath + 'css/jquery.tablescroll.css']
        

    def headExtra(self):
        """Returns additional tags for the <HEAD> section."""
        return """    <link rel="stylesheet" type="text/css" href="jquery.tablescroll.css"/>
    <!-- <link rel="stylesheet" type="text/css" href="bootstrap.min.css"/> -->
    <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/1.5.1/jquery.min.js"></script>
    <script type="text/javascript" src="jquery.tablescroll.js"></script>
"""  

    def header(self):
        """Returns the header part of the HTML report (called by preamble)."""
        return """<table class='hdr'>
      <tr><td align='left'><A href='http://biotech.ufl.edu/'><img src='UF-ICBR-logo.png' border='0'></A></td><td align='right'><A class='dibig' href='http://dibig.biotech.ufl.edu'>DiBiG</A></td></tr>
      <tr><th class='hdr' align='left'>ICBR Bioinformatics</th><th class='hdr' align='right'><i>Powered by Actor, v1.0</i><tr>
    </table>"""

