from enum import Enum
from itertools import chain


class A(Enum):
    A1 = 1
    A2 = 2
    A3 = 3
    A4 = 4

    @property
    def isodd(self):
        return self in [self.__class__.A1, self.__class__.A3]


a1 = A.A1
a2 = A.A2
a3 = A.A3
a4 = A.A4

print([a1.isodd, a2.isodd, a3.isodd, a4.isodd])
