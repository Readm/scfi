from asmplayground import *
from scfi import *
import runspec
from pprint import pprint

pass_lst = ["400.perlbench", "401.bzip2", "403.gcc",  "445.gobmk", "456.hmmer",
            "458.sjeng",  "464.h264ref", "433.milc", 
            "471.omnetpp", "473.astar", "483.xalancbmk",
            "444.namd", '453.povray']


def test1():
    asm = SCFIAsm.read_file('/home/readm/scfi/testcase/401.bzip.s')
    asm.move_file_directives_forward()
    asm.add_ID_fail()
    with open('/home/readm/scfi/testcase/401.bzip.s.tmp', 'w') as f:
        f.writelines([line+'\n' for line in asm.traverse_lines()])
    exit()
    slots = SLOTS_INFO([SLOT_INFO.new_ID(0x12, 0), SLOT_INFO.new_ID(
        0x34, 1), SLOT_INFO.new_slot(5, 4), SLOT_INFO.new_slot(3, 4), SLOT_INFO.new_slot(0x12, 8)])
    pprint(slots.build_prefix_line_and_label(Line('hello:')))


def test2():
    logger.setLevel(logging.DEBUG)
    spec_path = '/home/readm/SPEC2006'
    work_path = '/home/readm/scfi/workload/'
    log_path = '/home/readm/scfi/log'
    version = 2006  # or 2000, 2017 if needed
    spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
    spec.work_lst = work_lst
    spec.get_fake_cmd(runspec.PYSPEC.get_runspec_cmd(
        config_file='vtable', size='test'))
    spec.lto_compile(asm_file_name='vtable.s')


def test3():
    asm = AsmSrc.read_file(
        '/home/readm/scfi/workload/483.xalancbmk/work/fastcfi_final.s')
    s = set()
    pprint([i for i in asm.get_sections() if '.text' in i])


#spec_lst=['400.perlbench', '401.bzip2', '403.gcc', '429.mcf', '445.gobmk', '456.hmmer', '458.sjeng', '462.libquantum', '464.h264ref', '471.omnetpp', '473.astar', '483.xalancbmk']
runspec.SPEC2006_C.extend(runspec.SPEC2006_CPP)
spec_lst = runspec.SPEC2006_C
# spec_lst=['433.milc']


def test4():
    '''scfi instrument'''
    for name in work_lst:
        filePath = '/home/readm/scfi/workload/%s/work/vtable.s' % name
        src_path = '/home/readm/scfi/workload/%s/work/' % name
        work_path = src_path.replace('fast-cfi', 'scfi')
        cfg_path = '/home/readm/scfi/workload/%s/work/scfi_tmp.cfg' % name
        asm = SCFIAsm.read_file(filePath, src_path=src_path)
        asm.tmp_asm_path = work_path+'scfi_tmp.s'
        asm.tmp_obj_path = work_path+'scfi_tmp.o'
        asm.tmp_dmp_path = work_path+'scfi_tmp.dump'
        asm.tmp_lds_path = work_path+'scfi_tmp.lds'
        asm.move_file_directives_forward()
        asm.mark_all_instructions(cfg=CFG.read_from_llvm_pass(cfg_path))
        asm.scfi_all()
        asm.log_file('/home/readm/scfi/log/scif.log')


def test5():
    '''compile origin'''
    spec_path = '/home/readm/SPEC2006'
    work_path = '/home/readm/scfi/workload/'
    log_path = '/home/readm/scfi/log'
    version = 2006  # or 2000, 2017 if needed
    spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
    spec.work_lst = spec_lst
    spec.work_lst = ['482.sphinx3']
    # spec.do('opt -load ~/llvm10/build/lib/LLVMSCFI.so -indirect-calls *.0.0.* 1>/dev/null 2>tmp.txt')
    # import time
    # time.sleep(1)
    spec.get_fake_cmd(runspec.PYSPEC.get_runspec_cmd(
        config_file='vtable', size='test'))
    # spec.lto_compile(asm_file_name='vtable.s')
    # spec.assemble(asm_name='vtable.s',output_name='vtable.o')
    # spec.link(object_name='vtable.o',output_name='vtable')
    spec.copy_input_data(size='test')
    spec.clear_err_file()
    spec.run_cycle(size='test', filelst=['./vtable'])
    import time
    # time.sleep(5)
    spec.list_err_file()


def run_new():
    spec_path = '/home/readm/SPEC2006'
    work_path = '/home/readm/scfi/workload/'
    log_path = '/home/readm/scfi/log'
    version = 2006  # or 2000, 2017 if needed
    spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
    spec.work_lst = work_lst
    # spec.work_lst=['400.perlbench','403.gcc','483.xalancbmk']
    spec.get_fake_cmd(runspec.PYSPEC.get_runspec_cmd(
        config_file='vtable', size='ref'))
    spec.copy_input_data(size='ref')
    spec.clear_err_file()
    spec.link(object_name='./scfi_tmp.o',
              output_name='./scfi_tmp', lds='./scfi_tmp.lds')
    spec.run_cycle(size='ref', filelst=['./vtable','./scfi_tmp'],n=11)
    # time.sleep(5)
    spec.list_err_file()


def prepare_cfg():
    spec_path = '/home/readm/SPEC2006'
    work_path = '/home/readm/scfi/workload/'
    log_path = '/home/readm/scfi/log'
    version = 2006  # or 2000, 2017 if needed
    spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
    spec.work_lst = pass_lst
    spec.get_fake_cmd(runspec.PYSPEC.get_runspec_cmd(
        config_file='vtable', size='test'))
    spec.do('opt -load ~/llvm10/build/lib/LLVMSCFI.so -indirect-calls *.0.0.* 1>/dev/null 2>scfi_tmp.cfg')

def readcfg():
    CFG.read_from_llvm_pass('/home/readm/scfi/workload/483.xalancbmk/work/scfi_tmp.cfg')

def size():
    spec_path = '/home/readm/SPEC2006'
    work_path = '/home/readm/scfi/workload/'
    log_path = '/home/readm/scfi/log'
    version = 2006  # or 2000, 2017 if needed
    spec = runspec.PYSPEC(spec_path, work_path, log_path, version)
    spec.work_lst = work_lst
    print(spec.get_exe_code_size('vtable'))

logger = logging.getLogger('SCFI')
logger.setLevel(logging.INFO)
logger0 = logging.getLogger('PYSPEC')
logger0.setLevel(logging.DEBUG)


def apache():
    target_bin_name='httpd'
    os.chdir('/home/readm/apache/httpd-2.4.43')
    #subprocess.run('/usr/local/bin/llc --thread-model=posix *.precodegen.bc -o '+target_bin_name+'.s', shell=True)
    asm = SCFIAsm.read_file(target_bin_name+'.s',src_path='/home/readm/apache/httpd-2.4.43/')
    asm.tmp_asm_path = 'scfi_tmp.s'
    asm.tmp_obj_path = 'scfi_tmp.o'
    asm.tmp_dmp_path = 'scfi_tmp.dump'
    asm.tmp_lds_path = 'scfi_tmp.lds'
    asm.move_file_directives_forward()
    asm.mark_all_instructions(cfg=CFG.read_from_llvm_pass('scfi_tmp.cfg'))
    asm.scfi_all(max_slot_length=6,skip_lib=True)
    #asm.compile_tmp()
    subprocess.run('gcc %s.s -o %s.o -g -c' %('scfi_tmp', 'scfi_tmp'), shell=True)
    subprocess.run('clang -O2 -pthread -flto -o httpd scfi_tmp.o -Wl,--export-dynamic,-T,scfi_tmp.lds server/.libs/libmain.a modules/core/.libs/libmod_so.a modules/http/.libs/libmod_http.a server/mpm/event/.libs/libevent.a os/unix/.libs/libos.a -L/usr/local/lib /usr/local/lib/libpcre.so /usr/lib/x86_64-linux-gnu/libaprutil-1.so /usr/lib/x86_64-linux-gnu/libapr-1.so -g', shell=True)
apache()
exit()

work_lst = ["464.h264ref"]#, "401.bzip2", "403.gcc", "429.mcf", "445.gobmk", "456.hmmer","458.sjeng", "462.libquantum", "464.h264ref","433.milc", "471.omnetpp", "473.astar"]


# size()

# readcfg()
# exit()
test2()
test4()
run_new()
