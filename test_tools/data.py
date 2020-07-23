path='/home/readm/scfi/log'
output=''

with open(path+'/result_run.log') as f:
    data=[]
    names=[]
    filenames=[]
    for line in f:
        strip_line = line.replace('Run ','').replace('seconds @ size=ref, file=','').replace(':','')
        data.append(strip_line.split())
        if data[-1][0] not in names: names.append(data[-1][0])
        if data[-1][2] not in filenames: filenames.append(data[-1][2])
    
    for filename in filenames:
        output+= filename+':\n'
        for name in names:
            output += name
            for i in data:
                if i[0]==name and i[2]==filename:
                    output += ' '+i[1]
            output += '\n'

# with open(path+'/size.log') as f:
#     output += 'size: origin / opt / random / only shrink\n'
#     for line in f:
#         strip_line = line.replace('Size of ','').replace(':	from','').replace(' \tto','').replace('\t(',' ')\
#             .replace(')(opt) /\t',' ').replace(')(no opt)/\t','').replace(')(on sh)','')
#         lst = strip_line.split()
#         lst[1], lst[2], lst[4], lst[6] = str(int(lst[1],16)), str(int(lst[2],16)), str(int(lst[4],16)), str(int(lst[6],16))
#         strip_line = ' '.join(lst)
#         output += strip_line+'\n'

with open(path+'/data.txt', 'w') as f:
    f.write(output)
    

lst = ['400.perlbench','401.bzip2','403.gcc','429.mcf','445.gobmk','456.hmmer','458.sjeng','462.libquantum','464.h264ref','471.omnetpp','473.astar','483.xalancbmk'] # CINT2006
def get_size_diff():
    import os
    ''' Previous papers use binary size instead of executable code size, so we calculate the diff'''
    for name in lst:
        print(name,'==================')
        path = 'paper-bin/'+name+'/baseline'
        c = 'objdump -h '+ path
        p=os.popen(c)
        output=p.readlines()
        count=0
        for line in output:
            if "." in line and ":" not in line:
                _name, size = line.split()[1:3]
                if not _name.startswith('.text'):
                    print(_name)
                    count+=int(size,16)
        print(count)
         
get_size_diff()

def count_size():
    for i in tqdm(lst):
        print('Counting: ',i)
        path = '/home/readm/fast-cfi/workload/'+i+'/work/'
        os.chdir(path)

        ori_size=dict()
        
        opt_size=dict()
        c = 'objdump fastcfi_opt_reorder.o -h'
        p=os.popen(c)
        output=p.readlines()
        for line in output:
            if "." in line:
                name, size = line.split()[1:3]
                opt_size[name] = size
        
        noopt_size=dict()
        c = 'objdump fastcfi_no_opt_reorder.o -h'
        p=os.popen(c)
        output=p.readlines()
        for line in output:
            if "." in line:
                name, size = line.split()[1:3]
                noopt_size[name] = size

        os_size=dict()
        c = 'objdump fastcfi_only_shrink.o -h'
        p=os.popen(c)
        output=p.readlines()
        for line in output:
            if "." in line:
                name, size = line.split()[1:3]
                os_size[name] = size

        with open('/home/readm/fast-cfi/log/size.log','a') as f:
                ori, opt, no_opt, _os = 0,0,0,0
                for name in ori_size.keys():
                    if not name.startswith('.text'): continue
                    if not (name in opt_size.keys() and name in noopt_size.keys()): print('lost section: '+name); continue
                    ori += int(ori_size[name], 16)
                    opt += int(opt_size[name],16)
                    no_opt += int(noopt_size[name],16)
                    _os += int(os_size[name],16) 
                f.write("Size of %s:\tfrom %x \tto %x\t(%f%%)(opt) /\t %x\t(%f%%)(no opt)/\t %x\t(%f%%)(on sh)\n"%(i, ori, opt, 100*(opt/ori-1), no_opt, 100*(no_opt/ori-1), _os, 100*(_os/ori-1)))