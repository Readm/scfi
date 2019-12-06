# Read, modify and rewrite assembly files.
# Supproted modification:
#      Add line before/after a line
#      Move lines to a new location

#TODO:
# Move lines: cut into functions
#             cut function into basic blocks
# Move all file declaration to the begining
# Insert line

class Line(str):
    def __init__(self,s):
        super(Line, self).__init__()
        # self.type: 'empty' 'instruction' 'comment' 'directive' 'label'

        #TODO: we assume no /*...*/ comments, or we should remove them in AsmSrc.__init__
        if "/*" in self: raise Exception('Not supported comment')

        first_char = self.lstrip()[:1]
        last_char = self.strip_comment().rstrip()[-1:]
        if not first_char:
            self.type = 'empty'
        elif first_char=='#':
            self.type = 'comment'
        elif last_char==':':
            self.type = 'label'
        elif first_char=='.':
            self.type = 'directive'
        else:
            self.type = 'instruction'
        
        self.section_declaration=None
        self.moved=False

    def strip_comment(self):
        return self.split('#')[0]
    
    @property
    def is_empty(self): return self.type=='empty'
    
    @property
    def is_instruction(self): return self.type=='instruction'

    @property
    def is_comment(self): return self.type=='comment'

    @property
    def is_directive(self): return self.type=='directive'

    def get_directive_type(self): return self.strip().split()[0] if self.is_directive else None

    @property
    def is_label(self): return self.type=='label'

    @property
    def is_section_directive(self):
        return True if self.is_directive and self.get_directive_type() in ['.section','.data','.text'] else False
    
    @property
    def is_loc_directive(self):
        return True if self.is_directive and self.get_directive_type() == '.loc' else False
    
    @property
    def get_loc(self):
        return [int(x) for x in self.split()[1:4]]
    
    @property
    def is_file_directive(self):
        return True if self.is_directive and self.get_directive_type() == '.file' else False
    
    @property
    def is_debug_file_directive(self): # the .file has two version, old and DWARF2, we concern DWARF2 only.
        return True if self.is_file_directive and not self.strip_comment().split()[1].startswith('"') else False
    
    @property
    def set_section_declaration(self,line):
        self.section_declaration=line

class AsmSrc(str):
    def __init__(self,s):
        super(AsmSrc, self).__init__()
        self.lines=[Line(i) for i in self.split('\n')]

        self.debug_file=dict() # key: file value: number
        current_section=None
        for line in self.lines:
            # update file number
            if line.is_debug_file_directive: 
                file_num,file_str = line.split()[1], line.split()[2]
                self.debug_file[file_str.replace('"','')]=int(file_num)
            if line.is_section_directive:
                current_section=line
            elif line.is_instruction:
                line.set_section_declaration(current_section)

    @classmethod
    def read_file(cls,path):
        with open(path) as f:
            return cls(f.read())



if __name__=="__main__":
    asm=AsmSrc.read_file('./testcase/401.bzip.s')
    for line in asm.lines:
        if line.is_debug_file_directive: print(line)
    print(asm.debug_file)
        # print(line.type,line)# == 'instruction': print(line)