import subprocess

lst=['10K.b',
    '50K.b',
    '100K.b',
    '500K.b',
    '1M.b',
    '5M.b',
    '10M.b',
    '50M.b',
    '100M.b',
    '500M.b',
    '1000M.b'
    ]

with open('log/apache.log', 'a') as f: 
    for s in lst:
        f.write(s+'\t')
        result = subprocess.run(['ab', '-c', '10', '-n', '1000', 'http://127.0.0.1/%s' %s], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in result.stdout.decode('ascii').split('\n'):
            if 'Time per request:' in line and '(mean)' in line:
                print(line.strip())
                f.write(line.split()[3]+'\t')
            if 'Total:' in line:
                print(line.strip())
                f.write(line.split()[3]+'\n')
