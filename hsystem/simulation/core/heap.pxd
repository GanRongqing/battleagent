# cython:language_level=3
# distutils: language=c++

cpdef heappush(list heap, item)

cpdef heappop(list heap)

cpdef heapreplace(list heap, item)

cpdef heappushpop(list heap, item)

cpdef heapify(x)

cdef _heappop_max(list heap)

cdef _heapreplace_max(list heap, item)

cdef _heapify_max(x)

cdef _siftdown(list heap, int startpos, int pos)

cdef _siftup(list heap, int pos)

cdef _siftdown_max(list heap, int startpos, int pos)

cdef _siftup_max(list heap, int pos)
