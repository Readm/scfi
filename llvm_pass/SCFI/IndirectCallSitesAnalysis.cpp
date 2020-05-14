#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Intrinsics.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Dominators.h"
#include "llvm/IR/DebugLoc.h"
#include "llvm/Support/Debug.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/InstIterator.h"
#include "llvm/ADT/MapVector.h"
#include "llvm/IR/Dominators.h"
#include "llvm/IR/Metadata.h"
#include "llvm/IR/DebugInfoMetadata.h"

#include "llvm/Analysis/TypeMetadataUtils.h"
#include "llvm/Transforms/IPO/WholeProgramDevirt.h"
#include "llvm/Analysis/TypeMetadataUtils.h"

#include "llvm/IR/LegacyPassManager.h"
#include "llvm/Transforms/IPO/PassManagerBuilder.h"

#include "llvm/Pass.h"

#include <set>
#include <memory>
#include <unordered_set>
#include <unordered_map>

namespace llvm {
class FunctionType;
class CallSite;
class Function;
} // namespace llvm


namespace  scfi{


class CFGResult
{
public:
    using FunctionSet = std::unordered_set<llvm::Function*>;
    using BranchSet = std::unordered_set<llvm::CallBase*>;
    
public:
    void addIndirectCallTarget(llvm::FunctionType* type, llvm::Function* target, bool is_virtual);
    void addIndirectCallTargets(llvm::FunctionType* type, const FunctionSet& targets, bool is_virtual);
    void addIndirectBranch(llvm::FunctionType* type, llvm::CallBase* branch, bool is_virtual);

    bool hasIndirectTargets(llvm::FunctionType* func_ty) const;
    const FunctionSet& getIndirectTargets(llvm::FunctionType* func_ty) const;

    virtual bool hasIndCSCallees(const llvm::CallSite& callSite) const ;
    virtual FunctionSet getIndCSCallees(const llvm::CallSite& callSite) ;

public:
    void dump();

private:
    std::unordered_map<llvm::FunctionType*, BranchSet> indirectBranches;
    std::unordered_map<llvm::FunctionType*, FunctionSet> indirectTargets;

    std::unordered_map<llvm::FunctionType*, BranchSet> indirectVirtualBranches;
    std::unordered_map<llvm::FunctionType*, FunctionSet> indirectVirtualTargets;
}; // class CFGResult

class IndirectCallSitesAnalysis : public llvm::ModulePass
{
public:
    using ResultPointer = CFGResult*; 
public:
    static char ID;

    IndirectCallSitesAnalysis();

public:
    void getAnalysisUsage(llvm::AnalysisUsage& AU) const override;
    bool runOnModule(llvm::Module& M) override;

public:
    ResultPointer getIndirectsAnalysisResult()
    {
        return results;
    }

private:
    class VirtualsImpl;
    VirtualsImpl *m_vimpl;

    class IndirectsImpl;
    IndirectsImpl *m_iimpl;

    ResultPointer results;
}; // class VirtualCallSitesAnalysis

}


namespace  scfi{


class IndirectCallSitesAnalysis::IndirectsImpl
{
public:
    using ResultPointer = IndirectCallSitesAnalysis::ResultPointer;
    IndirectsImpl(ResultPointer results);
    void runOnModule(llvm::Module& M);

private:
    ResultPointer  results;
};

IndirectCallSitesAnalysis::IndirectsImpl::IndirectsImpl(ResultPointer results)
    : results(results)
{
}

void IndirectCallSitesAnalysis::IndirectsImpl::runOnModule(llvm::Module& M)
{
    for (auto& F : M) {
        if (F.isDeclaration()) {
            continue;
        }
        auto type = F.getFunctionType();
        results->addIndirectCallTarget(type, &F, false);

        for (llvm::Function::iterator b = F.begin(), be = F.end(); b != be; ++b) {
            for (llvm::BasicBlock::iterator i = b->begin(), ie = b->end(); i != ie; ++i) {
                if (llvm::CallBase* callInst = llvm::dyn_cast<llvm::CallBase>(&*i)) {
                    if (callInst->isIndirectCall()){
                        llvm::FunctionType* ft = callInst->getFunctionType();
                        results->addIndirectBranch(ft,callInst,false);

                    }
                }
            }
        } 

    }
}

class IndirectCallSitesAnalysis::VirtualsImpl
{
private:
    struct VTableSlot
    {
        llvm::Metadata* TypeID;
        uint64_t ByteOffset; 
    };

    struct VirtualCallSite
    {
        llvm::Value* VTable;
        llvm::CallSite CS;
    };

    class VTableSlotEqual
    {
     public:
        bool operator() (const VTableSlot& slot1, const VTableSlot& slot2) const
        {
            return slot1.TypeID == slot2.TypeID && slot1.ByteOffset == slot2.ByteOffset;
        }
    };

    class VTableSlotHasher
    {
     public:
        unsigned long operator() (const VTableSlot& slot) const
        {
            return std::hash<llvm::Metadata*>{}(slot.TypeID) ^ std::hash<uint64_t>{}(slot.ByteOffset);
        }
    };

    using VirtualCallSites = std::vector<VirtualCallSite>;
    using VTableSlotCallSitesMap = std::unordered_map<VTableSlot, VirtualCallSites, VTableSlotHasher, VTableSlotEqual>;

public:
    using FunctionSet = CFGResult::FunctionSet;
    using ResultPointer = IndirectCallSitesAnalysis::ResultPointer;
    VirtualsImpl(ResultPointer results);

public:
    void runOnModule(llvm::Module& M, llvm::function_ref<llvm::DominatorTree &(llvm::Function &)>  domTreeGetter);

private:
    void collectTypeTestUsers(llvm::Function* F, llvm::function_ref<llvm::DominatorTree &(llvm::Function &)> domTreeGetter);
    void buildTypeIdentifierMap(std::vector<llvm::wholeprogramdevirt::VTableBits> &Bits,
                                std::unordered_map<llvm::Metadata*, std::set<llvm::wholeprogramdevirt::TypeMemberInfo>> &TypeIdMap);
    bool tryFindVirtualCallTargets(std::vector<llvm::wholeprogramdevirt::VirtualCallTarget>& TargetsForSlot,
                                   const std::set<llvm::wholeprogramdevirt::TypeMemberInfo>& TypeMemberInfos,
                                   uint64_t ByteOffset);
    void updateResults(const std::vector<VirtualCallSite>& S,
                       const std::vector<llvm::wholeprogramdevirt::VirtualCallTarget> TargetsForSlot);

private:
   llvm::Module* m_module; 
   VTableSlotCallSitesMap m_callSlots;
   ResultPointer results;
};

IndirectCallSitesAnalysis::VirtualsImpl::VirtualsImpl(ResultPointer results)
    : results(results)
{
}

void IndirectCallSitesAnalysis::VirtualsImpl::runOnModule(llvm::Module& M,  llvm::function_ref<llvm::DominatorTree &(llvm::Function &)> domTreeGetter)
{
    m_module = &M;

    llvm::Function* TypeTestFunc = M.getFunction(llvm::Intrinsic::getName(llvm::Intrinsic::type_test));
    llvm::Function *TypeCheckedLoadFunc = M.getFunction(llvm::Intrinsic::getName(llvm::Intrinsic::type_checked_load));
    llvm::Function *AssumeFunc = M.getFunction(llvm::Intrinsic::getName(llvm::Intrinsic::assume));

    if ((!TypeTestFunc || TypeTestFunc->use_empty() || !AssumeFunc ||
                AssumeFunc->use_empty()) &&
            (!TypeCheckedLoadFunc || TypeCheckedLoadFunc->use_empty()))
        return;

    if (TypeTestFunc && AssumeFunc) {
        collectTypeTestUsers(TypeTestFunc, domTreeGetter);
    }

    std::vector<llvm::wholeprogramdevirt::VTableBits> Bits;
    std::unordered_map<llvm::Metadata*, std::set<llvm::wholeprogramdevirt::TypeMemberInfo>> TypeIdMap;
    buildTypeIdentifierMap(Bits, TypeIdMap);
    if (TypeIdMap.empty()) {
        return;
    }
    for (auto& S : m_callSlots) {
        std::vector<llvm::wholeprogramdevirt::VirtualCallTarget> TargetsForSlot;
        if (!tryFindVirtualCallTargets(TargetsForSlot, TypeIdMap[S.first.TypeID], S.first.ByteOffset)) {
            continue;
        }
        updateResults(S.second, TargetsForSlot);
    }

    //results->dump();
    // cleanup uneccessary data
    m_callSlots.clear();
}

void IndirectCallSitesAnalysis::VirtualsImpl::collectTypeTestUsers(llvm::Function* F, llvm::function_ref<llvm::DominatorTree &(llvm::Function &)> domTreeGetter)
{
    auto I = F->use_begin();
    while (I != F->use_end()) {
        auto CI = llvm::dyn_cast<llvm::CallInst>(I->getUser());
        ++I;
        if (!CI) {
            continue;
        }
        llvm::SmallVector<llvm::DevirtCallSite, 1> DevirtCalls;
        llvm::SmallVector<llvm::CallInst *, 1> Assumes;
        auto &DT = domTreeGetter(*CI->getFunction());
        llvm::findDevirtualizableCallsForTypeTest(DevirtCalls, Assumes, CI, DT);

        if (Assumes.empty()) {
            return;
        }
        std::unordered_set<llvm::Value*> SeenPtrs;
        llvm::Metadata* TypeId = llvm::cast<llvm::MetadataAsValue>(CI->getArgOperand(1))->getMetadata();
        llvm::Value* Ptr = CI->getArgOperand(0)->stripPointerCasts();
        if (!SeenPtrs.insert(Ptr).second) {
            continue;
        }
        for (const auto& Call : DevirtCalls) {
            m_callSlots[{TypeId, Call.Offset}].push_back({CI->getArgOperand(0), Call.CS});
        }
    }
}

void IndirectCallSitesAnalysis::VirtualsImpl::buildTypeIdentifierMap(
                                          std::vector<llvm::wholeprogramdevirt::VTableBits>& Bits,
                                          std::unordered_map<llvm::Metadata*, std::set<llvm::wholeprogramdevirt::TypeMemberInfo>>& TypeIdMap)
{
    llvm::DenseMap<llvm::GlobalVariable*, llvm::wholeprogramdevirt::VTableBits*> GVToBits;
    Bits.reserve(m_module->getGlobalList().size());
    llvm::SmallVector<llvm::MDNode *, 2> Types;
    for (auto& GV : m_module->globals()) {
        Types.clear();
        GV.getMetadata(llvm::LLVMContext::MD_type, Types);
        if (Types.empty())
            continue;

        llvm::wholeprogramdevirt::VTableBits *&BitsPtr = GVToBits[&GV];
        if (!BitsPtr) {
            Bits.emplace_back();
            Bits.back().GV = &GV;
            Bits.back().ObjectSize = m_module->getDataLayout().getTypeAllocSize(GV.getInitializer()->getType());
            BitsPtr = &Bits.back();
        }

        for (auto Type : Types) {
            auto TypeID = Type->getOperand(1).get();
            uint64_t Offset = llvm::cast<llvm::ConstantInt>(llvm::cast<llvm::ConstantAsMetadata>(
                                                                            Type->getOperand(0))->getValue())->getZExtValue();
            TypeIdMap[TypeID].insert({BitsPtr, Offset});
        }
    }
}

bool IndirectCallSitesAnalysis::VirtualsImpl::tryFindVirtualCallTargets(
                                   std::vector<llvm::wholeprogramdevirt::VirtualCallTarget>& TargetsForSlot,
                                   const std::set<llvm::wholeprogramdevirt::TypeMemberInfo>& TypeMemberInfos,
                                   uint64_t ByteOffset)
{
    for (const auto& TM : TypeMemberInfos) {
        if (!TM.Bits->GV->isConstant()) {
            return false;
        }

        llvm::Constant *Ptr = getPointerAtOffset(TM.Bits->GV->getInitializer(),
                                       TM.Offset + ByteOffset, *m_module);
        if (!Ptr)
            return false;

        auto Fn = llvm::dyn_cast<llvm::Function>(Ptr->stripPointerCasts());
        // auto Fn = llvm::dyn_cast<llvm::Function>(Init->getOperand(Op)->stripPointerCasts());
        if (!Fn) {
            return false;
        }

        // We can disregard __cxa_pure_virtual as a possible call target, as
        // calls to pure virtuals are UB.
        if (Fn->getName() == "__cxa_pure_virtual")
            continue;

        TargetsForSlot.push_back({Fn, &TM});
    }

    // Give up if we couldn't find any targets.
    return !TargetsForSlot.empty();
}

void IndirectCallSitesAnalysis::VirtualsImpl::updateResults(const std::vector<VirtualCallSite>& S,
                                                   const std::vector<llvm::wholeprogramdevirt::VirtualCallTarget> TargetsForSlot)
{
    for (auto& cs : S) {
        FunctionSet candidates;
        for (const auto& slot : TargetsForSlot) {
            candidates.insert(slot.Fn);
        }
        llvm::FunctionType* functionType = cs.CS.getFunctionType();
        llvm::Instruction* callins = cs.CS.getInstruction();
        llvm::CallBase* callInst = llvm::dyn_cast<llvm::CallBase>(callins);
        results->addIndirectBranch(functionType, callInst, true);
        results->addIndirectCallTargets(functionType, std::move(candidates), true);
    }
}

void CFGResult::addIndirectCallTarget(llvm::FunctionType* type, llvm::Function* target, bool is_virtual)
{   
    if (!is_virtual) indirectTargets[type].insert(target);
    else indirectVirtualTargets[type].insert(target);
}

void CFGResult::addIndirectBranch(llvm::FunctionType* type, llvm::CallBase* branch, bool is_virtual)
{
    if (!is_virtual) indirectBranches[type].insert(branch);
    else indirectVirtualBranches[type].insert(branch);
}

void CFGResult::addIndirectCallTargets(llvm::FunctionType* type, const FunctionSet& targets, bool is_virtual)
{   
    if (!is_virtual) indirectTargets[type].insert(targets.begin(), targets.end());
    else indirectVirtualTargets[type].insert(targets.begin(), targets.end());
}


bool CFGResult::hasIndirectTargets(llvm::FunctionType* func_ty) const
{
    return indirectTargets.find(func_ty) != indirectTargets.end();
}

const CFGResult::FunctionSet& CFGResult::getIndirectTargets(llvm::FunctionType* func_ty) const
{
    auto pos = indirectTargets.find(func_ty);
    return pos->second;
}

bool CFGResult::hasIndCSCallees(const llvm::CallSite& callSite) const
{
    return hasIndirectTargets(callSite.getFunctionType());
}

CFGResult::FunctionSet CFGResult::getIndCSCallees(const llvm::CallSite& callSite)
{
    return getIndirectTargets(callSite.getFunctionType());
}

void CFGResult::dump()
{
    llvm::raw_ostream &output= llvm::errs();

    output<<"Virtual Function CFG:\n";
    output<<"Virtual Function Branches:\n";
    for (const auto& item : indirectVirtualBranches) {
        output << "Type: " << *item.first << "\n";
        for (const auto& candidate : item.second) {
            llvm::DebugLoc DBLoc=candidate->getDebugLoc();
            //llvm::DILocation* DILoc = DBLoc.get();
            llvm::DIScope *Scope = llvm::cast<llvm::DIScope>(DBLoc->getScope());
            auto fileName = Scope->getFilename();
            output << fileName<<":"<< DBLoc.getLine()<<":"<<DBLoc.getCol()<< "\n";
        }
    }
    output<<"Virtual Function Targets:\n";
        for (const auto& item : indirectVirtualTargets) {
        output << "Type: " << *item.first << "\n";
        for (const auto& candidate : item.second) {
            output << candidate->getName() << "\n";
        }
    }

    output<<"Function Pointer CFG:\n";
    output<<"Function Pointer Branches:\n";
    for (const auto& item : indirectBranches) {
        output << "Type: " << *item.first << "\n";
        for (const auto& candidate : item.second) {
            llvm::DebugLoc DBLoc=candidate->getDebugLoc();
            //llvm::DILocation* DILoc = DBLoc.get();
            llvm::DIScope *Scope = llvm::cast<llvm::DIScope>(DBLoc->getScope());
            auto fileName = Scope->getFilename();
            output << fileName<<":"<< DBLoc.getLine()<<":"<<DBLoc.getCol()<< "\n";
        }
    }
    output<<"Function Pointer Targets:\n";
        for (const auto& item : indirectTargets) {
        output << "Type: " << *item.first << "\n";
        for (const auto& candidate : item.second) {
            output << candidate->getName() << "\n";
        }
    }
    
}

char IndirectCallSitesAnalysis::ID = 0;

IndirectCallSitesAnalysis::IndirectCallSitesAnalysis()
    : llvm::ModulePass(ID){
    results = new CFGResult();
    m_vimpl = new VirtualsImpl(results);
    m_iimpl = new IndirectsImpl(results);

}

void IndirectCallSitesAnalysis::getAnalysisUsage(llvm::AnalysisUsage& AU) const
{
    AU.addRequired<llvm::DominatorTreeWrapperPass>();
    AU.setPreservesAll();
}

bool IndirectCallSitesAnalysis::runOnModule(llvm::Module& M)
{
    //auto domTreeGetter = [this] (llvm::Function &F) {return &this->getAnalysis<llvm::DominatorTreeWrapperPass>(F).getDomTree(); };
    auto domTreeGetter = [this](llvm::Function &F) -> llvm::DominatorTree & {
    return this->getAnalysis<llvm::DominatorTreeWrapperPass>(F).getDomTree();
    };
    m_vimpl->runOnModule(M, domTreeGetter);
    m_iimpl->runOnModule(M);
    results->dump();
    return false;
}


static llvm::RegisterPass<IndirectCallSitesAnalysis> X("indirect-calls","runs indirect and virtual calls analysis");

}


