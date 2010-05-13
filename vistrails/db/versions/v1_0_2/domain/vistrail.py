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

import copy
from auto_gen import DBVistrail as _DBVistrail
from auto_gen import DBAdd, DBChange, DBDelete, DBAbstraction, DBGroup, \
    DBModule
from id_scope import IdScope

class DBVistrail(_DBVistrail):
    def __init__(self, *args, **kwargs):
	_DBVistrail.__init__(self, *args, **kwargs)
        self.idScope = IdScope(remap={DBAdd.vtType: 'operation',
                                      DBChange.vtType: 'operation',
                                      DBDelete.vtType: 'operation',
                                      DBAbstraction.vtType: DBModule.vtType,
                                      DBGroup.vtType: DBModule.vtType})

        self.idScope.setBeginId('action', 1)
        self.db_objects = {}

        # keep a reference to the current logging information here
        self.db_log_filename = None
        self.log = None

    def __copy__(self):
        return DBVistrail.do_copy(self)

    def do_copy(self, new_ids=False, id_scope=None, id_remap=None):
        cp = _DBVistrail.do_copy(self, new_ids, id_scope, id_remap)
        cp.__class__ = DBVistrail
        
        cp.idScope = copy.copy(self.idScope)
        cp.db_objects = copy.copy(self.db_objects)
        cp.db_log_filename = self.db_log_filename
        if self.log is not None:
            cp.log = copy.copy(self.log)
        else:
            cp.log = None
        
        return cp

    @staticmethod
    def update_version(old_obj, trans_dict, new_obj=None):
        if new_obj is None:
            new_obj = DBVistrail()
        new_obj = _DBVistrail.update_version(old_obj, trans_dict, new_obj)
        new_obj.update_id_scope()
        if hasattr(old_obj, 'db_log_filename'):
            new_obj.db_log_filename = old_obj.db_log_filename
        if hasattr(old_obj, 'log'):
            new_obj.log = old_obj.log
        return new_obj

    def update_id_scope(self):
        def getOldObjId(operation):
            if operation.vtType == 'change':
                return operation.db_oldObjId
            return operation.db_objectId

        def getNewObjId(operation):
            if operation.vtType == 'change':
                return operation.db_newObjId
            return operation.db_objectId

        for action in self.db_actions:
            self.idScope.updateBeginId('action', action.db_id+1)
            if action.db_session is not None:
                self.idScope.updateBeginId('session', action.db_session + 1)
            for operation in action.db_operations:
                self.idScope.updateBeginId('operation', operation.db_id+1)
                if operation.vtType == 'add' or operation.vtType == 'change':
                    # update ids of data
                    self.idScope.updateBeginId(operation.db_what, 
                                               getNewObjId(operation)+1)
                    if operation.db_data is None:
                        if operation.vtType == 'change':
                            operation.db_objectId = operation.db_oldObjId
                    self.db_add_object(operation.db_data)
            for annotation in action.db_annotations:
                self.idScope.updateBeginId('annotation', annotation.db_id+1)
        
        for annotation in self.db_annotations:
            self.idScope.updateBeginId('annotation', annotation.db_id+1)
        for annotation in self.db_actionAnnotations:
            self.idScope.updateBeginId('actionAnnotation', annotation.db_id+1)

    def db_add_object(self, obj):
        self.db_objects[(obj.vtType, obj.db_id)] = obj

    def db_get_object(self, type, id):
        return self.db_objects.get((type, id), None)

    def db_update_object(self, obj, **kwargs):
        # want to swap out old object with a new version
        # need this for updating aliases...
        # hack it using setattr...
        real_obj = self.db_objects[(obj.vtType, obj.db_id)]
        for (k, v) in kwargs.iteritems():
            if hasattr(real_obj, k):
                setattr(real_obj, k, v)