from django.utils import timezone

from firebase_admin.exceptions import FirebaseError

from the_redhuman_is.async_utils.push_notifications import send_single_message

from the_redhuman_is.models import (
    DeliveryWorkerFCMToken,
    WorkerPoll,
)


# !!! It's better to be a part of a huey task (see tasks.py)
def try_push_a_question(
        author_id: int,
        worker_id: int,
        question_code: str,
        question_title: str,
        question: str
):

    token = DeliveryWorkerFCMToken.objects.filter(
        user__workeruser__worker_id=worker_id
    ).order_by(
        'timestamp'
    ).last()

    if token == None:
        return

    try:
        send_single_message(
            None,
            None,
            {
                'gt_action': 'gt_poll',
                'gt_title': question_title,
                'gt_text': question,
                'gt_yes_text': 'Да',
                'gt_no_text': 'Нет',
                'gt_question_code': question_code,
            },
            'worker_poll',
            token.token
        )

        WorkerPoll.objects.create(
            author_id=author_id,
            worker_id=worker_id,
            question_code=question_code,
            question_title=question_title,
            question=question,
        )

    except FirebaseError as e:
        pass


def try_register_answer(worker_id: int, question_code: str, answer: str):
    poll = WorkerPoll.objects.filter(
        worker_id=worker_id,
        question_code=question_code,
        answer__isnull=True
    ).order_by(
        'timestamp'
    ).last()

    # Todo: select for update?

    if poll is not None:
        poll.answer_timestamp = timezone.now()
        poll.answer = answer
        poll.save()
