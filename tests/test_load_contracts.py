#!/usr/bin/env python
from warnings import simplefilter; simplefilter('ignore')
from colorama import Style, Fore, init; init()
from pyrpctools import RPC_Client, MAXGAS
from test_node import TestNode
import subprocess
import traceback
import signal
import shutil
import time
import json
import sha3
import os

test_code = {
    'foobar':{
        'sqrt.se':'''\
def sqrt(x):
    with guess = ONE:
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        guess = avg(guess, fdiv(x, guess))
        return(avg(guess, fdiv(x, guess)))

inset('../math_macros.sm')
''',
        'foo.se':'''\
import sqrt as SQRT

def bar(x):
    s = SQRT.sqrt(x)
    return(fdiv(2*s, s - ONE))

inset('../math_macros.sm')
'''},
    'math_macros.sm':'''\
macro ONE: 0x10000000000000000

macro fdiv($a, $b):
    $a*ONE/$b

macro avg($a, $b):
    ($a + $b)/2
'''}

def make_tree(file_tree, dirname=os.getcwd()):
    for name, data in file_tree.items():
        if type(data) == dict: # make a folder, and write its contents to disk
            newdir = os.path.join(dirname, name)
            os.mkdir(newdir)
            make_tree(data, newdir)
        elif type(data) in (str, unicode): #write the text to a file
            with open(os.path.join(dirname, name), 'w') as datafile:
                datafile.write(data)

def test_compile_imports():
    test_dir = os.path.dirname(os.path.realpath(__file__))

    try:
        make_tree(test_code, dirname=test_dir)
    except:
        shutil.rmtree(os.path.join(test_dir, 'foobar'))
        make_tree(test_code, dirname=test_dir)

    node = TestNode(log=open(os.path.join(test_dir,
                                          'test_compile_imports.log'), 
                             'w'))
    node.start()

    try:
        rpc = RPC_Client((node.rpchost, node.rpcport), 0)
        password = os.urandom(32).encode('hex')
        coinbase = rpc.personal_newAccount(password)['result']
        rpc.personal_unlockAccount(coinbase, password, 10**10)
        rpc.miner_start(2)

        gas_price = int(rpc.eth_gasPrice()['result'], 16)
        balance = 0

        print Style.BRIGHT + 'Mining coins...' + Style.RESET_ALL
        while balance/gas_price < int(MAXGAS, 16):
            balance = int(rpc.eth_getBalance(coinbase)['result'], 16)
            time.sleep(1)

        load_contracts = os.path.join(os.path.dirname(test_dir), 'load_contracts.py')

        subprocess.check_call(['python',
                               load_contracts,
                               '-C', test_dir,
                               '-p', '9696',
                               '-b', '2',
                               '-d', 'test_load_contracts.json',
                               '-s', 'foobar'])

        db = json.load(open(os.path.join(test_dir, "test_load_contracts.json")))
        func1 = db['foo']['fullsig'][0]['name']
        prefix = sha3.sha3_256(func1.encode('ascii')).hexdigest()[:8]
        arg = 8
        expected = round((2 * 8**0.5) / (8**0.5 - 1), 6)
        encoded_arg = hex(arg*2**64)[2:].strip('L').rjust(64, '0')
        result = rpc.eth_call(sender=coinbase,
                              to=db['foo']['address'],
                              data=('0x' + prefix + encoded_arg),
                              gas=hex(3*10**6))['result']

        result = int(result, 16)
        if result > 2**255:
            result -= 2**256
    
        #the different internal representations
        #used in the calculations lead to some difference,
        #but the answers should be approximately the same.
        result = round(float(result)/2**64, 6)

        if result == expected:
            print 'TEST PASSED'
        else:
            print 'TEST FAILED: <expected {}> <result {}>'.format(expected, result)
    except Exception as exc:
        traceback.print_exc()
    finally:
        shutil.rmtree(os.path.join(test_dir, 'foobar'))
        os.remove(os.path.join(test_dir, 'math_macros.sm'))
        os.remove(os.path.join(test_dir, 'test_load_contracts.json'))

if __name__ == '__main__':
    test_compile_imports()
