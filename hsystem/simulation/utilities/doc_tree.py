import os
import pydoc

from simulation import algorithm
from simulation import core

class TreeNode(object):
    def __init__(self, name, parent=None, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.parent = parent
        self.children = []
        if parent is not None:
            self.parent.children.append(self)
                 
    def query_child(self, name):
        for child in self.children:
            if child.name == name:
                return child
        return None
    
    def print_node(self, i=0):
        if self.kwargs:
            s_list = [f"{k}:{w}" for k, w in self.kwargs.items()]
            s = ", ".join(s_list)
            print(f"{'----'*i}{self.name}--{s}")
        else:
            print(f"{'----'*i}{self.name}")
        for child in self.children:
            child.print_node(i+1)
            
    def to_dict(self):

        name_class = core.CLASS.get(self.name)
        if name_class.__doc__ is not None:
            new_name = self.name+" : "+name_class.__doc__
        else:
            new_name=self.name
        dct = {"name": self.name, 'label': new_name}
        dct.update(self.kwargs)
        dct["children"] = []
        for child in self.children:
            dct["children"].append(child.to_dict())
        return dct


class Tree(object):
    def __init__(self, root_name):
        self.root = TreeNode(root_name)
    
    def parse_sequence(self, seq):
        n = len(seq)
        if n == 0 or seq[0] != self.root.name:
            return
        elif n > 1:
            node = self.root
            for i in range(len(seq)-1):
                j = i+1
                child = node.query_child(seq[j])
                if child is None:
                    child = TreeNode(seq[j], node)
                node = child   

    def print_tree(self):
        self.root.print_node()
        
    def to_dict(self):
        return self.root.to_dict()
    def get_keys(self):
        return self.root


def gen_class_tree(return_dict=False):
    model_num = 0
    class_tree = Tree("Node")
    doc_dict = {}
    for name, obj in core.CLASS.items():
        seq = []
        for item in obj.__mro__[-2::-1]:
            seq.append(item.__name__)
            model_num += 1
        class_tree.parse_sequence(seq)
        doc_dict[name]=obj.__doc__
    if return_dict:
        return {'count': model_num, 'data': class_tree.to_dict()},None
    return class_tree,doc_dict

def gen_node_model_info():
    return gen_class_tree(return_dict=True)[0]

def gen_fun_tree(return_dict=False):
    model_num = 0
    fun_tree = Tree("algorithm")
    alg_path = os.path.dirname(algorithm.__file__)
    for fname in os.listdir(alg_path):
        if fname[-3:] == ".py" and fname[:2] != "__":
            fun_tree.root.children.append(TreeNode(fname[:-3]))
    for child in fun_tree.root.children:
        module = eval("algorithm."+child.name)
        for item in dir(module):
            if item[:2] != "__":
                fun = eval("algorithm."+child.name+"."+item)
                if fun.__class__.__name__ == 'function':
                    child.children.append(TreeNode(item))
                    model_num += 1
    if return_dict:
        return {'count': model_num, 'data': fun_tree.to_dict()}
    return fun_tree

def gen_algorithm_model_info():
    return gen_fun_tree(return_dict=True)

def gen_class_desc(obj_name):
    if " : " in obj_name:
        obj_name = obj_name.split(" : ")[0]
    return pydoc.render_doc(core.CLASS[obj_name], renderer=pydoc.plaintext)

def gen_fun_desc(obj_name):
    return pydoc.render_doc(eval(obj_name), renderer=pydoc.plaintext)


if __name__ == "__main__":
    # tree = gen_class_tree()
    # print(tree.to_dict())
    # tree.print_tree()
    # print(gen_class_desc('FSM'))
    res = gen_node_model_info()
    import json
    print(json.dumps(res))