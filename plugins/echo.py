# sourcery skip: avoid-builtin-shadow
import __utils__ as utils

__protocol__ = 0
__name__ = "Echo"
__version__ = "0.1.1"
__description__ = "A simple echo protocol that returns the received data."
__author__ = "Kellen"
__last_updated__ = "2025-05-13"
__license__ = "MPL 2.0"

def main(*args,**kwargs):
    return utils.Protocol()