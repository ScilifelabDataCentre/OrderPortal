#!/bin/bash

datum=`date +"%Y-%m-%d"`
dirpath=/home/bupp/bupp_filez/orderportal_xyz
filename=orderportal_xyz_dump_$datum.tar.gz

cd /home/per.kraulis/OrderPortal/orderportal
PYTHONPATH=/home/per.kraulis/OrderPortal /usr/bin/scl enable rh-python36 -- pyth
on cli.py dump -d $dirpath/$filename

# Copy to homer for taping.
scp -i /root/.ssh/dbbupp $dirpath/$filename bupp@homer.scilifelab.se:~/

# Remove old dumps.
/bin/find $dirpath -type f -ctime +40 -name 'orderportal_xyz_dump*' -delete
