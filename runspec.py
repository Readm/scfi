from tqdm import tqdm
from time import time
import pickle
import subprocess,os

spec_path = '/home/readm/SPEC2006'

def get_fake_cmd(cmd):
    h = hash(cmd)
    if os.path.exists('./cache/%s' % str(h)):
        with open('/home/readm/scfi/cache/%s' % str(h),mode='rb') as f:
            _str = f.read()
    else:
        os.chdir(spec_path)
        c = '. ./shrc'
        p=subprocess.Popen(c+';'+cmd,stdout=subprocess.PIPE,shell=True)
        _str=p.stdout.read()
        p.wait()
        with open('/home/readm/scfi/cache/%s' % str(h), mode='wb') as f:
            f.write(_str)
    return str(_str,encoding='utf-8')

class spec_cmd():
    def __init__(self, name):
        self.name = name
        self.clean_cmd = []
        self.make_cmd  = []
        self.options_cmd = []
        self.run_cmd   = []
        self.compare_cmd = []

def parse(_str):
    stage = ''
    recording = ''
    all_cmd = []
    index = -1
    for line in _str.splitlines(False):
        if not line: continue
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
        if line.startswith('Compiling Binaries'): stage='compiling'
        if stage=='compiling':
            if line.startswith('%% Fake commands from make.clean'): attr_str = 'clean_cmd'; index+=1; continue
            elif line.startswith('%% Fake commands from make '): attr_str = 'make_cmd'; continue
            elif line.startswith('%% Fake commands from options'): attr_str = 'options_cmd'; continue
        if line.startswith('Running Benchmarks'): stage='running'; index=-1
        if stage=='running':
            if line.startswith('%% Fake commands from benchmark_run'): attr_str = 'run_cmd'; index+=1; continue
            elif line.startswith('%% Fake commands from compare_run '): attr_str = 'compare_cmd'; continue
        
        if recording:
            all_cmd[index].__getattribute__(attr_str).append(line)
    return all_cmd
        

def get_runspec_cmd(config='default',n=1,fake=True,target='int',noreportable=True):
    cmd = 'runspec '
    cmd += '-c='+config+' '
    cmd += '-n='+str(n)+' '
    cmd += target+' '
    if fake: cmd += '--fake '
    if noreportable: cmd += '-noreportable '
    return cmd

def get_cmds(config='default',n=1,fake=True,target='int',noreportable=True):
    cmd = get_runspec_cmd(config=config, n=n, fake=fake, target=target, noreportable=noreportable)
    return parse(get_fake_cmd(cmd))

def copy_data(path, size='ref'):
    # path = workload/name
    for f in os.listdir(path+'/data'):
        if f=='all' or f==size:
            for g in os.listdir(path+'/data/'+f):
                if g=='input':
                    os.chdir(path+'/data/'+f+'/'+g)
                    os.system('cp -r * ../../../work/')
                    
def run_cycle(size='ref',filelst=['/tmp/scfi_tmp'],lst=\
    ['400.perlbench','401.bzip2','403.gcc','429.mcf','445.gobmk','456.hmmer','458.sjeng','462.libquantum','464.h264ref','471.omnetpp','473.astar','483.xalancbmk']):
    
    #prepare_all(size=size)
    target = 'int -size='+size
    for cmds in tqdm(get_cmds(config='lto.cfg',target=target)):
        if cmds.name in lst:
            for filename in filelst:
                print('Running %s with file %s...' % (cmds.name, filename))
                os.chdir('/home/readm/fast-cfi/workload/'+cmds.name+'/work')
                total_takes = 0
                try:
                    run_cmd = cmds.run_cmd
                    for c in run_cmd:
                        if c.startswith('#'): continue
                        if c.startswith('cd'): continue
                        c=filename+' '+c.split(' ',1)[-1]
                        print(c)
                        start=time()
                        p=subprocess.Popen(c,stdout=subprocess.PIPE,shell=True)
                        p.wait()
                        takes=time()-start
                        print('Finished after %d seconds.' % takes)
                        total_takes+=takes
                except Exception:
                    with open('/home/readm/fast-cfi/log/error.log','a') as f:
                        f.write(cmds.name+traceback.format_exc())
                    with open('/home/readm/fast-cfi/log/run.log','a') as f:
                        f.write('Run %s: faild @ size=%s, file=%s.\n' % (cmds.name, size, filename))
                print('Finished %s: %d seconds.' %(cmds.name, total_takes))
                with open('/home/readm/fast-cfi/log/run.log','a') as f:
                    f.write('Run %s: %f seconds @ size=%s, file=%s.\n' %(cmds.name, total_takes, size, filename))