from asmplayground import *
from scfi import *
import runspec
from pprint import pprint


def test1():
    asm = SCFIAsm.read_file('/home/readm/scfi/testcase/401.bzip.s')
    asm.move_file_directives_forward()
    asm.add_ID_fail()
    with open('/home/readm/scfi/testcase/401.bzip.s.tmp', 'w') as f:
        f.writelines([line+'\n' for line in asm.traverse_lines()])
    exit()
    slots=SLOTS_INFO([SLOT_INFO.new_ID(0x12,0),SLOT_INFO.new_ID(0x34,1),SLOT_INFO.new_slot(5,4),SLOT_INFO.new_slot(3,4),SLOT_INFO.new_slot(0x12,8)])
    pprint(slots.build_prefix_line_and_label(Line('hello:')))


def test2():
    logger.setLevel(logging.DEBUG)
    spec_path = '/home/readm/SPEC2006'
    work_path = '/home/readm/scfi/workload/'
    log_path = '/home/readm/scfi/log'
    version = 2006  # or 2000, 2017 if needed
    spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
    spec.work_lst = ['400.perlbench']
    spec.get_fake_cmd(runspec.PYSPEC.get_runspec_cmd(config_file='vtable',size='test'))
    spec.lto_compile(asm_file_name='vtableo0.s')
    exit()


def test3():
    asm = AsmSrc.read_file(
        '/home/readm/scfi/workload/483.xalancbmk/work/fastcfi_final.s')
    s = set()
    pprint([i for i in asm.get_sections() if '.text' in i])


#spec_lst=['400.perlbench', '401.bzip2', '403.gcc', '429.mcf', '445.gobmk', '456.hmmer', '458.sjeng', '462.libquantum', '464.h264ref', '471.omnetpp', '473.astar', '483.xalancbmk']
spec_lst=runspec.SPEC2006_C
spec_lst=['400.perlbench']

def test4():
    logger.setLevel(logging.INFO)
    for name in spec_lst:

        filePath = '/home/readm/scfi/workload/%s/work/vtable.s' % name
        src_path = '/home/readm/scfi/workload/%s/work/' % name
        work_path = src_path.replace('fast-cfi', 'scfi')
        cfg_path = '/home/readm/scfi/workload/%s/work/tmp.txt' % name
        asm = SCFIAsm.read_file(filePath, src_path=src_path)
        asm.tmp_asm_path = work_path+'scfi_tmp.s'
        asm.tmp_obj_path = work_path+'scfi_tmp.o'
        asm.tmp_dmp_path = work_path+'scfi_tmp.dump'
        asm.move_file_directives_forward()
        asm.mark_all_instructions(cfg=CFG.read_from_llvm_pass(cfg_path))
        asm.scfi_all()

def test5():
    spec_path = '/home/readm/SPEC2006'
    work_path = '/home/readm/scfi/workload/'
    log_path = '/home/readm/scfi/log'
    version = 2006  # or 2000, 2017 if needed
    spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
    spec.work_lst=spec_lst
    # spec.do('opt -load ~/llvm10/build/lib/LLVMSCFI.so -indirect-calls *.0.0.* 1>/dev/null 2>tmp.txt')
    # import time
    # time.sleep(1)
    spec.get_fake_cmd(runspec.PYSPEC.get_runspec_cmd(config_file='vtable',size='test'))
    spec.link(object_name='scfi_tmp.o',output_name='scfi_tmp')
    #spec.copy_input_data(size='test')
    #spec.clear_err_file()
    spec.run_cycle(size='test', filelst=['./scfi_tmp'])
    import time
    #time.sleep(5)
    spec.list_err_file()




test4()