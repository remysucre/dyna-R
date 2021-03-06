from dyna import *

import pytest


# This is a shortcut for writing code quickly where we are going to lookup a method
# so we can write something like `M.add(1,2,3)`
class M(object):
    # TODO?: maybe shouldn't have this return the resulting variable, it feels
    # that from unit tests that it is easier to specify the return variable.
    def __getattribute__(self, n):
        def f(*args):
            ret = interpreter.VariableId(('Ret', object()))
            r = dyna_system.lookup_term((n, len(args)))
            return r(*args, ret=ret), ret
        return f
M = M()


def test_most_basic():
    # X+Y
    rexpr, ret = M.add(1,2)

    frame = interpreter.Frame()
    frame[1] = 7
    frame[2] = 8
    rr = interpreter.simplify(rexpr, frame)

    assert rr == interpreter.Terminal(1)
    assert ret.getValue(frame) == 15


def test_two_add():
    # (X + Y) + Z

    rexpr1, ret1 = M.add(1,2)
    rexpr2, ret2 = M.add(ret1, 3)

    rexpr = Intersect(rexpr1, rexpr2)

    frame = Frame()
    frame[1] = 7
    frame[2] = 8
    frame[3] = 9
    rr = simplify(rexpr, frame)

    assert rr == interpreter.Terminal(1)
    assert ret2.getValue(frame) == 24


def test_simple_range():
    rexpr, ret = M.range(1,2,3)

    r = {ret: constant(True)}
    rexpr = rexpr.rename_vars(lambda x: r.get(x,x))

    frame = Frame()
    frame[1] = 4  # 1 < 4 < 7
    frame[2] = 1
    frame[3] = 7

    rr = simplify(rexpr, frame)
    assert rr == Terminal(1)


def test_sum_aggregator():
    # f(X, Y) += R for R:X..Y.
    v1,v2,v3,v4 = variables_named(1,2,3,4)

    rexpr, ret1 = M.range(v1,v2,v3)
    rexpr = Aggregator(v4, (v2,v3), v1, AggregatorOpImpl(lambda a,b: a+b), rexpr)

    r = {ret1: constant(True)}
    rexpr = rexpr.rename_vars(lambda x: r.get(x,x))

    frame = Frame()
    v2.setValue(frame, 1)
    v3.setValue(frame, 4)

    rr = simplify(rexpr, frame)

    assert rr == Terminal(1)
    assert v4.getValue(frame) == 6


def test_basic_union():
    # f(X) += R for R:1..X.
    # f(X) += R for R:X..20.

    a1, r1, lret = variables_named(1, 2, 3)

    rexpr1, ret1 = M.range(lret, constant(1), a1)
    rexpr2, ret2 = M.range(lret, a1, constant(20))

    rpart = Partition((a1, lret), (rexpr1, rexpr2))

    rexpr = Aggregator(r1, (a1,), lret, AggregatorOpImpl(lambda x,y: x+y), rpart)
    r = {ret1: constant(True), ret2: constant(True)}
    rexpr = rexpr.rename_vars(lambda x: r.get(x,x))

    frame = Frame()
    a1.setValue(frame, 5)

    rr = simplify(rexpr, frame)

    assert rr == Terminal(1)

    assert r1.getValue(frame) == 190


def test_overlap_union():
    # f(X) += R for R:1..X*2.
    # f(X) += R for R:X..20.

    a1, r1, lret = variables_named(1, 2, 3)

    rexpr_mul, a2mul = M.mul(constant(2), a1)
    rexpr1, ret1 = M.range(lret, constant(1), a2mul)
    rexpr1 = Intersect(rexpr1, rexpr_mul)
    rexpr2, ret2 = M.range(lret, a1, constant(20))

    rpart = Partition((a1, lret), (rexpr1, rexpr2))

    rexpr = Aggregator(r1, (a1,), lret, AggregatorOpImpl(lambda x,y: x+y), rpart)
    r = {ret1: constant(True), ret2: constant(True)}
    rexpr = rexpr.rename_vars(lambda x: r.get(x,x))

    x = 5

    frame = Frame()
    a1.setValue(frame, x)

    rr = simplify(rexpr, frame)

    assert rr == Terminal(1)

    rv = sum(range(1, 2*x)) + sum(range(x, 20))

    assert r1.getValue(frame) == rv


def test_basic_term():
    # a = &x(1,2), a=&x(X, Y).

    a,x,y = variables_named(1,2,3)

    rexpr = BuildStructure('x', constant(Term('x', (1, 2))), (x, y))

    frame = Frame()
    rr = simplify(rexpr, frame)

    assert rr == Terminal(1)
    assert x.getValue(frame) == 1
    assert y.getValue(frame) == 2


def test_basic_method_call():
    add_call = dyna_system.call_term('add', 2)

    frame = Frame()
    frame[0] = 1
    frame[1] = 2

    rr = saturate(add_call, frame)
    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == 3


def test_list_length():
    list_len = dyna_system.call_term('list_length', 2)

    lst = Term.fromlist([1,2,3,4])

    frame = Frame()
    frame[1] = lst

    rr = saturate(list_len, frame)
    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == True
    assert frame[0] == 4


from dyna.interpreter import VariableId
#from dyna import dyna_system

# deleteone([Z|Zs], Zs, Z).
# deleteone([X|Xs], [X|Ys], Z) :- deleteone(Xs, Ys, Z).
deleteone =  Intersect(Unify(constant(True), interpreter.ret_variable),
                       Partition(variables_named(0,1,2),
                                 (BuildStructure('.', VariableId(0), (VariableId(2), VariableId(1))),
                                  Intersect(BuildStructure('.', VariableId(0), (VariableId('X'), VariableId('Xs'))),
                                            BuildStructure('.', VariableId(1), (VariableId('X'), VariableId('Ys'))),
                                            dyna_system.call_term('deleteone', 3)(*variables_named('Xs', 'Ys', 2)))
                                 )))
dyna_system.define_term('deleteone', 3, deleteone)

# permutation([], []).
# permutation(A, [Z|Rs]) :- deleteone(A, R, Z), permutation(R, Rs).
permutation = Intersect(Unify(constant(True), interpreter.ret_variable),
                        Partition(variables_named(0,1),
                                  (Intersect(BuildStructure('nil', VariableId(0), ()), BuildStructure('nil', VariableId(1), ())),
                                   Intersect(BuildStructure('.', VariableId(1), variables_named('Z', 'Rs')),
                                             dyna_system.call_term('deleteone', 3)(*variables_named(0, 'R', 'Z')),
                                             dyna_system.call_term('permutation', 2)(*variables_named('R', 'Rs'))
                                ))))
dyna_system.define_term('permutation', 2, permutation)

def test_deleteone():
    deleteone_call = dyna_system.call_term('deleteone', 3)

    frame = Frame()
    frame[0] = Term.fromlist([1,2,3,4])
    frame[2] = 3

    rr = saturate(deleteone_call, frame)
    assert rr == Terminal(1)
    assert frame[1].aslist() == [1,2,4]

def test_deleteone2():
    deleteone_call = dyna_system.call_term('deleteone', 3)

    frame = Frame()
    frame[0] = Term.fromlist([3,4,3])
    frame[2] = 3

    rr = saturate(deleteone_call, frame)

    cnt = 0
    def cntr(a,b):
        nonlocal cnt
        cnt += 1
    loop(rr, frame, cntr)
    assert cnt == 2  # check that the callback was done twice, but didn't check that it got the two distinct values...

def test_deleteone3():
    deleteone_call = dyna_system.call_term('deleteone', 3)

    frame = Frame()
    frame[0] = Term.fromlist([1,2,3,4])

    rr = saturate(deleteone_call, frame)

    cnt = 0
    def cntr(a,b):
        nonlocal cnt
        cnt += 1
    loop(rr, frame, cntr)
    assert cnt == 4  # check that the callback was done twice, but didn't check that it got the two distinct values...


def test_permutation():
    # this needs to loop over the different branches that can be constructed

    permute_call = dyna_system.call_term('permutation', 2)

    lst = Term.fromlist([1,2,3,4])

    frame = Frame()
    frame[0] = lst

    rr = saturate(permute_call, frame)

    # v = rr.children[0].arguments[0]
    # v2 = {v: VariableId('foo')}
    # r2 = rr.rename_vars(lambda x: v2.get(x,x))

    cnt = 0
    def cntr(r, f):
        nonlocal cnt
        cnt += 1
    loop(rr, frame, cntr, till_terminal=True)

    assert cnt == 24

from dyna.builtins import gteq, lteq, sub, add

rrv = variables_named('RR')[0]
fib = Aggregator(interpreter.ret_variable, variables_named(0), rrv, AggregatorOpImpl(lambda a,b: a+b),
Partition(variables_named(0, rrv),
                (Intersect(Unify(constant(0), VariableId(0)), Unify(constant(0), rrv)),  # fib(0) = 0
                 Intersect(Unify(constant(1), VariableId(0)), Unify(constant(1), rrv)),  # fib(1) = 1
                 Intersect(gteq(VariableId(0), constant(2)), lteq(VariableId(0), constant(40)),  # fib(X) = X >= 2, X <= 40, fib(X-1) + fib(X-2).
                           sub(VariableId(0), constant(1), ret=VariableId('Xm1')),
                           sub(VariableId(0), constant(2), ret=VariableId('Xm2')),
                           dyna_system.call_term('fib', 1)(VariableId('Xm1'), ret=VariableId('F1')),
                           dyna_system.call_term('fib', 1)(VariableId('Xm2'), ret=VariableId('F2')),
                           add(VariableId('F1'), VariableId('F2'), ret=rrv)
                 )))
)
dyna_system.define_term('fib', 1, fib)

def test_fib_basic():
    dyna_system.delete_term('fib', 1)
    dyna_system.define_term('fib', 1, fib)

    fib_call = dyna_system.call_term('fib', 1)

    frame = Frame()
    frame[0] = 4

    rr = saturate(fib_call, frame)

    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == 3


def test_fib_unk_memos():
    dyna_system.delete_term('fib', 1)

    fibm = rewrite_to_memoize(fib, is_null_memo=False)

    dyna_system.define_term('fib', 1, fibm)

    dyna_system.run_agenda()

    fib_call = dyna_system.call_term('fib', 1)

    # use a large number to ensure that we are doing stuff with memos
    frame = Frame()
    frame[0] = 30  # because this does the computation on the stack, we end up hitting the recursion depth error if we go too deep

    rr = saturate(fib_call, frame)

    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == 832040



def test_fib_null_memos():
    dyna_system.delete_term('fib', 1)

    fibm = rewrite_to_memoize(fib, is_null_memo=True)

    dyna_system.define_term('fib', 1, fibm)

    dyna_system.run_agenda()

    # going to lookup directly into the memo table to determien what the values are
    mt = fibm.body.memos.memos
    assert len(mt._children) == 41
    assert mt._children[(40, 102334155)] == [Terminal(1)]


def test_fib_null_memos2():
    dyna_system.delete_term('fib', 1)
    dyna_system.define_term('fib', 1, fib)

    dyna_system.memoize_term(('fib', 1))

    fibm = [x for x in dyna_system.lookup_term(('fib', 1)).all_children() if isinstance(x, RMemo)][0]

    dyna_system.run_agenda()

    # going to lookup directly into the memo table to determien what the values are
    mt = fibm.memos.memos
    assert len(mt._children) == 41
    assert mt._children[(40, 102334155)] == [Terminal(1)]


def test_reflect():
    res, name, nargs, alist = variables_named(*'abcd')

    rf = ReflectStructure(res, name, nargs, alist)

    frame = Frame()
    name.setValue(frame, 'test')
    nargs.setValue(frame, 3)

    rr = simplify(rf, frame)

    assert isinstance(rr._children[0], BuildStructure)
    assert rr._children[0].name == 'test'
    assert len(rr._children[0].arguments) == 3


    frame2 = Frame()
    res.setValue(frame2, Term('test', (1,2,3)))

    rr = simplify(rf, frame2)

    assert alist.isBound(frame2)

    assert alist.getValue(frame2) == Term.fromlist([1,2,3])
    assert name.getValue(frame2) == 'test'
    assert nargs.getValue(frame2) == 3


def test_evaluate_reflect():
    ret, name, nargs, alist = variables_named(*'abcd')

    e = Evaluate_reflect(dyna_system, ret, name, nargs, alist)

    dyna_system.define_term('test_foo', 3, Unify(VariableId(0), VariableId(1)))

    frame = Frame()
    name.setValue(frame, 'test_foo')
    nargs.setValue(frame, 3)

    rr = simplify(e, frame)

    # this should be the same unify as the body of test_foo
    assert isinstance(rr._children[0], Unify)

    frame = Frame()
    name.setValue(frame, 'test_no')
    nargs.setValue(frame, 3)

    rr = simplify(e, frame)

    assert rr == Terminal(0)

def test_evaluate_call():
    call = dyna_system.call_term('$call', 2)

    frame = Frame()
    frame[0] = Term('add', (1,))

    rr = simplify(call, frame)

    assert rr.name == 'add'


def test_merge_rules():
    z, rv = variables_named(0, 'RR')

    agg_op = AggregatorOpImpl(lambda a,b: a+b)


    r1 = Aggregator(interpreter.ret_variable, (z,), rv, agg_op,
                    Partition((z, rv),
                              [Unify(z, rv)]))

    dyna_system.add_to_term('merge_rule', 1, r1)

    r2 = Aggregator(interpreter.ret_variable, (z,), rv, agg_op,
                    Partition((z, rv),
                              [add(constant(1), z, ret=rv)]))

    dyna_system.add_to_term('merge_rule', 1, r2)

    mc = dyna_system.call_term('merge_rule', 1)
    frame = Frame()
    z.setValue(frame, 3)

    rr = simplify(mc, frame)

    assert interpreter.ret_variable.getValue(frame) == 7


def test_optimizer1():
    fibo = run_optimizer(fib, variables_named(0,interpreter.ret_variable))

def test_optimizer2():
    # check that we can perform inference on the types of a tuple and use that
    # to perform the approperate reflection and then inline calls.  This should
    # also eleminate excess variables from the expression.

    dyna_system.define_term('opt_call', 2, Intersect(Unify(constant(True), interpreter.ret_variable), Unify(*variables_named(0,1))))  # opt_call(X,X).

    res, sv, a1, a2, sname, snargs, alist = variables_named(*'abcdefg')

    # res = *&opt_call(A1, A2)
    rx = Intersect(BuildStructure('opt_call', sv, (a1, a2)), ReflectStructure(sv, sname, snargs, alist), Evaluate_reflect(dyna_system, res, sname, snargs, alist))

    rr, assumptions = run_optimizer(rx, (a1, a2, res))

    assert set(rr._children) == set((Unify(constant(True), res), Unify(a1,a2)))


def test_optimizer3():

    dyna_system.define_term('opt_call2', 2, Intersect(Unify(constant(True), interpreter.ret_variable), Unify(*variables_named(0,1))))  # opt_call(X,X).

    res, sv, a1, a2, sname, snargs, alist = variables_named(*'abcdefg')

    # res = *&opt_call(A1, 7).
    rx = Intersect(BuildStructure('opt_call2', sv, (a1, constant(7))), ReflectStructure(sv, sname, snargs, alist), Evaluate_reflect(dyna_system, res, sname, snargs, alist))

    rr, assumptions = run_optimizer(rx, (a1, a2, res))

    # there should just be two unify expressions with constants
    assert set(rr._children) == set((Unify(constant(True), res), Unify(a1,constant(7))))


def test_optimizer4():
    # the occurs check performed by the optimizer

    a, b = variables_named(*'ab')

    # X = s(s(X))
    rx = Intersect(BuildStructure('s', a, (b,)), BuildStructure('s', b, (a,)))

    rr, assumptions = run_optimizer(rx, (a,b))

    assert rr == Terminal(0)


def test_optimizer5():
    dyna_system.add_rules("""
    f_bar(X) = &bar(X).
    f_dbaz(&baz(X)) = X.
    f_barbaz(X) = f_dbaz(f_bar(X)).
    """)

    #dyna_system.optimize_term(('f_barbaz', 1))
    dyna_system.optimize_term(('f_barbaz', 1))
    dyna_system.run_agenda()

    # this should get that the result is empty, as the intersection of the two different build structures does not work
    # though we have to remove the aggregator to be able to figure this out

    r = dyna_system.call_term('f_barbaz', 1)
    r = simplify(r, Frame())

    assert r == Terminal(0)


def test_even_odd():
    even = Intersect(Unify(interpreter.ret_variable, constant(True)),
                           Partition(variables_named(0),
                                     (BuildStructure('nil', VariableId(0), ()),  # even([]).
                                      Intersect(BuildStructure('.', VariableId(0), (VariableId('J1'), VariableId('L'))),  # even([X,Y|Xs]) :- even(Xs).
                                                BuildStructure('.', VariableId('L'), (VariableId('J2'), VariableId('Ls'))),
                                                dyna_system.call_term('even_list', 1)(VariableId('Ls')))
                                      )))

    dyna_system.define_term('even_list', 1, even)

    odd = Intersect(Unify(interpreter.ret_variable, constant(True)),
                    BuildStructure('.', VariableId(0), (VariableId('X'), VariableId('Xs'))),
                    dyna_system.call_term('even_list', 1)(VariableId('Xs')))

    dyna_system.define_term('odd_list', 1, odd)


    el = Term.fromlist([1,2,3,4,5,6,7,8,9,10])
    ol = Term.fromlist([1,2,3])


    frame = Frame()
    frame[0] = el
    assert saturate(even, frame) == Terminal(1)

    frame = Frame()
    frame[0] = ol
    assert saturate(even, frame) == Terminal(0)

    frame = Frame()
    frame[0] = ol
    assert saturate(odd, frame) == Terminal(1)

    combined = Intersect(even(0), odd(0))  # combine the two rules, if we can identify that the states are the same then this should just be empty

    frame = Frame()
    rr = saturate(combined, frame)
    assert not rr.isEmpty()

    rx, assumptions = run_optimizer(combined, variables_named(0))

    # at this point, the optimizer would have pushed more tasks to the agenda to
    # try the recursive parts.  Those will eventually identify that this can not
    # hit a base case, and thus will mark it as terminal(0)
    dyna_system.run_agenda()

    frame = Frame()
    rr2 = saturate(rx, frame)

    assert rr2 == Terminal(0)


def test_even_odd_parser():
    from dyna.syntax.normalizer import add_rules

    c = """
    even_list_p([]).
    even_list_p([X,Y|Z]) :- even_list_p(Z).
    odd_list_p([X|Y]) :- even_list_p(Y).
    even_odd_list_p(X) :- even_list_p(X), odd_list_p(X).
    """
    for l in c.split('\n'):
        add_rules(l)

    #dyna_system._optimize_term(('even_odd_list_p', 1))
    dyna_system.optimize_system()
    dyna_system.run_agenda()

    call = dyna_system.call_term('even_odd_list_p', 1)
    frame = Frame()
    rr = saturate(call, frame)

    assert rr == Terminal(0)



def test_mapl_neural_network():
    ret_variable = interpreter.ret_variable

    add_agg = AggregatorOpImpl(lambda a,b: a+b)
    eq_agg = AggregatorOpImpl(lambda a,b: 1/0)  # error if there are more than one key


    ws = [(0,2),
         (-1,3),
         (1,5)]
    weights = Aggregator(ret_variable, (VariableId(0),), VariableId('RR_inp2'), eq_agg,
                         Partition((VariableId(0), VariableId('RR_inp2')),
                                   [Intersect(Unify(VariableId(0), constant(w[0])),
                                              Unify(VariableId('RR_inp2'), constant(w[1]))) for w in ws]))

    dyna_system.define_term('weights', 1, weights)

    # neural_input(&inp(X)) = weights(X).
    neural_input = Aggregator(ret_variable, (VariableId(0),), VariableId('RR_inp'), eq_agg,
                              Intersect(BuildStructure('inp', VariableId(0), (VariableId('X'),)),
                                        dyna_system.call_term('weights', 1)(VariableId('X'), ret=VariableId('RR_inp'))))

    dyna_system.define_term('neural_input', 1, neural_input)

    # neural_output(X) += neural_edge(X, Y) * neural_input(Y).
    neural_output = Aggregator(ret_variable, (VariableId(0),), VariableId('RR_out'), add_agg,
                               Intersect(dyna_system.call_term('neural_input', 1)(VariableId('Y'), ret=VariableId('Yr')),
                                         dyna_system.call_term('neural_edge', 2)(VariableId(0), VariableId('Y'), ret=VariableId('Er')),
                                         dyna_system.call_term('*', 2)(VariableId('Er'), VariableId('Yr'), ret=VariableId('RR_out'))))

    dyna_system.define_term('neural_output', 1, neural_output)

    # edge(&out(Y), &inp(X)) = X+Z=Y, weights(Z).
    edge = Aggregator(ret_variable, (VariableId(0), VariableId(1),), VariableId('RR_edge'), eq_agg,
                      Intersect(BuildStructure('inp', VariableId(1), (VariableId('X'),)),
                                BuildStructure('out', VariableId(0), (VariableId('Y'),)),
                                dyna_system.call_term('+', 2)(VariableId('X'), VariableId('Zweight'), ret=VariableId('Y')),
                                dyna_system.call_term('weights', 1)(VariableId('Zweight'), ret=VariableId('RR_edge'))
                      ))

    dyna_system.define_term('neural_edge', 2, edge)


    eo = neural_output #dyna_system.call_term('neural_edge', 2)

    true_values = {0: 34, -1: 12, 1: 20, -2: 9, 2: 25}

    if 1:
        frame = Frame()
        vs = {}
        def cb(R, frame):
            assert isinstance(R, Terminal)
            vs[frame[0].arguments[0]] = ret_variable.getValue(frame)
            #import ipdb; ipdb.set_trace()

        eo = saturate(eo, frame)
        #re,_ = run_optimizer(eo, (VariableId(0), ret_variable))

        #zz = interpreter.make_aggregator_loopable(eo, frame)
        zz = eo

        loop(zz, frame, cb, best_effort=True)

        assert vs == true_values

    for k in true_values.keys():
        frame = Frame()
        frame[0] = Term('out', (k,))

        rr = saturate(eo, frame)

        assert rr == Terminal(1)
        assert ret_variable.getValue(frame) == true_values[k]


def test_safety_planning1():

    from dyna.syntax.normalizer import add_rules

    add_rules("""
    poly(X, [], 0).
    poly(X, [A|As], F) :- poly(X, As, Q), F is X*Q + A.

    factorial(0, 1).
    factorial(N, F) :- F is N*Q, factorial(N-1, Q).

    goal_delayed :- X > 7.  % these delayed constraints can't be processed

    sp_fib(X) = 0.
    """)

    # check what mode we could enumerate these variables.

    sp = dyna_system.safety_planner

    call_poly = dyna_system.call_term('poly', 3)
    out_mode, has_delayed, is_finite = sp(call_poly, variables_named(0,1,2,interpreter.ret_variable), (False,True,True,False))
    assert out_mode == (False,True,True,True)  # the variable X should still be unbound
    assert has_delayed
    assert not is_finite

    call_fact = dyna_system.call_term('factorial', 2)
    out_fact, has_delayed, is_finite = sp(call_fact, variables_named(0,1,interpreter.ret_variable), (True,False,False))

    assert out_fact == (True,True,True)
    assert not has_delayed
    assert not is_finite

    call_goal_delayed = dyna_system.call_term('goal_delayed', 0)
    out_delayed, has_delayed, is_finite = sp(call_goal_delayed, (), ())
    assert out_delayed == ()
    assert has_delayed
    assert is_finite

    # call_sp_fib = dyna_system.call_term('sp_fib', 1)
    # out_fib, has_delayed, is_finite = sp(call_sp_fib,
    #                                      variables_named(0, interpreter.ret_variable), (True, False))
    # assert out_fib == (True, True)
    # assert has_delayed
    # assert is_finite


    # call_deleteone = dyna_system.call_term('deleteone', 3)
    # out_delayed, has_delayed = sp(call_deleteone, variables_named(0,1,2), (False,False,False))
    # import ipdb; ipdb.set_trace()




def test_compiler1():
    # simplest version of the compiler that returns fully ground
    add3 = Intersect(add('x', 2, ret=interpreter.ret_variable), add(0,1,ret='x'))

    dyna_system.define_term('add3', 3, add3)

    # compile the expression that the
    dyna_system._compile_term(('add3', 3), set(variables_named(0,1,2)))

    call_add3 = dyna_system.call_term('add3', 3)

    frame = Frame()
    r = simplify(call_add3, frame)

    frame[0] = 1
    frame[1] = 2
    frame[2] = 3

    rr = simplify(r, frame)

    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == 6


def test_compiler2():
    # compiler that returns an inequality constraint between some variable and some new introduced variable
    inequ3 = Intersect(gteq(0, 'x'), add(1,2,ret='x'), Unify(constant(True), interpreter.ret_variable))  # f(A,B,C) :- A >= B + C.

    dyna_system.define_term('inequ3', 3, inequ3)
    dyna_system._compile_term(('inequ3', 3), set(variables_named(1,2)))  # compile the mode (-,+,+)

    frame = Frame()
    r = simplify(dyna_system.call_term('inequ3', 3), frame)

    frame[1] = 1
    frame[2] = 3

    rr = simplify(r, frame)

    assert rr._tuple_rep()[0:2] == ('ModedOp', 'lteq')
    assert 4 in frame.values()  # that there is some new variable that contains the sum of 1+3


def test_compiler3():
    # generation of a loop, using the range expression and an aggregator

    # f(X, Y) += Z for Z:X..Y.
    srange = Aggregator(interpreter.ret_variable, variables_named(0,1), VariableId('RR'), AggregatorOpImpl(lambda a,b:a+b),
                        dyna_system.call_term('range', 3)(VariableId('RR'), 0, 1))

    dyna_system.define_term('comp_range', 2, srange)
    dyna_system._optimize_term(('comp_range', 2))  # make this optimize so that the range call is embedded

    dyna_system._compile_term(('comp_range', 2), set(variables_named(0,1)))  # compiling for the fully ground mode

    frame = Frame()
    r = simplify(dyna_system.call_term('comp_range', 2), frame)

    frame[0] = 3
    frame[1] = 7

    rr = simplify(r, frame)

    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == sum(range(3,7))


def test_compiler4():
    # testing of unification failure inside of the compiler

    # f(X, Y) += Z for Z:X..Y, Z < 8.
    srange2 = Aggregator(interpreter.ret_variable, variables_named(0,1), VariableId('RR'), AggregatorOpImpl(lambda a,b:a+b),
                         Intersect(dyna_system.call_term('range', 3)(VariableId('RR'), 0, 1),
                                   dyna_system.call_term('<', 2)(VariableId('RR'), constant(8))))

    dyna_system.define_term('comp_range2', 2, srange2)
    dyna_system._optimize_term(('comp_range2', 2))  # make this optimize so that the range call is embedded

    dyna_system._compile_term(('comp_range2', 2), set(variables_named(0,1)))  # compiling for the fully ground mode

    frame = Frame()
    r = simplify(dyna_system.call_term('comp_range2', 2), frame)

    frame[0] = 3
    frame[1] = 15

    rr = simplify(r, frame)

    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == sum(range(3,8))


def test_compiler5():
    # testing partitiosn that might be overlapping

    # f(X, Y) += I for I:X...(2*Y) I < 8.
    # f(X, Y) += I for I:X...Y, I > 5.
    srange5 = Aggregator(interpreter.ret_variable, variables_named(0,1), VariableId('RR'), AggregatorOpImpl(lambda a,b:a+b),
                         Partition(variables_named(0,1,'RR'),
                                   [
                                       Intersect(dyna_system.call_term('*', 2)(1, constant(2), ret='mm'),
                                           dyna_system.call_term('range', 3)(VariableId('RR'), 0, 'mm'),
                                                 dyna_system.call_term('<', 2)(VariableId('RR'), constant(8))),
                                       Intersect(dyna_system.call_term('range', 3)(VariableId('RR'), 0, 1),
                                                 dyna_system.call_term('>', 2)(VariableId('RR'), constant(5))),
                                   ]))


    dyna_system.define_term('comp_range5', 2, srange5)
    dyna_system._optimize_term(('comp_range5', 2))

    dyna_system._compile_term(('comp_range5', 2), set(variables_named(0,1)))

    frame = Frame()
    r = simplify(dyna_system.call_term('comp_range5', 2), frame)

    frame[0] = 3
    frame[1] = 15

    rr = simplify(r, frame)

    assert rr == Terminal(1)
    assert interpreter.ret_variable.getValue(frame) == sum(range(3,8)) + sum(range(6,15))


@pytest.mark.xfail
def test_compiler6():
    #return  # TODO: need to handle recursive methods

    # test compiling the recursive definition of fib
    rrv = variables_named('RR')[0]
    fib = Aggregator(interpreter.ret_variable, variables_named(0), rrv, AggregatorOpImpl(lambda a,b: a+b),
    Partition(variables_named(0, rrv),
                    (Intersect(Unify(constant(0), VariableId(0)), Unify(constant(0), rrv)),  # fib(0) = 0
                     Intersect(Unify(constant(1), VariableId(0)), Unify(constant(1), rrv)),  # fib(1) = 1
                     Intersect(gteq(VariableId(0), constant(2)), lteq(VariableId(0), constant(40)),  # fib(X) = X >= 2, X <= 40, fib(X-1) + fib(X-2).
                               sub(VariableId(0), constant(1), ret=VariableId('Xm1')),
                               sub(VariableId(0), constant(2), ret=VariableId('Xm2')),
                               dyna_system.call_term('fib_comp', 1)(VariableId('Xm1'), ret=VariableId('F1')),
                               dyna_system.call_term('fib_comp', 1)(VariableId('Xm2'), ret=VariableId('F2')),
                               add(VariableId('F1'), VariableId('F2'), ret=rrv)
                     )))
    )
    dyna_system.define_term('fib_comp', 1, fib)

    dyna_system._optimize_term(('fib_comp', 1))
    dyna_system._compile_term(('fib_comp', 1), set(variables_named(0)))


def test_compiler7():
    # test reading memoized values.  For now will not allow for the memoized
    # values to return delayed R-exprs, rather this will
    pass


def test_compiler8_structure():
    return

    from dyna.syntax.normalizer import add_rules

    add_rules("""

    """)


@pytest.mark.xfail
def test_counting_custom_int():
    # this test doesn't work as it can't get an iterator over the X variable at
    # the start.  The backchaining that is required would construct an infinite
    # iterator, and the current backchaining rules are preventing this from
    # going all the way to the base case.  It also wouldn't know that the base
    # case is as that is value dependent.
    #
    # This is basically that it won't run the - -> + mode via backwards chaining
    # as it can't know when it would stop.  So I guess the safety thing in this
    # case is just that we could forward chain this operation, but then it
    # doesn't allow for it to stop once it has observed enough values? (if it
    # could even prove that)
    #
    # This should end up getting marked as mode plannable, but this requires
    # that there is an infinite recursion which means that it likely doesn't
    # terminate.

    from dyna.syntax.normalizer import add_rules

    add_rules("""
    positive_int(1).
    positive_int(X+1) :- X >= 1, positive_int(X).  % parser bug, the last expression is not unified with True when with :-, and thus the X>=1 can't be the last expression

    count_positive_int(Y) += positive_int(X), X < Y, 1.
    """)

    count_call = dyna_system.call_term('count_positive_int', 1)
    frame = Frame()
    frame[0] = 1

    rr = saturate(count_call, frame)

    assert rr == Terminal(1)

    # this problem with backwards chaining also occures with prolog style
    # programs if we follow the top to bottom execution order, eg if we write:
    #
    # peano(s(X)) :- peano(X).
    # peano(z).
    #
    # if we try and run - -> + (which this supports via forward chaining) then
    # it would simply not terminate, as it would just keep backwards as it can
    # keep expanding one more level.  We can think of our system as if it was
    # expanding all of the branches at the same time, so the "non-terminating"
    # branches that prolog would eventually encoutner are something that we
    # encounter "up front"


def test_colon_equals():
    from dyna.syntax.normalizer import add_rules

    add_rules("""
    colon_e(X) := 0.
    colon_e(1) := 1.
    colon_e(Y) := 2 for Y > 7, Y < 10.
    """)

    def c(x):
        colon_e = dyna_system.call_term('colon_e', 1)
        frame = Frame()
        frame[0] = x
        rr = saturate(colon_e, frame)
        assert rr == Terminal(1)
        return interpreter.ret_variable.getValue(frame)

    assert c(1) == 1
    assert c(0) == 0
    assert c(5) == 0
    assert c(8) == 2

def test_aggregator_saturates():
    from dyna.syntax.normalizer import add_rules

    add_rules("""
    agg_saturates |= true for range(X, 0, 1000000000000000000000).  % big number so it should stop the loop early
    """)

    a = dyna_system.call_term('agg_saturates', 0)
    frame = Frame()
    rr = saturate(a, frame)
    assert rr == Terminal(1)

    assert interpreter.ret_variable.getValue(frame) == True


def test_geometric_series():
    from dyna.syntax.normalizer import add_rules

    add_rules("""
    geometric += 1.
    geometric += geometric / 2.
    """)

    dyna_system.memoize_term(('geometric', 0), 'null')

    dyna_system.run_agenda()

    geo = dyna_system.call_term('geometric', 0)
    frame = Frame()
    rr = saturate(geo, frame)

    assert interpreter.ret_variable.getValue(frame) == 2.0



def test_quicksort_optimize():
    from dyna.syntax.normalizer import add_rules

    add_rules("""
    quicksort([X|Xs],Ys) :-
    partition(Xs,X,Left,Right),
    quicksort(Left,Ls),
    quicksort(Right,Rs),
    append(Ls,[X|Rs],Ys).
    quicksort([],[]).

    partition([X|Xs],Y,[X|Ls],Rs) :-
    X <= Y, partition(Xs,Y,Ls,Rs).
    partition([X|Xs],Y,Ls,[X|Rs]) :-
    X > Y, partition(Xs,Y,Ls,Rs).
    partition([],Y,[],[]).
    """)

    #dyna_system._optimize_term(('partition', 4))
    dyna_system._optimize_term(('quicksort', 2))
    dyna_system.run_agenda()

    qs = dyna_system.call_term('quicksort', 2)
    frame = Frame()
    frame[0] = Term.fromlist([3,1,2])
    rr = saturate(qs, frame)

    assert rr == Terminal(1)


def test_watching_terms():
    counter = 0
    def cb(msg):
        nonlocal counter
        assert msg.key == (123,456)
        print(msg)
        counter += 1

    w = dyna_system.watch_term_changes(('test_term_watch', 1), cb)

    from dyna.syntax.normalizer import add_rules
    dyna_system.run_agenda()

    add_rules("""
    test_term_watch(123) = 456.
    """)
    dyna_system.run_agenda()

    assert counter == 1


def test_memo_defaults():
    from dyna.syntax.normalizer import add_rules

    add_rules("""
    fib_defaulting(X) += fib_defaulting(X - 1) + fib_defaulting(X - 2) for X > 1, X < 6.
    fib_defaulting(0) += 0.
    fib_defaulting(1) += 1.

    fib_defaulting(X) += 1.  % make this use a default with adding a value
    """)

    def check():
        w = dyna_system.call_term('fib_defaulting', 1)
        frame = Frame()
        frame[0] = 5

        rr = simplify(w, frame)
        assert rr == Terminal(1)
        assert interpreter.ret_variable.getValue(frame) == 20
    check()

    # make this memoized

    # this does not work as a null memo, as it just keeps embedding the R-expr
    # one more level and this means that it just keeps growing without haivng
    # any meaningful result.
    #
    # So in this case, it could instead identify that the size of the R-expr is
    # continuing to grow and ask if it should just killl the memoized result.
    #  - I suppose that the depth of a R-expr could be a good indicator of something, as well as the depth.
    #    simply having a lot of keys in a memo table would be a large width, though that might be a fine singal in most cases
    #
    # In the case that there is a msg for a null memo table which contains NULL
    # for one of the keys, it should just drop that value as null readable.  As
    # in that case, there is something which is code and not able to partisipate
    # in a join operation.  This might make it so that it would



    # dyna_system.memoize_term(('fib_defaulting', 1), kind='null')
    # dyna_system.run_agenda()

    # check()


def test_type_information_passing():
    from dyna.syntax.normalizer import add_rules

    add_rules("""
    type_r1(&foo(X, Y)).
    type_r2(&bar(Q, R)).

    type_z :- type_r1(X), type_r2(X).
    """)

    z = dyna_system.call_term('type_z', 0)
    frame = Frame()
    rr = saturate(z, frame)
    assert rr == Terminal(0)
