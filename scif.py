from pprint import pprint
from asmplayground import *

def is_indirect_call(line,language='x86_at&t'):
    # remember to add rules for more languages
    return True if line.is_instruction and 'call' in line and '*' in line else False

#TODO: support indirect jump
def is_indirect_jump(line,language='x86_at&t'):
    return False

def is_indirect_branch(line,language='x86_at&t'):
    return is_indirect_call(line,language='x86_at&t') or is_indirect_jump(line,language='x86_at&t')

class CFG():
    def __init__(self, target=dict(), branch=dict()):
        self.target=target # label-> [tags]
        self.branch=branch # debug loc -> [tags]
        # remember: the tags is in a list, we support multi tags
    
    @classmethod
    def read_from_llvm(cls,path):
        with open(path) as f:
            target, branch = dict(), dict()
            for line in f:
                line = line.strip()
                if line.startswith('FastCFI:callee'):
                    info=line.replace('FastCFI:callee=','').split('@')
                    target[info[0]]=[info[-1]]
                elif line.startswith('FastCFI:caller'):
                    info=line.replace('FastCFI:caller=','').split('@')
                    branch[info[0]]=[info[-1]]
            valid_tags=branch.values()
            for key in [k for k in target.keys()]:
                if target[key] not in valid_tags:
                    target.pop(key)
            return cls(target=target, branch=branch)
            
    
    # convert the string:y:z to x y z form
    def convert_filename_to_number(self, file_numbers):
        for branch_loc in [k for k in self.branch.keys()]:
            new_key = str(file_numbers[branch_loc.split(':')[0]])
            new_key += ' '+' '.join(branch_loc.split(':')[1:3])
            self.branch[new_key]=self.branch[branch_loc]
            self.branch.pop(branch_loc)



class SCFIAsm(AsmSrc):
    def __init__(self, s, cfg=CFG(), src_path=''):
        super().__init__(s)
        self.cfg=cfg
        self.slot_bit_width=8
        self.branch_lst=[]
        self.marked_branch_lst=[]
        self.marked_target_lst=[]
        self.update_debug_file_number(src_path)

    @property
    def cfi_info(self):
        info = \
            'slot bit width: %d\n' % self.slot_bit_width+\
            'icalls: %d\n' % len(self.branch_lst) +\
            'marked_icalls: %d\n' % len(self.marked_branch_lst) +\
            'marked_targets: %d\n' % len(self.marked_target_lst) +\
            'cfg_branches: %d\n' % len(self.cfg.branch.keys()) +\
            'cfg_targets: %d\n' % len(self.cfg.target.keys())
        return info

    
    def prepare_and_count(self):
        for line in self.lines:
            if is_indirect_branch(line): 
                self.branch_lst.append(line)

    def mark_all_instructions(self,cfg=None):
        if cfg: self.cfg=cfg
        self.cfg.convert_filename_to_number(self.debug_file_number)
        self.mark_all_branches()
        self.mark_all_targets()
    def mark_all_branches(self):
        for branch in self.branch_lst:
            if branch.debug_loc in self.cfg.branch.keys():
                setattr(branch,'tag',self.cfg.branch[branch.debug_loc])
                self.marked_branch_lst.append(branch)
    def mark_all_targets(self):
        for label in self.cfg.target.keys():
            if self.find_label(label):
                setattr(self.find_label(label),'tags',self.cfg.target[label])
                self.marked_target_lst.append(self.find_label(label))
    

if __name__ == '__main__':
    asm=SCFIAsm.read_file('./testcase/401.bzip.s',src_path='/home/readm/fast-cfi/401.bzip2/')
    asm.prepare_and_count()
    asm.mark_all_instructions(cfg=CFG.read_from_llvm('./testcase/cfg.txt'))
    print(asm.cfi_info)