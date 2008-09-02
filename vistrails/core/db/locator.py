############################################################################
##
## Copyright (C) 2006-2007 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################

import os.path
from core.configuration import get_vistrails_configuration, \
    get_vistrails_temp_configuration
from core.system import vistrails_default_file_type, get_elementtree_library, \
                        default_connections_file
from core.external_connection import ExtConnectionList, DBConnection
from db.services.locator import XMLFileLocator as _XMLFileLocator, \
    DBLocator as _DBLocator, ZIPFileLocator as _ZIPFileLocator
from PyQt4 import QtCore
import core.configuration
ElementTree = get_elementtree_library()

class CoreLocator(object):

    @staticmethod
    def load_from_gui(parent_widget, obj_type):
        pass # Opens a dialog that the user will be able to use to
             # show the right values, and returns a locator suitable
             # for loading a file

    @staticmethod
    def save_from_gui(parent_widget, obj_type, locator):
        pass # Opens a dialog that the user will be able to use to
             # show the right values, and returns a locator suitable
             # for saving a file

    def update_from_gui(self, klass=None):
        pass

class XMLFileLocator(_XMLFileLocator, CoreLocator):

    def __init__(self, filename):
        _XMLFileLocator.__init__(self, filename)
        
    def load(self, klass=None):
        from core.vistrail.vistrail import Vistrail
        if klass is None:
            klass = Vistrail
        obj = _XMLFileLocator.load(self, klass.vtType)
        klass.convert(obj)
        obj.locator = self
        return obj

    def save(self, obj):
        klass = obj.__class__
        obj = _XMLFileLocator.save(self, obj, False)
        klass.convert(obj)
        obj.locator = self
        return obj

    def save_as(self, obj):
        klass = obj.__class__
        obj = _XMLFileLocator.save(self, obj, True)
        klass.convert(obj)
        obj.locator = self
        return obj

    ##########################################################################

    def __eq__(self, other):
        if type(other) != XMLFileLocator:
            return False
        return self._name == other._name

    ##########################################################################

    @staticmethod
    def load_from_gui(parent_widget, obj_type):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_load_file_locator_from_gui(parent_widget, obj_type)

    @staticmethod
    def save_from_gui(parent_widget, obj_type, locator=None):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_save_file_locator_from_gui(parent_widget, obj_type,
                                                         locator)

    def update_from_gui(self, klass=None):
        from core.vistrail.vistrail import Vistrail
        if klass is None:
            klass = Vistrail
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_load_file_locator_from_gui(parent_widget, klass.vtType)

class DBLocator(_DBLocator, CoreLocator):
    
    __list = ExtConnectionList.getInstance(default_connections_file())
    
    class getKeyChain(object):
        def set_key(self, key, passwd):
            QtCore.QCoreApplication.instance().keyChain.set_key(key,passwd)
        
        def get_key(self, key):
            return QtCore.QCoreApplication.instance().keyChain.get_key(key)
    
    keyChain = getKeyChain()
    
    def __init__(self, host, port, database, user, passwd, name=None,
                 obj_id=None, obj_type=None, connection_id=None,
                 version_node=None, version_tag=None):
        
        _DBLocator.__init__(self, host, port, database, user, passwd, name,
                            obj_id, obj_type, connection_id, version_node,
                            version_tag)
        self.ext_connection_id = -1

    def load(self, klass=None):
        from core.vistrail.vistrail import Vistrail
        if klass is None:
            klass = Vistrail
        obj = _DBLocator.load(self, klass.vtType)
        klass.convert(obj)
        obj.locator = self
        return obj

    def save(self, obj):
        klass = obj.__class__
        obj = _DBLocator.save(self, obj, False)
        klass.convert(obj)
        obj.locator = self
        return obj

    def save_as(self, obj):
        klass = obj.__class__
        obj = _DBLocator.save(self, obj, True)
        klass.convert(obj)
        obj.locator = self
        return obj

    def update_from_gui(self, klass=None):
        from core.vistrail.vistrail import Vistrail
        if klass is None:
            klass = Vistrail
        config = self.find_connection_info(self._host, self._port, self._db) 
        if config is None:
            import gui.extras.core.db.locator as db_gui
            config = db_gui.get_db_connection_from_gui(None,klass.vtType,"",
                                                       self._host,
                                                       self._port,
                                                       self._user,
                                                       self._passwd,
                                                       self._db
                                                       )
        if config and config['succeeded'] == True:
            self._host = config['host']
            self._port = config['port']
            self._db = config['db']
            self._user = config['user']
            self._passwd = config['passwd']
            self.ext_connection_id = self.set_connection_info(**config)
            return True
        
        return False
    
    def find_connection_info(self, host, port, db):
        """find_connection_info(host:str, port: int, db: str) -> dict
        Returns complete info of a connection with the given parameters

        """
        id = self.__list.find_db_connection(host,port,db)
        if id != -1:
            return self.get_connection_info(id)
        else:
            return None
    
    def get_connection_info(self, id):
        """get_connection_info(id: int) -> dict
        Returns info of ExtConnection """
        conn = self.__list.get_connection(id)
        if conn != None:
            key = str(conn.id) + "." + conn.name + "." + conn.host
            passwd = DBLocator.keyChain.get_key(key)
            config = {'id': conn.id,
                      'name': conn.name,
                      'host': conn.host,
                      'port': conn.port,
                      'user': conn.user,
                      'passwd': passwd,
                      'db': conn.database,
                      'succeeded': True}
        else:
            config = None
        return config
    
    def set_connection_info(self, *args, **kwargs):
        """set_connection_info(id: int, name: str, host: str, port:int,
                     user:str, passwd:str, db:str) -> None
        If the connection exists it will update it, else it will add it

        """
        if kwargs.has_key("id"):
            id = kwargs["id"]
        if kwargs.has_key("name"):
            name = kwargs["name"]
        if kwargs.has_key("host"):
            host = kwargs["host"]
        if kwargs.has_key("port"):
            port = kwargs["port"]
        if kwargs.has_key("user"):
            user = kwargs["user"]
        if kwargs.has_key("passwd"):
            passwd = kwargs["passwd"]
        if kwargs.has_key("db"):
            db = kwargs["db"]

        conn = DBConnection(id=id,
                            name=name,
                            host=host,
                            port=port,
                            user=user,
                            passwd='',
                            database=db,
                            dbtype='MySQL')
        
        if self.__list.has_connection(id):    
            self.__list.set_connection(id,conn)
        else:
            if conn.id == -1:
                conn.id = self.__list.get_fresh_id()
            self.__list.add_connection(conn)
        key = str(conn.id) + "." + conn.name + "." + conn.host
        DBLocator.keyChain.set_key(key,passwd)
        return conn.id
    
    @staticmethod
    def from_link_file(filename):
        """from_link_file(filename: str) -> DBLocator
        This will parse a '.vtl' file and  will create a DBLocator. .vtl files
        are vistrail link files and they are used to point vistrails to open
        vistrails from the database on the web. """
        def convert_from_str(value,type):
            def bool_conv(x):
                s = str(x).upper()
                if s == 'TRUE':
                    return True
                if s == 'FALSE':
                    return False
            
            if value is not None:
                if type == 'str':
                    return str(value)
                elif value.strip() != '':
                    if type == 'long':
                        return long(value)
                    elif type == 'float':
                       return float(value)
                    elif type == 'int':
                        return int(value)
                    elif type == 'bool':
                        return bool_conv(value)
            return None
        tree = ElementTree.parse(filename)
        node = tree.getroot()
        if node.tag != 'vtlink':
            return None
        #read attributes
        data = node.get('host', None)
        host = convert_from_str(data, 'str')
        data = node.get('port', None)
        port = convert_from_str(data,'int')
        data = node.get('database', None)
        database = convert_from_str(data,'str')
        data = node.get('vtid')
        vt_id = convert_from_str(data, 'str')
        data = node.get('version')
        version = convert_from_str(data, 'str')
        data = node.get('tag')
        tag = convert_from_str(data, 'str')
        data = node.get('execute')
        execute = convert_from_str(data, 'bool')
        data = node.get('showSpreadsheetOnly')
        showSpreadsheetOnly = convert_from_str(data, 'bool')
        #asking to show only the spreadsheet force the workflow to be executed
        if showSpreadsheetOnly:
            execute = True
        try:
            version = int(version)
        except:
            tag = version
            pass
        if tag is None:
            tag = '';
        ## execute and showSpreadsheetOnly should be written to the current
        ## configuration
        config = get_vistrails_temp_configuration()
        config.executeWorkflows = execute
        config.showSpreadsheetOnly = showSpreadsheetOnly
        
        user = ""
        passwd = ""
            
        return DBLocator(host, port, database,
                         user, passwd, None, vt_id, None, None, version, tag)

    ##########################################################################

    def __eq__(self, other):
        if type(other) != type(self):
            return False
        return (self._host == other._host and
                self._port == other._port and
                self._db == other._db and
                self._user == other._user and
                self._name == other._name and
                self._obj_id == other._obj_id and
                self._obj_type == other._obj_type)

    ##########################################################################
        
    @staticmethod
    def load_from_gui(parent_widget, obj_type):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_load_db_locator_from_gui(parent_widget, obj_type)

    @staticmethod
    def save_from_gui(parent_widget, obj_type, locator=None):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_save_db_locator_from_gui(parent_widget, obj_type,
                                                   locator)

class ZIPFileLocator(_ZIPFileLocator, CoreLocator):

    def __init__(self, filename):
        _ZIPFileLocator.__init__(self, filename)
        
    def load(self, klass=None):
        from core.vistrail.vistrail import Vistrail
        if klass is None:
            klass = Vistrail
        obj = _ZIPFileLocator.load(self, klass.vtType)
        klass.convert(obj)
        obj.locator = self
        return obj

    def save(self, obj):
        klass = obj.__class__
        obj = _ZIPFileLocator.save(self, obj, False)
        klass.convert(obj)
        obj.locator = self
        return obj

    def save_as(self, obj):
        klass = obj.__class__
        obj = _ZIPFileLocator.save(self, obj, True)
        klass.convert(obj)
        obj.locator = self
        return obj

    ##########################################################################

    def __eq__(self, other):
        if type(other) != ZIPFileLocator:
            return False
        return self._name == other._name

    ##########################################################################

    @staticmethod
    def load_from_gui(parent_widget, obj_type):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_load_file_locator_from_gui(parent_widget, obj_type)

    @staticmethod
    def save_from_gui(parent_widget, obj_type, locator=None):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_save_file_locator_from_gui(parent_widget, obj_type,
                                                         locator)

class FileLocator(CoreLocator):
    def __new__(self, *args):
        if len(args) > 0:
            filename = args[0]
            if filename.endswith('.vt'):
                return ZIPFileLocator(filename)
            elif filename.endswith('.vtl'):
                return DBLocator.from_link_file(filename)
            else:
                return XMLFileLocator(filename)
        else:
            #return class based on default file type
            if vistrails_default_file_type() == '.vt':
                return ZIPFileLocator
            else:
                return XMLFileLocator
    
    @staticmethod
    def load_from_gui(parent_widget, obj_type):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_load_file_locator_from_gui(parent_widget, obj_type)

    @staticmethod
    def save_from_gui(parent_widget, obj_type, locator=None):
        import gui.extras.core.db.locator as db_gui
        return db_gui.get_save_file_locator_from_gui(parent_widget, obj_type,
                                                         locator)

    @staticmethod
    def parse(element):
        """ parse(element) -> XMLFileLocator
        Parse an XML object representing a locator and returns an
        XMLFileLocator or a ZIPFileLocator object.

        """
        if str(element.getAttribute('type')) == 'file':
            for n in element.childNodes:
                if n.localName == "name":
                    filename = str(n.firstChild.nodeValue).strip(" \n\t")
                    return FileLocator(filename)
            return None
        else:
            return None
    
    #ElementTree port
    @staticmethod
    def from_xml(node):
        """from_xml(node:ElementTree.Element) -> XMLFileLocator or None
        Parse an XML object representing a locator and returns a
        XMLFileLocator or a ZIPFileLocator object."""
        if node.tag != 'locator':
            return None
        type_ = node.get('type', '')
        if str(type_) == 'file':
            for child in node.getchildren():
                if child.tag == 'name':
                    filename = str(child.text).strip(" \n\t")
                    return FileLocator(filename)
        return None
        
def untitled_locator():
    basename = 'untitled' + vistrails_default_file_type()
    config = get_vistrails_configuration()
    if config:
        dot_vistrails = config.dotVistrails
    else:
        dot_vistrails = core.system.default_dot_vistrails()
    fullname = os.path.join(dot_vistrails, basename)
    return FileLocator(fullname)
