#/usr/bin/python3
import logging
import subprocess

CLOUD9_DIRECTORY_BASE = 'debian@192.168.7.2:/var/lib/cloud9/mm-machineapp-template'

def run():
    # Upload your new program to the server
    print('****************************************************************')
    print('**************** Uploading your Machine App ********************')
    print('******** You will be prompted to enter your password ***********')
    print('******************** Password is: temppwd ***********************')
    print('****************************************************************')
    print('Uploading your server/internal program to the MachineMotion...')
    subprocess.run(['scp', './server/internal/*.py', CLOUD9_DIRECTORY_BASE + '/server/internal'])
    print('Internal upload complete.')
    print('Uploading your server program to the MachineMotion...')
    subprocess.run(['scp', './server/*.py', CLOUD9_DIRECTORY_BASE + '/server'])
    print('Server upload complete.')
    print('Uploading your client program to the MachineMotion...')
    subprocess.run(['scp', '-r', './client/*', CLOUD9_DIRECTORY_BASE + '/client/'])
    print('Client upload complete.')


if __name__ == "__main__":
    run()