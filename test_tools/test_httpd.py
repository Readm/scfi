import subprocess

lst=[('10K.b', 0.3, 100000),
    ('50K.b',0.3, 100000),
    ('100K.b',0.5, 100000),
    ('500K.b',0.5, 10000),
    ('1M.b',1, 10000),
    ('5M.b',1, 10000),
    ('10M.b',2, 10000),
    ('50M.b',2, 1000),
    ('100M.b',4, 1000),
    ('500M.b',8, 1000),
    ('1000M.b',16, 1000)
    ]



with open('log/apache.log', 'a') as f: 
    for s, max_sd, times in lst:
        f.write(s+'\t')
        time=0
        sd=1000
        while sd==1000: #1time
            result = subprocess.run(['ab', '-c', '10', '-n', '%d'%times, 'http://127.0.0.1/%s' %s], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for line in result.stdout.decode('ascii').split('\n'):
                if 'Time per request:' in line and '(mean)' in line:
                    time = line.split()[3]
                    print(time)
                if 'Total:' in line:
                    sd =float(line.split()[3])
                    print(sd)
        f.write(time+'\t'+str(sd)+'\n')
