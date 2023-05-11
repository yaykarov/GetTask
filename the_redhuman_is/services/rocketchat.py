import uuid

from django.core.exceptions import ObjectDoesNotExist

from rocketchat_API.rocketchat import RocketChat

from the_redhuman_is.models.chat import (
    WorkerRocketchatVisitor
)

from the_redhuman_is.services import chat_telegram_bot


ROCKETCHAT_URL = None
ROCKETCHAT_USER = None
ROCKETCHAT_PASSWORD = None

try:
    from .rocketchat_local import *
except ImportError:
    pass


chat = None
if ROCKETCHAT_URL is not None:
    chat = RocketChat(
        user=ROCKETCHAT_USER,
        password=ROCKETCHAT_PASSWORD,
        server_url=ROCKETCHAT_URL,
    )


def _create_room(visitor_token):
    room_response = chat.livechat_room(
        token=str(visitor_token),
    )
    room_response.raise_for_status()
    room_data = room_response.json()
    print(room_data)
    return room_data['room']['_id']


def _tranfer_room_to_correct_department(visitor):
    worker = visitor.worker

    try:
        worker_city = worker.workerzone.zone.name
    except ObjectDoesNotExist:
        worker_city = 'Москва'

    departments = chat.call_api_get('livechat/department').json()
    def _department_id(name):
        for department in departments['departments']:
            if department['name'] == name:
                return department['_id']
        return None

    department_id = _department_id(worker_city)
    if department_id is None:
        department_id = _department_id('Москва')

    # Todo: :(
    department_id = _department_id('Москва')

    print(f'department_id is {department_id}')

    if department_id is not None:
        transfer_response = chat.call_api_post(
            'livechat/room.transfer',
            token=str(visitor.rocketchat_visitor_token),
            rid=str(visitor.rocketchat_visitor_room_id),
            department=department_id
        )
        print(transfer_response)
        print(transfer_response.json())


# Todo: errors?
def _init_visitor(worker):
    visitor_token = uuid.uuid4()

    visitor_response = chat.livechat_register_visitor(
        token=str(visitor_token),
        visitor={
            'name': str(worker),
            'phone': worker.tel_number,
        }
    )
    print(visitor_response)
    print(visitor_response.json())

    room_id = _create_room(visitor_token)

    visitor = WorkerRocketchatVisitor.objects.create(
        worker=worker,
        rocketchat_visitor_token=visitor_token,
        rocketchat_visitor_room_id=room_id,
    )

    _tranfer_room_to_correct_department(visitor)

    return visitor


def _do_send_message(visitor, message):
    message_response = chat.livechat_message(
        token=str(visitor.rocketchat_visitor_token),
        rid=str(visitor.rocketchat_visitor_room_id),
        msg=message
    )
    print(message_response)
    print(message_response.json())
    if message_response.status_code == 400:
        data = message_response.json()
        if data.get('error') == 'room-closed':
            room_id = _create_room(visitor.rocketchat_visitor_token)
            visitor.rocketchat_visitor_room_id = room_id
            visitor.save()
            _tranfer_room_to_correct_department(visitor)
            second_message_response = chat.livechat_message(
                token=str(visitor.rocketchat_visitor_token),
                rid=str(visitor.rocketchat_visitor_room_id),
                msg=message
            )
            print(second_message_response)
            print(second_message_response.json())


# Todo: this will fail if the room is closed
def send_message_from_worker(worker, message):
    print(f'sending message "{message}" to worker {worker.pk}/{worker}')

    try:
        visitor = WorkerRocketchatVisitor.objects.get(worker=worker)
    except WorkerRocketchatVisitor.DoesNotExist:
        visitor = _init_visitor(worker)

    _do_send_message(visitor, message)


# Todo: errors
def on_new_agent_message(data):
    try:
        room_id = data['_id']
        visitor_token = uuid.UUID(data['visitor']['token'])

        visitor = WorkerRocketchatVisitor.objects.get(
            rocketchat_visitor_token=visitor_token,
            rocketchat_visitor_room_id=room_id
        )

        for message in data['messages']:
            chat_telegram_bot.send_message_to_worker(visitor.worker, message['msg'])

    # Todo: more specific errors
    except Exception as e:
        print(e)
