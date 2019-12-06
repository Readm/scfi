+ [ ] 一个通用的汇编文件处理工具
  + [x] 读取和整理section，file loc信息
  + [ ] 重排
    + [ ] （可能需要）函数分割
    + [ ] （可能需要）基本快分割
+ [ ] SCFI框架
  + [ ] 基础功能
    + [x]  读取CFG信息，标记所有相关指令
    + [ ]  分配slot
    + [ ]  添加padding
    + [ ]  重排优化
  + [ ] 动态库支持
    + [ ] 添加object的slot使用信息
    + [ ] 处理不同section的对齐
+ [ ] CFG生成工具
  + [x] LLVM icall