from pprint import pprint
import logging
import subprocess


from asmplayground import *
from runspec import run_cycle, link
import os


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

        if self.isa == 'x86':
            self.island_length = 11  # insert island length, the worst case
            self.island_head = 5  # length from island begin to landing pad, the worst case

    def get_tmp_label(self, info=''):

        self.tmp_label_count += 1
        return '.scfi_tmp%d%s' % (self.tmp_label_count, info)

    def is_control_transfer(self, line):
        if self.isa == 'x86':
            op = line.get_opcode()
            if not op:
                return False
            if 'ret' in op:
                return True
            if op.startswith('j'):
                return True
            if 'call' in op:
                return True
            return False

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
        return Line('\t.org ((.-0x%x-1)/(1<<%d)+1)*(1<<%d)+0x%x, 0x90 \t# pad to 0x%x, in width %d' %
                    (slot, bit_width, bit_width, slot, slot, bit_width))

    def padding_to_label(self, bit_width, label):
        return Line('\t.org ((.-(%s%%(1<<%d))-1)/(1<<%d)+1)*(1<<%d)+(%s%%(1<<%d)), 0x90 \t# pad to %s, in width %d' %
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
                    lines.append(Line('\tmovq\t%s, %%r11' % call_expr))
                    # tmp del lines.append(slot_line)
                    lines.append(Line('\tcallq \t*%r11'))
                    return lines

        raise Exception('Unsupported syntex or ISA')

    def set_branch_slot(self, line, slot):
        if self.isa == 'x86':
            if self.syntex == 'AT&T':
                if type == 'replace_8_bits':
                    line.replace('0x0', hex(slot))

    # used in "insert" moving
    # mark several lines as "pinned_island", insert them into codes, and modify the original label
    # they will "float" in the code, but always "pin" in the address
    # a normal form:
    # scfi_island_begin_target:
    #     jump island_end
    #     .org (padding to ...)
    # target:
    #     landding_pad
    #     jump scfi_real_target
    # scfi_island_end_target:
    def build_target_island(self, ori_line, padding_line):
        label = ori_line.get_label()
        modified_label = 'scfi_real_'+label
        ori_line.set_str(ori_line.replace(label, modified_label))

        lines = []
        lines.append(Line('scfi_island_begin_%s:' % label))
        lines.append(Line('\tjmp\tscfi_island_end_%s' % label))
        lines.append(padding_line)
        lines.append(Line('%s:' % label))
        lines.append(self.get_landing_pad_line())
        lines.append(Line('\tjmp\t%s' % modified_label))
        lines.append(Line('scfi_island_end_%s:' % label))

        setattr(lines[0], 'island_label', label)
        setattr(lines[0], 'island_end', lines[-1])
        setattr(lines[0], 'padding_line', padding_line)

        for line in lines:
            setattr(line, 'on_island', True)
        return lines


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
        self.branch_lst = []  # in order
        self.marked_branch_lst = []  # in order
        self.marked_target_lst = []
        self.valid_branch_tags = set()       # cfg contains more tags than our object
        self.valid_target_tags = set()
        self.tag_slot = dict()
        self.label_address = dict()
        self.label_size = dict()

        self.tmp_asm_path = '/tmp/scfi_tmp.s'
        self.tmp_obj_path = '/tmp/scfi_tmp.o'
        self.tmp_dmp_path = '/tmp/scfi_tmp.dump'

        self.update_debug_file_number(src_path)

        self.toolkit = ToolKit()

    def prepare_and_count(self):
        for line in self.traverse_lines():
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
        logger.info('valid branch tags: %d' % len(self.valid_branch_tags))
        logger.info('valid target tags: %d' % len(self.valid_target_tags))

    def mark_all_branches(self):
        for branch in self.branch_lst:
            if branch.debug_loc in self.cfg.branch.keys():
                setattr(branch, 'tags', self.cfg.branch[branch.debug_loc])
                self.marked_branch_lst.append(branch)
                for tag in self.cfg.branch[branch.debug_loc]:
                    self.valid_branch_tags.add(tag)

    def mark_all_targets(self):
        for line in self.label_list:
            label = line.get_label()
            if line.get_label() in self.cfg.target.keys():
                setattr(line, 'tags', self.cfg.target[label])
                self.marked_target_lst.append(line)
                for tag in self.cfg.target[label]:
                    self.valid_target_tags.add(tag)

    @property
    def inside_valid_tags(self):
        return self.valid_branch_tags.intersection(self.valid_target_tags)

    def cut_one_side_tags(self):
        logger.info('Cutting one side tags...')
        for target in self.marked_target_lst:
            target.tags = [
                i for i in target.tags if i in self.valid_branch_tags]
        old = len(self.marked_target_lst)
        self.marked_target_lst = [
            i for i in self.marked_target_lst if len(i.tags) > 0]
        new = len(self.marked_target_lst)
        logger.debug('Marked targets: %d -> %d' % (old, new))

        for branch in self.marked_branch_lst:
            branch.tags = [
                i for i in branch.tags if i in self.valid_target_tags]
        old = len(self.marked_branch_lst)
        self.marked_branch_lst = [
            i for i in self.marked_branch_lst if len(i.tags) > 0]
        new = len(self.marked_branch_lst)
        logger.debug('Marked branch: %d -> %d' % (old, new))

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
        logger.debug(cmd)
        p = subprocess.run(cmd, stderr=subprocess.PIPE, shell=True)
        logger.debug('end: '+cmd)
        compile_err = p.stderr.decode('utf-8')
        if compile_err:
            logger.warn(compile_err)
        if update_label:
            logger.info('updateing labels...')
            self.update_tmp_label_addresses()
        logger.info('Finish compile.')

    # return the function name the address in
    def function_hold_address(self, address):
        for function in self.label_size.keys():  # only functions have size
            if self.label_address[function] <= address and self.label_address[function]+self.label_size[function] >= address:
                return function
        return None

    # mark all basic blocks in a function, return all tmp labels
    def mark_function_basic_blocks(self, function_name):
        lines = self.get_function_lines(function_name)
        tmp_labels = []
        for line in lines:
            if self.toolkit.is_control_transfer(line):
                tmp_label = self.toolkit.get_tmp_label()
                self.insert_after(Line(tmp_label+':'),line)
        return tmp_labels

    def insert_island(self, island, target_label, slot=None, align_label=''):
        if not slot and not align_label:
            raise Exception("need a island align target")
        if not slot and align_label:
            slot = self.read_label_address(
                align_label) % (1 << self.slot_bit_width)

        insert_slot = (slot-self.toolkit.island_head) % (1 <<
                                                         self.slot_bit_width)
        ideal_place = target_label >> self.slot_bit_width << self.slot_bit_width
        ideal_place += insert_slot

        # TODO: do not affect former islands
        # if ideal_place > self.max_island_end: pass

        function_name = self.function_hold_address(ideal_place)
        if not function_name:
            # TODO: no place for the island
            raise Exception('No place for the island')
        tmp_labels = self.mark_function_basic_blocks(function_name)
        self.compile_tmp(update_label=True)
        max_label = function_name
        for tmp_label in tmp_labels:
            if self.label_address[tmp_label] < ideal_place and self.label_address[tmp_label] > self.label_address[function_name]:
                max_label = tmp_label

        self.insert_after(island, max_label)

    def update_tmp_label_addresses(self):
        cmd = ['readelf', '-s', self.tmp_obj_path]
        logger.debug(' '.join(cmd))
        output = subprocess.run(
            cmd, stdout=subprocess.PIPE).stdout.decode('utf-8')
        for line in output.split('\n'):
            try:
                info = line.split()
                label = info[-1]
                address = info[1]
                size = info[2]
                _type = info[3]
            except IndexError:
                continue
            if _type == 'FUNC':
                self.label_address[label] = int(address, 16)
                self.label_size[label] = int(size, 16 if '0x' in size else 10)
            if _type == 'NOTYPE':
                self.label_address[label] = int(address, 16)

    def read_label_address(self, label):
        return self.label_address[label]

    # only reorder target, not branches
    # use insert or padding
    # assumptions: targets are all (function) labels
    #              each branch has only one tag
    #              each target has only one tag
    def only_move_targets(self, move_method='padding'):
        # attributes set:
        # first_met_tags = first time met a tag, which means use it nature slot
        # met_tags = tags met already, which means use the slot equals to the first one
        logger.info('Only_move_targets, move method: %s' % move_method)
        self.cut_one_side_tags()

        need_move = []
        need_reprocessing_branches = []  # slot reserved
        need_reprocessing_targets = []  # slot reserved
        # modify all branches, and with slot reserved
        for line in self.marked_branch_lst:
            prev = line.prev
            self.unlink_line(line)
            for new_line in self.toolkit.modified_branch(line, type='replace_8_bits', reserved=True)[::-1]:
                if hasattr(new_line, 'reserved_tags'):
                    need_reprocessing_branches.append(new_line)
                self.insert_after(new_line, prev)

        allocated_tags = set()

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

        logger.debug('All instructions marked.')
        # until now all instructions are marked by:
        # branch: reserved_tags
        # target: reserved_tags, align_to

        logger.debug('Moving...')
        if move_method == 'padding':
            for line in need_move:
                if len(line.align_to_tags) > 1:
                    raise Exception('Not implemented')
                self.insert_before(self.toolkit.padding_to_label(
                    self.slot_bit_width, 'fsttag%s' % line.align_to_tags[0]), line)
                self.insert_after(self.toolkit.get_landing_pad_line(), line)
        elif move_method == 'insert':
            for line in need_move:
                logger.info('inserting...................................')
                if len(line.align_to_tags) > 1:
                    raise Exception('Not implemented')
                padding_line = self.toolkit.padding_to_label(
                    self.slot_bit_width, 'fsttag%s' % line.align_to_tags[0])
                island = self.toolkit.build_target_island(
                    line, padding_line=padding_line)
                self.insert_island(island, target_label=line.get_label,
                                   align_label='fsttag%s' % line.align_to_tags[0])
        else:
            raise Exception('Unknown move method %s' % move_method)

        # compile and get the slots
        self.compile_tmp()
        for tag in self.inside_valid_tags:
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
    name = '456.hmmer'
    filePath = '/home/readm/fast-cfi/workload/%s/work/fastcfi_final.s' % name
    src_path = '/home/readm/fast-cfi/workload/%s/work/' % name
    cfg_path = '/home/readm/fast-cfi/workload/%s/work/fastcfi.info' % name
    asm = SCFIAsm.read_file(filePath, src_path=src_path)
    asm.tmp_asm_path = src_path+'scfi_tmp.s'
    asm.tmp_obj_path = src_path+'scfi_tmp.o'
    asm.tmp_dmp_path = src_path+'scfi_tmp.dump'

    asm.prepare_and_count()
    asm.mark_all_instructions(cfg=CFG.read_from_llvm(cfg_path))
    asm.move_file_directives_forward()
    asm.only_move_targets(move_method='insert')
    os.chdir(src_path)
    asm.compile_tmp()
    link(asm.tmp_obj_path, src_path+'scfi_tmp')

    run_cycle(size='test', filelst=['./scfi_tmp'], lst=[name])
