# Frame of SCFI

SCFI work flow:

CFG generation -> CFG normalization -> SCFI instrument -> assembly rewriting -> compile and run

and this tool supports following functions:

1. CFG generation tool in LLVM pass.
2. CFG normalization (prepared for other CFG generation tools)
3. Assembly rewriting tool (common tool for assembly tool)
4. SCFI instrument (core of SCFI)
5. Python toolkit for SPEC

## CFG generation in LLVM pass

src code: llvm_pass/SCFI (tested in llvm10)

Usage:

1. copy `llvm_pass/SCFI` to LLVM source code `llvm/lib/Transforms/`
2. add a new line in `llvm/lib/Transforms/CMakeLists.txt`: 
```
add_subdirectory(SCFI)
```
3. Build LLVM
4. Use the pass by `opt -load ~/llvm_build_path/lib/LLVMSCFI.so -indirect-calls 1>/dev/null 2>scfi_tmp.cfg`

The output contains:

+ Virtual Function CFG: (for C++ Virtual Functions)
  + Virtual Function Branches:
  + Virtual Function Targets:
+ Function Pointer CFG: (for all Function Pointers)
  + Function Pointer Branches:
  + Function Pointer Targets:

Format of branches:
```
Type: i32 (%struct.sv*, %struct.sv*)
pp_sort.c:357:13
pp_sort.c:1234:20
```
means there are two indirect branches of type `i32 (%struct.sv*, %struct.sv*)`, in given locations.

Format of Targets:
```
Type: void (%struct.op*)
Perl_push_return
Perl_peep
Perl_package
Perl_save_freeop
```
means the given functions have the type `void (%struct.op*)`

Note:

1. If use the CFG normalization tool, you can ignore the detail of this part.
2. The record in Virtual Function has a copy in Function Pointer.

## CFG normalization


