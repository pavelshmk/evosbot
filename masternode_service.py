from pathlib import Path

from bottle import request, route, run, abort, auth_basic, post
import dbus


def check(user, pw):
    return user == 'mnusername' and pw == 'mnpassword'


@post('/config')
@auth_basic(check)
def config():
    data = request.json
    if not data or 'content' not in data:
        return abort(400)

    with Path('~/.ParadiseCoin/masternode.conf').expanduser().open('w') as f:
        f.write(data['content'])

    print('masternode.conf was updated')
    return 'OK'


@post('/reload')
@auth_basic(check)
def reload():
    sysbus = dbus.SystemBus()
    systemd1 = sysbus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
    manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
    job = manager.RestartUnit('parad.service', 'fail')
    return 'OK'


if __name__ == '__main__':
    run(host='0.0.0.0', port=8888)
