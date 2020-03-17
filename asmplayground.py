# Read, modify and rewrite assembly files.
# Supproted modification:
#      Add line before/after a line
#      Move lines to a new location

import logging
import subprocess
import copy
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SCFI')

X86 = 0
ARM = 1
RISCV = 2
ATT = 0
INTEL = 1


class Environment():
    def __init__(self, isa=X86, syntax=ATT):
        self.isa = X86
        self.syntax = ATT

    @property
    def comment_character(self):
        if self.isa == X86:
            return '#'
        if self.isa == ARM:
            return '@'


global_env = Environment(X86, ATT)


class Line(str):
    key_id = 0  # we need a unique id for each Line, otherwise we cannot distinguish different line with the same content

    def __init__(self, s):
        self._key_id = Line.key_id
        Line.key_id += 1
        # index_of_line is too slow, we add a two-way link list
        self.prev = None
        self.next = None
        # self.type: 'empty' 'instruction' 'comment' 'directive' 'label'
        # TODO: we assume no /*...*/ comments, or we should remove them in AsmSrc.__init__
        if "/*" in self:
            logger.warn('Not supported comment: /*...*/')

        first_char = self.lstrip()[:1]
        last_char = self.strip_comment().rstrip()[-1:]
        if not first_char:
            self.type = 'empty'
        elif first_char == global_env.comment_character:
            self.type = 'comment'
        elif last_char == ':':
            self.type = 'label'
        elif first_char == '.':
            self.type = 'directive'
        else:
            self.type = 'instruction'

        self.section_declaration = None
        self.new_str = None

    def __hash__(self):
        return hash(self._key_id)

    def __eq__(self, other):
        if isinstance(other, Line):
            return other and self._key_id == other._key_id
        else:
            return super(Line, self).__eq__(other)

    def set_str(self, s):
        self.new_str = s

    # TODO: fix it
    def __str__(self):
        if self.new_str != None:
            return str(self.new_str)
        return super().__str__()

    def strip_comment(self):
        return self.split(global_env.comment_character)[0]

    def get_opcode(self):
        if self.is_instruction:
            return self.split()[0]

    @property
    def is_empty(self): return self.type == 'empty'

    @property
    def is_instruction(self): return self.type == 'instruction'

    @property
    def is_comment(self): return self.type == 'comment'

    @property
    def is_directive(self): return self.type == 'directive'

    # with dot
    def get_directive_type(self): return self.strip_comment().strip().split()[
        0] if self.is_directive else None

    @property
    def is_label(self): return self.type == 'label'

    def get_label(self): return self.strip_comment().strip().split()[
        0].replace(':', '') if self.is_label else None

    @property
    def is_section_directive(self):
        return True if self.is_directive and self.get_directive_type() in ['.section', '.data', '.text'] else False

    def get_section(self):
        '''Return the section and the flags'''
        if not self.is_section_directive:
            return False
        if self.get_directive_type() in ['.data', '.text']:
            return self.get_directive_type()
        return self.split(None, 1)[-1].strip()
    
    def get_bare_section(self):
        '''Return the section name only'''
        return '.'+self.get_section().split(',',1)[0].split('.')[1]

    @property
    def is_loc_directive(self):
        return True if self.is_directive and self.get_directive_type() == '.loc' else False

    @property
    def get_loc(self):
        return ' '.join(self.split()[1:4])

    def set_loc(self, loc):
        self.debug_loc = loc

    @property
    def is_file_directive(self):
        return True if self.is_directive and self.get_directive_type() == '.file' else False

    @property
    # the .file has two version, old and DWARF2, we concern DWARF2 only.
    def is_debug_file_directive(self):
        return True if self.is_file_directive and not self.strip_comment().split()[1].startswith('"') else False

    def set_section_declaration(self, line):
        self.section_declaration = line


class AsmSrc(str):
    def __init__(self, s):
        super(AsmSrc, self).__init__()
        self.lines = [Line(i) for i in self.split('\n')]
        for index in range(len(self.lines)-1):
            self.lines[index].next = self.lines[index+1]
            self.lines[index+1].prev = self.lines[index]
        self.HEAD = self.lines[0]
        self.labels = dict()
        self.label_list = []  # in order
        self.section_lines = []

        self.functions = []   # name strings
        self.line_hash_index = dict()

        self.debug_file_number = dict()  # key: file value: number
        current_section = None
        current_loc = None
        for line in self.lines:
            # update file number
            if line.is_debug_file_directive:
                file_num, file_str = line.split()[1], line.split()[2]
                self.debug_file_number[file_str.replace(
                    '"', '')] = int(file_num)

            if line.is_section_directive:
                self.section_lines.append(line)
                current_section = line
            elif line.is_instruction:
                line.set_section_declaration(current_section)

            if line.is_directive and line.get_directive_type() == '.type':
                args = line.strip_comment().replace('.type', '').strip()
                function_name = args.split(',')[0].strip()
                self.functions.append(function_name)

            if line.is_label:
                line.set_section_declaration(current_section)
                self.label_list.append(line)
                self.labels[line.get_label()] = line

            if line.is_loc_directive:
                current_loc = line.get_loc
            elif line.is_instruction:
                line.set_loc(current_loc)

    def __str__(self):
        output = ''
        for line in self.traverse_lines():
            output += str(line)+'\n'
        return output

    def traverse_lines(self):
        p = self.HEAD
        while p.next != None:
            yield p
            p = p.next
        yield p

    def traverse_from(self, line):
        p = line
        while p.next != None:
            yield p
            p = p.next
        yield p

    def traverse_back_from(self, line):
        p = line
        while p.prev != None:
            yield p
            p = p.prev
        yield p

    def update_debug_file_number(self, path):
        # we add more keys to the debug_file_number to facilitate the mapping
        if not path:
            return
        for key in [k for k in self.debug_file_number.keys()]:
            new_key = key.replace(path, '')
            self.debug_file_number[new_key] = self.debug_file_number[key]
        for key in [k for k in self.debug_file_number.keys()]:
            if key.startswith('.'):
                new_key = key.replace('.', '')
                self.debug_file_number[new_key] = self.debug_file_number[key]

    def get_file_numbers(self):
        return self.debug_file_number

    def find_label(self, label):
        try:
            return self.labels[label]
        except KeyError:
            raise
            logger.debug('label %s not found' % label)
            return None

    def insert_before(self, insert_line, before_line):
        insert_line.next = before_line
        insert_line.prev = before_line.prev
        insert_line.prev.next = insert_line
        before_line.prev = insert_line

    def insert_after(self, insert_line, after_line):
        insert_line.prev = after_line
        insert_line.next = after_line.next
        insert_line.next.prev = insert_line
        after_line.next = insert_line

    def insert_lines_before(self, lines, before_line):
        for line in lines:
            self.insert_before(line, before_line)

    def insert_lines_after(self, lines, after_line):
        for line in lines[::-1]:
            self.insert_after(line, after_line)

    def unlink_line(self, line):
        line.prev.next = line.next
        line.next.prev = line.prev

    def del_line(self, line):
        del line

    def sort_lines(self, lines):
        new_lst = []
        for line in self.traverse_lines():
            if line in lines:
                new_lst.append(line)
        return new_lst

    def move_lines_before(self, line_lst, before_line):
        for line in line_lst:
            self.unlink_line(line)
        self.insert_lines_before(line_lst, before_line)

    def move_lines_after(self, line_lst, after_line):
        for line in line_lst:
            self.unlink_line(line)
        self.insert_lines_after(line_lst, after_line)

    def move_file_directives_forward(self):
        # move so that all .loc will not meet undeclared file
        last_one = None
        for line in self.traverse_lines():
            if line.is_debug_file_directive:
                if last_one and last_one.next != line:
                    self.unlink_line(line)
                    self.insert_after(line, last_one)
                last_one = line

    def get_function_lines(self, function_name, speculate='clang debug'):
        # guess function beginning/ending is not reliable
        # so use arg speculate to use different speculate information
        if speculate == 'clang debug':
            begin_line = end_line = self.find_label(function_name)

            # find comment 'Begin function' first
            while '# -- Begin function' not in begin_line:
                begin_line = begin_line.prev
            # if before this line, it's a section declaration, include it
            if begin_line.prev.is_section_directive:
                begin_line = begin_line.prev

            # find comment 'End function'
            while '# -- End function' not in end_line:
                end_line = end_line.next

            function = []
            p = begin_line
            while p != end_line.next:
                function.append(p)
                p = p.next
            return function

    # move lines and repair the section declaration
    def move_function_before(self, lines, before_line):
        self.move_lines_before(lines, before_line)
        for line in lines:
            if line.is_section_directive:
                return  # exist a section declaration
            if line.is_instruction:
                declare = copy.deepcopy(line.section_declaration)
                self.insert_before(declare, lines[0])

    def move_function_after(self, lines, after_line):
        self.move_lines_after(lines, after_line)
        for line in lines:
            if line.is_section_directive:
                return  # exist a section declaration
            if line.is_instruction:
                declare = copy.deepcopy(line.section_declaration)
                self.insert_before(declare, lines[0])

    def get_sections(self):
        return [line.get_section() for line in self.section_lines]

    @classmethod
    def read_file(cls, path, src_path=''):
        logger.info('Loading %s' % path)
        with open(path) as f:
            asm = cls(f.read())
            asm.update_debug_file_number(src_path)
            return asm
