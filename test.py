from asmplayground import *
from scfi import *


if 0: # test asmplayground
    asm = AsmSrc.read_file('./testcase/401.bzip.s')
    s = set()
    for line in asm.traverse_lines():
        if line.get_opcode() == None:
            continue
        s.add(line.get_opcode())
    from pprint import pprint
    pprint(s)


if 1: # test scfi
    logger.setLevel(logging.DEBUG)
    #spec_lst=['400.perlbench', '401.bzip2', '403.gcc', '429.mcf', '445.gobmk', '456.hmmer', '458.sjeng', '462.libquantum', '464.h264ref', '471.omnetpp', '473.astar', '483.xalancbmk']
    spec_lst = ['400.perlbench']
    for name in spec_lst:
        filePath = '/home/readm/fast-cfi/workload/%s/work/fastcfi_final.s' % name
        src_path = '/home/readm/fast-cfi/workload/%s/work/' % name
        cfg_path = '/home/readm/fast-cfi/workload/%s/work/fastcfi.info' % name
        asm = SCFIAsm.read_file(filePath, src_path=src_path)
        asm.tmp_asm_path = src_path+'scfi_tmp.s'
        asm.tmp_obj_path = src_path+'scfi_tmp.o'
        asm.tmp_dmp_path = src_path+'scfi_tmp.dump'

        asm.mark_all_instructions(cfg=CFG.read_from_llvm(cfg_path))
        asm.move_file_directives_forward()
        asm.huffman_slot_allocation()
        asm.only_move_targets(move_method=PADDING,slot_alloc=DETERMIN)
        os.chdir(src_path)
        asm.compile_tmp()
        link(asm.tmp_obj_path, src_path+'scfi_tmp')

        run_cycle(size='test', filelst=['./scfi_tmp'], lst=[name])