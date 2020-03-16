from time import time
import logging
import hashlib
import os
import subprocess
import pickle
import shutil
import sys
import traceback
from pprint import pprint
from distutils.dir_util import copy_tree


# def tqdm(s): return s  # disable tqdm in pypy


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PYSPEC')

try:
    from tqdm import tqdm
except ImportError:
    logger.info('No tqdm module found, ignore.')
    def tqdm(s): return s


SPEC2006_CPP = ["471.omnetpp", "473.astar", "483.xalancbmk",
                "444.namd", "447.dealII", "450.soplex", "453.povray"]
SPEC2006_C = ["400.perlbench", "401.bzip2", "403.gcc", "429.mcf", "445.gobmk", "456.hmmer",
              "458.sjeng", "462.libquantum", "464.h264ref", "433.milc", "470.lbm", "482.sphinx3"]


class SPEC_CMD():
    """Commands for a benchmark"""

    def __init__(self, benchmark):
        self.name = benchmark
        self.clean_cmd = []
        self.make_cmd = []
        self.options_cmd = []
        self.run_cmd = []
        self.compare_cmd = []


class PYSPEC():
    """work_lst defines the default list of all operations, however it will not affect the command gathering."""

    def __init__(self, spec_path, work_path, log_path, version):
        # define the path of SPEC
        self.spec_path = spec_path
        self.work_path = work_path
        self.log_path = log_path
        self.version = version  # 2000 / 2006 / 2017
        self.work_lst = self.bench_lst  # defult list of all operations
        # now we do not concern fortran
        self.work_lst = SPEC2006_C
        self.work_lst.extend(SPEC2006_CPP)

    @property
    def bench_path(self):
        if self.version == 2006:
            return os.path.join(self.spec_path, 'benchspec/CPU2006')
        else:
            raise Exception("Undefined bench marks path")

    @property
    def bench_lst(self):
        return [f for f in os.listdir(self.bench_path) if os.path.isdir((os.path.join(self.bench_path, f)))]

    def copy_src(self, cp_lst=None):
        if cp_lst == None:  cp_lst = self.work_lst
        for f in cp_lst:
            shutil.copytree(os.path.join(self.bench_path, f, 'src'),
                            os.path.join(self.work_path, f, 'src'))

    def clear_and_setup_work(self, wk_lst=None):
        if wk_lst == None:
            wk_lst = self.work_lst
        for bench in wk_lst:
            if os.path.isdir(os.path.join(self.work_path, bench, 'work')):
                shutil.rmtree(os.path.join(self.work_path, bench, 'work'))
            if os.path.isfile(os.path.join(self.work_path, bench, 'work')):
                os.remove(os.path.join(self.work_path, bench, 'work'))
            os.mkdir(os.path.join(self.work_path, bench, 'work'))

    def copy_input_data(self, size='ref', cp_lst=None):
        """Copy input data of a certain size into work folder, skip if exist.
        Remember to clear and setup work folder before copy."""
        if cp_lst == None:
            cp_lst = self.work_lst
        for benchmark in cp_lst:
            data_path = os.path.join(self.bench_path, benchmark, 'data')
            for folder in os.listdir(data_path):
                if folder == 'all' or folder == size:
                    if 'input' in os.listdir(os.path.join(data_path, folder)):
                        for node in os.listdir(os.path.join(data_path, folder, 'input')):
                            if os.path.exists(os.path.join(self.work_path, benchmark, 'work', node)):
                                continue
                            if os.path.isfile(os.path.join(data_path, folder, 'input', node)):
                                shutil.copy(os.path.join(data_path, folder, 'input', node), os.path.join(
                                    self.work_path, benchmark, 'work', node))
                            if os.path.isdir(os.path.join(data_path, folder, 'input', node)):
                                shutil.copytree(os.path.join(data_path, folder, 'input', node), os.path.join(
                                    self.work_path, benchmark, 'work', node))


    def parse(self, _str):
        stage = ''
        recording = ''
        self.all_cmd = []
        index = -1
        for line in _str.splitlines(False):
            if not line:
                continue
            if line.startswith('Benchmarks selected:'):
                for name in line.split(':')[-1].split(','):
                    self.all_cmd.append(SPEC_CMD(name.strip()))
                continue
            # index
            if line.startswith('%% Fake commands'):
                recording = True
            if line.startswith('%% End of fake'):
                recording = False

            # attr
            if line.startswith('Compiling Binaries'):
                stage = 'compiling'
            if stage == 'compiling':
                if line.startswith('%% Fake commands from make.clean'):
                    attr_str = 'clean_cmd'
                    index += 1
                    continue
                elif line.startswith('%% Fake commands from make '):
                    attr_str = 'make_cmd'
                    continue
                elif line.startswith('%% Fake commands from options'):
                    attr_str = 'options_cmd'
                    continue
            if line.startswith('Running Benchmarks'):
                stage = 'running'
                index = -1
            if stage == 'running':
                if line.startswith('%% Fake commands from benchmark_run'):
                    attr_str = 'run_cmd'
                    index += 1
                    continue
                elif line.startswith('%% Fake commands from compare_run '):
                    attr_str = 'compare_cmd'
                    continue

            if recording:
                self.all_cmd[index].__getattribute__(attr_str).append(line)

    def get_fake_cmd(self, cmd):
        """Get and cache the output of a spec cmd.
        If the output may changed remove all cache files."""
        h = hashlib.md5(cmd.encode('utf-8')).hexdigest()
        cache_path = os.path.join(os.path.split(__file__)[0], 'spec_cmd_cache')
        if os.path.exists(os.path.join(cache_path, str(h))):
            with open(os.path.join(cache_path, str(h)), mode='rb') as f:
                _str = f.read()
        else:
            os.chdir(self.spec_path)
            c = '. ./shrc'
            p = subprocess.Popen(c+';'+cmd, stdout=subprocess.PIPE, shell=True)
            _str = p.stdout.read()
            p.wait()
            with open(os.path.join(cache_path, str(h)), mode='wb') as f:
                f.write(_str)
        self.parse(str(_str, encoding='utf-8'))

    @classmethod
    def get_runspec_cmd(cls, config_file='default', n=1, fake=True, target='int fp', noreportable=True, size='ref'):
        """Get a spec cmd"""
        cmd = 'runspec '
        cmd += '-c='+config_file+' '
        cmd += '-n='+str(n)+' '
        cmd += target+' '
        cmd += '--size='+size+' '
        if fake:
            cmd += '--fake '
        if noreportable:
            cmd += '-noreportable '
        return cmd


    def get_cmds_by_name(self, name):
        for cmd in self.all_cmd:
            if cmd.name == name:
                return cmd
        raise Exception('No SPEC_CMD found for %s' % name)

    def lto_compile(self, c_lst=None, asm_file_name='tmp.s', add_args=" -w", save_bc_file=None):
        if c_lst == None:
            c_lst = self.work_lst

        for benchmark in tqdm(c_lst):
            cmd = self.get_cmds_by_name(benchmark).make_cmd
            os.chdir(os.path.join(self.work_path, benchmark, 'work'))
            os.system('cp -r ../src/* ./')

            for c in tqdm(cmd[:-1]):
                if c.strip():
                    logger.debug(c)
                    p = subprocess.Popen(c+add_args, stdout=subprocess.PIPE, shell=True)
                    p.wait()

            c = cmd[-1] + ' -save-temps -Wl,-plugin-opt=save-temps'
            logger.debug(c)
            p = subprocess.Popen(c, stdout=subprocess.PIPE, shell=True)
            p.wait()

            if save_bc_file:
                c="cp *.precodegen.bc "+save_bc_file
                p = subprocess.Popen(c, stdout=subprocess.PIPE, shell=True)
                p.wait()
            c = "/usr/local/bin/llc *.precodegen.bc -o " + asm_file_name
            p = subprocess.Popen(c, stdout=subprocess.PIPE, shell=True)
            p.wait()

    def benchmark_is_cpp(self, benchmark):
        if self.version == 2006:
            return benchmark in SPEC2006_CPP

    def assemble(self, as_lst=None, asm_name='tmp.s', output_name='tmp.o'):
        if as_lst == None:
            as_lst = self.work_lst
        for benchmark in as_lst:
            tmp_asm_path = os.path.join(self.work_path, benchmark, asm_name)
            tmp_obj_path = os.path.join(self.work_path, benchmark, output_name)
            cmd = 'as %s -o %s' % (tmp_asm_path, tmp_obj_path)
            logger.debug(cmd)
            p = subprocess.run(cmd, stderr=subprocess.PIPE, shell=True)

    def link(self, lk_lst=None, object_name='tmp.o', output_name='tmp'):
        if lk_lst == None:
            lk_lst = self.work_lst
        for benchmark in lk_lst:
            obj_path = os.path.join(
                self.work_path, benchmark, 'work', object_name)
            output_path = os.path.join(
                self.work_path, benchmark, 'work', output_name)
            is_cpp = self.benchmark_is_cpp(benchmark)
            if self.version != 2006:
                logger.warn(
                    "Linking use SPEC2006 config, not tested for other version.")
            if is_cpp:
                c = '"/usr/bin/ld" "-z" "relro" "--hash-style=gnu" "--eh-frame-hdr" "-m" "elf_x86_64" "-dynamic-linker" "/lib64/ld-linux-x86-64.so.2" "-o" "%s" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crt1.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crti.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtbegin.o" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../../lib64" "-L/lib/x86_64-linux-gnu" "-L/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu" "-L/usr/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu/../../lib64" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../.." "-L/usr/local/bin/../lib" "-L/lib" "-L/usr/lib" "%s" "-lm" "-lstdc++" "-lm" "-lgcc_s" "-lgcc" "-lc" "-lgcc_s" "-lgcc" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtend.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crtn.o"' % (
                    output_path, obj_path)
                logger.debug(c)
                os.popen(c)
            else:
                c = '"/usr/bin/ld" "-z" "relro" "--hash-style=gnu" "--eh-frame-hdr" "-m" "elf_x86_64" "-dynamic-linker" "/lib64/ld-linux-x86-64.so.2" "-o" "%s" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crt1.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crti.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtbegin.o" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../../lib64" "-L/lib/x86_64-linux-gnu" "-L/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu" "-L/usr/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu/../../lib64" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../.." "-L/usr/local/bin/../lib" "-L/lib" "-L/usr/lib" "%s" "-lm" "-lgcc" "--as-needed" "-lgcc_s" "--no-as-needed" "-lc" "-lgcc" "--as-needed" "-lgcc_s" "--no-as-needed" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtend.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crtn.o"' % (
                    output_path, obj_path)
                logger.debug(c)
                os.popen(c)


    def run_cycle(self, size='ref', filelst=['tmp'], ru_lst = None):
        if ru_lst==None: ru_lst = self.work_lst
        for benchmark in ru_lst: 
            cmds=self.get_cmds_by_name(benchmark)
            for filename in filelst:
                logger.info('Running %s with file %s...' %
                            (benchmark, filename))
                os.chdir(os.path.join(self.work_path,benchmark,'work'))
                total_takes = 0
                try:
                    run_cmd = cmds.run_cmd
                    for c in run_cmd:
                        if c.startswith('#'): continue
                        if c.startswith('cd'): continue
                        c = filename+' '+c.split(' ', 1)[-1]
                        c = c.replace('>>', '>')
                        logger.debug(c)
                        start = time()
                        p = subprocess.Popen(c, stdout=subprocess.PIPE, shell=True)
                        p.wait()
                        takes = time()-start
                        logger.info('Finished after %d seconds.' % takes)
                        total_takes += takes
                except Exception:
                    with open(os.path.join(self.log_path, 'error.log'), 'a') as f:
                        f.write(cmds.name+traceback.format_exc())
                    with open(os.path.join(self.log_path, 'run.log'), 'a') as f:
                        f.write('Run %s: faild @ size=%s, file=%s.\n' %
                                (cmds.name, size, filename))
                logger.info('Finished %s: %d seconds.' %
                            (cmds.name, total_takes))
                with open(os.path.join(self.log_path, 'run.log'), 'a') as f:
                    f.write('Run %s: %f seconds @ size=%s, file=%s.\n' %
                            (cmds.name, total_takes, size, filename))
    
    def do(self,cmd, do_lst=None):
        if do_lst==None: do_lst= self.work_lst
        for benchmark in do_lst:
            os.chdir(os.path.join(self.work_path,benchmark,'work'))
            os.system(cmd)

    def clear_err_file(self, do_lst=None):
        self.do("rm -f ./*.err",do_lst)
    
    def list_err_file(self, do_lst=None):
        if do_lst==None: do_lst= self.work_lst
        for benchmark in do_lst:
            print('---------------------- errs of ', benchmark)
            os.chdir(os.path.join(self.work_path,benchmark,'work'))
            os.system('cat *.err')


