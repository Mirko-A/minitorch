import unittest
import math

import sys
import os
sys.path.append(os.curdir + "\..")

from minigrad import Value

class TestBinaryOps(unittest.TestCase):
    def test_add_two_value_objects(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        v2 = Value(b)
        self.assertEqual((v1 + v2).data, a + b)

    def test_add_value_object_and_scalar(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        self.assertEqual((v1 + b).data, a + b)

    def test_add_scalar_and_value_object(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        self.assertEqual((b + v1).data, a + b)

    def test_sub_two_value_objects(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        v2 = Value(b)
        self.assertEqual((v1 - v2).data, a - b)

    def test_sub_value_object_and_scalar(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        self.assertEqual((v1 - b).data, a - b)

    def test_sub_scalar_and_value_object(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        self.assertEqual((b - v1).data, b - a)

    def test_mul_two_value_objects(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        v2 = Value(b)
        self.assertEqual((v1 * v2).data, a * b)

    def test_mul_value_object_and_scalar(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        self.assertEqual((v1 * b).data, a * b)

    def test_mul_scalar_and_value_object(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        self.assertEqual((b * v1).data, a * b)

    def test_div_two_value_objects(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        v2 = Value(b)
        self.assertEqual((v1 / v2).data, a / b)

    def test_div_value_object_and_scalar(self):
        a = 3.0
        b = 1.5
        v1 = Value(a)
        self.assertEqual((v1 / b).data, a / b)

    def test_div_scalar_and_value_object(self):
        a = 3.0
        v1 = Value(a)
        self.assertEqual((1 / v1).data, 1 / a)

    def test_pow_two_value_objects(self):
        a = 3.0
        b = 2.0
        v1 = Value(a)
        v2 = Value(b)
        self.assertEqual((v1 ** v2).data, a ** b)

    def test_pow_value_object_and_scalar(self):
        a = 3.0
        b = 2.0
        v1 = Value(a)
        self.assertEqual((v1 ** b).data, a ** b)

    def test_pow_scalar_and_value_object(self):
        a = 3.0
        b = 2.0
        v1 = Value(a)
        self.assertEqual((b ** v1).data, b ** a)

class TestUnaryOps(unittest.TestCase):
    def test_neg_value_object(self):
        a = 3.0
        v1 = Value(a)
        self.assertEqual(-v1.data, -a)

class TestActivationFuncs(unittest.TestCase):
    def test_sigmoid(self):
        a = 3.0
        v1 = Value(a)
        self.assertEqual((v1.sigmoid()).data, 1 / (1 + math.exp(-a)))

    def test_relu_below_zero(self):
        a = -3.0
        a_relu = 0
        v1 = Value(a)
        self.assertEqual((v1.relu()).data, a_relu)
    
    def test_relu_above_zero(self):
        a = 3.0
        a_relu = a
        v1 = Value(a)
        self.assertEqual((v1.relu()).data, a_relu)
        
    def test_tanh(self):
        a = 3.0
        v1 = Value(a)
        self.assertEqual((v1.tanh()).data, (math.exp(2*a) - 1) / (math.exp(2*a) + 1))

class TestOtherFuncs(unittest.TestCase):
    def test_exp(self):
        a = 3.0
        v1 = Value(a)
        self.assertEqual((math.e ** v1).data, math.e ** a)

class TestBackwardFuncs(unittest.TestCase):
    def test_add_backward(self):
        a = Value(3.0)
        b = Value(1.7)

        a_grad = b_grad = 1.0

        c = a + b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)
        self.assertEqual(c.grad, 1.0)

    def test_sub_backward_both_value_object(self):
        a = Value(3.0)
        b = Value(1.7)

        a_grad = 1.0
        b_grad = -1.0

        c = a - b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)
        
    def test_sub_backward_first_place_value_object(self):
        a = Value(3.0)
        b = 1.7

        a_grad = 1.0
        b_grad = -1.0

        c = a - b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)
        
    def test_sub_backward_second_place_value_object(self):
        a = 3.0
        b = Value(1.7)

        a_grad = 1.0
        b_grad = -1.0

        c = a - b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)

    def test_mul_backward(self):
        a = Value(3.0)
        b = Value(1.7)

        a_grad = 1.7
        b_grad = 3.0

        c = a * b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)
        
    def test_div_backward_value_object_and_scalar(self):
        a = Value(3.0)
        b = 1.7

        a_grad = 1/1.7
        b_grad = -(3.0 / (1.7 ** 2)) 

        c = a / b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)

    def test_div_backward_scalar_and_value_object(self):
        a = 3.0
        b = Value(1.7)

        a_grad = 1/1.7
        b_grad = -(3.0 / (1.7 ** 2)) 

        c = a / b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)

    def test_div_backward_two_value_objects(self):
        a = Value(3.0)
        b = Value(1.7)

        a_grad = 1/1.7
        b_grad = -(3.0 / (1.7 ** 2)) 

        c = a / b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)

    def test_pow_backward_value_object_and_scalar(self):
        a = Value(3.0)
        b = 1.7

        a_grad = b * (a.data ** (b - 1))
        b_grad = (a.data ** b) * math.log(b)

        c = a ** b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)

    def test_pow_backward_scalar_and_value_object(self):
        a = 3.0
        b = Value(1.7)

        a_grad = b.data * (a ** (b.data - 1))
        b_grad = (a ** b.data) * math.log(b.data)

        c = a ** b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)
        
    def test_pow_backward_two_value_objects(self):
        a = Value(3.0)
        b = Value(1.7)

        a_grad = b.data * (a.data ** (b.data - 1))
        b_grad = (a.data ** b.data) * math.log(b.data)

        c = a ** b
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        self.assertEqual(c._children[1].grad, b_grad)

    def test_sigmoid_backward(self):
        a = Value(2.7)

        def sigmoid_impl(x):
            return 1 / (1 + math.exp(-x))

        a_grad = sigmoid_impl(a.data) * (1 - sigmoid_impl(a.data))

        c = a.sigmoid()
        c.backward()
        
        self.assertEqual(c._children[0].grad, a_grad)

    def test_relu_backward_below_zero(self):
        a = Value(-3.0)
        
        a_grad = 0
        
        c = a.relu()
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        
    def test_relu_backward_above_zero(self):
        a = Value(3.0)
        
        a_grad = 1
        
        c = a.relu()
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)
        
    def test_tanh_backward(self):
        a = Value(3.0)
        
        a_grad = 1 - ((math.exp(2*a.data) - 1) / (math.exp(2*a.data) + 1)) ** 2
        
        c = a.tanh()
        c.backward()
        self.assertEqual(c._children[0].grad, a_grad)

    def test_complex_backward(self):
        a = Value(3.0)
        b = Value(1.7)
        c = Value(0.4)

        d = a * b
        f = d - c

        a_grad = 1.7
        b_grad = 3.0
        c_grad = -1.0
        d_grad = 1.0

        f.backward()
        self.assertEqual(a.grad, a_grad)
        self.assertEqual(b.grad, b_grad)
        self.assertEqual(c.grad, c_grad)
        self.assertEqual(d.grad, d_grad)
        self.assertEqual(f.grad, 1.0)

if __name__ == "__main__":
    unittest.main()