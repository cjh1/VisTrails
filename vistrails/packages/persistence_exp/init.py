############################################################################
##
## Copyright (C) 2006-2010 University of Utah. All rights reserved.
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
import os
import shutil
import tempfile
import uuid
try:
    import hashlib
    sha_hash = hashlib.sha1
except ImportError:
    import sha
    sha_hash = sha.new

from core.configuration import ConfigurationObject
from core.modules.basic_modules import Path, File, Directory, Boolean, \
    String, Constant
from core.modules.module_registry import get_module_registry, MissingModule, \
    MissingPackageVersion, MissingModuleVersion
from core.modules.vistrails_module import Module, ModuleError, NotCacheable
from core.system import default_dot_vistrails, execute_cmdline, systemType, \
    current_user, current_time
from core.upgradeworkflow import UpgradeWorkflowHandler, UpgradeWorkflowError
from compute_hash import compute_hash
from widgets import ManagedRefInlineWidget, ManagedInputFileConfiguration, \
    ManagedOutputFileConfiguration, ManagedInputDirConfiguration, \
    ManagedOutputDirConfiguration, ManagedRefModel
from db_utils import DatabaseAccessSingleton

global_db = None
local_db = None
search_dbs = None
db_access = None
compress_by_default = False
temp_persist_files = []

# FIXME add paths for git and tar...

class ManagedRef(Constant):

    # ref types
    ALWAYS_NEW = 0
    CREATE = 1
    EXISTING = 2
    
    def __init__(self):
        Constant.__init__(self)
        self.default_value = self
        
        self.type = ManagedRef.CREATE
        self.id = None
        self.version = None
        self.local_path = None
        self.local_read = False
        self.local_writeback = False
        self.versioned = False
        self.name = ''
        self.tags = ''

    @staticmethod
    def get_widget_class():
        return ManagedRefInlineWidget

    @staticmethod
    def translate_to_python(x):
        res = ManagedRef()
        s_tuple = eval(x)
        (res.type, res.id, res.version, res.local_path, res.local_read,
         res.local_writeback, res.versioned, res.name, res.tags) = s_tuple
#         result.settings = dict(zip(sorted(default_settings.iterkeys()),
#                                    s_tuple))
#         print 'from_string:', result.settings
        return res

    @staticmethod
    def translate_to_string(x):
        rep = str((x.type, x.id, x.version, x.local_path,
                   x.local_read, x.local_writeback, x.versioned,
                   x.name, x.tags))
        # rep = str(tuple(y[1] for y in sorted(x.settings.iteritems())))
        print 'to_string:', rep
        return rep
        
    @staticmethod
    def validate(x):
        return type(x) == ManagedRef

    _input_ports = [('value', 
                     '(edu.utah.sci.vistrails.persistence.exp:ManagedRef)')]
    _output_ports = [('value', 
                     '(edu.utah.sci.vistrails.persistence.exp:ManagedRef)')]

class ManagedPath(Module):
    def __init__(self):
        Module.__init__(self)

    def git_command(self):
        return ["cd", "%s" % local_db, "&&", "git"]

    def git_get_path(self, name, version="HEAD", path_type=None, 
                     out_name=None):
        if path_type is None:
            path_type = self.git_get_type(name, version)
        if path_type == 'tree':
            return self.git_get_dir(name, version, out_name)
        elif path_type == 'blob':
            return self.git_get_file(name, version, out_name)
        
        raise ModuleError(self, "Unknown path type '%s'" % path_type)

    def git_get_file(self, name, version="HEAD", out_fname=None):
        global temp_persist_files
        if out_fname is None:
            # create a temporary file
            (fd, out_fname) = tempfile.mkstemp(prefix='vt_persist')
            os.close(fd)
            temp_persist_files.append(out_fname)
            
        output = []
        cmd_line =  self.git_command() + ["show", str(version + ':' + name), 
                                          '>', out_fname]
        print 'executing command', cmd_line
        result = execute_cmdline(cmd_line, output)
        print output
        if result != 0:
            # check output for error messages
            raise ModuleError(self, "Error retrieving file '%s'\n" % name +
                              "\n".join(output))
        return out_fname

    def git_get_dir(self, name, version="HEAD", out_dirname=None):
        global temp_persist_files
        if out_dirname is None:
            # create a temporary directory
            out_dirname = tempfile.mkdtemp(prefix='vt_persist')
            temp_persist_files.append(out_dirname)
            
        output = []
        cmd_line = self.git_command() + ["archive", str(version + ':' + name), 
                                         '|', 'tar', '-C', out_dirname, '-xf-']
        print 'executing command', cmd_line
        result = execute_cmdline(cmd_line, output)
        print output
        if result != 0:
            # check output for error messages
            raise ModuleError(self, "Error retrieving file '%s'\n" % name +
                              "\n".join(output))
        return out_dirname

    def git_get_hash(self, name, version="HEAD"):
        output = []
        cmd_line = ["cd", "%s" % local_db, "&&", 
                    "echo", str(version + ':' + name), "|",
                    "git", "cat-file", "--batch-check"]
        print 'executing command', cmd_line
        result = execute_cmdline(cmd_line, output)
        print output
        if result != 0:
            # check output for error messages
            raise ModuleError(self, "Error retrieving file '%s'\n" % name +
                              "\n".join(output))
        return output[0].split()[0]

    def git_get_type(self, name, version="HEAD"):
        output = []
        cmd_line = ["cd", "%s" % local_db, "&&", 
                    "echo", str(version + ':' + name), "|",
                    "git", "cat-file", "--batch-check"]
        print 'executing command', cmd_line
        result = execute_cmdline(cmd_line, output)
        print output
        if result != 0:
            # check output for error messages
            raise ModuleError(self, "Error retrieving file '%s'" % name +
                              "\n".join(output))
        return output[0].split()[1]        

    def git_add_commit(self, filename):
        output = []
        cmd_line = self.git_command() + ['add', filename]
        print 'executing', cmd_line
        result = execute_cmdline(cmd_line, output)
        print output
        print '***'

        cmd_line = self.git_command() + ['commit', '-q', '-m', 
                                         'Updated %s' % filename]
        print 'executing', cmd_line
        result = execute_cmdline(cmd_line, output)
        print 'result:', result
        print output
        print '***'

        if len(output) > 1:
            # failed b/c file is the same
            # return 
            print 'got unexpected output'
            return None

        cmd_line = self.git_command() + ['log', '-1']
        print 'executing', cmd_line
        result = execute_cmdline(cmd_line, output)
        print output
        print '***'

        if output[0].startswith('commit'):
            return output[0].split()[1]
        return None

    def git_compute_hash(self, path, path_type=None):
        if path_type is None:
            if os.path.isdir(path):
                path_type = 'tree'
            elif os.path.isfile(path):
                path_type = 'blob'
        if path_type == 'tree':
            return self.git_compute_tree_hash(path)
        elif path_type == 'blob':
            return self.git_compute_file_hash(path)
        
        raise ModuleError(self, "Unknown path type '%s'" % path_type)
        

    def git_compute_file_hash(self, filename):
        # run git hash-object filename
        output = []
        cmd_line = self.git_command() + ['hash-object', filename]
        print 'executing', cmd_line
        result = execute_cmdline(cmd_line, output)
        print 'result:', result
        print output
        print '***'

        if result != 0:
            raise ModuleError(self, "Error retrieving file '%s'\n" % filename +
                              "\n".join(output))
        return output[0].strip()

    def git_compute_tree_hash(self, dirname):
        lines = []
        for file in os.listdir(dirname):
            fname = os.path.join(dirname, file)
            if os.path.isdir(fname):
                hash = self.git_compute_tree_hash(fname)
                lines.append("040000 tree " + hash + '\t' + file)
            elif os.path.isfile(fname):
                hash = self.git_compute_file_hash(fname)
                lines.append("100644 blob " + hash + '\t' + file)

        (fd, tree_fname) = tempfile.mkstemp(prefix='vt_persist')
        os.close(fd)
        
        tree_f = open(tree_fname, 'w')
        for line in lines:
            print >>tree_f, line
        tree_f.close()

        output = []
        cmd_line = self.git_command() + ['mktree', '--missing', 
                                         '<', tree_fname]
        print 'executing', cmd_line
        result = execute_cmdline(cmd_line, output)
        print 'result:', result
        print output
        print '***'
        os.remove(tree_fname)
        if result != 0:
            raise ModuleError(self, "Error retrieving file '%s'\n" % dirname +
                              "\n".join(output))
        tree_hash = output[-1].strip()
        print 'hash:', tree_hash

        output = []
        cmd_line = self.git_command() + ['prune']
        print 'executing', cmd_line
        result = execute_cmdline(cmd_line, output)
        print 'result:', result
        print output
        print '***'
        
        return tree_hash

    def get_path_type(self, path):
        if os.path.isdir(path):
            return 'tree'
        elif os.path.isfile(path):
            return 'blob'            

    def copypath(self, src, dst, path_type=None):
        if path_type is None:
            path_type = self.get_path_type(src)

        if path_type == 'blob':
            shutil.copyfile(src, dst)
        elif path_type == 'tree':
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            raise ModuleError(self, "Unknown path type '%s'" % path_type)

    def set_result(self, path):
        persistent_path = Path()
        persistent_path.name = path
        persistent_path.setResult('value', self)
        persistent_path.upToDate = True
        self.setResult("value", persistent_path)

    def updateUpstream(self, is_input=None, path_type=None):
        global local_db, db_access

        if is_input is None:
            if not self.hasInputFromPort('value'):
                is_input = True
            else:
                # FIXME: check if the signature is the signature of
                # the value if so we know that it's an input...
                is_input = False

        self.persistent_ref = None
        self.persistent_path = None
        if not is_input:
            # can check updateUpstream
            if not hasattr(self, 'signature'):
                raise ModuleError(self, 'Module has no signature')
            if not self.hasInputFromPort('ref'):
                # create new reference with no name or tags
                ref = ManagedRef()
                ref.signature = self.signature
                print 'searching for signature', self.signature
                sig_ref = db_access.search_by_signature(self.signature)
                print 'sig_ref:', sig_ref
                if sig_ref:
                    print 'setting persistent_ref'
                    ref.id, ref.version = sig_ref
                    self.persistent_ref = ref
                    #             else:
                    #                 ref.id = uuid.uuid1()
            else:
                # update single port
                self.updateUpstreamPort('ref')
                ref = ManagedRef.translate_to_python(
                    self.getInputFromPort('ref'))
                if db_access.ref_exists(ref.id, ref.version):
                    signature = db_access.get_signature(ref.id, ref.version)
                    if signature == self.signature:
                        # need to create a new version
                        self.persistent_ref = ref

                # copy as normal
                # don't copy if equal

            # FIXME also need to check that the file actually exists here!
            if self.persistent_ref is not None:
                self.persistent_path = \
                    self.git_get_path(self.persistent_ref.id, 
                                      self.persistent_ref.version)
                print self.persistent_path
                print self.persistent_ref.local_path

        if self.persistent_ref is None or self.persistent_path is None:
            Module.updateUpstream(self)

    def compute(self, is_input=None, path_type=None):
        global db_access
        if not self.hasInputFromPort('value') and \
                not self.hasInputFromPort('ref'):
            raise ModuleError(self, "Need to specify path or reference")

        if self.persistent_path is not None:
            print 'using persistent path'
            ref = self.persistent_ref
            path = self.persistent_path            
        elif self.hasInputFromPort('ref'):
            ref = ManagedRef.translate_to_python(self.getInputFromPort('ref'))
            if ref.id is None:
                ref.id = str(uuid.uuid1())
        else:
            # create a new reference
            ref = ManagedRef()
            ref.id = str(uuid.uuid1())

        if is_input is None:
            is_input = False
            if not self.hasInputFromPort('value'):
                is_input = True
            else:
                if ref.local_path and ref.local_read:
                    print 'found local path with local read'
                    is_input = True
                # FIXME: check if the signature is the signature of
                # the value if so we know that it's an input...

        # if just reference, pull path from repository (get latest
        # version unless specified as specific version)
        if self.persistent_path is None and not self.hasInputFromPort('value') \
                and is_input and not (ref.local_path and ref.local_read):
            if ref.version:
                # get specific ref.uuid, ref.version combo
                path = self.git_get_path(ref.id, ref.version)
            else:
                # get specific ref.uuid path
                path = self.git_get_path(ref.id)
        elif self.persistent_path is None:
            # copy path to persistent directory with uuid as name
            if is_input and ref.local_path and ref.local_read:
                print 'using local_path'
                path = ref.local_path
            else:
                path = self.getInputFromPort('value').name
            new_hash = self.git_compute_hash(path, path_type)
            rep_path = os.path.join(local_db, ref.id)
            do_update = True
            if os.path.exists(rep_path):
                old_hash = self.git_get_hash(ref.id)
                print 'old_hash:', old_hash
                print 'new_hash:', new_hash
                if old_hash == new_hash:
                    do_update = False
                    
            if do_update:
                print 'doing update'
                self.copypath(path, os.path.join(local_db, ref.id))

                # commit (and add to) repository
                # get commit id as version id
                # persist object-hash, commit-version to repository
                version = self.git_add_commit(ref.id)
                
                # write object-hash, commit-version to provenance
                if is_input:
                    signature = new_hash
                else:
                    signature = self.signature
                db_access.write_database({'id': ref.id, 
                                          'name': ref.name, 
                                          'tags': ref.tags, 
                                          'user': current_user(),
                                          'date_created': current_time(),
                                          'date_modified': current_time(),
                                          'content_hash': new_hash,
                                          'version': version, 
                                          'signature': signature,
                                          'type': path_type})
            
        # if keep-local and path is different than the selected path, copy
        # the path to the keep-local path
        if ref.local_path and ref.local_writeback:
            if path != ref.local_path:
                self.copypath(path, ref.local_path)

        # for all paths
        self.set_result(path)

    _input_ports = [('value', '(edu.utah.sci.vistrails.basic:Path)'),
                    ('ref', '(edu.utah.sci.vistrails.basic:String)')]
    _output_ports = [('value', '(edu.utah.sci.vistrails.basic:Path)')]

class ManagedFile(ManagedPath):
    _input_ports = [('value', '(edu.utah.sci.vistrails.basic:File)')]
    _output_ports = [('value', '(edu.utah.sci.vistrails.basic:File)')]

    def set_result(self, path):
        persistent_path = File()
        persistent_path.name = path
        persistent_path.setResult('value', self)
        persistent_path.upToDate = True
        self.setResult("value", persistent_path)

class ManagedDir(ManagedPath):
    _input_ports = [('value', '(edu.utah.sci.vistrails.basic:Directory)')]
    _output_ports = [('value', '(edu.utah.sci.vistrails.basic:Directory)')]

    def updateUpstream(self, is_input=None):
        ManagedPath.updateUpstream(self, is_input, 'tree')

    def compute(self, is_input=None):
        ManagedPath.compute(self, is_input, 'tree')

    def set_result(self, path):
        persistent_path = Directory()
        persistent_path.name = path
        persistent_path.setResult('value', self)
        persistent_path.upToDate = True
        self.setResult("value", persistent_path)

class ManagedFile(ManagedPath):
    _input_ports = [('value', '(edu.utah.sci.vistrails.basic:File)')]
    _output_ports = [('value', '(edu.utah.sci.vistrails.basic:File)')]

    def updateUpstream(self, is_input=None):
        ManagedPath.updateUpstream(self, is_input, 'blob')

    def compute(self, is_input=None):
        ManagedPath.compute(self, is_input, 'blob')

    def set_result(self, path):
        persistent_path = File()
        persistent_path.name = path
        persistent_path.setResult('value', self)
        persistent_path.upToDate = True
        self.setResult("value", persistent_path)

class ManagedInputDir(ManagedDir):
    _input_ports = [('value', '(edu.utah.sci.vistrails.basic:Directory)', True)]

    def updateUpstream(self):
        ManagedDir.updateUpstream(self, True)

    def compute(self):
        ManagedDir.compute(self, True)
        
class ManagedIntermediateDir(ManagedDir):
    def updateUpstream(self):
        ManagedDir.updateUpstream(self, False)

    def compute(self):
        ManagedDir.compute(self, False)
    
class ManagedOutputDir(ManagedDir):
    _output_ports = [('value', '(edu.utah.sci.vistrails.basic:Directory)', 
                      True)]

    def updateUpstream(self):
        ManagedDir.updateUpstream(self, False)

    def compute(self):
        ManagedDir.compute(self, False)

class ManagedInputFile(ManagedFile):
    _input_ports = [('value', '(edu.utah.sci.vistrails.basic:File)', True)]

    def updateUpstream(self):
        ManagedFile.updateUpstream(self, True)

    def compute(self):
        ManagedFile.compute(self, True)
    
class ManagedIntermediateFile(ManagedFile):
    def updateUpstream(self):
        ManagedFile.updateUpstream(self, False)

    def compute(self):
        ManagedFile.compute(self, False)
    
class ManagedOutputFile(ManagedFile):
    _output_ports = [('value', '(edu.utah.sci.vistrails.basic:File)', True)]

    def updateUpstream(self):
        ManagedFile.updateUpstream(self, False)

    def compute(self):
        ManagedFile.compute(self, False)
    
def persistent_file_hasher(pipeline, module, constant_hasher_map={}):
    hasher = sha_hash()
    u = hasher.update
    u(module.name)
    u(module.package)
    u(module.namespace or '')
    # FIXME: Not true because File can be a function!
    # do not include functions here because they shouldn't change the
    # hashing of the persistent_file
    return hasher.digest()

# _modules = [(PersistentFile, {'signatureCallable': persistent_file_hasher})]
_modules = [ManagedRef, ManagedPath, ManagedFile, ManagedDir,
            (ManagedInputFile, {'configureWidgetType': \
                                    ManagedInputFileConfiguration}),
            (ManagedOutputFile, {'configureWidgetType': \
                                     ManagedOutputFileConfiguration}),
            (ManagedIntermediateFile, {'configureWidgetType': \
                                           ManagedOutputFileConfiguration}),
            (ManagedInputDir, {'configureWidgetType': \
                                   ManagedInputDirConfiguration}),
            (ManagedOutputDir, {'configureWidgetType': \
                                    ManagedOutputDirConfiguration}),
            (ManagedIntermediateDir, {'configureWidgetType': \
                                          ManagedOutputDirConfiguration}),]

def git_init(dir):
    output = []
    cmd = ["cd", "%s" % dir, "&&", "git", "init"]
    result = execute_cmdline(cmd, output)
    print 'init result', result
    print 'init output', output

def initialize():
    global global_db, local_db, search_dbs, compress_by_default, db_access

    if configuration.check('compress_by_default'):
        compress_by_default = configuration.compress_by_default
    if configuration.check('global_db'):
        global_db = configuration.global_db
    if configuration.check('local_db'):
        local_db = configuration.local_db
        if not os.path.exists(local_db):
            raise Exception('local_db "%s" does not exist' % local_db)
    else:
        local_db = os.path.join(default_dot_vistrails(), 'persistent_files2')
        if not os.path.exists(local_db):
            try:
                os.mkdir(local_db)
            except:
                raise Exception('local_db "%s" does not exist' % local_db)

    git_init(local_db)
    print 'creating DatabaseAccess'
    db_path = os.path.join(local_db, '.files.db')
    db_access = DatabaseAccessSingleton(db_path)
    print 'done', db_access
    
    search_dbs = [local_db,]
    if configuration.check('search_dbs'):
        try:
            check_paths = eval(configuration.search_dbs)
        except:
            print "*** persistence error: cannot parse search_dbs ***"
        for path in check_paths:
            if os.path.exists(path):
                search_dbs.append(path)
            else:
                print '*** persistence warning: cannot find path "%s"' % path

def finalize():
    # delete all temporary files/directories used by zip
    global temp_persist_files, db_access

    for fname in temp_persist_files:
        if os.path.isfile(fname):
            os.remove(fname)
        elif os.path.isdir(fname):
            shutil.rmtree(fname)
    db_access.finalize()

def handle_module_upgrade_request(controller, module_id, pipeline):
    reg = get_module_registry()
    module_remap = {'PerisistentFile': ManagedIntermediateFile,
                    'PersistentDirectory': ManagedIntermediateDir,
                    } # 'PersistentPath': ManagedIntermediatePath}
    function_remap = {'value': 'value',
                      'compress': None}
    src_port_remap = {'value': 'value',
                      'compress': None},
    dst_port_remap = {'value': 'value'}

    old_module = pipeline.modules[module_id]
    if old_module.name in module_remap:
        new_descriptor = reg.get_descriptor(module_remap[old_module.name])
        action_list = \
            UpgradeWorkflowHandler.replace_module(controller, pipeline,
                                                  module_id, new_descriptor,
                                                  function_remap,
                                                  src_port_remap,
                                                  dst_port_remap)
        return action_list

    return UpgradeWorkflowHandler.attempt_automatic_upgrade(controller, 
                                                            pipeline,
                                                            module_id)
    
def handle_missing_module(controller, module_id, pipeline):
    reg = get_module_registry()
    module_remap = {'PersistentFile': ManagedIntermediateFile,
                    'PersistentDirectory': ManagedIntermediateDir,
                    } # 'PersistentPath': ManagedIntermediatePath}
    function_remap = {'value': 'value',
                      'compress': None}
    src_port_remap = {'value': 'value',
                      'compress': None},
    dst_port_remap = {'value': 'value'}

    old_module = pipeline.modules[module_id]
    print 'running handle_missing_module', old_module.name
    if old_module.name in module_remap:
        print 'running through remamp'
        new_descriptor = reg.get_descriptor(module_remap[old_module.name])
        action_list = \
            UpgradeWorkflowHandler.replace_module(controller, pipeline,
                                                  module_id, new_descriptor,
                                                  function_remap,
                                                  src_port_remap,
                                                  dst_port_remap)
        print 'action_list', action_list
        return action_list

    return False

def handle_all_errors(controller, err_list, pipeline):
    new_actions = []
    print 'starting handle_all_errors'
    for err in err_list:
        print 'processing', err
        if isinstance(err, MissingModule):
            print 'got missing'
            actions = handle_missing_module(controller, err._module_id, 
                                            pipeline)
            if actions:
                new_actions.extend(actions)
        elif isinstance(err, MissingPackageVersion):
            print 'got package version change'
            actions = handle_module_upgrade_request(controller, err._module_id,
                                                    pipeline)
            if actions:
                new_actions.extend(actions)

    if len(new_actions) == 0:
        return None
    return new_actions