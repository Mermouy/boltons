# -*- coding: utf-8 -*-

from bisect import bisect_left
from itertools import chain, islice
import operator
from math import log as math_log

try:
    from compat import make_sentinel
    _MISSING = make_sentinel(var_name='_MISSING')
except ImportError:
    _MISSING = object()


# TODO: __delitem__, __setitem__, index
# TODO: sorted version
# TODO: inherit from list


class BarrelList(object):
    def __init__(self, iterable=None, **kw):
        self.lists = [[]]
        self._size_factor = kw.pop('size_factor', 1520)
        if iterable:
            self.extend(iterable)

    @property
    def _cur_size_limit(self):
        len_self, size_factor = len(self), self._size_factor
        return int(round(size_factor * math_log(len_self + 2, 2)))

    def _translate_index(self, index):
        if index < 0:
            index += len(self)
        rel_idx, lists = index, self.lists
        for list_idx in range(len(lists)):
            len_list = len(lists[list_idx])
            if rel_idx < len_list:
                break
            rel_idx -= len_list
        if rel_idx < 0:
            return None, None
        return list_idx, rel_idx

    def _balance_list(self, list_idx):
        if list_idx < 0:
            list_idx += len(self.lists)
        cur_list, len_self = self.lists[list_idx], len(self)
        size_limit = self._cur_size_limit
        if len(cur_list) > size_limit:
            half_limit = size_limit / 2
            while len(cur_list) > half_limit:
                next_list_idx = list_idx + 1
                self.lists.insert(next_list_idx, cur_list[-half_limit:])
                del cur_list[-half_limit:]
            return True
        return False

    def insert(self, index, item):
        if len(self.lists) == 1:
            self.lists[0].insert(index, item)
            self._balance_list(0)
        list_idx, rel_idx = self._translate_index(index)
        if list_idx is None:
            raise IndexError()
        self.lists[list_idx].insert(rel_idx, item)
        self._balance_list(list_idx)
        return

    def append(self, item):
        self.lists[-1].append(item)

    def extend(self, iterable):
        self.lists[-1].extend(iterable)

    def pop(self, *a):
        lists = self.lists
        if len(lists) == 1 and not a:
            return self.lists[0].pop()
        index = a and a[0]
        if index == () or index is None or index == -1:
            ret = lists[-1].pop()
            if len(lists) > 1 and not lists[-1]:
                lists.pop()
        else:
            list_idx, rel_idx = self._translate_index(index)
            if list_idx is None:
                raise IndexError()
            ret = lists[list_idx].pop(rel_idx)
            self._balance_list(list_idx)
        return ret

    def count(self, item):
        return sum([cur.count(item) for cur in self.lists])

    def iter_slice(self, start, stop, step=None):
        iterable = self  # TODO: optimization opportunities abound
        # start_list_idx, stop_list_idx = 0, len(self.lists)
        if start is None:
            start = 0
        if stop is None:
            stop = len(self)
        if step is not None and step < 0:
            step = -step
            start, stop = -start, -stop - 1
            iterable = reversed(self)
        if start < 0:
            start += len(self)
            # start_list_idx, start_rel_idx = self._translate_index(start)
        if stop < 0:
            stop += len(self)
            # stop_list_idx, stop_rel_idx = self._translate_index(stop)
        return islice(iterable, start, stop, step)

    def del_slice(self, start, stop, step=None):
        if step is not None and abs(step) > 1:  # punt
            new_list = chain(self.iter_slice(0, start, step),
                             self.iter_slice(stop, None, step))
            self.lists[0][:] = new_list
            self._rebalance_list(0)
            return
        if start is None:
            start = 0
        if stop is None:
            stop = len(self)
        start_list_idx, start_rel_idx = self._translate_index(start)
        stop_list_idx, stop_rel_idx = self._translate_index(stop)
        if start_list_idx is None:
            raise IndexError()
        if stop_list_idx is None:
            raise IndexError()

        if start_list_idx == stop_list_idx:
            del self.lists[start_list_idx][start_rel_idx:stop_rel_idx]
        elif start_list_idx < stop_list_idx:
            del self.lists[start_list_idx + 1:stop_list_idx]
            del self.lists[start_list_idx][start_rel_idx:]
            del self.lists[stop_list_idx][:stop_rel_idx]
        else:
            assert False, ('start list index should never translate to'
                           ' greater than stop list index')

    @classmethod
    def from_iterable(cls, it):
        return cls(it)

    def __iter__(self):
        return chain(*self.lists)

    def __reversed__(self):
        return chain.from_iterable(reversed(l) for l in reversed(self.lists))

    def __len__(self):
        return sum([len(l) for l in self.lists])

    def __contains__(self, item):
        for cur in self.lists:
            if item in cur:
                return True
        return False

    def __getitem__(self, index):
        try:
            start, stop, step = index.start, index.stop, index.step
        except AttributeError:
            index = operator.index(index)
        else:
            iter_slice = self.iter_slice(start, stop, step)
            return self.from_iterable(iter_slice)
        list_idx, rel_idx = self._translate_index(index)
        if list_idx is None:
            raise IndexError()
        return self.lists[list_idx][rel_idx]

    def __delitem__(self, index):
        try:
            start, stop, step = index.start, index.stop, index.step
        except AttributeError:
            index = operator.index(index)
        else:
            self.del_slice(start, stop, step)
            return
        list_idx, rel_idx = self._translate_index(index)
        if list_idx is None:
            raise IndexError()
        del [list_idx][rel_idx]


    def __setitem__(self, index, item):
        try:
            start, stop, step = index.start, index.stop, index.step
        except AttributeError:
            index = operator.index(index)
        else:
            iter_slice = self.iter_slice(start, stop, step)
            return self.from_iterable(iter_slice)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def sort(self):
        # poor pythonist's mergesort, it's faster than sorted(self)
        # when the lists average larger than 512 items
        if len(self.lists) == 1:
            self.lists[0].sort()
        else:
            self.lists[0] = sorted(chain(*[sorted(l) for l in self.lists]))
            self._balance_list(0)


class SortedBarrelList(object):
    pass

# Tests

def main():
    import os

    bl = BarrelList()
    bl.insert(0, 0)
    bl.insert(1, 1)
    bl.insert(0, -1)
    bl.extend(range(100000))
    bl._balance_list(0)
    bl.pop(50000)

    rands = [ord(i) * x for i, x in zip(os.urandom(1024), range(1024))]
    bl2 = BarrelList(rands)
    bl2.sort()
    print bl2[:-10:-1]

    bl3 = BarrelList(range(int(1e5)))
    for i in range(10000):
        bl3.insert(0, bl3.pop(len(bl3) / 2))

    del bl3[10:1000]
    import pdb;pdb.set_trace()
    del bl3[:5000]
    import pdb;pdb.set_trace()

from collections import defaultdict
import gc

def tune():
    from timeit import timeit
    old_size_factor = size_factor = 512
    all_times = defaultdict(list)
    min_times = {}
    step = 512
    while abs(step) > 4:
        gc.collect()
        for x in range(3):
            tottime = timeit('bl.insert(0, bl.pop(len(bl)/2))',
                             "from listutils import BarrelList; bl = BarrelList(range(int(1e5)), size_factor=%s)" % size_factor,
                             number=10000)
            all_times[size_factor].append(tottime)
        min_time = round(min(all_times[size_factor]), 3)
        min_times[size_factor] = min_time
        print size_factor, min_time, step
        if min_time > (min_times[old_size_factor] + 0.005):
            step = -(step)/2
        old_size_factor = size_factor
        size_factor += step
    print tottime


if __name__ == '__main__':
    try:
        main() #tune()
    except Exception as e:
        import pdb;pdb.post_mortem()
        raise