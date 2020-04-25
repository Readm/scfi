from pprint import pprint
import logging
import subprocess


from asmplayground import *
from cfg import *
import os


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SCFI')

PADDING = 0
INSERT = 1
FSTMET = 2
DETERMIN = 3

# attributes set:
# 'reserved_tags': we add the instruction with tags, but did not decide its slot
# 'tags', 'slots'


class ToolKit():
    '''Language specified toolkits'''

    def __init__(self, landing_pad='.byte 0xF3, 0x0F, 0x1E, 0xFA', landing_pad_len=4):
        self.landing_pad = landing_pad
        self.landing_pad_len = landing_pad_len
        self.tmp_label_count = 0

        if global_env.isa == X86:
            self.trampo_length = 11  # insert trampo length, the worst case
            self.trampo_head = 5  # length from trampo begin to landing pad, the worst case

    def get_tmp_label(self, info=''):
        self.tmp_label_count += 1
        return '.scfi_tmp%d%s' % (self.tmp_label_count, info)

    def is_control_transfer(self, line):
        if global_env.isa == X86:
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
        else:
            raise Exception('Not implemented.')

    def is_indirect_call(self, line):
        # remember to add rules for more languages
        if global_env.isa == X86:
            if global_env.syntax == ATT:
                return True if line.is_instruction and 'call' in line and '*' in line else False
        raise Exception('Unsupported syntax or ISA')

    # TODO: support indirect jump
    def is_indirect_jump(self, line):
        return False

    def is_indirect_branch(self, line):
        return self.is_indirect_call(line) or self.is_indirect_jump(line)

    def get_call_expr(self, line):
        return line.strip_comment().split('*')[-1]

    # retrun a Line of .org
    def padding_to_slot(self, bit_width, slot):
        return PaddingLine.pad_to_slot(slot, bit_width)

    def padding_to_label(self, bit_width, label):
        return PaddingLine.pad_to_label(label, bit_width)

    def get_landing_pad_line(self):
        return Line('\t'+self.landing_pad)

    def jump_label(self, label):
        if global_env.isa == X86:
            if global_env.syntax == ATT:
                return Line('\tjmp %s' % label)
        raise Exception('Unsupported syntax or ISA')

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
    def modified_branch(self, line, type='', slots=[], slot_width=8, reserved=True):
        lines = []
        if global_env.isa == X86:
            if global_env.syntax == ATT:
                if type == 'replace_8_bits':
                    call_expr = self.get_call_expr(line)
                    if reserved:
                        slot_line = Line('\tmov\t$0x0, %r11b')
                        setattr(slot_line, 'reserved_tags', line.tags)
                    else:
                        slot_line = Line('\tmov\t$%s, %%r11b' % hex(slots[0]))
                        # setattr(slot_line, 'slot', slot)
                    lines.append(Line('\tmovq\t%s, %%r11' % call_expr))
                    lines.append(slot_line)
                    lines.append(Line('\tcallq \t*%r11'))
                    return lines
                if type == 'variable_width':
                    call_expr = self.get_call_expr(line)
                    slot_mask = 0xffffffffffffffff ^ ((1 << slot_width)-1)
                    if reserved:
                        slot_clear_line = Line(
                            '\tand\t$%s, %r11' % hex(slot_mask))
                        slot_write_line = Line('\tor\t$0x0, %r11')
                        setattr(slot_line, 'reserved_tags', line.tags)
                    else:
                        slot_clear_line = Line(
                            '\tand\t$%s, %%r11' % hex(slot_mask))
                        slot_write_line = Line(
                            '\tor\t$%s, %%r11' % hex(slots[0]))
                        # setattr(slot_line, 'slot', slot)
                    lines.append(Line('\tmovq\t%s, %%r11' % call_expr))
                    lines.append(slot_clear_line)
                    lines.append(slot_write_line)
                    lines.append(Line('\tcallq \t*%r11'))
                    return lines

        raise Exception('Unsupported syntax or ISA')

    def set_branch_slot(self, line, slot):
        if global_env.isa == X86:
            if global_env.syntax == ATT:
                if type == 'replace_8_bits':
                    line.replace('0x0', hex(slot))

    def padding_ID_lines(self, line, slots, IDs):
        '''Arrange slots and traditonal IDs before a multi-tag target'''
        pass

tk = ToolKit()


class PaddingLine(Line):
    def __init__(self, s, bit_width=8):
        super().__init__(s)
        self.bit_width = bit_width

    @classmethod
    def pad_to_label(cls, label, bit_width=8):
        return cls('\t.org ((.-(%s%%(1<<%d))-1)/(1<<%d)+1)*(1<<%d)+(%s%%(1<<%d)), 0x90 \t# pad to %s, in width %d' % (label, bit_width, bit_width, bit_width, label, bit_width, label, bit_width))

    @classmethod
    def pad_to_slot(cls, slot, bit_width=8):
        return cls('\t.org ((.-0x%x-1)/(1<<%d)+1)*(1<<%d)+0x%x, 0x90 \t# pad to 0x%x, in width %d' %
                   (slot, bit_width, bit_width, slot, slot, bit_width))

    @classmethod
    def pad_n(cls, n):
        return cls('\t.p2align\t%d, 0x90' % n)

class IDLine(Line):
    def __init__(self, s):
        super().__init__(s)

    @classmethod
    def get_ID_line(cls, value, offset):
        s = ''
        v = value
        for i in range(offset):
            s = hex(v & 0xff)+', '+s
            v = v >> 8
        return cls('\t.byte\t'+s[:-2]+'\t# scfi_tmp IDs')



class SLOT_INFO():
    def __init__(self, value, width, is_traditional):
        '''Single Slot:
        Bool is_traditional: if true, the slot is a traditional CFI ID, else, slot
        value: slot value/ ID value
        width:  slot width/ ID value offset
        Traditional offset:   ...3|2|1|0 + landing pad, each ID is one byte.
        '''
        self.value = value
        self.width = width
        self.is_traditional = is_traditional

    @property  # alias
    def offset(self): return self.width

    @classmethod
    def new_slot(cls, value, width):
        return cls(value, width, False)

    @classmethod
    def new_ID(cls, value, width):
        return cls(value, width, True)

    def build_prefix_line_and_branch(self, branch_line, skip_low_bit=0,debug=False,skip_lib=False,skip_trap=False):
        lines = []
        if self.is_traditional:
            if global_env.isa == X86:
                if global_env.syntax == ATT:
                    call_expr = tk.get_call_expr(branch_line)
                    lines.append(Line('\tmovq\t%s, %%r11' % call_expr))
                    if skip_lib:
                            lines.append(Line('\tcmpq\t $0xFFFFFFF,  %r11' ))
                            lines.append(Line('\tjge\t.+10'))
                    # lines.append(Line('\tsub\t$%s, %%r11' % str(self.width+1)))
                    lines.append(Line('\tcmpb\t $%s, -%d(%%r11)' % (hex(self.value),self.width+1)))
                    # lines.append(Line('\tadd\t$%s, %%r11' % str(self.width+1)))
                    lines.append(Line('\tje\t.+3'))
                    if skip_trap:
                        lines.append(Line('\tnop'))
                    else:
                        lines.append(Line('\tint3'))

                    lines.append(Line('\tcallq \t*%r11\t\t# scfi_call ID'))
                    return lines
            raise Exception('Unsupported syntax or ISA')
        else:
            slot_width=self.width+skip_low_bit
            slot_value = self.value<<skip_low_bit
            if global_env.isa == X86:
                if global_env.syntax == ATT:
                    call_expr = tk.get_call_expr(branch_line)
                    slot_mask = 0xffffffffffffffff ^ ((1 << slot_width)-1)
                    if debug:
                        tmp_reg = '%r10' if ('r11' in call_expr) else '%r11'
                        lines.append(Line('\tmovq\t%s, %s' % (call_expr,tmp_reg)))
                        # todo the offset 14 is not correct
                        # if skip_lib:
                        #     lines.append(Line('\tcmp\t $0xFFFFFFFF, %r11'))
                        #     lines.append(Line('\tjle\t.+14'))
                        # reserve slot
                        slot_clear_line = Line(
                            '\tand\t$%s, %s' % (hex((1 << slot_width)-1),tmp_reg))
                        lines.append(slot_clear_line)
                        lines.append(Line('\tcmp\t $%s, %s' % (slot_value,tmp_reg)))
                        lines.append(Line('\tje\t.+3'))
                        if skip_trap:
                            lines.append(Line('\tnop'))
                        else:
                            lines.append(Line('\tint3'))
                        # lines.append(Line('\tud2'))
                        lines.append(Line('\tcallq *%s\t\t# scfi_call slot debug' % call_expr))
                    else:
                        slot_mask = 0xffffffffffffffff ^ ((1 << slot_width)-1)
                        tmp_reg = '%r11'
                        if False:#'(' not in call_expr:
                            tmp_reg = call_expr
                        else:
                            lines.append(Line('\tmovq\t%s, %s' % (call_expr,tmp_reg)))
                        if skip_lib:
                                lines.append(Line('\tcmpq\t $0xFFFFFFF,  %s' % tmp_reg))
                                lines.append(Line('\tjge\t.+10'))
                        lines.append(Line('\tand\t$%s, %s' % (hex(slot_mask),tmp_reg)))
                        lines.append(Line('\tor\t$%s, %s' % (hex(slot_value),tmp_reg)))
                        lines.append(Line('\tcallq \t*%s\t# scfi_call slot' % tmp_reg))
                    return lines
            raise Exception('Unsupported syntax or ISA')


class SLOTS_INFO():
    def __init__(self, slots):
        '''Contains multiple SLOT_INFO'''
        self.slots = slots

    def get_max_align(self):
        max_align = 0
        for slot in self.slots:
            if not slot.is_traditional:
                max_align = max(max_align, slot.width)
        return max_align

    def build_prefix_line_and_label(self, label_line, skip_low_bit=0, debug=False):
        '''Build target prefix line and label based on the slot info. Output pattern:
        multi tag: |slot1 landingpad|...|slot2|.....|slot3|....|jump label|IDs|label|
        only one slot: padding|label|landingpad
        only IDs: IDs|label|landingpad
        '''
        if debug:
            offset_lst = [slot.offset for slot in self.slots if slot.is_traditional]
            if len(set(offset_lst))!=len(offset_lst):
                raise Exception("Same offset IDs.")

        # Build traditional ID prefix first
        tra_slots = [s for s in self.slots if s.is_traditional]
        tra_prefix = 0
        tra_prefix_width = 0
        for s in tra_slots:
            tra_prefix_width = max(tra_prefix_width, s.offset+1)
            tra_prefix ^= s.value << (s.offset*8)

        real_slot = [s for s in self.slots if not s.is_traditional]
        real_slot.sort(key=lambda x: x.width)

        # only IDs
        if not real_slot:
            return [
                IDLine.get_ID_line(tra_prefix, tra_prefix_width),
                label_line,
                tk.get_landing_pad_line()
            ]

        # get first slot
        start = real_slot.pop()
        self.tmp_width = start.width
        self.min_value = start.value
        self.max_value = start.value+tk.landing_pad_len
        self.hit_set = set(range(self.min_value, self.max_value))

        slot_value=start.value<<skip_low_bit
        slot_width=start.width+skip_low_bit
        # if only one slot
        if not real_slot:
            # no IDs
            if not tra_prefix_width:
                return [
                    PaddingLine.pad_to_slot(slot_value, slot_width),
                    label_line,
                    tk.get_landing_pad_line()
                ]
            else:
                new_slot_value = (
                    slot_value - tra_prefix_width) % (1 << slot_width)
                return[
                    PaddingLine.pad_to_slot(new_slot_value, slot_width),
                    IDLine.get_ID_line(tra_prefix, tra_prefix_width),
                    label_line,
                    tk.get_landing_pad_line()
                ]

        raise Exception('Multi Real Slot!')


class SCFIAsm(AsmSrc):
    def __init__(self, s, cfg=CFG(), src_path=''):
        super().__init__(s)
        self.cfg = cfg
        self.default_fixed_slot_bit_width = 8
        self.max_slot_length = 0 # for huffman-encoding
        self.max_padding_slot_width = 6  # for padding/trampoline
        self.max_variable_slot_bit_width = 10
        self.slot_type = 'variable_width'  # or replace_8_bit

        self.branch_lst = []  # in order
        self.marked_branch_lst = []  # in order
        self.marked_target_lst = []

        self.valid_branch_tags = set()    # since cfg contains more tags than our object
        self.valid_target_tags = set()

        self.both_valid_tag = set()  # after cutting one side tags, the tags remained

        self.tag_slot = dict()     # tag->SLOT_INFO

        self.tag_branch_count = dict()
        self.tag_target = dict()  # tag-> target with this tag
        self.tag_count = dict()

        self.label_address = dict()
        self.label_size = dict()

        self.tmp_asm_path = '/tmp/scfi_tmp.s'
        self.tmp_obj_path = '/tmp/scfi_tmp.o'
        self.tmp_dmp_path = '/tmp/scfi_tmp.dump'
        self.tmp_lds_path = '/tmp/scfi_tmp.lds'

        self.section_align = dict() # record the max alignment for each section

        self.update_debug_file_number(src_path)

        self.toolkit = ToolKit()

        self.max_slot_address = 0 # for inserting trampoline

    def mark_all_instructions(self, cfg=None):
        '''Add "tags" for all targets and branches'''
        for line in self.traverse_lines():
            if self.toolkit.is_indirect_branch(line):
                self.branch_lst.append(line)
        if cfg:
            self.cfg = cfg
        self.cfg.convert_filename_to_number(self.debug_file_number)
        self.mark_all_branches()
        self.mark_all_targets()
        logger.info('marked all instructions')
        logger.info('default slot bit width: %d' %
                    self.default_fixed_slot_bit_width)
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
                    try:
                        self.tag_branch_count[tag] += 1
                    except KeyError:
                        self.tag_branch_count[tag] = 1
                    try:
                        self.tag_count[tag] += 1
                    except KeyError:
                        self.tag_count[tag] = 1

    def tag_target_count(self, tag):
        return len(self.tag_target[tag])

    def mark_all_targets(self):
        for line in self.label_list:
            label = line.get_label()
            if line.get_label() in self.cfg.target.keys():
                setattr(line, 'tags', self.cfg.target[label])
                self.marked_target_lst.append(line)
                for tag in self.cfg.target[label]:
                    self.valid_target_tags.add(tag)
                    try:
                        self.tag_target[tag].add(line)
                    except KeyError:
                        self.tag_target[tag] = set([line])
                    try:
                        self.tag_count[tag] += 1
                    except KeyError:
                        self.tag_count[tag] = 1

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
        self.both_valid_tag = {
            t for t in self.valid_branch_tags if t in self.valid_target_tags}

    def random_slot_allocation(self):
        '''Fixed slot bit width. Use hash, this allocation requires no compile'''
        for target in self.marked_target_lst:
            slots = []
            for tag in target.tags:
                slot = hash(tag) & ((1 << self.default_fixed_slot_bit_width)-1)
                self.tag_slot[tag] = (slot, self.default_fixed_slot_bit_width)
                slots.append(slot)
            setattr(target, 'slots', slots)
        for branch in self.marked_branch_lst:
            slots = []
            for tag in branch.tags:
                slot = hash(tag) & ((1 << self.default_fixed_slot_bit_width)-1)
                self.tag_slot[tag] = (slot, self.default_fixed_slot_bit_width)
                slots.append(slot)
            setattr(target, 'slots', slots)
        for tag in self.tag_slot.keys():
            logger.debug('random_allocation:\t'+str(tag) +
                         ' -> \t'+hex(self.tag_slot[tag][0]))

    def huffman_slot_allocation(self, source='target'):
        '''use huffman coding encode all labels'''
        from huffmanx import codebook
        if source == 'target':
            code = codebook([(tag, self.tag_target_count(tag))
                             for tag in self.valid_target_tags],
                            weight_fun=lambda x, y: 2*(x+y))
        elif source == 'branch':
            code = codebook([(tag, self.tag_branch_count[tag])
                             for tag in self.valid_target_tags],
                            weight_fun=lambda x, y: 2*(x+y))
        elif source == 'both':
            code = codebook([(tag, self.tag_count[tag])
                             for tag in self.valid_target_tags],
                            weight_fun=lambda x, y: 2*(x+y))
        else:
            raise Exception('Wrong source for huffman slot allocation.')
        for key in code.keys():
            if len(code[key]) > self.max_variable_slot_bit_width:
                code[key] = code[key][:self.max_variable_slot_bit_width]
            self.tag_slot[key] = (int(code[key], 2), len(code[key]))
            logger.debug("tag %s \t-> %s \t%x(%dbits)" %
                         (key, code[key], int(code[key], 2), len(code[key])))

    def compile_tmp(self, cmd='', update_label=True):
        logger.info('compiling...')
        with open(self.tmp_asm_path, 'w') as f:
            f.writelines((str(i)+'\n' for i in self.traverse_lines()))
        if not cmd:
            cmd = 'as %s -o %s' % (self.tmp_asm_path, self.tmp_obj_path)
        logger.debug(cmd)
        p = subprocess.run(cmd, stderr=subprocess.PIPE, shell=True)
        logger.debug('end: '+cmd)
        compile_err = p.stderr.decode('utf-8')
        if compile_err:
            if 'Error:' in compile_err:
                raise Exception(compile_err)
            logger.warn(compile_err)
        if update_label:
            logger.info('updateing labels...')
            self.update_tmp_label_addresses()
        logger.info('Finish compile.')

    def function_hold_address(self, address):
        '''return the function name the address in'''
        for function in self.label_size.keys():  # only functions have size
            if self.label_address[function] <= address and self.label_address[function]+self.label_size[function] >= address:
                return function
        return None

    def mark_function_basic_blocks(self, function_name):
        '''mark all basic blocks in a function, return all tmp labels'''
        lines = self.get_function_lines(function_name)
        tmp_labels = []
        for line in lines:
            if self.toolkit.is_control_transfer(line):
                tmp_label = Line(self.toolkit.get_tmp_label()+':')
                self.insert_after(tmp_label, line)
                tmp_labels.append(tmp_label)
        return tmp_labels

    def mark_all_basic_blocks(self):
        tmp_labels = []
        for line in self.traverse_lines():
            if self.toolkit.is_control_transfer(line):
                tmp_label = Line(self.toolkit.get_tmp_label()+':')
                self.insert_after(tmp_label, line)
                tmp_labels.append(tmp_label)
        self.basic_block_labels = tmp_labels

    def build_target_trampo(self, ori_line, padding_line):
        '''used in "insert" moving
        mark several lines as "pinned_trampo", insert them into codes, and modify the original label
        they will "float" in the code, but always "pin" in the address
        a normal form:
        SCFIIBtarget:
            jump trampo_end
            .org (padding to ...)
        target:
            landding_pad
            jump .Rtarget
        SCFIIEtarget:'''
        label = ori_line.get_label()
        modified_label = '.scfi_real_'+label
        ori_line.set_str(ori_line.replace(label, modified_label))

        lines = []
        lines.append(Line('.scfi_ib_%s:' % label))
        lines.append(Line('\tjmp\t.scfi_ie_%s' % label))
        lines.append(padding_line)
        l = Line('%s:' % label)
        setattr(l, 'ori_label_line', True)
        lines.append(l)
        lines.append(self.toolkit.get_landing_pad_line())
        lines.append(Line('\tjmp\t%s' % modified_label))
        lines.append(Line('.scfi_ie_%s:' % label))

        setattr(lines[0], 'trampo_label', label)
        setattr(lines[0], 'trampo_end', lines[-1])
        setattr(lines[0], 'padding_line', padding_line)

        # fix .size
        for line in self.traverse_from(ori_line):
            if line.is_directive:
                if '.size' == line.get_directive_type():
                    line.set_str(line.replace(label, modified_label))
                    break

        for line in self.traverse_back_from(ori_line):
            if line.is_directive:
                if '.type' == line.get_directive_type():
                    line.set_str(line.replace(label, modified_label))
                    break

        for line in lines:
            setattr(line, 'on_trampo', True)
        return lines

    def insert_ideal_place(self, target_label, width, slot=None, align_label=''):
        target_label = '.scfi_real_'+target_label
        if not (bool(slot != None) ^ bool(align_label)):
            raise Exception(
                "Need ONE trampo align target")
        if align_label:
            slot = self.read_label_address(
                align_label) % (1 << width)
        insert_slot = (slot-self.toolkit.trampo_head) % (1 <<
                                                         width)
        ideal_place = self.label_address[target_label] >> width << width
        ideal_place += insert_slot
        if ideal_place < self.label_address[target_label]:
            ideal_place += 1 << width
        return ideal_place

    def insert_trampo(self, trampo, search_begin, ideal_place, width):
        '''Insert trampo into a place, first try the ideal_place, from search_begin'''
        last_label = None
        for tmp_label in self.basic_block_labels:
            address = self.label_address[tmp_label.get_label()]
            if address < search_begin:
                continue
            if address > ideal_place:
                break
            last_label = tmp_label

        logger.debug('ideal place \t%x' % ideal_place)
        if not last_label:
            self.insert_trampo(trampo, search_begin, ideal_place +
                               (1 << width), width)
        # or address < self.max_slot_address:
        elif hasattr(last_label.next, 'on_trampo'):
            address = self.label_address[last_label.get_label()]
            self.insert_trampo(trampo, search_begin, ideal_place +
                               (1 << width), width)
        else:
            address = self.label_address[last_label.get_label()]
            self.max_slot_address = max(self.max_slot_address, address)
            logger.debug('final place \t%x' % address)
            # record where it should be
            setattr(trampo[0], 'placed_address', address)
            self.insert_lines_after(trampo, last_label)

    # not tested yet
    def fix_trampo_address(self, trampo):
        begin_label = trampo[0].get_label()
        address = self.label_address[begin_label]
        right_address = trampo[0].placed_address
        # > (1 << (self.default_fixed_slot_bit_width-1)):  # need fix
        if address-right_address:
            logger.debug('Fixing')
            for line in trampo:
                if hasattr(line, 'ori_label_line'):
                    continue
                self.unlink_line(line)
            self.compile_tmp(update_label=True)
            for line in trampo:
                if not hasattr(line, 'ori_label_line'):
                    continue
                self.unlink_line(line)
            self.insert_trampo(trampo, right_address -
                               (1 << self.default_fixed_slot_bit_width), address)

    def update_tmp_label_addresses(self):
        cmd = ['readelf', '-Ws', self.tmp_obj_path]
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

    # abandoned
    def only_move_targets(self, move_method=PADDING, slot_alloc=FSTMET, optimize_round=0):
        '''only reorder target, not branches
        use insert or padding
        slot_alloc: FSTMET (align to first met), DETERMIN (predetermined)
        assumptions: targets are all (function) labels
                    each branch has only one tag
                    each target has only one tag'''
        # attributes set:
        # first_met_tags = first time met a tag, which means use it nature slot
        # met_tags = tags met already, which means use the slot equals to the first one
        logger.info('Only_move_targets_nature, move method: %s, slot_alloc: %s' % (
            move_method, slot_alloc))
        self.cut_one_side_tags()

        need_move = []
        need_reprocessing_branches = []  # slot reserved
        need_reprocessing_targets = []  # slot reserved

        # modify all branches
        for line in self.marked_branch_lst:
            prev = line.prev
            self.unlink_line(line)
            if slot_alloc == FSTMET:
                for new_line in self.toolkit.modified_branch(line, type=self.slot_type, reserved=True)[::-1]:
                    if hasattr(new_line, 'reserved_tags'):
                        need_reprocessing_branches.append(new_line)
                    self.insert_after(new_line, prev)
            elif slot_alloc == DETERMIN:
                slots = [self.tag_slot[tag][0] for tag in line.tags]
                if len(slots) > 1:
                    raise Exception('Not implemented')
                slot_width = max([self.tag_slot[tag][1] for tag in line.tags])
                for new_line in self.toolkit.modified_branch(line, type=self.slot_type, reserved=False, slots=slots, slot_width=slot_width)[::-1]:
                    self.insert_after(new_line, prev)
            else:
                raise Exception("Unknown slot allocation.")

        # if use predetermined, we mark all tags allocated
        if slot_alloc == FSTMET:
            allocated_tags = set()
        elif slot_alloc == DETERMIN:
            allocated_tags = self.valid_target_tags

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
                    need_move.append(line)
                    if slot_alloc == FSTMET:
                        setattr(line, 'align_to_tags', line.met_tags)
                    elif slot_alloc == DETERMIN:
                        slots = [self.tag_slot[tag][0] for tag in line.tags]
                        slot_width = max([self.tag_slot[tag][1]
                                          for tag in line.tags])
                        setattr(line, 'slots', slots)
                        setattr(line, 'slot_width', slot_width)

        logger.debug('All instructions marked.')
        # in first met, until now all instructions are marked by:
        # branch: reserved_tags
        # target: reserved_tags, align_to
        # in predetermined, we do not need the marks

        logger.debug('Moving...')
        if move_method == PADDING:
            for line in need_move:
                if slot_alloc == FSTMET:
                    if len(line.align_to_tags) > 1:
                        raise Exception('Not implemented')
                    padding_line = self.toolkit.padding_to_label(
                        self.default_fixed_slot_bit_width, 'fsttag%s' % line.align_to_tags[0])
                elif slot_alloc == DETERMIN:
                    padding_line = self.toolkit.padding_to_slot(
                        line.slot_width, slot=line.slots[0])
                self.insert_before(padding_line, line)
                self.insert_after(self.toolkit.get_landing_pad_line(), line)

        elif move_method == INSERT:
            if need_move:
                self.mark_all_basic_blocks()
            line_to_trampo = dict()
            for line in need_move:
                if slot_alloc == FSTMET:
                    if len(line.align_to_tags) > 1:
                        raise Exception('Not implemented')
                    padding_line = self.toolkit.padding_to_label(
                        self.default_fixed_slot_bit_width, 'fsttag%s' % line.align_to_tags[0])
                elif slot_alloc == DETERMIN:
                    print(line+'use')
                    padding_line = self.toolkit.padding_to_slot(
                        line.slot_width, slot=line.slots[0])
                trampo = self.build_target_trampo(
                    line, padding_line=padding_line)
                line_to_trampo[line] = trampo
            move_lst = [x for x in need_move]
            while move_lst:
                logger.debug('Moving: %d/%d' %
                             (len(need_move)-len(move_lst), len(need_move)))
                self.compile_tmp()
                line_ideal_place = dict()
                for x in move_lst:
                    if slot_alloc == FSTMET:
                        line_ideal_place[x] = self.insert_ideal_place(
                            x.get_label(), align_label='fsttag%s' % x.align_to_tags[0])
                    elif slot_alloc == DETERMIN:
                        line_ideal_place[x] = self.insert_ideal_place(
                            x.get_label(), slot=line.slots[0])
                move_lst.sort(key=lambda x: line_ideal_place[x])
                search_begin = self.label_address['.scfi_real_' +
                                                  move_lst[0].get_label()]
                self.insert_trampo(
                    line_to_trampo[move_lst[0]], search_begin, line_ideal_place[move_lst[0]])
                logger.debug('insert:%s' % move_lst[0])
                move_lst.pop(0)
        else:
            raise Exception('Unknown move method %s' % move_method)

        # optimization
        for _ in range(optimize_round):
            logger.info('Optimizing...')
            self.compile_tmp()
            if move_method == PADDING:
                pass
            elif move_method == INSERT:
                for line in need_move:
                    self.fix_trampo_address(line_to_trampo[line])

        # compile and get the slots
        self.compile_tmp()
        if slot_alloc == FSTMET:
            for tag in self.inside_valid_tags:
                self.tag_slot[tag] = self.read_label_address(
                    'fsttag%s' % str(tag)) & ((1 << self.default_fixed_slot_bit_width)-1)

        # update all slots
        for line in need_reprocessing_branches:
            self.toolkit.set_branch_slot(
                line, self.tag_slot[line.reserved_tags[0]])
        for line in need_reprocessing_targets:
            pass

    def try_move_slot(self, tag, target_slot):  # todo
        return

    # mixed: padding (<threshold), trampline (>threshold), determined slot, single slot
    def move_targets_mix(self, trampline_threshold=6):
        logger.info(
            'Only_move_targets_nature, move method: mix, threshold: %d bit(s)' % trampline_threshold)
        self.cut_one_side_tags()

        need_move = []

        # modify all branches
        for line in self.marked_branch_lst:
            prev = line.prev
            self.unlink_line(line)
            slots = [self.tag_slot[tag][0] for tag in line.tags]
            if len(slots) > 1:
                raise Exception('Not implemented')
            slot_width = max([self.tag_slot[tag][1] for tag in line.tags])
            for new_line in self.toolkit.modified_branch(line, type=self.slot_type, reserved=False, slots=slots, slot_width=slot_width)[::-1]:
                self.insert_after(new_line, prev)

        allocated_tags = self.valid_target_tags

        for line in self.marked_target_lst:
            need_move.append(line)
            slots = [self.tag_slot[tag][0] for tag in line.tags]
            slot_width = max([self.tag_slot[tag][1]
                              for tag in line.tags])
            setattr(line, 'slots', slots)
            setattr(line, 'slot_width', slot_width)

        logger.debug('All instructions marked.')

        logger.debug('Moving...')
        if need_move:
            self.mark_all_basic_blocks()
        line_to_trampo = dict()

        need_insert = []
        for line in need_move:
            if line.slot_width <= trampline_threshold:
                padding_line = self.toolkit.padding_to_slot(
                    line.slot_width, slot=line.slots[0])
                self.insert_before(padding_line, line)
                self.insert_after(self.toolkit.get_landing_pad_line(), line)

            else:  # INSERT:
                need_insert.append(line)
                padding_line = self.toolkit.padding_to_slot(
                    line.slot_width, slot=line.slots[0])
                trampo = self.build_target_trampo(
                    line, padding_line=padding_line)
                line_to_trampo[line] = trampo

        total_target_num = len(need_move)
        padding_target_num = len(need_move)-len(need_insert)
        logger.info("Padding: %d (%02f%%), Trampoline: %d (%02f%%)" % (padding_target_num, padding_target_num /
                                                                       total_target_num * 100, total_target_num-padding_target_num, 100-(padding_target_num/total_target_num * 100)))

        while need_insert:
            logger.debug('Moving: %d/%d' %
                         (total_target_num-padding_target_num-len(need_insert)+1, total_target_num-padding_target_num))
            self.compile_tmp()
            line_ideal_place = dict()
            for x in need_insert:
                line_ideal_place[x] = self.insert_ideal_place(
                    x.get_label(), width=x.slot_width, slot=x.slots[0])
            need_insert.sort(key=lambda x: line_ideal_place[x])
            search_begin = self.label_address['.scfi_real_' +
                                              need_insert[0].get_label()]
            self.insert_trampo(
                line_to_trampo[need_insert[0]], search_begin, line_ideal_place[need_insert[0]], need_insert[0].slot_width)
            logger.debug('insert:%s' % need_insert[0])
            need_insert.pop(0)

        # compile and get the slots
        self.compile_tmp()

    # todo, it is not very common
    def remove_single_edge(self):
        return
        remove_tags = [
            tag for tag in self.both_valid_tag if self.tag_target_count(tag) == 1]
        print(len(remove_tags), '/', len(self.both_valid_tag))

    def new_lds(self):
        '''Ensure the alignment in ld script'''
        default_lds_path = '/home/readm/scfi/default.lds'
        if not self.section_align:  
            import shutil
            shutil.copy(default_lds_path, self.tmp_lds_path)

        unlikely_s, exit_s, startup_s, hot_s, other_s=[],[],[],[],[]
        for section_name in self.section_align.keys():
            align_width=self.section_align[section_name]
            if  align_width<=4: continue 
            if '.text' not in section_name:
                logger.warn('Try to change alignment of a non-text section: %s', section_name)
            align_value=1<<align_width
            align_line="    . = ALIGN(%s);\n" % hex(align_value)
            section_line="    *(%s)\n" % section_name
            current_set=None
            if 'unlikely' in section_name:
                current_set=unlikely_s
            elif '.text.exit' in section_name:
                current_set=exit_s
            elif '.text.startup' in section_name:
                current_set=startup_s
            elif '.text.hot' in section_name:
                current_set=hot_s
            else:
                current_set=other_s
            current_set.append(align_line)
            current_set.append(section_line)
        with open(default_lds_path) as fi:
            with open(self.tmp_lds_path,'w') as fo:
                for line in fi:
                    fo.write(line)
                    if 'SCFI insert mark' in line:
                        if '#unlikely#' in line:
                            fo.writelines(unlikely_s)
                        elif '#exit#' in line:
                            fo.writelines(exit_s)
                        elif '#startup#' in line:
                            fo.writelines(startup_s)
                        elif '#hot#' in line:
                            fo.writelines(hot_s)
                        elif '#default#' in line:
                            fo.writelines(other_s)


    def add_ID_fail(self):
        lines = [
            Line('__scfi_ID_fail:'),
            Line('\tud2')
        ]
        for line in self.traverse_lines():
            if line.get_directive_type() in ('.text', '.file'):
                continue
            self.insert_lines_before(lines, line)
            return

    @property
    def max_color(self):
        if not self.tag_color.values():
            return 0
        return max(self.tag_color.values())  # requires coloring first

    # TODO: branch number sort
    def coloring(self, runtime_first=True):
        '''Coloring: 0 stands for slot, 1,2,3 for IDs'''
        self.tag_color = dict()
        for tag in self.both_valid_tag:
            self.tag_color[tag] = 0
        current_max_color = 0

        if runtime_first:
            lambda_sort= lambda x: self.tag_branch_count[tag]
        else:
            lambda_sort= lambda x: self.tag_target_count(tag)
        sorted_lst = sorted([tag for tag in self.both_valid_tag],
                            key=lambda_sort, reverse=True)

        while True:
            this_round_changed = False
            for tag in sorted_lst:
                for target in self.tag_target[tag]:
                    if len(target.tags) > 1:
                        sorted_tags = sorted(
                            [tag for tag in target.tags], key=lambda_sort)
                        color_set = set()
                        for t in sorted_tags:
                            if self.tag_color[t] not in color_set:
                                color_set.add(self.tag_color[t])
                            else:
                                self.tag_color[t] = current_max_color+1
                                this_round_changed = True
            current_max_color += 1
            if not this_round_changed:
                break

        import collections
        logger.debug('Coloring first try (by tag):' +
                    str(collections.Counter([self.tag_color[v] for v in self.both_valid_tag])))

        lst = []
        for t in self.marked_target_lst:
            for tag in t.tags:
                lst.append(self.tag_color[tag])
        logger.debug('Coloring first try (by target):' + str(collections.Counter(lst)))

    def colored_IDs(self):
        '''After coloring, assign each tag a ID'''
        current_ID_of_color = dict()
        self.tag_id = dict()
        for tag in self.both_valid_tag:
            color = self.tag_color[tag]
            if color:
                if color in current_ID_of_color:
                    self.tag_id[tag] = current_ID_of_color[color]
                    current_ID_of_color[color] = current_ID_of_color[color]+1
                else:
                    self.tag_id[tag] = 0
                    current_ID_of_color[color] = 1

    def huffman_after_coloring(self, orthogonal=True, max_length=6, runtime_first=True):
        '''After Coloring, use huffman coding encode the color 0 (slots)
        If the max_length of coding > max_length, make a new color for them.
        After this, each marked branch has a "slot_info",each marked target has a "slots_info"'''
        from huffmanx import codebook
        if len(self.both_valid_tag) <= 1:
            return

        # get all colored in the huffman
        def get_input():
            _input = []
            colored_weight = 0
            colored_tag = set()
            for tag in self.both_valid_tag:
                if self.tag_color[tag] == 0:
                    _input.append((tag, self.tag_target_count(tag)))
                else:
                    colored_weight += self.tag_target_count(tag)
                    colored_tag.add(tag)
            if orthogonal and colored_weight:
                _input.append(('SCFI_COLORED', colored_weight))
            return _input

        code = codebook(get_input(), weight_fun=lambda x, y: 2*(x+y))
        logger.info("Huffman encoded after coloring (prepare): max length %d" % max(
            [len(x) for x in code.values()]))

        # if encoding too long
        if max([len(x) for x in code.values()]) > max_length:
            current_ID = 0
            first_color = self.max_color+1
            if not runtime_first:
                sorted_lst = sorted([t for t in self.both_valid_tag if self.tag_color[t]==0],
                                    key=lambda x: self.tag_target_count(x), reverse=True)
            else:
                sorted_lst = sorted([t for t in self.both_valid_tag if self.tag_color[t]==0],
                                    key=lambda x: self.tag_branch_count[x], reverse=True)
            while True:
                for _ in range(len(sorted_lst)//4):
                    tag = sorted_lst.pop()
                    self.tag_color[tag] = first_color+(current_ID//256)
                    self.tag_id[tag] = current_ID % 256
                    current_ID += 1
                code = codebook(get_input(), weight_fun=lambda x, y: 2*(x+y))
                logger.info("Huffman encoded after coloring (try): max length %d" % max(
                    [len(x) for x in code.values()]))
                if max([len(x) for x in code.values()]) <= max_length:
                    break
        
        # record a global max length
        self.max_slot_length = max([len(x) for x in code.values()])

        # count information
        import collections
        logger.info('Coloring (by tag):' +
                    str(collections.Counter([self.tag_color[v] for v in self.both_valid_tag])))

        lst = []
        for t in self.marked_target_lst:
            for tag in t.tags:
                lst.append(self.tag_color[tag])
        counts=collections.Counter(lst)
        logger.info('Coloring (by target):' + str(counts))

        # sort color number from more to less
        sorted_color=sorted([color for color in counts.keys() if color!=0],key= lambda x: counts[x],reverse=True)
        old_to_new=dict()
        for i in range(len(sorted_color)):
            old_to_new[sorted_color[i]]=i+1
        for tag in self.both_valid_tag:
            if self.tag_color[tag]: # skip 0
                self.tag_color[tag]=old_to_new[self.tag_color[tag]]


        lst = []
        for t in self.marked_target_lst:
            for tag in t.tags:
                lst.append(self.tag_color[tag])
        counts=collections.Counter(lst)
        logger.info('Sorted Coloring (by target):' + str(counts))


        color_slot = None  # slot info for colored
        max_color = self.max_color
        if orthogonal and 'SCFI_COLORED' in code.keys():
            color_slot = SLOT_INFO.new_slot(
                int(code['SCFI_COLORED'], 2), len(code['SCFI_COLORED']))
        for tag in self.both_valid_tag:
            if self.tag_color[tag]:
                self.tag_slot[tag] = SLOT_INFO.new_ID(
                    self.tag_id[tag], self.tag_color[tag])
            else:
                self.tag_slot[tag] = SLOT_INFO.new_slot(
                    int(code[tag], 2), len(code[tag]))

        for branch in self.marked_branch_lst:
            if len(branch.tags) > 1:
                raise Exception("not supported")
            setattr(branch, 'slot_info', self.tag_slot[branch.tags[0]])

        for target in self.marked_target_lst:
            setattr(target, 'slots_info', set([]))
            color_set = set([])
            for tag in target.tags:
                target.slots_info.add(self.tag_slot[tag])
                color_set.add(self.tag_color[tag])
            if orthogonal:
                for i in range(max_color+1):
                    if i in color_set:
                        continue  # has this identifier
                    if i == 0:  # has no slot
                        target.slots_info.add(color_slot)
                    else:
                        target.slots_info.add(SLOT_INFO.new_ID(0xFF, i))
            target.slots_info = SLOTS_INFO(target.slots_info)



    def branch_instrument(self,debug=False, skip_lib=False,skip_low_bit=0):
        for line in self.marked_branch_lst:
            next_line = line.next
            self.unlink_line(line)
            self.insert_lines_before(
                line.slot_info.build_prefix_line_and_branch(line,debug=debug, skip_lib=skip_lib, skip_low_bit=skip_low_bit), next_line)

    def target_instrument(self,skip_low_bit=0):
        if len(self.both_valid_tag) <= 1: # if no slot, only marks for landingpad
            for line in  self.marked_target_lst:
                self.insert_after(self.toolkit.get_landing_pad_line(),line)
        else:
            for line in self.marked_target_lst:
                # back_up alias
                back_up=None
                if line.get_label() in line.next.get_label(): 
                    back_up=line.next
                    self.unlink_line(back_up)
                next_line = line.next
                self.unlink_line(line)

                # update section_align
                section_name=line.section_declaration.get_bare_section()
                if section_name in self.section_align.keys():
                    self.section_align[section_name]=max(self.section_align[section_name], line.slots_info.get_max_align()+skip_low_bit)
                else:
                    self.section_align[section_name] = line.slots_info.get_max_align() +skip_low_bit
                
                # instrument
                self.insert_lines_before(
                    line.slots_info.build_prefix_line_and_label(line,skip_low_bit=skip_low_bit), next_line)
                
                # restore alias
                if back_up: self.insert_after(back_up,line)

    def code_instrument(self,debug=False,skip_lib=False,skip_low_bit=0):
        self.target_instrument(skip_low_bit)
        if len(self.both_valid_tag) <= 1:
            return
        self.branch_instrument(debug=debug,skip_lib=skip_lib,skip_low_bit=skip_low_bit)

    def scfi_all(self, orthogonal=True, max_slot_length=8,debug=False,skip_lib=False,runtime_first=True,skip_low_bit=1):
        '''Paper version: branch with only one identifier, branch may has multiple.
        Only padding, not trampoline.
        :param orthogonal: Generate orthogonal identifiers
        :param max_slot_length: Max huffman code length, if exceed, use ID policy for some slot.
        :param debug: Generate debug asm.
        :param skip_lib: Generate asm that skip the high memory space.
        :param runtime_first: Runtime first (more branches use slot) or Code Size first (more target use slot).
        :param skip_low_bit: maintain at least n bits aligned for each target
        '''

        # prepare, after read cfg

        self.try_convert_indirect()
        self.cut_one_side_tags()
        self.remove_single_edge()
        self.coloring(runtime_first=runtime_first)
        self.colored_IDs()
        self.huffman_after_coloring(
            orthogonal=orthogonal, max_length=max_slot_length, runtime_first=runtime_first)
        self.code_instrument(debug=debug, skip_lib=skip_lib, skip_low_bit=skip_low_bit)
        self.new_lds()
        self.compile_tmp()
        print(str('_ZN10xalanc_1_814FormatterToXML10flushCharsEv' in self.marked_target_lst))
        print(self.label_name_to_line['_ZN10xalanc_1_814FormatterToXML10flushCharsEv'])
    
    def log_file(self,path):
        import collections
        with open(path , 'a') as f:
            f.write('Log for %s:\n'% self.tmp_asm_path)
            f.write('Total icalls number: %d\n'  % len(self.branch_lst))
            f.write('Marked icalls: %d\n' % len(self.marked_branch_lst))
            f.write('Marked targets: %d\n' % len(self.marked_target_lst))
            f.write('Valid tags: %d\n' % len(self.both_valid_tag))
            f.write('Coloring (by tag):' +
                    str(collections.Counter([self.tag_color[v] for v in self.both_valid_tag]))+'\n')
            
            max_identifier=0
            lst = []
            for t in self.marked_target_lst:
                max_identifier = max(max_identifier, len(t.tags))
                for tag in t.tags:
                    lst.append(self.tag_color[tag])
            f.write('Coloring (by target):' + str(collections.Counter(lst))+'\n')
            lst = []
            for t in self.marked_branch_lst:
                for tag in t.tags:
                    lst.append(self.tag_color[tag])
            f.write('Coloring (by branch):' + str(collections.Counter(lst))+'\n')
            f.write('Max multi-tag target # tag: %d' % max_identifier+'\n')

    def try_convert_indirect(self):
        for branch in [b for b in self.marked_branch_lst]:
            '''Some indirect call has a "callq *Label" format, we directly dereference the pointer here.'''
            if self.toolkit.get_call_expr(branch) in self.label_name_to_line.keys():    # call *Label
                if self.label_name_to_line[self.toolkit.get_call_expr(branch)].next.get_directive_type()=='.quad':  #Label:\n  .quad label_name
                    traget_name=self.label_name_to_line[self.toolkit.get_call_expr(branch)].next.strip_comment().split()[-1].strip()
                    if traget_name in self.functions:
                        branch.set_str("\tcallq\t%s"%traget_name)
                        self.marked_branch_lst.remove(branch)
                        