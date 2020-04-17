#!/usr/bin/python3
import sys,subprocess

args = sys.argv[1:]
args.insert(0,'clang++')
with open('/home/readm/scfi/wrapper/runlog','a') as f:
    f.write(' '.join(args)+'\n')
subprocess.run(args)