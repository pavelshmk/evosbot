#!/usr/bin/env bash

if [[ "$PWD" != "/var/www/evosbot" ]]; then
    echo "Project must be located at /var/www/evosbot"
    exit 1
fi

#set -xe

sudo apt install build-essential python3-dev virtualenv nginx postgresql libpq-dev supervisor \
     redis-server python3-dbus libwebp-dev libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libgdk-pixbuf2.0-dev \
     libffi-dev shared-mime-info cmake libdbus-glib-1-dev

git clone https://github.com/aruiz/webp-pixbuf-loader
cd webp-pixbuf-loader
git checkout ddbcacf37d98aeca24429ee2cd975fb804d1f265
cmake .
make
make install
ln -s /usr/local/lib/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-webp.so /usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/
gdk-pixbuf-query-loaders > /usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache
cd ..
rm -rf webp-pixbuf-loader

sudo systemctl enable nginx postgresql supervisor redis-server
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt
sudo su postgres -c 'createuser evosbot'
sudo su postgres -c 'createdb evosbot -O evosbot'
sudo su postgres -c "echo \"alter user evosbot with password 'evosbot';\" | psql"
cp example.env .env
cp nginx.conf /etc/nginx/conf.d/evosbot.conf
cp supervisor.conf /etc/supervisor/conf.d/evosbot.conf

echo "Input domain name (could be changed later in /etc/nginx/conf.d/evosbot.conf)"
read domainname
sed -i "s/_hostname_/$domainname/g" /etc/nginx/conf.d/evosbot.conf

./manage.py collectstatic --noinput
./manage.py migrate
./manage.py createsuperuser

#sudo reboot
