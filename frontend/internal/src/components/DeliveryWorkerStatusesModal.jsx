import React from 'react';

import { Button } from 'antd';
import { Icon } from 'antd';
import { Modal } from 'antd';
import { Spin } from 'antd';
import { Tag } from 'antd';
import { Upload } from 'antd';

import { message } from 'antd';

import { Button as BSButton} from 'react-bootstrap';

import RemoteSelect from './RemoteSelect.jsx';

import { SingleJsonFetcher } from '../utils/fetch.jsx';

import { getCookie } from '../utils/cookies.jsx';


class WorkerRow extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            fetching: false,
            error: false,
        }
    }

    fetchStatus = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.assigned_worker_status_url, window.location);
        url.searchParams.set('pk', this.props.pk);

        try {
            let response = await fetch(
                url,
                {
                    headers: new Headers({
                        'X-CSRFToken': getCookie('csrftoken'),
                    }),
                }
            );

            if (response.ok) {
                const body = await response.json();
                if (body.status === 'ok') {
                    this.props.updateRow(this.props.index, body.data);
                    this.setState({ fetching: false });
                    return
                }
            }
        } catch (exception) {
            // nothing to do
        }

        // something goes wrong
        this.setState({ fetching: false, error: true });
    }

    updateWorker = async (action) => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.update_assigned_worker_url, window.location);
        url.searchParams.set('pk', this.props.pk);
        url.searchParams.set('action', action);

        try {
            let response = await fetch(
                url,
                {
                    method: 'POST',
                    headers: new Headers({
                        'X-CSRFToken': getCookie('csrftoken'),
                    }),
                }
            );

            if (response.ok) {
                const body = await response.json();
                if (body.status === 'ok') {
                    if (action === 'delete') {
                        this.props.deleteRow(this.props.index);
                        this.setState({ fetching: false });
                    } else {
                        this.fetchStatus();
                    }
                    return
                } else if (body.status === 'error' && body.message) {
                    message.error({ content: body.message });
                }
            }
        } catch (exception) {
            // nothing to do
        }

        // something goes wrong
        this.setState({ fetching: false, error: true });
    }

    onUploadChange = (data) => {
        if (data.file.status === 'done') {
            this.fetchStatus();
        }
    }

    status = (code) => {
        let text = code;
        let color = null;

        if (code === 'new') {
            text = 'новая';
        } else if (code === 'arrival_checking') {
            text = 'отметка проверяется';
            color = 'blue';
        } else if (code === 'arrival_rejected') {
            text = 'отметка отклонена';
            color = 'orange';
        } else if (code === 'confirmed') {
            text = 'подтверждена';
            color = 'cyan';
        } else if (code === 'arrived') {
            text = 'на месте';
            color = 'lime';
        } else if (code === 'photo_checking') {
            text = 'фото проверяется';
            color = 'blue';
        } else if (code === 'photo_rejected') {
            text = 'фото отклонено';
            color = 'orange';
        } else if (code === 'closed') {
            text = 'выполнена';
            color = 'green';
        }

        return (
            <Tag
                color={color}
            >
                {text}
            </Tag>
        );
    }

    action = (code) => {
        let text = code;
        let action = code;

        if (code === 'new') {
            text = 'подтвердить заявку';
            action = 'set_confirmed';
        } else if (code === 'confirmed') {
            text = 'подтвердить прибытие';
            action = 'set_arrived';
        } else if (code === 'arrived' || code === 'photo_rejected') {
            const url = this.props.urls.attach_photo_url + '?pk=' + this.props.pk;
            return (
                <Upload
                    name='image'
                    action={url}
                    headers={{ 'X-CSRFToken': getCookie('csrftoken') }}
                    showUploadList={false}
                    onChange={this.onUploadChange}
                    multiple={false}
                >
                    <Button
                        size='small'
                    >
                        <Icon type='upload' />добавить фото
                    </Button>
                </Upload>
            );
        } else if (code === 'photo_checking' || code === 'arrival_checking') {
            const url = (
                this.props.urls.photo_checking_url +
                '?pk=' + this.props.delivery_request_pk
            );
            return (
                <a
                    href={url}
                    target='_blank'
                >
                    проверить фото
                </a>
            );
        } else {
            return undefined;
        }

        return (
            <Button
                size='small'
                onClick={() => this.updateWorker(action)}
            >
                {text}
            </Button>
        );
    }

    mapLink = () => {
        if (this.props.latitude) {
            const location = '' + this.props.longitude + ',' + this.props.latitude;
            const url = (
                'https://maps.yandex.ru/?ll=' + location + '&pt=' + location +
                '&z=14'
            );
            return (
                <a
                    href={url}
                    target='_blank'
                >
                    точка прибытия
                </a>
            );
        } else {
            return undefined;
        }
    }

    removeButton = () => {
        return (
            <BSButton
                variant='outline-danger'
                size='sm'
                onClick={() => this.updateWorker('delete')}
            >
                <i className="fa fa-trash"></i>
            </BSButton>
        );
    }

    render() {
        if (this.state.fetching) {
            return (
                <tr>
                    <td/><td/>
                    <td>
                        <Spin
                            size='small'
                            spinning='true'
                            style={{ width: '100%' }}
                        />
                    </td>
                    <td/><td/>
                </tr>
            );
        }

        const worker_url = this.props.urls.worker_url_template.replace(
            '12345',
            this.props.worker_pk
        );

        return (
            <tr>
                <td>
                    <a
                        href={worker_url}
                        target='_blank'
                    >
                        {this.props.name}
                    </a>
                </td>
                <td>
                    {this.props.phone}
                </td>
                <td>
                    {this.status(this.props.status)}
                </td>
                <td>
                    {this.action(this.props.status)}
                </td>
                <td>
                    {this.mapLink()}
                </td>
                <td>
                    {this.removeButton()}
                </td>
            </tr>
        );
    }
}


export class DeliveryWorkerStatusesModal extends React.Component {
    constructor(props) {
        super(props);

        this.fetcher = new SingleJsonFetcher();

        this.state = {
            fetching: false,
            error: false,

            selected_workers: [],
            workers: [],
        }
    }

    onWorkerSelectionBlur = () => {
        this.commitWorkers();
    }

    onWorkerSelectionChange = (value) => {
        this.setState({ selected_workers: value });
    }

    updateRow = (index, data) => {
        this.setState(
            state => {
                state.workers[index] = data;

                return state;
            }
        );
    }

    deleteRow = (index) => {
        this.setState(
            state => {
                state.workers.splice(index, 1);
                return state;
            }
        );
    }

    fetchWorkers = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.assigned_worker_statuses_url, window.location);
        url.searchParams.set('pk', this.props.delivery_request_pk);

        let response = await this.fetcher.fetch(
            url,
            {
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                })
            }
        );
        if (response && response.status === 'ok') {
            this.setState({ fetching: false, workers: response.data });
        } else {
            this.setState({ fetching: false, error: true });
        }
    }

    commitWorkers = async () => {
        const workers = this.state.selected_workers;
        console.log(workers);
        if (workers.length === 0) {
            // nothing to do
            return;
        }

        this.setState({ fetching: true, selected_workers: [] });

        let url = new URL(this.props.urls.update_request_url, window.location);
        url.searchParams.set('pk', this.props.delivery_request_pk);
        url.searchParams.set('field', 'assigned_workers');
        workers.forEach(
            value => {
                url.searchParams.append('value', value.key);
            }
        );

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                }),
            }
        )

        if (response) {
            if (response.status === 'ok') {
                this.fetchWorkers();
                return;
            } else if (response.status === 'error' && response.message) {
                message.error({ content: response.message });
            }
        }

        this.setState({ fetching: false, error: true });
    }

    content = () => {
        if (this.state.error) {
            return 'Что-то пошло не так :(';
        }

        if (this.state.fetching) {
            return (
                <Spin
                    size='large'
                    spinning='true'
                    style={{ width: '100%' }}
                />
            );
        }

        const rows = this.state.workers.map(
            (worker, index) => (
                <WorkerRow
                    index={index}
                    delivery_request_pk={this.props.delivery_request_pk}
                    urls={this.props.urls}
                    {...worker}
                    updateRow={this.updateRow}
                    deleteRow={this.deleteRow}
                />
            )
        );
        return [
            (
                <table
                    className='table rh-table table-hover'
                >
                    <thead>
                        <tr>
                            <th className='text-center'>ФИО</th>
                            <th className='text-center'>Тел.</th>
                            <th className='text-center'>Статус</th>
                            <th></th>
                            <th></th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            ),
            (
                <RemoteSelect
                    url={this.props.urls.worker_ac_url}
                    width='520px'
                    value={this.state.selected_workers}
                    forward={{
                        delivery_request_pk: this.props.delivery_request_pk,
                    }}
                    extra_select_options={{
                        mode: 'tags',
                        defaultOpen: false,
                        onBlur: this.onWorkerSelectionBlur,
                    }}
                    onChange={this.onWorkerSelectionChange}
                />
            )
        ];
    }

    componentDidMount() {
        this.fetchWorkers();
    }

    render() {
        return (
            <Modal
                visible={this.props.visible}
                title='Статусы рабочих'
                width='640px'
                onCancel={this.props.onCancel}
                footer={null}
            >
                {this.content()}
            </Modal>
        );
    }
}
