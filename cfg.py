import os
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SCFI')
logger.setLevel(logging.DEBUG)




# with open('/home/readm/scfi/workload/471.omnetpp/doxygen/inherit/classbusLAN__inherit__graph.dot') as f:
#     G=pydot.graph_from_dot_data(f.read())
#     for i in G:
#         for edge in (i.get_edges()):
#             print(i.get_node(edge.get_source())[0].get('label'))
#             print(i.get_node(edge.get_destination())[0].get('label'))


class InheritGraph(dict):
    '''A dict, always give the parent name. Only support single inherit.'''
    def __init__(self, path):
        import pydot
        '''Read inherit graph file in the path'''
        logger.info('Loading inherit graph from: '+path)
        for file_name in os.listdir(path):
            if file_name.endswith("__inherit__graph.dot"):
                with open(os.path.join(path,file_name)) as f:
                    G_lst=pydot.graph_from_dot_data(f.read())
                    G=G_lst[0]
                    for edge in (G.get_edges()):
                        parent=G.get_node(edge.get_source())[0].get('label')[1:-1]
                        child =G.get_node(edge.get_destination())[0].get('label')[1:-1]
                        self[child]=parent
                        logger.debug('Inherit: %s from %s'%(child,parent))



class CFG():
    '''Label based CFG, each target/branch has tags(labels)
    Tags can be strings, int ...
    For each target: keyed by label
    For each branch: keyed by debug_loc
    Remember to add new read function for new formats'''

    def __init__(self, target=dict(), branch=dict()):
        self.target = target  # label-> [tags]
        self.branch = branch  # debug loc -> [tags]
        # remember: the tags is in a list, we support multi tags

    @classmethod
    def read_from_llvm_fastcfi(cls, path):
        with open(path) as f:
            target, branch = dict(), dict()
            for line in f:
                line = line.strip()
                if line.startswith('FastCFI:callee'):
                    info = line.replace('FastCFI:callee=', '').split('@')
                    target[info[0]] = [info[-1]]
                elif line.startswith('FastCFI:caller'):
                    info = line.replace('FastCFI:caller=', '').split('@')
                    branch[info[0]] = [info[-1]]
            valid_tags = branch.values()
            for key in [k for k in target.keys()]:
                if target[key] not in valid_tags:
                    target.pop(key)
            return cls(target=target, branch=branch)

    @classmethod
    def read_from_llvm_pass(cls, path, ignore_class_name=False, union_file='scfi_tmp.union', inherit_path='', virtual_inherit=False, only_virtual=False, to_object=False):
        import re

        inherit_graph=dict()
        if inherit_path:
            inherit_graph = InheritGraph(inherit_path)

        def _get_top_parent(s):
            if inherit_path:
                while s in inherit_graph.keys():
                    if (not to_object) and inherit_graph[s] == 'cObject':
                        return s
                    s = inherit_graph[s]
                return s
            else: return s

        def get_top_parent(s):
            retval = _get_top_parent(s)
            logger.debug('Type Inherit: %s -> %s' %(s, retval))
            return retval

        # get the parent class name
        def class_to_top(s):
            pattern = re.compile(r"\w+")
            token_lst = pattern.findall(s)
            for token in token_lst:
                if token in inherit_graph.keys() and inherit_graph[token]!= 'cObject':
                    tmp_pattern =  re.compile('\b%s\b'%token)
                    new_str = get_top_parent(token)
                    s=tmp_pattern.sub(new_str,s)
            return s

        #strip class/struct number,
        def class_strip(s):
            pattern = re.compile(r"class\.[^:]+::[^\.]+\.[\d.]+")
            lst = re.findall(pattern, s)
            for _type in lst:
                pattern = re.compile(r"class\.[^:]+::[^\.]+")
                new_type = re.match(pattern, _type).group()
                s = s.replace(_type, new_type)

            pattern = re.compile(r"struct\.[\w]+\.[\d.]+")
            lst = re.findall(pattern, s)
            for _type in lst:
                pattern = re.compile(r"struct\.[\w]+")
                new_type = re.match(pattern, _type).group()
                s = s.replace(_type, new_type)
            return s
        
        # sometimes we need union some set
        union_set=[]
        if os.path.exists(os.path.join(os.path.split(path)[0],union_file)):
            with open(os.path.join(os.path.split(path)[0],union_file)) as f:
                union_l = []
                for line in f:
                    if not line.startswith('(end)'):
                        union_l.append(line.strip())
                    else:
                        union_set.append(union_l)
                        union_l=[]


        # read the file
        with open(path) as f:
            target, branch = dict(), dict()
            # first read the cfg in type
            virtual_branch = dict()
            virtual_target = dict()
            pointer_branch = dict()
            pointer_target = dict()

            _type = ""
            items = set()
            current_set = None  # empty
            for line in f:
                if line.startswith('#'): continue # white list
                if line.strip().endswith('0:0'): continue
                if line.startswith('Virtual Function Branches:'):
                    current_set = virtual_branch
                    continue
                if line.startswith('Virtual Function Targets:'):
                    current_set = virtual_target
                    continue
                if line.startswith('Function Pointer Branches:'):
                    current_set = pointer_branch
                    continue
                if line.startswith('Function Pointer Targets:'):
                    current_set = pointer_target
                    continue
                if line.startswith('Function Pointer CFG:'):
                    current_set = None
                    continue

                if current_set == None:
                    continue
                if line.startswith('Type:'):
                    _type = class_strip(line.strip()[6:])
                    for union_lst in union_set:
                        if _type in union_lst:
                            _type=union_lst[0]
                    # print(_type)
                    continue
                try:
                    current_set[_type].add(line.strip())
                except KeyError:
                    current_set[_type] = set([line.strip()])
            
            if only_virtual: pointer_target=pointer_branch=dict()


            # remove items in Function Pointer if in Virtual Call
            rm_lst = []
            for key in pointer_branch.keys():
                if key in virtual_branch.keys():
                    rm_lst.append(key)
            for key in rm_lst:
                del pointer_branch[key]
            rm_lst = []
            for key in pointer_target.keys():
                if key in virtual_target.keys():
                    rm_lst.append(key)
            for key in rm_lst:
                del pointer_target[key]

            # update pointers to top
            inherit_lst = [pointer_branch, pointer_target]
            if virtual_inherit: 
                inherit_lst.append(virtual_target)
                inherit_lst.append(virtual_branch)
            for _set in inherit_lst:
                rm_lst = []
                for key in _set.keys():
                    if key != class_to_top(key):
                        print(len(inherit_graph), key,'->', class_to_top(key))
                        rm_lst.append(key)
                        _set[class_to_top(key)]=_set[key]
                for key in rm_lst:
                    del _set[key]


            tmp_branch = dict()
            for key in virtual_branch.keys():
                for item in virtual_branch[key]:
                    try:
                        tmp_branch[item].add(key)
                    except KeyError:
                        tmp_branch[item] = set([key])
            for key in pointer_branch.keys():
                for item in pointer_branch[key]:
                    try:
                        tmp_branch[item].add(key)
                    except KeyError:
                        tmp_branch[item] = set([key])

            # merge multi type of branchs
            # in fact, it may lose some security
            # TODO: for better security, DIVIDE not MERGE the class
            merge_type = dict()  # from type to a merge number
            merge_type_count = 0
            for item in tmp_branch.keys():
                if len(tmp_branch[item]) == 1:
                    continue
                new_type_lst = []
                for _type in tmp_branch[item]:
                    # map to new type recursely
                    new_type = _type
                    while new_type in merge_type.keys():
                        new_type = merge_type[new_type]
                    new_type_lst.append(new_type)
                new_merge_type = 'Merged_type_%d' % merge_type_count
                merge_type_count += 1
                for new_type in new_type_lst:
                    merge_type[new_type] = new_merge_type
                tmp_branch[item] = set([new_merge_type])

            target, branch = dict(), dict()
            for br_set in [virtual_branch, pointer_branch]:
                for key in br_set.keys():
                    new_type = key
                    while new_type in merge_type.keys():
                        new_type = merge_type[new_type]
                    for item in br_set[key]:
                        try:
                            branch[item].add(new_type)
                            if len(branch[item]) > 1:
                                logger.warn(
                                    'Multi-tag branch found: %s' % item)
                        except KeyError:
                            branch[item] = set([new_type])

            for tg_set in [virtual_target, pointer_target]:
                for key in tg_set.keys():
                    new_type = key
                    while new_type in merge_type.keys():
                        new_type = merge_type[new_type]
                    for item in tg_set[key]:
                        try:
                            target[item].add(new_type)
                            if len(target[item]) > 1:
                                logger.debug(
                                    'Multi-tag target found: %d %s' % (len(target[item]), item))
                        except KeyError:
                            target[item] = set([new_type])
                

        return cls(target, branch)

    def convert_filename_to_number(self, file_numbers):
        '''convert the string:y:z to x y z form'''
        for branch_loc in [k for k in self.branch.keys()]:
            try:
                new_key = str(file_numbers[branch_loc.split(':')[0]])
                new_key += ' '+' '.join(branch_loc.split(':')[1:3])
                self.branch[new_key] = self.branch[branch_loc]
                self.branch.pop(branch_loc)
            except KeyError:  # some branches in CFG do not appera in assemble file
                continue

    def dump(self,path):
        import pickle
        with open(path,'wb+') as f:
            pickle.dump(self,f)
    
    @classmethod
    def load(cls,path):
        import pickle
        with open(path,'rb') as f:
            return pickle.load(f)