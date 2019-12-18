+ [x] 一个通用的汇编文件处理工具
  + [x] 读取和整理section，file loc信息
  + [x] 重排
    + [x] （可能需要）函数分割
    + [x] （可能需要）基本快分割
+ [ ] SCFI框架
  + [x] 基础功能
    + [x]  读取CFG信息，标记所有相关指令
    + [x]  分配slot
      + [x] 随机allocation
      + [ ] variable width slot allocation
    + [x]  重排
      + [x]  padding
        + [ ]  optimize
      + [x]  inserting
        + [ ]  optimize
      + [ ] fix same slot  
  + [ ]  C++ support (section union)
  + [ ]  language support
    + [x]  X86
    + [ ]  ARM
    + [ ]  RISC-V
  + [ ] 动态库支持
    + [ ] 添加object的slot使用信息
    + [x] 处理不同section的对齐
+ [ ] CFG生成工具
  + [x] LLVM icall
  + [ ] C++ 虚函数
  + [ ] switch 等其他

## leaving problems

+ [x] how to modify arbitrary bits
+ [ ] variable slot width/ allocation for it
+ [ ] optimizing compile speed