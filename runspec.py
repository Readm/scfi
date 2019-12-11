from tqdm import tqdm
from time import time
import pickle
import subprocess
import os
import hashlib
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SCFI')

spec_path = '/home/readm/SPEC2006'

def compiles(path,cmd):
    os.chdir(path)
    with open("fastcfi.info", "w") as f:
        for c in tqdm(cmd[:-1]):
            print(c,file=sys.stderr)
            if c.strip():
                p=os.popen(c+' -w')
                output=p.readlines()
                for line in output:
                    if "FastCFI" in line:
                        f.writelines([line])

    c = cmd[-1] + ' -save-temps -Wl,-plugin-opt=save-temps'
    print(c,file=sys.stderr)
    p=subprocess.Popen(c,stdout=subprocess.PIPE,shell=True)
    p.wait()

    compiler = 'clang++' if 'clang++' in cmd[-1].split()[0] else 'clang'
    c = "/usr/local/bin/llc *.precodegen.bc -o fastcfi_final.s"
    p=subprocess.Popen(c,stdout=subprocess.PIPE,shell=True)
    p.wait()
    return


def compile_all():
    lst = \
    ['400.perlbench','401.bzip2','403.gcc','429.mcf','445.gobmk','456.hmmer','458.sjeng','462.libquantum','464.h264ref','471.omnetpp','473.astar','483.xalancbmk'] # CINT2006
    for cmds in tqdm(get_cmds(config='lto.cfg',target='int')):
        if cmds.name in lst:
            try:
                build_cmd = cmds.make_cmd
                dirpath = work_path+cmds.name+'/work'
                if os.path.exists(dirpath) and os.path.isdir(dirpath):
                    shutil.rmtree(dirpath)
                shutil.copytree(work_path+cmds.name+'/src', dirpath)
                compiles(dirpath, build_cmd)
            except Exception as e:
                with open('/home/readm/fast-cfi/log/error.log','a') as f:
                    f.write(cmds.name+traceback.format_exc())

def prepare_all(size='ref'):
    lst = ['400.perlbench','401.bzip2','403.gcc','429.mcf','445.gobmk','456.hmmer','458.sjeng','462.libquantum','464.h264ref','471.omnetpp','473.astar','483.xalancbmk'] # CINT2006
    for i in lst:
        path = '/home/readm/fast-cfi/workload/'+i
        copy_data(path, size=size)


def get_fake_cmd(cmd):
    h = hashlib.md5(cmd.encode('utf-8')).hexdigest()
    if os.path.exists('/home/readm/scfi/cache/%s' % str(h)):
        with open('/home/readm/scfi/cache/%s' % str(h), mode='rb') as f:
            _str = f.read()
    else:
        os.chdir(spec_path)
        c = '. ./shrc'
        p = subprocess.Popen(c+';'+cmd, stdout=subprocess.PIPE, shell=True)
        _str = p.stdout.read()
        p.wait()
        with open('/home/readm/scfi/cache/%s' % str(h), mode='wb') as f:
            f.write(_str)
    return str(_str, encoding='utf-8')


class spec_cmd():
    def __init__(self, name):
        self.name = name
        self.clean_cmd = []
        self.make_cmd = []
        self.options_cmd = []
        self.run_cmd = []
        self.compare_cmd = []


def parse(_str):
    stage = ''
    recording = ''
    all_cmd = []
    index = -1
    for line in _str.splitlines(False):
        if not line:
            continue
        if line.startswith('Benchmarks selected:'):
            for name in line.split(':')[-1].split(','):
                all_cmd.append(spec_cmd(name.strip()))
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
            all_cmd[index].__getattribute__(attr_str).append(line)
    return all_cmd


def get_runspec_cmd(config='default', n=1, fake=True, target='int', noreportable=True):
    cmd = 'runspec '
    cmd += '-c='+config+' '
    cmd += '-n='+str(n)+' '
    cmd += target+' '
    if fake:
        cmd += '--fake '
    if noreportable:
        cmd += '-noreportable '
    return cmd


def get_cmds(config='default', n=1, fake=True, target='int', noreportable=True):
    cmd = get_runspec_cmd(config=config, n=n, fake=fake,
                          target=target, noreportable=noreportable)
    return parse(get_fake_cmd(cmd))


def copy_data(path, size='ref'):
    # path = workload/name
    for f in os.listdir(path+'/data'):
        if f == 'all' or f == size:
            for g in os.listdir(path+'/data/'+f):
                if g == 'input':
                    os.chdir(path+'/data/'+f+'/'+g)
                    os.system('cp -r * ../../../work/')


def run_cycle(size='ref', filelst=['/tmp/scfi_tmp'], lst=['400.perlbench', '401.bzip2', '403.gcc', '429.mcf', '445.gobmk', '456.hmmer', '458.sjeng', '462.libquantum', '464.h264ref', '471.omnetpp', '473.astar', '483.xalancbmk']):

    # prepare_all(size=size)
    target = 'int -size='+size
    for cmds in tqdm(get_cmds(config='lto.cfg', target=target)):
        if cmds.name in lst:
            for filename in filelst:
                logger.info('Running %s with file %s...' % (cmds.name, filename))
                os.chdir('/home/readm/scfi/workload/'+cmds.name+'/work')
                total_takes = 0
                try:
                    run_cmd = cmds.run_cmd
                    for c in run_cmd:
                        if c.startswith('#'):
                            continue
                        if c.startswith('cd'):
                            continue
                        c = filename+' '+c.split(' ', 1)[-1]
                        c = c.replace('>>','>')
                        logger.debug(c)
                        start = time()
                        p = subprocess.Popen(
                            c, stdout=subprocess.PIPE, shell=True)
                        p.wait()
                        takes = time()-start
                        logger.info('Finished after %d seconds.' % takes)
                        total_takes += takes
                except Exception:
                    with open('/home/readm/scfi/log/error.log', 'a') as f:
                        f.write(cmds.name+traceback.format_exc())
                    with open('/home/readm/scfi/log/run.log', 'a') as f:
                        f.write('Run %s: faild @ size=%s, file=%s.\n' %
                                (cmds.name, size, filename))
                logger.info('Finished %s: %d seconds.' % (cmds.name, total_takes))
                with open('/home/readm/scfi/log/run.log', 'a') as f:
                    f.write('Run %s: %f seconds @ size=%s, file=%s.\n' %
                            (cmds.name, total_takes, size, filename))


def link(object_path, output_path, is_cpp=False):
    if is_cpp:
        c = '"/usr/bin/ld" "-z" "relro" "--hash-style=gnu" "--eh-frame-hdr" "-m" "elf_x86_64" "-dynamic-linker" "/lib64/ld-linux-x86-64.so.2" "-o" "%s" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crt1.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crti.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtbegin.o" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../../lib64" "-L/lib/x86_64-linux-gnu" "-L/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu" "-L/usr/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu/../../lib64" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../.." "-L/usr/local/bin/../lib" "-L/lib" "-L/usr/lib" "%s" "-lm" "-lstdc++" "-lm" "-lgcc_s" "-lgcc" "-lc" "-lgcc_s" "-lgcc" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtend.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crtn.o"' % (
            output_path, object_path)
        os.popen(c)
    else:
        c = '"/usr/bin/ld" "-z" "relro" "--hash-style=gnu" "--eh-frame-hdr" "-m" "elf_x86_64" "-dynamic-linker" "/lib64/ld-linux-x86-64.so.2" "-o" "%s" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crt1.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crti.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtbegin.o" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../../lib64" "-L/lib/x86_64-linux-gnu" "-L/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu" "-L/usr/lib/../lib64" "-L/usr/lib/x86_64-linux-gnu/../../lib64" "-L/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../.." "-L/usr/local/bin/../lib" "-L/lib" "-L/usr/lib" "%s" "-lm" "-lgcc" "--as-needed" "-lgcc_s" "--no-as-needed" "-lc" "-lgcc" "--as-needed" "-lgcc_s" "--no-as-needed" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/crtend.o" "/usr/lib/gcc/x86_64-linux-gnu/5.4.0/../../../x86_64-linux-gnu/crtn.o"' % (
            output_path, object_path)
        os.popen(c)

def reset_env():
    compile_all()
    prepare_all()

