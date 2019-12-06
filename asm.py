# 废弃 作为参考
import subprocess
# Tools

def pad_to_slot(bitwidth,slot):
    return '\t.org ((.-0x%x-1)/(1<<%d)+1)*(1<<%d)+0x%x, 0x90 \t# pad to 0x%x, in width %d\n' %(slot, bitwidth, bitwidth, slot, slot, bitwidth)

def pad_to_label(bitwidth,label):
    return '\t.org ((.-(%s%%(1<<%d))-1)/(1<<%d)+1)*(1<<%d)+(%s%%(1<<%d)), 0x90 \t# pad to %s, in width %d\n' % \
        (label, bitwidth, bitwidth, bitwidth, label ,bitwidth, label, bitwidth)

def read_label_address(label, path):
    # Return None if not found
    with open(path) as f:
        got=False
        for line in f:
            if got: return int(line.split(':')[0],16)
            if label+'>:' in line: got=True

def align_next_try(n):
    if (n & 0xF) ==0: return n-0Xf
    elif (n & 0xF) == 0xF: return n+0x11
    else: return n+1


# Ins
class Ins():
    def __init__(self, s, section='', debug_loc='', tag = None):
        # tag is the label in CFG, since assember label is call label here, we use tag to represent the label in CFG
        self.content=s
        self.section=section
        self.debug_loc=debug_loc
        self.tag = tag   # None for nothing, else number, 0 is also an tag, lst for multi-tag
        self.add_before = ''
        self.add_after = ''
        self.slot = None # None for nothing, else number, 0 is also an tag, lst for multi-tag

    def __str__(self):
        if self.content.startswith('\t.loc\t'): return ''
        return self.add_before+self.content.__str__()+self.add_after
    
    def set_tag(self, tag):
        self.tag = tag
    
    def add_tag(self, tag):
        if isinstance(self.tag, list): 
            if isinstance(tag, list):
                self.tag = self.tag + tag
            else:
                self.tag.append(tag)
        else:
            if self.tag == None:
                self.set_tag(tag)
            else:
                self.tag = [self.tag, tag]
    
    def set_slot(self, slot):
        # this is used in optimized way
        self.slot = slot
    
    def add_slot(self, slot):
        if isinstance(self.slot, list): 
            if isinstance(slot, list):
                self.slot = self.slot + slot
            else:
                self.slot.append(slot)
        else:
            if self.slot == None:
                self.set_slot(slot)
            else:
                self.slot = [self.slot, slot]
    
    @property
    def is_ins(self):
        if not self.content: return False
        if self.content[0] != '\t': return False
        if not self.content.lstrip(): return False
        if self.content.lstrip()[0] in ['.', '#']: return False
        return True

    @property # remove comment
    def ins(self):
        return self.content.split('#')[0].strip()
        
    @property
    def is_label(self):
        return self.content.lstrip() == self.content and self.ins.endswith(':')

    @property
    def label(self):
        if not self.is_label: raise Exception()
        return self.ins.split(':')[0]

    @property
    def isCall(self):
        return self.ins.startswith("call")
    
    @property
    def isICall(self):
        return self.isCall and '*' in self.ins

class Asm():

    def __init__(self, path):
        # tag: the tag of llvm-cfi
        self.tag_set=set([])
        # caller info: debug_loc -> tag
        self.caller_info = dict()
        # callee info: tag -> list of [name, debug_loc]
        self.callee_info = dict()
        # all icall with tag
        self.icall_lst = []
        # slot: tag -> slot
        self.slot = dict([])
        # bit width of slot
        self.slot_bit_width = 10
        # label count of .Lfastcfi
        self.label_count = 0
        # replace count
        self.replaced = 0
        # reorder 
        self.order=[]

        self.function_size = dict()
        with open(path) as f:
            self.body=[]
            self.function_list=[]
            self.labes=dict() # accelarate
            debug_loc = ''
            section = ''
            for line in f:
                if line.lstrip().startswith('.loc\t'): debug_loc = line.split("#")[-1].strip()
                if line.lstrip().startswith('.text'): section = '.text'
                if line.lstrip().startswith('.data'): section = '.data'
                if line.lstrip().startswith('.bss'): section = '.bss'
                if line.lstrip().startswith('.section'): section = '.' +line.split('.')[-1]
                
                if "# -- Begin function" in line:
                    function_name = line.split()[-1]
                    self.function_list.append(function_name)
                
                if "# -- End function" in line:
                    debug_loc = ''

                ins = Ins(line, section=section, debug_loc=debug_loc)
                if ins.is_label: self.labes[ins.label]=ins
                self.body.append(ins)
    
    @property
    def bit_mask(self):
        return (1<<self.slot_bit_width)-1

    def get_cfi_info(self, path):
        self.caller_info, self.callee_info = read_cfi_info(path)
        self.tag_set = set(self.caller_info.values())
        del_lst = []
        for k in self.callee_info.keys():
            if k not in self.tag_set:
                del_lst.append(k)
        for k in del_lst:
            del self.callee_info[k]

    def read_function_len(self, fun, path):
        if self.function_size:
            return self.function_size[fun]
        else:
            with open(path) as f:
                last_add = None
                last_lab = None
                last_line = None
                for line in f:
                    if line.startswith('0'):
                        add=int(line.split()[0],16)
                        if last_lab: self.function_size[last_lab] = add-last_add
                        last_lab=line.split('<')[-1].split('>')[0]
                        last_add=add
                        continue
                    last_line = line
                add=int(last_line.split(':')[0],16)
                self.function_size[last_lab] = add-last_add
                dump_path = path
                return self.function_size[fun]

    def find_label(self, label):
        try:
            return self.labes[label]
        except KeyError:
            return None

    def write(self,path):
        if self.order:
            self.write_order(path, self.order)
        else:
            with open(path, 'w') as f:
                for ins in self.body:
                    f.write(ins.__str__())

    def write_order(self, path, order):
        with open(path, 'w') as f:
            f.write(self.pre_fun.__str__())
            for fun in order:
                f.write(self.functions[fun].__str__())
            for fun in [f for f in self.ori_order if f not in order]:
                f.write(self.functions[fun].__str__())
            f.write(self.suf_fun.__str__())
   
    def mark_all_icall(self, log=False):
        dct = dict()
        cnt = 0
        for i in self.body:
            if i.debug_loc.endswith('0:0'): continue
            if i.isICall:
                if i.debug_loc in self.caller_info.keys():
                    i.settag(self.caller_info[i.debug_loc])
                    self.icall_lst.append(i)

                    cnt += 1
                    if self.caller_info[i.debug_loc] in dct.keys():
                        dct[self.caller_info[i.debug_loc]] +=1
                    else:
                        dct[self.caller_info[i.debug_loc]] = 1

                elif 1:
                    print("NOT FOUND:"+i.debug_loc)
        for tag in self.callee_info.keys():
            for value in self.callee_info[tag]:
                if not self.find_label(value[0]):
                    continue
                self.find_label(value[0]).settag(tag)

                cnt+=1
                if tag in dct.keys():
                        dct[tag] +=1
                else:
                        dct[tag] = 1
        
        ndct=dict()
        for num in dct.values():
            ndct[num]=list(dct.values()).count(num)
        
        return(' '+str(cnt)+' '+str(ndct))

    # for not optimized
    def slot_allocate(self, align_first=True):
        # tag -> slot
        # no share slot
        # align_first: first allocate 16 byte align slot
        key_set=set(self.callee_info.keys())
        for tag in self.caller_info.values():
            key_set.add(tag)
        for tag in key_set:
            first_try = int(tag,16) & ((1<<self.slot_bit_width) - 1)
            if align_first: first_try = first_try & ~0xF
            if first_try not in self.slot.values():
                self.slot[tag] = first_try
            else: #occupied
                # TODO: fix align_first
                while len(self.slot.values())<(1<<self.slot_bit_width): # not full
                    first_try += 1
                    if first_try not in self.slot.values():
                        self.slot[tag] = first_try
                        break
                else:
                    raise Exception('Slot full.')

    # for not optimized
    def reorder_to_slot(self):
        for i in self.body:
            if i.tag != None:
                if i.is_label:
                    i.add_before = pad_to_slot(self.slot_bit_width, self.slot[i.tag])
                    i.add_after = '\t.byte 0xF3, 0x0F, 0x1E, 0xFA\n'
                else:
                    label='.Lfastcfi%d' % self.label_count
                    self.label_count +=1
                    i.add_before = '\tjmp %s \n'%label + pad_to_slot(self.slot_bit_width, self.slot[i.tag]) + '%s:\n'%label

    def no_opt_slot_allocate(self):
        self.slot_allocate()
        self.mark_all_icall()
        self.reorder_to_slot()

    def only_shrink(self):
        # need get_cfi_info
        def compile_tmp(order):
            print('LOG: compiling...')
            _order = [f for f in order]
            for f in self.functions.keys():
                if f not in _order: _order.append(f)
            
            self.write_order('fastcfi_tmp.s', _order)
            c = 'as fastcfi_tmp.s -o fastcfi_tmp.o'
            p=subprocess.Popen(c,stderr=subprocess.PIPE,shell=True)
            p.wait()
            if p.stderr.read(): raise Exception
            c = 'objdump -d fastcfi_tmp.o > fastcfi_tmp.dump'
            p=subprocess.Popen(c,stdout=subprocess.PIPE,shell=True)
            p.wait()
        
        # Step 1: Mark all src/dest
        print('LOG: Cutting into functions...')
        self.cut_into_functions()
        print('LOG: Marking all IDs...')
        self.mark_all_icall()

        # Step 2: Mark all Functions to float/pin

        # Step 3: Initialize
        # to do : remove all align
        placed_fun = []
        # tmp dump path
        path = 'fastcfi_tmp.dump'

        # Step 4: place all pin functions
        fp_buffer = [f for f in self.order]
        while fp_buffer:
            this_roundtags = set()
            this_round_fun = set()
            shrink_funs = dict()
            id_fun_label = dict() # function shares the id tag, record them

            # one place round
            i_fp = [f for f in fp_buffer]   # can't modify while iteration
            for f in i_fp:
                # check this round id in f
                crosstag = False
                for tag in self.functions[f].undeftags:
                    if tag in this_roundtags: crosstag = True; break
                if crosstag: break
                
                print('LOG: placeing function: %s'%f)
                for tag in self.functions[f].undeftags: this_roundtags.add(tag)
                placed_fun.append(f)
                this_round_fun.add(f)

                # handle function
                markedtag = set()  # need allocated this round
                for i in self.functions[f].body:
                    if i.tag == None: continue   # need allocated
                    if i.slot == None:           # not allocated id
                        if not i.is_label: # an icall ins
                            if i.tag in markedtag:
                                if i.tag in id_fun_label.keys():
                                    i.add_before = pad_to_label(self.slot_bit_width, id_fun_label[i.tag])
                                else:
                                    i.add_before = pad_to_label(self.slot_bit_width, 'ID%s'%i.tag)
                            else:
                                markedtag.add(i.tag)
                                #print('TMPLOG: %s'%i.tag)
                                i.add_before = '\t.p2align\t4, 0x90\n'+'ID%s:\n' % i.tag # mark ID, align first
                        else: # an function
                            if i.tag in markedtag:
                                raise Exception("Never shoud happend")
                            else:
                                id_fun_label[i.tag] = i.label
                                markedtag.add(i.tag)
                    else: # allocated id
                        if i.is_label: # allocated function
                            i.add_before = pad_to_slot(self.slot_bit_width, self.slot[i.tag])
                            i.add_after = '\t.byte 0xF3, 0x0F, 0x1E, 0xFA\n'
                        else: # allocated ins
                            label='.Lfastcfi%d' % self.label_count
                            self.label_count +=1
                            i.add_before = '\tjmp %s \n'%label + pad_to_slot(self.slot_bit_width, self.slot[i.tag]) + '%s:\n'%label
    
                # if need shrink
                if self.functions[f].has_allocatedtag:
                    for i in self.functions[f].body: # find first shrink target 
                        if i.tag != None and i.slot != None:
                            if i.is_label: break # if the target is function itself
                            else:
                                label = [x for x in i.add_before.split() if x.startswith('.')][0] 
                                i.add_before = i.add_before.replace(label, 'FastCFItmp'+label[1:]) # enable label in objdump
                                #print("TMPLOG: %s"%i.add_before)
                                #print('TMPLOG: function:%s, label:%s'%(f,label[1:]))
                                shrink_funs[f]='FastCFItmp'+label[1:]
                            break


            # if need shrink
            if shrink_funs:
                compile_tmp(placed_fun) 
                path = 'fastcfi_tmp.dump'
                for f in shrink_funs.keys():
                    if shrink_funs[f].startswith('FastCFItmp'): 
                        for i in self.functions[f].body:
                            if i.tag !=None and i.slot != None and not i.is_label:
                                if 'FastCFItmp' in i.add_before:
                                    i.add_before = i.add_before.replace('FastCFItmp', '.') # disable label in objdump
                                    break
                    pad_len = read_pad_len_before(shrink_funs[f], path)
                    pad_len = pad_len >> 4 << 4
                    if not pad_len: continue # skip small padding
                    head_now = read_label_address(f, path)  >> 4 << 4 
                    new_head_slot = (head_now + pad_len) & self.bit_mask
                    self.functions[f].align_and_head[0].add_before = pad_to_slot(self.slot_bit_width, new_head_slot)
            # TODO: double shrink
                    
            compile_tmp(placed_fun)
            print("LOG: this_roundtags: ", this_roundtags)
            for tag in this_roundtags:
                print('LOG: try ID: %s'%tag)
                label = id_fun_label[tag] if tag in id_fun_label.keys() else 'ID%s' % tag
                #print('TMPLOG: ID:%s label:%s' %(tag, label))
                add = read_label_address(label, path)
                _try = add & self.bit_mask
                first_try = _try
                if _try not in self.slot.values():
                    self.slot[tag]=_try
                else:
                    if _try &0xF == 0: _try=_try-1 # try next align first
                    while len(self.slot.values()) < (1<< self.slot_bit_width):
                        _try = align_next_try(_try)%(1<<self.slot_bit_width)
                        if _try not in self.slot.values():
                            self.slot[tag]=_try
                            break
                    else:
                        raise Exception('Slot Full')
                #print('TMPLOG: slot for id%s: %x'%(tag, self.slot[tag]))
                
                # update this id
                for f in fp_buffer:
                    for i in self.functions[f].body:
                        if i.tag == tag:
                            i.slot = self.slot[tag]
                            if i.is_label: # allocated function
                                i.add_before = pad_to_slot(self.slot_bit_width, self.slot[i.tag])
                                i.add_after = '\t.byte 0xF3, 0x0F, 0x1E, 0xFA\n'
                            else: # allocated ins
                                label='.Lfastcfi%d' % self.label_count
                                self.label_count +=1
                                i.add_before = '\tjmp %s \n'%label + pad_to_slot(self.slot_bit_width, self.slot[i.tag]) + '%s:\n'%label
                
                if first_try != _try:
                    print('LOG: conflict %x -> %x' % (first_try,_try))
                    compile_tmp(placed_fun)
                
            # update buffer
            for f in this_round_fun:
                fp_buffer.remove(f)


        compile_tmp(placed_fun)

        return('LOG: slots: %d, aligned: %d\n'\
             % (len(self.slot.keys()), len([i for i in self.slot.values() if i&0xF==0])) )

    def only_shrink_multi(self):
        pass

if __name__ == '__main__':

    asm=Asm('/home/readm/fast-cfi/workload/401.bzip2/work/fastcfi_final.s')#.replace('401.bzip2','483.xalancbmk'))
    asm.get_cfi_info('/home/readm/fast-cfi/workload/401.bzip2/work/')#.replace('401.bzip2','483.xalancbmk'))
    asm.mark_all_icall()
    exit()
    #asm.no_opt_slot_allocate()
    asm.only_shrink()
    asm.write('ons.s')
    for f in asm.functions.keys():
        print(f)
    exit()