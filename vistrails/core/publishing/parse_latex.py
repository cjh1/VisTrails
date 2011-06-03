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

from itertools import izip
import re

def parse_vt_command(opt_arg, arg):
    opt_dict = {}
    for opt_str in opt_arg[1:-1].split(','):
        opt_str = opt_str.strip()
        opt_list = opt_str.split('=',1)
        if len(opt_list) > 1:
            if opt_list[0].strip():
                opt_dict[opt_list[0]] = opt_list[1]
        else:
            if opt_list[0].strip():
                opt_dict[opt_list[0]] = None
    opt_dict['_args'] = arg[1:-1]
    return opt_dict

def build_vt_command(opt_dict):
    if '_args' in opt_dict:
        args = opt_dict['_args']
    else:
        args = ''
    opt_str = ''
    for k, v in opt_dict.iteritems():
        if k == '_args':
            continue
        if v is None:
            opt_str += '%s,\n' % k
        else:
            opt_str += '%s=%s,\n' % (k,v)
    if opt_str:
        full_str = "\\vistrail[%s]{%s}" % (opt_str, args)
    else:
        full_str = "\\vistrail{%s}" % args
    print '^^ LATEX ^^', opt_dict, full_str
    return full_str

def parse_latex_file(fname):
    # vt_begin_re = re.compile(r"% -- VISTRAILS BEGIN --")
    # vt_end_re = re.compile(r"% -- VISTRAILS END --")
    vt_begin_re = re.compile(r"^(?:(?:\\%)|[^%])*(\\vistrail[\[\{])")

    # we'll just assume balanced parens here...
    # vt_end_re = re.compile(r"\}")
    vt_bracket_re = re.compile(r"[\[\]]")
    vt_brace_re = re.compile(r"[\{\}]")
    f = open(fname)
    
    raw_text = [""]
    raw_idx = 0
    vt_text = []
    for line in f:
        m = vt_begin_re.search(line)
        if not m:
            raw_text[raw_idx] += line
        else:
            # print 'found:', m.start(1), m.end(1), line[m.end(1) - 1]

            # first end the current raw_text block
            raw_text[raw_idx] += line[:m.start(1)]
            raw_text.append("")
            raw_idx += 1

            cmd_text = ""
            # line = line[m.start(1):]
            line = line[m.end(1)-1:]

            # we'll just assume balanced parens here...
            if line[0] == '[':
                brackets_complete = False
                found_start = False
                brackets = 0
                while not brackets_complete:
                    for m in vt_bracket_re.finditer(line):
                        bracket_char = line[m.start()]
                        if bracket_char == '[':
                            brackets += 1
                            found_start = True
                        else:
                            brackets -= 1
                        if found_start and brackets == 0:
                            brackets_complete = True
                            cmd_text += line[:m.end()]
                            line = line[m.end():]
                            break
                    if brackets_complete:
                        break
                    cmd_text += line
                    line = f.next()
            
            opt_cmd_text = cmd_text
            cmd_text = ""
            braces_complete = False
            found_start = False
            braces = 0
            while not braces_complete:
                for m in vt_brace_re.finditer(line):
                    brace_char = line[m.start()]
                    if brace_char == '{':
                        braces += 1
                        found_start = True
                    else:
                        braces -= 1
                    if found_start and braces == 0:
                        braces_complete = True
                        cmd_text += line[:m.end()]
                        break
                if braces_complete:
                    break
                cmd_text += line
                line = f.next()
            # print cmd_text
            vt_text.append((opt_cmd_text,cmd_text))
            raw_text[raw_idx] += line[m.end():]
            
        # if vt_begin_re.search(line):
        #     line = f.next()
        #     while not vt_end_re.search(line):
        #         print line.strip()
        #         line = f.next()
    f.close()

    # vt_text.append(("", ""))
    for t, vt in izip(raw_text, vt_text + [("", "")]):
        print "RAW:", t
        print "VT:", parse_vt_command(*vt)
    return (raw_text, vt_text)

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print "Usage: %s %s <latex-file>" % (sys.executable, sys.argv[0])
        sys.exit(-1)
    
    parse_vt_file(sys.argv[1])