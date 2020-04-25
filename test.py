import cfg

a=cfg.CFG.read_from_llvm_pass('/home/readm/scfi/workload/483.xalancbmk/work/scfi_tmp.cfg',union_file='/home/readm/scfi/workload/483.xalancbmk/work/scfi_tmp.union',inherit_path='/home/readm/scfi/workload/483.xalancbmk/doxygen/html/')
print(str('_ZN10xalanc_1_814FormatterToXML10flushCharsEv' in a.target.keys()))
a.dump('/home/readm/scfi/workload/483.xalancbmk/work/scfi_tmp.cfgdump.test')

b=cfg.CFG.load('/home/readm/scfi/workload/483.xalancbmk/work/scfi_tmp.cfgdump.test')
from pprint import pprint

print(str('_ZN10xalanc_1_814FormatterToXML10flushCharsEv' in b.target.keys()))