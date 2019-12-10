# Read, modify and rewrite assembly files.
# Supproted modification:
#      Add line before/after a line
#      Move lines to a new location

import logging
import subprocess
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SCFI')

class Line(str):
    key_id = 0  # we need a unique id for each Line, otherwise we cannot distinguish different line with the same content

    def __init__(self, s):
        super(Line, self).__init__()
        self._key_id = Line.key_id
        Line.key_id += 1
        self.index_cache=self._key_id
        # self.type: 'empty' 'instruction' 'comment' 'directive' 'label'

        # TODO: we assume no /*...*/ comments, or we should remove them in AsmSrc.__init__
        if "/*" in self:
            raise Exception('Not supported comment')

        first_char = self.lstrip()[:1]
        last_char = self.strip_comment().rstrip()[-1:]
        if not first_char:
            self.type = 'empty'
        elif first_char == '#':
            self.type = 'comment'
        elif last_char == ':':
            self.type = 'label'
        elif first_char == '.':
            self.type = 'directive'
        else:
            self.type = 'instruction'

        self.section_declaration = None
        self.moved = False

    def __eq__(self, other):
        if isinstance(other, Line):
            return other and self._key_id == other._key_id
        else:
            return super(Line, self).__eq__(other)
    def __hash__(self):
        return hash(str(self)+str(self._key_id))

    def strip_comment(self):
        return self.split('#')[0]

    @property
    def is_empty(self): return self.type == 'empty'

    @property
    def is_instruction(self): return self.type == 'instruction'

    @property
    def is_comment(self): return self.type == 'comment'

    @property
    def is_directive(self): return self.type == 'directive'

    def get_directive_type(self): return self.strip_comment().strip().split()[
        0] if self.is_directive else None

    @property
    def is_label(self): return self.type == 'label'

    def get_label(self): return self.strip_comment().strip().split()[
        0].replace(':', '') if self.is_label else None

    @property
    def is_section_directive(self):
        return True if self.is_directive and self.get_directive_type() in ['.section', '.data', '.text'] else False

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
        self.labels = dict()
        
        self.index_cache = dict() # for accelerate index_of_line

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
                current_section = line
            elif line.is_instruction:
                line.set_section_declaration(current_section)

            if line.is_directive and line.get_directive_type() == '.type':
                args = line.strip_comment().replace('.type', '').strip()
                function_name = args.split(',')[0].strip()
                self.functions.append(function_name)

            if line.is_label:
                self.labels[line.get_label()] = line

            if line.is_loc_directive:
                current_loc = line.get_loc
            elif line.is_instruction:
                line.set_loc(current_loc)

    def __str__(self):
        return '\n'.join(self.lines)

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
            logger.warn('label %s not found' % label)
            return None

    def index_of_line(self, line):
            index = line.index_cache
            if self.lines[index] == line: return index
            else:
                for index in range(len(self.lines)):
                    self.lines[index].index_cache = index
                    if self.lines[index]==line: return index
        # lines_hash = hash(str(self))
        # if lines_hash != self.lines_hash:
        #     self.lines_hash = lines_hash
        #     self.line_hash_index=dict()
        #     index = 0
        #     for l in self.lines:
        #         self.line_hash_index[(str(l),l._key_id)]=index
        #         if l == line: 
        #             self.last_found_index = index
        #             return index
        # else:
        #     try: 
        #         return self.line_hash_index[line]
        #     except KeyError:
        #         try:
        #             while True:
        #                 index = self.last_found_index + 1
        #                 if self.lines[index]== line:
        #                     self.last_found_index=index
        #                     return index
        #         except IndexError:
        #             raise IndexError

        #return self.lines.index(line)

    def insert_before(self, insert_line, before_line):
        self.lines.insert(self.index_of_line(before_line), insert_line)

    def insert_after(self, insert_line, after_line):
        self.lines.insert(self.index_of_line(after_line)+1, insert_line)

    # TODO: make moves faster: it calls index_of_line too many times
    def move_lines_before(self, line_lst, before_line):
        for line in line_lst:
            self.lines.remove(line)
        for line in line_lst:
            self.insert_before(line, before_line)

    def move_lines_after(self, line_lst, after_line):
        for line in line_lst:
            self.lines.remove(line)
        for line in line_lst:
            self.insert_after(line, after_line)

    def move_file_directives_forward(self):
        # move so that all .loc will not meet undeclared file
        last_index = 0
        for i in range(len(self.lines)):
            if self.lines[i].is_debug_file_directive:
                if not last_index:
                    last_index = i
                    continue
                if i > last_index+1:
                    self.lines.insert(last_index+1, self.lines.pop(i))
                last_index += 1

    def get_function_lines(self, function_name, speculate='clang debug'):
        # guess function beginning/ending is not reliable
        # so use arg speculate to use different speculate information
        if speculate == 'clang debug':
            begin_index = end_index = self.index_of_line(
                self.find_label(function_name))

            # find comment 'Begin function' first
            while '# -- Begin function' not in self.lines[begin_index]:
                begin_index -= 1
            # if before this line, it's a section declaration, include it
            if self.lines[begin_index-1].is_section_directive:
                begin_index -= 1

            # find comment 'End function'
            while '# -- End function' not in self.lines[end_index]:
                end_index += 1

            function = self.lines[begin_index:end_index+1]
            return function

    # move lines and repair the section declaration
    def move_function_before(self, lines, before_line):
        self.move_lines_before(lines, before_line)
        for line in lines:
            if line.is_section_directive:
                return  # exist a section declaration
            if line.is_instruction:
                self.insert_before(line.section_declaration, lines[0])

    def move_function_after(self, lines, after_line):
        self.move_lines_after(lines, after_line)
        for line in lines:
            if line.is_section_directive:
                return  # exist a section declaration
            if line.is_instruction:
                self.insert_before(line.section_declaration, lines[0])

    @classmethod
    def read_file(cls, path, src_path=''):
        with open(path) as f:
            asm = cls(f.read())
            asm.update_debug_file_number(src_path)
            return asm


if __name__ == "__main__":
    asm = AsmSrc.read_file('./testcase/401.bzip.s')
    for line in asm.lines:
        if line.is_instruction and 'call' in line:
            print(line)
