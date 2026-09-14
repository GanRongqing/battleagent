import heapq
import bisect
from simulation.core import CLASS
# from simulation.core cimport heap as heapq


cdef class Node:
    """ Base class of all logic class.
    """

    def __init__(self, Node parent=None):
        """ Base class of all logic class.

        Parameters
        ----------
        parent : core.base.Node
            The parent of the current node. Set to None if the current node
            will be the root node.
        """
        assert parent is None or isinstance(parent, Node), type(parent)

        self._parent = parent

    def __str__(self):
        return f"{type(self).__name__}<{id(self)}>"

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return id(self)

    def __eq__(self, rhs):
        return id(self) == rhs if isinstance(rhs, int) else id(self) == id(rhs)

    def __lt__(self, rhs):
        return id(self) < rhs if isinstance(rhs, int) else id(self) < id(rhs)

    def __gt__(self, rhs):
        return id(self) > rhs if isinstance(rhs, int) else id(self) > id(rhs)

    property parent:
        def __get__(self):
            return self._parent
        def __set__(self, parent):
            self._parent = parent

    property root:
        def __get__(self):
            return self if self._parent is None else self._parent.root

    property id:
        def __get__(self):
            return id(self)

# CLASS.register(Node)

cdef class Heap:
    """
    Priority heap for scheduler.
    事件调度队列使用小顶堆来维护，其时间复杂度为logN，优先级最高的任务（priority值最小）总是在树的根结点
    """

    def __init__(self):
        """
        Priority heap for scheduler.
        _items : list
            用于存放调度任务 ，其中的元素为元组，该元组包含priority, _index, item三个元素
        _index : int
            用于表示任务到来的顺序号
        """
        self._items = []
        self._index = 0

    def __len__(self):
        return len(self._items)

    cpdef peek(self):
        """ Peek the smallest item on the heap.

        Returns
        -------
        priority : int
            Highest priority value.
        item : any
            Associated item with highest priority.
        """
        priority, _, item = self._items[0]
        return priority, item

    cpdef push(self, double priority, item):
        """ Add item with priority to the heap.

        Parameters
        ----------
        priority : float
            Priority value (smaller the value, higher the priority).
            在priority相等的情况下，比较_index，以此保证时间相同的情况下先push的先被pop
        item : any
            Associated item to be stored in the heap.
        """
        assert isinstance(priority, (int, float)), \
            "expect int or float, got %s" % type(priority)
        heapq.heappush(self._items, (priority, self._index, item))
        self._index += 1

    cpdef pop(self):
        """ Return the item with highest priority.

        Returns
        -------
        priority : int
            Priority value (smaller the value, higher the priority).
        item : any
            Associated item with highest priority.

        Raises
        ------
        IndexError
            If the heap is empty.
        """
        priority, _, item = heapq.heappop(self._items)
        return priority, item
    
    cdef _delete(self, items, key):
        """从self._items中删除指定的项

        Args:
            items (list): 待删除的列表
            key (lambda, optional): self._items中取出待删除元素key的方法. Defaults to lambda x:x.

        Returns:
            list: 元素是否删除成功的列表
        """
        assert isinstance(items, list) and len(set(items)) == len(items), "items需要为列表，且无重复元素"
        item_dict = {item: False for item in items}
        _new_items = []
        for item in self._items:
            k = key(item[2])
            if k in item_dict:
                assert not item_dict[k], "当前指定的k重复映射"
                item_dict[k] = True
            else:
                _new_items.append(item)
        heapq.heapify(_new_items)
        self._items = _new_items
        return [item_dict[item] for item in items]

    def delete(self, items, key=lambda x:x):
        return self._delete(items, key)

    cpdef modify(self, items):
        """修改self._items中指定的项（主要是priority）

        Args:
            items (list): [(p1, id1), (p2, id2), ]
        """

        assert isinstance(items, list)
        item_dct = {id: p for p, id in items}
        _new_items = []
        for item in self._items:
            if item[2] not in item_dct:
                _new_items.append(item)
            else:
                priority = item_dct[item[2]]
                _new_items.append((priority, item[1], item[2]))
        heapq.heapify(_new_items)
        self._items = _new_items

cdef class Bag:
    """ Ordered container.

    This container owns a sorted list of added items and supports fast item
    query by item id.
    """

    def __init__(self):
        """ Ordered container.

        This container owns a sorted list of added items and supports fast item
        query by item id.
        """
        self._items = []

    def __len__(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]

    cpdef list tolist(self):
        return self._items

    cpdef Node add(self, Node item):
        """ Add a item into the bag.

        Parameters
        ----------
        item : Node
            Ttem that will be added.

        Raises
        ------
        TypeError
            If the item object doesn't support '<' operator
        """
        assert isinstance(item, Node), type(item)

        bisect.insort(self._items, item)
        return item

    cpdef Node remove(self, Node item):
        """ remove a item.

        Parameters
        ----------
        item : Node
            Ttem that will be added.

        Raises
        ------
        TypeError
            If the item object doesn't support '<' operator
        """
        assert isinstance(item, Node), type(item)
        if item in self._items:
            self._items.remove(item)
        return item

    cpdef Node find(self, int itemid):
        """ Find the item object by its id.

        Parameters
        ----------
        item : int
            The node instance id that will be searched for.

        Returns
        -------
        item : item or None
            - Item if the itemid is recorded in the bag.
            - None if the item doesn't exist in the bag.
        """
        assert isinstance(itemid, int), type(itemid)

        index = bisect.bisect(self._items, itemid)
        # item doesn't exist in the bag ?
        if index == 0 or id(self._items[index - 1]) != itemid:
            return None
        return self._items[index - 1]
