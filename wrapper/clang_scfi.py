#!/usr/bin/python3
# note: CC="/usr/local/bin/clang-scfi" CFLAGS="-O2 -pthread -scfi" LDFLAGS="-flto -pthread"     ./configure
import sys,subprocess

target_bin_list = ['httpd']

args = sys.argv[1:]

args.insert(0,'clang')

# if scfi
if '-scfi' in args:
    args.remove('-scfi')
    args.append('-flto') # requires lto
    if '-pthread' not in args: args.append('-pthread')
    args.append('-g')    # requires debug
    #args.append('-fvisibility=hidden')
    if '-c' not in args: # compile and link
        if '-o' in args:
            target_bin_name=args[args.index('-o')+1]
            if target_bin_name in target_bin_list:
                with open('/home/readm/scfi/wrapper/runlog','a') as f:
                    f.write(' '.join(args)+'\n')
                args+=['-save-temps', '-Wl,-plugin-opt=save-temps']
                subprocess.run(args)
                subprocess.run('opt -load ~/llvm10/build/lib/LLVMSCFI.so -indirect-calls %s.0.0.*.bc 1>/dev/null 2>scfi_tmp.cfg' % target_bin_name, shell= True)
                # subprocess.run('/usr/local/bin/llc *.precodegen.bc -o '+target_bin_name+'.s', shell=True)
                # from scfi import SCFIAsm,CFG
                # asm = SCFIAsm.read_file(target_bin_name+'.s',src_path='/home/readm/apache/httpd-2.4.43/')
                # asm.move_file_directives_forward()
                # asm.mark_all_instructions(cfg=CFG.read_from_llvm_pass('scfi_tmp.cfg'))
                # asm.scfi_all()
                # asm.log_file('/home/readm/scfi/log/scif.log')
                # subprocess.run('as %s.s -o %s.o' %(target_bin_name, target_bin_name), shell=True)
                exit()
subprocess.run(args)