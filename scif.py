from asmplayground import *
from pprint import pprint
import logging
import subprocess
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SCFI')


def is_indirect_call(line, language='x86_at&t'):
    # remember to add rules for more languages
    return True if line.is_instruction and 'call' in line and '*' in line else False

# TODO: support indirect jump


def is_indirect_jump(line, language='x86_at&t'):
    return False


def is_indirect_branch(line, language='x86_at&t'):
    return is_indirect_call(line, language='x86_at&t') or is_indirect_jump(line, language='x86_at&t')

# retrun a Line of .org


def padding_to_slot(bit_width, slot):
    return Line('\t.org ((.-0x%x-1)/(1<<%d)+1)*(1<<%d)+0x%x, 0x90 \t# pad to 0x%x, in width %d\n' %
                (slot, bit_width, bit_width, slot, slot, bit_width))


def padding_to_label(bit_width, label):
    return Line('\t.org ((.-(%s%%(1<<%d))-1)/(1<<%d)+1)*(1<<%d)+(%s%%(1<<%d)), 0x90 \t# pad to %s, in width %d\n' %
                (label, bit_width, bit_width, bit_width, label, bit_width, label, bit_width))

# Label based CFG, each target/branch has tags(labels)
# Tags can be strings, int ...
# For each target: keyed by label
# For each branch: keyed by debug_loc
# add new read function for new formats


class CFG():
    def __init__(self, target=dict(), branch=dict()):
        self.target = target  # label-> [tags]
        self.branch = branch  # debug loc -> [tags]
        # remember: the tags is in a list, we support multi tags

    @classmethod
    def read_from_llvm(cls, path):
        with open(path) as f:
            target, branch = dict(), dict()
            for line in f:
                line = line.strip()
                if line.startswith('FastCFI:callee'):
                    info = line.replace('FastCFI:callee=', '').split('@')
                    target[info[0]] = [info[-1]]
                elif line.startswith('FastCFI:caller'):
                    info = line.replace('FastCFI:caller=', '').split('@')
                    branch[info[0]] = [info[-1]]
            valid_tags = branch.values()
            for key in [k for k in target.keys()]:
                if target[key] not in valid_tags:
                    target.pop(key)
            return cls(target=target, branch=branch)

    # convert the string:y:z to x y z form

    def convert_filename_to_number(self, file_numbers):
        for branch_loc in [k for k in self.branch.keys()]:
            new_key = str(file_numbers[branch_loc.split(':')[0]])
            new_key += ' '+' '.join(branch_loc.split(':')[1:3])
            self.branch[new_key] = self.branch[branch_loc]
            self.branch.pop(branch_loc)


class SCFIAsm(AsmSrc):
    def __init__(self, s, cfg=CFG(), src_path=''):
        super().__init__(s)
        self.cfg = cfg
        self.slot_bit_width = 8
        self.branch_lst = []
        self.marked_branch_lst = []
        self.marked_target_lst = []
        self.valid_tags = set()       # cfg contains more tags than our object
        self.tag_slot = dict()

        self.tmp_asm_path = '/tmp/scfi_tmp.s'
        self.tmp_obj_path = '/tmp/scfi_tmp.o'
        self.tmp_dmp_path = '/tmp/scfi_tmp.dump'

        self.update_debug_file_number(src_path)

    def prepare_and_count(self):
        for line in self.lines:
            if is_indirect_branch(line):
                self.branch_lst.append(line)

    def mark_all_instructions(self, cfg=None):
        if cfg:
            self.cfg = cfg
        self.cfg.convert_filename_to_number(self.debug_file_number)
        self.mark_all_branches()
        self.mark_all_targets()
        logger.info('marked all instructions')
        logger.info('slot bit width: %d' % self.slot_bit_width)
        logger.info('icalls: %d' % len(self.branch_lst))
        logger.info('marked_icalls: %d' % len(self.marked_branch_lst))
        logger.info('marked_targets: %d' % len(self.marked_target_lst))
        logger.info('cfg_branches: %d' % len(self.cfg.branch.keys()))
        logger.info('cfg_targets: %d' % len(self.cfg.target.keys()))
        logger.info('valid tags: %d' % len(self.valid_tags))

    def mark_all_branches(self):
        for branch in self.branch_lst:
            if branch.debug_loc in self.cfg.branch.keys():
                setattr(branch, 'tags', self.cfg.branch[branch.debug_loc])
                self.marked_branch_lst.append(branch)
                for tag in self.cfg.branch[branch.debug_loc]:
                    self.valid_tags.add(tag)

    def mark_all_targets(self):
        for label in self.cfg.target.keys():
            if self.find_label(label):
                setattr(self.find_label(label), 'tags', self.cfg.target[label])
                self.marked_target_lst.append(self.find_label(label))
                for tag in self.cfg.target[label]:
                    self.valid_tags.add(tag)

    def random_slot_allocation(self):
        # use hash, this allocation requires no compile
        for target in self.marked_target_lst:
            slots = []
            for tag in target.tags:
                slot = hash(tag) & ((1 << self.slot_bit_width)-1)
                self.tag_slot[tag] = slot
                slots.append(slot)
            setattr(target, 'slots', slots)
        for branch in self.marked_branch_lst:
            slots = []
            for tag in branch.tags:
                slot = hash(tag) & ((1 << self.slot_bit_width)-1)
                self.tag_slot[tag] = slot
                slots.append(slot)
            setattr(target, 'slots', slots)
        for tag in self.tag_slot.keys():
            logger.debug('random_allocation:\t'+str(tag) +
                         ' -> \t'+hex(self.tag_slot[tag]))

    def compile_tmp(self, cmd=''):
        logger.info('compiling...')
        with open(self.tmp_asm_path, 'w') as f:
            f.write(self)
        if not cmd:
            cmd = 'as %s -o %s' % (self.tmp_asm_path, self.tmp_obj_path)
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
        p.wait()
        compile_err = p.stderr.read()
        if compile_err:
            raise Exception(compile_err)
        c = 'objdump -d %s > %s' % (self.tmp_obj_path, self.tmp_dmp_path)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        p.wait()
        logger.info('Finish compile.')


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    asm = SCFIAsm.read_file('./testcase/401.bzip.s',
                            src_path='/home/readm/fast-cfi/401.bzip2/')
    asm.prepare_and_count()
    asm.mark_all_instructions(cfg=CFG.read_from_llvm('./testcase/cfg.txt'))
    asm.random_slot_allocation()
    asm.move_file_directives_forward()
    for line in asm.lines:
        if line.is_debug_file_directive:
            print(line)
    # print(asm.cfi_info)
    # for line in asm.lines:
    #     if '.text' in line:
    #         pprint(line)
    #         pprint(asm.index_of_line(line))
