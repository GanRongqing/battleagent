# cython:language_level=3
# distutils: language=c++

cdef class Node:
    """ Base class of all logic class.
    """
    cdef Node _parent


cdef class Heap:
    cdef list _items
    cdef int _index

    cpdef peek(self)
    cpdef push(self, double priority, item)
    cpdef pop(self)
    cdef _delete(self, items, key)
    cpdef modify(self, items)

cdef class Bag:
    cdef list _items

    cpdef list tolist(self)
    cpdef Node add(self, Node item)
    cpdef Node remove(self, Node item)
    cpdef Node find(self, int itemid)
