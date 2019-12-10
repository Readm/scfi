from pprint import pprint
import logging
import subprocess


from asmplayground import *
from runspec import run_cycle


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SCFI')

# attributes set:
# 'reserved_tags': we add the instruction with tags, but did not decide its slot
# 'tags', 'slots'

# language specified toolkits


class ToolKit():

    def __init__(self, isa='x86', syntex='AT&T', landing_pad='.byte 0xF3, 0x0F, 0x1E, 0xFA', landing_pad_len=4):
        self.isa = isa
        self.syntex = syntex
        self.landing_pad = landing_pad
        self.landing_pad_len = landing_pad_len
        self.tmp_label_count = 0

    def get_tmp_label(self, info=''):

        self.tmp_label_count += 1
        return '.scfi_tmp%d%s' % (self.tmp_label_count, info)

    def is_indirect_call(self, line):
        # remember to add rules for more languages
        if self.isa == 'x86':
            if self.syntex == 'AT&T':
                return True if line.is_instruction and 'call' in line and '*' in line else False
        raise Exception('Unsupported syntex or ISA')

    # TODO: support indirect jump
    def is_indirect_jump(self, line):
        return False

    def is_indirect_branch(self, line):
        return self.is_indirect_call(line) or self.is_indirect_jump(line)

    def get_call_expr(self, line):
        return line.strip_comment().split('*')[-1]

    # retrun a Line of .org
    def padding_to_slot(self, bit_width, slot):
        return Line('\t.org ((.-0x%x-1)/(1<<%d)+1)*(1<<%d)+0x%x, 0x90 \t# pad to 0x%x, in width %d\n' %
                    (slot, bit_width, bit_width, slot, slot, bit_width))

    def padding_to_label(self, bit_width, label):
        return Line('\t.org ((.-(%s%%(1<<%d))-1)/(1<<%d)+1)*(1<<%d)+(%s%%(1<<%d)), 0x90 \t# pad to %s, in width %d\n' %
                    (label, bit_width, bit_width, bit_width, label, bit_width, label, bit_width))

    def get_landing_pad_line(self):
        return Line('\t'+self.landing_pad)

    def jump_label(self, label):
        if self.isa == 'x86':
            if self.syntex == 'AT&T':
                return Line('\tjmp %s' % label)
        raise Exception('Unsupported syntex or ISA')

    def landing_and_jump(self, label):
        lines = []
        lines.append(self.get_landing_pad_line())
        lines.append(self.jump_label(label))
        return lines

    # a landing and jump, and skip them. used when in other codes
    def skipped_landing_and_jump(self, label):
        lines = []
        tmp_label = self.get_tmp_label()
        lines.append(self.jump_label(tmp_label))
        lines.append(self.landing_and_jump(label))
        lines.append(Line('%s:' % tmp_label))
        return lines

    # branch -> branch in CFI
    def modified_branch(self, line, type='', slot=[], reserved=True):
        lines = []
        if self.isa == 'x86':
            if self.syntex == 'AT&T':
                if type == 'replace_8_bits':
                    call_expr = self.get_call_expr(line)
                    if reserved:
                        slot_line = Line('\tmov\t$0x0, %r11b')
                        setattr(slot_line, 'reserved_tags', line.tags)
                    else:
                        slot_line = Line('\tmov\t$%s, %%r11b' % hex(slot[0]))
                        #setattr(slot_line, 'slot', slot)
                    lines.append(Line('\tmovq\t%s, %%rcx' % call_expr))
                    lines.append(slot_line)
                    lines.append(Line('\tcallq \t*%rcx'))
                    return lines

        raise Exception('Unsupported syntex or ISA')

    def set_branch_slot(self, line, slot):
        if self.isa == 'x86':
            if self.syntex == 'AT&T':
                if type == 'replace_8_bits':
                    line.replace('0x0', hex(slot))


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
        self.label_address = dict()
        self.label_size = dict()

        self.tmp_asm_path = '/tmp/scfi_tmp.s'
        self.tmp_obj_path = '/tmp/scfi_tmp.o'
        self.tmp_dmp_path = '/tmp/scfi_tmp.dump'

        self.update_debug_file_number(src_path)

        self.toolkit = ToolKit()

    def prepare_and_count(self):
        for line in self.lines:
            if self.toolkit.is_indirect_branch(line):
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

    def compile_tmp(self, cmd='', update_label=True):
        logger.info('compiling...')
        with open(self.tmp_asm_path, 'w') as f:
            f.write(str(self))
        if not cmd:
            cmd = 'as %s -o %s' % (self.tmp_asm_path, self.tmp_obj_path)
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
        p.wait()
        compile_err = p.stderr.read()
        if compile_err:
            raise Exception(compile_err)
        # cmd = 'objdump -d %s > %s' % (self.tmp_obj_path, self.tmp_dmp_path)
        # p = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
        # p.wait()
        # compile_err = p.stderr.read()
        # if compile_err:
        #     raise Exception(compile_err)
        if update_label:
            logger.info('updateing labels...')
            self.update_tmp_label_addresses()
        logger.info('Finish compile.')

    def update_tmp_label_addresses(self):
        cmd = 'readelf -s %s' % self.tmp_obj_path
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, shell=True)
        p.wait()
        compile_err = p.stderr.read()
        if compile_err:
            raise Exception(compile_err)
        output = p.stdout.readlines()
        for line in output:
            try:
                info = line.split()
                label = info[-1].decode('ascii')
                address = info[1]
                size = info[2]
                _type = info[3]
            except IndexError:
                continue
            if _type == b'FUNC':
                self.label_address[label] = int(address, 16)
                self.label_size[label] = int(size)
            if _type == b'NOTYPE':
                self.label_address[label] = int(address, 16)

    def read_label_address(self, label):
        return self.label_address[label]

    # only reorder target, not branches
    # use insert or padding
    # assumptions: targets are all (function) labels
    #              each branch has only one tag
    #              each target has only one tag
    def only_reorder_targets(self, move_method='padding'):
        # attributes set:
        # first_met_tags = first time met a tag, which means use it nature slot
        # met_tags = tags met already, which means use the slot equals to the first one

        need_move = []
        need_reprocessing_branches = []  # slot reserved
        need_reprocessing_targets = []  # slot reserved
        # modify all branches, and with slot reserved
        for line in self.marked_branch_lst:
            index = self.index_of_line(line)
            for new_line in self.toolkit.modified_branch(self.lines.pop(index), type='replace_8_bits', reserved=True)[::-1]:
                if hasattr(new_line, 'reserved_tags'):
                    need_reprocessing_branches.append(new_line)
                self.lines.insert(index, new_line)

        allocated_tags = set()

        self.marked_target_lst.sort(key=lambda x: self.index_of_line(x))
        for line in self.marked_target_lst:
            first_met_tags = []
            met_tags = []
            for tag in line.tags:
                if tag not in allocated_tags:
                    allocated_tags.add(tag)
                    first_met_tags.append(tag)
                else:
                    met_tags.append(tag)

            setattr(line, 'first_met_tags', first_met_tags)
            setattr(line, 'met_tags', met_tags)

            if not line.met_tags:  # all tags are un-allocated
                for tag in line.first_met_tags:
                    landing = self.toolkit.get_landing_pad_line()
                    setattr(landing, 'reserved_tags', [tag])
                    need_reprocessing_targets.append(landing)
                    self.insert_after(landing, line)
                    self.insert_after(Line('fsttag%s:' % str(tag)), line)
            else:  # has allocated tag
                if line.first_met_tags:  # has other un-allocated
                    raise Exception('Not implemented')
                elif len(line.met_tags) > 1:  # has multiple allocated tag
                    raise Exception('Not implemented')
                else:   # only one allocated tag
                    setattr(line, 'align_to_tags', line.met_tags)
                    need_move.append(line)

        # until now all instructions are marked by:
        # branch: reserved_tags
        # target: reserved_tags, align_to

        if move_method == 'padding':
            for line in need_move:
                if len(line.align_to_tags) > 1:
                    raise Exception('Not implemented')
                self.insert_after(self.toolkit.padding_to_label(
                    self.slot_bit_width, 'fsttag%s' % line.align_to_tags[0]), line)
                self.insert_after(self.toolkit.get_landing_pad_line(), line)

        # compile and get the slots
        self.compile_tmp()
        for tag in self.valid_tags:
            self.tag_slot[tag] = self.read_label_address(
                'fsttag%s' % str(tag)) & ((1 << self.slot_bit_width)-1)

        # update all slots
        for line in need_reprocessing_branches:
            self.toolkit.set_branch_slot(
                line, self.tag_slot[line.reserved_tags[0]])
        for line in need_reprocessing_targets:
            pass


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    name = '400.perlbench'
    filePath = '/home/readm/fast-cfi/workload/%s/work/fastcfi_final.s' % name
    src_path = '/home/readm/fast-cfi/workload/%s/work/' % name
    cfg_path = '/home/readm/fast-cfi/workload/%s/work/fastcfi.info' % name
    asm = SCFIAsm.read_file(filePath, src_path=src_path)
    asm.prepare_and_count()
    asm.mark_all_instructions(cfg=CFG.read_from_llvm(cfg_path))
    asm.move_file_directives_forward()
    asm.only_reorder_targets()
    asm.compile_tmp()
    run_cycle(lst=[name])
