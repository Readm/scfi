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
    