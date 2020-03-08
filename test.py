from asmplayground import *
from scfi import *
import runspec

logger.setLevel(logging.WARN)
CFG.read_from_llvm_pass('/home/readm/scfi/workload/483.xalancbmk/work/tmp.txt')

exit()

logger.setLevel(logging.DEBUG)
spec_path = '/home/readm/SPEC2006'
work_path = '/home/readm/scfi/workload/'
log_path = '/home/readm/scfi/log'
version = 2006  # or 2000, 2017 if needed
spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
spec.work_lst = ['483.xalancbmk']
spec.get_fake_cmd(runspec.PYSPEC.get_runspec_cmd(config_file='strict',size='test'))
spec.lto_compile(asm_file_name='strict.s')
exit()

if 0:  # test asmplayground
    asm = AsmSrc.read_file(
        '/home/readm/scfi/workload/483.xalancbmk/work/fastcfi_final.s')
    s = set()
    pprint([i for i in asm.get_sections() if '.text' in i])
else:  # test scfi
    logger.setLevel(logging.DEBUG)
    #spec_lst=['400.perlbench', '401.bzip2', '403.gcc', '429.mcf', '445.gobmk', '456.hmmer', '458.sjeng', '462.libquantum', '464.h264ref', '471.omnetpp', '473.astar', '483.xalancbmk']
    spec_lst = ['401.bzip2']
    for name in spec_lst:
        filePath = '/home/readm/scfi/workload/%s/work/fastcfi_final.s' % name
        src_path = '/home/readm/fast-cfi/workload/%s/work/' % name
        work_path = src_path.replace('fast-cfi', 'scfi')
        cfg_path = '/home/readm/scfi/workload/%s/work/fastcfi.info' % name
        asm = SCFIAsm.read_file(filePath, src_path=src_path)
        asm.tmp_asm_path = work_path+'scfi_tmp.s'
        asm.tmp_obj_path = work_path+'scfi_tmp.o'
        asm.tmp_dmp_path = work_path+'scfi_tmp.dump'

        asm.mark_all_instructions(cfg=CFG.read_from_llvm(cfg_path))
        asm.move_file_directives_forward()
        asm.huffman_slot_allocation()
        asm.move_targets_mix()
        os.chdir(work_path)
        asm.compile_tmp()
        link(asm.tmp_obj_path, work_path+'scfi_tmp', is_cpp=True)
        import time
        time.sleep(1)

        run_cycle(size='test', filelst=['./scfi_tmp'], lst=[name])
