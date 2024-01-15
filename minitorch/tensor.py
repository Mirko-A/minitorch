from __future__ import annotations
from typing import Optional, Type
import math

from minitorch import helpers
from minitorch.storage import Storage
from minitorch.dtype import Dtype
from minitorch.settings import DEBUG

class Function:
    def __init__(self, *inputs: Tensor):
        self.inputs_need_grad = [input.requires_grad for input in inputs]
        self.output_requires_grad = True if any(self.inputs_need_grad) else False
        if self.output_requires_grad:
            self.parents = inputs

    def forward(self, *args, **kwargs) -> Tensor: assert False, f"forward not implemented for {type(self)}"
    def backward(self, *args, **kwargs) -> Tensor: assert False, f"backward not implemented for {type(self)}"

    @classmethod
    def apply(fn_ctor: Type[Function], *inputs: Tensor, **kwargs) -> Tensor: 
        # fn_ctor is the constructor of the child class from which 'apply' is called
        ctx = fn_ctor(*inputs)
        result = Tensor(ctx.forward(*[input.storage for input in inputs], **kwargs), ctx.output_requires_grad)
        
        # Keep the reference to the function which created the result
        # Used for autograd
        if ctx.output_requires_grad:
            result._ctx = ctx
        
        return result

import minitorch.ops as ops

class Tensor:
    __slots__ = ("storage", "requires_grad", "dtype", "grad", "_ctx")
    __deletable__ = ("_ctx",)

    def __init__(self, data: float | int | list | Storage, requires_grad: bool = False, dtype: Dtype = Dtype.Float):
        self.storage = data if isinstance(data, Storage) else Storage(data, dtype)

        assert self.storage.rank <= 4, \
            f"Cannot construct Tensor of rank {self.storage.rank}. Maximum supported rank is 4."

        self.requires_grad = requires_grad
        self.dtype = dtype
        self.grad: Optional[Tensor] = None
        # Internal variable used for autograd graph construction
        self._ctx: Optional[Function] = None

    @property
    def shape(self) -> list[int]:
        return self.storage.shape
    
    @property
    def rank(self) -> int:
        return self.storage.rank

    @property
    def T(self) -> Tensor:
        return self.transpose()

    #* Static Tensor generation methods
    # TODO: Implement: one_hot

    @staticmethod
    def fill(shape: list[int], value: int | float, requires_grad: bool = False, dtype: Dtype = Dtype.Int) -> Tensor:
        return Tensor(Storage.fill(shape, value, dtype), requires_grad)

    @staticmethod
    def zeros(shape: list[int], requires_grad: bool = False, dtype: Dtype = Dtype.Int) -> Tensor:
        return Tensor.fill(shape, 0, requires_grad, dtype)

    @staticmethod
    def ones(shape: list[int], requires_grad: bool = False, dtype: Dtype = Dtype.Int) -> Tensor:
        return Tensor.fill(shape, 1, requires_grad, dtype)

    @staticmethod
    def arange(start: int, end: int, requires_grad: bool = False, dtype: Dtype = Dtype.Int) -> Tensor:
        return Tensor(Storage.arange(start, end, dtype), requires_grad)

    @staticmethod
    def one_hot(n_classes, hot_class) -> Tensor:
        ...

    @staticmethod
    def randn(shape: list[int], mean: float = 0.0, std_dev: float = 1.0, requires_grad: bool = False) -> Tensor:
        return Tensor(Storage.randn(shape, mean, std_dev), requires_grad)

    @staticmethod
    def uniform(shape: list[int], low: float, high: float, requires_grad: bool = False) -> Tensor:
        return Tensor(Storage.uniform(shape, low, high), requires_grad)

    @staticmethod
    def masked_fill(input: Tensor, mask: list[bool], value: float) -> Tensor:
        if DEBUG:
            assert all(isinstance(mask_val, bool) for mask_val in mask), \
                   f"Invalid mask type provided. Expected list[bool]"
        assert len(mask) == len(input.storage.data), \
               f"Cannot mask {input.shape} Tensor with mask of length {len(mask)}"
        
        return Tensor(Storage.masked_fill(input.storage, mask, value), input.requires_grad)

    @staticmethod
    def replace(input: Tensor, target: float | int, new: float | int) -> Tensor:
        return Tensor(Storage.replace(input.storage, target, new), input.requires_grad)

    @staticmethod
    def tril(input: Tensor, diagonal: int = 0) -> Tensor:
        assert input.is_square(), "Cannot apply tril to non-square Tensors."
        assert diagonal >= -3 and diagonal < 3, \
            f"Cannot apply tril, invalid value provided for diagonal parameter: {diagonal}. Expected range [-3, 2]."
        
        return Tensor(Storage.tril(input.storage, diagonal), input.requires_grad)

    @staticmethod
    def concat(axis: int, *inputs: Tensor) -> Tensor:
        if DEBUG:
            assert all(isinstance(input, Tensor) for input in inputs), \
                f"Cannot concatenate, invalid operands provided. Expected: Tensors, got {type(inputs)}."
            
        x = inputs[0]

        for y in inputs[1:]:
            x = x.cat(axis, y)

        return x

    #* Movement methods
    
    #? NOTE: Mirko, 1. 1. 2024.
    # This function accepts a new shape as a list[int] but can
    # optionally accept any number of additional integers and
    # those will be appended to the new shape.
    def reshape(self, new_shape: list[int], *args: int) -> Tensor:
        new_shape = helpers.argfix(new_shape, *args)
        assert 0 not in new_shape, \
            f"Zeros not allowed in shape ({new_shape})."
        assert math.prod(new_shape) == math.prod(self.shape), \
            f"Cannot reshape Tensor. Number of elements must remain the same ({math.prod(new_shape)} != {math.prod(self.shape)})."
        
        return ops.Reshape.apply(self, new_shape=[s for s in new_shape])
    
    def flatten(self) -> Tensor:
        total_elements = math.prod(self.shape)

        return ops.Reshape.apply(self, new_shape=[total_elements])

    def permute(self, order: list[int]) -> Tensor:
        assert len(order) >= len(self.shape), \
                f"Cannot permute Tensor. New shape dimensionality {len(order)} is smaller than original one {len(self.shape)}"
        
        x = self
        shape_diff = len(order) - len(x.shape)
        
        if shape_diff > 0:
            x = Tensor.pad_shapes(shape_diff, x)

        return ops.Permute.apply(x, order=order)

    def transpose(self, axis0 = -2, axis1 = -1) -> Tensor:
        x = self
        shape_len = len(x.shape)

        if shape_len < 2:
            x = Tensor.pad_shapes(2 - shape_len, x)

        order = [i for i in range(len(x.shape))]
        order[axis0], order[axis1] = order[axis1], order[axis0]

        return ops.Permute.apply(x, order=order)

    #* Mutate methods
    
    def pad(self, axis: int, pad_sizes: tuple[int, int]) -> Tensor:
        if DEBUG:
            assert isinstance(pad_sizes, tuple) and all(isinstance(size, int) for size in pad_sizes), \
                    f"Cannot pad, pad sizes expected type is tuple[int, int] but got type{type(pad_sizes)}."

        # Negative axes allowed
        if axis < 0:
            axis = len(self.shape) + axis
        
        return ops.Pad.apply(self, axis=axis, pad_sizes=pad_sizes)

    def shrink(self, axis: int, shrink_sizes: tuple[int, int]) -> Tensor:
        if DEBUG:
            assert isinstance(shrink_sizes, tuple) and all(isinstance(dim, int) for dim in shrink_sizes), \
                    f"Cannot shrink, new shape expected type is tuple[int, ...] but got type{shrink_sizes}."
        assert sum(shrink_sizes) < self.shape[axis], \
            f"Cannot shrink, shrink sizes are {shrink_sizes} but size of dimension[{axis}] is {self.shape[axis]}. Operation would create an empty row."

        # Negative axes allowed
        if axis < 0:
            axis = len(self.shape) + axis

        return ops.Shrink.apply(self, axis=axis, shrink_sizes=shrink_sizes)
    
    def expand(self, new_shape: list[int]) -> Tensor:
        if DEBUG:
            assert isinstance(new_shape, list) and all(isinstance(dim, int) for dim in new_shape), \
                    f"Cannot expand, new shape expected type is tuple[int, ...] but got type{new_shape}."
        assert len(new_shape) >= len(self.shape), \
            f"Cannot expand, new shape dimensionality {new_shape} is smaller than original one {self.shape}."
            
        x = self
        shape_diff = len(new_shape) - len(x.shape)
        
        if shape_diff > 0:
            x = Tensor.pad_shapes(shape_diff, x)

        for dim_idx in range(len(x.shape)):
            if x.shape[dim_idx] != new_shape[dim_idx]:
                assert x.shape[dim_idx] == 1, \
                    f"Cannot expand along ({dim_idx}) a non-singular axis ({x.shape[dim_idx]} != 1)."
                
                x = ops.Expand.apply(x,  axis=dim_idx, expanded_size=new_shape[dim_idx])

        
        return x
    
    def cat(self, axis: int, other: Tensor) -> Tensor:
        x, y = self, other

        # Negative axes allowed
        if axis < 0:
            axis = len(self.shape) + axis
            
        if DEBUG:
            assert isinstance(y, Tensor), \
                f"Cannot concatenate, invalid operands provided. Expected: Tensors, got {type(y)}."
        assert all(x_dim == y_dim for dim_idx, (x_dim, y_dim) in enumerate(zip(x.shape, y.shape)) if dim_idx != axis), \
            f"Cannot concatenate, both Tensors must have the same shape along all axes except the one they're being concatenated along ({x.shape}, {y.shape})."

        x_pad_size = y.shape[axis]
        y_pad_size = x.shape[axis]
        x = x.pad(axis, (0, x_pad_size))
        y = y.pad(axis, (y_pad_size, 0))

        return x + y

    #* Unary operations

    def neg(self) -> Tensor:
        return ops.Neg.apply(self)

    def log(self) -> Tensor:
        return ops.Log.apply(self)

    def log2(self) -> Tensor:
        return ops.Log2.apply(self)
    
    # Reduce operations

    def sum(self, axis: Optional[int] = None, keepdims: bool = False) -> Tensor:
        x = self

        def _sum(t: Tensor, axis: int, keepdims: bool = False) -> Tensor:
            if DEBUG:
                assert isinstance(axis, int), f"Cannot calculate sum, invalid axis provided. Expected int but got {type(axis)}."
            assert abs(axis) < len(self.shape), f"Cannot calculate sum, invalid axis provided. Tensor shape is {self.shape} but {axis}th dimension was provided."

            # Negative axes allowed
            if axis < 0:
                axis = len(self.shape) + axis

            shape_squeezed = [s for i,s in enumerate(t.shape) if i != axis]
            reuslt = ops.Sum.apply(t, axis=axis)

            return reuslt if keepdims or axis is None else ops.Reshape.apply(reuslt, new_shape=shape_squeezed)
        
        if axis is not None:
            return _sum(x, axis, keepdims)
        else:
            for axis_idx in range(len(self.shape)):
                x = _sum(x, axis_idx, keepdims=True)

            if keepdims:
                return x
            else:
                return ops.Reshape.apply(x, new_shape=[1])
        
    def mean(self, axis: Optional[int] = None, keepdims: bool = False) -> Tensor:
        _sum = self.sum(axis, keepdims=keepdims)

        if axis is not None:
            return _sum / float(self.shape[axis])
        else:
            return _sum / float(math.prod(self.shape))

    def std(self, axis: Optional[int] = None, keepdims: bool = False) -> Tensor:
        # Number of samples
        N = math.prod(self.shape) if axis is None else self.shape[axis]
        # Bessel's correction (taking into account the case where N = 1)
        N = max(1, N - 1)

        _mean = self.mean(axis, True)
        deviation = ((self - _mean) ** 2.0)
        
        return (deviation.sum(axis, keepdims) / float(N)).sqrt()

    def var(self, axis: Optional[int] = None, keepdims: bool = False) -> Tensor:
        return self.std(axis, keepdims) ** 2.0

    #* Binary operations

    def add(self, other: Tensor, reverse: bool = False) -> Tensor:
        x, y = self, other

        if reverse:
            x, y = y, x

        return ops.Add.apply(*x._broadcasted(y))
    
    def sub(self, other: Tensor, reverse: bool = False) -> Tensor:
        x, y = self, other

        if reverse:
            x, y = y, x

        return ops.Sub.apply(*x._broadcasted(y))

    def mul(self, other: Tensor, reverse: bool = False) -> Tensor:
        x, y = self, other

        if reverse:
            x, y = y, x

        return ops.Mul.apply(*x._broadcasted(y))
    
    def div(self, other: Tensor, reverse: bool = False) -> Tensor:
        x, y = self, other

        if reverse:
            x, y = y, x

        return ops.Div.apply(*x._broadcasted(y))

    def pow(self, other: Tensor, reverse: bool = False) -> Tensor:
        x, y = self, other

        if reverse:
            x, y = y, x

        return ops.Pow.apply(*x._broadcasted(y), is_exp=reverse)

    def exp(self) -> Tensor:
        return math.e ** self
    
    def sqrt(self) -> Tensor:
        return self ** 0.5

    def matmul(self, other: Tensor) -> Tensor:
        x, y = self, other
        n1, n2 = len(x.shape), len(y.shape)
        
        assert n1 > 1 and n2 > 1, \
            f"both arguments to matmul need to be at least 2D, but they are {n1}D and {n2}D."
        assert x.shape[-1] == y.shape[-2], \
            f"Input Tensor shapes {x.shape} and {y.shape} cannot be multiplied ({x.shape[-1]} != {y.shape[-2]})"
        
        #? NOTE: Mirko, 24. 12. 2023 
        # Example to ilustrate what is happening below:
        # let x.shape = [3, 3]  &  y.shape = [3, 2]
        # x.shape = [3, 1, 3]
        # y.shape = [1, 3, 2]^T = [1, 2, 3]
        # Broadcasted: 
        # x.shape = [3, 2, 3]
        # y.shape = [3, 2, 3]
        # Performing element-wise product and then sum over the last
        # dimension (rows) is essentially giving the same result as
        # matrix multiplication.
        x = self.reshape(*self.shape[0:-1], 1, self.shape[-1])
        y = y.reshape(*y.shape[0:-2], 1, *y.shape[-2:]).transpose()

        return (x*y).sum(-1)

    #* Activation functions
    
    def sigmoid(self) -> Tensor:
        return ops.Sigmoid.apply(self)
    
    def tanh(self) -> Tensor:
        return 2.0 * (2.0 * self).sigmoid() - 1.0

    def relu(self) -> Tensor:
        return ops.Relu.apply(self)
    
    def softmax(self, axis = -1) -> Tensor:
        self_exp = self.exp()

        return self_exp / self_exp.sum(axis, keepdims=True)

    #* Cost functions

    def MSE(self, target: Tensor, axis: Optional[int] = None) -> Tensor:
        if DEBUG:
            assert isinstance(target, Tensor), \
                f"Cannot calculate MSE loss, invalid target type. Expected Tensor, got {type(target)}."

        square_error = (self - target) ** 2.0
        return square_error.mean(axis)

    def cross_entropy(self, target: Tensor, axis: Optional[int] = None) -> Tensor:
        if DEBUG:
            assert isinstance(target, Tensor), \
                f"Cannot calculate Cross Entropy loss, invalid target type. Expected Tensor, got {type(target)}."

        #? NOTE: Mirko, 25. 12. 2023. 
        # PyTorch uses natural log here, might be relevant later
        log_input = self.log()
        return -(target * log_input).sum(axis)

    #* Backpropagation

    def toposort(self):
        def _toposort(node: Tensor, visited: set[Tensor], nodes: list[Tensor]):
            visited.add(node)

            if getattr(node, "_ctx", None):
                for parent in node._ctx.parents:
                    if parent not in visited: 
                        _toposort(parent, visited, nodes)

                nodes.append(node)

            return nodes
      
        return _toposort(self, set(), [])

    def backward(self):
        assert self.is_scalar(), f"Backward can only be called for scalar tensors, but it has shape {self.shape})"

        self.grad = Tensor(1.0, requires_grad=False)
        autograd_graph = self.toposort()

        for node in reversed(autograd_graph):
            assert node.grad is not None

            grads = node._ctx.backward(node.grad.storage)
            grads = [Tensor(g, requires_grad=False) if g is not None else None
                        for g in ([grads] if len(node._ctx.parents) == 1 else grads)]
            
            for parent, grad in zip(node._ctx.parents, grads):
                if grad is not None and parent.requires_grad:
                    assert grad.shape == parent.shape, f"Grad shape must match Tensor shape, {grad.shape} != {parent.shape} ({node._ctx})"
                    parent.grad = grad if parent.grad is None else (parent.grad + grad)
            
            del node._ctx

    #* Broadcasting

    def _broadcasted(self, y: Tensor) -> tuple[Tensor, Tensor]:
        x: Tensor = self
    
        if (xshape:=x.shape) == (yshape:=y.shape):
            return (x, y)
        
        shape_delta = len(xshape) - len(yshape)

        if shape_delta > 0:
            new_shape = [1] * shape_delta + yshape 
            y = y.reshape(new_shape)
        elif shape_delta < 0:
            new_shape = [1] * -shape_delta + xshape 
            x = x.reshape(new_shape)

        if (xshape:=x.shape) == (yshape:=y.shape): 
            return (x, y)
    
        shape_ret = [max(x, y) for x, y in zip(xshape, yshape)]

        if xshape != shape_ret: 
            x = x.expand(shape_ret)
        if yshape != shape_ret: 
            y = y.expand(shape_ret)

        return (x, y)

    #* Unary operator magic methods

    def __neg__(self) -> Tensor:
        return self.neg()

    def __getitem__(self, keys: tuple[int, ...]) -> float:
        assert len(keys) == len(self.shape), \
            f"Cannot retreive an element from Tensor with given key: {keys}. Key must match Tensor's shape ({self.shape})."
        return self.data[keys]
    
    #* Binary operator magic methods

    def __add__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor addition, operand types do not match ({self.dtype, other.dtype})."

        return self.add(other)
    
    def __radd__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor addition, operand types do not match ({self.dtype, other.dtype})."

        return self.add(other, True)
    
    def __iadd__(self, other) -> Tensor: 
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor addition, operand types do not match ({self.dtype, other.dtype})."

        return self.assign(self.add(other))

    def __sub__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor subtraction, operand types do not match ({self.dtype, other.dtype})."

        return self.sub(other)

    def __rsub__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor subtraction, operand types do not match ({self.dtype, other.dtype})."

        return self.sub(other, True)

    def __isub__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor subtraction, operand types do not match ({self.dtype, other.dtype})."

        return self.assign(self.sub(other))

    def __mul__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor multiplication, operand types do not match ({self.dtype, other.dtype})."

        return self.mul(other)
    
    def __rmul__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor multiplication, operand types do not match ({self.dtype, other.dtype})."

        return self.mul(other, True)

    def __imul__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor multiplication, operand types do not match ({self.dtype, other.dtype})."

        return self.assign(self.mul(other))

    def __truediv__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor division, operand types do not match ({self.dtype, other.dtype})."

        return self.div(other)
    
    def __rtruediv__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor division, operand types do not match ({self.dtype, other.dtype})."

        return self.div(other, True)
    
    def __itruediv__(self, other) -> Tensor: 
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor division, operand types do not match ({self.dtype, other.dtype})."

        return self.assign(self.div(other))

    def __pow__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor exponentiation, operand types do not match ({self.dtype, other.dtype})."

        return self.pow(other)

    def __rpow__(self, other) -> Tensor:
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor exponentiation, operand types do not match ({self.dtype, other.dtype})."

        return self.pow(other, True)
    
    def __ipow__(self, other) -> Tensor: 
        if not isinstance(other, Tensor): 
            other = Tensor(other)
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor exponentiation, operand types do not match ({self.dtype, other.dtype})."

        return self.assign(self.pow(other))

    def __matmul__(self, other) -> Tensor:
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor matrix multiplication, operand types do not match ({self.dtype, other.dtype})."
        if DEBUG:
            assert isinstance(other, Tensor), f"Cannot perform Tensor multiplication with type {type(other)}"
        
        return self.matmul(other)
    
    def __imatmul__(self, other) -> Tensor: 
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot perform Tensor matrix multiplication, operand types do not match ({self.dtype, other.dtype})."
        if DEBUG:
            assert isinstance(other, Tensor), f"Cannot perform Tensor multiplication with type {type(other)}"
        
        return self.assign(self.matmul(other))

    def __eq__(self, other) -> bool | list[bool]:
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot check for Tensor equality (equal), operand types do not match ({self.dtype, other.dtype})."
        if isinstance(other, Tensor):
            assert self.shape == other.shape, f"Cannot compare {self.shape} and {other.shape} Tensors. Shapes must match."

            return self.storage == other.storage
        elif isinstance(other, (int, float)):
            return self.storage == other
        else:
            assert False, f"Invalid type for Tensor equality: {type(other)}. Expected Tensor, int or float."

    def __lt__(self, other) -> list[bool]:
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot check for Tensor equality (less than), operand types do not match ({self.dtype, other.dtype})."
        if DEBUG:
            assert isinstance(other, (int, float)), f"Invalid type for Tesnor less-than: {type(other)}. Expected int or float."

        return self.storage < other
    
    def __gt__(self, other) -> list[bool]:
        if DEBUG:
            assert self.dtype == other.dtype, \
                f"Cannot check for Tensor equality (greater than), operand types do not match ({self.dtype, other.dtype})."
        if DEBUG:
            assert isinstance(other, (int, float)), f"Invalid type for Tesnor greater-than: {type(other)}. Expected int or float."

        return self.storage > other

    def __hash__(self) -> int:
        return id(self)

    #* Data handlers

    #? NOTE: Mirko, 24. 12. 2023
    # This function shall be used whenever a Tensor needs to be
    # modified inplace. It is essentially a shallow copy.
    # Other use case for this function is when traversing a 
    # collection of tensors (i.e. list of Tensors that repre-
    # sent parameters of an NN module) and needing to update
    # the Tensors from there.
    def assign(self, x) -> Tensor:
        if not isinstance(x, Tensor): 
            x = Tensor(x)
        assert self.shape == x.shape, f"Assign shape mismatch {self.shape} != {x.shape}."
        assert not x.requires_grad

        self.storage = x.storage
        
        return self

    #? NOTE: Mirko, 24. 12. 2023
    # This function shall be used to detach the Tensor from
    # the autograd graph. It is mostly used in the NN modules
    # to use data from the Tensors without adding those operations
    # to the graph.
    def detach(self) -> Tensor: 
        return Tensor(self.storage)

    #* Utility
    
    #? NOTE: Mirko, 25. 12. 2023
    # Some reshape operations require the Tensors shape
    # to match the provided shape. This helper fn can
    # be used to pad the Tensor with singular dimensions
    # on the left (e.g. [m, n] -> [1, m, n]).
    @staticmethod
    def pad_shapes(shape_diff: int, x: Tensor) -> Tensor:
        padded_shape = [1] * shape_diff + x.shape
        return ops.Reshape.apply(x, new_shape=padded_shape)

    #? NOTE: Mirko, 25. 12. 2023
    # Some reshape operations require the Tensors shape
    # to match the provided shape. This helper fn can
    # be used to squeeze the singular dimensions of the
    # Tensor on the left (e.g. [1, m, n] -> [m, n]).
    @staticmethod
    def squeeze_shapes(shape_diff: int, x: Tensor) -> Tensor:
        squeezed_shape = x.shape[shape_diff:]
        return ops.Reshape.apply(x, new_shape=squeezed_shape)

    def is_scalar(self) -> bool:
        return self.storage.is_scalar()
    
    def is_square(self) -> bool:
        assert len(self.shape) >= 2, f"Cannot check for squareness on a {len(self.shape)}D Tensor. Expected 2D or higher."
        return self.storage.is_square()

    def __repr__(self) -> str:
        return f"<Tensor: {self.storage.buffer} with grad {self.grad.storage.buffer if self.grad else None}>"
