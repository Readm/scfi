import copy
path = '/home/readm/fast-cfi/vir_mem_call_list.txt'

def line_paser(line, debug=False):
    line = line.replace('const','').replace('=0','').replace('*','').replace('&','')
    if line.startswith('/home'): #caller
        debug_info, caller_info = line.strip().split('#')
        class_info, var_name, fun_info = caller_info.split('$')
        namespace, class_name = class_info.split("::")
        function_retval = fun_info.split(')')[-1].strip().split('::')[-1].strip()
        function_args = line.count(',')+1
        if not (line.count('(')==1 and line.split('(')[-1].split(')')[0].strip()): function_args = 0
        
    else: #callee
        line = line.replace('+','').replace('^','').strip()
        class_name = line.split('::')[0]
        function_retval = line.split()[1].strip()
        function_args = line.count(',')+1
        if not (line.count('(')==1 and line.split('(')[-1].split(')')[0].strip()): function_args = 0
    
    if 'Bool' in function_retval: function_retval='bool'
    if 'unsigned' in function_retval: function_retval='unsigned'
    function_retval.replace('_','').strip()

    if debug:
        print(line)
        print({'arg_num':function_args, 'fun_ret':function_retval, 'cla_name':class_name})
        input()
    return {'arg_num':function_args, 'fun_ret':function_retval, 'cla_name':class_name} 

with open(path) as f:
    dct = dict()
    state = 'end'
    callee = []
    for line in f:
        if state == 'end':
            if line.startswith('/home'): # a caller
                state = "begin"
                caller = line
        elif state == 'begin':
            if not line.strip(): 
                state='end' # a empty line
                dct[caller]=callee
                callee = []
            elif line.startswith('    +'): # a callee
                callee.append(line)
        
    dct[caller]=callee

    dct1=copy.deepcopy(dct)

    for caller in dct.keys():
        if len(dct[caller]) == 1: continue

        caller_info = line_paser(caller)
        dellst=[]
        for callee in dct[caller]:
            callee_info = line_paser(callee)
            if callee_info['arg_num'] != caller_info['arg_num']: 
                if callee_info['arg_num'] ==0: continue
                dellst.append(callee); continue


            if callee_info['fun_ret'] != caller_info['fun_ret']: dellst.append(callee); continue
            if callee_info['cla_name'] != caller_info['cla_name']: 
                if '^' in callee:  dellst.append(callee); continue
        for i in dellst: dct[caller].remove(i)

        if len(dct[caller]) != 1:
            print(len(dct[caller]),' ',end='')
        #     print(caller)
        #     for callee in dct[caller]:
        #         print(callee)
            # line_paser(caller,debug=True)
            # for callee in dct1[caller]: line_paser(callee,debug=True)
        
        if len(dct[caller]) == 0:
            # print('\n'+caller)
            # print(dct1[caller])
            print(caller_info['cla_name'],'<>',end='')
            for callee in dct1[caller]: print(' ',line_paser(callee)['cla_name'], end='')
            dct[caller]=dct1[caller]
        

