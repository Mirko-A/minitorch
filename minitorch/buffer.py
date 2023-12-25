from __future__ import annotations
from typing import Optional
from enum import Enum, auto
import numpy as np
import math

#! WARN: Mirko, 24. 12. 2023
# In order for everything to work as expected, MiniBuffer data
# must remain contiguous at all times. That means that operations
# which involve permuting the MiniBuffer must be, at the end, fo-
# llowed by a neutral operation (addition with 0, multiplication
# with 1) in order to create a new, contiguous MiniBuffer from the
# current one's data.

class MiniBuffer:
    class UnaryOp(Enum):
        NEG  = 0
        LOG  = auto()
        LOG2 = auto()

    class BinaryOp(Enum):
        ADD = 0
        SUB = auto()
        MUL = auto()
        DIV = auto()
        POW = auto()
        MAX = auto()

    class ReshapeOp(Enum):
        PAD = 0
        SHRINK = auto()

    class CmpOp(Enum):
        LT = 0
        EQ = auto()
        GT = auto()

    def __init__(self, 
                 data: list[float], 
                 shape: tuple[int, ...], 
                 strides: Optional[tuple[int, ...]] = None):
        assert isinstance(data, list) and all(isinstance(value, float) for value in data), \
                f"Cannot construct buffer. Expected data type is list[float] but got: {type(data)}."
        assert isinstance(shape, tuple) and all(isinstance(dim, int) for dim in shape), \
                f"Cannot construct buffer. Expected shape type is tuple[int, ...] but got {type(shape)}"
        
        self.data = data
        self.shape = shape

        if strides is None:
            self.strides = MiniBuffer.get_strides_from_shape(shape)
        else:
            self.strides = strides

    #* Static MiniBuffer generation operations

    @staticmethod
    def np_load(data: list) -> MiniBuffer:
        _np = np.array(data)
        shape = ()

        for shape_n in _np.shape:
            shape += (shape_n,)
        
        return MiniBuffer(_np.reshape(-1).astype(np.float32).tolist(), shape)

    @staticmethod
    def fill(shape: tuple[int, ...], value: float | int) -> MiniBuffer:
        if isinstance(value, int):
            value = float(value)
            
        total_elements = math.prod(shape)

        return MiniBuffer([value] * total_elements, shape)

    @staticmethod
    def replace(input: MiniBuffer, target: float, new: float) -> MiniBuffer:
        out_data = []
        
        for val in input.data:
            if val == target:
                out_data.append(new)
            else:
                out_data.append(val)

        return MiniBuffer(out_data, input.shape)

    @staticmethod
    def full_like(input: MiniBuffer, value: float | int) -> MiniBuffer:
        if isinstance(value, int):
            value = float(value)

        return MiniBuffer.fill(input.shape, value)

    @staticmethod
    def masked_fill(input: MiniBuffer, mask: list[bool], value: float) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_masked_fill(0,
                                                             0,
                                                             mask,
                                                             value,
                                                             input)
        
        return MiniBuffer(out_data, input.shape)

    @staticmethod
    def tril(input: MiniBuffer, diagonal: int) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_tril(0,
                                                      0,
                                                      diagonal,
                                                      input)
        
        return MiniBuffer(out_data, input.shape)

    #* Unary operations

    def neg(self) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, ),
                                                          MiniBuffer.UnaryOp.NEG,
                                                          self)

        return MiniBuffer(out_data, self.shape)

    def log(self) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, ),
                                                          MiniBuffer.UnaryOp.LOG,
                                                          self)

        return MiniBuffer(out_data, self.shape)

    def log2(self) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, ),
                                                          MiniBuffer.UnaryOp.LOG2,
                                                          self)

        return MiniBuffer(out_data, self.shape)

    #* Reduce operations

    def sum(self, axis: int) -> MiniBuffer:
        x = self

        # Same as input but with a 1 at the sum axis index
        out_shape = [1 if dim_idx == axis else self.shape[dim_idx] for dim_idx in range(len(self.shape))]
        dim_order = [i for i in range(len(self.shape))]

        # Permute so sum axis is last
        dim_order[axis], dim_order[-1] = dim_order[-1], dim_order[axis]
        out_shape[axis], out_shape[-1] = out_shape[-1], out_shape[axis]
        x = x.permute(dim_order)
        
        x = MiniBuffer(MiniBuffer._traverse_dims_and_sum_along_last(0,
                                                                    0,
                                                                    x), tuple(out_shape))
        
        # Permute back to original
        out_shape[axis], out_shape[-1] = out_shape[-1], out_shape[axis]
        result = x.permute(dim_order)

        # Hack to make a contiguous MiniBuffer again
        return (result + MiniBuffer.full_like(result, 0))
        
    #* Binary operations

    def add(self, other: MiniBuffer) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, 0),
                                                          MiniBuffer.BinaryOp.ADD,
                                                          self, other)

        return MiniBuffer(out_data, self.shape)
    
    def sub(self, other: MiniBuffer) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, 0),
                                                          MiniBuffer.BinaryOp.SUB,
                                                          self, other)

        return MiniBuffer(out_data, self.shape)

    def mul(self, other: MiniBuffer) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, 0),
                                                          MiniBuffer.BinaryOp.MUL,
                                                          self, other)
    
        return MiniBuffer(out_data, self.shape)
    
    def div(self, other: MiniBuffer) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, 0),
                                                          MiniBuffer.BinaryOp.DIV,
                                                          self, other)

        return MiniBuffer(out_data, self.shape)
    
    def pow(self, other: MiniBuffer) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, 0),
                                                          MiniBuffer.BinaryOp.POW,
                                                          self, other)

        return MiniBuffer(out_data, self.shape)
    
    def max(self, other: MiniBuffer) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_op(0,
                                                          (0, 0),
                                                          MiniBuffer.BinaryOp.MAX,
                                                          self, other)

        return MiniBuffer(out_data, self.shape)

    def is_equal_to(self, target: MiniBuffer) -> bool:
        return MiniBuffer._traverse_dims_and_compare(0,
                                                     (0, 0),
                                                     self,
                                                     target)

    def is_elementwise_greater_than(self, target: float) -> list[bool]:
        return MiniBuffer._traverse_dims_and_compare_elementwise(0,
                                                                 0,
                                                                 MiniBuffer.CmpOp.GT,
                                                                 self,
                                                                 target)
    
    def is_elementwise_less_than(self, target: float) -> list[bool]:
        return MiniBuffer._traverse_dims_and_compare_elementwise(0,
                                                                 0,
                                                                 MiniBuffer.CmpOp.LT,
                                                                 self,
                                                                 target)
    
    def is_elementwise_equal_to(self, target: float) -> list[bool]:
        return MiniBuffer._traverse_dims_and_compare_elementwise(0,
                                                                 0,
                                                                 MiniBuffer.CmpOp.EQ,
                                                                 self,
                                                                 target)

    #* Movemenet operations

    def reshape(self, new_shape: tuple[int, ...]) -> MiniBuffer:
        return MiniBuffer(self.data, new_shape)
    
    def flatten(self) -> MiniBuffer:
        total_elements = math.prod(self.shape)

        return MiniBuffer(self.data, (total_elements, ))

    def permute(self, order: tuple[int, ...]) -> MiniBuffer:
        new_dims = ()
        new_strides = ()

        for ord in order:
            new_dims += (self.shape[ord],)
            new_strides += (self.strides[ord],)

        result = MiniBuffer(self.data, new_dims, strides=new_strides)

        # Hack to make a contiguous MiniBuffer again
        return (result + MiniBuffer.full_like(result, 0))

    #* Reshape methods
    
    #? NOTE: Mirko, 24. 12. 2023 
    # These are different from the reshape() fn. These operations
    # add/remove elements of the tensor whereas the reshape() fn just
    # changes the shape without modifying the elements.
    
    def pad(self, new_shape: tuple[int, ...]) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_reshape_op(0,
                                                                  0,
                                                                  MiniBuffer.ReshapeOp.PAD,
                                                                  new_shape,
                                                                  self)

        return MiniBuffer(out_data, new_shape)
    
    def shrink(self, new_shape: tuple[int, ...]) -> MiniBuffer:
        out_data = MiniBuffer._traverse_dims_and_apply_reshape_op(0,
                                                                  0,
                                                                  MiniBuffer.ReshapeOp.SHRINK,
                                                                  new_shape,
                                                                  self)

        return MiniBuffer(out_data, new_shape)

    def expand(self, axis: int, expanded_size: int) -> MiniBuffer:
        out_data = self.data * expanded_size

        out_shape = [dim for dim in self.shape]
        out_shape[axis] = expanded_size

        #? NOTE: Mirko, 24. 12. 2023 
        # Since we're just multiplying the data array by
        # expanded_size, somehow we need to preserve the
        # meaning of the original shape and strides. Other-
        # wise, expanding a 1x3 and a 3x1 tensor would res-
        # ult in the same output, which is wrong.
        # The correct strides for the output are same as
        # the input strides, with the stride at position
        # pos=expansion_axis being the product of all dims
        # of the original shape except the one we're expan-
        # ding along. This makes sense because we expand by
        # simply duplicating the original data expanded_size
        # times.
        out_strides = [stride for stride in self.strides]
        corrected_input_shape = [1 if i == axis else self.shape[i] for i in range(len(self.shape))]
        out_strides[axis] = math.prod(corrected_input_shape)

        result = MiniBuffer(out_data, tuple(out_shape), tuple(out_strides))

        # Hack to make a contiguous MiniBuffer again
        return (result + MiniBuffer.full_like(result, 0))

    #* Unary operator magic methods

    def __neg__(self):
        return self.neg()

    #* Binary operator magic methods

    def __add__(self, other):
        assert isinstance(other, MiniBuffer), f"Cannot perform addition with MiniBuffer and {type(other)}."

        return self.add(other)
    
    def __sub__(self, other):
        assert isinstance(other, MiniBuffer), f"Cannot perform subtraction with MiniBuffer and {type(other)}."

        return self.sub(other)

    def __mul__(self, other):
        assert isinstance(other, MiniBuffer), f"Cannot perform multiplication with MiniBuffer and {type(other)}."

        return self.mul(other)

    def __truediv__(self, other):
        assert isinstance(other, MiniBuffer), f"Cannot perform division with MiniBuffer and {type(other)}."

        return self.div(other)
    
    def __pow__(self, other):
        assert isinstance(other, MiniBuffer), f"Cannot perform exponentiation with MiniBuffer and {type(other)}."

        return self.pow(other)

    def __lt__(self, other):
        assert isinstance(other, (int, float)), f"Invalid type for Tesnor less-than: {type(other)}. Expected int or float."
        if isinstance(other, int):
            other = float(other)

        return self.is_elementwise_less_than(other)
    
    def __gt__(self, other):
        assert isinstance(other, (int, float)), f"Invalid type for Tesnor greater-than: {type(other)}. Expected int or float."
        if isinstance(other, int):
            other = float(other)

        return self.is_elementwise_greater_than(other)


    #* Utility

    def is_scalar(self) -> bool:
        return len(self.shape) == 1

    def is_square(self) -> bool:
        assert len(self.shape) >= 2, f"Cannot check for squareness on a {len(self.shape)}D Tensor. Expected 2D or higher."
        return self.shape[-2] == self.shape[-1]

    def __getitem__(self, keys: tuple[int, ...]) -> list[float]:
        item_pos = 0

        for dim_idx, key in enumerate(keys):
            item_pos += self.strides[dim_idx] * key
            
        return self.data[item_pos]

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        repr = str("[")

        repr += MiniBuffer._traverse_dims_and_repr(0,
                                                   0,
                                                   self)
        
        repr += "]"

        return repr

    #* Helper methods

    #* Helper static methods
    
    @staticmethod
    def get_strides_from_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
        strides = ()
        shape_len = len(shape)

        for dim_idx in range(shape_len):
            # Stride for each dimension is calculated by taking the product 
            # of all the dimension sizes (shapes) proceeding it. The last
            # dimension always has a stride of 1.
            if dim_idx == (shape_len - 1):
                strides += (1,)
            else:
                strides += (math.prod(shape[dim_idx + 1:]),)

        return strides

    #? NOTE: Mirko, 24. 12. 2023
    #  This function iterates over the elements of all provided dimensions 
    # (taken from 'current_shape' which starts as the shape of the operand)
    # and performs the following:
    # Check if we've reached  the last dimension -> that's where the values
    # are! We iterate over the values and append them to the output list.
    # Otherwise, we iterate over the elements of the current (non-last)
    # dimension and recursively call this function with the depth_idx
    # (essentialy used for tracking recursion depth) incremented.
    # All of the calls to this function return a list of floats
    # which we can just append to the initial empty list.
    @staticmethod
    def _traverse_dims_and_apply_op(depth_idx: int,
                                    current_positions: tuple[int, ...],
                                    op: UnaryOp | BinaryOp,
                                    *operands: MiniBuffer) -> list[float]:
        out_data = []

        if depth_idx == len(operands[0].shape) - 1:
            for val_idx in range(operands[0].shape[depth_idx]):
                x_val_pos = current_positions[0] + val_idx * operands[0].strides[depth_idx]
            
                if isinstance(op, MiniBuffer.UnaryOp):
                    out_data.append(MiniBuffer._apply_op_unary(op, 
                                                               operands[0].data[x_val_pos]))
                elif isinstance(op, MiniBuffer.BinaryOp):
                    y_val_pos = current_positions[1] + val_idx * operands[1].strides[depth_idx]
                    out_data.append(MiniBuffer._apply_op_binary(op, 
                                                                operands[0].data[x_val_pos],
                                                                operands[1].data[y_val_pos]))
                else:
                    assert False, f"Invalid operation: {op}."
        else:
            for dim_idx in range(operands[0].shape[depth_idx]):
                x_pos = current_positions[0] + dim_idx * operands[0].strides[depth_idx]
                next_pos = (x_pos, )

                if isinstance(op, MiniBuffer.BinaryOp):
                    y_pos = current_positions[1] + dim_idx * operands[1].strides[depth_idx]
                    next_pos += (y_pos, )

                out_data += MiniBuffer._traverse_dims_and_apply_op(depth_idx + 1,
                                                                   next_pos,
                                                                   op,
                                                                   *operands)
        
        return out_data

    @staticmethod
    def _traverse_dims_and_sum_along_last(depth_idx: int,
                                          current_position: int,
                                          x: MiniBuffer) -> list[float]:
        out_data = []

        if depth_idx == len(x.shape) - 1:
            sum = 0.0

            for val_idx in range(x.shape[depth_idx]):
                val_pos = current_position + val_idx * x.strides[depth_idx]
                sum += x.data[val_pos]

            out_data.append(sum)
        else:
            for dim_idx in range(x.shape[depth_idx]):
                next_pos = current_position +  dim_idx * x.strides[depth_idx]

                out_data += MiniBuffer._traverse_dims_and_sum_along_last(depth_idx + 1,
                                                                         next_pos,
                                                                         x)

        return out_data

    @staticmethod
    def _traverse_dims_and_apply_reshape_op(depth_idx: int,
                                            current_position: int,
                                            op: ReshapeOp,
                                            new_shape: tuple[int, ...],
                                            x: MiniBuffer) -> list[float]:
        out_data = []

        if depth_idx == len(new_shape) - 1:
            if op == MiniBuffer.ReshapeOp.PAD:
                current_dim = MiniBuffer._pad(depth_idx, 
                                              current_position, 
                                              new_shape, 
                                              x)
            elif op == MiniBuffer.ReshapeOp.SHRINK:
                current_dim = MiniBuffer._shrink(depth_idx, 
                                                 current_position, 
                                                 new_shape, 
                                                 x)
            else:
                assert False, f"Invalid operation: {op}."
            
            out_data += current_dim
        else:
            for dim_idx in range(new_shape[depth_idx]):
                next_pos = current_position + dim_idx * x.strides[depth_idx]
                out_data += MiniBuffer._traverse_dims_and_apply_reshape_op(depth_idx + 1,
                                                                           next_pos,
                                                                           op,
                                                                           new_shape,
                                                                           x)
        
        return out_data

    @staticmethod
    def _traverse_dims_and_compare(depth_idx: int,
                                   current_position: tuple[int, int],
                                   x: MiniBuffer,
                                   target: MiniBuffer) -> bool:
        if depth_idx == len(x.shape) - 1:
            return MiniBuffer._compare(depth_idx,
                                       current_position,
                                       x,
                                       target)
        else:
            for dim_idx in range(x.shape[depth_idx]):
                x_pos = current_position + dim_idx * x.strides[depth_idx]
                target_pos = dim_idx * target.strides[depth_idx]
                next_pos = (x_pos, target_pos)

                return MiniBuffer._traverse_dims_and_compare(depth_idx + 1,
                                                             next_pos,
                                                             x,
                                                             target)

    @staticmethod
    def _traverse_dims_and_compare_elementwise(depth_idx: int,
                                               current_position: int,
                                               op: CmpOp,
                                               x: MiniBuffer,
                                               target: float) -> bool:
        out_data = []

        if depth_idx == len(x.shape) - 1:
            for val_idx in range(x.shape[depth_idx]):
                val_pos = current_position + val_idx * x.strides[depth_idx]

                if op == MiniBuffer.CmpOp.LT:
                    out_data.append(x.data[val_pos] < target)
                elif op == MiniBuffer.CmpOp.EQ:
                    out_data.append(x.data[val_pos] == target)
                elif op == MiniBuffer.CmpOp.GT:
                    out_data.append(x.data[val_pos] > target)
                else:
                    assert False, f"Invalid operation: {op}."
        else:
            for dim_idx in range(x.shape[depth_idx]):
                next_pos = current_position + dim_idx * x.strides[depth_idx]
                out_data += MiniBuffer._traverse_dims_and_compare_elementwise(depth_idx + 1,
                                                                              next_pos,
                                                                              op,
                                                                              x,
                                                                              target)
        
        return out_data

    @staticmethod
    def _traverse_dims_and_masked_fill(depth_idx: int,
                                       current_position: int,
                                       mask: list[bool],
                                       value: float,
                                       x: MiniBuffer) -> list[float]:
        out_data = []

        if depth_idx == len(x.shape) - 1:
            for val_idx in range(x.shape[depth_idx]):
                val_pos = current_position + val_idx * x.strides[depth_idx]
                should_fill = mask[val_pos]
                
                if should_fill:
                    out_data.append(value)
                else:
                    out_data.append(x.data[val_pos])
        else:
            for dim_idx in range(x.shape[depth_idx]):
                next_pos = current_position + dim_idx * x.strides[depth_idx]
                out_data += MiniBuffer._traverse_dims_and_masked_fill(depth_idx + 1,
                                                                      next_pos,
                                                                      mask,
                                                                      value,
                                                                      x)
        
        return out_data

    @staticmethod
    def _traverse_dims_and_tril(depth_idx: int,
                                current_position: int,
                                diagonal: str,
                                x: MiniBuffer) -> list[float]:
        out_data = []

        if depth_idx == len(x.shape) - 2:
                out_data += MiniBuffer._tril(depth_idx,
                                             current_position,
                                             diagonal,
                                             x)
        else:
            for dim_idx in range(x.shape[depth_idx]):
                next_pos = current_position + dim_idx * x.strides[depth_idx]
                out_data += MiniBuffer._traverse_dims_and_tril(depth_idx + 1,
                                                               next_pos,
                                                               diagonal,
                                                               x)
        
        return out_data

    @staticmethod
    def _apply_op_unary(op: MiniBuffer.UnaryOp, x: float) -> float:
        if op == MiniBuffer.UnaryOp.NEG:
            return -x
        elif op == MiniBuffer.UnaryOp.LOG:
            return math.log(x, math.e)
        elif op == MiniBuffer.UnaryOp.LOG2:
            return math.log(x, 2)
        else:
            assert False, f"Reshape operation {type(op)} is not supported."

    @staticmethod
    def _apply_op_binary(op: MiniBuffer.BinaryOp, x: float, y: float) -> MiniBuffer:
        if op == MiniBuffer.BinaryOp.ADD:
            return x + y
        elif op == MiniBuffer.BinaryOp.SUB:
            return x - y
        elif op == MiniBuffer.BinaryOp.MUL:
            return x * y
        elif op == MiniBuffer.BinaryOp.DIV:
            return x / y
        elif op == MiniBuffer.BinaryOp.POW:
            return x ** y
        elif op == MiniBuffer.BinaryOp.MAX:
            return max(x, y)
        else:
            assert False, f"Reshape operation {type(op)} is not supported."

    @staticmethod
    def _pad(depth_idx: int,
             current_position: int,
             new_shape: tuple[int, ...],
             x: MiniBuffer) -> list[float]:
        current_dim = []

        for val_idx in range(new_shape[depth_idx]):
            val_pos = current_position + val_idx * x.strides[depth_idx]
                
            if val_idx < x.shape[depth_idx] and val_pos < len(x.data):
                current_dim.append(x.data[val_pos])
            else:
                current_dim.append(0.0)

        return current_dim

    @staticmethod
    def _shrink(depth_idx: int,
                current_position: int,
                new_shape: tuple[int, ...],
                x: MiniBuffer) -> list[float]:
        current_dim = []

        for val_idx in range(new_shape[depth_idx]):
            val_pos = current_position + val_idx * x.strides[depth_idx]

            if len(current_dim) < new_shape[depth_idx]:
                current_dim.append(x.data[val_pos])

        return current_dim

    @staticmethod
    def _compare(depth_idx: int,
                 current_positions: tuple[int, int],
                 x: MiniBuffer,
                 target: MiniBuffer) -> bool:
        for val_idx in range(x.shape[depth_idx]):
            val_pos = current_positions[0] + val_idx * x.strides[depth_idx]
            target_pos = current_positions[1] + val_idx * target.strides[depth_idx]

            if x.data[val_pos] != target.data[target_pos]:
                return False

        return True

    #? NOTE: Mirko, 24. 12. 2023 
    # This only works with contiguous MiniBuffers, so
    # you better make sure to keep them contiguous at
    # all times.
    def _tril(depth_idx: int,
              current_position: int,
              diagonal: int,
              x: MiniBuffer) -> list[float]:
        out_data = []
        tril_cursor = 1 + diagonal

        for row_idx in range(x.shape[depth_idx]):
            out_row = []
            row_pos = current_position + row_idx * x.strides[depth_idx]

            for val_idx in range(x.shape[depth_idx + 1]):
                val_pos = row_pos + val_idx * x.strides[depth_idx + 1]
                should_keep_value = val_idx < tril_cursor
                out_row.append(x.data[val_pos] if should_keep_value else 0.0)
            
            out_data += out_row
            tril_cursor += 1
            
        return out_data

    @staticmethod
    def _traverse_dims_and_repr(depth_idx: int,
                                current_position: int,
                                x: MiniBuffer) -> str:
        repr = ""

        if depth_idx == len(x.shape) - 1:
            for val_idx in range(x.shape[depth_idx]):
                val_pos = current_position + val_idx * x.strides[depth_idx]
            
                if val_idx == (x.shape[depth_idx] - 1):
                    repr += f"{x.data[val_pos]:.4f}"
                else:
                    repr += f"{x.data[val_pos]:.4f}, "
        else:
            for dim_idx in range(x.shape[depth_idx]):
                # Check if we are at the beginning of the current dimension.
                # If so, add a simple opening bracket. Otherwise, add brackets
                # with spaces for proper alignment and extra newlines for tensors
                # in 3D and higher, for better visibility.
                if dim_idx == 0:
                    repr += "["
                else:
                    repr += " " * depth_idx
                    # Check if we're past 2D and if that is the case,
                    # add a extra newlines for better visibility.
                    if depth_idx + 2 < len(x.shape):
                        # Number of newlines should decrease with the
                        # depth level
                        repr += "\n" * (len(x.shape) - depth_idx - 2)
                        
                    repr += "           ["

                x_pos = current_position + dim_idx * x.strides[depth_idx]
                repr += MiniBuffer._traverse_dims_and_repr(depth_idx + 1,
                                                           x_pos,
                                                           x)
        
                if dim_idx == (x.shape[depth_idx] - 1):
                    repr += "]"
                else:
                    repr += "],\n"

        return repr