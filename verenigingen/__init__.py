__version__ = "0.0.5"

# Import overrides to apply monkey patches
try:
    from . import overrides
    from .overrides import sales_invoice
except ImportError:
    pass
