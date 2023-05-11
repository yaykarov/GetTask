!#@%! У текста ниже весьма спорная актуальность! !%@#!

Обновляем Python до последней версии:

    sudo add-apt-repository ppa:jonathonf/python-3.6
    sudo apt update
    sudo apt dist-upgrade -y
http://ubuntuhandbook.org/index.php/2017/07/install-python-3-6-1-in-ubuntu-16-04-lts/

Проверь версию питона командой `python -V` должна быть `3.6` минимум.

Redis лучше поставить по другому:

    sudo add-apt-repository ppa:chris-lea/redis-server
    sudo apt update
    sudo apt install redis -y

    sudo systemctl daemon-reload
    sudo systemctl start redis

Далее нужно перестроить виртуальное окружение, перейди в папку с виртуальными окружениями и просто удали папку со старым окружением.
Создай заново окружение с тем же именем

    virtualenv --no-site-packages -p /usr/bin/python3 <venv_name>
    source <path_to_venv>/bin/activate

Перейди в папку с проектом вытяни все изменения из репозитария и поставь все необходимые питон пакеты:
    #pip install -r requirements.pip
    python -u manage.py -U -r requirements.pip

Примени последние миграции, собери всю статику и перекинь сессии в редис:

    python -u manage.py migrate
    python -u manage.py collectstatic
    python -u manage.py migrate_sessions_to_redis


Подправь конфиг Nginx:

    server {
        listen 80;
        server_name <domain_host>;

        access_log    /var/log/nginx/redhuman.access.log;
        error_log     /var/log/nginx/redhuman.error.log;

        client_max_body_size  10m;
        root  /<path_to_project_dir>/public;

        location ~ /(media|static)/ {
            try_files  $uri  =404;
            access_log off;
            expires 1y;
        }

        location / {
            try_files $uri @proxy_to_app;
        }

        location @proxy_to_app {
            include     uwsgi_params;
            uwsgi_pass  unix:/var/run/uwsgi/redhuman.sock;
            uwsgi_read_timeout    300s;
        }
    }


не забудь перезапустить nginx

Для перезапуска сайта:

    sudo systemctl restart nginx
    sudo systemctl restart uwsgi
