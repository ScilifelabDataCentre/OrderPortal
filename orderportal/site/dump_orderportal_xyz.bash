#!/bin/bash

datum=`date +"%Y-%m-%d"`
dirpath=/home/bupp/bupp_filez/orderportal_xyz
filename=orderportal_xyz_dump_$datum.tar.gz

cd /var/www/apps/xyz/OrderPortal/orderportal
PYTHONPATH=/var/www/apps/xyz/OrderPortal /bin/python2 dump.py -d $filename

# copy to homer for taping
scp -i /root/.ssh/dbbupp $dirpath/$filename backup@backup.scilifelab.se:~/

# remove old dumps
/bin/find $dirpath -type f -ctime +40 -name '*dump*' -delete
